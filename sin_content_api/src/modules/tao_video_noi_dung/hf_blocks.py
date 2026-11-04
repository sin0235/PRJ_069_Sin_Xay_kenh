"""Kho khối dựng sẵn của HyperFrames (registry chính thức, Apache-2.0, HeyGen) nối vào cảnh dựng bằng mã.

Mỗi khối là một sub-composition có biến (`data-composition-variables`) và đọc giá trị qua `window.__hyperframes.getVariables()`.
Ở đây khối được: (1) bỏ phần tải GSAP và font từ CDN (dự án dùng GSAP cục bộ và font Be Vietnam Pro có dấu tiếng Việt),
(2) đổi định danh theo từng lần dùng để nhiều lần dùng trong một video không đè nhau, (3) khoác bảng màu thương hiệu qua biến CSS.

Hai cách dùng:
- Cảnh kể chuyện: `BLOCK_SCENES[layout]` gồm vài biến thể khối; `scene_composition()` chọn một biến thể ổn định theo nội dung
  rồi điền biến từ `diagram`. Cùng layout ở hai video khác nhau cho vẻ ngoài khác nhau mà cùng nội dung vẫn ra cùng kết quả.
- Lớp phủ và chuyển cảnh: `overlay()` cho nền động, hạt phim, rò sáng... đặt chồng lên cảnh.
Danh sách khối đã kiểm bằng ảnh chụp nằm trong blocks/catalog.json (xem tools_catalog)."""
from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import hf_vendor
from .hf_manifest import (
    BlockManifest,
    load_manifests,
    render_literals,
    render_variables,
)

BLOCKS_DIR = Path(__file__).resolve().parents[3] / "engines" / "hyperframes" / "blocks"
CATALOG_FILE = BLOCKS_DIR / "catalog.json"

# Biến CSS mà các khối đọc (--fg, --bg, --brand, --accent...). Bảng màu khớp "Origami Editorial Motion B2B v1": navy, ngà, ngọc lam, vàng, đỏ san hô.
THEME_STYLE = ("--bg:#0a1c2b;--fg:#f6efe0;--surface:#12324a;--border:rgba(255,255,255,.16);--brand:#ffd54a;--accent:#5cc8c0;"
               "--accent-2:#e8695a;--muted:#9fb4c4;--font-display:'Viet',sans-serif;--font-body:'Viet',sans-serif;--font-mono:'Viet',monospace")

# Chữ mẫu tiếng Anh có sẵn trong mã khối -> tiếng Việt (khối không có biến cho các chữ này).
_VIETNAMESE_TEXT: dict[str, dict[str, str]] = {
    "overwhelm-surround": {
        "Inbox": "Hộp thư", "Due": "Hạn chót", "@you": "@bạn", "ASAP": "GẤP", "Review": "Duyệt", "Call": "Gọi lại", "3 pings": "3 tin", "Sync": "Đồng bộ",
        "Today": "Hôm nay", "Reply": "Trả lời", "8 tabs": "8 tab", "Update": "Cập nhật", "Now": "Ngay", "Draft": "Soạn", "4 alerts": "4 cảnh báo",
        "Fix": "Sửa", "Follow up": "Theo dõi", "Queue": "Hàng chờ", "2 min": "2 phút", "Waiting": "Đang chờ",
    },
    "notification-pileup": {
        "Messages": "Tin nhắn", "Can you take a quick look?": "Anh xem giúp em một chút?", "Calendar": "Lịch", "Stand-up moved to 10:30": "Họp giao ban dời sang 10:30",
        "Mail": "Thư", "Five new replies in your thread": "Năm phản hồi mới trong chuỗi", "Updates": "Cập nhật", "A new version is ready": "Có bản mới cần duyệt",
        "Tasks": "Công việc", "Deadline changed to today": "Hạn nộp đổi sang hôm nay", "Drive": "Kho tệp", "Someone requested access": "Có người xin quyền truy cập",
        "Security": "Bảo mật", "New sign-in needs review": "Đăng nhập mới cần duyệt", "Social": "Mạng xã hội", "You have twelve new mentions": "Mười hai lượt nhắc mới",
        "Notes": "Ghi chú", "Shared checklist was updated": "Danh sách chung vừa đổi", "Reminders": "Nhắc việc", "Follow up before end of day": "Theo dõi trước cuối ngày",
    },
}


def block_path(name: str) -> Path:
    path = BLOCKS_DIR / f"{name}.html"
    if not path.is_file():
        raise FileNotFoundError(f"HYPERFRAMES_BLOCK_MISSING:{name}")
    return path


def prepare_block(name: str, cid: str, duration: float | None = None, literals: dict[str, str] | None = None) -> str:
    """Mã khối cho MỘT lần dùng: bỏ CDN, đổi định danh `name` thành `cid`. Khối đọc độ dài D từ `data-duration` của chính nó
    (không lấy từ thẻ host) nên phải ghi D thật vào đó, nếu không khối thoát cảnh theo độ dài mặc định."""
    text = block_path(name).read_text(encoding="utf-8")
    text, _ = hf_vendor.localize(text)
    remaining_urls = hf_vendor.scan_external(text)
    if remaining_urls:
        raise ValueError(f"HYPERFRAMES_BLOCK_EXTERNAL_URL:{name}:{remaining_urls[0]}")
    if duration is not None:
        text = re.sub(r'(data-(?:composition-)?duration=")[\d.]+(")', lambda m: f"{m.group(1)}{duration:.3f}{m.group(2)}", text)
        # Khi chạy, runtime không để lại data-duration trên #root nên khối rơi về giá trị mặc định trong mã: `dataset.duration || "3.5"`.
        text = re.sub(r'(dataset\.duration\s*\|\|\s*")[\d.]+(")', lambda m: f"{m.group(1)}{duration:.3f}{m.group(2)}", text)
    for english, vietnamese in _VIETNAMESE_TEXT.get(name, {}).items():
        text = text.replace(f'"{english}"', f'"{vietnamese}"')
    for old, new in (literals or {}).items():   # chữ cố định trong mã khối mà khối không có biến: thay bằng nội dung của cảnh
        if old not in text:
            raise ValueError(f"HYPERFRAMES_BLOCK_LITERAL_MISSING:{name}:{old[:30]}")
        text = text.replace(old, new)   # new do hàm dựng literals tự escape phần nội dung
    return re.sub(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9_])", cid, text)


def vendor_files_for(name: str) -> tuple[str, ...]:
    """Các tệp vendor cục bộ mà khối cần (từ báo cáo localize trên tệp gốc)."""
    text = block_path(name).read_text(encoding="utf-8")
    _, report = hf_vendor.localize(text)
    return report.files


def host_attrs(variables: dict | None = None) -> str:
    """Thuộc tính thêm cho thẻ host: giá trị biến của khối (JSON trong dấu nháy đơn)."""
    if not variables:
        return ""
    return " data-variable-values='" + json.dumps(variables, ensure_ascii=False).replace("&", "&amp;").replace("'", "&#39;") + "'"


def load_catalog() -> dict:
    try:
        return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"blocks": {}}


@dataclass(frozen=True)
class Variant:
    block: str
    variables: Callable[[dict], dict]
    max_chars: int = 999   # khối cỡ chữ cố định chỉ hợp tiêu đề ngắn
    literals: Callable[[dict], dict] | None = None   # chữ cố định trong mã khối cần thay theo nội dung cảnh
    manifest: BlockManifest | None = None


# Đọc toàn bộ manifest từ blocks/manifest/*.json
_LOADED_MANIFESTS = load_manifests()


def _build_block_scenes() -> dict[str, list[Variant]]:
    scenes: dict[str, list[Variant]] = {}
    for layout, m_list in _LOADED_MANIFESTS.items():
        variants: list[Variant] = []
        for m in m_list:
            v_vars = (lambda mf: lambda d: render_variables(mf, d))(m)
            v_lits = (lambda mf: (lambda d: render_literals(mf, d)) if mf.literals else None)(m)
            variants.append(Variant(
                block=m.block,
                variables=v_vars,
                max_chars=m.max_chars,
                literals=v_lits,
                manifest=m,
            ))
        scenes[layout] = variants
    return scenes


BLOCK_SCENES: dict[str, list[Variant]] = _build_block_scenes()

# Hệ số phóng cảnh khối ở khung 9:16 (dựng từ manifest)
PORTRAIT_SCALE: dict[str, float] = {
    layout: m_list[0].portrait_scale.get("base", 1.0)
    for layout, m_list in _LOADED_MANIFESTS.items()
    if m_list and m_list[0].portrait_scale.get("base", 1.0) != 1.0
}
SQUARE_BLOCKS: tuple[str, ...] = tuple(
    layout for layout, m_list in _LOADED_MANIFESTS.items()
    if any(m.square for m in m_list)
)


def portrait_scale(layout: str, data: dict) -> float:
    """Hệ số phóng ở khung 9:16. Khối chữ một dòng đã tự co theo chiều rộng nên câu dài phóng thêm sẽ tràn mép: câu càng dài phóng càng ít."""
    manifests = _LOADED_MANIFESTS.get(layout, [])
    rules = manifests[0].portrait_scale if manifests else {}
    base = PORTRAIT_SCALE.get(layout, 1.0)
    if layout in ("MARK_PHRASE", "WORD_SWAP"):
        size = len(str(data.get("title") or "")) + (
            (sum(len(s) for s in data.get("steps") or []) // max(1, len(data.get("steps") or [1]))
             + len(str(data.get("caption") or "")))
            if layout == "WORD_SWAP" else 0
        )
        if size <= 22:
            return rules.get("lte_22", base)
        elif size <= 30:
            return rules.get("lte_30", 1.15)
        else:
            return rules.get("default", 1.0)
    return base


def pick_variant(layout: str, data: dict) -> Variant:
    variants = [v for v in BLOCK_SCENES[layout] if len(str(data.get("title") or "")) <= v.max_chars] or BLOCK_SCENES[layout][-1:]
    key = json.dumps([layout, data.get("title"), data.get("tag")], ensure_ascii=False, sort_keys=True)
    return variants[zlib.crc32(key.encode("utf-8")) % len(variants)]


def scene_composition(layout: str, cid: str, data: dict, duration: float | None = None) -> tuple[str, str, str]:
    """(mã composition, thuộc tính host, style host) cho một cảnh khối; style host mang bảng màu thương hiệu."""
    variant = pick_variant(layout, data)
    scale = portrait_scale(layout, data) if data.get("portrait") else 1.0   # khung 9:16 hẹp hơn nên khối cỡ chữ theo chiều ngang trông nhỏ
    style = THEME_STYLE + (f";transform:scale({scale});transform-origin:50% 50%" if scale != 1.0 else "")
    if layout in SQUARE_BLOCKS:   # khối vuông 1080x1080 đặt giữa khung
        style += ";transform:translate(0,420px)" if data.get("portrait") else ";transform:translate(420px,0)"
    literals = variant.literals(data) if variant.literals else None
    return prepare_block(variant.block, cid, duration, literals), host_attrs(variant.variables(data)), style


def _drag_literals(data: dict) -> dict[str, str]:
    """Hàm tương thích ngược phỏng sinh literals cho DRAG_TASKS qua manifest."""
    manifests = _LOADED_MANIFESTS.get("DRAG_TASKS", [])
    return render_literals(manifests[0], data) if manifests else {}


def _shift_literals(data: dict) -> dict[str, str]:
    """Hàm tương thích ngược phỏng sinh literals cho CARD_SHIFT qua manifest."""
    manifests = _LOADED_MANIFESTS.get("CARD_SHIFT", [])
    return render_literals(manifests[0], data) if manifests else {}
