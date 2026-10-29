"""UI_SIM dùng MediaAsset/receipt hiện có, source CONTENT_VIDEO_UI_SIM; không gọi Flow."""
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.modules.tao_video_noi_dung.planner import UiScene
from src.modules.tao_video_noi_dung.runner import evaluate_shot_qc


def scene(layout="CHAT"):
    return UiScene(layout=layout, messages=[
        {"role": "customer", "text": "Tôi cần hỗ trợ lúc hai giờ sáng. Giá bao nhiêu?", "at_s": 0},
        {"role": "ai", "text": "Chào bạn! AI có thể tìm thông tin và gửi tới nhân viên.", "at_s": 0.8},
    ], highlight="Phản hồi ngoài giờ, không bỏ sót khách hàng")


@pytest.mark.parametrize("ratio,layout", [("9:16", "CHAT"), ("16:9", "AI_PANEL"), ("16:9", "DASHBOARD")])
def test_render_chat_scene_passes_shot_qc(tmp_path, ratio, layout):
    from src.modules.tao_video_noi_dung.ui_sim import render_ui_scene
    out = tmp_path / "scene.mp4"
    meta = render_ui_scene(scene(layout), {}, 2, ratio, out)
    assert evaluate_shot_qc(meta, 2, aspect_ratio=ratio) == []
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-f", "null", "-"], check=True, capture_output=True, timeout=30)
    assert (meta["width"], meta["height"]) == ((1080, 1920) if ratio == "9:16" else (1920, 1080))


def test_render_scene_text_with_vietnamese_diacritics_not_clipped(tmp_path):
    from PIL import Image, ImageChops
    from playwright.sync_api import sync_playwright
    from src.modules.tao_video_noi_dung.ui_sim import _scene_html, render_ui_scene
    html = _scene_html(scene(), {})
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html)
        assert page.locator(".message").all_text_contents()[0].endswith("Giá bao nhiêu?")
        assert page.locator(".message").evaluate_all("els => els.every(e => e.scrollWidth <= e.clientWidth && e.getBoundingClientRect().bottom < innerHeight)")
        browser.close()
    out = tmp_path / "text.mp4"
    render_ui_scene(scene(), {}, 2, "9:16", out)
    frame = tmp_path / "middle.png"
    subprocess.run(["ffmpeg", "-v", "error", "-ss", "1.5", "-i", str(out), "-frames:v", "1", str(frame)], check=True, capture_output=True)
    crop = Image.open(frame).convert("RGB").crop((120, 220, 900, 700))
    assert ImageChops.difference(crop, Image.new("RGB", crop.size, crop.getpixel((0, 0)))).getbbox()


def test_renderer_escapes_untrusted_text_and_blocks_overflow(tmp_path):
    from src.modules.tao_video_noi_dung.ui_sim import _scene_html, render_ui_scene
    data = scene().model_dump()
    data["messages"][0]["text"] = '<script>fetch("https://evil.test")</script>'
    assert "<script>" not in _scene_html(UiScene.model_validate(data), {})
    data["messages"] = [{"role": "ai", "text": "Nội dung rất dài " * 50, "at_s": 0}] * 30
    with pytest.raises(ValueError, match="UI_SCENE_TEXT_OVERFLOW"):
        render_ui_scene(UiScene.model_validate(data), {}, 2, "9:16", tmp_path / "too-long.mp4")
    assert not (tmp_path / "too-long.mp4").exists()


@pytest.mark.parametrize("production,fail_render", [(False, False), (True, False), (False, True)])
def test_runner_skips_flow_for_ui_sim_shot(tmp_path, monkeypatch, production, fail_render):
    from contextlib import nullcontext
    from tests.test_content_video_pipeline import _content_video_test_database, _seed_content_video_history, _v4_storyboard_data
    from src.models.entities import ContentVideoPlan, ContentVideoRun, MediaAsset
    from src.modules.tao_video_noi_dung import runner, cong_harness
    from src.modules.tao_video_noi_dung.planner import Storyboard

    if production:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setattr("src.modules.media_queue.service.authorized_worker_tenant", lambda *_: nullcontext())
        monkeypatch.setattr("src.modules.flow_sessions.service.resolve_profile", lambda *_: pytest.fail("UI_SIM requested Flow profile"))

    engine, Session = _content_video_test_database()
    data = _v4_storyboard_data()
    for shot in data["shots"]:
        shot.update(shot_kind="UI_SIM", action_beats=[], ui_scene=scene().model_dump())
    board = Storyboard.model_validate(data)
    monkeypatch.setattr(runner, "SessionLocal", Session)
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr(runner, "get_workspace_storage_dir", lambda _: tmp_path)
    monkeypatch.setattr(runner, "_heartbeat", lambda *_: True)
    monkeypatch.setattr(runner._RunHeartbeat, "start", lambda _: None)
    monkeypatch.setattr(runner._RunHeartbeat, "stop", lambda _: None)
    monkeypatch.setattr(runner, "_voice_input", lambda *_: None)
    monkeypatch.setattr(runner, "dispatch_shot", lambda **_: pytest.fail("UI_SIM called Flow"))
    def render(scene, style, duration, ratio, out):
        if fail_render:
            raise RuntimeError("render interrupted")
        out.write_bytes(json.dumps(scene.model_dump()).encode() + out.name.encode())
        return {}
    monkeypatch.setattr(runner, "render_ui_scene", render)
    monkeypatch.setattr(runner, "_probe_shot_with_qc", lambda *_: ({}, []))
    def finish(db, run, plan, storyboard, asset_ids):
        assert len(asset_ids) == 3
        run.status = "COMPLETED"
        db.commit()
    monkeypatch.setattr(runner, "_render_and_qc", finish)
    try:
        with Session() as db:
            _seed_content_video_history(db)
            plan, run = db.get(ContentVideoPlan, "plan-1"), db.get(ContentVideoRun, "run-1")
            plan.storyboard_json = board.model_dump_json()
            plan.storyboard_sha256 = cong_harness.canonical_hash(board.model_dump(mode="json"))
            run.storyboard_sha256 = plan.storyboard_sha256
            run.approval_sha256 = cong_harness.approval_receipt_hash(plan)
            run.status, run.lease_token = "RUNNING", "token"
            run.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            from src.models.entities import ContentVideoWorkerLease
            db.add(ContentVideoWorkerLease(name=runner.LEASE_NAME, token="token", expires_at=run.lease_expires_at))
            run.steps_json = json.dumps([cong_harness.build_shot_receipt(
                run_id=run.id, workspace_id=run.workspace_id, project_id=run.project_id, plan=plan,
                voice_asset_id=None, shot=shot, style_snapshot=json.loads(plan.style_snapshot_json),
                continuity_anchor=board.continuity_anchor) for shot in board.shots])
            db.commit()
        runner.process_run("run-1", "token")
        with Session() as db:
            run = db.get(ContentVideoRun, "run-1")
            if fail_render:
                assert run.status == "FAILED" and run.error_code == "UI_SIM_RENDER_FAILED"
                assert all(step["state"] == "READY" for step in json.loads(run.steps_json))
                return
            assert run.status == "COMPLETED", run.error_message
            assets = db.query(MediaAsset).filter_by(source_product="CONTENT_VIDEO_UI_SIM").all()
            assert len(assets) == 3
            assert all(a.workspace_id == run.workspace_id and a.project_id == run.project_id for a in assets)
    finally:
        engine.dispose()


def test_ui_receipt_binds_scene_and_rejects_flow_dispatch():
    from tests.test_content_video_pipeline import _approved_harness_shot
    from src.modules.tao_video_noi_dung import cong_harness
    from src.modules.tao_video_noi_dung.planner import StoryboardShot
    run, plan, _, _ = _approved_harness_shot()
    shot = StoryboardShot(shot_id="ui", scene="Hội thoại", narration="Khách hỏi ngoài giờ.", prompt="Mô phỏng cuộc hội thoại.",
        duration_seconds=3, prompt_contract_version=4, beat="DEMO", continues_previous=False,
        shot_kind="UI_SIM", ui_scene=scene())
    step = cong_harness.build_shot_receipt(run_id=run.id, workspace_id=run.workspace_id, project_id=run.project_id,
        plan=plan, voice_asset_id=run.voice_asset_id, shot=shot, style_snapshot=json.loads(plan.style_snapshot_json), continuity_anchor="Nhân viên giấy.")
    assert cong_harness.verify_shot_receipt(run, plan, shot, step)["shot_kind"] == "UI_SIM"
    step["state"] = "SUBMITTING"
    with pytest.raises(RuntimeError, match="FLOW_SHOT_REQUIRED"):
        cong_harness.dispatch_shot(db=None, run=run, plan=plan, shot=shot, step=step)
    shot.ui_scene.messages[0].text = "Nội dung bị sửa sau duyệt."
    with pytest.raises(RuntimeError, match="HARNESS_COMMAND_RECEIPT_INVALID"):
        cong_harness.verify_shot_receipt(run, plan, shot, step)


def test_ui_only_run_does_not_resolve_flow_profile_and_replays_idempotently(monkeypatch):
    from tests.test_content_video_pipeline import _content_video_test_database, _seed_content_video_history, _v4_storyboard_data
    from src.modules.tao_video_noi_dung import service, cong_harness
    from src.modules.tao_video_noi_dung.planner import Storyboard
    from src.modules.tao_video_noi_dung.contracts import CreateRunRequest
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr("src.modules.flow_sessions.service.resolve_profile", lambda *_: pytest.fail("UI-only run needs no profile"))
    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            plan, _, _ = _seed_content_video_history(db)
            data = _v4_storyboard_data()
            for shot in data["shots"]:
                shot.update(shot_kind="UI_SIM", action_beats=[], ui_scene=scene().model_dump())
            board = Storyboard.model_validate(data)
            plan.storyboard_json = board.model_dump_json()
            plan.storyboard_sha256 = cong_harness.canonical_hash(board.model_dump(mode="json"))
            db.commit()
            request = CreateRunRequest(plan_id=plan.id, idempotency_key="ui-only-run-001", flow_profile_id="unused-profile")
            run = service.create_run(db, "project-1", "workspace-1", "creator-1", request)
            assert all(step.get("flow_profile_id") is None for step in run.steps)
            assert service.create_run(db, "project-1", "workspace-1", "creator-1", request).id == run.id
    finally:
        engine.dispose()
