# Hợp đồng DTO và schema Pydantic V2 cho phân quyền doanh nghiệp Baha Group.
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

# --- Nền tảng và trường chung ---
class ErrorPayload(BaseModel):
    error_code: str
    message: str
    correlation_id: Optional[str] = None
    policy_version: str = "1.0.0"


class StrictRequest(BaseModel):
    """Từ chối trường lạ để ngăn gửi thừa dữ liệu đặc quyền."""

    model_config = ConfigDict(extra="forbid")

# --- Không gian làm việc và thành viên ---
class WorkspaceCreate(StrictRequest):
    name: StrictStr
    slug: StrictStr
    type: Literal["ENTERPRISE", "AGENCY", "SUBSIDIARY"] = "ENTERPRISE"

class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    type: str
    status: str
    created_at: datetime

class MemberInviteRequest(StrictRequest):
    email: StrictStr
    full_name: StrictStr
    initial_role_code: StrictStr = "GUEST"
    scope_type: Literal["WORKSPACE", "DEPARTMENT", "TEAM", "PROJECT", "OWN"] = "WORKSPACE"
    scope_id: Optional[StrictStr] = None

class MemberOut(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    email: str
    full_name: Optional[str] = None
    status: str
    joined_at: datetime
    roles: List[str] = []

# --- Cơ cấu tổ chức ---
class OrgUnitCreate(StrictRequest):
    name: StrictStr
    type: Literal["COMPANY", "DEPARTMENT", "TEAM"] = "DEPARTMENT"
    parent_id: Optional[StrictStr] = None

class OrgUnitOut(BaseModel):
    id: str
    workspace_id: str
    parent_id: Optional[str] = None
    type: str
    name: str
    status: str
    created_at: datetime

class ReportingLineCreate(StrictRequest):
    manager_membership_id: StrictStr
    report_membership_id: StrictStr
    org_unit_id: Optional[StrictStr] = None

class ReportingLineOut(BaseModel):
    id: str
    workspace_id: str
    manager_membership_id: str
    report_membership_id: str
    org_unit_id: Optional[str] = None
    valid_from: datetime
    valid_until: Optional[datetime] = None

# --- Vai trò và quyền ---
class RoleOut(BaseModel):
    id: str
    code: str
    name: str
    is_template: bool
    is_custom: bool
    status: str

class PermissionOut(BaseModel):
    id: str
    action_key: str
    risk_tier: str
    is_immutable: bool
    description: Optional[str] = None

class RoleAssignmentRequest(StrictRequest):
    grantee_membership_id: StrictStr
    role_code: StrictStr
    scope_type: Literal["WORKSPACE", "DEPARTMENT", "TEAM", "PROJECT", "OWN"] = "WORKSPACE"
    scope_id: Optional[StrictStr] = None
    valid_until: Optional[datetime] = None
    reason: Optional[StrictStr] = None

    @field_validator("valid_until")
    @classmethod
    def valid_until_must_have_timezone(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Thời hạn phải có múi giờ rõ ràng.")
        return value

class RoleAssignmentOut(BaseModel):
    id: str
    workspace_id: str
    membership_id: str
    role_code: str
    scope_type: str
    scope_id: Optional[str] = None
    valid_from: datetime
    valid_until: Optional[datetime] = None
    status: str

class DelegationRequest(StrictRequest):
    grantee_membership_id: StrictStr
    allowed_actions: List[StrictStr] = Field(min_length=1, max_length=10)
    expires_at: datetime
    reason: Optional[StrictStr] = None

    @field_validator("expires_at")
    @classmethod
    def expires_at_must_have_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời hạn phải có múi giờ rõ ràng.")
        return value

class DelegationOut(BaseModel):
    id: str
    workspace_id: str
    grantor_membership_id: str
    grantee_membership_id: str
    allowed_actions: List[str]
    starts_at: datetime
    expires_at: datetime
    status: str

# --- Đánh giá chính sách ---
class EvaluateRequest(StrictRequest):
    action_key: StrictStr
    resource_id: Optional[StrictStr] = None

class EvaluateResponse(BaseModel):
    allowed: bool
    decision: str  # "ALLOW" | "DENY".
    reason_code: str
    internal_reason: str
    policy_version: str

# --- Phê duyệt nhiều cấp ---
class ApprovalRunCreate(StrictRequest):
    artifact_type: StrictStr
    artifact_id: StrictStr
    expected_version: StrictInt = Field(gt=0)


class ApprovalDecisionRequest(StrictRequest):
    step_id: StrictStr
    result: Literal["APPROVED", "REJECTED", "CHANGES_REQUESTED"]
    artifact_version: StrictInt = Field(gt=0)
    content_hash: StrictStr = Field(min_length=64, max_length=64)
    reason: Optional[StrictStr] = Field(default=None, max_length=2000)

class ApprovalStepOut(BaseModel):
    id: str
    stage_key: str
    allowed_role_or_assignee: str
    status: str
    ordinal: int

class ApprovalRunOut(BaseModel):
    id: str
    workspace_id: str
    artifact_type: str
    artifact_id: str
    artifact_version: int
    content_hash: str
    status: str
    created_by: str
    created_at: datetime
    steps: List[ApprovalStepOut] = []

# --- Grant tác vụ worker ---
class DelegatedJobGrantRequest(StrictRequest):
    job_id: StrictStr = Field(min_length=1, max_length=100)
    target_resource: StrictStr = Field(min_length=1, max_length=255)
    allowed_actions: List[StrictStr] = Field(min_length=1, max_length=10)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def expires_at_must_have_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời hạn phải có múi giờ rõ ràng.")
        return value

class DelegatedJobGrantOut(BaseModel):
    id: str
    workspace_id: str
    job_id: str
    initiating_membership_id: str
    target_resource: str
    resource_type: str
    artifact_version: int
    content_hash: str
    policy_version: str
    allowed_actions: List[str]
    expires_at: datetime
    status: str

class WorkerRecheckRequest(StrictRequest):
    job_id: StrictStr = Field(min_length=1, max_length=100)
    action_key: StrictStr = Field(min_length=1, max_length=100)

class WorkerRecheckResponse(BaseModel):
    allowed: bool
    job_id: str
    action_key: str
    status: str
    reason: str
    workspace_id: Optional[StrictStr] = None
    target_resource: Optional[StrictStr] = None
    resource_type: Optional[StrictStr] = None
    artifact_version: Optional[StrictInt] = None
    content_hash: Optional[StrictStr] = None
    policy_version: Optional[StrictStr] = None

# --- Sự kiện kiểm toán ---
class AuditEventOut(BaseModel):
    id: str
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    actor_type: str
    action_key: str
    resource_type: Optional[str] = None
    decision: str
    internal_reason: str
    policy_version: str
    timestamp: datetime
