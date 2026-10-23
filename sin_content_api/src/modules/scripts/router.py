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
    require_resolved_resource_action,
)
from src.schemas.contracts import (
    ScriptDraftCreate, ScriptDraftEditRequest, ScriptDraftOut,
    ScriptReviewRequest
)
from src.models.entities import ScriptDraftVersion
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
    tenant: TenantContext = Depends(require_resolved_resource_action("script.approve_final"))
):
    """
    Phe duyet kich ban:
    Bat buoc 100% tuyen bo dinh luong phai khop AllowedFact (T091).
    Tu choi phe duyet va tra ve ma loi neu con tuyen bo chua duoc kiem dinh (T090).
    """
    script = db.query(ScriptDraftVersion).filter(
        ScriptDraftVersion.id == script_id,
        ScriptDraftVersion.workspace_id == tenant.workspace_id
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="ScriptDraftVersion not found in workspace")

    authorize_resource(
        tenant,
        "script.approve_final",
        resource_type="script_draft",
        resource_id=script.id,
        workspace_id=script.workspace_id,
        creator_id=script.created_by_user_id,
        require_creator=True,
    )
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
