from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text

from src.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FlowProfile(Base):
    __tablename__ = "flow_profiles"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_flow_profiles_workspace_name"),
        Index(
            "uq_flow_profiles_active_workspace",
            "workspace_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active"),
        ),
    )

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(64), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False)
    state = Column(String(32), nullable=False, default="UNKNOWN")
    flow_music_state = Column(String(32), nullable=False, default="UNKNOWN")
    google_flow_state = Column(String(32), nullable=False, default="UNKNOWN")
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(64), nullable=True)
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class FlowLoginSession(Base):
    __tablename__ = "flow_login_sessions"
    __table_args__ = (UniqueConstraint("active_slot", name="uq_flow_login_active_slot"),)

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(64), nullable=False, index=True)
    profile_id = Column(String(36), ForeignKey("flow_profiles.id"), nullable=False, index=True)
    requested_by = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="LOGIN_REQUESTED", index=True)
    active_slot = Column(String(16), nullable=True)
    lease_token = Column(String(36), nullable=True)
    error_code = Column(String(64), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class FlowSessionCommand(Base):
    __tablename__ = "flow_session_commands"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(64), nullable=False, index=True)
    profile_id = Column(String(36), ForeignKey("flow_profiles.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("flow_login_sessions.id"), nullable=True, index=True)
    kind = Column(String(24), nullable=False)
    state = Column(String(24), nullable=False, default="PENDING", index=True)
    result_json = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    lease_token = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class FlowDesktopGrant(Base):
    __tablename__ = "flow_desktop_grants"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("flow_login_sessions.id"), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    token_digest = Column(String(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
