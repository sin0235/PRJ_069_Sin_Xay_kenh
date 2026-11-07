"""So ba engine dựng (playwright, hyperframes, remotion) trên cùng một cảnh: thời gian dựng, kích thước, và độ lệch khung hình so với playwright.

Dùng:  python so_sanh_engine.py --ra <thu_muc> [--giay 8] [--aspect 16:9|9:16] [--engines playwright,hyperframes,remotion]
Đặt PRJ069_ENGINES_DIR trỏ tới thư mục engines đã `npm install` nếu không dùng thư mục trong repo. Không quay về playwright khi engine lỗi (để thấy lỗi thật).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modules.media_studio.video_processor import video_processor   # noqa: E402
from src.modules.tao_video_noi_dung.planner import UiScene   # noqa: E402
from src.modules.tao_video_noi_dung.render_engines import render_scene   # noqa: E402

NARRATION = "Trước khi tự động hóa, hãy liệt kê công đoạn lặp lại, đo thời gian từng công đoạn, rồi chọn công đoạn tốn nhất."
SCENE = UiScene(layout="CHECKLIST", diagram={"title": "Ba việc kiểm trước khi tự động hóa", "steps": ["Liệt kê công đoạn", "Đo thời gian", "Chọn công đoạn tốn nhất"], "stamp": "SẴN SÀNG", "camera_motion": "PARALLAX_PASS",
                                              "on": {"c0": "liệt kê công đoạn", "c1": "đo thời gian", "c2": "chọn công đoạn", "stamp": "tốn nhất"}})


def psnr(reference: Path, other: Path) -> str:
    result = subprocess.run([video_processor.ffmpeg_bin, "-v", "info", "-i", str(other), "-i", str(reference), "-lavfi", "psnr", "-f", "null", "-"], capture_output=True, text=True)
    match = re.search(r"average:([\d.inf]+)", result.stderr)
    return match.group(1) if match else "không đo được"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ra", required=True)
    parser.add_argument("--giay", type=int, default=8)
    parser.add_argument("--engines", default="playwright,hyperframes,remotion")
    parser.add_argument("--aspect", choices=("16:9", "9:16"), default="16:9")
    parser.add_argument("--fixture", type=Path, help="JSON cảnh, lời đọc và mốc từ cục bộ")
    parser.add_argument("--remotion-native", action="store_true", help="Yêu cầu cảnh React trực tiếp")
    args = parser.parse_args()
    scene, narration, word_times = SCENE, NARRATION, None
    if args.fixture:
        data = json.loads(args.fixture.read_text(encoding="utf-8-sig"))
        scene = UiScene.model_validate(data["scene"])
        narration, word_times = data.get("narration", ""), data.get("word_times")
        if not isinstance(narration, str) or (word_times is not None and (
            not isinstance(word_times, list) or len(word_times) != len(narration.split())
            or any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 for t in word_times)
            or word_times != sorted(word_times)
        )):
            raise ValueError("Dữ liệu lời đọc hoặc mốc từ không hợp lệ")
    out = Path(args.ra)
    out.mkdir(parents=True, exist_ok=True)
    reference = None
    failed = False
    report = []
    expected_size = (1080, 1920) if args.aspect == "9:16" else (1920, 1080)
    print(f"{'engine':<12}{'giây dựng':>11}{'byte':>10}{'kích thước':>14}{'PSNR so với playwright':>26}")
    for name in (item.strip() for item in args.engines.split(",")):
        path = out / f"{name}.mp4"
        started = time.monotonic()
        previous_fallback = os.environ.get("CONTENT_VIDEO_RENDER_FALLBACK")
        os.environ["CONTENT_VIDEO_RENDER_FALLBACK"] = "0"
        try:
            style = {"render_engine": name}
            if name == "remotion" and args.remotion_native:
                style["remotion_native"] = True
            meta = render_scene(scene, style, args.giay, args.aspect, path, narration=narration, word_times=word_times)
        except Exception as exc:   # in lỗi thật của từng engine, không dừng cả bảng
            print(f"{name:<12}LỖI {type(exc).__name__}: {str(exc)[:300]}")
            report.append({"requested_engine": name, "status": "failed", "error": str(exc)[:300]})
            failed = True
            continue
        finally:
            if previous_fallback is None:
                os.environ.pop("CONTENT_VIDEO_RENDER_FALLBACK", None)
            else:
                os.environ["CONTENT_VIDEO_RENDER_FALLBACK"] = previous_fallback
        if (meta.get("render_engine") != name or (meta.get("width"), meta.get("height")) != expected_size or not path.is_file()
                or name == "remotion" and args.remotion_native and meta.get("render_variant") != "native"):
            print(f"{name:<12}LỖI kết quả không khớp engine hoặc kích thước yêu cầu")
            report.append({**meta, "requested_engine": name, "status": "failed", "error": "ENGINE_RESULT_MISMATCH"})
            failed = True
            continue
        seconds = time.monotonic() - started
        if name == "playwright":
            reference = path
        diff = psnr(reference, path) if reference and name != "playwright" else "-"
        report.append({**meta, "requested_engine": name, "status": "passed", "layout": scene.layout,
                       "wall_seconds": seconds, "byte_size": path.stat().st_size,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "psnr": diff})
        print(f"{name:<12}{seconds:>11.1f}{path.stat().st_size:>10}{str(meta['width']) + 'x' + str(meta['height']):>14}{diff:>26}")
    (out / "bao_cao_so_sanh.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
