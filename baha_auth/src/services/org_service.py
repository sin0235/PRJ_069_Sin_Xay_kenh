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
