"""Xuất một shot cảnh giấy của storyboard thành dự án HyperFrames để xem trước, kiểm lint và contrast, hoặc dựng thử.

Dùng:  python xuat_hyperframes.py --storyboard storyboard.json --shot shot-05 --ra <thu_muc_du_an>
Sau đó (cần Node 22 và FFmpeg):  cd <thu_muc_du_an> && npx hyperframes@0.8.222 check && npx hyperframes@0.8.222 render -o shot.mp4
Đặt HYPERFRAMES_NO_TELEMETRY=1; không dùng lệnh cloud, auth hay publish của HyperFrames (đẩy dữ liệu ra ngoài).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modules.tao_video_noi_dung.planner import Storyboard   # noqa: E402
from src.modules.tao_video_noi_dung.ui_sim import hyperframes_composition_html   # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--storyboard", required=True)
    parser.add_argument("--shot", required=True, help="shot_id của một shot cảnh giấy")
    parser.add_argument("--ra", required=True)
    parser.add_argument("--giay", type=int, help="Độ dài clip (giây); mặc định là duration_seconds của shot")
    args = parser.parse_args()
    storyboard = Storyboard.model_validate_json(Path(args.storyboard).read_text(encoding="utf-8"))
    shot = next((item for item in storyboard.shots if item.shot_id == args.shot), None)
    if shot is None or not shot.ui_scene or not shot.ui_scene.diagram:
        raise SystemExit("Không tìm thấy shot cảnh giấy: " + args.shot)
    out = Path(args.ra)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(hyperframes_composition_html(shot.ui_scene, shot.narration, args.giay or shot.duration_seconds), encoding="utf-8")
    (out / "package.json").write_text(json.dumps({"name": shot.shot_id, "private": True, "type": "module"}, indent=2), encoding="utf-8")
    print("Đã ghi", out / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
