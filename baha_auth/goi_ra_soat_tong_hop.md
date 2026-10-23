# Gói rà soát tổng hợp — nguồn hiện tại
Không có HEAD/baseline tracked nên đây là ảnh nguồn kèm hash, không giả lập diff. Nhóm 2 đang sửa vòng 1 theo ra_soat_doc_lap_nhom_2.md và nhat_ky_dieu_phoi_sua_quyen.md; phần reviewer tổng hợp cần đối chiếu cả bản sửa cuối đó trước kết luận.
## baha_auth/src/database.py — SHA256 6569F964B18669C9882F035501D4EBD06E243B79EA343CD41096413FEDDBB155
```
"""Quản lý engine và session chuẩn; ứng dụng không tự tạo schema."""

import contextvars
from typing import Generator, Optional

from sqlalchemy import create_engine, inspect, text, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException, status

from baha_auth.src.config import settings


_current_tenant_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "baha_auth_current_tenant_id", default=None
)

engine = None
if settings.database_url:
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    pool_options = {}
    if settings.database_url in ("sqlite://", "sqlite:///:memory:"):
        pool_options["poolclass"] = StaticPool
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        echo=settings.debug,
        **pool_options,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


if engine is not None and settings.database_url and settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def set_tenant_context(workspace_id: str, db: Optional[Session] = None) -> None:
    """Gắn workspace đã xác minh vào yêu cầu và giao dịch PostgreSQL hiện tại."""
    _current_tenant_id.set(workspace_id)
    if db is not None:
        db.info["baha_auth.trusted_workspace_id"] = workspace_id
        # Bắt đầu giao dịch để hook after_begin đặt ngữ cảnh RLS trước khi truy vấn.
        db.connection()


def get_tenant_context() -> Optional[str]:
    return _current_tenant_id.get()


def clear_tenant_context(db: Optional[Session] = None) -> None:
    _current_tenant_id.set(None)
    if db is not None:
        db.info.pop("baha_auth.trusted_workspace_id", None)


@event.listens_for(Session, "after_begin")
def _apply_postgres_tenant_context(db: Session, _transaction, connection) -> None:
    workspace_id = db.info.get("baha_auth.trusted_workspace_id")
    if workspace_id and connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT set_config('baha.current_workspace_id', :workspace_id, true)"),
            {"workspace_id": workspace_id},
        )


def get_db() -> Generator[Session, None, None]:
    if engine is None or not settings.database_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "AUTH_DATABASE_NOT_CONFIGURED", "message": "Cơ sở dữ liệu phân quyền chưa được cấu hình."},
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        clear_tenant_context(db)
        db.close()


def init_db() -> None:
    """Dừng khởi động nếu thiếu schema được quản lý bên ngoài; không tự tạo schema."""
    if engine is None or not settings.database_url:
        raise RuntimeError("AUTH_DATABASE_NOT_CONFIGURED")
    existing = set(inspect(engine).get_table_names())
    required = set(Base.metadata.tables)
    missing = sorted(required - existing)
    if missing:
        raise RuntimeError("AUTH_SCHEMA_NOT_INITIALIZED")

```
## baha_auth/src/models/entities.py — SHA256 BD6F273B426465125012F1B84A6AEAD5E46747C6952EF5DDB93112268FC8882D
```
# Toan bo thuc the ORM cho He thong Phan quyen Doanh nghiep BAHA GROUP (BAHA-AUTHZ-001)
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, ForeignKeyConstraint,
    Text, UniqueConstraint, Index, DDL, event,
)
from sqlalchemy.orm import relationship
from baha_auth.src.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class GlobalUser(Base):
    __tablename__ = "global_users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    primary_identity_ref = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE") # ACTIVE, SUSPENDED, REVOKED
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")

class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    type = Column(String(50), nullable=False, default="ENTERPRISE") # ENTERPRISE, AGENCY, SUBSIDIARY
    status = Column(String(50), nullable=False, default="ACTIVE")
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    memberships = relationship("Membership", back_populates="workspace", cascade="all, delete-orphan")
    org_units = relationship("OrgUnit", back_populates="workspace", cascade="all, delete-orphan")
    resources = relationship("BusinessResource", back_populates="workspace", cascade="all, delete-orphan")

class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
        UniqueConstraint("workspace_id", "id", name="uq_memberships_workspace_id"),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("global_users.id"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="ACTIVE") # INVITED, ACTIVE, SUSPENDED, REVOKED
    joined_at = Column(DateTime, default=utc_now, nullable=False)
    policy_revision = Column(Integer, default=1, nullable=False)
    
    workspace = relationship("Workspace", back_populates="memberships")
    user = relationship("GlobalUser", back_populates="memberships")
    org_assignments = relationship(
        "OrgAssignment", back_populates="membership", cascade="all, delete-orphan",
        overlaps="assignments,org_unit",
    )
    role_assignments = relationship(
        "RoleAssignment", back_populates="membership", cascade="all, delete-orphan",
        foreign_keys="RoleAssignment.membership_id",
    )

class OrgUnit(Base):
    __tablename__ = "org_units"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_org_units_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "parent_id"], ["org_units.workspace_id", "org_units.id"],
            name="fk_org_units_parent_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    parent_id = Column(String(36), nullable=True, index=True)
    type = Column(String(50), nullable=False, default="DEPARTMENT") # COMPANY, DEPARTMENT, TEAM
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="org_units")
    parent = relationship(
        "OrgUnit", remote_side=[workspace_id, id], foreign_keys=[workspace_id, parent_id],
        back_populates="children", overlaps="org_units,workspace",
    )
    children = relationship(
        "OrgUnit", foreign_keys=[workspace_id, parent_id], back_populates="parent",
        overlaps="org_units,workspace",
    )
    assignments = relationship(
        "OrgAssignment", back_populates="org_unit", cascade="all, delete-orphan",
        overlaps="org_assignments,membership",
    )

class ReportingLine(Base):
    __tablename__ = "reporting_lines"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_reporting_lines_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "manager_membership_id"],
            ["memberships.workspace_id", "memberships.id"],
            name="fk_reporting_manager_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "report_membership_id"],
            ["memberships.workspace_id", "memberships.id"],
            name="fk_reporting_report_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "org_unit_id"], ["org_units.workspace_id", "org_units.id"],
            name="fk_reporting_org_unit_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    manager_membership_id = Column(String(36), nullable=False, index=True)
    report_membership_id = Column(String(36), nullable=False, index=True)
    org_unit_id = Column(String(36), nullable=True)
    valid_from = Column(DateTime, default=utc_now, nullable=False)
    valid_until = Column(DateTime, nullable=True)

class OrgAssignment(Base):
    __tablename__ = "org_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "membership_id"], ["memberships.workspace_id", "memberships.id"],
            name="fk_org_assignment_membership_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "org_unit_id"], ["org_units.workspace_id", "org_units.id"],
            name="fk_org_assignment_unit_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    membership_id = Column(String(36), nullable=False, index=True)
    org_unit_id = Column(String(36), nullable=False, index=True)
    assignment_type = Column(String(50), nullable=False, default="PRIMARY") # PRIMARY, SECONDARY, TEMPORARY
    
    membership = relationship("Membership", back_populates="org_assignments", overlaps="assignments,org_unit")
    org_unit = relationship("OrgUnit", back_populates="assignments", overlaps="org_assignments,membership")

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True) # NULL cho platform template
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    is_template = Column(Boolean, default=False, nullable=False)
    is_custom = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")
    rank_label_only = Column(String(50), nullable=True)
    
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    action_key = Column(String(100), unique=True, nullable=False, index=True)
    risk_tier = Column(String(50), nullable=False, default="LOW") # LOW, MEDIUM, HIGH, CRITICAL
    is_immutable = Column(Boolean, default=True, nullable=False)
    description = Column(Text, nullable=True)
    
    roles = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")

class RolePermission(Base):
    __tablename__ = "role_permissions"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False, index=True)
    permission_id = Column(String(36), ForeignKey("permissions.id"), nullable=False, index=True)
    allowed_scope_type = Column(String(50), nullable=False, default="WORKSPACE") # WORKSPACE, DEPARTMENT, TEAM, PROJECT, OWN
    condition_code = Column(String(100), nullable=True)
    policy_version = Column(String(50), nullable=False, default="1.0.0")
    
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")

class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "membership_id"], ["memberships.workspace_id", "memberships.id"],
            name="fk_role_assignment_membership_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "granted_by"], ["memberships.workspace_id", "memberships.id"],
            name="fk_role_assignment_grantor_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    membership_id = Column(String(36), nullable=False, index=True)
    role_id = Column(String(36), ForeignKey("roles.id"), nullable=False, index=True)
    scope_type = Column(String(50), nullable=False, default="WORKSPACE") # WORKSPACE, DEPARTMENT, TEAM, PROJECT, OWN
    scope_id = Column(String(36), nullable=True, index=True)
    valid_from = Column(DateTime, default=utc_now, nullable=False)
    valid_until = Column(DateTime, nullable=True)
    granted_by = Column(String(36), nullable=True)
    grant_reason = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE")
    policy_version = Column(String(50), nullable=False, default="1.0.0")
    
    membership = relationship(
        "Membership", back_populates="role_assignments", foreign_keys=[membership_id]
    )
    role = relationship("Role")

class ResourceGrant(Base):
    __tablename__ = "resource_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "membership_id"], ["memberships.workspace_id", "memberships.id"],
            name="fk_resource_grant_membership_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False, index=True)
    resource_id = Column(String(36), nullable=False, index=True)
    membership_id = Column(String(36), ForeignKey("memberships.id"), nullable=False, index=True)
    permission_id = Column(String(36), ForeignKey("permissions.id"), nullable=False)
    granted_by = Column(String(36), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE")

class Delegation(Base):
    __tablename__ = "delegations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "grantor_membership_id"], ["memberships.workspace_id", "memberships.id"],
            name="fk_delegation_grantor_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "grantee_membership_id"], ["memberships.workspace_id", "memberships.id"],
            name="fk_delegation_grantee_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    grantor_membership_id = Column(String(36), ForeignKey("memberships.id"), nullable=False, index=True)
    grantee_membership_id = Column(String(36), ForeignKey("memberships.id"), nullable=False, index=True)
    grant_spec_json = Column(Text, nullable=False) # JSON: {"role_id": "...", "allowed_actions": [...], "scope_id": "..."}
    approved_by = Column(String(36), nullable=True)
    starts_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")

class ApprovalPolicy(Base):
    __tablename__ = "approval_policies"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_approval_policies_workspace_id"),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    brand_id = Column(String(36), nullable=True)
    campaign_id = Column(String(36), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    stages_json = Column(Text, nullable=False) # JSON array of stages: [{"stage_key": "TEAM_REVIEW", "allowed_role": "TEAM_LEAD"}]
    valid_from = Column(DateTime, default=utc_now, nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")

class ApprovalRun(Base):
    __tablename__ = "approval_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "artifact_type", "artifact_id", "artifact_version", "policy_id",
            name="uq_approval_run_artifact_version_policy",
        ),
        UniqueConstraint("workspace_id", "id", name="uq_approval_runs_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "artifact_id"], ["business_resources.workspace_id", "business_resources.id"],
            name="fk_approval_run_artifact_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "policy_id"], ["approval_policies.workspace_id", "approval_policies.id"],
            name="fk_approval_run_policy_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "created_by"], ["memberships.workspace_id", "memberships.id"],
            name="fk_approval_run_creator_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    artifact_type = Column(String(100), nullable=False, index=True)
    artifact_id = Column(String(36), nullable=False, index=True)
    artifact_version = Column(Integer, default=1, nullable=False)
    content_hash = Column(String(64), nullable=False)
    policy_id = Column(String(36), ForeignKey("approval_policies.id"), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING") # PENDING, APPROVED, REJECTED, CANCELED
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    steps = relationship("ApprovalStep", backref="run", cascade="all, delete-orphan")

class ApprovalStep(Base):
    __tablename__ = "approval_steps"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_approval_steps_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "run_id"], ["approval_runs.workspace_id", "approval_runs.id"],
            name="fk_approval_step_run_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    run_id = Column(String(36), nullable=False, index=True)
    stage_key = Column(String(50), nullable=False)
    allowed_role_or_assignee = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING") # PENDING, APPROVED, REJECTED
    ordinal = Column(Integer, default=1, nullable=False)
    assigned_at = Column(DateTime, default=utc_now, nullable=False)

class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (
        UniqueConstraint("step_id", name="uq_approval_decision_step"),
        ForeignKeyConstraint(
            ["workspace_id", "step_id"], ["approval_steps.workspace_id", "approval_steps.id"],
            name="fk_approval_decision_step_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "reviewer_membership_id"], ["memberships.workspace_id", "memberships.id"],
            name="fk_approval_decision_reviewer_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    step_id = Column(String(36), nullable=False, index=True)
    reviewer_membership_id = Column(String(36), nullable=False, index=True)
    result = Column(String(50), nullable=False) # APPROVED, REJECTED, CHANGES_REQUESTED
    reason = Column(Text, nullable=True)
    artifact_version = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False)
    decided_at = Column(DateTime, default=utc_now, nullable=False)

class DelegatedJobGrant(Base):
    __tablename__ = "delegated_job_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "initiating_membership_id"],
            ["memberships.workspace_id", "memberships.id"],
            name="fk_job_grant_membership_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "target_resource"],
            ["business_resources.workspace_id", "business_resources.id"],
            name="fk_job_grant_resource_same_workspace",
        ),
    )
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    initiating_membership_id = Column(String(36), nullable=False, index=True)
    target_resource = Column(String(255), nullable=False)
    target_artifact_version = Column(Integer, nullable=False)
    target_content_hash = Column(String(64), nullable=False)
    worker_subject = Column(String(255), nullable=False)
    allowed_actions_json = Column(Text, nullable=False) # JSON list of action keys
    expires_at = Column(DateTime, nullable=False)
    policy_version = Column(String(50), nullable=False, default="1.0.0")
    status = Column(String(50), nullable=False, default="ACTIVE") # ACTIVE, REVOKED, EXPIRED
    created_at = Column(DateTime, default=utc_now, nullable=False)

class AuthorizationAuditEvent(Base):
    __tablename__ = "authz_audit_events"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), nullable=True, index=True)
    actor_id = Column(String(36), nullable=True, index=True)
    actor_type = Column(String(50), nullable=False, default="USER") # USER, AI_AGENT, WORKER, SYSTEM
    action_key = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=True)
    resource_id_hash = Column(String(64), nullable=True)
    decision = Column(String(50), nullable=False) # ALLOW, DENY
    internal_reason = Column(String(255), nullable=False)
    policy_version = Column(String(50), nullable=False, default="1.0.0")
    request_id = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    safe_metadata_json = Column(Text, nullable=True)


event.listen(
    AuthorizationAuditEvent.__table__,
    "after_create",
    DDL("CREATE TRIGGER IF NOT EXISTS authz_audit_no_update BEFORE UPDATE ON authz_audit_events BEGIN SELECT RAISE(ABORT, 'Nhật ký phân quyền chỉ được ghi nối tiếp'); END").execute_if(dialect="sqlite"),
)
event.listen(
    AuthorizationAuditEvent.__table__,
    "after_create",
    DDL("CREATE TRIGGER IF NOT EXISTS authz_audit_no_delete BEFORE DELETE ON authz_audit_events BEGIN SELECT RAISE(ABORT, 'Nhật ký phân quyền chỉ được ghi nối tiếp'); END").execute_if(dialect="sqlite"),
)

class BusinessResource(Base):
    """Tai nguyen nghiep vu mau de kiem dinh cach ly Tenant, IDOR, Tim kiem va Quarantine"""
    __tablename__ = "business_resources"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True) # Nullable de test orphaned quarantine
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_business_resources_workspace_id"),
        ForeignKeyConstraint(
            ["workspace_id", "org_unit_id"], ["org_units.workspace_id", "org_units.id"],
            name="fk_business_resource_org_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "owner_id"], ["memberships.workspace_id", "memberships.user_id"],
            name="fk_business_resource_owner_same_workspace",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "creator_id"], ["memberships.workspace_id", "memberships.user_id"],
            name="fk_business_resource_creator_same_workspace",
        ),
    )

    org_unit_id = Column(String(36), nullable=True, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    brand_id = Column(String(36), nullable=True, index=True)
    channel_id = Column(String(36), nullable=True, index=True)
    owner_id = Column(String(36), ForeignKey("global_users.id"), nullable=True, index=True)
    creator_id = Column(String(36), ForeignKey("global_users.id"), nullable=True, index=True)
    artifact_version = Column(Integer, nullable=False, default=1)
    resource_type = Column(String(100), nullable=False, default="IDEA")
    title = Column(String(255), nullable=False)
    content_hash = Column(String(64), nullable=True)
    search_text = Column(Text, nullable=True)
    asset_url = Column(String(255), nullable=True)
    view_count = Column(Integer, default=0, nullable=False)
    is_quarantined = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    workspace = relationship("Workspace", back_populates="resources")

```
## baha_auth/src/services/danh_tinh_service.py — SHA256 35A15EB43E567130CC3B5A77371053A30CC3CC41FCBE8B3079E387713B0DD9DA
```
"""Nạp ngữ cảnh phân quyền hiện tại cho người dùng đã xác minh trong workspace."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from baha_auth.src.models.entities import (
    GlobalUser,
    Membership,
    OrgAssignment,
    RoleAssignment,
    Workspace,
)
from baha_auth.src.policy.evaluator import ActorContext


def _effective_at(assignment: RoleAssignment, now: datetime) -> bool:
    start = assignment.valid_from
    end = assignment.valid_until
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return (
        assignment.status == "ACTIVE"
        and (start is None or start <= now)
        and (end is None or end > now)
    )


def load_actor(db: Session, workspace_id: str, membership_id: str) -> Optional[ActorContext]:
    """Nạp tác nhân từ membership thuộc workspace; bỏ qua các quyền đã hết hiệu lực."""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace or workspace.status != "ACTIVE":
        return None

    membership = db.query(Membership).filter(
        Membership.workspace_id == workspace_id,
        Membership.id == membership_id,
    ).first()
    if not membership or membership.status != "ACTIVE":
        return None
    user = db.query(GlobalUser).filter(GlobalUser.id == membership.user_id).first()
    if not user or user.status != "ACTIVE":
        return None

    now = datetime.now(timezone.utc)
    assignments = db.query(RoleAssignment).filter(
        RoleAssignment.workspace_id == workspace_id,
        RoleAssignment.membership_id == membership.id,
    ).all()
    roles = []
    for assignment in assignments:
        role = assignment.role
        if not role or role.status != "ACTIVE":
            continue
        if role.workspace_id not in (None, workspace_id) or not _effective_at(assignment, now):
            continue
        roles.append({
            "role_code": role.code,
            "role_status": role.status,
            "scope_type": assignment.scope_type,
            "scope_id": assignment.scope_id,
            "assignment_status": assignment.status,
            "valid_from": assignment.valid_from,
            "valid_until": assignment.valid_until,
            "policy_version": assignment.policy_version,
            "is_active": True,
        })

    org_assignments = db.query(OrgAssignment).filter(
        OrgAssignment.workspace_id == workspace_id,
        OrgAssignment.membership_id == membership.id,
    ).all()
    departments = []
    teams = []
    for assignment in org_assignments:
        unit = assignment.org_unit
        if not unit or unit.workspace_id != workspace_id or unit.status != "ACTIVE":
            continue
        if unit.type == "DEPARTMENT":
            departments.append(unit.id)
        elif unit.type == "TEAM":
            teams.append(unit.id)

    return ActorContext(
        user_id=user.id,
        workspace_id=workspace_id,
        membership_id=membership.id,
        membership_status=membership.status,
        roles=roles,
        department_ids=sorted(set(departments)),
        team_ids=sorted(set(teams)),
        user_status=user.status,
        workspace_status=workspace.status,
    )


def load_actor_for_user(db: Session, workspace_id: str, user_id: str) -> Optional[ActorContext]:
    membership = db.query(Membership).filter(
        Membership.workspace_id == workspace_id,
        Membership.user_id == user_id,
    ).first()
    if not membership:
        return None
    return load_actor(db, workspace_id, membership.id)

```
## baha_auth/src/services/role_service.py — SHA256 782554B67924E979572F8FDC4DC74B0B253144DD051923364F84CC6EF004EE98
```
"""Dịch vụ cấp, thu hồi vai trò và ủy quyền có giới hạn."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from baha_auth.src.models.entities import (
    Delegation,
    GlobalUser,
    Membership,
    OrgAssignment,
    OrgUnit,
    Role,
    RoleAssignment,
    Workspace,
)
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.policy.registry import registry
from baha_auth.src.services.danh_tinh_service import load_actor
from baha_auth.src.services.nhat_ky_kiem_toan import hash_resource_id, write_audit_event


def _aware(value: Optional[datetime]) -> bool:
    return value is None or (value.tzinfo is not None and value.utcoffset() is not None)


def _scope_resource(db: Session, workspace_id: str, scope_type: str, scope_id: Optional[str]) -> ResourceContext:
    if scope_type in ("WORKSPACE", "OWN"):
        if scope_id is not None:
            raise ValueError("INVALID_SCOPE_ID")
        return ResourceContext(workspace_id=workspace_id)
    if scope_type in ("DEPARTMENT", "TEAM") and scope_id:
        unit = db.query(OrgUnit).filter(
            OrgUnit.workspace_id == workspace_id,
            OrgUnit.id == scope_id,
            OrgUnit.status == "ACTIVE",
        ).first()
        expected_type = scope_type
        if not unit or unit.type != expected_type:
            raise ValueError("SCOPE_RESOURCE_NOT_FOUND")
        return ResourceContext(workspace_id=workspace_id, org_unit_id=unit.id)
    if scope_type == "PROJECT":
        raise ValueError("UNSUPPORTED_PROJECT_SCOPE")
    raise ValueError("INVALID_SCOPE")


def _effective_owner_assignments(db: Session, workspace_id: str, role_id: str, now: datetime) -> list[RoleAssignment]:
    rows = db.query(RoleAssignment, Membership, GlobalUser, Role).join(
        Membership,
        (RoleAssignment.workspace_id == Membership.workspace_id)
        & (RoleAssignment.membership_id == Membership.id),
    ).join(GlobalUser, GlobalUser.id == Membership.user_id).join(
        Role, Role.id == RoleAssignment.role_id,
    ).filter(
        RoleAssignment.workspace_id == workspace_id,
        RoleAssignment.role_id == role_id,
        RoleAssignment.scope_type == "WORKSPACE",
        RoleAssignment.status == "ACTIVE",
        Membership.status == "ACTIVE",
        GlobalUser.status == "ACTIVE",
        Role.status == "ACTIVE",
        (Role.workspace_id.is_(None) | (Role.workspace_id == workspace_id)),
    ).all()
    active = []
    for assignment, membership, user, role in rows:
        start = assignment.valid_from
        end = assignment.valid_until
        if start is not None and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if (start is None or start <= now) and (end is None or end > now):
            active.append(assignment)
    return active


def _grant_decision(
    actor: ActorContext, target_role_code: str, resource: ResourceContext
):
    eligible = [
        grant for grant in actor.roles
        if registry.can_grant_role(grant["role_code"], target_role_code)
    ]
    for grant in eligible:
        scoped_actor = ActorContext(
            user_id=actor.user_id,
            workspace_id=actor.workspace_id,
            membership_id=actor.membership_id,
            membership_status=actor.membership_status,
            roles=[grant],
            department_ids=actor.department_ids,
            team_ids=actor.team_ids,
            user_status=actor.user_status,
            workspace_status=actor.workspace_status,
        )
        decision = evaluate_permission(scoped_actor, "roles.assign", resource)
        if decision.allowed:
            return decision, True
    return None, bool(eligible)


def _revoke_decision(
    actor: ActorContext, target_role_code: str, resource: ResourceContext
):
    eligible = [
        grant for grant in actor.roles
        if registry.can_grant_role(grant["role_code"], target_role_code)
        or (
            target_role_code == "WORKSPACE_OWNER"
            and grant["role_code"] == "WORKSPACE_OWNER"
        )
    ]
    for grant in eligible:
        scoped_actor = ActorContext(
            user_id=actor.user_id,
            workspace_id=actor.workspace_id,
            membership_id=actor.membership_id,
            membership_status=actor.membership_status,
            roles=[grant],
            department_ids=actor.department_ids,
            team_ids=actor.team_ids,
            user_status=actor.user_status,
            workspace_status=actor.workspace_status,
        )
        decision = evaluate_permission(scoped_actor, "roles.assign", resource)
        if decision.allowed:
            return decision, True
    return None, bool(eligible)


def _authorized_role_grant(
    db: Session,
    workspace_id: str,
    grantor_membership_id: str,
    role_code: str,
    scope_type: str,
    scope_id: Optional[str],
):
    role = db.query(Role).filter(Role.code == role_code, Role.status == "ACTIVE").first()
    if not role or role.workspace_id not in (None, workspace_id):
        raise ValueError("UNKNOWN_OR_FOREIGN_ROLE")
    actor = load_actor(db, workspace_id, grantor_membership_id)
    if not actor:
        raise ValueError("GRANTOR_NOT_AUTHORIZED")
    resource = _scope_resource(db, workspace_id, scope_type, scope_id)
    decision, grantable = _grant_decision(actor, role_code, resource)
    if not grantable:
        raise ValueError("UNAUTHORIZED_ROLE_GRANT")
    if not decision:
        raise ValueError("GRANT_SCOPE_NOT_AUTHORIZED")
    return role, actor, resource, decision


class RoleService:
    @staticmethod
    def authorize_role_grant(
        db: Session,
        workspace_id: str,
        grantor_membership_id: str,
        role_code: str,
        scope_type: str = "WORKSPACE",
        scope_id: Optional[str] = None,
    ) -> None:
        """Xác thực quyền cấp vai trò và phạm vi trước khi tạo dữ liệu thành viên."""
        _authorized_role_grant(
            db, workspace_id, grantor_membership_id, role_code, scope_type, scope_id
        )

    @staticmethod
    def assign_role(
        db: Session,
        workspace_id: str,
        grantor_membership_id: str,
        grantee_membership_id: str,
        role_code: str,
        scope_type: str = "WORKSPACE",
        scope_id: Optional[str] = None,
        valid_until: Optional[datetime] = None,
        reason: Optional[str] = None,
    ) -> RoleAssignment:
        if grantor_membership_id == grantee_membership_id:
            raise ValueError("SELF_PRIVILEGE_ESCALATION_DENIED")
        if not _aware(valid_until):
            raise ValueError("TIMEZONE_REQUIRED")
        now = datetime.now(timezone.utc)
        if valid_until is not None and valid_until <= now:
            raise ValueError("ROLE_ASSIGNMENT_ALREADY_EXPIRED")

        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).with_for_update().first()
        grantor = db.query(Membership).filter(
            Membership.workspace_id == workspace_id, Membership.id == grantor_membership_id
        ).first()
        grantee = db.query(Membership).filter(
            Membership.workspace_id == workspace_id, Membership.id == grantee_membership_id
        ).first()
        if not workspace or workspace.status != "ACTIVE" or not grantor or not grantee:
            raise ValueError("MEMBERSHIP_NOT_FOUND_OR_INACTIVE")
        if grantor.status != "ACTIVE" or grantee.status != "ACTIVE":
            raise ValueError("MEMBERSHIP_NOT_FOUND_OR_INACTIVE")
        grantor_user = db.query(GlobalUser).filter(GlobalUser.id == grantor.user_id).first()
        grantee_user = db.query(GlobalUser).filter(GlobalUser.id == grantee.user_id).first()
        if not grantor_user or grantor_user.status != "ACTIVE" or not grantee_user or grantee_user.status != "ACTIVE":
            raise ValueError("USER_NOT_FOUND_OR_INACTIVE")

        role, grantor_actor, resource, decision = _authorized_role_grant(
            db, workspace_id, grantor_membership_id, role_code, scope_type, scope_id
        )

        if scope_type in ("DEPARTMENT", "TEAM"):
            belongs = db.query(OrgAssignment).filter(
                OrgAssignment.workspace_id == workspace_id,
                OrgAssignment.membership_id == grantee_membership_id,
                OrgAssignment.org_unit_id == scope_id,
            ).first()
            if not belongs:
                raise ValueError("GRANT_SCOPE_TARGET_NOT_MEMBER")
        assignment = RoleAssignment(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            membership_id=grantee_membership_id,
            role_id=role.id,
            scope_type=scope_type,
            scope_id=scope_id,
            valid_from=now,
            valid_until=valid_until,
            granted_by=grantor_membership_id,
            grant_reason=reason,
            status="ACTIVE",
            policy_version=decision.policy_version,
        )
        db.add(assignment)
        grantee.policy_revision += 1
        write_audit_event(
            db,
            workspace_id=workspace_id,
            actor_id=grantor_user.id,
            actor_type="USER",
            action_key="roles.assign",
            decision="ALLOW",
            reason="ROLE_ASSIGNMENT_CREATED",
            policy_version=decision.policy_version,
            resource_type="ROLE_ASSIGNMENT",
            resource_id=assignment.id,
            safe_metadata={
                "change": "ASSIGNED",
                "role_code": role.code,
                "scope_type": scope_type,
                "scope_ref": hash_resource_id(scope_id),
                "target_membership_ref": hash_resource_id(grantee_membership_id),
                "reason": reason,
            },
        )
        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def revoke_role(
        db: Session,
        workspace_id: str,
        actor_membership_id: str,
        assignment_id: str,
    ) -> bool:
        db.query(Workspace).filter(Workspace.id == workspace_id).with_for_update().first()
        assignment = db.query(RoleAssignment).filter(
            RoleAssignment.workspace_id == workspace_id,
            RoleAssignment.id == assignment_id,
        ).first()
        if not assignment:
            return False
        if assignment.status != "ACTIVE":
            return False

        actor = load_actor(db, workspace_id, actor_membership_id)
        if not actor:
            raise ValueError("ACTOR_NOT_AUTHORIZED")
        if not assignment.role:
            raise ValueError("UNAUTHORIZED_ROLE_REVOCATION")
        try:
            resource = _scope_resource(db, workspace_id, assignment.scope_type, assignment.scope_id)
        except ValueError:
            raise ValueError("UNAUTHORIZED_ROLE_REVOCATION")
        decision, grantable = _revoke_decision(actor, assignment.role.code, resource)
        if not grantable:
            raise ValueError("UNAUTHORIZED_ROLE_REVOCATION")
        if not decision or not decision.allowed:
            raise ValueError("UNAUTHORIZED_ROLE_REVOCATION")

        if assignment.role.code == "WORKSPACE_OWNER":
            now = datetime.now(timezone.utc)
            current_owners = _effective_owner_assignments(db, workspace_id, assignment.role_id, now)
            target_start = assignment.valid_from
            target_end = assignment.valid_until
            if target_start is not None and target_start.tzinfo is None:
                target_start = target_start.replace(tzinfo=timezone.utc)
            if target_end is not None and target_end.tzinfo is None:
                target_end = target_end.replace(tzinfo=timezone.utc)
            target_is_effective = (
                assignment in current_owners
                and (target_start is None or target_start <= now)
                and (target_end is None or target_end > now)
            )
            if target_is_effective and not any(owner.id != assignment.id for owner in current_owners):
                raise ValueError("LAST_OWNER_PROTECTION_VIOLATION")

        assignment.status = "REVOKED"
        if assignment.membership:
            assignment.membership.policy_revision += 1
        write_audit_event(
            db,
            workspace_id=workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key="roles.assign",
            decision="ALLOW",
            reason="ROLE_ASSIGNMENT_REVOKED",
            policy_version=decision.policy_version,
            resource_type="ROLE_ASSIGNMENT",
            resource_id=assignment.id,
            safe_metadata={
                "change": "REVOKED",
                "role_code": assignment.role.code if assignment.role else None,
                "scope_type": assignment.scope_type,
                "scope_ref": hash_resource_id(assignment.scope_id),
            },
        )
        db.commit()
        return True

    @staticmethod
    def delegate_permissions(
        db: Session,
        workspace_id: str,
        grantor_membership_id: str,
        grantee_membership_id: str,
        grant_spec_json: str,
        expires_at: datetime,
    ) -> Delegation:
        now = datetime.now(timezone.utc)
        if not _aware(expires_at) or expires_at <= now or expires_at > now + timedelta(hours=24):
            raise ValueError("INVALID_DELEGATION_EXPIRY")
        actor = load_actor(db, workspace_id, grantor_membership_id)
        grantee = db.query(Membership).filter(
            Membership.workspace_id == workspace_id,
            Membership.id == grantee_membership_id,
            Membership.status == "ACTIVE",
        ).first()
        if not actor or not grantee:
            raise ValueError("MEMBERSHIP_NOT_FOUND_OR_INACTIVE")
        decision = evaluate_permission(actor, "delegation.issue")
        if not decision.allowed:
            raise ValueError("UNAUTHORIZED_DELEGATION")
        try:
            spec = json.loads(grant_spec_json)
            actions = spec.get("allowed_actions", [])
        except (TypeError, json.JSONDecodeError):
            raise ValueError("INVALID_DELEGATION_SPEC")
        if not isinstance(actions, list) or not actions or any(
            not isinstance(action, str) or not evaluate_permission(actor, action).allowed for action in actions
        ):
            raise ValueError("DELEGATION_EXCEEDS_GRANTOR_SCOPE")

        delegation = Delegation(
            id=str(uuid.uuid4()), workspace_id=workspace_id,
            grantor_membership_id=grantor_membership_id,
            grantee_membership_id=grantee_membership_id,
            grant_spec_json=grant_spec_json,
            starts_at=now,
            expires_at=expires_at,
            status="ACTIVE",
        )
        db.add(delegation)
        write_audit_event(
            db, workspace_id=workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="delegation.issue", decision="ALLOW", reason="DELEGATION_CREATED",
            policy_version=decision.policy_version, resource_type="DELEGATION", resource_id=delegation.id,
            safe_metadata={"actions": actions, "target_membership_ref": hash_resource_id(grantee_membership_id)},
        )
        db.commit()
        db.refresh(delegation)
        return delegation

```
## baha_auth/src/services/tenant_service.py — SHA256 2E6880B5204BCBA985CB7299E8330733BBB447B41586850634BCC32080B8948D
```
"""Thao tác tài nguyên trong workspace với ngữ cảnh quyền do máy chủ phân giải."""

import hashlib
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from baha_auth.src.config import settings
from baha_auth.src.models.entities import BusinessResource
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event


class TenantService:
    @staticmethod
    def _context(resource: BusinessResource) -> ResourceContext:
        return ResourceContext(
            workspace_id=resource.workspace_id,
            resource_id=resource.id,
            resource_type=resource.resource_type,
            org_unit_id=resource.org_unit_id,
            owner_id=resource.owner_id,
            creator_id=resource.creator_id,
            artifact_version=resource.artifact_version,
            content_hash=resource.content_hash,
            project_id=resource.project_id,
            brand_id=resource.brand_id,
            channel_id=resource.channel_id,
        )

    @staticmethod
    def _audit(
        db: Session,
        actor: ActorContext,
        action: str,
        decision: str,
        reason: str,
        resource_id: Optional[str] = None,
    ) -> None:
        write_audit_event(
            db,
            workspace_id=actor.workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key=action,
            decision=decision,
            reason=reason,
            policy_version=settings.policy_version,
            resource_type="BUSINESS_RESOURCE",
            resource_id=resource_id,
        )
        db.commit()

    @staticmethod
    def get_resource(db: Session, actor: ActorContext, resource_id: str) -> Optional[BusinessResource]:
        resource = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.id == resource_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if resource is None:
            TenantService._audit(db, actor, "ideas.read", "DENY", "RESOURCE_NOT_FOUND_OR_CROSS_TENANT", resource_id)
            return None
        decision = evaluate_permission(actor, "ideas.read", TenantService._context(resource))
        if not decision.allowed:
            TenantService._audit(db, actor, "ideas.read", "DENY", decision.reason_code, resource_id)
            return None
        return resource

    @staticmethod
    def list_resources(db: Session, actor: ActorContext) -> List[BusinessResource]:
        resources = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.is_quarantined.is_(False),
        ).all()
        return [
            resource for resource in resources
            if evaluate_permission(actor, "ideas.read", TenantService._context(resource)).allowed
        ]

    @staticmethod
    def create_resource(
        db: Session,
        actor: ActorContext,
        title: str,
        attempted_workspace_id: Optional[str] = None,
        search_text: Optional[str] = None,
    ) -> BusinessResource:
        del attempted_workspace_id
        context = ResourceContext(workspace_id=actor.workspace_id)
        decision = evaluate_permission(actor, "ideas.create", context)
        if not decision.allowed:
            TenantService._audit(db, actor, "ideas.create", "DENY", decision.reason_code)
            raise ValueError("RESOURCE_CREATE_NOT_AUTHORIZED")
        resource = BusinessResource(
            id=str(uuid.uuid4()),
            workspace_id=actor.workspace_id,
            owner_id=actor.user_id,
            creator_id=actor.user_id,
            title=title,
            search_text=search_text,
            content_hash=hashlib.sha256((title + (search_text or "")).encode("utf-8")).hexdigest(),
            artifact_version=1,
            is_quarantined=False,
        )
        db.add(resource)
        write_audit_event(
            db,
            workspace_id=actor.workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key="ideas.create",
            decision="ALLOW",
            reason="RESOURCE_CREATED",
            policy_version=decision.policy_version,
            resource_type="BUSINESS_RESOURCE",
            resource_id=resource.id,
        )
        db.commit()
        db.refresh(resource)
        return resource

    @staticmethod
    def search_resources(db: Session, actor: ActorContext, query_text: str) -> List[BusinessResource]:
        resources = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.search_text.contains(query_text),
            BusinessResource.is_quarantined.is_(False),
        ).all()
        return [
            resource for resource in resources
            if evaluate_permission(actor, "ideas.read", TenantService._context(resource)).allowed
        ]

    @staticmethod
    def get_asset_download_url(db: Session, actor: ActorContext, resource_id: str) -> Optional[str]:
        resource = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.id == resource_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if resource is None:
            TenantService._audit(db, actor, "media.read", "DENY", "RESOURCE_NOT_FOUND_OR_CROSS_TENANT", resource_id)
            return None
        decision = evaluate_permission(actor, "media.read", TenantService._context(resource))
        if not decision.allowed:
            TenantService._audit(db, actor, "media.read", "DENY", decision.reason_code, resource_id)
            return None
        # Không có nhà cung cấp ký URL được cấu hình; tuyệt đối không tự tạo URL dùng được.
        return None

    @staticmethod
    def quarantine_orphaned_resource(
        db: Session,
        resource_id: str,
        *,
        system_maintenance: bool = False,
    ) -> Optional[BusinessResource]:
        if not system_maintenance:
            raise ValueError("SYSTEM_MAINTENANCE_AUTHORIZATION_REQUIRED")
        resource = db.query(BusinessResource).filter(
            BusinessResource.id == resource_id,
            BusinessResource.workspace_id.is_(None),
        ).first()
        if resource:
            resource.is_quarantined = True
            write_audit_event(
                db, workspace_id=None, actor_id=None, actor_type="SYSTEM", action_key="resource.quarantine",
                decision="ALLOW", reason="ORPHAN_RESOURCE_QUARANTINED", policy_version=settings.policy_version,
                resource_type="BUSINESS_RESOURCE", resource_id=resource.id,
            )
            db.commit()
            db.refresh(resource)
        return resource

    @staticmethod
    def aggregate_view_counts(db: Session, actor: ActorContext) -> int:
        return sum(resource.view_count for resource in TenantService.list_resources(db, actor))

    @staticmethod
    def update_resource(db: Session, actor: ActorContext, resource_id: str, new_title: str) -> bool:
        resource = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.id == resource_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if resource is None:
            TenantService._audit(db, actor, "ideas.edit", "DENY", "RESOURCE_NOT_FOUND_OR_CROSS_TENANT", resource_id)
            return False
        decision = evaluate_permission(actor, "ideas.edit", TenantService._context(resource))
        if not decision.allowed:
            TenantService._audit(db, actor, "ideas.edit", "DENY", decision.reason_code, resource_id)
            return False
        resource.title = new_title
        resource.artifact_version += 1
        resource.content_hash = hashlib.sha256(
            (new_title + (resource.search_text or "")).encode("utf-8")
        ).hexdigest()
        write_audit_event(
            db,
            workspace_id=actor.workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key="ideas.edit",
            decision="ALLOW",
            reason="RESOURCE_UPDATED",
            policy_version=decision.policy_version,
            resource_type="BUSINESS_RESOURCE",
            resource_id=resource.id,
            safe_metadata={"artifact_version": resource.artifact_version},
        )
        db.commit()
        return True

```
## baha_auth/src/services/org_service.py — SHA256 EBEFC7BE8742937C2FD579BC121A1D5C3E94D0772F0CA52B3B7F56C31B290E7F
```
"""Thao tác đơn vị tổ chức và quan hệ báo cáo có kiểm tra workspace, phạm vi."""

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from baha_auth.src.config import settings
from baha_auth.src.models.entities import Membership, OrgAssignment, OrgUnit, ReportingLine
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event


class OrgService:
    @staticmethod
    def create_org_unit(
        db: Session,
        workspace_id: str,
        name: str,
        unit_type: str = "DEPARTMENT",
        parent_id: Optional[str] = None,
        actor: Optional[ActorContext] = None,
    ) -> OrgUnit:
        if actor is None or actor.workspace_id != workspace_id:
            raise ValueError("ACTOR_REQUIRED")
        parent = None
        if parent_id:
            parent = db.query(OrgUnit).filter(
                OrgUnit.workspace_id == workspace_id,
                OrgUnit.id == parent_id,
                OrgUnit.status == "ACTIVE",
            ).first()
            if not parent:
                raise ValueError("PARENT_UNIT_NOT_FOUND_OR_CROSS_TENANT")
        resource = ResourceContext(workspace_id=workspace_id, org_unit_id=parent.id if parent else None)
        decision = evaluate_permission(actor, "org.manage", resource)
        if not decision.allowed:
            write_audit_event(
                db, workspace_id=workspace_id, actor_id=actor.user_id, actor_type="USER",
                action_key="org.manage", decision="DENY", reason=decision.reason_code,
                policy_version=decision.policy_version, resource_type="ORG_UNIT", resource_id=parent_id,
            )
            db.commit()
            raise ValueError("UNAUTHORIZED_ORG_SCOPE")

        unit = OrgUnit(
            id=str(uuid.uuid4()), workspace_id=workspace_id, parent_id=parent_id, type=unit_type, name=name
        )
        db.add(unit)
        write_audit_event(
            db, workspace_id=workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="org.manage", decision="ALLOW", reason="ORG_UNIT_CREATED",
            policy_version=decision.policy_version, resource_type="ORG_UNIT", resource_id=unit.id,
            safe_metadata={"unit_type": unit_type, "parent_id": parent_id},
        )
        db.commit()
        db.refresh(unit)
        return unit

    @staticmethod
    def set_unit_parent(
        db: Session,
        unit_id: str,
        new_parent_id: str,
        actor: Optional[ActorContext] = None,
    ) -> bool:
        unit = db.query(OrgUnit).filter(OrgUnit.id == unit_id).first()
        parent = db.query(OrgUnit).filter(OrgUnit.id == new_parent_id).first()
        if not unit or not parent or unit.workspace_id != parent.workspace_id:
            return False
        if actor is None or actor.workspace_id != unit.workspace_id:
            raise ValueError("ACTOR_REQUIRED")
        decision = evaluate_permission(
            actor, "org.manage", ResourceContext(workspace_id=unit.workspace_id, org_unit_id=unit.id)
        )
        if not decision.allowed:
            return False
        if unit_id == new_parent_id:
            return False

        current_id = new_parent_id
        visited = set()
        while current_id:
            if current_id in visited or current_id == unit_id:
                return False
            visited.add(current_id)
            current = db.query(OrgUnit).filter(
                OrgUnit.workspace_id == unit.workspace_id, OrgUnit.id == current_id
            ).first()
            current_id = current.parent_id if current else None

        unit.parent_id = new_parent_id
        write_audit_event(
            db, workspace_id=unit.workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="org.manage", decision="ALLOW", reason="ORG_PARENT_UPDATED",
            policy_version=decision.policy_version, resource_type="ORG_UNIT", resource_id=unit.id,
            safe_metadata={"parent_id": new_parent_id},
        )
        db.commit()
        return True

    @staticmethod
    def assign_reporting_line(
        db: Session,
        workspace_id: str,
        manager_membership_id: str,
        report_membership_id: str,
        actor: Optional[ActorContext] = None,
        org_unit_id: Optional[str] = None,
    ) -> bool:
        if actor is None or actor.workspace_id != workspace_id:
            raise ValueError("ACTOR_REQUIRED")
        manager = db.query(Membership).filter(
            Membership.workspace_id == workspace_id, Membership.id == manager_membership_id
        ).first()
        report = db.query(Membership).filter(
            Membership.workspace_id == workspace_id, Membership.id == report_membership_id
        ).first()
        if not manager or not report or manager.status != "ACTIVE" or report.status != "ACTIVE":
            return False
        if manager_membership_id == report_membership_id:
            return False

        scope_unit = None
        if org_unit_id:
            scope_unit = db.query(OrgUnit).filter(
                OrgUnit.workspace_id == workspace_id, OrgUnit.id == org_unit_id
            ).first()
            if not scope_unit:
                return False
        else:
            assigned = db.query(OrgAssignment).filter(
                OrgAssignment.workspace_id == workspace_id,
                OrgAssignment.membership_id == report_membership_id,
            ).first()
            scope_unit = assigned.org_unit if assigned else None
        resource = ResourceContext(workspace_id=workspace_id, org_unit_id=scope_unit.id if scope_unit else None)
        decision = evaluate_permission(actor, "org.manage", resource)
        if not decision.allowed:
            return False

        current = manager_membership_id
        visited = set()
        while current:
            if current in visited or current == report_membership_id:
                return False
            visited.add(current)
            line = db.query(ReportingLine).filter(
                ReportingLine.workspace_id == workspace_id,
                ReportingLine.report_membership_id == current,
            ).first()
            current = line.manager_membership_id if line else None

        db.add(ReportingLine(
            id=str(uuid.uuid4()), workspace_id=workspace_id,
            manager_membership_id=manager_membership_id, report_membership_id=report_membership_id,
            org_unit_id=scope_unit.id if scope_unit else None,
        ))
        write_audit_event(
            db, workspace_id=workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="org.manage", decision="ALLOW", reason="REPORTING_LINE_CREATED",
            policy_version=decision.policy_version, resource_type="REPORTING_LINE",
            resource_id=report_membership_id,
            safe_metadata={"manager_membership_id": manager_membership_id},
        )
        db.commit()
        return True

    @staticmethod
    def get_department_roster(
        db: Session,
        actor: ActorContext,
        target_dept_id: str,
    ) -> Optional[List[Membership]]:
        unit = db.query(OrgUnit).filter(
            OrgUnit.workspace_id == actor.workspace_id,
            OrgUnit.id == target_dept_id,
            OrgUnit.status == "ACTIVE",
        ).first()
        if not unit or unit.type not in ("DEPARTMENT", "TEAM"):
            write_audit_event(
                db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
                action_key="org.read", decision="DENY", reason="ORG_UNIT_NOT_FOUND",
                policy_version=settings.policy_version, resource_type="ORG_UNIT", resource_id=target_dept_id,
            )
            db.commit()
            return None
        decision = evaluate_permission(
            actor, "org.read", ResourceContext(workspace_id=unit.workspace_id, org_unit_id=unit.id)
        )
        if not decision.allowed:
            write_audit_event(
                db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
                action_key="org.read", decision="DENY", reason=decision.reason_code,
                policy_version=decision.policy_version, resource_type="ORG_UNIT", resource_id=unit.id,
            )
            db.commit()
            return None
        assignments = db.query(OrgAssignment).filter(
            OrgAssignment.workspace_id == actor.workspace_id,
            OrgAssignment.org_unit_id == unit.id,
        ).all()
        members = [a.membership for a in assignments if a.membership and a.membership.status == "ACTIVE"]
        write_audit_event(
            db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="org.read", decision="ALLOW", reason="ORG_ROSTER_READ",
            policy_version=decision.policy_version, resource_type="ORG_UNIT", resource_id=unit.id,
            safe_metadata={"member_count": len(members)},
        )
        db.commit()
        return members

```
## baha_auth/src/services/nhat_ky_kiem_toan.py — SHA256 565E4A8BDD5D6F6B2AA222D6FE918E3732184991B55D65EA517BE1FC446112D4
```
"""Ghi sự kiện kiểm toán phân quyền dùng chung theo chế độ chỉ ghi nối tiếp."""

import hashlib
import json
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from baha_auth.src.models.entities import AuthorizationAuditEvent


def hash_resource_id(resource_id: Optional[str]) -> Optional[str]:
    if resource_id is None:
        return None
    return hashlib.sha256(resource_id.encode("utf-8")).hexdigest()


def _safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        output = {}
        for key, item in value.items():
            safe_key = str(key)[:80]
            if any(secret_word in safe_key.lower() for secret_word in ("token", "secret", "cookie", "password", "credential")):
                continue
            output[safe_key] = _safe_value(item)
        return output
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value[:30]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value[:500] if isinstance(value, str) else value
    return str(value)[:500]


def write_audit_event(
    db: Session,
    *,
    workspace_id: Optional[str],
    actor_id: Optional[str],
    actor_type: str,
    action_key: str,
    decision: str,
    reason: str,
    policy_version: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None,
    safe_metadata: Optional[Mapping[str, Any]] = None,
) -> AuthorizationAuditEvent:
    """Thêm sự kiện đã làm sạch vào giao dịch của bên gọi; hàm này không tự commit."""
    if decision not in {"ALLOW", "DENY"}:
        raise ValueError("INVALID_AUDIT_DECISION")
    metadata = _safe_value(safe_metadata or {})
    metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(metadata_json) > 2_000:
        metadata_json = json.dumps({"truncated": True}, separators=(",", ":"))

    event = AuthorizationAuditEvent(
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action_key=action_key[:100],
        resource_type=resource_type[:100] if resource_type else None,
        resource_id_hash=hash_resource_id(resource_id),
        decision=decision,
        internal_reason=reason[:255],
        policy_version=policy_version[:50],
        request_id=request_id[:100] if request_id else None,
        safe_metadata_json=metadata_json,
    )
    db.add(event)
    db.flush()
    return event

```
## baha_auth/src/api/deps.py — SHA256 A765005F196D514E1931BF023971B64B520BB3BA564ACA367065919CDC0B3F20
```
"""Dependency xác minh bearer và thực thi phân quyền cho FastAPI."""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from baha_auth.src.config import settings
from baha_auth.src.database import get_db, set_tenant_context
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.services.danh_tinh_service import load_actor_for_user
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event
from baha_auth.src.xac_minh_danh_tinh import InvalidBearerToken, verify_bearer_token


_bearer = HTTPBearer(auto_error=False)


def get_current_actor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    db: Session = Depends(get_db),
) -> ActorContext:
    """Xác minh bearer trước, rồi nạp membership đang hoạt động trong tenant đã chọn."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "BEARER_TOKEN_REQUIRED", "message": "Yêu cầu bearer token hợp lệ."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not x_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "WORKSPACE_REQUIRED", "message": "Yêu cầu header X-Workspace-Id."},
        )
    if not all((settings.jwt_secret_key, settings.jwt_issuer, settings.jwt_audience)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "IDENTITY_PROVIDER_NOT_CONFIGURED", "message": "Chưa cấu hình nhà cung cấp danh tính để xác minh bearer."},
        )

    try:
        identity = verify_bearer_token(
            credentials.credentials,
            secret=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except InvalidBearerToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": str(exc), "message": "Bearer token không hợp lệ."},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    set_tenant_context(x_workspace_id, db)
    actor = load_actor_for_user(db, x_workspace_id, identity.user_id)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACTIVE_MEMBERSHIP_REQUIRED", "message": "Người dùng chưa có membership đang hoạt động trong workspace này."},
        )
    return actor


def require_action(action_key: str):
    """Tạo dependency kiểm tra action ở phạm vi workspace trước khi chạy route."""
    def permission_checker(
        request: Request,
        actor: ActorContext = Depends(get_current_actor),
        db: Session = Depends(get_db),
    ) -> ActorContext:
        decision = evaluate_permission(actor, action_key)
        write_audit_event(
            db,
            workspace_id=actor.workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key=action_key,
            decision=decision.decision,
            reason=decision.internal_reason,
            policy_version=decision.policy_version,
            request_id=request.headers.get("X-Request-Id"),
        )
        db.commit()
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": decision.reason_code,
                    "message": "Bạn không có quyền thực hiện action này.",
                    "action_key": action_key,
                    "policy_version": decision.policy_version,
                },
            )
        return actor
    return permission_checker

```
## baha_auth/src/api/role_router.py — SHA256 53D761229546287847E09178DBF76E7E9351C26630FA71B30C2A44B93E5CDC72
```
# Bộ định tuyến API cho vai trò, phân quyền và ủy quyền (pha A04).
import uuid
import json
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from baha_auth.src.config import settings
from baha_auth.src.database import get_db
from baha_auth.src.api.deps import get_current_actor, require_action, ActorContext
from baha_auth.src.models.entities import (
    Role, Permission, RoleAssignment, Delegation, Membership, GlobalUser, OrgAssignment, OrgUnit,
)
from baha_auth.src.schemas.contracts import (
    RoleOut, PermissionOut, RoleAssignmentRequest, RoleAssignmentOut,
    DelegationRequest, DelegationOut, MemberInviteRequest, MemberOut
)
from baha_auth.src.services.role_service import RoleService
from baha_auth.src.policy.registry import registry
from baha_auth.src.policy.evaluator import ResourceContext, evaluate_permission
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event

router = APIRouter(prefix="/authz/v1", tags=["Vai trò và quyền hạn"])

@router.get("/roles", response_model=List[RoleOut])
def list_roles(
    actor: ActorContext = Depends(require_action("roles.read")),
    db: Session = Depends(get_db)
):
    # Lấy cả vai trò mẫu và vai trò riêng của workspace.
    roles = db.query(Role).filter(
        (Role.workspace_id == actor.workspace_id) | (Role.is_template == True)
    , Role.status == "ACTIVE").all()
    return roles

@router.get("/permissions", response_model=List[PermissionOut])
def list_permissions(
    actor: ActorContext = Depends(require_action("roles.read")),
    db: Session = Depends(get_db)
):
    perms = db.query(Permission).order_by(Permission.action_key).all()
    if not perms:
        # Neu chua nạp DB, tra tu registry
        out = []
        for p in registry._permissions.values():
            out.append(PermissionOut(
                id=str(uuid.uuid4()),
                action_key=p.get("action") or p.get("action_key", ""),
                risk_tier=p.get("risk_tier", "LOW"),
                is_immutable=True,
                description=p.get("constraints")
            ))
        return out
    return perms

@router.post("/members/invite", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def invite_member(
    payload: MemberInviteRequest,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db)
):
    target_org = None
    if payload.scope_type in ("DEPARTMENT", "TEAM"):
        target_org = db.query(OrgUnit).filter(
            OrgUnit.workspace_id == actor.workspace_id,
            OrgUnit.id == payload.scope_id,
            OrgUnit.type == payload.scope_type,
            OrgUnit.status == "ACTIVE",
        ).first()
        if not target_org:
            write_audit_event(
                db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
                action_key="members.invite", decision="DENY", reason="INVITE_SCOPE_NOT_FOUND",
                policy_version=settings.policy_version, resource_type="ORG_UNIT", resource_id=payload.scope_id,
                safe_metadata={"scope_type": payload.scope_type},
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="INVITE_SCOPE_NOT_FOUND")
        target_resource = ResourceContext(workspace_id=actor.workspace_id, org_unit_id=target_org.id)
    elif payload.scope_type == "WORKSPACE" and payload.scope_id is None:
        target_resource = ResourceContext(workspace_id=actor.workspace_id)
    else:
        write_audit_event(
            db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="members.invite", decision="DENY", reason="INVITE_SCOPE_UNSUPPORTED",
            policy_version=settings.policy_version, resource_type="ORG_UNIT", resource_id=payload.scope_id,
            safe_metadata={"scope_type": payload.scope_type},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="INVITE_SCOPE_UNSUPPORTED")

    decision = evaluate_permission(actor, "members.invite", target_resource)
    if not decision.allowed:
        write_audit_event(
            db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="members.invite", decision="DENY", reason=decision.reason_code,
            policy_version=decision.policy_version, resource_type="ORG_UNIT" if target_org else None,
            resource_id=target_org.id if target_org else None,
            request_id=None,
            safe_metadata={"scope_type": payload.scope_type},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
            "error_code": decision.reason_code, "message": "Bạn không được phép mời thành viên vào phạm vi này."
        })

    existing_user = db.query(GlobalUser).filter(GlobalUser.email == payload.email).first()
    if existing_user and db.query(Membership).filter(
        Membership.workspace_id == actor.workspace_id,
        Membership.user_id == existing_user.id,
    ).first():
        write_audit_event(
            db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="members.invite", decision="DENY", reason="USER_ALREADY_MEMBER",
            policy_version=decision.policy_version,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="USER_ALREADY_MEMBER")

    try:
        RoleService.authorize_role_grant(
            db,
            actor.workspace_id,
            grantor_membership_id=actor.membership_id,
            role_code=payload.initial_role_code,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
        )
    except ValueError as exc:
        write_audit_event(
            db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="roles.assign", decision="DENY", reason=str(exc),
            policy_version=decision.policy_version,
            resource_type="ORG_UNIT" if target_org else None,
            resource_id=target_org.id if target_org else None,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    write_audit_event(
        db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
        action_key="members.invite", decision="ALLOW", reason="INVITATION_AUTHORIZED",
        policy_version=decision.policy_version,
        resource_type="ORG_UNIT" if target_org else None,
        resource_id=target_org.id if target_org else None,
        safe_metadata={"scope_type": payload.scope_type, "initial_role_code": payload.initial_role_code},
    )

    user = existing_user
    if not user:
        user = GlobalUser(
            id=str(uuid.uuid4()),
            email=payload.email,
            full_name=payload.full_name,
            status="ACTIVE"
        )
        db.add(user)
        db.flush()

    # Kiem tra membership
    mem = db.query(Membership).filter(
        Membership.workspace_id == actor.workspace_id,
        Membership.user_id == user.id
    ).first()
    if mem:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="USER_ALREADY_MEMBER")

    mem = Membership(
        id=str(uuid.uuid4()),
        workspace_id=actor.workspace_id,
        user_id=user.id,
        status="ACTIVE"
    )
    db.add(mem)
    db.flush()

    if target_org:
        db.add(OrgAssignment(
            workspace_id=actor.workspace_id,
            membership_id=mem.id,
            org_unit_id=target_org.id,
        ))
        db.flush()

    try:
        RoleService.assign_role(
            db,
            actor.workspace_id,
            grantor_membership_id=actor.membership_id,
            grantee_membership_id=mem.id,
            role_code=payload.initial_role_code,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id
        )
    except ValueError as exc:
        db.rollback()
        write_audit_event(
            db, workspace_id=actor.workspace_id, actor_id=actor.user_id, actor_type="USER",
            action_key="members.invite", decision="DENY", reason="INVITATION_COMMIT_FAILED",
            policy_version=decision.policy_version, resource_type="ORG_UNIT" if target_org else None,
            resource_id=target_org.id if target_org else None,
            safe_metadata={"error_code": str(exc)},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    db.commit()
    db.refresh(mem)
    return MemberOut(
        id=mem.id,
        workspace_id=mem.workspace_id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        status=mem.status,
        joined_at=mem.joined_at,
        roles=[payload.initial_role_code]
    )

@router.post("/assignments", response_model=RoleAssignmentOut, status_code=status.HTTP_201_CREATED)
def assign_role(
    payload: RoleAssignmentRequest,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db)
):
    try:
        assignment = RoleService.assign_role(
            db,
            actor.workspace_id,
            grantor_membership_id=actor.membership_id,
            grantee_membership_id=payload.grantee_membership_id,
            role_code=payload.role_code,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            valid_until=payload.valid_until,
            reason=payload.reason
        )
        return RoleAssignmentOut(
            id=assignment.id,
            workspace_id=assignment.workspace_id,
            membership_id=assignment.membership_id,
            role_code=payload.role_code,
            scope_type=assignment.scope_type,
            scope_id=assignment.scope_id,
            valid_from=assignment.valid_from,
            valid_until=assignment.valid_until,
            status=assignment.status
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

@router.delete("/assignments/{assignment_id}", response_model=dict)
def revoke_role(
    assignment_id: str,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db)
):
    try:
        success = RoleService.revoke_role(
            db,
            actor.workspace_id,
            actor_membership_id=actor.membership_id,
            assignment_id=assignment_id
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ASSIGNMENT_NOT_FOUND")
        return {"status": "success", "message": "Đã thu hồi vai trò thành công."}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

@router.post("/delegations", response_model=DelegationOut, status_code=status.HTTP_201_CREATED)
def issue_delegation(
    payload: DelegationRequest,
    actor: ActorContext = Depends(require_action("delegation.issue")),
    db: Session = Depends(get_db)
):
    delegation = RoleService.delegate_permissions(
        db,
        actor.workspace_id,
        grantor_membership_id=actor.membership_id,
        grantee_membership_id=payload.grantee_membership_id,
        grant_spec_json=json.dumps({"allowed_actions": payload.allowed_actions, "reason": payload.reason}),
        expires_at=payload.expires_at
    )
    return DelegationOut(
        id=delegation.id,
        workspace_id=delegation.workspace_id,
        grantor_membership_id=delegation.grantor_membership_id,
        grantee_membership_id=delegation.grantee_membership_id,
        allowed_actions=payload.allowed_actions,
        starts_at=delegation.starts_at,
        expires_at=delegation.expires_at,
        status=delegation.status
    )

```
## baha_auth/src/api/org_router.py — SHA256 9A54BEB625888FB9E41FE0A53933404078BB7F475FB7161C38E647E108D2AB53
```
# Bộ định tuyến API cho sơ đồ tổ chức và phòng ban (pha A02).
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from baha_auth.src.database import get_db
from baha_auth.src.api.deps import get_current_actor, require_action, ActorContext
from baha_auth.src.models.entities import OrgUnit, ReportingLine
from baha_auth.src.schemas.contracts import OrgUnitCreate, OrgUnitOut, ReportingLineCreate, ReportingLineOut, MemberOut
from baha_auth.src.policy.evaluator import ResourceContext, evaluate_permission
from baha_auth.src.services.danh_tinh_service import load_actor
from baha_auth.src.services.org_service import OrgService

router = APIRouter(prefix="/authz/v1/org", tags=["Cơ cấu tổ chức"])

@router.get("/units", response_model=List[OrgUnitOut])
def list_org_units(
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db)
):
    units = db.query(OrgUnit).filter(
        OrgUnit.workspace_id == actor.workspace_id,
        OrgUnit.status == "ACTIVE",
    ).all()
    return [
        unit for unit in units
        if evaluate_permission(
            actor, "org.read", ResourceContext(workspace_id=unit.workspace_id, org_unit_id=unit.id)
        ).allowed
    ]

@router.post("/units", response_model=OrgUnitOut, status_code=status.HTTP_201_CREATED)
def create_org_unit(
    payload: OrgUnitCreate,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db)
):
    try:
        unit = OrgService.create_org_unit(
            db,
            actor.workspace_id,
            name=payload.name,
            unit_type=payload.type,
            parent_id=payload.parent_id,
            actor=actor,
        )
        return unit
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

@router.post("/reporting-lines", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_reporting_line(
    payload: ReportingLineCreate,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db)
):
    success = OrgService.assign_reporting_line(
        db,
        actor.workspace_id,
        manager_membership_id=payload.manager_membership_id,
        report_membership_id=payload.report_membership_id,
        actor=actor,
        org_unit_id=payload.org_unit_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "CYCLE_OR_CROSS_TENANT_DETECTED", "message": "Quan hệ báo cáo không hợp lệ hoặc vượt ranh giới workspace."},
        )
    return {"status": "success", "message": "Đã thiết lập quan hệ báo cáo."}

@router.get("/departments/{dept_id}/roster", response_model=List[MemberOut])
def get_department_roster(
    dept_id: str,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db)
):
    members = OrgService.get_department_roster(db, actor, dept_id)
    if members is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="UNAUTHORIZED_DEPARTMENT_ROSTER: Bạn không được phép xem thành viên của phòng ban khác."
        )
    
    out = []
    for m in members:
        member_actor = load_actor(db, m.workspace_id, m.id)
        out.append(MemberOut(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            email=m.user.email if m.user else "",
            full_name=m.user.full_name if m.user else None,
            status=m.status,
            joined_at=m.joined_at,
            roles=[item["role_code"] for item in member_actor.roles] if member_actor else []
        ))
    return out

```
## baha_auth/src/api/evaluate_router.py — SHA256 A8C6C888667ACA9E81F11DDD7DD45291D4F542E997BC863FD1B05B30193E794D
```
"""Định tuyến API đánh giá quyền dựa trên tài nguyên do máy chủ phân giải."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from baha_auth.src.api.deps import ActorContext, get_current_actor
from baha_auth.src.database import get_db
from baha_auth.src.models.entities import BusinessResource
from baha_auth.src.config import settings
from baha_auth.src.policy.evaluator import AuthorizationDecision, ResourceContext, evaluate_permission
from baha_auth.src.schemas.contracts import EvaluateRequest, EvaluateResponse
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event


router = APIRouter(prefix="/authz/v1", tags=["Authorization Decision Engine"])


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_access(
    payload: EvaluateRequest,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
    request: Request = None,
):
    resource_ctx = None
    resource_type = None
    if payload.resource_id:
        resource = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.id == payload.resource_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if resource is None:
            decision = AuthorizationDecision(
                allowed=False,
                decision="DENY",
                reason_code="RESOURCE_NOT_FOUND",
                internal_reason="Tài nguyên không tồn tại trong workspace đang hoạt động.",
                policy_version=settings.policy_version,
            )
        else:
            resource_type = resource.resource_type
            resource_ctx = ResourceContext(
                workspace_id=resource.workspace_id,
                resource_id=resource.id,
                resource_type=resource.resource_type,
                org_unit_id=resource.org_unit_id,
                owner_id=resource.owner_id,
                creator_id=resource.creator_id,
                artifact_version=resource.artifact_version,
                content_hash=resource.content_hash,
                project_id=resource.project_id,
                brand_id=resource.brand_id,
                channel_id=resource.channel_id,
            )
            decision = evaluate_permission(actor, payload.action_key, resource_ctx)
    else:
        decision = evaluate_permission(actor, payload.action_key)

    write_audit_event(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        actor_type="USER",
        action_key=payload.action_key,
        decision=decision.decision,
        reason=decision.internal_reason,
        policy_version=decision.policy_version,
        resource_type=resource_type,
        resource_id=payload.resource_id,
        request_id=request.headers.get("X-Request-Id") if request else None,
    )
    db.commit()
    return EvaluateResponse(
        allowed=decision.allowed,
        decision=decision.decision,
        reason_code=decision.reason_code,
        internal_reason=decision.internal_reason,
        policy_version=decision.policy_version,
    )

```
## baha_auth/src/policy/registry.py — SHA256 3A1B7CD6D9557E5924409D80241A7682852CC5F0D0030D0378FD00C3381E1365
```
# Danh mục quản lý 58 action key và 15 vai trò khởi tạo.
import os
import json
import csv
from typing import Dict, List, Optional, Set

REGISTRY_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "09_kiem_thu_quyen", "PERMISSION_REGISTRY.json"
))

_SCOPE_CODES = {
    "W": "WORKSPACE",
    "B": "BRAND",
    "D": "DEPARTMENT",
    "T": "TEAM",
    "P": "PROJECT",
    "H": "CHANNEL",
    "S": "OWN",
    "R": "CLIENT_REVIEWED",
    "A": "OBJECT",
    "O": "PLATFORM",
}

MATRIX_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "09_kiem_thu_quyen", "ROLE_PERMISSION_MATRIX.csv"
))

# Ánh xạ vai trò được phép cấp theo ROLE_GRANT_RULES.md.
DEFAULT_GRANTABLE_ROLES: Dict[str, List[str]] = {
    "WORKSPACE_OWNER": [
        "EXECUTIVE", "DEPARTMENT_MANAGER", "TEAM_LEAD", "RESEARCHER",
        "STRATEGIST", "VIDEO_EDITOR", "PUBLISHER", "ANALYST", "FINANCE_MANAGER",
        "CLIENT_APPROVER", "AUDITOR", "GUEST"
    ],
    "EXECUTIVE": [
        "TEAM_LEAD", "RESEARCHER", "STRATEGIST", "VIDEO_EDITOR", "ANALYST", "GUEST"
    ],
    "DEPARTMENT_MANAGER": [
        "TEAM_LEAD", "RESEARCHER", "STRATEGIST", "VIDEO_EDITOR", "ANALYST", "GUEST"
    ],
    "TEAM_LEAD": [
        "RESEARCHER", "STRATEGIST", "VIDEO_EDITOR", "GUEST"
    ],
    "RESEARCHER": [],
    "STRATEGIST": [],
    "VIDEO_EDITOR": [],
    "PUBLISHER": [],
    "ANALYST": [],
    "FINANCE_MANAGER": [],
    "CLIENT_APPROVER": [],
    "AUDITOR": [],
    "GUEST": [],
    "PLATFORM_OPS": [],
    "SERVICE_PRINCIPAL": []
}

class PolicyRegistry:
    def __init__(self):
        self._permissions: Dict[str, dict] = {}
        self._role_matrix: Dict[str, Dict[str, str]] = {} # role_code -> {action_key: scope}
        self.load()

    def load(self):
        # 1. Load PERMISSION_REGISTRY.json
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                perms = data.get("permissions", [])
                for p in perms:
                    act = p.get("action") or p.get("action_key")
                    if act:
                        self._permissions[act] = p

        # 2. Load ROLE_PERMISSION_MATRIX.csv
        if os.path.exists(MATRIX_FILE):
            with open(MATRIX_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    action_key = row.get("permission") or row.get("action_key")
                    if not action_key:
                        continue
                    for role_col, scope_val in row.items():
                        if role_col in ["permission", "action_key", "risk", "risk_tier", "notes", "immutable_constraints"]:
                            continue
                        if role_col not in self._role_matrix:
                            self._role_matrix[role_col] = {}
                        if scope_val and scope_val.strip() not in ("-", "NONE"):
                            self._role_matrix[role_col][action_key] = scope_val.strip()

    def get_permission(self, action_key: str) -> Optional[dict]:
        return self._permissions.get(action_key)

    def is_action_registered(self, action_key: str) -> bool:
        return action_key in self._permissions

    def get_role_action_scope(self, role_code: str, action_key: str) -> Optional[str]:
        """Trả về phạm vi tối đa theo ngữ nghĩa; mã ma trận không rõ sẽ bị từ chối."""
        raw_scope = self._role_matrix.get(role_code, {}).get(action_key)
        if raw_scope is None:
            return None
        if raw_scope in _SCOPE_CODES.values():
            return raw_scope
        return _SCOPE_CODES.get(raw_scope)

    def get_grantable_roles(self, grantor_role: str) -> List[str]:
        return DEFAULT_GRANTABLE_ROLES.get(grantor_role, [])

    def can_grant_role(self, grantor_role: str, target_role: str) -> bool:
        return target_role in self.get_grantable_roles(grantor_role)

registry = PolicyRegistry()

```
## baha_auth/di_chuyen_du_lieu/001_rang_buoc_tenant_va_nhat_ky.sql — SHA256 24137D951F866CEE6F10DF343B9F44F4E9FD7FC109E2C1EDBC98B575ED83294E
```
-- Migration PostgreSQL ngoại tuyến cho ràng buộc cùng tenant và nhật ký bất biến.
-- Chạy bằng tài khoản migration sau khi lưu trữ và rà soát kết quả các truy vấn kiểm tra.
-- Không áp dụng migration này vào cơ sở dữ liệu dự án trong lượt sửa lỗi.

BEGIN;

ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS creator_id VARCHAR(36);
ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS artifact_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS project_id VARCHAR(36);
ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS brand_id VARCHAR(36);
ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS channel_id VARCHAR(36);

ALTER TABLE delegated_job_grants ADD COLUMN IF NOT EXISTS target_artifact_version INTEGER;
ALTER TABLE delegated_job_grants ADD COLUMN IF NOT EXISTS target_content_hash VARCHAR(64);
ALTER TABLE delegated_job_grants ADD COLUMN IF NOT EXISTS worker_subject VARCHAR(255);

-- Thu hồi các grant cũ chưa khóa tài nguyên và principal; không tự đoán dữ liệu tin cậy.
UPDATE delegated_job_grants
SET status = CASE WHEN status = 'ACTIVE' THEN 'REVOKED' ELSE status END,
    target_artifact_version = COALESCE(target_artifact_version, 0),
    target_content_hash = COALESCE(target_content_hash, repeat('0', 64)),
    worker_subject = COALESCE(worker_subject, 'revoked-unpinned')
WHERE target_artifact_version IS NULL
   OR target_content_hash IS NULL
   OR worker_subject IS NULL;

ALTER TABLE delegated_job_grants ALTER COLUMN target_artifact_version SET NOT NULL;
ALTER TABLE delegated_job_grants ALTER COLUMN target_content_hash SET NOT NULL;
ALTER TABLE delegated_job_grants ALTER COLUMN worker_subject SET NOT NULL;

-- Từ chối migration nếu dữ liệu cũ đang trỏ sang tenant khác hoặc có khóa duy nhất bị trùng.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM org_units child JOIN org_units parent ON parent.id = child.parent_id
        WHERE child.parent_id IS NOT NULL AND child.workspace_id <> parent.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công cây OrgUnit đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM org_assignments a JOIN memberships m ON m.id = a.membership_id
        JOIN org_units o ON o.id = a.org_unit_id
        WHERE a.workspace_id <> m.workspace_id OR a.workspace_id <> o.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công OrgAssignment đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM role_assignments a JOIN memberships m ON m.id = a.membership_id
        WHERE a.workspace_id <> m.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công RoleAssignment đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM role_assignments a JOIN memberships m ON m.id = a.granted_by
        WHERE a.granted_by IS NOT NULL AND a.workspace_id <> m.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công grantor của RoleAssignment đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM reporting_lines r
        LEFT JOIN memberships manager ON manager.id = r.manager_membership_id
        LEFT JOIN memberships report ON report.id = r.report_membership_id
        LEFT JOIN org_units unit ON unit.id = r.org_unit_id
        WHERE r.workspace_id <> manager.workspace_id OR r.workspace_id <> report.workspace_id
           OR (r.org_unit_id IS NOT NULL AND r.workspace_id <> unit.workspace_id)
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ReportingLine đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM resource_grants g JOIN memberships m ON m.id = g.membership_id
        WHERE g.workspace_id <> m.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ResourceGrant đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM delegations d
        LEFT JOIN memberships grantor ON grantor.id = d.grantor_membership_id
        LEFT JOIN memberships grantee ON grantee.id = d.grantee_membership_id
        WHERE d.workspace_id <> grantor.workspace_id OR d.workspace_id <> grantee.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công Delegation đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM business_resources r
        LEFT JOIN org_units o ON o.id = r.org_unit_id
        WHERE r.org_unit_id IS NOT NULL AND r.workspace_id <> o.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công BusinessResource đang gắn OrgUnit khác tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM business_resources r
        LEFT JOIN memberships m ON m.user_id = r.owner_id AND m.workspace_id = r.workspace_id
        WHERE r.workspace_id IS NOT NULL AND r.owner_id IS NOT NULL AND m.id IS NULL
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công owner của BusinessResource không thuộc tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM business_resources r
        LEFT JOIN memberships m ON m.user_id = r.creator_id AND m.workspace_id = r.workspace_id
        WHERE r.workspace_id IS NOT NULL AND r.creator_id IS NOT NULL AND m.id IS NULL
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công creator của BusinessResource không thuộc tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM approval_runs
        GROUP BY workspace_id, artifact_type, artifact_id, artifact_version, policy_id
        HAVING count(*) > 1
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ApprovalRun trùng tài nguyên, phiên bản và policy'; END IF;

    IF EXISTS (
        SELECT 1 FROM approval_runs r
        LEFT JOIN business_resources b ON b.id = r.artifact_id
        LEFT JOIN approval_policies p ON p.id = r.policy_id
        LEFT JOIN memberships m ON m.id = r.created_by
        WHERE b.id IS NULL OR b.workspace_id <> r.workspace_id
           OR p.id IS NULL OR p.workspace_id <> r.workspace_id
           OR m.id IS NULL OR m.workspace_id <> r.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ApprovalRun tham chiếu khác tenant hoặc thiếu dữ liệu'; END IF;

    IF EXISTS (
        SELECT 1 FROM delegated_job_grants g
        LEFT JOIN business_resources b ON b.id = g.target_resource
        LEFT JOIN memberships m ON m.id = g.initiating_membership_id
        WHERE b.id IS NULL OR b.workspace_id <> g.workspace_id
           OR m.id IS NULL OR m.workspace_id <> g.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công worker grant tham chiếu khác tenant hoặc thiếu dữ liệu'; END IF;

    IF EXISTS (
        SELECT 1 FROM approval_decisions GROUP BY step_id HAVING count(*) > 1
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ApprovalDecision trùng step_id'; END IF;
END;
$$;

-- Hàm tạm chỉ giúp thêm ràng buộc một lần trong cùng phiên migration.
CREATE OR REPLACE FUNCTION pg_temp.add_constraint_if_missing(
    p_table REGCLASS, p_name TEXT, p_definition TEXT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = p_table AND conname = p_name
    ) THEN
        EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', p_table, p_name, p_definition);
    END IF;
END;
$$;

SELECT pg_temp.add_constraint_if_missing('memberships', 'uq_memberships_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('org_units', 'uq_org_units_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'uq_approval_runs_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_steps', 'uq_approval_steps_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_policies', 'uq_approval_policies_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'uq_business_resources_workspace_id',
    'UNIQUE (workspace_id, id)');

SELECT pg_temp.add_constraint_if_missing('org_units', 'fk_org_units_parent_same_workspace',
    'FOREIGN KEY (workspace_id, parent_id) REFERENCES org_units (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('org_assignments', 'fk_org_assignment_membership_same_workspace',
    'FOREIGN KEY (workspace_id, membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('org_assignments', 'fk_org_assignment_unit_same_workspace',
    'FOREIGN KEY (workspace_id, org_unit_id) REFERENCES org_units (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('role_assignments', 'fk_role_assignment_membership_same_workspace',
    'FOREIGN KEY (workspace_id, membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('role_assignments', 'fk_role_assignment_grantor_same_workspace',
    'FOREIGN KEY (workspace_id, granted_by) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('reporting_lines', 'uq_reporting_lines_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('reporting_lines', 'fk_reporting_manager_same_workspace',
    'FOREIGN KEY (workspace_id, manager_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('reporting_lines', 'fk_reporting_report_same_workspace',
    'FOREIGN KEY (workspace_id, report_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('reporting_lines', 'fk_reporting_org_unit_same_workspace',
    'FOREIGN KEY (workspace_id, org_unit_id) REFERENCES org_units (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('resource_grants', 'fk_resource_grant_membership_same_workspace',
    'FOREIGN KEY (workspace_id, membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('delegations', 'fk_delegation_grantor_same_workspace',
    'FOREIGN KEY (workspace_id, grantor_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('delegations', 'fk_delegation_grantee_same_workspace',
    'FOREIGN KEY (workspace_id, grantee_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_steps', 'fk_approval_step_run_same_workspace',
    'FOREIGN KEY (workspace_id, run_id) REFERENCES approval_runs (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_decisions', 'uq_approval_decision_step',
    'UNIQUE (step_id)');
SELECT pg_temp.add_constraint_if_missing('approval_decisions', 'fk_approval_decision_step_same_workspace',
    'FOREIGN KEY (workspace_id, step_id) REFERENCES approval_steps (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_decisions', 'fk_approval_decision_reviewer_same_workspace',
    'FOREIGN KEY (workspace_id, reviewer_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'fk_job_grant_membership_same_workspace',
    'FOREIGN KEY (workspace_id, initiating_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'fk_job_grant_resource_same_workspace',
    'FOREIGN KEY (workspace_id, target_resource) REFERENCES business_resources (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'fk_approval_run_artifact_same_workspace',
    'FOREIGN KEY (workspace_id, artifact_id) REFERENCES business_resources (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'fk_approval_run_policy_same_workspace',
    'FOREIGN KEY (workspace_id, policy_id) REFERENCES approval_policies (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'fk_approval_run_creator_same_workspace',
    'FOREIGN KEY (workspace_id, created_by) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'uq_approval_run_artifact_version_policy',
    'UNIQUE (workspace_id, artifact_type, artifact_id, artifact_version, policy_id)');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'fk_business_resource_org_same_workspace',
    'FOREIGN KEY (workspace_id, org_unit_id) REFERENCES org_units (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'fk_business_resource_owner_same_workspace',
    'FOREIGN KEY (workspace_id, owner_id) REFERENCES memberships (workspace_id, user_id)');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'fk_business_resource_creator_same_workspace',
    'FOREIGN KEY (workspace_id, creator_id) REFERENCES memberships (workspace_id, user_id)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'ck_job_grant_version_nonnegative',
    'CHECK (target_artifact_version >= 0)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'ck_job_grant_hash_length',
    'CHECK (length(target_content_hash) = 64)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'ck_job_grant_active_is_pinned',
    'CHECK (status <> ''ACTIVE'' OR (target_artifact_version > 0 AND target_content_hash <> repeat(''0'', 64) AND worker_subject <> ''revoked-unpinned''))');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'ck_business_resource_version_positive',
    'CHECK (artifact_version > 0)');

-- Chỉ cho truy vấn theo tenant đã được backend xác minh trong giao dịch hiện tại.
DO $$
DECLARE
    table_name TEXT;
    tenant_tables TEXT[] := ARRAY[
        'memberships', 'org_units', 'reporting_lines', 'org_assignments',
        'role_assignments', 'resource_grants', 'delegations', 'approval_policies',
        'approval_runs', 'approval_steps', 'approval_decisions',
        'delegated_job_grants', 'authz_audit_events', 'business_resources'
    ];
BEGIN
    ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
    ALTER TABLE workspaces FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_workspace_isolation ON workspaces;
    CREATE POLICY tenant_workspace_isolation ON workspaces
        USING (id = NULLIF(current_setting('baha.current_workspace_id', true), ''))
        WITH CHECK (id = NULLIF(current_setting('baha.current_workspace_id', true), ''));

    FOREACH table_name IN ARRAY tenant_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS tenant_workspace_isolation ON %I', table_name);
        IF table_name = 'business_resources' THEN
            EXECUTE format(
                'CREATE POLICY tenant_workspace_isolation ON %I USING (workspace_id = NULLIF(current_setting(''baha.current_workspace_id'', true), '''') OR (workspace_id IS NULL AND current_setting(''baha.authz_maintenance'', true) = ''on'')) WITH CHECK (workspace_id = NULLIF(current_setting(''baha.current_workspace_id'', true), '''') OR (workspace_id IS NULL AND current_setting(''baha.authz_maintenance'', true) = ''on''))',
                table_name
            );
        ELSE
            EXECUTE format(
                'CREATE POLICY tenant_workspace_isolation ON %I USING (workspace_id = NULLIF(current_setting(''baha.current_workspace_id'', true), '''')) WITH CHECK (workspace_id = NULLIF(current_setting(''baha.current_workspace_id'', true), ''''))',
                table_name
            );
        END IF;
    END LOOP;

    ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
    ALTER TABLE roles FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_role_catalog ON roles;
    CREATE POLICY tenant_role_catalog ON roles
        USING (workspace_id IS NULL OR workspace_id = NULLIF(current_setting('baha.current_workspace_id', true), ''))
        WITH CHECK (workspace_id = NULLIF(current_setting('baha.current_workspace_id', true), ''));

    ALTER TABLE permissions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE permissions FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS shared_permission_catalog ON permissions;
    CREATE POLICY shared_permission_catalog ON permissions FOR SELECT USING (true);

    ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_role_permissions ON role_permissions;
    CREATE POLICY tenant_role_permissions ON role_permissions FOR SELECT
        USING (EXISTS (
            SELECT 1 FROM roles r WHERE r.id = role_permissions.role_id
              AND (r.workspace_id IS NULL OR r.workspace_id = NULLIF(current_setting('baha.current_workspace_id', true), ''))
        ));
END;
$$;

-- Bảo vệ nhật ký kể cả khi một đường API mới vô tình thêm thao tác cập nhật/xóa.
CREATE OR REPLACE FUNCTION authz_reject_audit_mutation() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Nhật ký phân quyền chỉ được ghi nối tiếp';
END;
$$;

DROP TRIGGER IF EXISTS authz_audit_no_update ON authz_audit_events;
CREATE TRIGGER authz_audit_no_update
    BEFORE UPDATE ON authz_audit_events FOR EACH ROW EXECUTE FUNCTION authz_reject_audit_mutation();
DROP TRIGGER IF EXISTS authz_audit_no_delete ON authz_audit_events;
CREATE TRIGGER authz_audit_no_delete
    BEFORE DELETE ON authz_audit_events FOR EACH ROW EXECUTE FUNCTION authz_reject_audit_mutation();

COMMIT;

```
## sin_content_api/src/auth/tenancy.py — SHA256 3574B0A6E1DE2AD0F0308296EF05CC35439D5EDDDC47BC2703C4E1FBC6B43B9D
```
"""Xác thực bearer và đánh giá RBAC qua kho Baha Auth chuẩn."""

from __future__ import annotations

import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db as get_content_db
from src.models.entities import Workspace


_WORKSPACE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class TenantContext:
    workspace_id: str
    user_id: str
    actor: Any
    auth_db: Session
    request_id: str


def _canonical_auth_modules() -> dict[str, Any]:
    """Nạp Baha Auth bằng namespace chuẩn khi toàn bộ cấu hình tường minh có mặt."""
    secret = os.getenv("BAHA_AUTH_JWT_SECRET")
    issuer = os.getenv("BAHA_AUTH_JWT_ISSUER")
    audience = os.getenv("BAHA_AUTH_JWT_AUDIENCE")
    database_url = os.getenv("BAHA_AUTH_DATABASE_URL")
    if not all((secret, issuer, audience, database_url)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dịch vụ phân quyền chưa được cấu hình.",
        )

    project_root = str(Path(__file__).resolve().parents[3])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        from baha_auth.src.database import (  # type: ignore[import-not-found]
            clear_tenant_context,
            get_db as get_auth_db,
            set_tenant_context,
        )
        from baha_auth.src.policy.evaluator import (  # type: ignore[import-not-found]
            ActorContext,
            ResourceContext,
            evaluate_permission,
        )
        from baha_auth.src.services.danh_tinh_service import (  # type: ignore[import-not-found]
            load_actor_for_user,
        )
        from baha_auth.src.services.nhat_ky_kiem_toan import (  # type: ignore[import-not-found]
            write_audit_event,
        )
        from baha_auth.src.xac_minh_danh_tinh import (  # type: ignore[import-not-found]
            verify_bearer_token,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dịch vụ phân quyền chưa sẵn sàng.",
        ) from exc

    return {
        "secret": secret,
        "issuer": issuer,
        "audience": audience,
        "get_auth_db": get_auth_db,
        "set_tenant_context": set_tenant_context,
        "clear_tenant_context": clear_tenant_context,
        "verify_bearer_token": verify_bearer_token,
        "load_actor_for_user": load_actor_for_user,
        "evaluate_permission": evaluate_permission,
        "write_audit_event": write_audit_event,
        "ActorContext": ActorContext,
        "ResourceContext": ResourceContext,
    }


def _close_generator(generator: Iterator[Session]) -> None:
    close = getattr(generator, "close", None)
    if close is not None:
        close()


def get_current_tenant_context(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    content_db: Session = Depends(get_content_db),
) -> Iterator[TenantContext]:
    """Lấy danh tính từ JWT và xác minh membership hiện hành cho workspace đã chọn."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần bearer token hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần bearer token hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not x_workspace_id or not _WORKSPACE_ID.fullmatch(x_workspace_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần chọn workspace hợp lệ.",
        )

    auth = _canonical_auth_modules()
    try:
        identity = auth["verify_bearer_token"](
            token,
            secret=auth["secret"],
            issuer=auth["issuer"],
            audience=auth["audience"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token không hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    auth_db_generator = auth["get_auth_db"]()
    auth_db: Optional[Session] = None
    try:
        auth_db = next(auth_db_generator)
        auth["set_tenant_context"](x_workspace_id, auth_db)
        actor = auth["load_actor_for_user"](
            auth_db,
            workspace_id=x_workspace_id,
            user_id=identity.user_id,
        )
        if actor is None or actor.user_id != identity.user_id or actor.workspace_id != x_workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập workspace đã chọn.",
            )

        # Membership chuẩn không tự tạo workspace trong kho nội dung tách biệt.
        if content_db.query(Workspace.id).filter(Workspace.id == x_workspace_id).first() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập workspace đã chọn.",
            )

        yield TenantContext(
            workspace_id=x_workspace_id,
            user_id=identity.user_id,
            actor=actor,
            auth_db=auth_db,
            request_id=str(uuid.uuid4()),
        )
    except HTTPException:
        raise
    except Exception as exc:
        if auth_db is not None:
            auth_db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể kiểm tra membership hoặc kết nối kho phân quyền.",
        ) from exc
    finally:
        if auth_db is not None:
            try:
                auth_db.rollback()
            except Exception:
                pass
            try:
                auth["clear_tenant_context"](auth_db)
            except Exception:
                pass
        _close_generator(auth_db_generator)
        auth["clear_tenant_context"]()


def _audit_decision(
    ctx: TenantContext,
    auth: dict[str, Any],
    action_key: str,
    decision: Any,
    resource: Any = None,
) -> None:
    try:
        # SET LOCAL clears on commit; bind lại tenant trước transaction audit.
        auth["set_tenant_context"](ctx.workspace_id, ctx.auth_db)
        auth["write_audit_event"](
            ctx.auth_db,
            workspace_id=ctx.workspace_id,
            actor_id=ctx.user_id,
            actor_type="USER",
            action_key=action_key,
            decision="ALLOW" if decision.allowed else "DENY",
            reason=decision.reason_code,
            policy_version=decision.policy_version,
            resource_type=getattr(resource, "resource_type", None),
            resource_id=getattr(resource, "resource_id", None),
            request_id=ctx.request_id,
            safe_metadata={},
        )
        ctx.auth_db.commit()
    except Exception as exc:
        ctx.auth_db.rollback()
        if decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể ghi nhận quyết định phân quyền.",
            ) from exc


def authorize_action(ctx: TenantContext, action_key: str, resource: Any = None) -> None:
    """Đánh giá action; request tổng hợp chỉ xét assignment cấp workspace."""
    auth = _canonical_auth_modules()
    try:
        actor = ctx.actor
        if resource is None:
            # Assignment TEAM/PROJECT/OWN không được nâng thành quyền đọc toàn tenant.
            actor = auth["ActorContext"](
                user_id=ctx.actor.user_id,
                workspace_id=ctx.actor.workspace_id,
                membership_id=ctx.actor.membership_id,
                membership_status=ctx.actor.membership_status,
                roles=[role for role in ctx.actor.roles if role.get("scope_type") == "WORKSPACE"],
                department_ids=[],
                team_ids=[],
                user_status=ctx.actor.user_status,
                workspace_status=ctx.actor.workspace_status,
            )
        decision = auth["evaluate_permission"](
            actor=actor,
            action_key=action_key,
            resource=resource,
        )
        _audit_decision(ctx, auth, action_key, decision, resource)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chính sách quyền chưa sẵn sàng.",
        ) from exc

    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không đủ quyền cho thao tác hoặc phạm vi tài nguyên này.",
        )


def authorize_resource(
    ctx: TenantContext,
    action_key: str,
    *,
    resource_type: str,
    resource_id: Optional[str],
    workspace_id: Optional[str],
    org_unit_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    creator_id: Optional[str] = None,
    artifact_version: Optional[int] = None,
    content_hash: Optional[str] = None,
    project_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    require_creator: bool = False,
) -> None:
    """Kiểm tra scope trên row đã được truy vấn server-side trong tenant."""
    if (
        not resource_id
        or not workspace_id
        or workspace_id != ctx.workspace_id
        or (require_creator and not creator_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể xác minh phạm vi hoặc nguồn tạo của tài nguyên.",
        )

    auth = _canonical_auth_modules()
    try:
        resource = auth["ResourceContext"](
            workspace_id=workspace_id,
            resource_id=resource_id,
            resource_type=resource_type,
            org_unit_id=org_unit_id,
            owner_id=owner_id,
            creator_id=creator_id,
            artifact_version=artifact_version,
            content_hash=content_hash,
            project_id=project_id,
            brand_id=brand_id,
            channel_id=channel_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tạo ngữ cảnh tài nguyên cho chính sách quyền.",
        ) from exc
    authorize_action(ctx, action_key, resource=resource)


def require_action(action_key: str) -> Callable[..., TenantContext]:
    """Dependency cho route tổng hợp; chỉ grant workspace được phép qua guard này."""
    def dependency(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        authorize_action(ctx, action_key)
        return ctx

    dependency.__name__ = f"require_action_{action_key.replace('.', '_')}"
    dependency.required_action = action_key  # type: ignore[attr-defined]
    return dependency


def require_actions(*action_keys: str) -> Callable[..., TenantContext]:
    """Yêu cầu đồng thời nhiều action trên dữ liệu tổng hợp cấp workspace."""
    def dependency(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        for action_key in action_keys:
            authorize_action(ctx, action_key)
        return ctx

    dependency.__name__ = "require_actions_" + "_".join(key.replace('.', '_') for key in action_keys)
    dependency.required_actions = tuple(action_keys)  # type: ignore[attr-defined]
    return dependency


def require_resolved_resource_action(action_key: str) -> Callable[..., TenantContext]:
    """Nạp actor cho route mà handler phải truy vấn row và gọi authorize_resource."""
    def dependency(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        return ctx

    dependency.__name__ = f"require_resolved_resource_{action_key.replace('.', '_')}"
    dependency.required_action = action_key  # type: ignore[attr-defined]
    dependency.requires_resource_authorization = True  # type: ignore[attr-defined]
    return dependency


def require_resolved_resource_actions(*action_keys: str) -> Callable[..., TenantContext]:
    """Nạp actor cho route có nhiều action được kiểm tra trên resource đã phân giải."""
    def dependency(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        return ctx

    dependency.__name__ = "require_resolved_resource_" + "_".join(
        key.replace('.', '_') for key in action_keys
    )
    dependency.required_actions = tuple(action_keys)  # type: ignore[attr-defined]
    dependency.requires_resource_authorization = True  # type: ignore[attr-defined]
    return dependency


def require_role(_: str):
    """Dependency role legacy bị vô hiệu hóa; route phải khai báo action RBAC cụ thể."""
    def deny_legacy_role(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kiểm tra role legacy đã bị vô hiệu hóa; route cần action RBAC cụ thể.",
        )

    deny_legacy_role.__name__ = "deny_legacy_role"
    return deny_legacy_role

```
## sin_content_workers/worker.py — SHA256 183163ABCA72E0F995D1A6E61A6B660FF3117EFD5D4016F4678B1890F699AB86
```
"""Hàng đợi tác vụ offline kiểm tra grant và ghim payload trước side effect."""

import json
import os
import time
import uuid
from threading import Lock
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


# Tên tác vụ nội bộ được ánh xạ tĩnh; không lấy action từ payload của job.
TASK_ACTIONS = {
    "research.run": "research.run",
    "ideas.generate": "ideas.create",
    "media.render": "media.edit",
    "content.publish": "publishing.execute",
}

PAYLOAD_BINDING_FIELDS = (
    "workspace_id",
    "resource_id",
    "resource_type",
    "artifact_version",
    "content_hash",
    "policy_version",
)
RESPONSE_BINDING_FIELDS = {
    "workspace_id": "workspace_id",
    "resource_id": "target_resource",
    "resource_type": "resource_type",
    "artifact_version": "artifact_version",
    "content_hash": "content_hash",
    "policy_version": "policy_version",
}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _http_open(request: Request, timeout: float):
    return build_opener(_NoRedirectHandler).open(request, timeout=timeout)


def _safe_authz_url(base_url: str) -> bool:
    """Chỉ gửi bearer qua HTTPS, trừ loopback để kiểm thử cục bộ."""
    try:
        parsed = urlsplit(base_url)
        host = (parsed.hostname or "").lower()
        loopback = host in {"localhost", "127.0.0.1", "::1"}
        return (
            parsed.scheme == "https" or (parsed.scheme == "http" and loopback)
        ) and bool(host) and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
    except ValueError:
        return False


def _canonical_payload(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict) or any(not isinstance(key, str) for key in payload):
        return None
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return None


def _payload_binding(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    binding = {field: payload.get(field) for field in PAYLOAD_BINDING_FIELDS}
    if not all(isinstance(binding[field], str) and binding[field].strip() for field in (
        "workspace_id", "resource_id", "resource_type", "content_hash", "policy_version"
    )):
        return None
    version = binding["artifact_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return None
    return binding


def _recheck_job_permission(
    job_id: str,
    action_key: str,
    expected_binding: Dict[str, Any],
) -> bool:
    """Yêu cầu Baha Auth xác nhận grant và toàn bộ binding của resource."""
    base_url = os.getenv("BAHA_AUTHZ_BASE_URL")
    service_token = os.getenv("BAHA_AUTH_WORKER_TOKEN")
    if not base_url or not service_token or not _safe_authz_url(base_url):
        return False

    request = Request(
        base_url.rstrip("/") + "/authz/v1/workers/recheck",
        data=json.dumps({"job_id": job_id, "action_key": action_key}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {service_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with _http_open(request, timeout=2) as response:
            if response.status != 200:
                return False
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return False

    if (
        not isinstance(result, dict)
        or result.get("allowed") is not True
        or result.get("job_id") != job_id
        or result.get("action_key") != action_key
    ):
        return False

    return all(
        result.get(response_field) == expected_binding[payload_field]
        for payload_field, response_field in RESPONSE_BINDING_FIELDS.items()
    )


class OfflineTaskQueue:
    """Hàng đợi trong RAM; mọi thay đổi payload sau enqueue đều bị từ chối."""

    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._payload_snapshots: Dict[str, str] = {}
        self._task_snapshots: Dict[str, str] = {}
        self._attempted_jobs = set()
        self._lock = Lock()

    def enqueue(self, task_name: str, payload: Dict[str, Any]) -> str:
        serialized = _canonical_payload(payload)
        if serialized is None:
            raise ValueError("Payload phải là object JSON hợp lệ")

        job_id = f"job_{uuid.uuid4().hex[:8]}"
        payload_snapshot = json.loads(serialized)
        self.jobs[job_id] = {
            "id": job_id,
            "task_name": task_name,
            "payload": payload_snapshot,
            "status": "QUEUED",
            "progress": 0,
            "created_at": time.time(),
            "error": None,
        }
        self._payload_snapshots[job_id] = serialized
        self._task_snapshots[job_id] = task_name
        return job_id

    def get_status(self, job_id: str) -> Dict[str, Any]:
        job = self.jobs.get(job_id)
        if not job:
            return {"status": "NOT_FOUND"}
        return {
            **job,
            "payload": json.loads(self._payload_snapshots[job_id]),
        }

    def _deny(self, job: Dict[str, Any]) -> None:
        job["status"] = "FAILED"
        job["error"] = "Authorization denied"

    def process_sync(self, job_id: str, handler: Callable[[Dict[str, Any]], Any]) -> Any:
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError("Job not found")

        expected_task = self._task_snapshots.get(job_id)
        expected_payload = self._payload_snapshots.get(job_id)
        action_key = TASK_ACTIONS.get(expected_task or "")
        current_payload = _canonical_payload(job.get("payload"))
        payload_snapshot = json.loads(expected_payload) if expected_payload else None
        binding = _payload_binding(payload_snapshot) if isinstance(payload_snapshot, dict) else None

        if (
            job.get("id") != job_id
            or job.get("task_name") != expected_task
            or current_payload != expected_payload
            or job.get("status") != "QUEUED"
            or not action_key
            or binding is None
        ):
            self._deny(job)
            raise PermissionError("Worker authorization denied")

        if not _recheck_job_permission(job_id, action_key, binding):
            self._deny(job)
            raise PermissionError("Worker authorization denied")

        with self._lock:
            if job_id in self._attempted_jobs:
                self._deny(job)
                raise PermissionError("Worker authorization denied")
            self._attempted_jobs.add(job_id)

        # Handler nhận bản copy từ snapshot đã được grant xác nhận, không nhận dict mutable trong queue.
        job["status"] = "PROCESSING"
        job["progress"] = 20
        try:
            result = handler(json.loads(expected_payload))
            job["status"] = "COMPLETED"
            job["progress"] = 100
            job["result"] = result
            return result
        except Exception as exc:
            job["status"] = "FAILED"
            job["error"] = str(exc)
            raise


task_queue = OfflineTaskQueue()

```
## sin_creator_os/src/app/(main)/team/page.tsx — SHA256 735235A0A5922662E70FD26C934DEB0E66A5ADE97A0A09CD5906B342D938222E
```
"use client";

import * as React from "react";
import {
  Building2,
  CheckCircle2,
  History,
  Lock,
  Network,
  Shield,
  Users,
  UserPlus,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function DataNotConnected({ title }: { title: string }) {
  return (
    <Card className="rounded-xl border shadow-xs">
      <CardHeader className="bg-muted/20 border-b pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-sm font-bold">{title}</CardTitle>
          <Badge variant="outline">Chưa kết nối</Badge>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <p className="text-sm text-muted-foreground">
          Chưa kết nối dữ liệu tổ chức. Liên hệ quản trị viên để thiết lập kết nối.
        </p>
      </CardContent>
    </Card>
  );
}

export default function TeamManagementPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-20">
      <div className="flex flex-col justify-between gap-4 border-b pb-5 md:flex-row md:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-foreground">
              <Shield className="size-6 text-primary" />
              <span>Quản trị tổ chức và phân quyền doanh nghiệp</span>
            </h1>
            <Badge variant="outline" className="border-primary/40 bg-primary/5 text-xs font-semibold text-primary">
              BAHA-AUTHZ-001
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Quản lý thành viên, cơ cấu tổ chức và quyền truy cập.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" className="h-8 gap-1.5 text-xs" disabled>
            <Building2 className="size-3.5" />
            <span>Thêm phòng ban</span>
          </Button>
          <Button size="sm" className="h-8 gap-1.5 rounded-lg text-xs" disabled>
            <UserPlus className="size-3.5" />
            <span>Mời thành viên</span>
          </Button>
        </div>
      </div>

      <Tabs defaultValue="members" className="space-y-6">
        <TabsList className="flex flex-wrap gap-1 rounded-xl border bg-muted/40 p-1">
          <TabsTrigger value="members" className="gap-1.5 py-1.5 text-xs font-semibold">
            <Users className="size-3.5" />
            <span>Thành viên và vai trò</span>
          </TabsTrigger>
          <TabsTrigger value="hierarchy" className="gap-1.5 py-1.5 text-xs font-semibold">
            <Network className="size-3.5" />
            <span>Sơ đồ tổ chức</span>
          </TabsTrigger>
          <TabsTrigger value="matrix" className="gap-1.5 py-1.5 text-xs font-semibold">
            <Lock className="size-3.5" />
            <span>Ma trận quyền</span>
          </TabsTrigger>
          <TabsTrigger value="inbox" className="gap-1.5 py-1.5 text-xs font-semibold">
            <CheckCircle2 className="size-3.5" />
            <span>Hòm thư phê duyệt</span>
          </TabsTrigger>
          <TabsTrigger value="audit" className="gap-1.5 py-1.5 text-xs font-semibold">
            <History className="size-3.5" />
            <span>Nhật ký kiểm toán</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="members" className="space-y-4">
          <DataNotConnected
            title="Danh sách thành viên và quyền được gán"
          />
        </TabsContent>
        <TabsContent value="hierarchy" className="space-y-4">
          <DataNotConnected
            title="Cơ cấu phòng ban và nhóm"
          />
        </TabsContent>
        <TabsContent value="matrix" className="space-y-4">
          <DataNotConnected
            title="Ma trận quyền hạn"
          />
        </TabsContent>
        <TabsContent value="inbox" className="space-y-4">
          <DataNotConnected
            title="Hòm thư phê duyệt"
          />
        </TabsContent>
        <TabsContent value="audit" className="space-y-4">
          <DataNotConnected
            title="Nhật ký quyết định phân quyền"
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

```
## sin_content_api/src/modules/briefs/router.py — SHA256 19C72106C56B2366403D8B5C1F29A92BC4E0EB15F163DB1C33DC1DDE4EDA3D5E
```
# Router quan ly Brand Brief co xac thuc tenant va vong doi phe duyet (P02)
import json
import uuid
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_resolved_resource_action,
)
from src.models.entities import BrandBriefVersion, AudienceSegment, AllowedFact, AuditEvent
from src.schemas.contracts import (
    BrandBriefCreate, BrandBriefUpdate, BrandBriefOut, BriefReviewRequest,
    AudienceSegmentOut, AllowedFactOut
)

router = APIRouter(prefix="/v1/briefs", tags=["Brand Briefs"])

def _format_brief_out(brief: BrandBriefVersion) -> BrandBriefOut:
    """Format BrandBriefVersion ORM thanh Pydantic BrandBriefOut"""
    segments_out = []
    for s in brief.audience_segments:
        segments_out.append(AudienceSegmentOut(
            id=s.id,
            brief_version_id=s.brief_version_id,
            label=s.label,
            contexts=json.loads(s.contexts_json or "[]"),
            needs=json.loads(s.needs_json or "[]"),
            disallowed_inferences=json.loads(s.disallowed_inferences_json or "[]"),
            awareness_stage=s.awareness_stage,
            created_at=s.created_at
        ))
        
    facts_out = []
    for f in brief.allowed_facts:
        facts_out.append(AllowedFactOut(
            id=f.id,
            brief_version_id=f.brief_version_id,
            claim_text=f.claim_text,
            fact_type=f.fact_type,
            source_citation=f.source_citation,
            verification_status=f.verification_status,
            created_at=f.created_at
        ))

    return BrandBriefOut(
        id=brief.id,
        workspace_id=brief.workspace_id,
        version=brief.version,
        brand_name=brief.brand_name,
        objective=brief.objective,
        voice_description=brief.voice_description,
        language=brief.language,
        current_audience=brief.current_audience,
        target_audience=brief.target_audience,
        topics_included=json.loads(brief.topics_included_json or "[]"),
        topics_excluded=json.loads(brief.topics_excluded_json or "[]"),
        production_limits=json.loads(brief.production_limits_json or "[]"),
        status=brief.status,
        approved_by_user_id=brief.approved_by_user_id,
        approved_at=brief.approved_at,
        created_at=brief.created_at,
        segments=segments_out,
        allowed_facts=facts_out
    )

@router.get("", response_model=List[BrandBriefOut])
def list_briefs(
    ctx: TenantContext = Depends(require_action("brief.read")),
    db: Session = Depends(get_db)
):
    briefs = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == ctx.workspace_id
    ).all()
    for brief in briefs:
        authorize_resource(
            ctx, "brief.read", resource_type="brand_brief",
            resource_id=brief.id, workspace_id=brief.workspace_id,
        )
    return [_format_brief_out(b) for b in briefs]

@router.post("", response_model=BrandBriefOut, status_code=status.HTTP_201_CREATED)
def create_brief(
    payload: BrandBriefCreate,
    ctx: TenantContext = Depends(require_action("brief.edit")),
    db: Session = Depends(get_db)
):
    brief = BrandBriefVersion(
        workspace_id=ctx.workspace_id,
        version=1,
        brand_name=payload.brand_name,
        objective=payload.objective,
        voice_description=payload.voice_description,
        current_audience=payload.current_audience,
        target_audience=payload.target_audience,
        topics_included_json=json.dumps(payload.topics_included),
        topics_excluded_json=json.dumps(payload.topics_excluded),
        production_limits_json=json.dumps(payload.production_limits or []),
        status="DRAFT"
    )
    db.add(brief)
    db.flush() # Sinh ID cho brief
    
    # Them segments neu co
    if payload.segments:
        for seg in payload.segments:
            s_entity = AudienceSegment(
                brief_version_id=brief.id,
                label=seg.label,
                contexts_json=json.dumps(seg.contexts),
                needs_json=json.dumps(seg.needs),
                disallowed_inferences_json=json.dumps(seg.disallowed_inferences),
                awareness_stage=seg.awareness_stage
            )
            db.add(s_entity)
            
    # Them allowed facts neu co
    if payload.allowed_facts:
        for f in payload.allowed_facts:
            f_entity = AllowedFact(
                brief_version_id=brief.id,
                claim_text=f.claim_text,
                fact_type=f.fact_type,
                source_citation=f.source_citation,
                verification_status=f.verification_status
            )
            db.add(f_entity)
            
    db.commit()
    db.refresh(brief)
    return _format_brief_out(brief)

@router.get("/{brief_id}", response_model=BrandBriefOut)
def get_brief(
    brief_id: str,
    ctx: TenantContext = Depends(require_resolved_resource_action("brief.read")),
    db: Session = Depends(get_db)
):
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == brief_id,
        BrandBriefVersion.workspace_id == ctx.workspace_id
    ).first()
    
    if not brief:
        exists_other = db.query(BrandBriefVersion).filter(BrandBriefVersion.id == brief_id).first()
        if exists_other:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CROSS_TENANT_DENIED: Khong the truy cap tai nguyen cua Workspace khac"
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BRIEF_NOT_FOUND")

    authorize_resource(
        ctx, "brief.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
        
    return _format_brief_out(brief)

@router.put("/{brief_id}", response_model=BrandBriefOut)
def update_or_revise_brief(
    brief_id: str,
    payload: BrandBriefUpdate,
    ctx: TenantContext = Depends(require_resolved_resource_action("brief.edit")),
    db: Session = Depends(get_db)
):
    """
    T021: Chinh sua Brief.
    - Neu brief dang o trang thai DRAFT hoac CHANGES_REQUESTED: Cap nhat truc tiep tai cho.
    - Neu brief da APPROVED: TAO PHIEN BAN BAT BIEN MOI (version = version + 1), brief cu giu nguyen APPROVED.
    """
    existing = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == brief_id,
        BrandBriefVersion.workspace_id == ctx.workspace_id
    ).first()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BRIEF_NOT_FOUND")

    authorize_resource(
        ctx, "brief.edit", resource_type="brand_brief",
        resource_id=existing.id, workspace_id=existing.workspace_id,
    )
        
    if existing.status == "APPROVED":
        # Tao phien ban bat bien moi!
        new_version_num = existing.version + 1
        new_brief = BrandBriefVersion(
            workspace_id=ctx.workspace_id,
            version=new_version_num,
            brand_name=payload.brand_name if payload.brand_name is not None else existing.brand_name,
            objective=payload.objective if payload.objective is not None else existing.objective,
            voice_description=payload.voice_description if payload.voice_description is not None else existing.voice_description,
            current_audience=payload.current_audience if payload.current_audience is not None else existing.current_audience,
            target_audience=payload.target_audience if payload.target_audience is not None else existing.target_audience,
            topics_included_json=json.dumps(payload.topics_included) if payload.topics_included is not None else existing.topics_included_json,
            topics_excluded_json=json.dumps(payload.topics_excluded) if payload.topics_excluded is not None else existing.topics_excluded_json,
            production_limits_json=json.dumps(payload.production_limits) if payload.production_limits is not None else existing.production_limits_json,
            status="DRAFT" # Phien ban moi bat buoc can duyet lai, khong tu thua huong approval
        )
        db.add(new_brief)
        db.flush()
        
        # Sao chep cac segments sang phien ban moi
        for seg in existing.audience_segments:
            db.add(AudienceSegment(
                brief_version_id=new_brief.id,
                label=seg.label,
                contexts_json=seg.contexts_json,
                needs_json=seg.needs_json,
                disallowed_inferences_json=seg.disallowed_inferences_json,
                awareness_stage=seg.awareness_stage
            ))
            
        # Sao chep cac facts sang phien ban moi
        for fact in existing.allowed_facts:
            db.add(AllowedFact(
                brief_version_id=new_brief.id,
                claim_text=fact.claim_text,
                fact_type=fact.fact_type,
                source_citation=fact.source_citation,
                verification_status=fact.verification_status
            ))
            
        db.commit()
        db.refresh(new_brief)
        return _format_brief_out(new_brief)
        
    else:
        # Cap nhat truc tiep ban nhap
        if payload.brand_name is not None: existing.brand_name = payload.brand_name
        if payload.objective is not None: existing.objective = payload.objective
        if payload.voice_description is not None: existing.voice_description = payload.voice_description
        if payload.current_audience is not None: existing.current_audience = payload.current_audience
        if payload.target_audience is not None: existing.target_audience = payload.target_audience
        if payload.topics_included is not None: existing.topics_included_json = json.dumps(payload.topics_included)
        if payload.topics_excluded is not None: existing.topics_excluded_json = json.dumps(payload.topics_excluded)
        if payload.production_limits is not None: existing.production_limits_json = json.dumps(payload.production_limits)
        
        db.commit()
        db.refresh(existing)
        return _format_brief_out(existing)

@router.post("/{brief_id}/review", response_model=BrandBriefOut)
def review_brief(
    brief_id: str,
    payload: BriefReviewRequest,
    ctx: TenantContext = Depends(require_resolved_resource_action("brief.approve")),
    db: Session = Depends(get_db)
):
    """
    T022: Phe duyet Brief.
    Yeu cau role toi thieu reviewer. Neu role viewer co tinh goi, middleware se chan va nem 403 Forbidden.
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == brief_id,
        BrandBriefVersion.workspace_id == ctx.workspace_id
    ).first()
    
    if not brief:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BRIEF_NOT_FOUND")

    # The current schema has no trusted creator attribution. Approval stays
    # disabled until a migration backfills and verifies that provenance.
    authorize_resource(
        ctx, "brief.approve", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
        creator_id=None, require_creator=True,
    )
        
    if payload.action == "APPROVE":
        brief.status = "APPROVED"
        brief.approved_by_user_id = ctx.user_id
        brief.approved_at = datetime.now(timezone.utc)
        
        # Ghi audit event
        audit = AuditEvent(
            workspace_id=ctx.workspace_id,
            actor_id=ctx.user_id,
            event_type="BRIEF_APPROVED",
            details=f"Brief {brief.id} (v{brief.version}) da duoc phe duyet boi {ctx.user_id}"
        )
        db.add(audit)
        
    elif payload.action == "REQUEST_CHANGES":
        brief.status = "CHANGES_REQUESTED"
        audit = AuditEvent(
            workspace_id=ctx.workspace_id,
            actor_id=ctx.user_id,
            event_type="BRIEF_CHANGES_REQUESTED",
            details=f"Brief {brief.id} (v{brief.version}) yeu cau sua doi: {payload.notes}"
        )
        db.add(audit)
        
    db.commit()
    db.refresh(brief)
    return _format_brief_out(brief)

```
## sin_content_api/src/modules/ideation/router.py — SHA256 005E5D49785E2B8454B053F8D6C932602B1F40D3BE25A4BD7F1050FDC549E169
```
# Router API cho Pha P08: Ideation & Citation Verification (/v1/ideation)
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_action,
    authorize_resource,
    require_action,
    require_resolved_resource_action,
    require_resolved_resource_actions,
)
from src.models.entities import BrandBriefVersion, IdeaCard
from src.schemas.contracts import (
    IdeaCardOut, IdeaCardVerifyRequest, IdeaCardVerifyResponse,
    IdeaGenerationRequest, IdeaGenerationResponse, IdeaReviewRequest
)
from src.modules.ideation.ideation_service import ideation_service

router = APIRouter(prefix="/v1/ideation", tags=["Ideation & Verification"])

@router.post("/generate", response_model=IdeaGenerationResponse)
def generate_ideas(
    payload: IdeaGenerationRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_actions("ideas.create", "brief.read", "evidence.read"))
):
    """
    Sinh cac the y tuong TikTok dua tren brief va bang chung trich dan thuc te trong workspace (T080, T082).
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == payload.brief_version_id,
        BrandBriefVersion.workspace_id == tenant.workspace_id,
    ).first()
    if brief is None:
        raise HTTPException(status_code=404, detail="Brand brief not found")
    authorize_resource(
        tenant, "brief.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_resource(
        tenant, "ideas.create", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_action(tenant, "evidence.read")
    return ideation_service.generate_ideas(db, tenant.workspace_id, tenant.user_id, payload)

@router.post("/verify", response_model=IdeaCardVerifyResponse)
def verify_idea(
    payload: IdeaCardVerifyRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_actions("ideas.read", "evidence.read"))
):
    """
    Kiem chung doc lap (IdeaVerifier):
    Xac thuc 100% ID bang chung va URL trich dan, phat hien va tu choi trich dan bia dat (T080, T081, T082, T085).
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == payload.idea_card.brief_version_id,
        BrandBriefVersion.workspace_id == tenant.workspace_id,
    ).first()
    if brief is None:
        raise HTTPException(status_code=404, detail="Brand brief not found")
    authorize_resource(
        tenant, "ideas.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_action(tenant, "evidence.read")
    return ideation_service.verify_idea_card(db, tenant.workspace_id, payload)

@router.get("/cards", response_model=List[IdeaCardOut])
def list_idea_cards(
    brief_version_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("ideas.read"))
):
    """
    Lay danh sach the y tuong trong workspace theo bo loc brief hoac trang thai review.
    """
    cards = db.query(IdeaCard).filter(IdeaCard.workspace_id == tenant.workspace_id)
    if brief_version_id:
        cards = cards.filter(IdeaCard.brief_version_id == brief_version_id)
    if status:
        cards = cards.filter(IdeaCard.status == status)
    for card in cards.limit(limit).all():
        authorize_resource(
            tenant, "ideas.read", resource_type="idea_card",
            resource_id=card.id, workspace_id=card.workspace_id,
        )
    return ideation_service.list_idea_cards(db, tenant.workspace_id, brief_version_id, status, limit)

@router.get("/cards/{idea_id}", response_model=IdeaCardOut)
def get_idea_card(
    idea_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_action("ideas.read"))
):
    """
    Chi tiet mot the y tuong kem trich dan va canh bao trung lap.
    """
    card = db.query(IdeaCard).filter(
        IdeaCard.id == idea_id,
        IdeaCard.workspace_id == tenant.workspace_id,
    ).first()
    if card is None:
        raise HTTPException(status_code=404, detail="IdeaCard not found")
    authorize_resource(
        tenant, "ideas.read", resource_type="idea_card",
        resource_id=card.id, workspace_id=card.workspace_id,
    )
    return ideation_service.get_idea_card(db, tenant.workspace_id, idea_id)

@router.post("/cards/{idea_id}/review", response_model=IdeaCardOut)
def review_idea_card(
    idea_id: str,
    payload: IdeaReviewRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_action("ideas.approve_team"))
):
    """
    Thao tac phe duyet / tu choi / yeu cau bo sung bang chung (Review Queue - HITL).
    """
    card = db.query(IdeaCard).filter(
        IdeaCard.id == idea_id,
        IdeaCard.workspace_id == tenant.workspace_id,
    ).first()
    if card is None:
        raise HTTPException(status_code=404, detail="IdeaCard not found")
    # The legacy schema has no trusted creator field, so separation-of-duties
    # cannot be established. Keep review closed until provenance is migrated.
    authorize_resource(
        tenant, "ideas.approve_team", resource_type="idea_card",
        resource_id=card.id, workspace_id=card.workspace_id,
        creator_id=None, require_creator=True,
    )
    return ideation_service.review_idea_card(db, tenant.workspace_id, tenant.user_id, idea_id, payload)

```
## sin_content_api/src/modules/ingestion/router.py — SHA256 7637289DC495DEFC791D82EA42F2A28F85E276CA470C6DC6FB82576181DF7B3A
```
"""
SIN Content Intelligence - Ingestion Router (P04)
REST endpoints for idempotent batch ingestion, multi-source lineage, and retention purge.
"""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_resolved_resource_action,
)
from src.models.entities import SourceRecord, SourceObservation, MetricSnapshot
from .service import ingestion_service

router = APIRouter(prefix="/v1/ingestion", tags=["Data Ingestion & Provenance"])

class IngestBatchRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)
    is_production: bool = False

class IngestBatchResponse(BaseModel):
    total: int
    created_sources: int
    created_observations: int
    deduplicated_observations: int
    quarantined_count: int
    status: str

@router.post("/batch", response_model=IngestBatchResponse)
def ingest_batch(
    payload: IngestBatchRequest,
    tenant: TenantContext = Depends(require_action("evidence.import")),
    db: Session = Depends(get_db),
):
    """
    Idempotent batch ingestion with provenance tracking, deduplication, and synthetic guard.
    """
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "EMPTY_BATCH", "message": "Ingestion batch items cannot be empty"},
        )

    res = ingestion_service.ingest_batch(
        workspace_id=tenant.workspace_id,
        items=payload.items,
        actor_user_id=tenant.user_id,
        is_production=payload.is_production,
        db=db,
    )
    return IngestBatchResponse(**res)

@router.post("/purge/{source_record_id}")
def purge_source_record(
    source_record_id: str,
    tenant: TenantContext = Depends(require_resolved_resource_action("evidence.purge")),
    db: Session = Depends(get_db),
):
    """
    T044: Data retention purge. Purges sensitive content fields and generates an audit event.
    """
    record = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == tenant.workspace_id,
        SourceRecord.id == source_record_id,
    ).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RECORD_NOT_FOUND")
    authorize_resource(
        tenant, "evidence.purge", resource_type="source_record",
        resource_id=record.id, workspace_id=record.workspace_id,
    )
    return ingestion_service.purge_record(
        workspace_id=tenant.workspace_id,
        source_record_id=source_record_id,
        actor_user_id=tenant.user_id,
        db=db,
    )

@router.get("/lineage/{source_record_id}")
def get_source_lineage(
    source_record_id: str,
    tenant: TenantContext = Depends(require_resolved_resource_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """
    T042: Retrieve multi-source provenance and lineage for a canonical source record.
    """
    record = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == tenant.workspace_id,
        SourceRecord.id == source_record_id,
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RECORD_NOT_FOUND", "message": f"SourceRecord {source_record_id} not found"},
        )

    authorize_resource(
        tenant, "evidence.read", resource_type="source_record",
        resource_id=record.id, workspace_id=record.workspace_id,
    )

    observations_out = []
    for obs in record.observations:
        observations_out.append({
            "observation_id": obs.observation_id,
            "provider_id": obs.provider_id,
            "observed_at": obs.observed_at.isoformat(),
            "rights_basis": obs.rights_basis,
            "retention_days": obs.retention_days,
            "is_purged": obs.is_purged,
        })

    snapshots_out = []
    for snap in record.metric_snapshots:
        snapshots_out.append({
            "observation_id": snap.observation_id,
            "observed_at": snap.observed_at.isoformat(),
            "view_count": snap.view_count, # Can be null (T041)
            "like_count": snap.like_count,
            "comment_count": snap.comment_count,
            "share_count": snap.share_count,
            "synthetic": snap.synthetic,
        })

    return {
        "canonical_record": {
            "id": record.id,
            "workspace_id": record.workspace_id,
            "canonical_url": record.canonical_url,
            "raw_external_id": record.raw_external_id,
            "title": record.title,
            "caption": record.caption,
            "synthetic": record.synthetic,
            "is_purged": record.is_purged,
            "purged_at": record.purged_at.isoformat() if record.purged_at else None,
            "created_at": record.created_at.isoformat(),
        },
        "observations_count": len(observations_out),
        "observations": observations_out,
        "snapshots_count": len(snapshots_out),
        "snapshots": snapshots_out,
    }

@router.get("/records")
def list_canonical_records(
    tenant: TenantContext = Depends(require_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """List canonical source records for the workspace."""
    records = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == tenant.workspace_id
    ).order_by(SourceRecord.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "canonical_url": r.canonical_url,
            "raw_external_id": r.raw_external_id,
            "title": r.title,
            "synthetic": r.synthetic,
            "is_purged": r.is_purged,
            "observations_count": len(r.observations),
            "snapshots_count": len(r.metric_snapshots),
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]

```
## sin_content_api/src/modules/research/router.py — SHA256 09B2FECABF61A2B388107726DF5B9E01E58AD3191FFD4A66E582CE0461867AB5
```
"""
SIN Content Intelligence - Research, Query Planning & Gold Sets Router (P05)
"""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_actions,
    require_resolved_resource_action,
    require_resolved_resource_actions,
)
from src.models.entities import BrandBriefVersion, ResearchRun
from .query_planner import ResearchRequest, ResearchPlan, query_planner
from .gold_evaluator import gold_manager, GoldCandidateItem
from .taxonomy import AUDIENCE_NEED_TAXONOMY

router = APIRouter(prefix="/v1/research", tags=["Research & Query Planning"])

@router.get("/taxonomy")
def get_taxonomy(tenant: TenantContext = Depends(require_action("research.read"))):
    """Retrieve standard Audience Need Taxonomy & Intent Groups."""
    return AUDIENCE_NEED_TAXONOMY

@router.post("/plans", response_model=ResearchPlan)
def create_research_plan(
    payload: ResearchRequest,
    tenant: TenantContext = Depends(require_resolved_resource_actions("research.run", "brief.read")),
    db: Session = Depends(get_db),
):
    """
    T050 & T052: Generate a deterministic, brand-safe ResearchPlan.
    Enforces negative keyword exclusion and quota/budget ceilings.
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == tenant.workspace_id,
        BrandBriefVersion.id == payload.brief_version_id,
    ).first()

    if not brief:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "BRIEF_NOT_FOUND", "message": f"Brand brief {payload.brief_version_id} not found in workspace"},
        )

    authorize_resource(
        tenant, "brief.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_resource(
        tenant, "research.run", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )

    # Generate deterministic plan
    plan = query_planner.generate_plan(brief=brief, request=payload)

    # Save ResearchRun record to database
    run = ResearchRun(
        workspace_id=tenant.workspace_id,
        brief_version_id=brief.id,
        status="PLANNED",
        plan_json=plan.model_dump_json(),
    )
    db.add(run)
    db.commit()

    return plan

@router.get("/plans/{run_id}")
def get_research_plan(
    run_id: str,
    tenant: TenantContext = Depends(require_resolved_resource_action("research.read")),
    db: Session = Depends(get_db),
):
    """Retrieve saved research plan by run ID."""
    run = db.query(ResearchRun).filter(
        ResearchRun.workspace_id == tenant.workspace_id,
        ResearchRun.id == run_id,
    ).first()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RUN_NOT_FOUND", "message": f"Research run {run_id} not found"},
        )

    authorize_resource(
        tenant, "research.read", resource_type="research_run",
        resource_id=run.id, workspace_id=run.workspace_id,
    )

    return json.loads(run.plan_json)

@router.get("/gold-sets")
def list_gold_datasets(tenant: TenantContext = Depends(require_action("research.read"))):
    """T051: List available human-reviewed gold benchmark datasets."""
    datasets = gold_manager.get_all_datasets()
    summaries = []
    for bid in datasets:
        summaries.append(gold_manager.get_summary(bid))
    return summaries

@router.get("/gold-sets/{brief_id}", response_model=List[GoldCandidateItem])
def get_gold_dataset_candidates(
    brief_id: str,
    tenant: TenantContext = Depends(require_resolved_resource_action("research.read")),
    db: Session = Depends(get_db),
):
    """T051: Retrieve human-annotated gold candidates for a specific brief."""
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == tenant.workspace_id,
        BrandBriefVersion.id == brief_id,
    ).first()
    if not brief:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GOLD_SET_NOT_FOUND")
    authorize_resource(
        tenant, "research.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    candidates = gold_manager.get_brief_candidates(brief_id)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "GOLD_SET_NOT_FOUND", "message": f"Gold set for brief {brief_id} not found"},
        )
    return candidates

@router.get("/gold-sets/{brief_id}/summary")
def get_gold_dataset_summary(
    brief_id: str,
    tenant: TenantContext = Depends(require_resolved_resource_action("research.read")),
    db: Session = Depends(get_db),
):
    """Retrieve evaluation summary metrics for a gold dataset."""
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == tenant.workspace_id,
        BrandBriefVersion.id == brief_id,
    ).first()
    if not brief:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GOLD_SET_NOT_FOUND")
    authorize_resource(
        tenant, "research.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    summary = gold_manager.get_summary(brief_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "GOLD_SET_NOT_FOUND", "message": f"Gold set for brief {brief_id} not found"},
        )
    return summary

```
## sin_content_api/src/modules/retrieval/router.py — SHA256 AA51993FE7CF7F4141E568EE47260C1EC356F6A0AD71ACBDED5D4269CDB6E562
```
# FastAPI Router cho Module Retrieval & Explicit Scoring (P07)
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_action,
    authorize_resource,
    require_action,
    require_resolved_resource_actions,
)
from src.models.entities import BrandBriefVersion
from src.schemas.contracts import (
    ScoringWeightsContract,
    CandidateScoreRequest,
    CandidateScoreResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    GoldEvaluationResponse
)
from src.modules.retrieval.ranking_service import ranking_service

router = APIRouter(prefix="/v1/retrieval", tags=["Retrieval, Filters & Explicit Scoring (P07)"])

@router.get("/weights", response_model=ScoringWeightsContract)
def get_scoring_weights(tenant: TenantContext = Depends(require_action("research.read"))):
    """
    Lay ma tran trong so tuong minh co dinh (T070).
    Phu hop khan gia 30%, Bang chung quan sat 25%, Muc tieu thuong hieu 20%,
    Tinh doc dao 15%, Tinh kha thi san xuat 10%. Tong = 100%.
    """
    weights = ranking_service.get_scoring_weights()
    return ScoringWeightsContract(**weights)

@router.post("/score", response_model=CandidateScoreResponse)
def score_candidate(
    payload: CandidateScoreRequest,
    tenant: TenantContext = Depends(require_resolved_resource_actions("research.run", "brief.read")),
    db: Session = Depends(get_db)
):
    """
    Cham diem tuong minh 5 thanh phan cho 1 ung vien so voi brief da duyet (T070, T071, T073).
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == tenant.workspace_id,
        BrandBriefVersion.id == payload.brief_version_id,
    ).first()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RESOURCE_NOT_FOUND")
    authorize_resource(
        tenant, "brief.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_resource(
        tenant, "research.run", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    try:
        res = ranking_service.score_candidate(
            db=db,
            workspace_id=tenant.workspace_id,
            data=payload
        )
        return CandidateScoreResponse(**res)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}
        )

@router.post("/search", response_model=HybridSearchResponse)
def search_hybrid(
    payload: HybridSearchRequest,
    tenant: TenantContext = Depends(require_resolved_resource_actions("research.run", "brief.read", "evidence.read")),
    db: Session = Depends(get_db)
):
    """
    Tim kiem lai (Bo loc cau truc + Full-text + Semantic) va xep hang ung vien.
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == tenant.workspace_id,
        BrandBriefVersion.id == payload.brief_version_id,
    ).first()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RESOURCE_NOT_FOUND")
    for action_key in ("brief.read", "research.run"):
        authorize_resource(
            tenant, action_key, resource_type="brand_brief",
            resource_id=brief.id, workspace_id=brief.workspace_id,
        )
    authorize_action(tenant, "evidence.read")
    try:
        res = ranking_service.search_hybrid(
            db=db,
            workspace_id=tenant.workspace_id,
            data=payload
        )
        return HybridSearchResponse(**res)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}
        )

@router.post("/evaluate-gold", response_model=GoldEvaluationResponse)
def evaluate_gold_set(
    dataset_name: str = Query("bento_box_gold.json"),
    tenant: TenantContext = Depends(require_action("research.run")),
):
    """
    Danh gia do chinh xac Top 10 (Precision@10 >= 80%) tren tap du lieu vang (T072).
    """
    try:
        res = ranking_service.evaluate_gold_dataset(dataset_name=dataset_name)
        return GoldEvaluationResponse(**res)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "GOLD_SET_NOT_FOUND", "message": str(e)}
        )

```
## sin_content_api/src/modules/scripts/router.py — SHA256 D151CD1FE4F6830A8A7B0C0916F976E8D2DA39F8CCDC4E7B71DEE50130A1E188
```
# Router API cho Pha P09: Script Drafting & Fact-Checking (/v1/scripts)
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_actions,
)
from src.schemas.contracts import (
    ScriptDraftCreate, ScriptDraftEditRequest, ScriptDraftOut,
    ScriptReviewRequest
)
from src.modules.scripts.script_service import script_service

router = APIRouter(prefix="/v1/scripts", tags=["Script Drafting & Fact-Checking"])

@router.post("", response_model=ScriptDraftOut)
def create_script(
    payload: ScriptDraftCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_actions("script.create", "ideas.read"))
):
    """
    Tao moi mot ban thao kich ban phan canh dua tren IdeaCard da duyet (T093).
    Tu dong kiem tra dung sai thoi luong va doi soat tuyen bo AllowedFact.
    """
    return script_service.create_script_draft(db, tenant.workspace_id, tenant.user_id, payload)

@router.get("", response_model=List[ScriptDraftOut])
def list_scripts(
    idea_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("script.read"))
):
    """
    Lay danh sach ban thao kich ban trong workspace.
    """
    return script_service.list_scripts(db, tenant.workspace_id, idea_id, status, limit)

@router.get("/{script_id}", response_model=ScriptDraftOut)
def get_script(
    script_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("script.read"))
):
    """
    Lay chi tiet kich ban kem danh sach phan canh va trang thai kiem dinh tuyen bo.
    """
    return script_service.get_script(db, tenant.workspace_id, script_id)

@router.post("/{script_id}/approve", response_model=ScriptDraftOut)
def approve_script(
    script_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("script.approve_final"))
):
    """
    Phe duyet kich ban:
    Bat buoc 100% tuyen bo dinh luong phai khop AllowedFact (T091).
    Tu choi phe duyet va tra ve ma loi neu con tuyen bo chua duoc kiem dinh (T090).
    """
    return script_service.approve_script(db, tenant.workspace_id, tenant.user_id, script_id)

@router.post("/{script_id}/edit", response_model=ScriptDraftOut)
def edit_script(
    script_id: str,
    payload: ScriptDraftEditRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("script.edit"))
):
    """
    Chinh sua kich ban:
    Neu kich ban da duoc phe duyet (APPROVED), tu dong sinh phien ban nhap moi bat bien (version = version + 1),
    chuyen phien ban cu sang SUPERSEDED (T092).
    """
    return script_service.edit_script(db, tenant.workspace_id, tenant.user_id, script_id, payload)

@router.post("/{script_id}/reject", response_model=ScriptDraftOut)
def reject_script(
    script_id: str,
    payload: ScriptReviewRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("script.edit"))
):
    """
    Tu choi kich ban kem ly do cua nguoi duyet.
    """
    return script_service.reject_script(db, tenant.workspace_id, tenant.user_id, script_id, payload)

```
## sin_content_api/src/modules/sources/router.py — SHA256 5C4756CBCE4865561EB463E3076245266C0645E50CB801CF638FB4BCBBC4FFDC
```
"""
SIN Content Intelligence - Sources Router
Manages Source Providers, Compliance Verification, Search & Ingestion.
"""
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import TenantContext, require_action
from src.models.entities import SourceRecord, MetricSnapshot, QuarantineRecord, AuditEvent
from .provider_protocol import (
    ProviderCapabilities,
    ProviderCapabilityStatus,
    ProviderStatus,
    SearchQuery,
    Budget,
    AuthContext,
    ProviderError,
    Page,
    ProviderPost,
)
from .provider_registry import default_registry, BANNED_SOURCES

router = APIRouter(prefix="/v1/sources", tags=["Data Source Providers"])

class SearchRequest(BaseModel):
    provider_id: str
    query: SearchQuery
    budget: Optional[Budget] = None
    oauth_token: Optional[str] = None

class CustomerImportRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)

class CustomerImportResponse(BaseModel):
    total: int
    valid_count: int
    quarantined_count: int
    status: ProviderStatus

@router.get("/providers", response_model=List[ProviderCapabilities])
def list_providers(tenant: TenantContext = Depends(require_action("research.read"))):
    """List all registered source providers and their capabilities."""
    return default_registry.list_capabilities()

@router.get("/providers/{provider_id}/capabilities", response_model=ProviderCapabilities)
def get_provider_capabilities(
    provider_id: str,
    tenant: TenantContext = Depends(require_action("research.read"))
):
    """Retrieve capabilities for a specific provider."""
    # Check if banned
    if provider_id.lower() in BANNED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ProviderStatus.RIGHTS_NOT_GRANTED,
                "provider_id": provider_id,
                "message": BANNED_SOURCES[provider_id.lower()],
            }
        )

    provider_or_err = default_registry.get_provider(provider_id)
    if isinstance(provider_or_err, ProviderError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": provider_or_err.error_code,
                "provider_id": provider_id,
                "message": provider_or_err.message_safe,
            }
        )
    return provider_or_err.capabilities()

@router.post("/search")
def search_sources(
    payload: SearchRequest,
    tenant: TenantContext = Depends(require_action("research.run")),
    db: Session = Depends(get_db),
):
    """
    Search content via a provider.
    Enforces compliance, budget limits, rate limiting, and circuit breaker.
    """
    auth = AuthContext(
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        oauth_token=payload.oauth_token,
    )
    budget = payload.budget or Budget()

    result = default_registry.execute_search(
        provider_id=payload.provider_id,
        query=payload.query,
        auth=auth,
        budget=budget,
    )

    if isinstance(result, ProviderError):
        # Map provider error to HTTP error status
        status_map = {
            ProviderStatus.RIGHTS_NOT_GRANTED: status.HTTP_403_FORBIDDEN,
            ProviderStatus.FORBIDDEN: status.HTTP_403_FORBIDDEN,
            ProviderStatus.AUTH_FAILED: status.HTTP_401_UNAUTHORIZED,
            ProviderStatus.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
            ProviderStatus.BUDGET_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
            ProviderStatus.UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
            ProviderStatus.NO_APPROVED_SOURCE: status.HTTP_404_NOT_FOUND,
            ProviderStatus.INVALID_DATA: status.HTTP_422_UNPROCESSABLE_ENTITY,
        }
        http_code = status_map.get(result.error_code, status.HTTP_400_BAD_REQUEST)
        
        # Log audit if access denied or banned tool requested
        if result.error_code in [ProviderStatus.RIGHTS_NOT_GRANTED, ProviderStatus.FORBIDDEN]:
            audit = AuditEvent(
                workspace_id=tenant.workspace_id,
                actor_id=tenant.user_id,
                event_type="UNAPPROVED_SOURCE_DENIED",
                details=f"Provider: {payload.provider_id}, Error: {result.message_safe}",
            )
            db.add(audit)
            db.commit()

        raise HTTPException(
            status_code=http_code,
            detail=result.model_dump(),
        )

    return result

@router.post("/customer-import", response_model=CustomerImportResponse)
def import_customer_data(
    payload: CustomerImportRequest,
    tenant: TenantContext = Depends(require_action("evidence.import")),
    db: Session = Depends(get_db),
):
    """
    Ingests customer-provided datasets (JSON).
    Validates records: isolates malformed items into quarantine; stages valid items.
    """
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "EMPTY_PAYLOAD", "message": "Import items array cannot be empty"},
        )

    provider_or_err = default_registry.get_provider("customer_import")
    if isinstance(provider_or_err, ProviderError):
        raise HTTPException(status_code=500, detail=provider_or_err.model_dump())

    adapter = provider_or_err
    import_res = adapter.import_batch(tenant.workspace_id, payload.items)

    # Persist quarantined records to DB for audit and provenance
    quarantined_items = adapter.get_quarantined_records(tenant.workspace_id)
    for q in quarantined_items:
        # Check if already saved
        existing = db.query(QuarantineRecord).filter(
            QuarantineRecord.id == q["quarantine_id"]
        ).first()
        if not existing:
            qr = QuarantineRecord(
                id=q["quarantine_id"],
                workspace_id=tenant.workspace_id,
                provider_id="customer_import",
                raw_payload_json=json.dumps(q["raw_payload"]),
                error_reason=q["error_reason"],
            )
            db.add(qr)

    # Persist valid records to DB
    for post in adapter._workspace_records.get(tenant.workspace_id, []):
        existing_sr = db.query(SourceRecord).filter(
            SourceRecord.workspace_id == tenant.workspace_id,
            SourceRecord.raw_external_id == post.external_id,
        ).first()
        if not existing_sr:
            sr = SourceRecord(
                workspace_id=tenant.workspace_id,
                provider_id="customer_import",
                raw_external_id=post.external_id,
                canonical_url=post.canonical_url,
                title=post.title,
                caption=post.text_excerpt,
                synthetic=post.synthetic,
                rights_basis="customer_supplied",
            )
            db.add(sr)
            db.flush()

            for m in post.metrics:
                ms = MetricSnapshot(
                    source_record_id=sr.id,
                    view_count=m.value if m.metric_name == "VIEW_COUNT" else None,
                    like_count=m.value if m.metric_name == "LIKE_COUNT" else None,
                    comment_count=m.value if m.metric_name == "COMMENT_COUNT" else None,
                    share_count=m.value if m.metric_name == "SHARE_COUNT" else None,
                    synthetic=post.synthetic,
                )
                db.add(ms)

    db.commit()

    return CustomerImportResponse(
        total=import_res["total"],
        valid_count=import_res["valid_count"],
        quarantined_count=import_res["quarantined_count"],
        status=import_res["status"],
    )

@router.get("/quarantine")
def list_quarantine_records(
    tenant: TenantContext = Depends(require_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """Retrieve list of quarantined records for the workspace."""
    records = db.query(QuarantineRecord).filter(
        QuarantineRecord.workspace_id == tenant.workspace_id
    ).order_by(QuarantineRecord.created_at.desc()).all()
    
    return [
        {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "provider_id": r.provider_id,
            "raw_payload": json.loads(r.raw_payload_json or "{}"),
            "error_reason": r.error_reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]

@router.get("/records")
def list_source_records(
    tenant: TenantContext = Depends(require_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """Retrieve list of saved source records for the workspace."""
    records = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == tenant.workspace_id
    ).order_by(SourceRecord.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "provider_id": r.provider_id,
            "raw_external_id": r.raw_external_id,
            "canonical_url": r.canonical_url,
            "title": r.title,
            "caption": r.caption,
            "synthetic": r.synthetic,
            "rights_basis": r.rights_basis,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]

```
## sin_content_api/src/modules/understanding/router.py — SHA256 A257F28FF9E705C71B4F8EF6F1819BE5EFFCBAF1603661B90CDD56F197F2BDC2
```
# FastAPI Router cho Module Understanding (P06)
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_actions,
    require_resolved_resource_actions,
)
from src.models.entities import SourceRecord
from src.schemas.contracts import (
    ExtractSignalsRequest,
    ExtractSignalsResponse,
    ClusterRequest,
    ClusterResponse,
    TopicClusterOut,
    NeedSignalOut,
    AsrStatusResponse,
    AsrEvaluateRequest,
    AsrEvaluateResponse
)
from src.modules.understanding.service import understanding_service

router = APIRouter(prefix="/v1/understanding", tags=["Understanding & Signals (P06)"])

@router.post("/extract-signals", response_model=ExtractSignalsResponse)
def extract_signals(
    payload: ExtractSignalsRequest,
    tenant: TenantContext = Depends(require_resolved_resource_actions("research.run", "evidence.read")),
    db: Session = Depends(get_db)
):
    """
    Tiep nhan trich doan/binh luan, kiem tra Prompt Injection,
    boc tach tin hieu nhu cau va luu tru co bao toan trich dan goc.
    """
    source_record = db.query(SourceRecord).filter(
        SourceRecord.id == payload.excerpt.source_record_id,
        SourceRecord.workspace_id == tenant.workspace_id,
    ).first()
    if source_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RESOURCE_NOT_FOUND")
    authorize_resource(
        tenant, "evidence.read", resource_type="source_record",
        resource_id=source_record.id, workspace_id=source_record.workspace_id,
    )
    authorize_resource(
        tenant, "research.run", resource_type="source_record",
        resource_id=source_record.id, workspace_id=source_record.workspace_id,
    )
    try:
        excerpt, signals, has_injection_risk, warning = understanding_service.extract_and_store_signals(
            db=db,
            workspace_id=tenant.workspace_id,
            data=payload.excerpt
        )
        return ExtractSignalsResponse(
            excerpt=excerpt,
            signals=signals,
            prompt_injection_detected=has_injection_risk,
            warning_notes=warning
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}
        )

@router.post("/cluster", response_model=ClusterResponse)
def run_clustering(
    payload: ClusterRequest,
    tenant: TenantContext = Depends(require_actions("research.run", "evidence.read")),
    db: Session = Depends(get_db)
):
    """
    Gom cum chu de cho cac tin hieu trong workspace (T060).
    Co the bat/tat bang payload.enabled.
    """
    clusters = understanding_service.run_clustering(
        db=db,
        workspace_id=tenant.workspace_id,
        enabled=payload.enabled,
        intent_group=payload.intent_group
    )
    return ClusterResponse(
        enabled=payload.enabled,
        total_clusters=len(clusters),
        clusters=clusters
    )

@router.get("/clusters", response_model=List[TopicClusterOut])
def get_clusters(
    tenant: TenantContext = Depends(require_actions("research.read", "evidence.read")),
    db: Session = Depends(get_db)
):
    """Lay danh sach cac cum chu de da gom trong workspace."""
    return understanding_service.get_clusters(db=db, workspace_id=tenant.workspace_id)

@router.get("/signals", response_model=List[NeedSignalOut])
def get_signals(
    intent_group: Optional[str] = Query(None),
    need_category: Optional[str] = Query(None),
    tenant: TenantContext = Depends(require_actions("research.read", "evidence.read")),
    db: Session = Depends(get_db)
):
    """Truy van danh sach tin hieu nhu cau trong workspace."""
    return understanding_service.get_signals(
        db=db,
        workspace_id=tenant.workspace_id,
        intent_group=intent_group,
        need_category=need_category
    )

@router.get("/asr-status", response_model=AsrStatusResponse)
def get_asr_status(
    licensed_audio_count: int = Query(0, ge=0),
    tenant: TenantContext = Depends(require_action("research.read")),
):
    """
    Kiem tra tinh trang nang luc ASR tieng Viet (T063).
    Tra ve UNVERIFIED neu chua co tap am thanh duoc cap phep.
    """
    status_info = understanding_service.check_asr_status(licensed_audio_count=licensed_audio_count)
    return AsrStatusResponse(**status_info)

@router.post("/asr-evaluate", response_model=AsrEvaluateResponse)
def evaluate_asr(
    payload: AsrEvaluateRequest,
    tenant: TenantContext = Depends(require_action("research.run")),
):
    """
    Danh gia do chinh xac (WER va terminology accuracy) tren tap am thanh duoc cap phep (T063).
    """
    try:
        eval_result = understanding_service.evaluate_asr(
            references=payload.reference_transcripts,
            hypotheses=payload.hypothesis_transcripts,
            domain_terms=payload.domain_terms
        )
        return AsrEvaluateResponse(**eval_result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_EVALUATION_INPUT", "message": str(e)}
        )

```
## sin_content_api/src/modules/workspaces/router.py — SHA256 11B933BA18B64436F46A1E4AF949ADFB0139912727D3857E6A3B02032F061745
```
# Router khoi tao va quan ly Workspace
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth.tenancy import TenantContext, authorize_resource, require_action
from src.models.entities import Workspace, User, Membership
from src.schemas.contracts import WorkspaceCreate, WorkspaceOut

router = APIRouter(prefix="/v1/workspaces", tags=["Workspaces"])

@router.get("", response_model=List[WorkspaceOut])
def list_workspaces(
    ctx: TenantContext = Depends(require_action("workspace.read")),
    db: Session = Depends(get_db),
):
    workspace = db.query(Workspace).filter(Workspace.id == ctx.workspace_id).first()
    if workspace is None:
        return []
    authorize_resource(
        ctx, "workspace.read", resource_type="workspace", resource_id=workspace.id,
        workspace_id=workspace.id,
    )
    return [workspace]

@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    ctx: TenantContext = Depends(require_action("workspace.create")),
    db: Session = Depends(get_db),
):
    existing = db.query(Workspace).filter(Workspace.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="WORKSPACE_SLUG_EXISTS")
        
    ws = Workspace(name=payload.name, slug=payload.slug)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws

```
