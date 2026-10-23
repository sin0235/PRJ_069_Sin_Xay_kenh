"""Bộ đánh giá phân quyền mặc định từ chối dựa trên actor và resource đáng tin cậy."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from baha_auth.src.config import settings
from baha_auth.src.policy.registry import registry


@dataclass
class ActorContext:
    user_id: str
    workspace_id: str
    membership_id: str
    membership_status: str
    roles: List[Dict[str, Any]]
    department_ids: List[str]
    team_ids: List[str]
    user_status: str = "ACTIVE"
    workspace_status: str = "ACTIVE"


@dataclass
class ResourceContext:
    workspace_id: str
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    org_unit_id: Optional[str] = None
    owner_id: Optional[str] = None
    creator_id: Optional[str] = None
    artifact_version: Optional[int] = None
    content_hash: Optional[str] = None
    project_id: Optional[str] = None
    brand_id: Optional[str] = None
    channel_id: Optional[str] = None


@dataclass
class AuthorizationDecision:
    allowed: bool
    decision: str
    reason_code: str
    internal_reason: str
    policy_version: str


def _deny(code: str, message: str) -> AuthorizationDecision:
    return AuthorizationDecision(False, "DENY", code, message, settings.policy_version)


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _active_grant(grant: Dict[str, Any], now: datetime) -> bool:
    if not grant.get("is_active", grant.get("assignment_status", "ACTIVE") == "ACTIVE"):
        return False
    if grant.get("assignment_status", "ACTIVE") != "ACTIVE":
        return False
    if grant.get("role_status", "ACTIVE") != "ACTIVE":
        return False
    starts_at = _utc(grant.get("valid_from"))
    expires_at = _utc(grant.get("valid_until"))
    return (starts_at is None or starts_at <= now) and (expires_at is None or expires_at > now)


def _assignment_scope_matches(
    grant: Dict[str, Any], actor: ActorContext, resource: Optional[ResourceContext]
) -> bool:
    scope_type = grant.get("scope_type", "WORKSPACE")
    scope_id = grant.get("scope_id")
    if scope_type == "WORKSPACE":
        return True
    if resource is None:
        return False
    if scope_type in {"DEPARTMENT", "TEAM"}:
        return bool(scope_id and resource.org_unit_id == scope_id)
    if scope_type == "PROJECT":
        return bool(scope_id and resource.project_id == scope_id)
    if scope_type == "OWN":
        return bool(
            (scope_id is None or scope_id == actor.user_id)
            and (resource.owner_id == actor.user_id or resource.creator_id == actor.user_id)
        )
    # Chưa có mô hình thành viên đáng tin cậy cho phạm vi thương hiệu, kênh, đối tượng hoặc nền tảng.
    return False


def _policy_scope_matches(
    policy_scope: str, grant: Dict[str, Any], actor: ActorContext, resource: Optional[ResourceContext]
) -> bool:
    if resource is None:
        return policy_scope == "WORKSPACE" and grant.get("scope_type", "WORKSPACE") == "WORKSPACE"

    if policy_scope == "WORKSPACE":
        return True
    if policy_scope == "DEPARTMENT":
        return bool(resource.org_unit_id and resource.org_unit_id in actor.department_ids)
    if policy_scope == "TEAM":
        return bool(resource.org_unit_id and resource.org_unit_id in actor.team_ids)
    if policy_scope == "PROJECT":
        # Quyền dự án cần được cấp đúng phạm vi dự án; phạm vi workspace quá rộng.
        return grant.get("scope_type") == "PROJECT" and bool(
            resource.project_id and grant.get("scope_id") == resource.project_id
        )
    if policy_scope == "OWN":
        return resource.owner_id == actor.user_id or resource.creator_id == actor.user_id
    return False


def evaluate_permission(
    actor: ActorContext,
    action_key: str,
    resource: Optional[ResourceContext] = None,
    conditions: Optional[Dict[str, Any]] = None,
) -> AuthorizationDecision:
    del conditions  # Điều kiện phải được nạp từ policy và resource tin cậy, không lấy từ client.
    if not actor.user_id or not actor.workspace_id or not actor.membership_id:
        return _deny("MISSING_TRUSTED_IDENTITY", "Thiếu user, workspace hoặc membership đã xác minh")
    if not registry.is_action_registered(action_key):
        return _deny("UNREGISTERED_ACTION", f"Action '{action_key}' chưa được đăng ký")
    if actor.membership_status != "ACTIVE" or actor.user_status != "ACTIVE" or actor.workspace_status != "ACTIVE":
        return _deny("INACTIVE_IDENTITY", "User, membership hoặc workspace không hoạt động")
    if resource is not None and resource.workspace_id != actor.workspace_id:
        return _deny("CROSS_TENANT_ACCESS_DENIED", "Resource thuộc workspace khác")

    action_lower = action_key.lower()
    if any(word in action_lower for word in ("approve", "review", "override")):
        if resource is None:
            return _deny("RESOURCE_CONTEXT_REQUIRED", "Phê duyệt cần ngữ cảnh tài nguyên đã xác minh")
        if not resource.owner_id and not resource.creator_id:
            return _deny("RESOURCE_ATTRIBUTION_REQUIRED", "Phê duyệt cần chủ sở hữu hoặc người tạo đã xác minh")
        interested_parties = {user_id for user_id in (resource.owner_id, resource.creator_id) if user_id}
        if actor.user_id in interested_parties:
            return _deny("SELF_FINAL_APPROVAL_DENIED", "Bên có lợi ích không được tự duyệt tài nguyên của mình")

    now = datetime.now(timezone.utc)
    for grant in actor.roles:
        if not _active_grant(grant, now):
            continue
        policy_scope = registry.get_role_action_scope(grant.get("role_code", ""), action_key)
        if policy_scope is None:
            continue
        if _policy_scope_matches(policy_scope, grant, actor, resource) and _assignment_scope_matches(grant, actor, resource):
            return AuthorizationDecision(
                True,
                "ALLOW",
                "AUTHORIZED",
                "Khớp role assignment đang hiệu lực trong phạm vi policy và assignment",
                settings.policy_version,
            )

    return _deny(
        "INSUFFICIENT_PERMISSIONS",
        f"Không có role assignment đang hiệu lực cho action '{action_key}' trong phạm vi resource yêu cầu",
    )
