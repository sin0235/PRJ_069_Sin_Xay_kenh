"""
SIN Content Intelligence - Research, Query Planning & Gold Sets Router (P05)
"""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_actions,
    require_resolved_resource_action,
    require_resolved_resource_actions,
)
from src.models.entities import BrandBriefVersion, ResearchRun
from .query_planner import ResearchRequest, ResearchPlan, query_planner
from .gold_evaluator import gold_manager, GoldCandidateItem
from .taxonomy import AUDIENCE_NEED_TAXONOMY

router = APIRouter(prefix="/v1/research", tags=["Research & Query Planning"])

@router.get("/taxonomy")
def get_taxonomy(tenant: TenantContext = Depends(require_action("research.read"))):
    """Retrieve standard Audience Need Taxonomy & Intent Groups."""
    return AUDIENCE_NEED_TAXONOMY

@router.post("/plans", response_model=ResearchPlan)
def create_research_plan(
    payload: ResearchRequest,
    tenant: TenantContext = Depends(require_resolved_resource_actions("research.run", "brief.read")),
    db: Session = Depends(get_db),
):
    """
    T050 & T052: Generate a deterministic, brand-safe ResearchPlan.
    Enforces negative keyword exclusion and quota/budget ceilings.
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == tenant.workspace_id,
        BrandBriefVersion.id == payload.brief_version_id,
    ).first()

    if not brief:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "BRIEF_NOT_FOUND", "message": f"Brand brief {payload.brief_version_id} not found in workspace"},
        )

    # P05-03: Bat buoc brief phai o trang thai APPROVED
    if getattr(brief, "status", None) != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "UNAPPROVED_BRIEF", "message": "Brand brief must be APPROVED before planning research runs"},
        )

    # P05-04: Validate va dong bo workspace_id
    if payload.workspace_id and payload.workspace_id != tenant.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "WORKSPACE_MISMATCH", "message": "payload.workspace_id does not match tenant workspace"},
        )
    payload.workspace_id = tenant.workspace_id

    authorize_resource(
        tenant, "brief.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_resource(
        tenant, "research.run", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )

    # Generate deterministic plan (P05-05: bat loi provider khong hop le)
    try:
        plan = query_planner.generate_plan(brief=brief, request=payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "INVALID_RESEARCH_REQUEST", "message": str(e)},
        )

    # P05-07: Dong nhat plan_id va ResearchRun.id de tra cuu GET /plans/{plan_id}
    run = ResearchRun(
        id=plan.plan_id,
        workspace_id=tenant.workspace_id,
        brief_version_id=brief.id,
        status="PLANNED",
        plan_json=plan.model_dump_json(),
    )
    db.add(run)
    db.commit()

    return plan

@router.get("/plans/{run_id}")
def get_research_plan(
    run_id: str,
    tenant: TenantContext = Depends(require_resolved_resource_action("research.read")),
    db: Session = Depends(get_db),
):
    """Retrieve saved research plan by run ID."""
    run = db.query(ResearchRun).filter(
        ResearchRun.workspace_id == tenant.workspace_id,
        ResearchRun.id == run_id,
    ).first()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RUN_NOT_FOUND", "message": f"Research run {run_id} not found"},
        )

    authorize_resource(
        tenant, "research.read", resource_type="research_run",
        resource_id=run.id, workspace_id=run.workspace_id,
    )

    return json.loads(run.plan_json)

@router.get("/gold-sets")
def list_gold_datasets(tenant: TenantContext = Depends(require_action("research.read"))):
    """T051: List available human-reviewed gold benchmark datasets."""
    datasets = gold_manager.get_all_datasets()
    summaries = []
    for bid in datasets:
        summaries.append(gold_manager.get_summary(bid))
    return summaries

@router.get("/gold-sets/{brief_id}", response_model=List[GoldCandidateItem])
def get_gold_dataset_candidates(
    brief_id: str,
    tenant: TenantContext = Depends(require_action("research.read")),
):
    """T051: Retrieve human-annotated gold candidates for a specific brief."""
    candidates = gold_manager.get_brief_candidates(brief_id)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "GOLD_SET_NOT_FOUND", "message": f"Gold set for brief {brief_id} not found"},
        )
    return candidates

@router.get("/gold-sets/{brief_id}/summary")
def get_gold_dataset_summary(
    brief_id: str,
    tenant: TenantContext = Depends(require_action("research.read")),
):
    """Retrieve evaluation summary metrics for a gold dataset."""
    summary = gold_manager.get_summary(brief_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "GOLD_SET_NOT_FOUND", "message": f"Gold set for brief {brief_id} not found"},
        )
    return summary
