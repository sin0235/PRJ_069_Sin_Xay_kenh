import importlib.util
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _worker_module():
    assert importlib.util.find_spec("src.modules.flow_sessions.worker") is not None
    from src.modules.flow_sessions import worker

    return worker


def test_worker_exports_private_control_app_and_durable_command_claim():
    worker = _worker_module()
    from src.database import Base, SessionLocal, engine
    from src.models.entities import Workspace
    from src.modules.flow_sessions.models import FlowProfile, FlowSessionCommand

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.query(FlowSessionCommand).delete()
        db.commit()
        db.add(Workspace(id="flow-worker-ws", name="Worker", slug="flow-worker-ws"))
        db.flush()
        db.add(FlowProfile(id="flow-worker-profile", workspace_id="flow-worker-ws", name="A", created_by="owner"))
        db.flush()
        command = FlowSessionCommand(
            id="flow-worker-command",
            workspace_id="flow-worker-ws",
            profile_id="flow-worker-profile",
            kind="CHECK",
            state="PENDING",
        )
        db.add(command)
        db.commit()

    manager = worker.FlowSessionWorker()
    claimed = manager._claim_pending_command()
    assert claimed == "flow-worker-command"
    with SessionLocal() as db:
        command = db.get(FlowSessionCommand, claimed)
        assert command.state == "RUNNING"
        assert command.attempts == 1
        assert command.claimed_at is not None
        token = command.lease_token
    worker._release_content_video_lease(token)
    assert worker.app is not None


def test_flow_session_worker_waits_for_shared_content_video_lease():
    worker = _worker_module()
    from src.database import Base, SessionLocal, engine
    from src.models.entities import ContentVideoWorkerLease
    from src.migrations.runner import migrate_content_video_up

    migrate_content_video_up()
    ContentVideoWorkerLease.__table__.create(bind=engine, checkfirst=True)
    with SessionLocal() as db:
        lease = db.get(ContentVideoWorkerLease, "content-video-flow")
        if lease is None:
            db.add(ContentVideoWorkerLease(name="content-video-flow"))
            db.flush()
            lease = db.get(ContentVideoWorkerLease, "content-video-flow")
        lease.token = "active-content-video"
        lease.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        db.commit()

    assert worker._try_acquire_content_video_lease("flow-test-token") is False
    with SessionLocal() as db:
        lease = db.get(ContentVideoWorkerLease, "content-video-flow")
        lease.token = None
        lease.expires_at = None
        db.commit()

    assert worker._try_acquire_content_video_lease("flow-test-token") is True
    worker._release_content_video_lease("flow-test-token")
    with SessionLocal() as db:
        lease = db.get(ContentVideoWorkerLease, "content-video-flow")
        assert lease.token is None


@pytest.mark.parametrize("ownership", ["expired", "live", "live-other", "unknown"])
def test_restart_recovers_only_expired_known_session_owner(tmp_path, monkeypatch, ownership):
    worker = _worker_module()
    from src.database import Base
    from src.models.entities import ContentVideoWorkerLease
    from src.modules.flow_sessions.models import FlowDesktopGrant, FlowLoginSession, FlowSessionCommand

    engine = create_engine(f"sqlite:///{tmp_path / 'restart.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(worker, "SessionLocal", sessions)
    now = datetime.now(timezone.utc)
    with sessions() as db:
        db.add(ContentVideoWorkerLease(
            name="content-video-flow", token="other-owner" if ownership == "live-other" else "old-owner",
            expires_at=now + timedelta(minutes=5) if ownership in {"live", "live-other"} else now - timedelta(seconds=1),
        ))
        db.add(FlowLoginSession(
            id="old-session", workspace_id="workspace", profile_id="profile", requested_by="owner",
            status="OPEN", active_slot="flow", lease_token=None if ownership == "unknown" else "old-owner",
            expires_at=now + timedelta(minutes=10),
        ))
        db.add(FlowSessionCommand(
            id="old-login", workspace_id="workspace", profile_id="profile", session_id="old-session",
            kind="LOGIN", state="RUNNING", lease_token=None if ownership == "unknown" else "old-owner",
            claimed_at=now - timedelta(minutes=10),
        ))
        db.add(FlowDesktopGrant(
            id="old-grant", workspace_id="workspace", session_id="old-session", user_id="owner",
            token_digest="digest", expires_at=now + timedelta(minutes=1),
        ))
        db.commit()

    worker.FlowSessionWorker()._recover_orphans()
    with sessions() as db:
        row = db.get(FlowLoginSession, "old-session")
        grant = db.get(FlowDesktopGrant, "old-grant")
        command = db.get(FlowSessionCommand, "old-login")
        if ownership == "expired":
            assert row.status == "INTERRUPTED"
            assert row.active_slot is None
            assert grant.revoked_at is not None
            assert command.state == "FAILED"
        else:
            assert row.status == "OPEN"
            assert row.active_slot == "flow"
            assert grant.revoked_at is None
            assert command.state == "RUNNING"


def test_restart_requeues_expired_running_check_and_claim_persists_lease(tmp_path, monkeypatch):
    worker = _worker_module()
    from src.database import Base
    from src.models.entities import ContentVideoWorkerLease
    from src.modules.flow_sessions.models import FlowSessionCommand

    engine = create_engine(f"sqlite:///{tmp_path / 'commands.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(worker, "SessionLocal", sessions)
    with sessions() as db:
        db.add(ContentVideoWorkerLease(
            name="content-video-flow", token="dead-check",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ))
        db.add(FlowSessionCommand(
            id="check", workspace_id="workspace", profile_id="profile", kind="CHECK", state="RUNNING",
            lease_token="dead-check", claimed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        ))
        db.commit()
    manager = worker.FlowSessionWorker()
    manager._recover_orphans()
    with sessions() as db:
        assert db.get(FlowSessionCommand, "check").state == "PENDING"
    assert manager._claim_pending_command() == "check"
    with sessions() as db:
        command = db.get(FlowSessionCommand, "check")
        lease = db.get(ContentVideoWorkerLease, "content-video-flow")
        assert command.state == "RUNNING"
        assert command.lease_token and command.lease_token == lease.token
        token = command.lease_token
    worker._release_content_video_lease(token)


def test_login_claim_records_session_owner_before_browser_start(tmp_path, monkeypatch):
    worker = _worker_module()
    from src.database import Base
    from src.models.entities import ContentVideoWorkerLease
    from src.modules.flow_sessions.models import FlowLoginSession, FlowSessionCommand

    engine = create_engine(f"sqlite:///{tmp_path / 'claim.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(worker, "SessionLocal", sessions)
    with sessions() as db:
        db.add(FlowLoginSession(
            id="login", workspace_id="workspace", profile_id="profile", requested_by="owner",
            status="LOGIN_REQUESTED", active_slot="flow", expires_at=datetime.now(timezone.utc) + timedelta(minutes=20),
        ))
        db.add(FlowSessionCommand(
            id="command", session_id="login", workspace_id="workspace", profile_id="profile", kind="LOGIN", state="PENDING",
        ))
        db.commit()
    assert worker.FlowSessionWorker()._claim_pending_command() == "command"
    with sessions() as db:
        token = db.get(ContentVideoWorkerLease, "content-video-flow").token
        assert token
        assert db.get(FlowSessionCommand, "command").lease_token == token
        assert db.get(FlowLoginSession, "login").lease_token == token
    worker._release_content_video_lease(token)


def test_pending_legacy_login_cannot_replace_unknown_live_owner(tmp_path, monkeypatch):
    worker = _worker_module()
    from src.database import Base
    from src.modules.flow_sessions.models import FlowLoginSession, FlowSessionCommand

    engine = create_engine(f"sqlite:///{tmp_path / 'unknown.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(worker, "SessionLocal", sessions)
    with sessions() as db:
        db.add(FlowLoginSession(
            id="legacy", workspace_id="workspace", profile_id="profile", requested_by="owner",
            status="OPEN", active_slot="flow", expires_at=datetime.now(timezone.utc) + timedelta(minutes=20),
        ))
        db.add(FlowSessionCommand(
            id="command", session_id="legacy", workspace_id="workspace", profile_id="profile", kind="LOGIN", state="PENDING",
        ))
        db.commit()
    manager = worker.FlowSessionWorker()
    monkeypatch.setattr(manager, "_start_login", lambda *args: pytest.fail("Must preserve an unknown owner"))
    assert manager._claim_pending_command() == "command"
    manager._process_command("command")
    with sessions() as db:
        assert db.get(FlowLoginSession, "legacy").status == "OPEN"
        assert db.get(FlowLoginSession, "legacy").active_slot == "flow"



def test_phien_windows_mo_native_khong_can_x11_novnc(monkeypatch):
    worker = _worker_module()
    monkeypatch.setattr(worker.os, "name", "nt")
    runtime = worker.DesktopRuntime()
    def forbidden(*args, **kwargs):
        raise AssertionError("X11_NOT_ALLOWED_ON_WINDOWS")
    monkeypatch.setattr(runtime, "_spawn", forbidden)
    runtime.start()
    assert runtime.processes == []
    assert runtime.stop() is True
