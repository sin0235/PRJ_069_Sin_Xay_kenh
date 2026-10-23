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
