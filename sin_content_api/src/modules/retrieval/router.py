# FastAPI Router cho Module Retrieval & Explicit Scoring (P07)
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_action,
    authorize_resource,
    require_action,
    require_resolved_resource_actions,
)
from src.models.entities import BrandBriefVersion
from src.schemas.contracts import (
    ScoringWeightsContract,
    CandidateScoreRequest,
    CandidateScoreResponse,
    HybridSearchRequest,
    HybridSearchResponse,
    GoldEvaluationResponse
)
from src.modules.retrieval.ranking_service import ranking_service

router = APIRouter(prefix="/v1/retrieval", tags=["Retrieval, Filters & Explicit Scoring (P07)"])

@router.get("/weights", response_model=ScoringWeightsContract)
def get_scoring_weights(tenant: TenantContext = Depends(require_action("research.read"))):
    """
    Lay ma tran trong so tuong minh co dinh (T070).
    Phu hop khan gia 30%, Bang chung quan sat 25%, Muc tieu thuong hieu 20%,
    Tinh doc dao 15%, Tinh kha thi san xuat 10%. Tong = 100%.
    """
    weights = ranking_service.get_scoring_weights()
    return ScoringWeightsContract(**weights)

@router.post("/score", response_model=CandidateScoreResponse)
def score_candidate(
    payload: CandidateScoreRequest,
    tenant: TenantContext = Depends(require_resolved_resource_actions("research.run", "brief.read")),
    db: Session = Depends(get_db)
):
    """
    Cham diem tuong minh 5 thanh phan cho 1 ung vien so voi brief da duyet (T070, T071, T073).
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == tenant.workspace_id,
        BrandBriefVersion.id == payload.brief_version_id,
    ).first()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RESOURCE_NOT_FOUND")
    authorize_resource(
        tenant, "brief.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_resource(
        tenant, "research.run", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    try:
        res = ranking_service.score_candidate(
            db=db,
            workspace_id=tenant.workspace_id,
            data=payload
        )
        return CandidateScoreResponse(**res)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}
        )

@router.post("/search", response_model=HybridSearchResponse)
def search_hybrid(
    payload: HybridSearchRequest,
    tenant: TenantContext = Depends(require_resolved_resource_actions("research.run", "brief.read", "evidence.read")),
    db: Session = Depends(get_db)
):
    """
    Tim kiem lai (Bo loc cau truc + Full-text + Semantic) va xep hang ung vien.
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == tenant.workspace_id,
        BrandBriefVersion.id == payload.brief_version_id,
    ).first()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RESOURCE_NOT_FOUND")
    for action_key in ("brief.read", "research.run"):
        authorize_resource(
            tenant, action_key, resource_type="brand_brief",
            resource_id=brief.id, workspace_id=brief.workspace_id,
        )
    authorize_action(tenant, "evidence.read")
    try:
        res = ranking_service.search_hybrid(
            db=db,
            workspace_id=tenant.workspace_id,
            data=payload
        )
        return HybridSearchResponse(**res)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}
        )

@router.post("/evaluate-gold", response_model=GoldEvaluationResponse)
def evaluate_gold_set(
    dataset_name: str = Query("bento_box_gold.json"),
    tenant: TenantContext = Depends(require_action("research.run")),
):
    """
    Danh gia do chinh xac Top 10 (Precision@10 >= 80%) tren tap du lieu vang (T072).
    """
    try:
        res = ranking_service.evaluate_gold_dataset(dataset_name=dataset_name)
        return GoldEvaluationResponse(**res)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "GOLD_SET_NOT_FOUND", "message": str(e)}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_DATASET_NAME", "message": str(e)}
        )
