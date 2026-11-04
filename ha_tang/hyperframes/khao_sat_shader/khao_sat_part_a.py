"""Khao sát thực nghiệm Phần A: Kiểm tra snapshot khung hình chuyển cảnh thực tế của 8 loại chuyển cảnh thuần GSAP.
Tạo dự án 3 cảnh trong thư mục tạm bên ngoài repo, thêm chuyển cảnh vào timeline,
chụp snapshot tại mốc trước, giữa và sau chuyển cảnh, rồi so sánh pixel bằng PIL.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageChops

# Thêm đường dẫn repo để import các module nội bộ
REPO_ROOT = Path(__file__).resolve().parents[3]
SIN_API_DIR = REPO_ROOT / "sin_content_api"
if str(SIN_API_DIR) not in sys.path:
    sys.path.insert(0, str(SIN_API_DIR))

from src.modules.tao_video_noi_dung import hf_project, hf_transitions
from src.modules.tao_video_noi_dung.planner import DiagramSpec, UiScene

VALID = {
    "KINETIC_TITLE": {"title": "Một nguồn sự thật", "tag": "sự thật"},
    "MARK_PHRASE": {"title": "Mỗi bộ phận giữ một con số khác nhau", "tag": "một con số khác nhau", "caption": "Không ai sai"},
    "PILE_UP": {"title": "Chủ shop", "value": "16"},
}


def build_base_project(target_dir: Path):
    shots = [
        {"seconds": 3.0, "start_seconds": 0.0, "scene": UiScene(layout="KINETIC_TITLE", diagram=DiagramSpec(**VALID["KINETIC_TITLE"])), "events": {}, "narration": "lời đọc cảnh 1"},
        {"seconds": 3.0, "start_seconds": 3.0, "scene": UiScene(layout="MARK_PHRASE", diagram=DiagramSpec(**VALID["MARK_PHRASE"])), "events": {}, "narration": "lời đọc cảnh 2"},
        {"seconds": 3.0, "start_seconds": 6.0, "scene": UiScene(layout="PILE_UP", diagram=DiagramSpec(**VALID["PILE_UP"])), "events": {}, "narration": "lời đọc cảnh 3"},
    ]
    hf_project.build_project(target_dir, shots, None, None, transitions=False, aspect_ratio="16:9")


def evaluate_kind(base_dir: Path, work_dir: Path, kind: str) -> dict:
    # Sao chép dự án gốc sang thư mục làm việc riêng để không đè
    shutil.rmtree(work_dir, ignore_errors=True)
    shutil.copytree(base_dir, work_dir)

    index_path = work_dir / "index.html"
    index_html = index_path.read_text(encoding="utf-8")

    # Thêm chuyển cảnh giữa s01 và s02 tại t=2.6s kéo dài 0.6s (giữa là 2.9s)
    # Thêm chuyển cảnh giữa s02 và s03 tại t=5.6s kéo dài 0.6s (giữa là 5.9s)
    code_transition = hf_transitions.transition_js(kind, "s01", "s02", 2.6, 0.6)
    marker = 'window.__timelines["main"] = tl;'
    if marker not in index_html:
        raise RuntimeError("Không tìm thấy điểm gán timeline trong index.html")
    new_html = index_html.replace(marker, code_transition + marker)
    index_path.write_text(new_html, encoding="utf-8")

    snapshot_dir = Path(tempfile.gettempdir()) / f"hf_snap_{kind}"
    shutil.rmtree(snapshot_dir, ignore_errors=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        hf_project._node(),
        str(hf_project.hyperframes_cli()),
        "snapshot",
        "--at", "2.0,2.9,3.5",
        "--no-end",
        "-o", str(snapshot_dir),
    ]

    res = subprocess.run(cmd, cwd=work_dir, env=hf_project._env(), capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        return {"kind": kind, "success": False, "error": res.stderr or res.stdout}

    png_files = list(snapshot_dir.glob("*.png"))
    # Tìm 3 khung hình: trước (khoảng 2s), giữa (khoảng 2.9s), sau (khoảng 3.5s)
    f_before = None
    f_mid = None
    f_after = None

    for p in png_files:
        name = p.stem.lower()
        if "2s" in name or "2.0" in name:
            f_before = p
        elif "2.9" in name:
            f_mid = p
        elif "3.5" in name:
            f_after = p

    if not (f_before and f_mid and f_after):
        # Sắp xếp theo tên hoặc mốc nếu tên khác quy ước
        png_files = sorted(png_files)
        if len(png_files) >= 3:
            f_before, f_mid, f_after = png_files[0], png_files[1], png_files[2]
        else:
            return {"kind": kind, "success": False, "error": f"Không đủ file ảnh: {[p.name for p in png_files]}"}

    im_before = Image.open(f_before).convert("RGB")
    im_mid = Image.open(f_mid).convert("RGB")
    im_after = Image.open(f_after).convert("RGB")

    diff1 = ImageChops.difference(im_mid, im_before)
    diff2 = ImageChops.difference(im_mid, im_after)

    bbox1 = diff1.getbbox()
    bbox2 = diff2.getbbox()

    diff1_differs = bbox1 is not None
    diff2_differs = bbox2 is not None

    # Dọn dẹp ảnh tạm
    shutil.rmtree(snapshot_dir, ignore_errors=True)
    shutil.rmtree(work_dir, ignore_errors=True)

    return {
        "kind": kind,
        "success": True,
        "differs_from_before": diff1_differs,
        "differs_from_after": diff2_differs,
        "visibly_changes": diff1_differs and diff2_differs,
        "bbox_before": bbox1,
        "bbox_after": bbox2,
    }


def main():
    temp_root = Path(tempfile.gettempdir()) / "hf_khao_sat_part_a"
    shutil.rmtree(temp_root, ignore_errors=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    base_project_dir = temp_root / "base_project"
    print(f"Xây dựng dự án mẫu tại: {base_project_dir}")
    build_base_project(base_project_dir)

    results = []
    print("Bắt đầu kiểm tra 8 kiểu chuyển cảnh...")
    for kind in hf_transitions.TRANSITION_KINDS:
        work_dir = temp_root / f"proj_{kind}"
        print(f"  -> Đang kiểm tra: {kind} ...", flush=True)
        r = evaluate_kind(base_project_dir, work_dir, kind)
        results.append(r)
        print(f"     Kết quả: visibly_changes={r.get('visibly_changes')}, differs_before={r.get('differs_from_before')}, differs_after={r.get('differs_from_after')}")

    # Dọn dẹp dự án mẫu
    shutil.rmtree(temp_root, ignore_errors=True)

    print("\n--- BÁO CÁO KẾT QUẢ PHẦN A ---")
    all_ok = True
    for r in results:
        status = "DAT" if r.get("visibly_changes") else "KHONG DAT"
        print(f"{r['kind']:10s}: {status} (diff_before={r.get('differs_from_before')}, diff_after={r.get('differs_from_after')})")
        if not r.get("visibly_changes"):
            all_ok = False
            if "error" in r:
                print(f"   Lỗi: {r['error']}")

    if all_ok:
        print("\nTất cả 8 kiểu chuyển cảnh đều thay đổi khung hình rõ rệt tại điểm giữa!")
    else:
        print("\nCó kiểu chuyển cảnh chưa thay đổi rõ rệt khung hình!")


if __name__ == "__main__":
    main()
