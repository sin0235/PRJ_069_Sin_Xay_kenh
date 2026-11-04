import json
import importlib
import sys
import types
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.entities import AIGenerationJob, ContentVideoWorkerLease, CostLedger, MediaAsset, Workspace
from src.modules.flow_sessions import service as flow_profile_service
from src.modules.media_queue.service import enqueue_media_job, process_next_media_job as service_process_next_media_job
from src.schemas.contracts import AIGenerationJobCreate, AIGenerationJobOut


def test_worker_auto_edit_khong_bi_khoa_ai_video_nhung_flow_van_tuan_tu(media_db, monkeypatch):
    from src.modules.media_queue import worker
    from src.models.entities import ProductionProject
    db, ws, _ = media_db
    db.add_all([ProductionProject(id='edit', workspace_id=ws, title='Edit', workflow_type='AUTO_EDIT', created_by='u'),
                ProductionProject(id='ai', workspace_id=ws, title='AI', workflow_type='AI_VIDEO', created_by='u')])
    for ident, project, backend in [('ai-job','ai','BAHA_AUTO_EDIT'), ('flow','edit','GOOGLE_FLOW'), ('diagram','edit','BAHA_AUTO_EDIT')]:
        db.add(AIGenerationJob(id=ident, project_id=project, workspace_id=ws, asset_type='VIDEO',
            provider='MEDIA_VIDEO', provider_mode='INTERNAL_RENDERER', model_id='test', idempotency_key=ident,
            created_by='u', request_payload_json=json.dumps({'backend_provider':backend})))
    db.add(ContentVideoWorkerLease(name='content-video-flow', token='busy-ai', expires_at=datetime.now(timezone.utc)+timedelta(minutes=5)))
    db.commit()
    monkeypatch.setattr(worker, 'AUTO_EDIT_ONLY', True, raising=False)
    monkeypatch.setattr(worker, 'LEASE_NAME', 'auto-edit-media')
    assert worker.acquire_media_lease(db, 'edit-token')
    assert worker._claim_next_job(db, 'edit-token').id == 'diagram'
    assert worker._claim_next_job(db, 'edit-token') is None
    assert db.get(AIGenerationJob,'ai-job').state == 'QUEUED'
    db.get(ContentVideoWorkerLease,'content-video-flow').expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    db.commit()
    assert worker._claim_next_job(db, 'edit-token').id == 'flow'
    assert db.get(ContentVideoWorkerLease,'content-video-flow').token == 'edit-token'


@pytest.fixture
def media_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    workspace_id = f"ws-queue-{uuid.uuid4().hex[:8]}"
    db.add(Workspace(id=workspace_id, name="Media queue test", slug=workspace_id))
    db.commit()
    profile = flow_profile_service.create_profile(db, workspace_id, "Queue test profile", "user-queue")
    db.info["flow_profile_id"] = profile.id
    try:
        yield db, workspace_id, session_factory
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _media_router_module(monkeypatch):
    flow_session = types.ModuleType("session_manager")

    class FlowLoginRequired(Exception):
        pass

    class FlowSubmissionNotSent(Exception):
        pass

    class FlowQuotaExceeded(Exception):
        error_code = "FLOW_QUOTA_LIMITED"

        def __init__(self, submitted=False):
            super().__init__("Quota is limited")
            self.submitted = submitted

    flow_session.FlowLoginRequired = FlowLoginRequired
    flow_session.FlowSubmissionNotSent = FlowSubmissionNotSent
    flow_session.FlowQuotaExceeded = FlowQuotaExceeded
    flow_session.LOCAL_BROWSER_PROFILE_DIR = "/tmp/flow-profile"
    monkeypatch.setitem(sys.modules, "session_manager", flow_session)
    return importlib.import_module("src.modules.media_studio.router")


@pytest.mark.parametrize("use_profile_context", [False, True])
def test_production_music_request_is_queued_without_running_provider(media_db, monkeypatch, use_profile_context):
    db, workspace_id, _ = media_db
    monkeypatch.setenv("APP_ENV", "production")
    provider_calls = []

    def generate_sync(**kwargs):
        provider_calls.append(kwargs)
        asset = MediaAsset(
            id=f"asset-{uuid.uuid4().hex[:12]}",
            workspace_id=workspace_id,
            storage_key=f"workspaces/{workspace_id}/media/music.mp3",
            sha256="a" * 64,
            byte_size=128,
            mime_detected="audio/mpeg",
            source_product="FLOW_MUSIC",
            original_filename="music.mp3",
            created_by="user-queue",
            duration_ms=30_000,
            approval_state="UNREVIEWED",
        )
        db.add(asset)
        db.commit()
        return asset

    media_router = _media_router_module(monkeypatch)
    monkeypatch.setattr(media_router.music_orchestrator, "generate_music_track", generate_sync)
    from src.modules.flow_sessions.context import profile_context

    profile_id = db.info["flow_profile_id"]
    context = profile_context(workspace_id, profile_id) if use_profile_context else nullcontext()
    with context:
        response = media_router.generate_music_track(
            prompt="A quiet piano loop",
            genre="Classical",
            mood="Calm",
            lyrics=None,
            use_official_lyria=False,
            provider="FLOW_BROWSER_PILOT",
            mode="PILOT_ASSISTED",
            duration_sec=30,
            project_id=None,
            idempotency_key="music-request-01",
            normalize_tiktok=True,
            db=db,
            tenant=SimpleNamespace(workspace_id=workspace_id, user_id="user-queue"),
        )

    assert provider_calls == []
    assert response.status_code == 202
    body = json.loads(response.body)
    assert body["job_id"]
    job = db.query(AIGenerationJob).filter(AIGenerationJob.id == body["job_id"]).one()
    assert job.state == "QUEUED"
    assert job.provider == "MEDIA_MUSIC"
    assert json.loads(job.request_payload_json)["profile_id"] == profile_id


def test_production_generic_flow_job_uses_media_envelope_without_sync_execution(media_db, monkeypatch):
    db, workspace_id, _ = media_db
    _media_router_module(monkeypatch)
    job_engine = importlib.import_module("src.modules.media_studio.job_engine").job_engine
    monkeypatch.setenv("APP_ENV", "production")
    sync_calls = []
    monkeypatch.setattr(job_engine, "_process_flow_job", lambda *args: sync_calls.append(args))
    payload = AIGenerationJobCreate(
        asset_type="MUSIC",
        provider="FLOW_MUSIC_ASSISTED",
        provider_mode="SUBSCRIPTION_ASSISTED",
        model_id="flow-music-web",
        idempotency_key="generic-flow-request-01",
        prompt_text="A slow instrumental",
        parameters={"genre": "Jazz"},
    )

    job = job_engine.submit_job(db, workspace_id, "user-queue", payload)

    request = json.loads(job.request_payload_json)
    assert sync_calls == []
    assert job.state == "QUEUED"
    assert job.provider == "MEDIA_MUSIC"
    assert request["backend_provider"] == "FLOW_MUSIC_ASSISTED"
    assert request["prompt_text"] == "A slow instrumental"
    assert request["profile_id"] == db.info["flow_profile_id"]
    duplicate = job_engine.submit_job(db, workspace_id, "user-queue", payload)
    assert duplicate.id == job.id


def test_media_job_accepts_multiple_auto_edit_outputs(media_db):
    from src.modules.media_queue import worker

    db, workspace_id, _ = media_db
    job = enqueue_media_job(
        db,
        workspace_id=workspace_id,
        user_id="user-queue",
        provider="MEDIA_VIDEO",
        operation="auto_edit_video",
        backend_provider="BAHA_AUTO_EDIT",
        provider_mode="LOCAL_CPU_AND_CONFIGURED_LLM",
        model_id="model-kiem-thu",
        prompt_text="Dựng video nguồn thành clip ngắn.",
        parameters={"source_asset_id": "source-01"},
        idempotency_key="auto-edit-output-list-01",
        project_id="project-01",
    )
    token = "auto-edit-worker-token"
    job.state = "RUNNING"
    job.lease_token = token
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    db.add(ContentVideoWorkerLease(name=worker.LEASE_NAME, token=token, expires_at=job.lease_expires_at))
    db.commit()
    outputs = [SimpleNamespace(id="clip-01"), SimpleNamespace(id="clip-02"), SimpleNamespace(id="manifest-01")]

    assert worker._finish_job(db, job, token, state="SUCCEEDED", asset=outputs)

    db.refresh(job)
    assert json.loads(job.output_asset_ids_json) == ["clip-01", "clip-02", "manifest-01"]


def test_production_video_form_queues_active_profile_without_running_provider(media_db, monkeypatch):
    db, workspace_id, _ = media_db
    media_router = _media_router_module(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(media_router.video_orchestrator, "generate_video_scene", lambda **_kwargs: pytest.fail("API must only enqueue"))

    response = media_router.generate_video_scene(
        prompt="A landscape shot", aspect_ratio="9:16", use_official_omni=False,
        project_id=None, start_image_asset_id=None, remove_watermark=False,
        idempotency_key="video-active-profile", db=db,
        tenant=SimpleNamespace(workspace_id=workspace_id, user_id="user-queue"),
    )

    assert response.status_code == 202
    job = db.get(AIGenerationJob, json.loads(response.body)["job_id"])
    assert json.loads(job.request_payload_json)["profile_id"] == db.info["flow_profile_id"]


@pytest.mark.parametrize("backend_provider,provider,operation", [
    ("FLOW_BROWSER_PILOT", "MEDIA_MUSIC", "generate_music_track"),
    ("GOOGLE_FLOW", "MEDIA_VIDEO", "generate_video_scene"),
])
def test_production_enqueue_persists_active_workspace_flow_profile(
    media_db, monkeypatch, backend_provider, provider, operation,
):
    db, workspace_id, _ = media_db
    monkeypatch.setenv("APP_ENV", "production")
    job = enqueue_media_job(
        db, workspace_id=workspace_id, user_id="user-queue", provider=provider,
        operation=operation, backend_provider=backend_provider, provider_mode="FLOW_BROWSER_PILOT",
        model_id="flow-web", prompt_text="Use the profile managed in the web UI", parameters={},
        idempotency_key=f"active-profile-{provider}",
    )

    assert json.loads(job.request_payload_json)["profile_id"] == db.info["flow_profile_id"]


def test_production_flow_enqueue_rejects_foreign_profile(media_db, monkeypatch):
    db, workspace_id, _ = media_db
    monkeypatch.setenv("APP_ENV", "production")
    other_workspace = f"ws-foreign-{uuid.uuid4().hex[:8]}"
    db.add(Workspace(id=other_workspace, name="Foreign workspace", slug=other_workspace))
    db.commit()
    foreign_profile = flow_profile_service.create_profile(db, other_workspace, "Foreign", "other-user")

    with pytest.raises(HTTPException) as error:
        enqueue_media_job(
            db, workspace_id=workspace_id, user_id="user-queue", provider="MEDIA_MUSIC",
            operation="generate_music_track", backend_provider="FLOW_BROWSER_PILOT", provider_mode="PILOT_ASSISTED",
            model_id="flow-web", prompt_text="Must not cross workspace", parameters={},
            idempotency_key="foreign-profile-request", profile_id=foreign_profile.id,
        )

    assert error.value.status_code == 404
    assert error.value.detail["error_code"] == "FLOW_PROFILE_NOT_FOUND"
    assert db.query(AIGenerationJob).count() == 0


def test_production_flow_enqueue_requires_active_profile(media_db, monkeypatch):
    db, workspace_id, _ = media_db
    monkeypatch.setenv("APP_ENV", "production")
    flow_profile_service.resolve_profile(db, workspace_id).is_active = False
    db.commit()

    with pytest.raises(HTTPException) as error:
        enqueue_media_job(
            db, workspace_id=workspace_id, user_id="user-queue", provider="MEDIA_MUSIC",
            operation="generate_music_track", backend_provider="FLOW_BROWSER_PILOT", provider_mode="PILOT_ASSISTED",
            model_id="flow-web", prompt_text="No implicit bridge default", parameters={},
            idempotency_key="missing-active-profile",
        )

    assert error.value.detail["error_code"] == "FLOW_ACTIVE_PROFILE_REQUIRED"
    assert db.query(AIGenerationJob).count() == 0


def test_missing_flow_profile_leaves_no_ledger_and_can_retry_after_setup(media_db, monkeypatch):
    db, workspace_id, _ = media_db
    _media_router_module(monkeypatch)
    job_engine = importlib.import_module("src.modules.media_studio.job_engine").job_engine
    monkeypatch.setenv("APP_ENV", "production")
    flow_profile_service.resolve_profile(db, workspace_id).is_active = False
    db.commit()
    payload = AIGenerationJobCreate(
        asset_type="MUSIC", provider="FLOW_MUSIC_ASSISTED", provider_mode="SUBSCRIPTION_ASSISTED",
        model_id="flow-music-web", idempotency_key="same-key-after-profile-setup",
        prompt_text="Continue after workspace profile setup", parameters={},
    )

    with pytest.raises(HTTPException) as error:
        job_engine.submit_job(db, workspace_id, "user-queue", payload)
    assert error.value.detail["error_code"] == "FLOW_ACTIVE_PROFILE_REQUIRED"
    assert db.query(CostLedger).count() == 0

    flow_profile_service.activate_profile(db, workspace_id, db.info["flow_profile_id"])
    job = job_engine.submit_job(db, workspace_id, "user-queue", payload)

    assert job.state == "QUEUED"
    assert json.loads(job.request_payload_json)["profile_id"] == db.info["flow_profile_id"]
    assert db.query(CostLedger).count() == 1


@pytest.mark.parametrize("backend_provider", ["GOOGLE_OFFICIAL", "GOOGLE_OMNI_FLASH"])
def test_production_official_enqueue_needs_no_flow_profile(media_db, monkeypatch, backend_provider):
    db, workspace_id, _ = media_db
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(flow_profile_service, "resolve_profile", lambda *_args: pytest.fail("official provider must not require Flow"))
    job = enqueue_media_job(
        db, workspace_id=workspace_id, user_id="user-queue", provider="MEDIA_MUSIC",
        operation="generate_music_track", backend_provider=backend_provider, provider_mode="OFFICIAL_API",
        model_id="official", prompt_text="Official credentials only", parameters={},
        idempotency_key=f"official-{backend_provider}",
    )

    assert json.loads(job.request_payload_json)["profile_id"] is None


def test_idempotent_flow_enqueue_keeps_saved_profile_after_active_profile_switch(media_db, monkeypatch):
    db, workspace_id, _ = media_db
    monkeypatch.setenv("APP_ENV", "production")
    request = dict(
        workspace_id=workspace_id, user_id="user-queue", provider="MEDIA_VIDEO",
        operation="generate_video_scene", backend_provider="GOOGLE_FLOW", provider_mode="FLOW_BROWSER_PILOT",
        model_id="flow-web", prompt_text="Keep this provider attempt", parameters={},
        idempotency_key="pin-original-profile",
    )
    original = enqueue_media_job(db, **request)
    new_profile = flow_profile_service.create_profile(db, workspace_id, "New active profile", "user-queue")
    flow_profile_service.activate_profile(db, workspace_id, new_profile.id)

    repeated = enqueue_media_job(db, **request)

    assert repeated.id == original.id
    assert json.loads(repeated.request_payload_json)["profile_id"] == db.info["flow_profile_id"]
    assert db.query(AIGenerationJob).count() == 1


@pytest.mark.parametrize("provider", ["FAKE_PROVIDER", "LOCAL_TEST_SYNTH", "LOCAL_TEST"])
def test_production_generic_job_rejects_test_providers(media_db, monkeypatch, provider):
    db, workspace_id, _ = media_db
    _media_router_module(monkeypatch)
    job_engine = importlib.import_module("src.modules.media_studio.job_engine").job_engine
    monkeypatch.setenv("APP_ENV", "production")
    payload = AIGenerationJobCreate.model_construct(
        asset_type="MUSIC",
        provider=provider,
        provider_mode="TEST_MOCK",
        model_id="fake",
        idempotency_key="fake-request-01",
        prompt_text="Must not run",
    )

    with pytest.raises(HTTPException) as error:
        job_engine.submit_job(db, workspace_id, "user-queue", payload)

    assert error.value.status_code == 403
    assert db.query(AIGenerationJob).count() == 0


def test_job_status_serializes_asset_ids_for_async_polling(media_db, monkeypatch):
    db, workspace_id, _session_factory = media_db
    media_router = _media_router_module(monkeypatch)
    job = _queued_music(db, workspace_id, "status-response")
    job.state = "SUCCEEDED"
    job.output_asset_ids_json = json.dumps(["asset-ready"])
    db.commit()

    payload = media_router.get_ai_job(
        job.id,
        db=db,
        tenant=SimpleNamespace(workspace_id=workspace_id),
    )
    response = AIGenerationJobOut.model_validate(payload)

    assert response.state == "SUCCEEDED"
    assert response.output_asset_ids == ["asset-ready"]


def test_generic_job_acceptance_keeps_legacy_and_async_response_fields(media_db, monkeypatch):
    db, workspace_id, _session_factory = media_db
    media_router = _media_router_module(monkeypatch)
    job = SimpleNamespace(
        id="job-contract",
        workspace_id=workspace_id,
        project_id=None,
        asset_type="MUSIC",
        provider="MEDIA_MUSIC",
        provider_mode="PILOT_ASSISTED",
        model_id="flow-music-web",
        cost_currency="USD",
        retry_count=0,
        created_by="user-queue",
        created_at=datetime.now(timezone.utc),
        finished_at=None,
        state="QUEUED",
        estimated_cost=0.12,
        actual_cost=0.0,
        credits_source="API_BILLING",
        error_code=None,
        error_message=None,
        idempotency_key="contract-key",
        output_asset_ids_json="[]",
    )
    monkeypatch.setattr(media_router.job_engine, "submit_job", lambda **_kwargs: job)
    monkeypatch.setattr(media_router, "is_production", lambda: True)

    response = media_router.submit_ai_job(
        payload=SimpleNamespace(),
        budget_cap=None,
        db=db,
        tenant=SimpleNamespace(workspace_id=workspace_id, user_id="user-queue"),
    )

    body = json.loads(response.body)
    assert response.status_code == 202
    assert body["id"] == body["job_id"] == "job-contract"
    assert body["state"] == "QUEUED"
    assert body["actual_cost"] == 0.0
    assert body["credits_source"] == "API_BILLING"
    assert body["created_by"] == "user-queue"
    assert body["created_at"]


def test_production_flow_login_route_returns_web_manager_without_launching_process(monkeypatch):
    media_router = _media_router_module(monkeypatch)
    monkeypatch.setattr(media_router, "is_production", lambda: True)
    monkeypatch.setattr(media_router.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("production must not launch a server browser"))
    workspace_id = "ws-owner-flow"
    user_id = "user-owner-flow"
    owner_role = {
        "role_code": "WORKSPACE_OWNER",
        "scope_type": "WORKSPACE",
        "scope_id": workspace_id,
        "assignment_status": "ACTIVE",
        "role_status": "ACTIVE",
        "is_active": True,
    }
    actor = SimpleNamespace(
        user_id=user_id,
        workspace_id=workspace_id,
        membership_status="ACTIVE",
        user_status="ACTIVE",
        workspace_status="ACTIVE",
        roles=[owner_role],
    )
    tenant = SimpleNamespace(
        user_id=user_id,
        workspace_id=workspace_id,
        actor=actor,
        auth_db=object(),
        dev_auth_bypass=False,
    )

    assert media_router.open_google_flow_login(tenant) == {
        "success": True,
        "url": "/flow-sessions",
    }


def test_authorized_worker_tenant_reloads_actor_and_checks_requested_action(monkeypatch):
    service = importlib.import_module("src.modules.media_queue.service")
    assert callable(getattr(service, "authorized_worker_tenant", None))
    auth_db = SimpleNamespace(rollback=lambda: None)
    actor = SimpleNamespace(user_id="user-current", workspace_id="ws-current")
    calls = []

    def auth_db_generator():
        yield auth_db

    auth = {
        "get_auth_db": auth_db_generator,
        "set_tenant_context": lambda *args: calls.append(("set", args)),
        "clear_tenant_context": lambda *args: calls.append(("clear", args)),
        "load_actor_for_user": lambda db, **kwargs: calls.append(("load", db, kwargs)) or actor,
    }
    monkeypatch.setattr(service, "_canonical_auth_modules", lambda: auth)
    monkeypatch.setattr(service, "authorize_action", lambda tenant, action: calls.append(("authorize", tenant, action)))

    with service.authorized_worker_tenant("ws-current", "user-current", "media.upload") as tenant:
        assert tenant.workspace_id == "ws-current"
        assert tenant.user_id == "user-current"

    assert any(item[0] == "load" and item[2] == {"workspace_id": "ws-current", "user_id": "user-current"} for item in calls)
    assert any(item[0] == "authorize" and item[2] == "media.upload" for item in calls)
    assert sum(item[0] == "clear" for item in calls) == 2


def test_authorized_worker_tenant_denies_revoked_membership_and_cleans_context(monkeypatch):
    service = importlib.import_module("src.modules.media_queue.service")
    assert callable(getattr(service, "authorized_worker_tenant", None))
    auth_db = SimpleNamespace(rollback=lambda: None)
    calls = []

    def auth_db_generator():
        yield auth_db

    auth = {
        "get_auth_db": auth_db_generator,
        "set_tenant_context": lambda *args: None,
        "clear_tenant_context": lambda *args: calls.append("clear"),
        "load_actor_for_user": lambda *args, **kwargs: None,
    }
    monkeypatch.setattr(service, "_canonical_auth_modules", lambda: auth)

    with pytest.raises(HTTPException) as error:
        with service.authorized_worker_tenant("ws-current", "revoked-user"):
            pytest.fail("a revoked actor must not enter provider execution")

    assert error.value.status_code == 403
    assert calls == ["clear", "clear"]


def _worker_module():
    queue = importlib.import_module("src.modules.media_queue")
    assert callable(getattr(queue, "process_next_media_job", None))
    return importlib.import_module("src.modules.media_queue.worker")


def test_parent_runtime_service_entrypoint_delegates_to_media_worker(monkeypatch):
    worker = _worker_module()
    calls = []
    monkeypatch.setattr(worker, "process_next_media_job", lambda db, token: calls.append((db, token)) or True)
    db = object()

    assert service_process_next_media_job(db, "shared-lease-token") is True
    assert calls == [(db, "shared-lease-token")]


def _queued_music(db, workspace_id, key="worker-request"):
    return enqueue_media_job(
        db,
        workspace_id=workspace_id,
        user_id="user-queue",
        provider="MEDIA_MUSIC",
        operation="generate_music_track",
        backend_provider="FLOW_BROWSER_PILOT",
        provider_mode="PILOT_ASSISTED",
        model_id="flow-music-web",
        prompt_text="Worker prompt",
        parameters={"prompt": "Worker prompt", "genre": "Jazz"},
        idempotency_key=key,
        profile_id=db.info["flow_profile_id"],
        estimated_cost=0.05,
    )


def _queued_generic_flow(db, workspace_id, key="generic-flow-resume"):
    return enqueue_media_job(
        db,
        workspace_id=workspace_id,
        user_id="user-queue",
        provider="MEDIA_MUSIC",
        operation="generate_flow_job",
        backend_provider="FLOW_MUSIC_ASSISTED",
        provider_mode="SUBSCRIPTION_ASSISTED",
        model_id="flow-music-web",
        prompt_text="Continue the same provider request",
        parameters={"prompt_text": "Continue the same provider request", "genre": "Jazz"},
        idempotency_key=key,
        profile_id=db.info["flow_profile_id"],
        estimated_cost=0.0,
    )


def test_flow_errors_are_retryable_only_when_submission_is_known_not_sent():
    worker = _worker_module()

    class FlowQuotaExceeded(Exception):
        def __init__(self, submitted):
            super().__init__("Flow quota is limited")
            self.error_code = "FLOW_QUOTA_LIMITED"
            self.submitted = submitted

    class FlowLoginRequired(Exception):
        pass

    class FlowSubmissionNotSent(Exception):
        pass

    before_submit = worker._error_state(FlowQuotaExceeded(submitted=False))
    after_submit = worker._error_state(FlowQuotaExceeded(submitted=True))
    login_required = worker._error_state(FlowLoginRequired("Sign in to Flow"))
    quota_submission_not_sent = worker._error_state(FlowSubmissionNotSent("FLOW_QUOTA_LIMITED"))

    assert before_submit == ("BLOCKED_FLOW_QUOTA", "FLOW_QUOTA_LIMITED", "Flow quota is limited")
    assert after_submit[0:2] == ("NEEDS_RECONCILIATION", "FLOW_QUOTA_LIMITED")
    assert login_required[0:2] == ("BLOCKED_FLOW_LOGIN", "FLOW_LOGIN_REQUIRED")
    assert quota_submission_not_sent[0:2] == ("BLOCKED_FLOW_QUOTA", "FLOW_QUOTA_LIMITED")


@pytest.mark.parametrize("blocked_state,error_code", [
    ("BLOCKED_FLOW_LOGIN", "FLOW_LOGIN_REQUIRED"),
    ("BLOCKED_FLOW_QUOTA", "FLOW_QUOTA_LIMITED"),
    ("FAILED", "FLOW_SUBMISSION_NOT_SENT"),
])
@pytest.mark.parametrize("operation", ["generate_flow_job", "generate_music_track", "generate_video_scene"])
def test_resume_blocked_generic_job_requeues_same_job_and_idempotency(media_db, monkeypatch, blocked_state, error_code, operation):
    db, workspace_id, _session_factory = media_db
    media_router = _media_router_module(monkeypatch)
    job = _queued_generic_flow(db, workspace_id)
    envelope = json.loads(job.request_payload_json)
    envelope["operation"] = operation
    if operation == "generate_music_track":
        envelope["backend_provider"] = "FLOW_BROWSER_PILOT"
    elif operation == "generate_video_scene":
        envelope["backend_provider"] = "GOOGLE_FLOW"
        envelope["provider"] = job.provider = "MEDIA_VIDEO"
        job.asset_type = "VIDEO"
    job.request_payload_json = json.dumps(envelope)
    replacement_profile = flow_profile_service.create_profile(db, workspace_id, "After login", "user-queue")
    original_id, original_key = job.id, job.idempotency_key
    job.state = blocked_state
    job.error_code = error_code
    job.error_message = "Quota is limited"
    job.finished_at = datetime.now(timezone.utc)
    db.commit()

    response = media_router.resume_ai_job(
        job_id=job.id,
        profile_id=replacement_profile.id,
        db=db,
        tenant=SimpleNamespace(workspace_id=workspace_id, user_id="user-queue"),
    )

    db.refresh(job)
    body = json.loads(response.body)
    request = json.loads(job.request_payload_json)
    assert response.status_code == 202
    assert body["id"] == body["job_id"] == original_id
    assert body["state"] == "QUEUED"
    assert job.idempotency_key == original_key
    assert job.error_code is None
    assert job.finished_at is None
    assert request["profile_id"] == replacement_profile.id


@pytest.mark.parametrize('state,code', [('NEEDS_RECONCILIATION','NEEDS_RECONCILIATION'), ('FAILED','INVALID_JOB_PAYLOAD'), ('NEEDS_RECONCILIATION','FLOW_SUBMISSION_NOT_SENT')])
def test_resume_rejects_provider_submission_uncertainty(media_db, monkeypatch,state,code):
    db, workspace_id, _session_factory = media_db
    media_router = _media_router_module(monkeypatch)
    job = _queued_generic_flow(db, workspace_id, "uncertain-generic-flow")
    job.state = state
    job.error_code = code
    db.commit()

    with pytest.raises(HTTPException) as error:
        media_router.resume_ai_job(
            job_id=job.id,
            profile_id=None,
            db=db,
            tenant=SimpleNamespace(workspace_id=workspace_id, user_id="user-queue"),
        )

    db.refresh(job)
    assert error.value.status_code == 409
    assert job.state == state


def test_worker_records_only_typed_pre_submit_provider_errors(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    flow_service = importlib.import_module("src.modules.flow_sessions.service")
    token = str(uuid.uuid4())
    job = _queued_music(db, workspace_id, "typed-pre-submit-quota")
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())
    records = []
    monkeypatch.setattr(flow_service, "record_provider_error", lambda *args: records.append(args))

    class FlowQuotaExceeded(Exception):
        error_code = "FLOW_QUOTA_LIMITED"
        submitted = False

    def raise_quota(*_args):
        raise FlowQuotaExceeded("Quota is limited")

    monkeypatch.setattr(worker, "_execute_job", raise_quota)
    assert worker.process_next_media_job(db, token) is True
    db.refresh(job)

    assert job.state == "BLOCKED_FLOW_QUOTA"
    assert job.error_code == "FLOW_QUOTA_LIMITED"
    assert len(records) == 1
    assert records[0][1:] == (workspace_id, db.info["flow_profile_id"], "FLOW_QUOTA_LIMITED")


def test_worker_records_typed_post_submit_quota_but_keeps_job_uncertain(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    flow_service = importlib.import_module("src.modules.flow_sessions.service")
    token = str(uuid.uuid4())
    job = _queued_music(db, workspace_id, "typed-post-submit-quota")
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())
    records = []
    monkeypatch.setattr(flow_service, "record_provider_error", lambda *args: records.append(args))

    class FlowQuotaExceeded(Exception):
        error_code = "FLOW_QUOTA_LIMITED"
        submitted = True

    def raise_quota(*_args):
        raise FlowQuotaExceeded("Quota response arrived after submit")

    monkeypatch.setattr(worker, "_execute_job", raise_quota)
    assert worker.process_next_media_job(db, token) is True
    db.refresh(job)

    assert job.state == "NEEDS_RECONCILIATION"
    assert job.error_code == "FLOW_QUOTA_LIMITED"
    assert len(records) == 1
    assert records[0][1:] == (workspace_id, db.info["flow_profile_id"], "FLOW_QUOTA_LIMITED")


def test_worker_does_not_update_profile_for_unknown_post_submit_failure(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    flow_service = importlib.import_module("src.modules.flow_sessions.service")
    token = str(uuid.uuid4())
    job = _queued_music(db, workspace_id, "unknown-post-submit-error")
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())
    records = []
    monkeypatch.setattr(flow_service, "record_provider_error", lambda *args: records.append(args))
    monkeypatch.setattr(worker, "_execute_job", lambda *_args: (_ for _ in ()).throw(RuntimeError("Provider outcome unknown")))

    assert worker.process_next_media_job(db, token) is True
    db.refresh(job)

    assert job.state == "NEEDS_RECONCILIATION"
    assert records == []


def _hold_shared_lease(db, token):
    db.add(ContentVideoWorkerLease(
        name="content-video-flow",
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=8),
    ))
    db.commit()


def _asset(workspace_id):
    return MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}",
        workspace_id=workspace_id,
        storage_key=f"workspaces/{workspace_id}/media/worker.mp3",
        sha256="b" * 64,
        byte_size=64,
        mime_detected="audio/mpeg",
        source_product="FLOW_MUSIC",
        original_filename="worker.mp3",
        created_by="user-queue",
        duration_ms=30_000,
        approval_state="UNREVIEWED",
    )


def test_worker_claims_only_media_jobs_and_fences_success_by_token(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    token = str(uuid.uuid4())
    queued = _queued_music(db, workspace_id)
    other = AIGenerationJob(
        id="voice-job", workspace_id=workspace_id, asset_type="AUDIO", provider="VOICE_STUDIO",
        provider_mode="VIE_NEU_V3_TURBO", model_id="voice-model", idempotency_key="voice-job-key",
        state="QUEUED", request_payload_json="{}", created_by="user-queue",
    )
    db.add(other)
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())

    def execute(db, job, request):
        from src.modules.flow_sessions.context import current_flow_profile

        assert current_flow_profile().profile_id == db.info["flow_profile_id"]
        asset = _asset(workspace_id)
        db.add(asset)
        db.flush()
        return asset

    monkeypatch.setattr(worker, "_execute_job", execute)

    assert worker.process_next_media_job(db, token) is True

    db.refresh(queued)
    db.refresh(other)
    assert queued.state == "SUCCEEDED"
    assert json.loads(queued.output_asset_ids_json)
    assert queued.actual_cost == 0.0
    assert queued.lease_token is None
    assert other.state == "QUEUED"
    shared_lease = db.get(ContentVideoWorkerLease, worker.LEASE_NAME)
    assert shared_lease.token is None
    assert shared_lease.expires_at is None


@pytest.mark.parametrize("profile_kind,expected_code", [
    ("missing", "FLOW_ACTIVE_PROFILE_REQUIRED"),
    ("foreign", "FLOW_PROFILE_NOT_FOUND"),
])
def test_production_worker_rechecks_profile_before_provider_execution(media_db, monkeypatch, profile_kind, expected_code):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    job = _queued_music(db, workspace_id, f"worker-profile-{profile_kind}")
    request = json.loads(job.request_payload_json)
    if profile_kind == "foreign":
        other_workspace = f"ws-worker-foreign-{uuid.uuid4().hex[:8]}"
        db.add(Workspace(id=other_workspace, name="Foreign worker workspace", slug=other_workspace))
        db.commit()
        profile = flow_profile_service.create_profile(db, other_workspace, "Foreign profile", "other-user")
        request["profile_id"] = profile.id
    else:
        request["profile_id"] = None
    job.request_payload_json = json.dumps(request)
    token = str(uuid.uuid4())
    _hold_shared_lease(db, token)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(worker, "_execute_job", lambda *_args: pytest.fail("provider must not use an unscoped profile"))

    assert worker.process_next_media_job(db, token) is True
    db.refresh(job)

    assert job.state == "FAILED"
    assert job.error_code == expected_code
    assert job.lease_token is None
    assert db.get(ContentVideoWorkerLease, worker.LEASE_NAME).token is None


def test_production_worker_enters_persisted_profile_even_after_active_profile_switch(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    monkeypatch.setenv("APP_ENV", "production")
    job = _queued_music(db, workspace_id, "worker-pinned-profile")
    original_profile_id = db.info["flow_profile_id"]
    replacement = flow_profile_service.create_profile(db, workspace_id, "Other active profile", "user-queue")
    flow_profile_service.activate_profile(db, workspace_id, replacement.id)
    token = str(uuid.uuid4())
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())

    def execute(db, claimed, request):
        from src.modules.flow_sessions.context import current_flow_profile

        assert current_flow_profile().workspace_id == workspace_id
        assert current_flow_profile().profile_id == original_profile_id
        asset = _asset(workspace_id)
        db.add(asset)
        db.flush()
        return asset

    monkeypatch.setattr(worker, "_execute_job", execute)

    assert worker.process_next_media_job(db, token) is True
    db.refresh(job)
    assert job.state == "SUCCEEDED"


def test_worker_releases_shared_lease_when_queue_is_empty(media_db):
    db, _workspace_id, _session_factory = media_db
    worker = _worker_module()
    token = str(uuid.uuid4())
    _hold_shared_lease(db, token)

    assert worker.process_next_media_job(db, token) is False

    shared_lease = db.get(ContentVideoWorkerLease, worker.LEASE_NAME)
    assert shared_lease.token is None
    assert shared_lease.expires_at is None


def test_worker_does_not_overwrite_job_after_lease_token_changes(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    token = str(uuid.uuid4())
    job = _queued_music(db, workspace_id, "fenced-request")
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())

    monkeypatch.setattr(worker, "_execute_job", lambda *args: _asset(workspace_id))
    finish_job = worker._finish_job

    def lose_lease_before_finish(db, claimed, owner_token, **kwargs):
        with session_factory() as other_db:
            other_job = other_db.get(AIGenerationJob, claimed.id)
            other_job.lease_token = "new-owner"
            other_db.commit()
        return finish_job(db, claimed, owner_token, **kwargs)

    monkeypatch.setattr(worker, "_finish_job", lose_lease_before_finish)

    assert worker.process_next_media_job(db, token) is True

    db.refresh(job)
    assert job.state == "SUBMITTING"
    assert job.lease_token == "new-owner"
    assert job.output_asset_ids_json == "[]"


def test_expired_provider_jobs_need_reconciliation_and_are_not_resubmitted(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    token = str(uuid.uuid4())
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    for state in ("RUNNING", "SUBMITTING"):
        db.add(AIGenerationJob(
            id=f"expired-{state}", workspace_id=workspace_id, asset_type="MUSIC", provider="MEDIA_MUSIC",
            provider_mode="PILOT_ASSISTED", model_id="flow-music-web", idempotency_key=f"expired-{state}-key",
            state=state, request_payload_json="{}", created_by="user-queue", lease_token="old-owner",
            lease_expires_at=expired_at,
        ))
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "_execute_job", lambda *args: pytest.fail("expired media jobs must not be resent"))

    assert worker.process_next_media_job(db, token) is True

    for state in ("RUNNING", "SUBMITTING"):
        recovered = db.get(AIGenerationJob, f"expired-{state}")
        assert recovered.state == "NEEDS_RECONCILIATION"
        assert recovered.error_code == "NEEDS_RECONCILIATION"
        assert recovered.lease_token is None


def test_flow_login_provider_error_is_persisted_without_returning_http_401(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    token = str(uuid.uuid4())
    job = _queued_music(db, workspace_id, "flow-login-request")
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())

    class FlowLoginRequired(Exception):
        pass

    def require_flow_login(*args):
        raise FlowLoginRequired("Google Flow login is required.")

    monkeypatch.setattr(worker, "_execute_job", require_flow_login)

    assert worker.process_next_media_job(db, token) is True

    db.refresh(job)
    assert job.state == "BLOCKED_FLOW_LOGIN"
    assert job.error_code == "FLOW_LOGIN_REQUIRED"
    assert job.error_message == "Google Flow login is required."


def test_worker_permission_revocation_prevents_provider_execution(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    token = str(uuid.uuid4())
    job = _queued_music(db, workspace_id, "revoked-worker-request")
    _hold_shared_lease(db, token)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)

    class DeniedTenant:
        def __enter__(self):
            raise HTTPException(status_code=403, detail="Permission revoked")

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: DeniedTenant())
    monkeypatch.setattr(worker, "_execute_job", lambda *args: pytest.fail("revoked actor must not call provider"))

    assert worker.process_next_media_job(db, token) is True

    db.refresh(job)
    assert job.state == "FAILED"
    assert job.error_code == "WORKER_PERMISSION_REVOKED"
    assert job.error_message == "Permission revoked"


def test_media_lease_heartbeat_extends_job_and_shared_lease(media_db, monkeypatch):
    db, workspace_id, session_factory = media_db
    worker = _worker_module()
    token = str(uuid.uuid4())
    job = _queued_music(db, workspace_id, "heartbeat-request")
    job.state = "RUNNING"
    job.lease_token = token
    job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    _hold_shared_lease(db, token)
    db.commit()
    old_job_expiry = job.lease_expires_at
    old_shared_expiry = db.get(ContentVideoWorkerLease, "content-video-flow").expires_at
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    heartbeat = worker._MediaJobHeartbeat(token, job.id)

    assert heartbeat.refresh_once() is True

    db.expire_all()
    new_job_expiry = db.get(AIGenerationJob, job.id).lease_expires_at.replace(tzinfo=timezone.utc)
    new_shared_expiry = db.get(ContentVideoWorkerLease, "content-video-flow").expires_at.replace(tzinfo=timezone.utc)
    assert new_job_expiry > old_job_expiry.replace(tzinfo=timezone.utc)
    assert new_shared_expiry > old_shared_expiry.replace(tzinfo=timezone.utc)


def test_worker_dispatches_auto_edit_hyperframes_scene_to_existing_renderer(media_db, monkeypatch):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor
    from src.modules.media_queue import worker

    db, workspace_id, _ = media_db
    job = SimpleNamespace(workspace_id=workspace_id, created_by="user-queue", project_id="project-queue")
    request = {
        "operation": "render_auto_edit_diagram",
        "backend_provider": "BAHA_AUTO_EDIT",
        "parameters": {"target_clip_id": "part1_01"},
    }
    expected = object()
    calls = []

    def render(database, render_job, payload):
        calls.append((database, render_job, payload))
        return expected

    monkeypatch.setattr(editor, "render_auto_edit_diagram", render)

    result = worker._execute_job(db, job, request)

    assert result is expected
    assert calls == [(db, job, request)]


@pytest.mark.parametrize('lease_lost',[False,True])
def test_worker_luu_project_flow_truoc_gui_va_chan_worker_mat_lease(media_db,monkeypatch,lease_lost):
    from src.modules.media_queue import worker
    from src.modules.media_studio.video_provider import video_orchestrator
    db,workspace_id,_=media_db
    job=enqueue_media_job(db,workspace_id=workspace_id,user_id='user-queue',provider='MEDIA_VIDEO',
        operation='generate_video_scene',backend_provider='GOOGLE_FLOW',provider_mode='FLOW_BROWSER_PILOT',
        model_id='google-flow',prompt_text='Cảnh giấy',parameters={'include_audio':False},
        idempotency_key='flow-project-before-submit',project_id='project-01')
    job.state='SUBMITTING';job.lease_token='owned'
    job.lease_expires_at=datetime.now(timezone.utc)+timedelta(minutes=5)
    db.commit()
    db.refresh(job)
    request=json.loads(job.request_payload_json)
    expected=object()
    def generate(**kwargs):
        assert kwargs['include_audio'] is False
        assert kwargs['flow_project_url'] is None
        if lease_lost:
            db.query(AIGenerationJob).filter(AIGenerationJob.id==job.id).update({'lease_token':'other'})
            db.commit()
        kwargs['on_flow_project_created']('https://flow.google.com/project/doi-soat')
        db.expire_all()
        assert json.loads(db.get(AIGenerationJob,job.id).request_payload_json)['flow_project_url']=='https://flow.google.com/project/doi-soat'
        return expected
    monkeypatch.setattr(video_orchestrator,'generate_video_scene',generate)
    if lease_lost:
        with pytest.raises(RuntimeError,match='MEDIA_JOB_LEASE_LOST_BEFORE_FLOW_SUBMISSION'):
            worker._execute_job(db,job,request)
    else:
        assert worker._execute_job(db,job,request) is expected


@pytest.mark.parametrize('invalid', [None, 'workspace', 'project', 'hash', 'active', 'duration', 'old', 'path', 'database'])
def test_doi_soat_flow_da_tai_khong_tao_lai(media_db,monkeypatch,tmp_path,invalid):
    from src.modules.media_queue import service
    from src.modules.media_studio import security
    from src.modules.media_studio.video_processor import video_processor
    db,ws,_=media_db
    job=enqueue_media_job(db,workspace_id=ws,user_id='user-queue',provider='MEDIA_VIDEO',
        operation='generate_video_scene',backend_provider='GOOGLE_FLOW',provider_mode='FLOW_BROWSER_PILOT',
        model_id='google-flow',prompt_text='Cảnh giấy',parameters={'aspect_ratio':'9:16'},
        idempotency_key='reconcile-downloaded-flow',project_id='project-01')
    job.state='SUBMITTING' if invalid=='active' else 'NEEDS_RECONCILIATION'
    path=tmp_path/'canh.mp4';path.write_bytes(b'flow-recovered')
    digest,size=security.hash_file(path)
    asset=MediaAsset(id='raw-recovered',workspace_id='other' if invalid=='workspace' else ws,
        project_id='other' if invalid=='project' else job.project_id,
        storage_key='../canh.mp4' if invalid=='path' else path.name,sha256='bad' if invalid=='hash' else digest,
        byte_size=size,mime_detected='video/mp4',source_product='UPLOAD',created_by='user-queue',
        created_at=datetime.now(timezone.utc)-timedelta(days=1) if invalid=='old' else datetime.now(timezone.utc))
    db.add(asset);db.commit()
    monkeypatch.setattr(security,'MEDIA_ROOT_DIR',tmp_path)
    monkeypatch.setattr(video_processor,'probe_video',lambda p:{'width':1080,'height':1920,
        'duration_seconds':4 if invalid=='duration' else 10,'frame_rate':30})
    args=dict(job_id=job.id,asset_id=asset.id,workspace_id=ws,user_id='user-queue',
        project_url='https://flow.google.com/project/doi-soat',reason='Đã đối chiếu cảnh tải từ Flow và kiểm tra gỡ logo.')
    if invalid=='database':
        from sqlalchemy.sql.dml import Update
        execute=db.execute
        def fail_update(statement,*args,**kwargs):
            if isinstance(statement,Update):raise RuntimeError('DATABASE_UNAVAILABLE')
            return execute(statement,*args,**kwargs)
        monkeypatch.setattr(db,'execute',fail_update)
        with pytest.raises(RuntimeError,match='DATABASE_UNAVAILABLE'):service.reconcile_flow_job(db,**args)
        assert not list(tmp_path.glob('flow_phuc_hoi_*.mp4'))
        assert path.read_bytes()==b'flow-recovered'
        return
    if invalid:
        with pytest.raises(HTTPException):service.reconcile_flow_job(db,**args)
        db.refresh(job);assert job.state!='SUCCEEDED'
    else:
        service.reconcile_flow_job(db,**args)
        db.refresh(job);assert job.state=='SUCCEEDED'
        output=json.loads(job.output_asset_ids_json)
        assert len(output)==1
        recovered=db.get(MediaAsset,output[0]);assert recovered.source_product=='GOOGLE_FLOW'
        assert recovered.parent_asset_id==asset.id
        assert recovered.storage_key!=asset.storage_key
        assert security.hash_file(tmp_path/recovered.storage_key)==(digest,size)
        service.reconcile_flow_job(db,**args)
        assert json.loads(job.output_asset_ids_json)==output


@pytest.mark.parametrize('invalid',[None,'old','hash','source','workspace'])
def test_doc_bien_ban_dung_lai_kiem_nguon_va_du_lieu(media_db,monkeypatch,tmp_path,invalid):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor
    db,ws,_=media_db
    source=MediaAsset(id='source-original',workspace_id=ws,project_id='project-01',storage_key='source.mp4',
        sha256='a'*64,byte_size=1,mime_detected='video/mp4',source_product='UPLOAD',created_by='user-queue')
    data={'source_asset_id':source.id,'source_sha256':'wrong' if invalid=='source' else source.sha256,
        'words':[{'id':'w1','text':'nội dung','start_ms':0,'end_ms':3000}],
        'plan':{'clips':[{'clip_id':'c1','start_ms':0,'end_ms':3000,'title':'Đủ ý','reason':'Đủ ý'}]},
        'visual_briefs':[],'visual_generation':[],'removed_pause_intervals':[],
        'pause_candidates':[],'waveform_peaks':[]}
    if invalid=='old':data.pop('words')
    path=tmp_path/'bien_ban.json';path.write_text(json.dumps(data),encoding='utf-8')
    from src.modules.media_studio.security import hash_file
    digest,size=hash_file(path)
    manifest=MediaAsset(id='manifest',workspace_id='other' if invalid=='workspace' else ws,project_id=source.project_id,
        parent_asset_id=source.id,storage_key=path.name,sha256='bad' if invalid=='hash' else digest,byte_size=size,
        mime_detected='application/json',source_product='AUTO_EDIT',created_by='user-queue')
    db.add_all([source,manifest]);db.commit();monkeypatch.setattr(editor,'MEDIA_ROOT_DIR',tmp_path)
    if invalid:
        with pytest.raises(ValueError):editor.doc_bien_ban_dung_lai(db,manifest.id,source,ws,source.project_id)
    else:
        assert editor.doc_bien_ban_dung_lai(db,manifest.id,source,ws,source.project_id)==data


@pytest.mark.parametrize("child_count", [2, 4, 20, 21])
def test_auto_edit_waits_for_flow_children_then_resumes_once(media_db, child_count):
    from src.modules.media_queue import worker

    db, workspace_id, _ = media_db
    parent = enqueue_media_job(
        db, workspace_id=workspace_id, user_id="user-queue", provider="MEDIA_VIDEO",
        operation="auto_edit_video", backend_provider="BAHA_AUTO_EDIT",
        provider_mode="LOCAL_CPU_AND_CONFIGURED_LLM", model_id="model-kiem-thu",
        prompt_text="Dựng video và tạo diễn hoạ.", parameters={"phase": "waiting_for_flow"},
        idempotency_key="auto-edit-parent-wait-01", project_id="project-01",
    )
    first = enqueue_media_job(
        db, workspace_id=workspace_id, user_id="user-queue", provider="MEDIA_VIDEO",
        operation="generate_video_scene", backend_provider="GOOGLE_FLOW",
        provider_mode="FLOW_BROWSER_PILOT", model_id="google-flow",
        prompt_text="Cảnh origami thứ nhất.", parameters={},
        idempotency_key="auto-edit-child-one-01", project_id="project-01",
    )
    second = enqueue_media_job(
        db, workspace_id=workspace_id, user_id="user-queue", provider="MEDIA_VIDEO",
        operation="generate_video_scene", backend_provider="GOOGLE_FLOW",
        provider_mode="FLOW_BROWSER_PILOT", model_id="google-flow",
        prompt_text="Cảnh origami thứ hai.", parameters={},
        idempotency_key="auto-edit-child-two-01", project_id="project-01",
    )
    child_ids = [first.id, second.id]
    for index in range(2, child_count):
        child = enqueue_media_job(
            db, workspace_id=workspace_id, user_id="user-queue", provider="MEDIA_VIDEO",
            operation="generate_video_scene", backend_provider="GOOGLE_FLOW",
            provider_mode="FLOW_BROWSER_PILOT", model_id="google-flow",
            prompt_text="Cảnh giấy bổ sung.", parameters={},
            idempotency_key=f"auto-edit-child-extra-{index}", project_id="project-01",
        )
        child.state = "SUCCEEDED"
        child_ids.append(child.id)
    request = json.loads(parent.request_payload_json)
    request["parameters"].update(phase="waiting_for_flow", flow_job_ids=child_ids)
    parent.request_payload_json = json.dumps(request)
    parent.state = "WAITING_FOR_FLOW"
    second.state = "SUCCEEDED"
    db.commit()
    token = "auto-edit-resume-token"
    db.add(ContentVideoWorkerLease(name=worker.LEASE_NAME, token=token,
                                   expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)))
    db.commit()

    assert worker._resume_waiting_auto_edit_jobs(db, token) == 0
    assert db.get(AIGenerationJob, parent.id).state == "WAITING_FOR_FLOW"

    first.state = "FAILED"
    db.commit()
    assert worker._resume_waiting_auto_edit_jobs(db, token) == 1
    assert db.get(AIGenerationJob, parent.id).state == "QUEUED"
    resumed = json.loads(db.get(AIGenerationJob, parent.id).request_payload_json)
    assert resumed["parameters"]["phase"] == "render"
    assert resumed["parameters"]["flow_job_ids"] == child_ids
    assert worker._resume_waiting_auto_edit_jobs(db, token) == 0



def test_auto_edit_cleanup_removes_only_its_persisted_plan(tmp_path, monkeypatch):
    from src.modules.media_queue import worker
    from src.modules.media_studio import security

    monkeypatch.setattr(security, "MEDIA_ROOT_DIR", tmp_path)
    plan = tmp_path / ".cache" / "auto_edit" / "parent-job.json"
    plan.parent.mkdir(parents=True)
    plan.write_text("{}", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    worker._cleanup_auto_edit_plan(
        SimpleNamespace(id="parent-job"),
        {"operation": "auto_edit_video", "parameters": {
            "phase": "render", "plan_storage_key": "../outside.json",
        }},
    )

    assert plan.is_file()
    assert outside.is_file()
    worker._cleanup_auto_edit_plan(
        SimpleNamespace(id="parent-job"),
        {"operation": "auto_edit_video", "parameters": {
            "phase": "render", "plan_storage_key": ".cache/auto_edit/parent-job.json",
        }},
    )
    assert not plan.exists()
