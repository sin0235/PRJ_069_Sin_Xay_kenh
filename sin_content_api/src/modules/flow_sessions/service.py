from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import FlowDesktopGrant, FlowLoginSession, FlowProfile, FlowSessionCommand

_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")

_ERROR_MESSAGES = {
    "FLOW_WORKSPACE_INVALID": "The selected workspace ID is invalid.",
    "FLOW_ACTIVE_PROFILE_REQUIRED": "Select an active Flow profile or provide a profile ID.",
    "FLOW_PROFILE_NOT_FOUND": "The Flow profile was not found in this workspace.",
    "FLOW_PROFILE_NAME_INVALID": "Profile names must contain between 1 and 100 characters.",
    "FLOW_PROFILE_NAME_EXISTS": "A Flow profile with this name already exists in this workspace.",
    "FLOW_SESSION_BUSY": "Another Flow login session is already active.",
    "FLOW_COMMAND_NOT_FOUND": "The Flow command was not found in this workspace.",
    "FLOW_SESSION_NOT_FOUND": "The Flow login session was not found in this workspace.",
    "FLOW_DESKTOP_UNAVAILABLE": "The Flow desktop is not open for this session.",
    "FLOW_DESKTOP_ORIGIN_DENIED": "The Flow desktop request origin is not allowed.",
    "FLOW_DESKTOP_ACCESS_EXPIRED": "The Flow desktop access has expired or been revoked.",
}


def _raise_flow_error(status_code: int, error_code: str) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"error_code": error_code, "message": _ERROR_MESSAGES[error_code]},
    )


def resolve_profile(db: Session, workspace_id: str, profile_id: str | None = None) -> FlowProfile:
    if not _SAFE_ID.fullmatch(workspace_id):
        _raise_flow_error(400, "FLOW_WORKSPACE_INVALID")
    query = db.query(FlowProfile).filter(FlowProfile.workspace_id == workspace_id)
    if profile_id is None:
        profile = query.filter(FlowProfile.is_active.is_(True)).first()
        if profile is None:
            _raise_flow_error(409, "FLOW_ACTIVE_PROFILE_REQUIRED")
        return profile
    if not _SAFE_ID.fullmatch(profile_id):
        _raise_flow_error(404, "FLOW_PROFILE_NOT_FOUND")
    profile = query.filter(FlowProfile.id == profile_id).first()
    if profile is None:
        _raise_flow_error(404, "FLOW_PROFILE_NOT_FOUND")
    return profile


def current_profile(db: Session, workspace_id: str) -> FlowProfile:
    return resolve_profile(db, workspace_id)


def current_login_session(db: Session, workspace_id: str) -> FlowLoginSession | None:
    return db.query(FlowLoginSession).filter(
        FlowLoginSession.workspace_id == workspace_id,
        FlowLoginSession.active_slot.is_not(None),
    ).first()


def list_profiles(db: Session, workspace_id: str) -> list[FlowProfile]:
    if not _SAFE_ID.fullmatch(workspace_id):
        _raise_flow_error(400, "FLOW_WORKSPACE_INVALID")
    return (
        db.query(FlowProfile)
        .filter(FlowProfile.workspace_id == workspace_id)
        .order_by(FlowProfile.created_at, FlowProfile.id)
        .all()
    )


def create_profile(db: Session, workspace_id: str, name: str, created_by: str) -> FlowProfile:
    if not _SAFE_ID.fullmatch(workspace_id):
        _raise_flow_error(400, "FLOW_WORKSPACE_INVALID")
    name = name.strip()
    if not 1 <= len(name) <= 100:
        _raise_flow_error(422, "FLOW_PROFILE_NAME_INVALID")
    profile = FlowProfile(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        name=name,
        is_active=db.query(FlowProfile.id).filter(FlowProfile.workspace_id == workspace_id).first() is None,
        created_by=created_by,
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        try:
            _raise_flow_error(409, "FLOW_PROFILE_NAME_EXISTS")
        except HTTPException as flow_exc:
            raise flow_exc from exc
    db.refresh(profile)
    return profile


def activate_profile(db: Session, workspace_id: str, profile_id: str) -> FlowProfile:
    profile = resolve_profile(db, workspace_id, profile_id)
    db.query(FlowProfile).filter(FlowProfile.workspace_id == workspace_id).update(
        {FlowProfile.is_active: False}, synchronize_session="fetch"
    )
    db.query(FlowProfile).filter(
        FlowProfile.workspace_id == workspace_id,
        FlowProfile.id == profile.id,
    ).update({FlowProfile.is_active: True}, synchronize_session="fetch")
    db.commit()
    db.refresh(profile)
    return profile


def request_login(
    db: Session,
    workspace_id: str,
    profile_id: str | None,
    requested_by: str,
) -> FlowLoginSession:
    profile = resolve_profile(db, workspace_id, profile_id)
    now = datetime.now(timezone.utc)
    session = FlowLoginSession(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        profile_id=profile.id,
        requested_by=requested_by,
        status="LOGIN_REQUESTED",
        active_slot="flow",
        expires_at=now + timedelta(minutes=20),
    )
    db.add(session)
    db.add(
        FlowSessionCommand(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            profile_id=profile.id,
            session_id=session.id,
            kind="LOGIN",
            state="PENDING",
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        try:
            _raise_flow_error(409, "FLOW_SESSION_BUSY")
        except HTTPException as flow_exc:
            raise flow_exc from exc
    db.refresh(session)
    return session


def request_profile_check(db: Session, workspace_id: str, profile_id: str | None) -> FlowSessionCommand:
    profile = resolve_profile(db, workspace_id, profile_id)
    command = FlowSessionCommand(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        profile_id=profile.id,
        kind="CHECK",
        state="PENDING",
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


def get_command(db: Session, workspace_id: str, command_id: str) -> FlowSessionCommand:
    command = (
        db.query(FlowSessionCommand)
        .filter(FlowSessionCommand.id == command_id, FlowSessionCommand.workspace_id == workspace_id)
        .first()
    )
    if command is None:
        _raise_flow_error(404, "FLOW_COMMAND_NOT_FOUND")
    return command


def request_close(db: Session, workspace_id: str, session_id: str) -> FlowLoginSession:
    session = (
        db.query(FlowLoginSession)
        .filter(FlowLoginSession.id == session_id, FlowLoginSession.workspace_id == workspace_id)
        .first()
    )
    if session is None:
        _raise_flow_error(404, "FLOW_SESSION_NOT_FOUND")
    if session.status in {"CLOSED", "TIMED_OUT", "FAILED", "INTERRUPTED"}:
        return session
    if session.status == "LOGIN_REQUESTED" and session.lease_token is None:
        session.status = "CLOSED"
        session.active_slot = None
        session.closed_at = datetime.now(timezone.utc)
        db.query(FlowSessionCommand).filter(
            FlowSessionCommand.session_id == session.id,
            FlowSessionCommand.state == "PENDING",
        ).update({FlowSessionCommand.state: "DONE", FlowSessionCommand.finished_at: session.closed_at}, synchronize_session=False)
        db.commit()
        db.refresh(session)
        return session
    session.status = "CLOSE_REQUESTED"
    db.query(FlowDesktopGrant).filter(
        FlowDesktopGrant.session_id == session.id,
        FlowDesktopGrant.workspace_id == workspace_id,
        FlowDesktopGrant.revoked_at.is_(None),
    ).update({FlowDesktopGrant.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
    close_exists = (
        db.query(FlowSessionCommand.id)
        .filter(
            FlowSessionCommand.session_id == session.id,
            FlowSessionCommand.kind == "CLOSE",
            FlowSessionCommand.state.in_(("PENDING", "RUNNING")),
        )
        .first()
    )
    if not close_exists:
        db.add(
            FlowSessionCommand(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                profile_id=session.profile_id,
                session_id=session.id,
                kind="CLOSE",
                state="PENDING",
            )
        )
    db.commit()
    db.refresh(session)
    return session


def create_desktop_grant(
    db: Session, workspace_id: str, session_id: str, user_id: str
) -> tuple[str, FlowDesktopGrant]:
    session = (
        db.query(FlowLoginSession)
        .filter(
            FlowLoginSession.id == session_id,
            FlowLoginSession.workspace_id == workspace_id,
            FlowLoginSession.status.in_(("OPEN", "LOGIN_OPEN")),
        )
        .first()
    )
    if session is None:
        _raise_flow_error(409, "FLOW_DESKTOP_UNAVAILABLE")
    db.query(FlowDesktopGrant).filter(
        FlowDesktopGrant.session_id == session.id,
        FlowDesktopGrant.workspace_id == workspace_id,
        FlowDesktopGrant.revoked_at.is_(None),
    ).update({FlowDesktopGrant.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
    raw_token = secrets.token_urlsafe(32)
    grant = FlowDesktopGrant(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        session_id=session.id,
        user_id=user_id,
        token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(grant)
    db.commit()
    return raw_token, grant


def validate_desktop_grant(
    db: Session, session_id: str, raw_token: str, origin: str | None
) -> FlowDesktopGrant:
    allowed_origins = {value.strip().rstrip("/") for value in __import__("os").environ.get("FLOW_DESKTOP_ALLOWED_ORIGINS", "").split(",") if value.strip()}
    if not origin or origin.rstrip("/") not in allowed_origins:
        _raise_flow_error(403, "FLOW_DESKTOP_ORIGIN_DENIED")
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    grant = (
        db.query(FlowDesktopGrant)
        .filter(
            FlowDesktopGrant.session_id == session_id,
            FlowDesktopGrant.token_digest == digest,
            FlowDesktopGrant.revoked_at.is_(None),
            FlowDesktopGrant.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if grant is None:
        _raise_flow_error(401, "FLOW_DESKTOP_ACCESS_EXPIRED")
    session = db.get(FlowLoginSession, grant.session_id)
    if session is None or session.workspace_id != grant.workspace_id or session.status not in {"OPEN", "LOGIN_OPEN"}:
        _raise_flow_error(401, "FLOW_DESKTOP_ACCESS_EXPIRED")
    return grant


def record_profile_state(
    db: Session,
    workspace_id: str,
    profile_id: str,
    *,
    state: str,
    error_code: str | None = None,
    provider: str | None = None,
) -> FlowProfile:
    if state not in {"READY", "LOGIN_REQUIRED", "QUOTA_LIMITED", "UNKNOWN", "CHECK_FAILED"}:
        raise ValueError("Unsupported Flow profile state")
    profile = resolve_profile(db, workspace_id, profile_id)
    profile.state = state
    profile.error_code = error_code
    profile.last_checked_at = datetime.now(timezone.utc)
    if provider == "google_flow":
        profile.google_flow_state = state
    elif provider == "flow_music":
        profile.flow_music_state = state
    db.commit()
    db.refresh(profile)
    return profile


def record_provider_error(
    db: Session, workspace_id: str, profile_id: str, error_code: str
) -> FlowProfile:
    state_by_error = {
        "FLOW_LOGIN_REQUIRED": "LOGIN_REQUIRED",
        "FLOW_QUOTA_LIMITED": "QUOTA_LIMITED",
        "FLOW_CREDITS_INSUFFICIENT": "QUOTA_LIMITED",
    }
    state = state_by_error.get(error_code)
    if state is None:
        raise ValueError("Unsupported Flow provider error code")
    return record_profile_state(
        db,
        workspace_id,
        profile_id,
        state=state,
        error_code=error_code,
        provider="google_flow",
    )


def record_profile_check(
    db: Session,
    workspace_id: str,
    profile_id: str,
    flow_music_state: str,
    google_flow_state: str,
) -> FlowProfile:
    states = {"READY", "LOGIN_REQUIRED", "QUOTA_LIMITED", "UNKNOWN", "CHECK_FAILED"}
    if flow_music_state not in states or google_flow_state not in states:
        raise ValueError("Unsupported Flow provider state")
    if "QUOTA_LIMITED" in {flow_music_state, google_flow_state}:
        aggregate = "QUOTA_LIMITED"
        error_code = "FLOW_QUOTA_LIMITED"
    elif "LOGIN_REQUIRED" in {flow_music_state, google_flow_state}:
        aggregate = "LOGIN_REQUIRED"
        error_code = "FLOW_LOGIN_REQUIRED"
    elif flow_music_state == google_flow_state == "READY":
        aggregate = "READY"
        error_code = None
    elif "CHECK_FAILED" in {flow_music_state, google_flow_state}:
        aggregate = "CHECK_FAILED"
        error_code = "FLOW_CHECK_FAILED"
    else:
        aggregate = "UNKNOWN"
        error_code = None
    profile = resolve_profile(db, workspace_id, profile_id)
    profile.flow_music_state = flow_music_state
    profile.google_flow_state = google_flow_state
    profile.state = aggregate
    profile.error_code = error_code
    profile.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    return profile
