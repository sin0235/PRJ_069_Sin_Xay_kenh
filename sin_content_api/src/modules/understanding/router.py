# FastAPI Router cho Module Understanding (P06)
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_actions,
    require_resolved_resource_actions,
)
from src.models.entities import SourceRecord
from src.schemas.contracts import (
    ExtractSignalsRequest,
    ExtractSignalsResponse,
    ClusterRequest,
    ClusterResponse,
    TopicClusterOut,
    NeedSignalOut,
    AsrStatusResponse,
    AsrEvaluateRequest,
    AsrEvaluateResponse
)
from src.modules.understanding.service import understanding_service

router = APIRouter(prefix="/v1/understanding", tags=["Understanding & Signals (P06)"])

@router.post("/extract-signals", response_model=ExtractSignalsResponse)
def extract_signals(
    payload: ExtractSignalsRequest,
    tenant: TenantContext = Depends(require_resolved_resource_actions("research.run", "evidence.read")),
    db: Session = Depends(get_db)
):
    """
    Tiep nhan trich doan/binh luan, kiem tra Prompt Injection,
    boc tach tin hieu nhu cau va luu tru co bao toan trich dan goc.
    P06-04: Bat buoc quyen research.run (chan auditor/guest/viewer).
    """
    source_record = db.query(SourceRecord).filter(
        SourceRecord.id == payload.excerpt.source_record_id,
        SourceRecord.workspace_id == tenant.workspace_id,
    ).first()
    if source_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RESOURCE_NOT_FOUND")
    authorize_resource(
        tenant, "evidence.read", resource_type="source_record",
        resource_id=source_record.id, workspace_id=source_record.workspace_id,
    )
    authorize_resource(
        tenant, "research.run", resource_type="source_record",
        resource_id=source_record.id, workspace_id=source_record.workspace_id,
    )
    try:
        excerpt, signals, has_injection_risk, warning = understanding_service.extract_and_store_signals(
            db=db,
            workspace_id=tenant.workspace_id,
            data=payload.excerpt
        )
        return ExtractSignalsResponse(
            excerpt=excerpt,
            signals=signals,
            prompt_injection_detected=has_injection_risk,
            warning_notes=warning
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}
        )

@router.post("/cluster", response_model=ClusterResponse)
def run_clustering(
    payload: ClusterRequest,
    tenant: TenantContext = Depends(require_actions("research.run", "evidence.read")),
    db: Session = Depends(get_db)
):
    """
    Gom cum chu de cho cac tin hieu trong workspace (T060).
    P06-04: Bat buoc quyen research.run (chan auditor/viewer).
    """
    clusters = understanding_service.run_clustering(
        db=db,
        workspace_id=tenant.workspace_id,
        enabled=payload.enabled,
        intent_group=payload.intent_group
    )
    return ClusterResponse(
        enabled=payload.enabled,
        total_clusters=len(clusters),
        clusters=clusters
    )

@router.get("/clusters", response_model=List[TopicClusterOut])
def get_clusters(
    tenant: TenantContext = Depends(require_actions("research.read", "evidence.read")),
    db: Session = Depends(get_db)
):
    """Lay danh sach cac cum chu de da gom trong workspace."""
    return understanding_service.get_clusters(db=db, workspace_id=tenant.workspace_id)

@router.get("/signals", response_model=List[NeedSignalOut])
def get_signals(
    intent_group: Optional[str] = Query(None),
    need_category: Optional[str] = Query(None),
    tenant: TenantContext = Depends(require_actions("research.read", "evidence.read")),
    db: Session = Depends(get_db)
):
    """Truy van danh sach tin hieu nhu cau trong workspace."""
    return understanding_service.get_signals(
        db=db,
        workspace_id=tenant.workspace_id,
        intent_group=intent_group,
        need_category=need_category
    )

@router.get("/asr-status", response_model=AsrStatusResponse)
def get_asr_status(
    licensed_audio_count: int = Query(0, ge=0),
    tenant: TenantContext = Depends(require_action("research.read")),
):
    """
    Kiem tra tinh trang nang luc ASR tieng Viet (T063 / P06-01).
    Tra ve UNVERIFIED neu chua co tap am thanh duoc cap phep.
    """
    status_info = understanding_service.check_asr_status(licensed_audio_count=licensed_audio_count)
    return AsrStatusResponse(**status_info)

@router.post("/asr-evaluate", response_model=AsrEvaluateResponse)
def evaluate_asr(
    payload: AsrEvaluateRequest,
    tenant: TenantContext = Depends(require_action("research.run")),
):
    """
    Danh gia do chinh xac (WER va terminology accuracy) tren tap am thanh duoc cap phep (T063).
    """
    try:
        eval_result = understanding_service.evaluate_asr(
            references=payload.reference_transcripts,
            hypotheses=payload.hypothesis_transcripts,
            domain_terms=payload.domain_terms
        )
        return AsrEvaluateResponse(**eval_result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_EVALUATION_INPUT", "message": str(e)}
        )
