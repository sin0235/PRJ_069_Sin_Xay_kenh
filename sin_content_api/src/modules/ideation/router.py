# Router API cho Pha P08: Ideation & Citation Verification (/v1/ideation)
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_action,
    authorize_resource,
    require_action,
    require_resolved_resource_action,
    require_resolved_resource_actions,
)
from src.models.entities import BrandBriefVersion, IdeaCard
from src.schemas.contracts import (
    IdeaCardOut, IdeaCardVerifyRequest, IdeaCardVerifyResponse,
    IdeaGenerationRequest, IdeaGenerationResponse, IdeaReviewRequest,
    ReviewAuditItemOut
)
from src.modules.ideation.ideation_service import ideation_service

router = APIRouter(prefix="/v1/ideation", tags=["Ideation & Verification"])

@router.post("/generate", response_model=IdeaGenerationResponse)
def generate_ideas(
    payload: IdeaGenerationRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_actions("ideas.create", "brief.read", "evidence.read"))
):
    """
    Sinh cac the y tuong TikTok dua tren brief va bang chung trich dan thuc te trong workspace (T080, T082).
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == payload.brief_version_id,
        BrandBriefVersion.workspace_id == tenant.workspace_id,
    ).first()
    if brief is None:
        raise HTTPException(status_code=404, detail="Brand brief not found")
    authorize_resource(
        tenant, "brief.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_resource(
        tenant, "ideas.create", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_action(tenant, "evidence.read")
    return ideation_service.generate_ideas(db, tenant.workspace_id, tenant.user_id, payload, idempotency_key=idempotency_key)

@router.post("/verify", response_model=IdeaCardVerifyResponse)
def verify_idea(
    payload: IdeaCardVerifyRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_actions("ideas.read", "evidence.read"))
):
    """
    Kiem chung doc lap (IdeaVerifier):
    Xac thuc 100% ID bang chung va URL trich dan, phat hien va tu choi trich dan bia dat (T080, T081, T082, T085).
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == payload.idea_card.brief_version_id,
        BrandBriefVersion.workspace_id == tenant.workspace_id,
    ).first()
    if brief is None:
        raise HTTPException(status_code=404, detail="Brand brief not found")
    authorize_resource(
        tenant, "ideas.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
    authorize_action(tenant, "evidence.read")
    return ideation_service.verify_idea_card(db, tenant.workspace_id, payload)

@router.get("/cards", response_model=List[IdeaCardOut])
def list_idea_cards(
    brief_version_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("ideas.read"))
):
    """
    Lay danh sach the y tuong trong workspace theo bo loc brief hoac trang thai review.
    """
    cards = db.query(IdeaCard).filter(IdeaCard.workspace_id == tenant.workspace_id)
    if brief_version_id:
        cards = cards.filter(IdeaCard.brief_version_id == brief_version_id)
    if status:
        cards = cards.filter(IdeaCard.status == status)
    for card in cards.limit(limit).all():
        authorize_resource(
            tenant, "ideas.read", resource_type="idea_card",
            resource_id=card.id, workspace_id=card.workspace_id,
        )
    return ideation_service.list_idea_cards(db, tenant.workspace_id, brief_version_id, status, limit)

@router.get("/cards/{idea_id}", response_model=IdeaCardOut)
def get_idea_card(
    idea_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_action("ideas.read"))
):
    """
    Chi tiet mot the y tuong kem trich dan va canh bao trung lap.
    """
    card = db.query(IdeaCard).filter(
        IdeaCard.id == idea_id,
        IdeaCard.workspace_id == tenant.workspace_id,
    ).first()
    if card is None:
        raise HTTPException(status_code=404, detail="IdeaCard not found")
    authorize_resource(
        tenant, "ideas.read", resource_type="idea_card",
        resource_id=card.id, workspace_id=card.workspace_id,
    )
    return ideation_service.get_idea_card(db, tenant.workspace_id, idea_id)

@router.post("/cards/{idea_id}/review", response_model=IdeaCardOut)
def review_idea_card(
    idea_id: str,
    payload: IdeaReviewRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_action("ideas.approve_team"))
):
    """
    Thao tac phe duyet / tu choi / yeu cau bo sung bang chung / mo lai (Review Queue - HITL).
    Kiem tra quy tac tach biet vai tro (Four-Eyes Principle / No Self-Approval) va khoa lac quan (T100, T101).
    """
    card = db.query(IdeaCard).filter(
        IdeaCard.id == idea_id,
        IdeaCard.workspace_id == tenant.workspace_id,
    ).first()
    if card is None:
        raise HTTPException(status_code=404, detail="IdeaCard not found")

    creator_id = getattr(card, "creator_id", None) or "system_ai_generator"
    authorize_resource(
        tenant, "ideas.approve_team", resource_type="idea_card",
        resource_id=card.id, workspace_id=card.workspace_id,
        creator_id=creator_id, require_creator=True,
    )
    return ideation_service.review_idea_card(db, tenant.workspace_id, tenant.user_id, idea_id, payload)

@router.get("/cards/{idea_id}/history", response_model=List[ReviewAuditItemOut])
def get_idea_history(
    idea_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_resolved_resource_action("ideas.read"))
):
    """
    Truy van nhat ky kiem toan / audit trail cho the y tuong (T100).
    """
    card = db.query(IdeaCard).filter(
        IdeaCard.id == idea_id,
        IdeaCard.workspace_id == tenant.workspace_id,
    ).first()
    if card is None:
        raise HTTPException(status_code=404, detail="IdeaCard not found")
    authorize_resource(
        tenant, "ideas.read", resource_type="idea_card",
        resource_id=card.id, workspace_id=card.workspace_id,
    )
    return ideation_service.get_idea_history(db, tenant.workspace_id, idea_id)
