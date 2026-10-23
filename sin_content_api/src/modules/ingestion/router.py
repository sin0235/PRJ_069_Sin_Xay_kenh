"""
SIN Content Intelligence - Ingestion Router (P04)
REST endpoints for idempotent batch ingestion, multi-source lineage, and retention purge.
"""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import (
    TenantContext,
    authorize_resource,
    require_action,
    require_resolved_resource_action,
)
from src.models.entities import SourceRecord, SourceObservation, MetricSnapshot
from .service import ingestion_service

router = APIRouter(prefix="/v1/ingestion", tags=["Data Ingestion & Provenance"])

class IngestBatchRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)
    is_production: bool = False

class IngestBatchResponse(BaseModel):
    total: int
    created_sources: int
    created_observations: int
    deduplicated_observations: int
    quarantined_count: int
    status: str

@router.post("/batch", response_model=IngestBatchResponse)
def ingest_batch(
    payload: IngestBatchRequest,
    tenant: TenantContext = Depends(require_action("research.run")),
    db: Session = Depends(get_db),
):
    """
    Idempotent batch ingestion with provenance tracking, deduplication, and synthetic guard.
    """
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "EMPTY_BATCH", "message": "Ingestion batch items cannot be empty"},
        )

    res = ingestion_service.ingest_batch(
        workspace_id=tenant.workspace_id,
        items=payload.items,
        actor_user_id=tenant.user_id,
        is_production=payload.is_production,
        db=db,
    )
    return IngestBatchResponse(**res)

@router.post("/purge/{source_record_id}")
def purge_source_record(
    source_record_id: str,
    tenant: TenantContext = Depends(require_resolved_resource_action("research.run")),
    db: Session = Depends(get_db),
):
    """
    T044: Data retention purge. Purges sensitive content fields and generates an audit event.
    """
    record = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == tenant.workspace_id,
        SourceRecord.id == source_record_id,
    ).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RECORD_NOT_FOUND")
    authorize_resource(
        tenant, "research.run", resource_type="source_record",
        resource_id=record.id, workspace_id=record.workspace_id,
    )
    return ingestion_service.purge_record(
        workspace_id=tenant.workspace_id,
        source_record_id=source_record_id,
        actor_user_id=tenant.user_id,
        db=db,
    )

@router.get("/lineage/{source_record_id}")
def get_source_lineage(
    source_record_id: str,
    tenant: TenantContext = Depends(require_resolved_resource_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """
    T042: Retrieve multi-source provenance and lineage for a canonical source record.
    """
    record = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == tenant.workspace_id,
        SourceRecord.id == source_record_id,
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RECORD_NOT_FOUND", "message": f"SourceRecord {source_record_id} not found"},
        )

    authorize_resource(
        tenant, "evidence.read", resource_type="source_record",
        resource_id=record.id, workspace_id=record.workspace_id,
    )

    observations_out = []
    for obs in record.observations:
        observations_out.append({
            "observation_id": obs.observation_id,
            "provider_id": obs.provider_id,
            "observed_at": obs.observed_at.isoformat(),
            "rights_basis": obs.rights_basis,
            "retention_days": obs.retention_days,
            "is_purged": obs.is_purged,
        })

    snapshots_out = []
    for snap in record.metric_snapshots:
        snapshots_out.append({
            "observation_id": snap.observation_id,
            "observed_at": snap.observed_at.isoformat(),
            "view_count": snap.view_count, # Can be null (T041)
            "like_count": snap.like_count,
            "comment_count": snap.comment_count,
            "share_count": snap.share_count,
            "synthetic": snap.synthetic,
        })

    return {
        "canonical_record": {
            "id": record.id,
            "workspace_id": record.workspace_id,
            "canonical_url": record.canonical_url,
            "raw_external_id": record.raw_external_id,
            "title": record.title,
            "caption": record.caption,
            "synthetic": record.synthetic,
            "is_purged": record.is_purged,
            "purged_at": record.purged_at.isoformat() if record.purged_at else None,
            "created_at": record.created_at.isoformat(),
        },
        "observations_count": len(observations_out),
        "observations": observations_out,
        "snapshots_count": len(snapshots_out),
        "snapshots": snapshots_out,
    }

@router.get("/records")
def list_canonical_records(
    tenant: TenantContext = Depends(require_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """List canonical source records for the workspace."""
    records = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == tenant.workspace_id
    ).order_by(SourceRecord.created_at.desc()).all()

    return [
        {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "canonical_url": r.canonical_url,
            "raw_external_id": r.raw_external_id,
            "title": r.title,
            "synthetic": r.synthetic,
            "is_purged": r.is_purged,
            "observations_count": len(r.observations),
            "snapshots_count": len(r.metric_snapshots),
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
