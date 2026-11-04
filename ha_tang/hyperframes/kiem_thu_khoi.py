"""Công cụ kiểm thử khói tự động cho các khối và thành phần HyperFrames registry."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Literal

# Xác định đường dẫn gốc kho mã nguồn
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SIN_CONTENT_API_DIR = REPO_ROOT / "sin_content_api"
if str(SIN_CONTENT_API_DIR) not in sys.path:
    sys.path.insert(0, str(SIN_CONTENT_API_DIR))

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

from src.modules.tao_video_noi_dung.hf_blocks import THEME_STYLE
from src.modules.tao_video_noi_dung.hf_catalog import CatalogEntry, load_index
from src.modules.tao_video_noi_dung.hf_project import (
    VIETSUB_FONT_PATH,
    _env,
    hyperframes_cli,
)
from src.modules.tao_video_noi_dung.render_engines import _node, engines_dir

# Khóa tránh chạy đồng thời nhiều tiến trình Chrome render trên máy 8 GB RAM
_CHROME_LOCK = threading.Lock()

# Biểu thức chính quy loại bỏ CDN GSAP và phông Google Fonts
_CDN_GSAP = re.compile(
    r'<script[^>]+src="https?://[^"]*(?:gsap|CustomEase)[^"]*"[^>]*></script>\s*',
    re.IGNORECASE,
)
_CDN_FONT = re.compile(
    r'<link[^>]+(?:fonts\.(?:googleapis|gstatic)\.com)[^>]*>\s*',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SmokeResult:
    """Kết quả kiểm thử khói của một khối hoặc thành phần."""
    name: str
    renders: bool
    reason: str
    runtime_errors: int
    layout_errors: int
    seconds: float
    frames: tuple[str, ...]
    external_deps: tuple[str, ...]


def select_names(
    index: dict[str, CatalogEntry] | dict[str, dict],
    nhom: str = "all",
    ca_webgpu: bool = False,
) -> list[str]:
    """Lọc danh sách tên khối theo nhóm, mặc định bỏ qua webgpu và can_anh trừ khi ca_webgpu=True."""
    selected: list[str] = []
    for name, entry in index.items():
        grp = getattr(entry, "group", None)
        if grp is None and isinstance(entry, dict):
            grp = entry.get("group")

        if not ca_webgpu and grp in ("webgpu", "can_anh"):
            continue
        if nhom and nhom != "all" and grp != nhom:
            continue
        selected.append(name)
    return selected


def names_done(jsonl_path: Path | str) -> set[str]:
    """Đọc tập hợp tên khối đã xử lý từ tệp jsonl để tiếp tục (resume)."""
    p = Path(jsonl_path)
    if not p.is_file():
        return set()
    done: set[str] = set()
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if "name" in data and isinstance(data["name"], str):
                    done.add(data["name"])
            except Exception:
                continue
    return done


def write_contact_sheet(results: list[SmokeResult], out_png: Path) -> None:
    """Tạo ảnh bảng liên lạc (contact sheet) dạng lưới từ 2 khung hình đầu tiên của mỗi khối."""
    if Image is None or ImageDraw is None:
        return

    # Lọc các kết quả có khung hình tồn tại thực tế
    valid_items: list[tuple[str, list[Path]]] = []
    for r in results:
        existing = [Path(f) for f in r.frames if Path(f).is_file()]
        if existing:
            valid_items.append((r.name, existing[:2]))

    if not valid_items:
        return

    thumb_w = 320
    thumb_h = 180
    header_h = 28
    padding = 16
    spacing = 10

    cell_w = thumb_w * 2 + spacing
    cell_h = header_h + thumb_h

    cols = 2 if len(valid_items) > 3 else 1
    rows = (len(valid_items) + cols - 1) // cols

    total_w = padding * 2 + cols * cell_w + (cols - 1) * padding
    total_h = padding * 2 + rows * cell_h + (rows - 1) * padding

    sheet = Image.new("RGB", (total_w, total_h), color=(10, 28, 43))
    draw = ImageDraw.Draw(sheet)

    font = None
    try:
        if ImageFont is not None:
            font = ImageFont.load_default()
    except Exception:
        pass

    for idx, (name, frames) in enumerate(valid_items):
        col = idx % cols
        row = idx // cols
        x0 = padding + col * (cell_w + padding)
        y0 = padding + row * (cell_h + padding)

        draw.text((x0 + 4, y0 + 4), name, fill=(246, 239, 224), font=font)

        for f_idx, frame_path in enumerate(frames):
            try:
                with Image.open(frame_path) as im:
                    im_thumb = im.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                    sheet.paste(im_thumb, (x0 + f_idx * (thumb_w + spacing), y0 + header_h))
            except Exception:
                pass

    out_path = Path(out_png)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def smoke_block(
    name: str,
    work_dir: Path,
    aspect: Literal["16:9", "9:16"] = "16:9",
) -> SmokeResult:
    """Thực hiện kiểm thử khói cho một khối trong thư mục tạm, xuất ảnh ra work_dir."""
    t0 = time.perf_counter()
    target_work_dir = Path(work_dir).resolve()
    target_work_dir.mkdir(parents=True, exist_ok=True)

    # Thư mục tạm dưới thư mục tạm hệ thống, không nằm trong repo
    temp_root = Path(tempfile.mkdtemp(prefix=f"hf_smoke_{name}_"))

    try:
        # Bước 1: Khởi tạo dự án tạm 1 và cài đặt khối qua hyperframes add
        proj1 = temp_root / "p1"
        proj1.mkdir(parents=True, exist_ok=True)
        (proj1 / "hyperframes.json").write_text(
            json.dumps({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}),
            encoding="utf-8",
        )
        (proj1 / "package.json").write_text(
            json.dumps({"name": "t", "private": True, "type": "module"}),
            encoding="utf-8",
        )

        cli = hyperframes_cli()
        node_bin = _node()
        env = _env()

        add_cmd = [node_bin, str(cli), "add", name, "--no-clipboard", "--json"]
        add_res = subprocess.run(
            add_cmd,
            cwd=proj1,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        # Xác định vị trí tệp đã cài
        candidates = [
            proj1 / "compositions" / f"{name}.html",
            proj1 / "compositions" / "components" / f"{name}.html",
        ]
        installed_file = next((c for c in candidates if c.is_file()), None)
        if installed_file is None:
            # Tìm kiếm dự phòng nếu đường dẫn cài đặt khác chuẩn
            found = list(proj1.glob(f"**/{name}.html"))
            installed_file = found[0] if found else None

        if installed_file is None:
            elapsed = round(time.perf_counter() - t0, 3)
            return SmokeResult(
                name=name,
                renders=False,
                reason=f"add_failed: {add_res.stderr or add_res.stdout}".strip(),
                runtime_errors=0,
                layout_errors=0,
                seconds=elapsed,
                frames=(),
                external_deps=(),
            )

        raw_html = installed_file.read_text(encoding="utf-8")

        # Kiểm tra xem khối có phải là đoạn mã (snippet) không có data-composition-id
        if "data-composition-id" not in raw_html:
            elapsed = round(time.perf_counter() - t0, 3)
            return SmokeResult(
                name=name,
                renders=False,
                reason="snippet",
                runtime_errors=0,
                layout_errors=0,
                seconds=elapsed,
                frames=(),
                external_deps=(),
            )

        # Bước 2: Áp dụng ba biến đổi cho mã khối
        # (1) Bỏ CDN GSAP
        transformed = _CDN_GSAP.sub("", raw_html)
        # (2) Bỏ thẻ <link> Google Fonts
        transformed = _CDN_FONT.sub("", transformed)
        # (3) Đổi tên khối thành 'blk'
        transformed = re.sub(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9_])", "blk", transformed)

        # Ghi nhận các liên kết http(s) còn lại làm external_deps
        raw_urls = re.findall(r'https?://[^\s"\'<>]+', transformed)
        external_deps = tuple(sorted(set(u for u in raw_urls if "w3.org" not in u and "schema.org" not in u)))

        # Bước 3: Lấy thông số thời lượng và kích thước từ danh mục
        catalog = load_index()
        entry = catalog.get(name)
        d_val = entry.duration if (entry and entry.duration is not None) else 4.0
        w_val = entry.width if (entry and entry.width is not None) else 1920
        h_val = entry.height if (entry and entry.height is not None) else 1080

        if aspect == "9:16":
            root_w, root_h = 1080, 1920
            host_w, host_h = 1080, 1920
        else:
            root_w, root_h = 1920, 1080
            host_w, host_h = w_val, h_val

        # Bước 4: Tạo dự án tạm 2 chứa index.html nhúng khối làm sub-composition
        proj2 = temp_root / "p2"
        proj2.mkdir(parents=True, exist_ok=True)
        (proj2 / "hyperframes.json").write_text(
            json.dumps({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}),
            encoding="utf-8",
        )
        (proj2 / "package.json").write_text(
            json.dumps({"name": "t", "private": True, "type": "module"}),
            encoding="utf-8",
        )

        (proj2 / "compositions").mkdir(parents=True, exist_ok=True)
        (proj2 / "compositions" / "blk.html").write_text(transformed, encoding="utf-8")

        vendor_dir = proj2 / "assets" / "vendor"
        fonts_dir = proj2 / "assets" / "fonts"
        vendor_dir.mkdir(parents=True, exist_ok=True)
        fonts_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy(engines_dir() / "vendor" / "gsap.min.js", vendor_dir / "gsap.min.js")
        shutil.copy(engines_dir() / "vendor" / "CustomEase.min.js", vendor_dir / "CustomEase.min.js")
        shutil.copy(VIETSUB_FONT_PATH, fonts_dir / "be_vietnam_pro_semibold.ttf")

        index_html = (
            f'<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width={root_w}, height={root_h}">\n'
            f'<script src="assets/vendor/gsap.min.js"></script>\n<script src="assets/vendor/CustomEase.min.js"></script>\n'
            f'<style>@font-face{{font-family:"Viet";src:url(assets/fonts/be_vietnam_pro_semibold.ttf);font-weight:100 900}}'
            f'html,body{{margin:0;width:{root_w}px;height:{root_h}px;overflow:hidden;background:#0a1c2b}}'
            f'#bg{{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,#12324a 0%,#0a1c2b 62%,#06131d 100%)}}</style>\n'
            f'</head>\n<body>\n'
            f'<div id="root" data-composition-id="main" data-start="0" data-duration="{d_val}" data-width="{root_w}" data-height="{root_h}">\n'
            f'<div id="bg"></div>\n'
            f'<div id="blk" data-composition-id="blk" data-composition-src="compositions/blk.html" data-start="0" data-duration="{d_val}" data-track-index="1" data-width="{host_w}" data-height="{host_h}" style="z-index:1;{THEME_STYLE}"></div>\n'
            f'</div>\n'
            f'<script>\nwindow.__timelines = window.__timelines || {{}};\n'
            f'const tl = gsap.timeline({{ paused: true }});\n'
            f'window.__timelines["main"] = tl;\n'
            f'</script>\n</body>\n</html>\n'
        )
        (proj2 / "index.html").write_text(index_html, encoding="utf-8")

        # Bước 5: Chạy hyperframes check --json
        runtime_errors = 0
        layout_errors = 0
        with _CHROME_LOCK:
            check_proc = subprocess.run(
                [node_bin, str(cli), "check", "--json"],
                cwd=proj2,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )

        try:
            bracket_idx = check_proc.stdout.find("{")
            if bracket_idx != -1:
                check_data = json.loads(check_proc.stdout[bracket_idx:])
                runtime_findings = check_data.get("runtime", {}).get("findings", [])
                runtime_errors = sum(1 for f in runtime_findings if f.get("severity") == "error")
                if runtime_errors == 0 and check_data.get("runtime", {}).get("errorCount", 0) > 0:
                    runtime_errors = int(check_data["runtime"]["errorCount"])

                layout_findings = check_data.get("layout", {}).get("findings", [])
                layout_errors = sum(1 for f in layout_findings if f.get("severity") == "error")
                if layout_errors == 0 and check_data.get("layout", {}).get("errorCount", 0) > 0:
                    layout_errors = int(check_data["layout"]["errorCount"])
        except Exception:
            pass

        # Bước 6: Chụp 2 khung hình snapshot tại 0.3*D và 0.65*D
        t1 = round(0.3 * d_val, 3)
        t2 = round(0.65 * d_val, 3)

        # Xóa các khung hình cũ trong work_dir trước khi chụp
        for old_f in target_work_dir.glob("frame-*.png"):
            try:
                old_f.unlink(missing_ok=True)
            except Exception:
                pass

        snap_cmd = [
            node_bin,
            str(cli),
            "snapshot",
            "--at",
            f"{t1},{t2}",
            "--no-end",
            "-o",
            str(target_work_dir),
        ]
        with _CHROME_LOCK:
            subprocess.run(
                snap_cmd,
                cwd=proj2,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )

        # Xóa contact-sheet.jpg tự động sinh nếu có, chỉ giữ lại PNGs
        contact_jpg = target_work_dir / "contact-sheet.jpg"
        if contact_jpg.is_file():
            try:
                contact_jpg.unlink(missing_ok=True)
            except Exception:
                pass

        frames = tuple(str(f.resolve()) for f in sorted(target_work_dir.glob("frame-*.png")))

        elapsed = round(time.perf_counter() - t0, 3)
        if len(frames) >= 2 and runtime_errors == 0:
            renders = True
            reason = "ok"
        elif runtime_errors > 0:
            renders = False
            reason = f"runtime_errors: {runtime_errors}"
        else:
            renders = False
            reason = "snapshot_failed"

        return SmokeResult(
            name=name,
            renders=renders,
            reason=reason,
            runtime_errors=runtime_errors,
            layout_errors=layout_errors,
            seconds=elapsed,
            frames=frames,
            external_deps=external_deps,
        )

    finally:
        # Xóa thư mục dự án tạm, chỉ giữ lại ảnh PNG
        try:
            shutil.rmtree(temp_root, ignore_errors=True)
        except Exception:
            pass


def main() -> None:
    """Điểm vào chạy dòng lệnh kiểm thử khói hàng loạt khối."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Kiểm thử khói tự động cho các khối HyperFrames.")
    parser.add_argument("--nhom", default="all", help="Nhóm khối (slug) hoặc all")
    parser.add_argument("--khung", choices=["16:9", "9:16"], default="16:9", help="Tỉ lệ khung hình (16:9 hoặc 9:16)")
    parser.add_argument("--gioi-han", type=int, default=None, help="Giới hạn số lượng khối cần kiểm")
    parser.add_argument("--ten", nargs="*", default=None, help="Danh sách tên khối cụ thể cần kiểm")
    parser.add_argument("--ca-webgpu", action="store_true", help="Bao gồm cả nhóm webgpu và can_anh")
    parser.add_argument("--out", type=Path, required=True, help="Thư mục ghi kết quả")

    args = parser.parse_args()

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "kiem_thu_khoi.jsonl"

    index = load_index()
    names = select_names(index, nhom=args.nhom, ca_webgpu=args.ca_webgpu)

    if args.ten:
        names = [n for n in names if n in args.ten]

    if args.gioi_han is not None:
        names = names[:args.gioi_han]

    done_names = names_done(jsonl_path)
    print(f"Tổng số khối được chọn: {len(names)}. Đã hoàn thành trước đó: {len(done_names)}.")

    all_results: list[SmokeResult] = []

    # Đọc lại các kết quả cũ từ tệp jsonl để tổng hợp bảng liên lạc
    if jsonl_path.is_file():
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    all_results.append(
                        SmokeResult(
                            name=d["name"],
                            renders=bool(d["renders"]),
                            reason=str(d.get("reason", "")),
                            runtime_errors=int(d.get("runtime_errors", 0)),
                            layout_errors=int(d.get("layout_errors", 0)),
                            seconds=float(d.get("seconds", 0.0)),
                            frames=tuple(d.get("frames", ())),
                            external_deps=tuple(d.get("external_deps", ())),
                        )
                    )
                except Exception:
                    continue

    for name in names:
        if name in done_names:
            print(f"Bỏ qua khối đã kiểm tra: {name}")
            continue

        print(f"Đang kiểm thử khối: {name} ...")
        block_out_dir = out_dir / name
        block_out_dir.mkdir(parents=True, exist_ok=True)

        res = smoke_block(name, work_dir=block_out_dir, aspect=args.khung)
        print(f"  -> renders={res.renders}, reason={res.reason}, runtime_errors={res.runtime_errors}, seconds={res.seconds}")

        # Ghi ngay một dòng vào tệp jsonl
        res_dict = {
            "name": res.name,
            "renders": res.renders,
            "reason": res.reason,
            "runtime_errors": res.runtime_errors,
            "layout_errors": res.layout_errors,
            "seconds": res.seconds,
            "frames": list(res.frames),
            "external_deps": list(res.external_deps),
        }
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(res_dict, ensure_ascii=False) + "\n")

        all_results.append(res)
        done_names.add(name)

    contact_png = out_dir / "contact_sheet.png"
    print(f"Đang tạo bảng liên lạc tại: {contact_png} ...")
    write_contact_sheet(all_results, contact_png)
    print("Hoàn thành toàn bộ quy trình kiểm thử khói.")


if __name__ == "__main__":
    main()
