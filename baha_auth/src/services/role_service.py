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
