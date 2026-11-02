import json
import sys
import types
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.entities import ContentVideoWorkerLease, MediaAsset, Workspace
from src.modules.media_queue.service import enqueue_media_job


@pytest.fixture
def media_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    workspace_id = f"ws-auto-edit-{uuid.uuid4().hex[:8]}"
    db.add(Workspace(id=workspace_id, name="Auto Edit", slug=workspace_id))
    db.commit()
    try:
        yield db, factory, workspace_id
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_hyperframes_child_worker_persists_output_asset(media_db, monkeypatch):
    db, factory, workspace_id = media_db
    flow_session = types.ModuleType("session_manager")
    flow_session.FlowLoginRequired = type("FlowLoginRequired", (Exception,), {})
    flow_session.FlowSubmissionNotSent = type("FlowSubmissionNotSent", (Exception,), {})
    flow_session.FlowQuotaExceeded = type("FlowQuotaExceeded", (Exception,), {})
    flow_session.LOCAL_BROWSER_PROFILE_DIR = None
    monkeypatch.setitem(sys.modules, "session_manager", flow_session)
    from src.modules.media_queue import worker
    from src.modules.dieu_phoi_dung import dung_video_dai as editor

    job = enqueue_media_job(
        db,
        workspace_id=workspace_id,
        user_id="user-auto-edit",
        provider="MEDIA_VIDEO",
        operation="render_auto_edit_diagram",
        backend_provider="BAHA_AUTO_EDIT",
        provider_mode="INTERNAL_RENDERER",
        model_id="hyperframes",
        prompt_text="Render paper diagram",
        parameters={"target_clip_id": "part1_01"},
        idempotency_key=f"hyperframes-{uuid.uuid4()}",
        credits_source="BAHA_AUTO_EDIT",
    )
    token = str(uuid.uuid4())
    db.add(ContentVideoWorkerLease(
        name=worker.LEASE_NAME,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=8),
    ))
    db.commit()

    def render(db, job, _request):
        asset = MediaAsset(
            id=str(uuid.uuid4()), workspace_id=job.workspace_id, project_id=job.project_id,
            storage_key=f"workspaces/{job.workspace_id}/media/diagram.mov", sha256="a" * 64,
            byte_size=24_000, mime_detected="video/quicktime", source_product="AUTO_EDIT_HYPERFRAMES",
            created_by=job.created_by,
        )
        db.add(asset)
        db.flush()
        return asset

    monkeypatch.setattr(editor, "render_auto_edit_diagram", render)
    monkeypatch.setattr(worker, "authorized_worker_tenant", lambda *args, **kwargs: nullcontext())
    monkeypatch.setattr(worker, "SessionLocal", factory)

    assert worker.process_next_media_job(db, token) is True

    db.refresh(job)
    output_ids = json.loads(job.output_asset_ids_json)
    assert job.state == "SUCCEEDED"
    assert len(output_ids) == 1
    assert db.query(MediaAsset).filter_by(id=output_ids[0], source_product="AUTO_EDIT_HYPERFRAMES").one()
