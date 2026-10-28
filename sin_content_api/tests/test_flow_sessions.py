import importlib.util

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.models.entities import Workspace


def _flow_session_service():
    assert importlib.util.find_spec("src.modules.flow_sessions") is not None
    service_spec = importlib.util.find_spec("src.modules.flow_sessions.service")
    assert service_spec is not None, "Flow profile lookup service must be available"
    from src.modules.flow_sessions import models, service

    return models, service


def test_resolve_profile_uses_active_profile_and_rejects_cross_workspace_ids(tmp_path):
    models, service = _flow_session_service()
    engine = create_engine(f"sqlite:///{tmp_path / 'flow_profiles.sqlite'}")
    models.Base.metadata.create_all(bind=engine, tables=[Workspace.__table__, models.FlowProfile.__table__])

    with Session(engine) as db:
        db.add_all(
            [
                models.FlowProfile(
                    id="profile-a", workspace_id="workspace-a", name="A", is_active=True, created_by="owner-a"
                ),
                models.FlowProfile(
                    id="profile-b", workspace_id="workspace-b", name="B", is_active=True, created_by="owner-b"
                ),
            ]
        )
        db.commit()

        assert service.current_profile(db, "workspace-a").id == "profile-a"
        assert service.resolve_profile(db, "workspace-a", "profile-a").id == "profile-a"
        with pytest.raises(HTTPException) as exc:
            service.resolve_profile(db, "workspace-a", "profile-b")
        assert exc.value.status_code == 404


def test_resolve_profile_requires_active_profile_when_id_is_omitted(tmp_path):
    models, service = _flow_session_service()
    engine = create_engine(f"sqlite:///{tmp_path / 'flow_profiles.sqlite'}")
    models.Base.metadata.create_all(bind=engine, tables=[Workspace.__table__, models.FlowProfile.__table__])

    with Session(engine) as db, pytest.raises(HTTPException) as exc:
        service.resolve_profile(db, "workspace-a")

    assert exc.value.status_code == 409
    assert exc.value.detail == {
        "error_code": "FLOW_ACTIVE_PROFILE_REQUIRED",
        "message": "Select an active Flow profile or provide a profile ID.",
    }


def test_profile_creation_activation_and_listing_stay_in_workspace(tmp_path):
    models, service = _flow_session_service()
    assert callable(getattr(service, "create_profile", None))
    assert callable(getattr(service, "activate_profile", None))
    assert callable(getattr(service, "list_profiles", None))
    engine = create_engine(f"sqlite:///{tmp_path / 'flow_profiles.sqlite'}")
    models.Base.metadata.create_all(bind=engine, tables=[Workspace.__table__, models.FlowProfile.__table__])

    with Session(engine) as db:
        first = service.create_profile(db, "workspace-a", "Primary", "owner-a")
        second = service.create_profile(db, "workspace-a", "Backup", "owner-a")
        other = service.create_profile(db, "workspace-b", "Other", "owner-b")

        assert first.is_active is True
        assert second.is_active is False
        assert [profile.id for profile in service.list_profiles(db, "workspace-a")] == [first.id, second.id]
        assert service.activate_profile(db, "workspace-a", second.id).id == second.id
        assert service.current_profile(db, "workspace-a").id == second.id
        assert service.activate_profile(db, "workspace-a", second.id).id == second.id
        assert db.query(models.FlowProfile).filter_by(workspace_id="workspace-a", is_active=True).count() == 1
        assert service.current_profile(db, "workspace-a").id == second.id

        assert service.activate_profile(db, "workspace-a", first.id).id == first.id
        assert db.query(models.FlowProfile).filter_by(workspace_id="workspace-a", is_active=True).count() == 1
        assert service.current_profile(db, "workspace-a").id == first.id
        with pytest.raises(HTTPException) as exc:
            service.activate_profile(db, "workspace-a", other.id)
        assert exc.value.status_code == 404


def test_login_request_is_a_durable_singleton_command(tmp_path):
    models, service = _flow_session_service()
    assert callable(getattr(service, "request_login", None))
    engine = create_engine(f"sqlite:///{tmp_path / 'flow_sessions.sqlite'}")
    models.Base.metadata.create_all(
        bind=engine,
        tables=[
            Workspace.__table__,
            models.FlowProfile.__table__,
            models.FlowLoginSession.__table__,
            models.FlowSessionCommand.__table__,
        ],
    )

    with Session(engine) as db:
        profile = service.create_profile(db, "workspace-a", "Primary", "owner-a")
        login = service.request_login(db, "workspace-a", profile.id, "owner-a")
        command = db.query(models.FlowSessionCommand).filter_by(session_id=login.id).one()

        assert login.status == "LOGIN_REQUESTED"
        assert command.kind == "LOGIN"
        assert command.state == "PENDING"
        with pytest.raises(HTTPException) as exc:
            service.request_login(db, "workspace-a", profile.id, "owner-a")
        assert exc.value.status_code == 409


def test_profile_check_is_queued_and_not_reported_as_provider_success(tmp_path):
    models, service = _flow_session_service()
    assert callable(getattr(service, "request_profile_check", None))
    engine = create_engine(f"sqlite:///{tmp_path / 'flow_sessions.sqlite'}")
    models.Base.metadata.create_all(bind=engine, tables=[Workspace.__table__, models.FlowProfile.__table__, models.FlowSessionCommand.__table__])

    with Session(engine) as db:
        profile = service.create_profile(db, "workspace-a", "Primary", "owner-a")
        command = service.request_profile_check(db, "workspace-a", profile.id)

        assert command.kind == "CHECK"
        assert command.state == "PENDING"
        assert profile.state == "UNKNOWN"


def test_closing_unclaimed_login_cancels_durable_request_without_opening_browser(tmp_path):
    models, service = _flow_session_service()
    engine = create_engine(f"sqlite:///{tmp_path / 'close.sqlite'}")
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        profile = service.create_profile(db, "workspace", "First", "owner")
        session = service.request_login(db, "workspace", profile.id, "owner")
        result = service.request_close(db, "workspace", session.id)
        assert result.status == "CLOSED"
        assert result.active_slot is None
        assert db.query(models.FlowSessionCommand).filter_by(session_id=session.id, state="PENDING").count() == 0


def test_generation_failures_can_persist_login_and_quota_state_per_workspace(tmp_path):
    models, service = _flow_session_service()
    assert callable(getattr(service, "record_provider_error", None))
    engine = create_engine(f"sqlite:///{tmp_path / 'flow_profiles.sqlite'}")
    models.Base.metadata.create_all(bind=engine, tables=[Workspace.__table__, models.FlowProfile.__table__])

    with Session(engine) as db:
        first = service.create_profile(db, "workspace-a", "Primary", "owner-a")
        other = service.create_profile(db, "workspace-b", "Primary", "owner-b")

        service.record_provider_error(db, "workspace-a", first.id, "FLOW_LOGIN_REQUIRED")
        assert first.state == "LOGIN_REQUIRED"
        assert first.google_flow_state == "LOGIN_REQUIRED"
        assert first.error_code == "FLOW_LOGIN_REQUIRED"

        service.record_provider_error(db, "workspace-a", first.id, "FLOW_QUOTA_LIMITED")
        assert first.state == "QUOTA_LIMITED"
        assert first.google_flow_state == "QUOTA_LIMITED"
        assert other.state == "UNKNOWN"
