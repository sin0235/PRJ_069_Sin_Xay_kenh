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
