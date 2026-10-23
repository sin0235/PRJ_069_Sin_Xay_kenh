"""
SIN Content Intelligence - Sources Router
Manages Source Providers, Compliance Verification, Search & Ingestion.
"""
import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import TenantContext, require_action
from src.models.entities import SourceRecord, MetricSnapshot, QuarantineRecord, AuditEvent
from src.schemas.contracts import SourceRecordDetailOut
from .provider_protocol import (
    ProviderCapabilities,
    ProviderCapabilityStatus,
    ProviderStatus,
    SearchQuery,
    Budget,
    AuthContext,
    ProviderError,
    Page,
    ProviderPost,
)
from .provider_registry import default_registry, BANNED_SOURCES

router = APIRouter(prefix="/v1/sources", tags=["Data Source Providers"])

class SearchRequest(BaseModel):
    provider_id: str
    query: SearchQuery
    budget: Optional[Budget] = None
    oauth_token: Optional[str] = None

class CustomerImportRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)

class CustomerImportResponse(BaseModel):
    total: int
    valid_count: int
    quarantined_count: int
    status: ProviderStatus

@router.get("/providers", response_model=List[ProviderCapabilities])
def list_providers(tenant: TenantContext = Depends(require_action("research.read"))):
    """List all registered source providers and their capabilities."""
    return default_registry.list_capabilities()

@router.get("/providers/{provider_id}/capabilities", response_model=ProviderCapabilities)
def get_provider_capabilities(
    provider_id: str,
    tenant: TenantContext = Depends(require_action("research.read"))
):
    """Retrieve capabilities for a specific provider."""
    # Check if banned
    if provider_id.lower() in BANNED_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": ProviderStatus.RIGHTS_NOT_GRANTED,
                "provider_id": provider_id,
                "message": BANNED_SOURCES[provider_id.lower()],
            }
        )

    provider_or_err = default_registry.get_provider(provider_id)
    if isinstance(provider_or_err, ProviderError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": provider_or_err.error_code,
                "provider_id": provider_id,
                "message": provider_or_err.message_safe,
            }
        )
    return provider_or_err.capabilities()

@router.post("/search")
def search_sources(
    payload: SearchRequest,
    tenant: TenantContext = Depends(require_action("research.run")),
    db: Session = Depends(get_db),
):
    """
    Search content via a provider.
    Enforces compliance, budget limits, rate limiting, and circuit breaker.
    """
    auth = AuthContext(
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        oauth_token=payload.oauth_token,
    )
    budget = payload.budget or Budget()

    result = default_registry.execute_search(
        provider_id=payload.provider_id,
        query=payload.query,
        auth=auth,
        budget=budget,
    )

    if isinstance(result, ProviderError):
        # Map provider error to HTTP error status
        status_map = {
            ProviderStatus.RIGHTS_NOT_GRANTED: status.HTTP_403_FORBIDDEN,
            ProviderStatus.FORBIDDEN: status.HTTP_403_FORBIDDEN,
            ProviderStatus.AUTH_FAILED: status.HTTP_401_UNAUTHORIZED,
            ProviderStatus.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
            ProviderStatus.BUDGET_EXCEEDED: status.HTTP_429_TOO_MANY_REQUESTS,
            ProviderStatus.UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
            ProviderStatus.NO_APPROVED_SOURCE: status.HTTP_404_NOT_FOUND,
            ProviderStatus.INVALID_DATA: status.HTTP_422_UNPROCESSABLE_ENTITY,
        }
        http_code = status_map.get(result.error_code, status.HTTP_400_BAD_REQUEST)
        
        # Log audit if access denied or banned tool requested
        if result.error_code in [ProviderStatus.RIGHTS_NOT_GRANTED, ProviderStatus.FORBIDDEN]:
            audit = AuditEvent(
                workspace_id=tenant.workspace_id,
                actor_id=tenant.user_id,
                event_type="UNAPPROVED_SOURCE_DENIED",
                details=f"Provider: {payload.provider_id}, Error: {result.message_safe}",
            )
            db.add(audit)
            db.commit()

        raise HTTPException(
            status_code=http_code,
            detail=result.model_dump(),
        )

    return result

@router.post("/customer-import", response_model=CustomerImportResponse)
def import_customer_data(
    payload: CustomerImportRequest,
    tenant: TenantContext = Depends(require_action("research.run")),
    db: Session = Depends(get_db),
):
    """
    Ingests customer-provided datasets (JSON).
    Validates records: isolates malformed items into quarantine; stages valid items.
    """
    if not payload.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_code": "EMPTY_PAYLOAD", "message": "Import items array cannot be empty"},
        )

    provider_or_err = default_registry.get_provider("customer_import")
    if isinstance(provider_or_err, ProviderError):
        raise HTTPException(status_code=500, detail=provider_or_err.model_dump())

    adapter = provider_or_err
    import_res = adapter.import_batch(tenant.workspace_id, payload.items)

    # Persist quarantined records to DB for audit and provenance
    quarantined_items = adapter.get_quarantined_records(tenant.workspace_id)
    for q in quarantined_items:
        # Check if already saved
        existing = db.query(QuarantineRecord).filter(
            QuarantineRecord.id == q["quarantine_id"]
        ).first()
        if not existing:
            qr = QuarantineRecord(
                id=q["quarantine_id"],
                workspace_id=tenant.workspace_id,
                provider_id="customer_import",
                raw_payload_json=json.dumps(q["raw_payload"]),
                error_reason=q["error_reason"],
            )
            db.add(qr)

    # Persist valid records to DB
    for post in adapter._workspace_records.get(tenant.workspace_id, []):
        existing_sr = db.query(SourceRecord).filter(
            SourceRecord.workspace_id == tenant.workspace_id,
            SourceRecord.raw_external_id == post.external_id,
        ).first()
        if not existing_sr:
            sr = SourceRecord(
                workspace_id=tenant.workspace_id,
                provider_id="customer_import",
                raw_external_id=post.external_id,
                canonical_url=post.canonical_url,
                title=post.title,
                caption=post.text_excerpt,
                synthetic=post.synthetic,
                rights_basis="customer_supplied",
            )
            db.add(sr)
            db.flush()

            for m in post.metrics:
                ms = MetricSnapshot(
                    source_record_id=sr.id,
                    view_count=m.value if m.metric_name == "VIEW_COUNT" else None,
                    like_count=m.value if m.metric_name == "LIKE_COUNT" else None,
                    comment_count=m.value if m.metric_name == "COMMENT_COUNT" else None,
                    share_count=m.value if m.metric_name == "SHARE_COUNT" else None,
                    synthetic=post.synthetic,
                )
                db.add(ms)

    db.commit()

    return CustomerImportResponse(
        total=import_res["total"],
        valid_count=import_res["valid_count"],
        quarantined_count=import_res["quarantined_count"],
        status=import_res["status"],
    )

@router.get("/quarantine")
def list_quarantine_records(
    tenant: TenantContext = Depends(require_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """Retrieve list of quarantined records for the workspace."""
    records = db.query(QuarantineRecord).filter(
        QuarantineRecord.workspace_id == tenant.workspace_id
    ).order_by(QuarantineRecord.created_at.desc()).all()
    
    return [
        {
            "id": r.id,
            "workspace_id": r.workspace_id,
            "provider_id": r.provider_id,
            "raw_payload": json.loads(r.raw_payload_json or "{}"),
            "error_reason": r.error_reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]

def _evaluate_source_metric(sr: SourceRecord, db: Session, max_age_days: int = 30) -> Dict[str, Any]:
    """
    T102: Danh gia trang thai chi so cua nguon noi dung.
    P10-04: is_trending phai co it nhat 2 snapshot de tinh van toc tang truong (growth velocity).
    P10-05: Observed_at trong tuong lai bi coi la FUTURE_TIMESTAMP_INVALID va loai bo.
    P10-08: Giu nguyen cac chi so co that (like_count, comment_count...) neu view_count=null, tra ve PARTIAL.
    """
    snapshots: List[MetricSnapshot] = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.source_record_id == sr.id)
        .order_by(MetricSnapshot.observed_at.desc())
        .limit(2)
        .all()
    )

    if not snapshots:
        return {
            "metric_status": "MISSING",
            "view_count": None,
            "like_count": None,
            "comment_count": None,
            "share_count": None,
            "is_trending": None,
            "last_observed_at": None,
        }

    latest_snapshot = snapshots[0]
    now = datetime.now(timezone.utc)
    obs_at = latest_snapshot.observed_at
    if obs_at.tzinfo is None:
        obs_at = obs_at.replace(tzinfo=timezone.utc)

    # P10-05: Chan moc quan sat trong tuong lai
    future_diff = (obs_at - now).total_seconds()
    if future_diff > 300: # Qua 5 phut dung sai dong ho
        return {
            "metric_status": "FUTURE_TIMESTAMP_INVALID",
            "view_count": None,
            "like_count": None,
            "comment_count": None,
            "share_count": None,
            "is_trending": False,
            "last_observed_at": None,
        }

    age_days = (now - obs_at).total_seconds() / 86400.0
    if age_days > max_age_days:
        return {
            "metric_status": "EXPIRED",
            "view_count": None,
            "like_count": None,
            "comment_count": None,
            "share_count": None,
            "is_trending": None,
            "last_observed_at": obs_at,
        }

    vc = latest_snapshot.view_count
    lk = latest_snapshot.like_count
    cm = latest_snapshot.comment_count
    sh = latest_snapshot.share_count

    # P10-08: Neu khong co bat ky chi so nao -> MISSING; neu thieu view_count nhung co chi so khac -> PARTIAL; neu du -> VALID
    if vc is None and lk is None and cm is None and sh is None:
        status_str = "MISSING"
    elif vc is None:
        status_str = "PARTIAL"
    else:
        status_str = "VALID"

    # P10-04: is_trending phai co it nhat 2 snapshot voi van toc tang truong duong (trend velocity)
    is_trending = False
    if len(snapshots) >= 2 and vc is not None:
        prev_snapshot = snapshots[1]
        prev_obs = prev_snapshot.observed_at
        if prev_obs.tzinfo is None:
            prev_obs = prev_obs.replace(tzinfo=timezone.utc)
        delta_hours = (obs_at - prev_obs).total_seconds() / 3600.0
        if delta_hours > 0 and prev_snapshot.view_count is not None:
            delta_views = vc - prev_snapshot.view_count
            hourly_velocity = delta_views / delta_hours
            if hourly_velocity >= 1000 and vc >= 50000:
                is_trending = True

    return {
        "metric_status": status_str,
        "view_count": vc,
        "like_count": lk,
        "comment_count": cm,
        "share_count": sh,
        "is_trending": is_trending if status_str == "VALID" else None,
        "last_observed_at": obs_at,
    }

@router.get("/records", response_model=List[SourceRecordDetailOut])
def list_source_records(
    tenant: TenantContext = Depends(require_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """
    Retrieve list of saved source records for the workspace with metric coverage status (T102).
    """
    records = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == tenant.workspace_id,
        SourceRecord.is_purged == False,
    ).order_by(SourceRecord.created_at.desc()).all()

    results = []
    for r in records:
        metric_info = _evaluate_source_metric(r, db)
        results.append(
            SourceRecordDetailOut(
                id=r.id,
                workspace_id=r.workspace_id,
                provider_id=r.provider_id,
                raw_external_id=r.raw_external_id,
                canonical_url=r.canonical_url,
                title=r.title,
                caption=r.caption,
                synthetic=r.synthetic,
                rights_basis=r.rights_basis,
                metric_status=metric_info["metric_status"],
                view_count=metric_info["view_count"],
                like_count=metric_info["like_count"],
                comment_count=metric_info["comment_count"],
                share_count=metric_info["share_count"],
                is_trending=metric_info["is_trending"],
                last_observed_at=metric_info["last_observed_at"],
                created_at=r.created_at,
            )
        )
    return results

@router.get("/records/{record_id}", response_model=SourceRecordDetailOut)
def get_source_record(
    record_id: str,
    tenant: TenantContext = Depends(require_action("evidence.read")),
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific source record with verified metrics and status (T102).
    """
    r = db.query(SourceRecord).filter(
        SourceRecord.id == record_id,
        SourceRecord.workspace_id == tenant.workspace_id,
        SourceRecord.is_purged == False,
    ).first()
    if not r:
        raise HTTPException(status_code=404, detail="SourceRecord not found")


    metric_info = _evaluate_source_metric(r, db)
    return SourceRecordDetailOut(
        id=r.id,
        workspace_id=r.workspace_id,
        provider_id=r.provider_id,
        raw_external_id=r.raw_external_id,
        canonical_url=r.canonical_url,
        title=r.title,
        caption=r.caption,
        synthetic=r.synthetic,
        rights_basis=r.rights_basis,
        metric_status=metric_info["metric_status"],
        view_count=metric_info["view_count"],
        like_count=metric_info["like_count"],
        comment_count=metric_info["comment_count"],
        share_count=metric_info["share_count"],
        is_trending=metric_info["is_trending"],
        last_observed_at=metric_info["last_observed_at"],
        created_at=r.created_at,
    )
