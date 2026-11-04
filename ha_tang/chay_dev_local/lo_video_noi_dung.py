"""Lô video nội dung: từ các bài nội dung (md) tạo dự án, storyboard bằng LLM (khung 9:16), duyệt theo ủy quyền, và (tùy chọn) tạo lượt dựng.

Chỉ nhận bài nội dung chữ; storyboard, lời đọc và prompt do planner tạo. Chạy lại bao nhiêu lần cũng được: bài nào đã có dự án và storyboard thì bỏ qua
(trạng thái lưu ở data/lo_video/trang_thai.json). Lượt dựng (tốn tín dụng Flow) chỉ tạo khi có --chay.

Ví dụ:
  python lo_video_noi_dung.py --bai 13 --du-an-co-san 13=113da8f0-668e-4c74-a1fc-c94cceb5421e --chay
  python lo_video_noi_dung.py --bai 01 02 03 04 06 07 08 09 10 11 12 14 17 18
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "sin_content_api"), str(ROOT)]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE / ".env.dev", override=True)

from src.database import SessionLocal  # noqa: E402
from src.models.entities import ContentVideoPlan, ProductionProject, VoiceProfile  # noqa: E402
from src.modules.tao_video_noi_dung.contracts import CreatePlanRequest, CreateRunRequest  # noqa: E402
from src.modules.tao_video_noi_dung.giong_da_luu import ap_dung_ho_so_giong  # noqa: E402
from src.modules.tao_video_noi_dung.service import approve_plan, create_plan, create_run  # noqa: E402

NOI_DUNG = Path(r"C:/Users/Baha Group/Documents/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/kich_ban/noi_dung_abstract_2026")
STATE = HERE / "data" / "lo_video" / "trang_thai.json"
# Giọng lấy từ thư viện clone giọng (hồ sơ "Sếp"), hồ sơ Flow của lượt dựng bài 13 đã đạt QC (run 561f6263).
TEN_GIONG = "Sếp"
FLOW_PROFILE = "d08e7af1-41c9-4869-aa99-b368a7675b98"


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def doc_bai(so: str) -> tuple[str, str]:
    path = glob.glob(str(NOI_DUNG / f"{so}_*.md"))[0]
    text = Path(path).read_text(encoding="utf-8")
    title = re.sub(r"^#+\s*", "", text.splitlines()[0]).strip()
    return title, text.split("### Nguồn kiểm chứng")[0].rstrip().rstrip("-").rstrip()


def id_giong(db, workspace_id: str) -> str:
    profile = db.query(VoiceProfile).filter(VoiceProfile.workspace_id == workspace_id, VoiceProfile.name == TEN_GIONG).first()
    if not profile:
        raise RuntimeError(f"Thư viện giọng chưa có giọng '{TEN_GIONG}'; lưu giọng ở trang Voice Studio trước")
    return profile.id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bai", nargs="+", required=True)
    parser.add_argument("--thoi-luong", type=int, default=100)
    parser.add_argument("--khung", choices=["16:9", "9:16"], default="16:9", help="khung hình; mặc định ngang 16:9")
    parser.add_argument("--du-an-co-san", nargs="*", default=[], help="so=project_id: tạo bản storyboard mới trong dự án đã có thay vì dự án mới")
    parser.add_argument("--chay", action="store_true", help="tạo lượt dựng (tốn tín dụng Flow)")
    parser.add_argument("--bo-qua-cong", action="store_true", help="bỏ qua cổng chất lượng trước khi tạo lượt dựng")
    args = parser.parse_args()
    existing = dict(item.split("=", 1) for item in args.du_an_co_san)
    state = load_state()
    with SessionLocal() as db:
        template = db.query(ContentVideoPlan).order_by(ContentVideoPlan.created_at.desc()).first()
        workspace_id, user_id = template.workspace_id, template.created_by
        for so in args.bai:
            entry = state.setdefault(so, {})
            title, content = doc_bai(so)
            try:
                if not entry.get("project_id"):
                    if so in existing:
                        entry["project_id"] = existing[so]
                    else:
                        project = ProductionProject(id=str(uuid.uuid4()), workspace_id=workspace_id, title=f"Bài {so} - {title} (lô 15, planner khối)",
                                                    workflow_type="AI_VIDEO", status="DRAFT", created_by=user_id)
                        db.add(project)
                        db.commit()
                        entry["project_id"] = project.id
                    save_state(state)
                if not entry.get("plan_id"):
                    t0 = time.time()
                    plan = create_plan(db, entry["project_id"], workspace_id, user_id,
                                       CreatePlanRequest(content=content, target_duration_seconds=args.thoi_luong, aspect_ratio=args.khung))
                    entry.update(plan_id=plan.id, revision=plan.revision, giay_llm=round(time.time() - t0))
                    storyboard = json.loads(plan.model_dump_json())["storyboard"]
                    kinds = [s["shot_kind"] + (":" + s["ui_scene"]["layout"] if s.get("ui_scene") else "") for s in storyboard["shots"]]
                    entry["shots"] = kinds
                    save_state(state)
                    log(f"bài {so}: storyboard rev {plan.revision} khung {args.khung} sau {entry['giay_llm']} giây,", len(kinds), "shot;", kinds)
                if not entry.get("approved"):
                    approve_plan(db, entry["project_id"], entry["plan_id"], workspace_id, user_id, allow_self_approval=True)
                    entry["approved"] = True
                    save_state(state)
                    log(f"bài {so}: đã duyệt storyboard (theo ủy quyền của Founder, Founder vẫn ký nghiệm thu cuối)")
                if args.chay and not entry.get("run_id"):
                    if not args.bo_qua_cong:
                        from ha_tang.hyperframes.cong_chat_luong import gate_plan
                        problems = gate_plan(entry["project_id"], entry["plan_id"])
                        if problems:
                            entry["cong_chat_luong"] = problems
                            save_state(state)
                            log(f"bài {so}: CỔNG CHẤT LƯỢNG KHÔNG ĐẠT ({len(problems)} lỗi):", problems)
                            continue
                    request = ap_dung_ho_so_giong(db, workspace_id, entry["project_id"], CreateRunRequest(
                        plan_id=entry["plan_id"], flow_profile_id=FLOW_PROFILE, voice_source="TTS", voice_profile_id=id_giong(db, workspace_id),
                        include_subtitles=True, idempotency_key=f"lo15-{so}-{entry['plan_id'][:8]}"))
                    run = create_run(db, entry["project_id"], workspace_id, user_id, request)
                    entry["run_id"] = run.id
                    save_state(state)
                    log(f"bài {so}: đã tạo lượt dựng {run.id[:8]} trạng thái {run.status}")
            except Exception as exc:  # một bài lỗi không chặn cả lô
                entry["loi"] = f"{type(exc).__name__}: {str(getattr(exc, 'detail', exc))[:300]}"
                save_state(state)
                log(f"bài {so}: LỖI", entry["loi"])
                db.rollback()
    log("xong lô; trạng thái ở", STATE)


if __name__ == "__main__":
    main()
