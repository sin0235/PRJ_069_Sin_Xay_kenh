"""Dựng video bằng dự án HyperFrames từ một thư mục chạy đã có storyboard, giọng và mốc từ (kết quả của tao_video_canh_giay_tron_goi.py).

Dùng:  python dung_video_hyperframes.py --chay <thu_muc_chay> --ra <thu_muc_ra> [--chi-kiem] [--dung-lai-du-an]
Đầu ra: <ra>/du_an (dự án HyperFrames), <ra>/video_hyperframes.mp4, <ra>/bao_cao_hyperframes.json.
Cần PRJ069_ENGINES_DIR trỏ tới thư mục engines đã npm install khi không dùng thư mục trong repo."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.modules.media_studio.video_processor import video_processor   # noqa: E402
from src.modules.tao_video_noi_dung import hf_project, planner   # noqa: E402
from src.modules.tao_video_noi_dung.brand import restore_display_words, to_display, to_spoken   # noqa: E402
from src.modules.tao_video_noi_dung.vietsub import align_script_words, transcribe_words_cached   # noqa: E402

LEAD = 0.15


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chay", required=True)
    parser.add_argument("--ra", required=True)
    parser.add_argument("--chi-kiem", action="store_true", help="Chỉ sinh dự án và chạy check, không dựng")
    args = parser.parse_args()
    run, out = Path(args.chay), Path(args.ra)
    out.mkdir(parents=True, exist_ok=True)
    storyboard = planner.Storyboard.model_validate_json((run / "storyboard.json").read_text(encoding="utf-8"))
    report = json.loads((run / "bao_cao_kiem_tra.json").read_text(encoding="utf-8"))
    seconds_list = report["clip_tung_shot_giay"]
    shots = []
    for index, shot in enumerate(storyboard.shots):
        seconds = seconds_list[index]
        asr = transcribe_words_cached(run / "giong" / f"{shot.shot_id}.wav", run / "cache" / f"{shot.shot_id}.json")
        aligned = align_script_words(to_spoken(shot.narration).split(), asr)
        word_times = [LEAD + item["start_ms"] / 1000 for item in aligned]
        events = planner.resolve_diagram_times(shot.ui_scene, shot.narration, seconds, word_times)
        shots.append({"shot_id": shot.shot_id, "scene": shot.ui_scene, "narration": shot.narration, "seconds": seconds, "events": events, "word_times": word_times})
    display_text = to_display(" ".join(shot.narration for shot in storyboard.shots))   # chữ hiển thị luôn là BAHA Group
    full = run / "giong" / "toan_bo.wav"
    asr_all = transcribe_words_cached(full, run / "cache" / "toan_bo.json")
    words = restore_display_words(display_text.split(), align_script_words(to_spoken(display_text).split(), asr_all))
    project = out / "du_an"
    info = hf_project.build_project(project, shots, full, words)
    print("Dự án:", info)
    checked = hf_project.check_project(project)
    print("check:", checked["returncode"], json.dumps({k: v for k, v in checked["data"].items() if k in ("errors", "warnings", "summary")}, ensure_ascii=False)[:600])
    (out / "check.txt").write_text(checked["text"], encoding="utf-8")
    if args.chi_kiem:
        return 0
    started = time.monotonic()
    video = out / "video_hyperframes.mp4"
    hf_project.render_project(project, video)
    meta = video_processor.probe_video(video)
    result = {"giay_dung": round(time.monotonic() - started, 1), "meta": meta, "native": info["native_scenes"], "legacy": info["legacy_scenes"], "check_returncode": checked["returncode"]}
    (out / "bao_cao_hyperframes.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("XONG:", video, json.dumps(result, ensure_ascii=False)[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
