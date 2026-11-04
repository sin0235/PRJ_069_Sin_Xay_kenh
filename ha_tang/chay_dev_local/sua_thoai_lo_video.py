"""Kéo lời đọc của storyboard trong lô video cho đủ ngân sách âm tiết (giọng phủ hết hình), rồi duyệt lại.

Planner chỉ cảnh báo mềm khi lời đọc lệch ngân sách nên có storyboard lời quá ngắn; lượt dựng sau đó dừng ở TTS_DURATION_OUT_OF_RANGE.
Công cụ gọi `fix_narration_budget` (một lượt LLM chỉ để sửa lời, giữ ý và cụm neo), lưu thành bản storyboard mới, duyệt theo ủy quyền và cập nhật
trạng thái lô để `lo_video_noi_dung.py --chay` tạo lượt dựng mới. Ví dụ: python sua_thoai_lo_video.py --bai 10 11 12
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "sin_content_api"), str(ROOT)]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / ".env.dev", override=True)

from src.database import SessionLocal  # noqa: E402
from src.models.entities import ContentVideoPlan  # noqa: E402
from src.modules.llm.client import LLMClient  # noqa: E402
from src.modules.tao_video_noi_dung.planner import Storyboard, fix_narration_budget, narration_length_problems  # noqa: E402
from src.modules.tao_video_noi_dung.service import approve_plan, update_plan  # noqa: E402

STATE = HERE / "data" / "lo_video" / "trang_thai.json"


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bai", nargs="+", required=True)
    parser.add_argument("--so-lan", type=int, default=2, help="số lần gọi LLM tối đa cho mỗi bài")
    args = parser.parse_args()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        client = LLMClient.from_db(db)
        for so in args.bai:
            entry = state[so]
            plan = db.get(ContentVideoPlan, entry["plan_id"])
            storyboard = Storyboard.model_validate_json(plan.storyboard_json)
            before = narration_length_problems(storyboard.shots)
            if not any(item.startswith("NARRATION_TOTAL") for item in before) and not before:
                log(f"bài {so}: lời đọc đã đủ ngân sách")
                continue
            log(f"bài {so}: lệch ngân sách ({len(before)} cảnh báo), sửa lời bằng LLM")
            for _ in range(args.so_lan):
                storyboard = fix_narration_budget(storyboard, plan.target_duration_seconds, client)
                after = narration_length_problems(storyboard.shots)
                if not after:
                    break
            log(f"bài {so}: còn {len(after)} cảnh báo:", "; ".join(after)[:300])
            new_plan = update_plan(db, entry["project_id"], plan.id, plan.workspace_id, plan.created_by, storyboard)
            approve_plan(db, entry["project_id"], new_plan.id, plan.workspace_id, plan.created_by, allow_self_approval=True)
            entry.update(plan_id=new_plan.id, revision=new_plan.revision, approved=True)
            entry.pop("run_id", None)
            entry.pop("loi", None)
            STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            log(f"bài {so}: đã lưu bản {new_plan.revision} và duyệt")


if __name__ == "__main__":
    main()
