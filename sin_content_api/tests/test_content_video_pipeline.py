from __future__ import annotations

import pathlib
import sys
import json
import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

API_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.modules.tao_video_noi_dung.planner import build_shot_prompt, generate_storyboard, parse_storyboard
from src.modules.tao_video_noi_dung.contracts import CreatePlanRequest, CreateRunRequest, ReconcileShotRequest
from src.modules.tao_video_noi_dung.runner import _has_duplicate_shot_media, evaluate_shot_qc, evaluate_video_qc
from src.modules.tao_video_noi_dung.runner import _mark_flow_setup_blocked
from src.modules.tao_video_noi_dung import cong_harness
from src.modules.tao_video_noi_dung import router as content_video_router
from src.modules.tao_video_noi_dung.cong_harness import build_shot_receipt, dispatch_shot
from src.modules.tao_video_noi_dung.planner import StoryboardShot
from src.migrations import runner as migration_runner


def test_content_video_migration_upgrades_existing_run_table(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE content_video_runs (id VARCHAR(36) PRIMARY KEY)"))
        monkeypatch.setattr(migration_runner, "engine", engine)

        migration_runner.migration_up()

        columns = {column["name"] for column in inspect(engine).get_columns("content_video_runs")}
        assert "voice_asset_id" in columns
        assert "tts_config_json" in columns
        assert {"content_video_plans", "content_video_worker_leases"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_full_migration_rollback_preserves_content_video_records(tmp_path, monkeypatch):
    from src import database
    from src.models.entities import ContentVideoPlan

    engine = create_engine(f"sqlite:///{tmp_path / 'rollback.db'}")
    Session = sessionmaker(bind=engine)
    try:
        monkeypatch.setattr(migration_runner, "engine", engine)
        monkeypatch.setattr(database, "SessionLocal", Session)
        migration_runner.migration_up()
        with Session() as db:
            db.add(ContentVideoPlan(
                id="plan-1", workspace_id="workspace-1", project_id="project-1", revision=1,
                source_content="content", content_sha256="content-hash", target_duration_seconds=30,
                style_snapshot_json="{}", style_snapshot_sha256="style-hash",
                storyboard_json="{}", storyboard_sha256="storyboard-hash", llm_model="test", created_by="creator-1",
            ))
            db.commit()

        with pytest.raises(RuntimeError, match="Cannot rollback content-video tables"):
            migration_runner.migration_down()

        with Session() as db:
            assert db.query(ContentVideoPlan).count() == 1
        assert "content_video_plans" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_storyboard_requires_ordered_shots_covering_target_duration():
    storyboard = parse_storyboard(
        '{"title":"Demo","narration":"Lời đọc","continuity_anchor":"Một nhân vật cố định mặc áo xanh trong studio navy, ánh sáng mềm.","shots":['
        '{"shot_id":"s1","scene":"Mở đầu","narration":"Lời mở đầu","prompt":"Cảnh đầu","duration_seconds":10},'
        '{"shot_id":"s2","scene":"Thân bài","narration":"Lời giữa","prompt":"Cảnh giữa","duration_seconds":10},'
        '{"shot_id":"s3","scene":"Kết luận","narration":"Lời kết","prompt":"Cảnh cuối","duration_seconds":10}]}',
        target_duration_seconds=30,
    )

    assert [shot.shot_id for shot in storyboard.shots] == ["s1", "s2", "s3"]
    assert sum(shot.duration_seconds for shot in storyboard.shots) == 30
    prompts = [build_shot_prompt({"style_name": "Studio", "visual_rules": "Consistent cinematic look", "palette": ["navy"]}, shot, storyboard.continuity_anchor) for shot in storyboard.shots]
    assert all(storyboard.continuity_anchor in prompt for prompt in prompts)
    assert all(shot.narration not in prompt and "âm thanh tự nhiên" in prompt for shot, prompt in zip(storyboard.shots, prompts, strict=True))
    assert CreateRunRequest(plan_id="plan-1", idempotency_key="native-flow-audio").voice_asset_id is None


def test_twenty_second_storyboard_is_accepted_by_api_and_planner():
    raw = (
        '{"title":"RAG","narration":"Tìm đúng tài liệu trước khi trả lời.",'
        '"continuity_anchor":"Một trợ lý giấy xanh navy đứng cạnh tủ tài liệu trong studio sáng.","shots":['
        '{"shot_id":"s1","scene":"Tìm kiếm","narration":"Tìm tài liệu liên quan.","prompt":"Tài liệu được truy xuất","duration_seconds":8},'
        '{"shot_id":"s2","scene":"Tạo câu trả lời","narration":"Tạo câu trả lời có căn cứ.","prompt":"Câu trả lời gắn với nguồn","duration_seconds":6},'
        '{"shot_id":"s3","scene":"Kết luận","narration":"Đó là RAG.","prompt":"Nguồn và kết quả bên nhau","duration_seconds":6}]}'
    )

    storyboard = parse_storyboard(raw, target_duration_seconds=20)
    plan_request = CreatePlanRequest(content="RAG truy xuất tri thức liên quan rồi mới tạo câu trả lời có căn cứ.", target_duration_seconds=20)

    assert sum(shot.duration_seconds for shot in storyboard.shots) == plan_request.target_duration_seconds == 20


def test_project_history_returns_latest_run_and_its_storyboard(monkeypatch):
    from src.models.entities import ContentVideoPlan, ContentVideoRun
    from src.modules.tao_video_noi_dung import service

    latest_run = SimpleNamespace(plan_id="plan-with-video")
    latest_plan = SimpleNamespace(id="plan-with-video")

    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_conditions):
            return self

        def order_by(self, *_ordering):
            return self

        def first(self):
            return latest_run if self.model is ContentVideoRun else latest_plan

    class Db:
        def query(self, model):
            return Query(model)

    monkeypatch.setattr(service, "_project", lambda *_args: None)
    monkeypatch.setattr(service, "_response", lambda plan: {"id": plan.id})
    monkeypatch.setattr(service, "_run_response", lambda run: {"plan_id": run.plan_id})

    result = service.get_latest_history(Db(), "project-1", "workspace-1")

    assert result == {"plan": {"id": "plan-with-video"}, "run": {"plan_id": "plan-with-video"}}


def test_create_plan_explains_gateway_rate_limit(monkeypatch):
    from fastapi import HTTPException
    from src.modules.llm.client import LLMResponseError
    from src.modules.tao_video_noi_dung import service

    class EnabledLLM:
        is_enabled = True

    monkeypatch.setattr(service, "_project", lambda *_args: None)
    monkeypatch.setattr(service.LLMClient, "from_db", classmethod(lambda _cls, _db: EnabledLLM()))
    monkeypatch.setattr(
        service,
        "generate_storyboard",
        lambda *_args: (_ for _ in ()).throw(LLMResponseError("quota", error_code="UPSTREAM_RATE_LIMITED")),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_plan(None, "project-1", "workspace-1", "user-1", CreatePlanRequest(
            content="Nội dung đủ dài để tạo video minh họa về cách truy xuất dữ liệu RAG.",
            target_duration_seconds=20,
        ))

    assert exc_info.value.detail["error_code"] == "UPSTREAM_RATE_LIMITED"
    assert "Hạn mức" in exc_info.value.detail["message"]


def test_storyboard_prompt_requires_three_shots_for_twenty_seconds():
    class RecordingClient:
        max_output_tokens = 6000

        def complete(self, messages, max_tokens):
            self.messages = messages
            return SimpleNamespace(
                content=(
                    '{"title":"RAG","narration":"Tìm đúng nguồn.",'
                    '"continuity_anchor":"Trợ lý giấy xanh navy cạnh tủ tài liệu, cùng một bối cảnh.","shots":['
                    '{"shot_id":"s1","scene":"Tìm","narration":"Tìm nguồn.","prompt":"Thẻ tài liệu bay ra.","flow_prompt_en":"One paper card glides from the shelf and settles on the desk.","duration_seconds":7,"continues_previous":false},'
                    '{"shot_id":"s2","scene":"Trả lời","narration":"Trả lời có căn cứ.","prompt":"Trợ lý đọc tài liệu.","flow_prompt_en":"The paper assistant reads one card, then looks toward the viewer.","duration_seconds":7,"continues_previous":false},'
                    '{"shot_id":"s3","scene":"Kết","narration":"Thử RAG.","prompt":"Nguồn và câu trả lời.","flow_prompt_en":"The source card rests beside the completed answer card.","duration_seconds":6,"continues_previous":false}]}'
                ),
                model="test-model",
            )

    client = RecordingClient()
    generate_storyboard(
        "RAG truy xuất tài liệu trước khi trả lời có căn cứ.",
        20,
        {"style_name": "Origami", "visual_rules": "Phong cách giấy thống nhất.", "palette": ["navy"]},
        client,
    )

    request = json.loads(client.messages[1]["content"])
    assert request["required_shot_durations"] == [7, 7, 6]


def test_storyboard_prompts_prevent_distorted_frames_and_unmotivated_motion():
    class RecordingClient:
        max_output_tokens = 6000

        def complete(self, messages, max_tokens):
            self.messages = messages
            return SimpleNamespace(
                content=(
                    '{"title":"RAG","narration":"Tìm nguồn.",'
                    '"continuity_anchor":"Trợ lý giấy xanh navy cạnh tủ tài liệu, cùng một bối cảnh.","shots":['
                    '{"shot_id":"s1","scene":"Tìm","narration":"Tìm nguồn.","prompt":"Một thẻ trượt tới.","flow_prompt_en":"A single paper card slides toward the assistant and stops.","duration_seconds":7,"continues_previous":false},'
                    '{"shot_id":"s2","scene":"Trả lời","narration":"Trả lời.","prompt":"Trợ lý đọc thẻ.","flow_prompt_en":"The assistant lifts one card, reads it, and lowers it back onto the desk.","duration_seconds":7,"continues_previous":false},'
                    '{"shot_id":"s3","scene":"Kết","narration":"Xong.","prompt":"Đặt thẻ lại.","flow_prompt_en":"The assistant places the card beside the answer and holds still.","duration_seconds":6,"continues_previous":false}]}'
                ),
                model="test-model",
            )

    client = RecordingClient()
    storyboard, _ = generate_storyboard(
        "RAG tìm nguồn trước khi trả lời.",
        20,
        {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"]},
        client,
    )
    system_prompt = client.messages[0]["content"].lower()
    shot_prompt = build_shot_prompt(
        {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"]},
        storyboard.shots[0],
        storyboard.continuity_anchor,
    ).lower()

    assert "một hành động chính" in system_prompt
    assert "không biến hình" in system_prompt
    assert "flow_prompt_en" not in system_prompt
    assert "mô hình giấy gấp nếp đã hoàn thiện" in system_prompt
    assert "điểm tiếp xúc/phản ứng vật lý" in system_prompt
    assert "không biến hình" in shot_prompt
    assert "không nhân đôi" in shot_prompt
    assert "một hành động chính" in shot_prompt
    assert "hai mắt cùng kích thước và cao độ" in shot_prompt
    assert "biểu cảm thân thiện tự nhiên" in shot_prompt
    assert 'giọng dẫn đọc nguyên văn bằng tiếng việt: "tìm nguồn."' in shot_prompt
    no_flow_narration = build_shot_prompt(
        {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"]},
        storyboard.shots[0], storyboard.continuity_anchor, include_narration_audio=False,
    ).lower()
    assert "chỉ tạo âm thanh bối cảnh nhẹ" in no_flow_narration
    assert 'giọng dẫn đọc nguyên văn' not in no_flow_narration


def test_flow_prompt_uses_vietnamese_and_ignores_legacy_english_prompt():
    shot = StoryboardShot(
        shot_id="s1", scene="Trợ lý origami chào khán giả", narration="Xin chào.",
        prompt="Mô hình trợ lý AI origami hoàn chỉnh vẫy tay một lần.", flow_prompt_en=(
            "A real person folds paper with bare hands."
        ), duration_seconds=7,
    )

    prompt = build_shot_prompt(
        {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"]},
        shot,
        "Một nhân vật giấy cố định trong studio navy.",
    )

    assert "A real person" not in prompt
    assert "mô hình origami đã gấp thành hình hoàn chỉnh" in prompt
    assert "không quay người thật, bàn tay hoặc ngón tay" in prompt.lower()
    assert "không mô tả hoặc thể hiện thao tác gấp giấy" in prompt.lower()
    assert "Không tạo lời nói tiếng Anh" in prompt
    assert "Xin chào." not in prompt
    assert "flow_prompt_en" not in shot.model_dump()


@pytest.mark.parametrize(
    "raw, target",
    [
        ('{"title":"x","narration":"y","continuity_anchor":"Nhân vật và bối cảnh cố định xuyên suốt video.","shots":[]}', 30),
        ('{"title":"x","narration":"y","shots":[{"shot_id":"s1","scene":"A","narration":"a","prompt":"B","duration_seconds":10}]}', 30),
        ('{"title":"x","narration":"y","shots":[{"shot_id":"s1","scene":"A","narration":"a","prompt":"B","duration_seconds":11},{"shot_id":"s2","scene":"C","narration":"c","prompt":"D","duration_seconds":9},{"shot_id":"s3","scene":"E","narration":"e","prompt":"F","duration_seconds":10}]}', 30),
        ('{"title":"x","narration":"y","shots":[{"shot_id":"s1","scene":"A","narration":"a","prompt":"B","duration_seconds":10},{"shot_id":"s1","scene":"C","narration":"c","prompt":"D","duration_seconds":10},{"shot_id":"s3","scene":"E","narration":"e","prompt":"F","duration_seconds":10}]}', 30),
        ('{"title":"x","narration":"y","shots":[{"shot_id":"s1","scene":"A","narration":"a","prompt":"B","duration_seconds":10},{"shot_id":"s2","scene":"C","narration":"c","prompt":"D","duration_seconds":10},{"shot_id":"s3","scene":"E","narration":"e","prompt":"F","duration_seconds":10}]}', 19),
    ],
)
def test_storyboard_rejects_invalid_shot_lists(raw: str, target: int):
    with pytest.raises(ValueError):
        parse_storyboard(raw, target_duration_seconds=target)


def test_video_qc_rejects_wrong_dimensions_and_duration():
    issues = evaluate_video_qc(
        {"width": 720, "height": 1280, "codec_name": "h264", "duration_seconds": 29.0, "frame_rate": 30.0},
        expected_duration_seconds=30,
        decode_ok=True,
    )

    assert "DIMENSIONS" in issues
    assert "DURATION" in issues
    assert "DECODE" not in issues


def test_flow_pre_submit_failure_is_resumable_without_reconciliation():
    run = SimpleNamespace(status="RUNNING", error_code=None, error_message=None, finished_at=None, steps_json="")
    steps = [{"shot_id": "shot_01", "state": "SUBMITTING"}, {"shot_id": "shot_02", "state": "READY"}]

    assert _mark_flow_setup_blocked(run, steps, RuntimeError("video mode control missing"))
    assert run.status == "BLOCKED_FLOW_SETUP"
    assert run.error_code == "FLOW_REQUEST_NOT_SUBMITTED"
    assert run.finished_at is None
    assert steps[0]["state"] == "READY"
    assert not _mark_flow_setup_blocked(run, [{"state": "NEEDS_RECONCILIATION"}], RuntimeError("unknown submission"))


def test_flow_credit_block_is_reported_without_submission():
    run = SimpleNamespace(status="RUNNING", error_code=None, error_message=None, finished_at=None, steps_json="")
    steps = [{"shot_id": "shot_04", "state": "SUBMITTING"}]

    assert _mark_flow_setup_blocked(run, steps, RuntimeError("FLOW_CREDITS_INSUFFICIENT: shot chưa được gửi"))
    assert run.status == "BLOCKED_FLOW_SETUP"
    assert run.error_code == "FLOW_CREDITS_INSUFFICIENT"
    assert steps[0]["state"] == "READY"


def test_content_video_render_preserves_native_flow_audio_qc(monkeypatch, tmp_path):
    from src.models.entities import MediaAsset, TimelineVersion
    from src.modules.tao_video_noi_dung import runner

    shot_assets = {
        f"shot-{index}": SimpleNamespace(
            id=f"shot-{index}", sha256=f"hash-{index}", duration_ms=10000,
            workspace_id="ws", project_id="project",
        )
        for index in range(1, 4)
    }

    class Query:
        def __init__(self, model):
            self.model = model
            self.asset_id = None

        def filter(self, *criteria):
            for criterion in criteria:
                if getattr(getattr(criterion, "left", None), "key", None) == "id":
                    self.asset_id = criterion.right.value
            return self

        def order_by(self, *_args):
            return self

        def first(self):
            return None if self.model is TimelineVersion else shot_assets.get(self.asset_id)

    class DB:
        def __init__(self):
            self.added = []

        def query(self, model):
            return Query(model)

        def add(self, item):
            self.added.append(item)

        def commit(self):
            pass

    captured = {}
    def render(timeline, _resolver, output_path, transition_seconds, caption_style):
        captured["timeline"] = timeline
        captured["transition_seconds"] = transition_seconds
        captured["caption_style"] = caption_style
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"rendered video")
        return {"flow_native_audio": True}

    monkeypatch.setattr(runner, "_voice_input", lambda *_args: None)
    monkeypatch.setattr(runner, "get_workspace_storage_dir", lambda _workspace: tmp_path)
    monkeypatch.setattr(runner.video_processor, "render_timeline_document", render)
    monkeypatch.setattr(runner.video_processor, "probe_video", lambda _path: {
        "width": 1920, "height": 1080, "codec_name": "h264", "frame_rate": 30.0,
        "duration_seconds": 30.0,
    })
    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr(runner.audio_processor, "verify_audio_qc", lambda *_args, **_kwargs: {"status": "PASS", "passed": True})
    monkeypatch.setattr(runner, "_write_export_package", lambda path, *_args: path.write_bytes(b"export"))

    shots = [SimpleNamespace(shot_id=f"shot-{index}", duration_seconds=10) for index in range(1, 4)]
    storyboard = SimpleNamespace(shots=shots)
    plan = SimpleNamespace(
        target_duration_seconds=30, style_snapshot_sha256="style-hash", source_content="source",
        storyboard_json="{}", style_snapshot_json='{"aspect_ratio":"16:9"}', id="plan", revision=1,
    )
    run = SimpleNamespace(
        id="run", workspace_id="ws", project_id="project", created_by="creator",
        voice_asset_id=None, steps_json="[]", output_asset_ids_json="[]",
    )

    runner._render_and_qc(DB(), run, plan, storyboard, list(shot_assets))

    assert captured["timeline"].captions == []
    assert (captured["timeline"].width, captured["timeline"].height) == (1920, 1080)
    assert captured["timeline"].voice_track is None
    assert captured["transition_seconds"] == 0.3
    assert captured["caption_style"] == "vietsub_v1"
    report = json.loads(run.qc_report_json)
    assert report["voice_source"] == "FLOW_NATIVE"
    assert report["flow_native_audio"] is True
    assert report["audio_qc"]["status"] == "PASS"
    assert run.status == "COMPLETED"


def test_shot_qc_allows_provider_clip_longer_than_used_trim_but_rejects_short_clip():
    meta = {"width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 30.0}

    assert "DURATION" not in evaluate_shot_qc({**meta, "duration_seconds": 10.0}, used_duration_seconds=7)
    assert "DURATION" in evaluate_shot_qc({**meta, "duration_seconds": 6.0}, used_duration_seconds=7)


def test_shot_qc_accepts_native_flow_720p_when_aspect_ratio_matches():
    meta = {
        "width": 720, "height": 1280, "codec_name": "h264", "frame_rate": 24.0,
        "duration_seconds": 10.0,
    }

    assert "DIMENSIONS" not in evaluate_shot_qc(meta, used_duration_seconds=7, aspect_ratio="9:16")
    assert "DIMENSIONS" in evaluate_shot_qc(meta, used_duration_seconds=7, aspect_ratio="16:9")


def test_shot_qc_rejects_wrong_frame_rate():
    meta = {"width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 20.0, "duration_seconds": 10.0}

    assert "FRAME_RATE" in evaluate_shot_qc(meta, used_duration_seconds=10)


def test_shot_qc_rejects_decode_failure():
    meta = {"width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 30.0, "duration_seconds": 10.0}

    assert "DECODE" in evaluate_shot_qc(meta, used_duration_seconds=10, decode_ok=False)


def test_pipeline_rejects_reused_shot_media_hashes():
    assert _has_duplicate_shot_media(["a", "b", "a"])
    assert not _has_duplicate_shot_media(["a", "b", "c"])


def test_video_qc_accepts_user_selected_landscape_ratio():
    meta = {"width": 1920, "height": 1080, "codec_name": "h264", "frame_rate": 30.0, "duration_seconds": 10.0}

    assert evaluate_video_qc(meta, 10, decode_ok=True, aspect_ratio="16:9") == []


def test_plan_request_persists_user_selected_aspect_ratio():
    request = CreatePlanRequest.model_validate({
        "content": "Một chủ đề đủ dài để tạo video minh họa về công nghệ trí tuệ nhân tạo.",
        "target_duration_seconds": 30,
        "aspect_ratio": "16:9",
    })

    assert request.aspect_ratio == "16:9"
    with pytest.raises(ValueError):
        CreatePlanRequest.model_validate({
            "content": "Một chủ đề đủ dài để tạo video minh họa về công nghệ trí tuệ nhân tạo.",
            "target_duration_seconds": 30,
            "aspect_ratio": "1:1",
        })


def test_plan_request_cannot_override_server_style_profile():
    with pytest.raises(ValueError):
        CreatePlanRequest.model_validate({
            "content": "Một chủ đề có đủ độ dài để lập storyboard nhất quán cho video.",
            "target_duration_seconds": 30,
            "style_snapshot": {"style_name": "random", "visual_rules": "different style", "palette": ["pink"]},
        })


def _approved_harness_shot():
    style = {"style_name": "Pilot", "visual_rules": "Giữ cùng chủ thể và ánh sáng mềm.", "palette": ["navy"], "aspect_ratio": "16:9"}
    anchor = "Một người dẫn mặc áo navy trong studio sáng mềm xuyên suốt video."
    shot = StoryboardShot(
        shot_id="shot-1",
        scene="Mở đầu trong studio",
        narration="Lời dẫn mở đầu.",
        prompt="Người dẫn mở đầu chủ đề.",
        flow_prompt_en="A paper assistant introduces the subject with one small hand gesture.",
        duration_seconds=10,
    )
    storyboard_data = {"continuity_anchor": anchor}
    plan = SimpleNamespace(
        id="plan-1",
        revision=1,
        status="APPROVED",
        approved_by="reviewer-1",
        approved_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        workspace_id="workspace-1",
        project_id="project-1",
        storyboard_sha256=cong_harness.canonical_hash(storyboard_data),
        style_snapshot_sha256=cong_harness.canonical_hash(style),
        style_snapshot_json=json.dumps(style),
        storyboard_json=json.dumps(storyboard_data),
    )
    run = SimpleNamespace(
        id="run-1",
        workspace_id=plan.workspace_id,
        project_id=plan.project_id,
        plan_id=plan.id,
        voice_asset_id="voice-1",
        plan_revision=plan.revision,
        storyboard_sha256=plan.storyboard_sha256,
        style_snapshot_sha256=plan.style_snapshot_sha256,
        approval_sha256=cong_harness.approval_receipt_hash(plan),
        created_by="creator-1",
    )
    step = build_shot_receipt(
        run_id=run.id,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        plan=plan,
        voice_asset_id=run.voice_asset_id,
        shot=shot,
        style_snapshot=style,
        continuity_anchor=anchor,
    )
    step["state"] = "SUBMITTING"
    return run, plan, shot, step


def test_harness_dispatches_only_approved_immutable_shot_receipt(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    calls = []
    expected_asset = object()
    monkeypatch.setattr(
        cong_harness.video_orchestrator,
        "generate_video_scene",
        lambda **kwargs: calls.append(kwargs) or expected_asset,
    )

    result = dispatch_shot(db=object(), run=run, plan=plan, shot=shot, step=step)

    assert result is expected_asset
    assert len(calls) == 1
    assert calls[0]["prompt"] == step["prompt"]
    assert calls[0]["prompt_language"] == "vi"
    assert calls[0]["aspect_ratio"] == "16:9"
    assert calls[0]["include_audio"] is True
    assert calls[0]["project_id"] == run.project_id


def test_harness_blocks_tampered_shot_receipt_before_provider_call(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    calls = []
    monkeypatch.setattr(cong_harness.video_orchestrator, "generate_video_scene", lambda **kwargs: calls.append(kwargs))
    step["prompt"] += " chuyển sang anime"

    with pytest.raises(RuntimeError, match="HARNESS_COMMAND_RECEIPT_INVALID"):
        dispatch_shot(db=object(), run=run, plan=plan, shot=shot, step=step)

    assert calls == []


def test_harness_binds_the_selected_voice_asset_before_provider_call(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    calls = []
    monkeypatch.setattr(cong_harness.video_orchestrator, "generate_video_scene", lambda **kwargs: calls.append(kwargs))
    step["voice_asset_id"] = "another-voice"

    with pytest.raises(RuntimeError, match="HARNESS_COMMAND_RECEIPT_INVALID"):
        dispatch_shot(db=object(), run=run, plan=plan, shot=shot, step=step)

    assert calls == []


def test_voice_preflight_rejects_audio_that_does_not_match_target_duration(monkeypatch, tmp_path):
    from src.modules.tao_video_noi_dung import runner

    voice_path = tmp_path / "voice.mp3"
    voice_path.write_bytes(b"audio fixture")
    asset = SimpleNamespace(
        id="voice-1", workspace_id="workspace-1", project_id="project-1",
        storage_key="voice.mp3", mime_detected="audio/mpeg", sha256=hashlib.sha256(voice_path.read_bytes()).hexdigest(),
    )
    query = SimpleNamespace(filter=lambda *args: query, first=lambda: asset)
    db = SimpleNamespace(query=lambda model: query)
    run = SimpleNamespace(id="run-1", voice_asset_id=asset.id, workspace_id=asset.workspace_id, project_id=asset.project_id)
    plan = SimpleNamespace(target_duration_seconds=30)
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr(runner.audio_processor, "probe_audio", lambda path: {"duration_seconds": 29, "codec_name": "mp3"})

    with pytest.raises(RuntimeError, match="VOICE_ASSET_DURATION_MISMATCH"):
        runner._voice_input(db, run, plan)


def test_voice_preflight_rejects_asset_bytes_that_do_not_match_recorded_hash(monkeypatch, tmp_path):
    from src.modules.tao_video_noi_dung import runner

    voice_path = tmp_path / "voice.mp3"
    voice_path.write_bytes(b"changed audio")
    asset = SimpleNamespace(
        id="voice-1", workspace_id="workspace-1", project_id="project-1",
        storage_key="voice.mp3", mime_detected="audio/mpeg", sha256="recorded-hash",
    )
    query = SimpleNamespace(filter=lambda *args: query, first=lambda: asset)
    db = SimpleNamespace(query=lambda model: query)
    run = SimpleNamespace(id="run-1", voice_asset_id=asset.id, workspace_id=asset.workspace_id, project_id=asset.project_id)
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)

    with pytest.raises(RuntimeError, match="VOICE_ASSET_HASH_MISMATCH"):
        runner._voice_input(db, run, SimpleNamespace(target_duration_seconds=30))


def test_export_package_contains_video_editable_plan_qc_and_hash_manifest(tmp_path):
    import zipfile
    from src.modules.tao_video_noi_dung.runner import _write_export_package
    from src.schemas.contracts import TimelineDocument

    video = tmp_path / "final.mp4"
    video.write_bytes(b"video fixture")
    package = tmp_path / "export.zip"
    run = SimpleNamespace(id="run-1", voice_asset_id=None)
    plan = SimpleNamespace(
        id="plan-1", revision=2, source_content="Nội dung nguồn", storyboard_json='{"shots":[]}',
        style_snapshot_sha256="style-hash",
    )
    report = {"status": "PASS", "acceptance_mode": "HYBRID", "speech_alignment": "NOT_MEASURED"}

    _write_export_package(
        package, video, run, plan, TimelineDocument(), report,
        [{"asset_id": "shot-1", "sha256": "shot-hash"}],
        [{"shot_id": "shot-1", "prompt": "Prompt", "command_sha256": "receipt-hash", "asset_id": "shot-1"}],
        None,
    )

    with zipfile.ZipFile(package) as archive:
        assert {"video/final.mp4", "plan/storyboard.json", "timeline/timeline.json", "production/shots.json", "qc/report.json", "manifest.json"} <= set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        qc_report = json.loads(archive.read("qc/report.json"))
        assert manifest["acceptance_mode"] == "HYBRID"
        assert manifest["voice_asset"] is None
        assert manifest["speech_alignment"] == "NOT_MEASURED"
        assert qc_report["acceptance_mode"] == "HYBRID"
        assert manifest["files"]["video/final.mp4"] == hashlib.sha256(video.read_bytes()).hexdigest()


def test_harness_blocks_changed_persisted_style_snapshot(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    calls = []
    monkeypatch.setattr(cong_harness.video_orchestrator, "generate_video_scene", lambda **kwargs: calls.append(kwargs))
    plan.style_snapshot_json = json.dumps({"style_name": "Other", "visual_rules": "đổi style", "palette": ["pink"]})

    with pytest.raises(RuntimeError, match="APPROVED_PLAN_HASH_CHANGED"):
        dispatch_shot(db=object(), run=run, plan=plan, shot=shot, step=step)

    assert calls == []


def test_plan_approval_authorizes_the_persisted_plan_as_a_resource(monkeypatch):
    from src.config import settings

    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CONTENT_VIDEO_TEST_SELF_APPROVAL", "1")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "database_url", "sqlite:///./sin_content_e2e_test.db")
    plan = SimpleNamespace(
        id="plan-1",
        created_by="creator-1",
        revision=4,
        storyboard_sha256="storyboard-hash",
    )
    authorization = {}
    monkeypatch.setattr(content_video_router, "get_plan", lambda *args: plan)
    monkeypatch.setattr(
        content_video_router,
        "authorize_resource",
        lambda tenant, action, **resource: authorization.update(
            tenant=tenant, action=action, **resource
        ),
    )
    monkeypatch.setattr(content_video_router, "approve_plan", lambda *args: "approved")
    tenant = SimpleNamespace(workspace_id="workspace-1", user_id="reviewer-1")

    result = content_video_router.approve_content_video_plan(
        "project-1", "plan-1", db=object(), tenant=tenant
    )

    assert result == "approved"
    assert authorization == {
        "tenant": tenant,
        "action": "media.approve",
        "resource_type": "content_video_plan",
        "resource_id": "plan-1",
        "workspace_id": "workspace-1",
        "creator_id": "creator-1",
        "artifact_version": 4,
        "content_hash": "storyboard-hash",
        "project_id": "project-1",
        "require_creator": True,
    }


def test_plan_creator_can_self_approve_only_in_explicit_e2e_test_mode(monkeypatch):
    plan = SimpleNamespace(id="plan-1", created_by="creator-1", revision=1, storyboard_sha256="hash")
    monkeypatch.setattr(content_video_router, "get_plan", lambda *args: plan)
    monkeypatch.setattr(content_video_router, "approve_plan", lambda *args: "approved")
    monkeypatch.setattr(content_video_router, "authorize_resource", lambda *_args, **_kwargs: pytest.fail("test mode should allow self-approval"))
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("BAHA_AUTH_APP_ENV", "test")
    monkeypatch.setenv("BAHA_AUTH_ALLOW_SELF_APPROVAL_IN_TEST", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sin_content_e2e_test.db")
    monkeypatch.setenv("BAHA_AUTH_DATABASE_URL", "sqlite:///./baha_auth_e2e_test.db")
    tenant = SimpleNamespace(workspace_id="workspace-1", user_id="creator-1")

    assert content_video_router.approve_content_video_plan("project-1", "plan-1", db=object(), tenant=tenant) == "approved"


def test_creator_can_edit_draft_storyboard_and_updates_hash(monkeypatch):
    from src.modules.tao_video_noi_dung.service import update_plan
    from src.modules.tao_video_noi_dung.planner import Storyboard

    original = Storyboard.model_validate({
        "title": "Bản AI", "narration": "Thoại cũ", "continuity_anchor": "Nhân vật origami xanh navy giữ nguyên xuyên suốt các cảnh.",
        "shots": [
            {"shot_id": "s1", "scene": "Cảnh cũ 1", "narration": "Thoại cũ 1", "prompt": "Cảnh origami thứ nhất.", "duration_seconds": 10},
            {"shot_id": "s2", "scene": "Cảnh cũ 2", "narration": "Thoại cũ 2", "prompt": "Cảnh origami thứ hai.", "duration_seconds": 10},
            {"shot_id": "s3", "scene": "Cảnh cũ 3", "narration": "Thoại cũ 3", "prompt": "Cảnh origami thứ ba.", "duration_seconds": 10},
        ],
    })
    plan = SimpleNamespace(
        id="plan-1", project_id="project-1", workspace_id="workspace-1", revision=1, status="DRAFT",
        source_content="Nội dung nguồn", content_sha256="content-hash", target_duration_seconds=30,
        style_snapshot_json='{"style_name":"Origami","visual_rules":"Quy tắc hình ảnh origami rõ ràng.","palette":["navy"],"aspect_ratio":"9:16"}',
        style_snapshot_sha256="style-hash", storyboard_json=original.model_dump_json(),
        storyboard_sha256="old-hash", llm_model="test", created_by="creator-1", approved_by=None,
        approved_at=None, created_at=datetime.now(timezone.utc),
    )

    class Query:
        def __init__(self, model): self.model = model
        def filter(self, *_args): return self
        def with_for_update(self): return self
        def first(self): return plan

    class DB:
        def query(self, model): return Query(model)
        def commit(self): pass
        def refresh(self, _plan): pass

    changed = original.model_copy(deep=True)
    changed.title = "Bản đã sửa"
    changed.shots[0].narration = "Thoại do người dùng viết lại"
    changed.narration = "Thoại do người dùng viết lại. Thoại cũ 2. Thoại cũ 3."
    before_hash = plan.storyboard_sha256

    result = update_plan(DB(), "project-1", "plan-1", "workspace-1", "creator-1", changed)

    assert result.storyboard.title == "Bản đã sửa"
    assert result.storyboard.shots[0].narration == "Thoại do người dùng viết lại"
    assert result.storyboard_sha256 != before_hash


def test_storyboard_edit_rejects_non_creator_and_changes_to_shot_timing():
    from fastapi import HTTPException
    from src.modules.tao_video_noi_dung.service import update_plan
    from src.modules.tao_video_noi_dung.planner import Storyboard

    storyboard = Storyboard.model_validate({
        "title": "Bản AI", "narration": "Thoại", "continuity_anchor": "Nhân vật origami xanh navy giữ nguyên xuyên suốt các cảnh.",
        "shots": [
            {"shot_id": f"s{i}", "scene": f"Cảnh {i}", "narration": f"Thoại {i}", "prompt": f"Cảnh origami số {i}.", "duration_seconds": 10}
            for i in range(1, 4)
        ],
    })
    plan = SimpleNamespace(id="plan-1", project_id="project-1", workspace_id="workspace-1", status="DRAFT", created_by="creator-1", storyboard_json=storyboard.model_dump_json())

    class Query:
        def filter(self, *_args): return self
        def with_for_update(self): return self
        def first(self): return plan
    class DB:
        def query(self, _model): return Query()

    with pytest.raises(HTTPException) as denied:
        update_plan(DB(), "project-1", "plan-1", "workspace-1", "other-user", storyboard)
    assert denied.value.status_code == 403

    changed = storyboard.model_copy(deep=True)
    changed.shots[0].duration_seconds = 9
    changed.shots[1].duration_seconds = 11
    with pytest.raises(HTTPException) as invalid:
        update_plan(DB(), "project-1", "plan-1", "workspace-1", "creator-1", changed)
    assert invalid.value.status_code == 422

    plan.status = "APPROVED"
    with pytest.raises(HTTPException) as locked:
        update_plan(DB(), "project-1", "plan-1", "workspace-1", "creator-1", storyboard)
    assert locked.value.status_code == 409


def test_reconciliation_route_uses_authenticated_operator_and_project_scope(monkeypatch):
    calls = []
    current_run = object()
    monkeypatch.setattr(content_video_router, "reconcile_shot", lambda *args: calls.append(args))
    monkeypatch.setattr(content_video_router, "get_run", lambda *args: current_run)
    tenant = SimpleNamespace(workspace_id="workspace-1", user_id="operator-1")
    request = ReconcileShotRequest(
        shot_id="shot-1", asset_id="asset-1", reason="Đã so clip trong Flow với đúng shot.",
    )

    result = content_video_router.reconcile_content_video_run(
        "project-1", "run-1", request, db="db", tenant=tenant
    )

    assert result is current_run
    assert calls == [("db", "project-1", "run-1", "workspace-1", "operator-1", request)]

def test_tts_run_contract_requires_one_explicit_provider_and_gwen_reference():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateRunRequest(plan_id="plan-1", idempotency_key="tts-contract-001", voice_source="TTS")
    with pytest.raises(ValidationError):
        CreateRunRequest(plan_id="plan-1", idempotency_key="tts-contract-002", voice_source="TTS", tts_provider="GWEN_TTS")
    with pytest.raises(ValidationError):
        CreateRunRequest(plan_id="plan-1", idempotency_key="tts-contract-003", voice_asset_id="asset-1", voice_source="TTS", tts_provider="VIE_NEU_V3_TURBO")

    request = CreateRunRequest(
        plan_id="plan-1", idempotency_key="tts-contract-004", voice_source="TTS",
        tts_provider="GWEN_TTS", tts_reference_asset_id="reference-1",
        tts_reference_text="Đây là bản ghi tham chiếu chính xác.", voice_clone_consent=True,
    )
    assert request.voice_asset_id is None
    assert request.tts_provider == "GWEN_TTS"


def test_tts_provider_manager_switches_one_loaded_model_without_fallback():
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError, TTSProviderManager

    events = []
    class Model:
        def __init__(self, name):
            self.name = name
            events.append(f"load:{name}")
        def __del__(self):
            events.append(f"unload:{self.name}")
        def infer(self, text, **kwargs):
            return (self.name, text, kwargs), 48000
        def generate_voice_clone(self, **kwargs):
            return [(self.name, kwargs["text"], kwargs)], 48000

    manager = TTSProviderManager({name: (lambda name=name: Model(name)) for name in ("GWEN_TTS", "VIE_NEU_V3_TURBO")})
    assert manager.synthesize({"provider": "GWEN_TTS", "reference_text": "đọc"}, "Xin chào")[0][0] == "GWEN_TTS"
    assert manager.synthesize({"provider": "VIE_NEU_V3_TURBO"}, "Xin chào")[0][0][0] == "VIE_NEU_V3_TURBO"
    assert events == ["load:GWEN_TTS", "unload:GWEN_TTS", "load:VIE_NEU_V3_TURBO"]
    with pytest.raises(TTSProviderError, match="TTS_PROVIDER_UNSUPPORTED"):
        manager.synthesize({"provider": "OTHER"}, "Xin chào")


def test_tts_worker_saves_one_project_scoped_asset_and_reuses_it(tmp_path, monkeypatch):
    import numpy as np

    added = []
    generated = []
    db = SimpleNamespace(add=added.append, commit=lambda: None, refresh=lambda _item: None)
    run = SimpleNamespace(
        id="run-tts-1", workspace_id="workspace-1", project_id="project-1", created_by="creator-1",
        tts_config_json='{"provider":"VIE_NEU_V3_TURBO","voice_id":"Hải Đăng"}',
        voice_asset_id=None, output_asset_ids_json="[]",
    )
    storyboard = SimpleNamespace(narration="Lời dẫn đã duyệt.")
    monkeypatch.setattr("src.modules.tao_video_noi_dung.runner.MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr("src.modules.tao_video_noi_dung.runner.audio_processor.probe_audio", lambda _path: {"codec_name": "pcm_s16le", "duration_seconds": 20})
    monkeypatch.setattr("src.modules.tao_video_noi_dung.runner.tts_provider_manager.synthesize", lambda *args: generated.append(args) or (np.zeros(20 * 100), 100))
    plan = SimpleNamespace(target_duration_seconds=20)

    from src.modules.tao_video_noi_dung.runner import _generate_tts_voice
    _generate_tts_voice(db, run, plan, storyboard)
    asset = added[0]
    _generate_tts_voice(db, run, plan, storyboard)

    assert len(generated) == 1
    assert asset.workspace_id == run.workspace_id and asset.project_id == run.project_id
    assert asset.source_product == "CONTENT_VIDEO_TTS"
    assert run.voice_asset_id == asset.id
    assert json.loads(run.output_asset_ids_json) == [asset.id]
    assert (tmp_path / asset.storage_key).is_file()


def test_tts_run_idempotency_and_response_keep_reference_text_private():
    from src.modules.tao_video_noi_dung.service import _run_response, _same_run_request

    config = json.dumps({"provider": "GWEN_TTS", "reference_text": "transcript kín"})
    run = SimpleNamespace(
        id="run-1", workspace_id="workspace-1", project_id="project-1", plan_id="plan-1",
        plan_revision=1, voice_asset_id="generated-asset", tts_config_json=config,
        status="QUEUED", current_step=None, steps_json="[]", output_asset_ids_json="[]",
        final_asset_id=None, qc_report_json=None, error_code=None, error_message=None,
        created_at=datetime.now(timezone.utc), started_at=None, finished_at=None,
    )

    assert _same_run_request(run, "workspace-1", "project-1", "plan-1", None, config)
    assert not _same_run_request(run, "workspace-1", "project-1", "plan-1", None, json.dumps({"provider": "VIE_NEU_V3_TURBO"}))
    response = _run_response(run).model_dump_json()
    assert '"tts_provider":"GWEN_TTS"' in response
    assert "transcript kín" not in response
