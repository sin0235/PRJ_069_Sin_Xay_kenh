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
