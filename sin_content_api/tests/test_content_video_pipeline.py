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
from src.modules.tao_video_noi_dung.runner import evaluate_shot_qc, evaluate_video_qc
from src.modules.tao_video_noi_dung.runner import _mark_flow_setup_blocked
from src.modules.tao_video_noi_dung import cong_harness
from src.modules.tao_video_noi_dung import router as content_video_router
from src.modules.tao_video_noi_dung.cong_harness import build_shot_receipt, dispatch_shot
from src.modules.tao_video_noi_dung.planner import StoryboardShot
from src.migrations import runner as migration_runner


def test_content_video_migration_upgrades_existing_run_table(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE content_video_runs (id VARCHAR(36) PRIMARY KEY)"))
        monkeypatch.setattr(migration_runner, "engine", engine)

        migration_runner.migration_up()

        columns = {column["name"] for column in inspect(engine).get_columns("content_video_runs")}
        assert "voice_asset_id" in columns
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
    assert all(f'“{shot.narration}”' in prompt and "cùng một giọng thuyết minh" in prompt for shot, prompt in zip(storyboard.shots, prompts, strict=True))
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


def test_storyboard_prompt_requires_three_shots_for_twenty_seconds():
    class RecordingClient:
        max_output_tokens = 6000

        def complete(self, messages, max_tokens):
            self.messages = messages
            return SimpleNamespace(
                content=(
                    '{"title":"RAG","narration":"Tìm đúng nguồn.",'
                    '"continuity_anchor":"Trợ lý giấy xanh navy cạnh tủ tài liệu, cùng một bối cảnh.","shots":['
                    '{"shot_id":"s1","scene":"Tìm","narration":"Tìm nguồn.","prompt":"Thẻ tài liệu bay ra.","duration_seconds":7},'
                    '{"shot_id":"s2","scene":"Trả lời","narration":"Trả lời có căn cứ.","prompt":"Trợ lý đọc tài liệu.","duration_seconds":7},'
                    '{"shot_id":"s3","scene":"Kết","narration":"Thử RAG.","prompt":"Nguồn và câu trả lời.","duration_seconds":6}]}'
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
                    '{"shot_id":"s1","scene":"Tìm","narration":"Tìm nguồn.","prompt":"Một thẻ trượt tới.","duration_seconds":7},'
                    '{"shot_id":"s2","scene":"Trả lời","narration":"Trả lời.","prompt":"Trợ lý đọc thẻ.","duration_seconds":7},'
                    '{"shot_id":"s3","scene":"Kết","narration":"Xong.","prompt":"Đặt thẻ lại.","duration_seconds":6}]}'
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
    assert "không biến hình" in shot_prompt
    assert "không nhân đôi" in shot_prompt
    assert "chuyển động liên tục" in shot_prompt


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


def test_content_video_render_keeps_narration_as_audio_without_caption_text(monkeypatch, tmp_path):
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
    def render(timeline, _resolver, output_path, transition_seconds):
        captured["timeline"] = timeline
        captured["transition_seconds"] = transition_seconds
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"rendered video")

    voice = SimpleNamespace(id="voice-1", sha256="voice-hash")
    monkeypatch.setattr(runner, "_voice_input", lambda *_args: None)
    monkeypatch.setattr(runner, "_flow_voice_asset", lambda *_args: voice)
    monkeypatch.setattr(runner, "get_workspace_storage_dir", lambda _workspace: tmp_path)
    monkeypatch.setattr(runner.video_processor, "render_timeline_document", render)
    monkeypatch.setattr(runner.video_processor, "probe_video", lambda _path: {
        "width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 30.0,
        "duration_seconds": 30.0,
    })
    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr(runner.audio_processor, "verify_audio_qc", lambda *_args, **_kwargs: {"passed": True})
    monkeypatch.setattr(runner, "_write_export_package", lambda path, *_args: path.write_bytes(b"export"))

    shots = [SimpleNamespace(shot_id=f"shot-{index}", duration_seconds=10) for index in range(1, 4)]
    storyboard = SimpleNamespace(shots=shots)
    plan = SimpleNamespace(
        target_duration_seconds=30, style_snapshot_sha256="style-hash", source_content="source",
        storyboard_json="{}", id="plan", revision=1,
    )
    run = SimpleNamespace(
        id="run", workspace_id="ws", project_id="project", created_by="creator",
        voice_asset_id=None, steps_json="[]", output_asset_ids_json="[]",
    )

    runner._render_and_qc(DB(), run, plan, storyboard, list(shot_assets))

    assert captured["timeline"].captions == []
    assert captured["transition_seconds"] == 0.3
    assert run.status == "COMPLETED"


def test_shot_qc_allows_provider_clip_longer_than_used_trim_but_rejects_short_clip():
    meta = {"width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 30.0}

    assert "DURATION" not in evaluate_shot_qc({**meta, "duration_seconds": 10.0}, used_duration_seconds=7)
    assert "DURATION" in evaluate_shot_qc({**meta, "duration_seconds": 6.0}, used_duration_seconds=7)


def test_plan_request_cannot_override_server_style_profile():
    with pytest.raises(ValueError):
        CreatePlanRequest.model_validate({
            "content": "Một chủ đề có đủ độ dài để lập storyboard nhất quán cho video.",
            "target_duration_seconds": 30,
            "style_snapshot": {"style_name": "random", "visual_rules": "different style", "palette": ["pink"]},
        })


def _approved_harness_shot():
    style = {"style_name": "Pilot", "visual_rules": "Giữ cùng chủ thể và ánh sáng mềm.", "palette": ["navy"]}
    anchor = "Một người dẫn mặc áo navy trong studio sáng mềm xuyên suốt video."
    shot = StoryboardShot(
        shot_id="shot-1",
        scene="Mở đầu trong studio",
        narration="Lời dẫn mở đầu.",
        prompt="Người dẫn mở đầu chủ đề.",
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
    run = SimpleNamespace(id="run-1", voice_asset_id="voice-1")
    plan = SimpleNamespace(
        id="plan-1", revision=2, source_content="Nội dung nguồn", storyboard_json='{"shots":[]}',
        style_snapshot_sha256="style-hash",
    )
    voice = SimpleNamespace(id="voice-1", sha256="voice-hash")
    report = {"status": "PASS", "acceptance_mode": "HYBRID", "speech_alignment": "NOT_MEASURED"}

    _write_export_package(
        package, video, run, plan, TimelineDocument(), report,
        [{"asset_id": "shot-1", "sha256": "shot-hash"}],
        [{"shot_id": "shot-1", "prompt": "Prompt", "command_sha256": "receipt-hash", "asset_id": "shot-1"}],
        voice,
    )

    with zipfile.ZipFile(package) as archive:
        assert {"video/final.mp4", "plan/storyboard.json", "timeline/timeline.json", "production/shots.json", "qc/report.json", "manifest.json"} <= set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        qc_report = json.loads(archive.read("qc/report.json"))
        assert manifest["acceptance_mode"] == "HYBRID"
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
