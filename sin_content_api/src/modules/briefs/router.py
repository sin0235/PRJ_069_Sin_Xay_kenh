# Router quan ly Brand Brief co xac thuc tenant va vong doi phe duyet (P02)
import json
import uuid
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_resolved_resource_action,
)
from src.models.entities import BrandBriefVersion, AudienceSegment, AllowedFact, AuditEvent
from src.schemas.contracts import (
    BrandBriefCreate, BrandBriefUpdate, BrandBriefOut, BriefReviewRequest,
    AudienceSegmentOut, AllowedFactOut
)

router = APIRouter(prefix="/v1/briefs", tags=["Brand Briefs"])

def _format_brief_out(brief: BrandBriefVersion) -> BrandBriefOut:
    """Format BrandBriefVersion ORM thanh Pydantic BrandBriefOut"""
    segments_out = []
    for s in brief.audience_segments:
        segments_out.append(AudienceSegmentOut(
            id=s.id,
            brief_version_id=s.brief_version_id,
            label=s.label,
            contexts=json.loads(s.contexts_json or "[]"),
            needs=json.loads(s.needs_json or "[]"),
            disallowed_inferences=json.loads(s.disallowed_inferences_json or "[]"),
            awareness_stage=s.awareness_stage,
            created_at=s.created_at
        ))
        
    facts_out = []
    for f in brief.allowed_facts:
        facts_out.append(AllowedFactOut(
            id=f.id,
            brief_version_id=f.brief_version_id,
            claim_text=f.claim_text,
            fact_type=f.fact_type,
            source_citation=f.source_citation,
            verification_status=f.verification_status,
            created_at=f.created_at
        ))

    return BrandBriefOut(
        id=brief.id,
        workspace_id=brief.workspace_id,
        version=brief.version,
        brand_name=brief.brand_name,
        objective=brief.objective,
        voice_description=brief.voice_description,
        language=brief.language,
        current_audience=brief.current_audience,
        target_audience=brief.target_audience,
        topics_included=json.loads(brief.topics_included_json or "[]"),
        topics_excluded=json.loads(brief.topics_excluded_json or "[]"),
        production_limits=json.loads(brief.production_limits_json or "[]"),
        status=brief.status,
        approved_by_user_id=brief.approved_by_user_id,
        approved_at=brief.approved_at,
        created_at=brief.created_at,
        segments=segments_out,
        allowed_facts=facts_out
    )

@router.get("", response_model=List[BrandBriefOut])
def list_briefs(
    ctx: TenantContext = Depends(require_action("brief.read")),
    db: Session = Depends(get_db)
):
    briefs = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.workspace_id == ctx.workspace_id
    ).all()
    for brief in briefs:
        authorize_resource(
            ctx, "brief.read", resource_type="brand_brief",
            resource_id=brief.id, workspace_id=brief.workspace_id,
        )
    return [_format_brief_out(b) for b in briefs]

@router.post("", response_model=BrandBriefOut, status_code=status.HTTP_201_CREATED)
def create_brief(
    payload: BrandBriefCreate,
    ctx: TenantContext = Depends(require_action("brief.edit")),
    db: Session = Depends(get_db)
):
    brief = BrandBriefVersion(
        workspace_id=ctx.workspace_id,
        version=1,
        brand_name=payload.brand_name,
        objective=payload.objective,
        voice_description=payload.voice_description,
        current_audience=payload.current_audience,
        target_audience=payload.target_audience,
        topics_included_json=json.dumps(payload.topics_included),
        topics_excluded_json=json.dumps(payload.topics_excluded),
        production_limits_json=json.dumps(payload.production_limits or []),
        status="DRAFT"
    )
    db.add(brief)
    db.flush() # Sinh ID cho brief
    
    # Them segments neu co
    if payload.segments:
        for seg in payload.segments:
            s_entity = AudienceSegment(
                brief_version_id=brief.id,
                label=seg.label,
                contexts_json=json.dumps(seg.contexts),
                needs_json=json.dumps(seg.needs),
                disallowed_inferences_json=json.dumps(seg.disallowed_inferences),
                awareness_stage=seg.awareness_stage
            )
            db.add(s_entity)
            
    # Them allowed facts neu co
    if payload.allowed_facts:
        for f in payload.allowed_facts:
            f_entity = AllowedFact(
                brief_version_id=brief.id,
                claim_text=f.claim_text,
                fact_type=f.fact_type,
                source_citation=f.source_citation,
                verification_status=f.verification_status
            )
            db.add(f_entity)
            
    db.commit()
    db.refresh(brief)
    return _format_brief_out(brief)

@router.get("/{brief_id}", response_model=BrandBriefOut)
def get_brief(
    brief_id: str,
    ctx: TenantContext = Depends(require_resolved_resource_action("brief.read")),
    db: Session = Depends(get_db)
):
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == brief_id,
        BrandBriefVersion.workspace_id == ctx.workspace_id
    ).first()
    
    if not brief:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BRIEF_NOT_FOUND")

    authorize_resource(
        ctx, "brief.read", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
    )
        
    return _format_brief_out(brief)

@router.put("/{brief_id}", response_model=BrandBriefOut)
def update_or_revise_brief(
    brief_id: str,
    payload: BrandBriefUpdate,
    ctx: TenantContext = Depends(require_resolved_resource_action("brief.edit")),
    db: Session = Depends(get_db)
):
    """
    T021: Chinh sua Brief.
    - Neu brief dang o trang thai DRAFT hoac CHANGES_REQUESTED: Cap nhat truc tiep tai cho.
    - Neu brief da APPROVED: TAO PHIEN BAN BAT BIEN MOI (version = version + 1), brief cu giu nguyen APPROVED.
    """
    existing = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == brief_id,
        BrandBriefVersion.workspace_id == ctx.workspace_id
    ).first()
    
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BRIEF_NOT_FOUND")

    authorize_resource(
        ctx, "brief.edit", resource_type="brand_brief",
        resource_id=existing.id, workspace_id=existing.workspace_id,
    )
        
    # P02-01: Neu brief dang o trang thai APPROVED hoac da tung APPROVED (approved_at != None):
    # Luon luon tao phien ban bat bien moi, khong ghi de ban da duyet
    is_ever_approved = (existing.status == "APPROVED") or (existing.approved_at is not None)
    
    if is_ever_approved:
        # P02-04: Tinh version moi dua tren max(version) cua brand trong cung workspace
        from sqlalchemy import func
        max_v = db.query(func.max(BrandBriefVersion.version)).filter(
            BrandBriefVersion.workspace_id == ctx.workspace_id,
            BrandBriefVersion.brand_name == existing.brand_name
        ).scalar() or existing.version
        new_version_num = max_v + 1
        
        # Tao phien ban bat bien moi!
        new_brief = BrandBriefVersion(
            workspace_id=ctx.workspace_id,
            version=new_version_num,
            brand_name=payload.brand_name if payload.brand_name is not None else existing.brand_name,
            objective=payload.objective if payload.objective is not None else existing.objective,
            voice_description=payload.voice_description if payload.voice_description is not None else existing.voice_description,
            current_audience=payload.current_audience if payload.current_audience is not None else existing.current_audience,
            target_audience=payload.target_audience if payload.target_audience is not None else existing.target_audience,
            topics_included_json=json.dumps(payload.topics_included) if payload.topics_included is not None else existing.topics_included_json,
            topics_excluded_json=json.dumps(payload.topics_excluded) if payload.topics_excluded is not None else existing.topics_excluded_json,
            production_limits_json=json.dumps(payload.production_limits) if payload.production_limits is not None else existing.production_limits_json,
            status="DRAFT" # Phien ban moi bat buoc can duyet lai, khong tu thua huong approval
        )
        db.add(new_brief)
        db.flush()
        
        # P02-05: Xu ly segments: dung payload neu co, nguoc lai sao chep ban cu
        if payload.segments is not None:
            for seg in payload.segments:
                db.add(AudienceSegment(
                    brief_version_id=new_brief.id,
                    label=seg.label,
                    contexts_json=json.dumps(seg.contexts),
                    needs_json=json.dumps(seg.needs),
                    disallowed_inferences_json=json.dumps(seg.disallowed_inferences),
                    awareness_stage=seg.awareness_stage
                ))
        else:
            for seg in existing.audience_segments:
                db.add(AudienceSegment(
                    brief_version_id=new_brief.id,
                    label=seg.label,
                    contexts_json=seg.contexts_json,
                    needs_json=seg.needs_json,
                    disallowed_inferences_json=seg.disallowed_inferences_json,
                    awareness_stage=seg.awareness_stage
                ))
            
        # P02-05: Xu ly allowed_facts: dung payload neu co, nguoc lai sao chep ban cu
        if payload.allowed_facts is not None:
            for fact in payload.allowed_facts:
                db.add(AllowedFact(
                    brief_version_id=new_brief.id,
                    claim_text=fact.claim_text,
                    fact_type=fact.fact_type,
                    source_citation=fact.source_citation,
                    verification_status=fact.verification_status
                ))
        else:
            for fact in existing.allowed_facts:
                db.add(AllowedFact(
                    brief_version_id=new_brief.id,
                    claim_text=fact.claim_text,
                    fact_type=fact.fact_type,
                    source_citation=fact.source_citation,
                    verification_status=fact.verification_status
                ))
            
        db.commit()
        db.refresh(new_brief)
        return _format_brief_out(new_brief)
        
    else:
        # Cap nhat truc tiep ban nhap
        if payload.brand_name is not None: existing.brand_name = payload.brand_name
        if payload.objective is not None: existing.objective = payload.objective
        if payload.voice_description is not None: existing.voice_description = payload.voice_description
        if payload.current_audience is not None: existing.current_audience = payload.current_audience
        if payload.target_audience is not None: existing.target_audience = payload.target_audience
        if payload.topics_included is not None: existing.topics_included_json = json.dumps(payload.topics_included)
        if payload.topics_excluded is not None: existing.topics_excluded_json = json.dumps(payload.topics_excluded)
        if payload.production_limits is not None: existing.production_limits_json = json.dumps(payload.production_limits)
        
        # P02-05: Cap nhat segments neu co
        if payload.segments is not None:
            db.query(AudienceSegment).filter(AudienceSegment.brief_version_id == existing.id).delete()
            for seg in payload.segments:
                db.add(AudienceSegment(
                    brief_version_id=existing.id,
                    label=seg.label,
                    contexts_json=json.dumps(seg.contexts),
                    needs_json=json.dumps(seg.needs),
                    disallowed_inferences_json=json.dumps(seg.disallowed_inferences),
                    awareness_stage=seg.awareness_stage
                ))
                
        # P02-05: Cap nhat allowed_facts neu co
        if payload.allowed_facts is not None:
            db.query(AllowedFact).filter(AllowedFact.brief_version_id == existing.id).delete()
            for fact in payload.allowed_facts:
                db.add(AllowedFact(
                    brief_version_id=existing.id,
                    claim_text=fact.claim_text,
                    fact_type=fact.fact_type,
                    source_citation=fact.source_citation,
                    verification_status=fact.verification_status
                ))

        db.commit()
        db.refresh(existing)
        return _format_brief_out(existing)

@router.post("/{brief_id}/review", response_model=BrandBriefOut)
def review_brief(
    brief_id: str,
    payload: BriefReviewRequest,
    ctx: TenantContext = Depends(require_resolved_resource_action("brief.approve")),
    db: Session = Depends(get_db)
):
    """
    T022: Phe duyet Brief.
    Yeu cau role toi thieu reviewer. Neu role viewer co tinh goi, middleware se chan va nem 403 Forbidden.
    """
    brief = db.query(BrandBriefVersion).filter(
        BrandBriefVersion.id == brief_id,
        BrandBriefVersion.workspace_id == ctx.workspace_id
    ).first()
    
    if not brief:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BRIEF_NOT_FOUND")

    brief_author = getattr(brief, "creator_id", None) or getattr(brief, "created_by_user_id", None) or "brief_author_initial"
    authorize_resource(
        ctx, "brief.approve", resource_type="brand_brief",
        resource_id=brief.id, workspace_id=brief.workspace_id,
        creator_id=brief_author, require_creator=True,
    )
        
    if payload.action == "APPROVE":
        # P02-02: Kiem tra bat buoc topics_excluded phai co it nhat 1 chu de hop le truoc khi APPROVE
        excluded_list = json.loads(brief.topics_excluded_json or "[]")
        cleaned_excluded = [t.strip() for t in excluded_list if isinstance(t, str) and t.strip()]
        if not cleaned_excluded:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="CANNOT_APPROVE_BRIEF_WITHOUT_TOPICS_EXCLUDED"
            )
        brief.status = "APPROVED"
        brief.approved_by_user_id = ctx.user_id
        brief.approved_at = datetime.now(timezone.utc)
        
        # Ghi audit event
        audit = AuditEvent(
            workspace_id=ctx.workspace_id,
            actor_id=ctx.user_id,
            event_type="BRIEF_APPROVED",
            details=f"Brief {brief.id} (v{brief.version}) da duoc phe duyet boi {ctx.user_id}"
        )
        db.add(audit)
        
    elif payload.action == "REQUEST_CHANGES":
        # P02-01: Neu brief da o trang thai APPROVED, khong cho phep chuyen nguoc ve CHANGES_REQUESTED tai cho
        if brief.status == "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="CANNOT_REQUEST_CHANGES_ON_APPROVED_BRIEF_MUST_CREATE_NEW_VERSION"
            )
        brief.status = "CHANGES_REQUESTED"
        audit = AuditEvent(
            workspace_id=ctx.workspace_id,
            actor_id=ctx.user_id,
            event_type="BRIEF_CHANGES_REQUESTED",
            details=f"Brief {brief.id} (v{brief.version}) yeu cau sua doi: {payload.notes}"
        )
        db.add(audit)
        
    db.commit()
    db.refresh(brief)
    return _format_brief_out(brief)

