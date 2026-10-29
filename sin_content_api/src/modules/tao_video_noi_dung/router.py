from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from src.auth.tenancy import (
    TenantContext,
    owner_direct_creation,
    authorize_resource,
    require_action,
    require_resolved_resource_action,
)
from src.database import get_db
from baha_auth.src.policy.evaluator import e2e_test_self_approval_enabled
from .contracts import ContentVideoPlanResponse, ContentVideoRunResponse, CreatePlanRequest, CreateRunRequest, ResumeRunRequest, ReconcileShotRequest, RerenderRunRequest, RetryRunRequest, UpdateStoryboardRequest
from .runner import reconcile_shot
from .service import approve_plan, create_plan, create_run, get_latest_history, get_plan, get_run, rerender_run, resume_run, retry_run, update_plan


router = APIRouter(prefix="/v1/media/projects/{project_id}/content-video", tags=["Content Video Production"])


@router.post("/plans", response_model=ContentVideoPlanResponse, status_code=201)
def create_content_video_plan(
    project_id: str,
    payload: CreatePlanRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    return create_plan(db, project_id, tenant.workspace_id, tenant.user_id, payload)


@router.get("/plans/{plan_id}", response_model=ContentVideoPlanResponse)
def read_content_video_plan(
    project_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    return get_plan(db, project_id, plan_id, tenant.workspace_id)


@router.put("/plans/{plan_id}", response_model=ContentVideoPlanResponse)
def update_content_video_plan(
    project_id: str,
    plan_id: str,
    payload: UpdateStoryboardRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    return update_plan(db, project_id, plan_id, tenant.workspace_id, tenant.user_id, payload.storyboard)


@router.get("/history")
def read_content_video_history(
    project_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    return get_latest_history(db, project_id, tenant.workspace_id)


@router.post("/plans/{plan_id}/approve", response_model=ContentVideoPlanResponse)
def approve_content_video_plan(
    project_id: str,
    plan_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_action("media.approve")),
):
    plan = get_plan(db, project_id, plan_id, tenant.workspace_id)
    allow_self_approval = e2e_test_self_approval_enabled() or getattr(tenant, "dev_auth_bypass", False)
    if not allow_self_approval:
        authorize_resource(
            tenant,
            "media.approve",
            resource_type="content_video_plan",
            resource_id=plan.id,
            workspace_id=tenant.workspace_id,
            creator_id=plan.created_by,
            artifact_version=plan.revision,
            content_hash=plan.storyboard_sha256,
            project_id=project_id,
            require_creator=True,
        )
    return approve_plan(
        db, project_id, plan_id, tenant.workspace_id, tenant.user_id,
        allow_self_approval=allow_self_approval,
    )


@router.post("/runs", response_model=ContentVideoRunResponse, status_code=202)
def create_content_video_run(
    project_id: str,
    payload: CreateRunRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    return create_run(db, project_id, tenant.workspace_id, tenant.user_id, payload,
        allow_direct_creation=owner_direct_creation(tenant))


@router.get("/runs/{run_id}", response_model=ContentVideoRunResponse)
def read_content_video_run(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    return get_run(db, project_id, run_id, tenant.workspace_id)


@router.post("/runs/{run_id}/resume", response_model=ContentVideoRunResponse, status_code=202)
def resume_content_video_run(
    project_id: str,
    run_id: str,
    payload: ResumeRunRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    return resume_run(db, project_id, run_id, tenant.workspace_id, profile_id=payload.flow_profile_id if payload else None)


@router.post("/runs/{run_id}/rerender", response_model=ContentVideoRunResponse, status_code=202)
def rerender_content_video_run(
    project_id: str,
    run_id: str,
    payload: RerenderRunRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    return rerender_run(db, project_id, run_id, tenant.workspace_id, payload.include_subtitles)


@router.post("/runs/{run_id}/retry", response_model=ContentVideoRunResponse, status_code=202)
def retry_content_video_run(
    project_id: str,
    run_id: str,
    payload: RetryRunRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    return retry_run(db, project_id, run_id, tenant.workspace_id, tenant.user_id, payload)


@router.post("/runs/{run_id}/reconcile", response_model=ContentVideoRunResponse)
def reconcile_content_video_run(
    project_id: str,
    run_id: str,
    payload: ReconcileShotRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    reconcile_shot(db, project_id, run_id, tenant.workspace_id, tenant.user_id, payload)
    return get_run(db, project_id, run_id, tenant.workspace_id)
