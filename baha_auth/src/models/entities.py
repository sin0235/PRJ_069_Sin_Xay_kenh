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


class LocalPasswordCredential(Base):
    __tablename__ = "local_password_credentials"

    user_id = Column(String(36), ForeignKey("global_users.id", ondelete="CASCADE"), primary_key=True)
    password_hash = Column(String(512), nullable=False)

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
