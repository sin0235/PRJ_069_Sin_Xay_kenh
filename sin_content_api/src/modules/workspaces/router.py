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
