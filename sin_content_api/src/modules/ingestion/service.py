"""
Ingestion Service: Provenance, Idempotency, Synthetic Guard & Retention Management.
Implements T040, T041, T042, T043, T044.
"""
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.config import settings
from src.models.entities import (
    SourceRecord,
    SourceObservation,
    MetricSnapshot,
    QuarantineRecord,
    AuditEvent,
    utc_now,
)

class IngestionService:
    def ingest_batch(
        self,
        workspace_id: str,
        items: List[Dict[str, Any]],
        actor_user_id: str,
        is_production: bool,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Idempotent batch ingestion with provenance tracking and synthetic guard.
        """
        # T043: Synthetic Fixture Guard in Production API
        effective_production = is_production or (settings.app_env.lower() == "production")
        if effective_production:
            for item in items:
                is_synthetic = item.get("synthetic") is True
                is_fixture = item.get("provider_id") == "test_fixture"
                if is_synthetic or is_fixture:
                    audit = AuditEvent(
                        workspace_id=workspace_id,
                        actor_id=actor_user_id,
                        event_type="SYNTHETIC_DATA_REJECTED",
                        details=f"Synthetic fixture rejected in production: external_id={item.get('external_id')}, provider={item.get('provider_id')}",
                    )
                    db.add(audit)
                    db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error_code": "SYNTHETIC_DATA_NOT_ALLOWED_IN_PROD",
                            "message": "Synthetic test fixtures are strictly prohibited in production mode. Data rejected.",
                        },
                    )

        created_sources = 0
        created_observations = 0
        deduplicated_observations = 0
        quarantined_count = 0
        seen_observations_in_batch = set()

        # P04-05: Danh muc nguon cam tuyet doi khong co quyen su dung
        BANNED_SOURCES = {"mediacrawler", "crawler_illegal", "unauthorized_scraper"}

        for raw in items:
            external_id = raw.get("external_id") or raw.get("raw_external_id")
            canonical_url = raw.get("canonical_url")
            title = raw.get("title") or raw.get("caption") or raw.get("text_excerpt")
            provider_id = raw.get("provider_id", "customer_import")

            # P04-05: Chan nguon cam ngay tai ranh gioi Ingestion
            if any(banned in str(provider_id).lower() for banned in BANNED_SOURCES):
                qr = QuarantineRecord(
                    workspace_id=workspace_id,
                    provider_id=provider_id,
                    raw_payload_json=json.dumps(raw),
                    error_reason=f"RIGHTS_NOT_GRANTED: Banned provider '{provider_id}' is strictly prohibited by content rights policy.",
                )
                db.add(qr)
                quarantined_count += 1
                continue

            # P04-04: Parse boolean synthetic chat che
            raw_synth = raw.get("synthetic", False)
            if isinstance(raw_synth, str):
                synthetic = raw_synth.lower() in ("true", "1", "yes")
            elif isinstance(raw_synth, (int, bool)):
                synthetic = bool(raw_synth)
            else:
                synthetic = False

            # P04-04: Chan du lieu synthetic trong moi truong production (T043)
            is_prod = getattr(settings, "app_env", "development").lower() in ("production", "prod") or effective_production
            if is_prod and synthetic:
                qr = QuarantineRecord(
                    workspace_id=workspace_id,
                    provider_id=provider_id,
                    raw_payload_json=json.dumps(raw),
                    error_reason="PRODUCTION_SYNTHETIC_DATA_PROHIBITED: Synthetic data cannot be ingested in production environment.",
                )
                db.add(qr)
                quarantined_count += 1
                continue

            rights_basis = raw.get("rights_basis", "customer_supplied")
            obs_id = str(raw.get("observation_id") or external_id or uuid.uuid4())

            # P04-06: Bao toan thoi diem quan sat goc
            raw_obs_at = raw.get("observed_at") or raw.get("published_at")
            observed_at_dt = datetime.now(timezone.utc)
            if raw_obs_at:
                try:
                    if isinstance(raw_obs_at, str):
                        observed_at_dt = datetime.fromisoformat(raw_obs_at.replace("Z", "+00:00"))
                    elif isinstance(raw_obs_at, datetime):
                        observed_at_dt = raw_obs_at
                except Exception:
                    pass

            # P04-08: Validate retention_days an toan khong lam sap batch
            try:
                ret_days_raw = raw.get("retention_days", 90)
                retention_days = int(ret_days_raw)
                if retention_days <= 0:
                    retention_days = 90
            except (ValueError, TypeError):
                qr = QuarantineRecord(
                    workspace_id=workspace_id,
                    provider_id=provider_id,
                    raw_payload_json=json.dumps(raw),
                    error_reason=f"INVALID_RETENTION_DAYS: retention_days must be a positive integer, got '{raw.get('retention_days')}'",
                )
                db.add(qr)
                quarantined_count += 1
                continue

            # Validate input: Must have at least (external_id or canonical_url) AND (title or caption)
            if (not external_id and not canonical_url) or not title:
                qr = QuarantineRecord(
                    workspace_id=workspace_id,
                    provider_id=provider_id,
                    raw_payload_json=json.dumps(raw),
                    error_reason="Missing essential fields: external_id/canonical_url or title",
                )
                db.add(qr)
                quarantined_count += 1
                continue

            # T042: Canonical Deduplication
            existing_sr: Optional[SourceRecord] = None
            if canonical_url:
                existing_sr = db.query(SourceRecord).filter(
                    SourceRecord.workspace_id == workspace_id,
                    SourceRecord.canonical_url == canonical_url,
                ).first()

            if not existing_sr and external_id:
                existing_sr = db.query(SourceRecord).filter(
                    SourceRecord.workspace_id == workspace_id,
                    SourceRecord.raw_external_id == external_id,
                ).first()

            if existing_sr:
                # P04-10: Nguon da bi purge, cam nap quan sat moi
                if existing_sr.is_purged:
                    qr = QuarantineRecord(
                        workspace_id=workspace_id,
                        provider_id=provider_id,
                        raw_payload_json=json.dumps(raw),
                        error_reason=f"SOURCE_PURGED: SourceRecord {existing_sr.id} has been purged. Ingestion of new observations is rejected.",
                    )
                    db.add(qr)
                    quarantined_count += 1
                    continue
                # P11-05: Cap nhat thong tin is_paid va channel_id neu co
                if "is_paid" in raw:
                    raw_p = raw.get("is_paid")
                    if isinstance(raw_p, str):
                        existing_sr.is_paid = raw_p.lower() in ("true", "1", "yes")
                    else:
                        existing_sr.is_paid = bool(raw_p)
                if raw.get("channel_id"):
                    existing_sr.channel_id = str(raw.get("channel_id"))
                source_record = existing_sr
            else:
                raw_p = raw.get("is_paid", False)
                if isinstance(raw_p, str):
                    is_paid_val = raw_p.lower() in ("true", "1", "yes")
                else:
                    is_paid_val = bool(raw_p)

                source_record = SourceRecord(
                    workspace_id=workspace_id,
                    provider_id=provider_id,
                    raw_external_id=str(external_id or f"gen-{uuid.uuid4().hex[:8]}"),
                    canonical_url=canonical_url,
                    title=str(title),
                    caption=raw.get("caption") or raw.get("text_excerpt"),
                    synthetic=synthetic,
                    rights_basis=rights_basis,
                    observed_at=observed_at_dt,
                    is_paid=is_paid_val,
                    channel_id=str(raw.get("channel_id")) if raw.get("channel_id") else None,
                )
                db.add(source_record)
                db.flush()
                created_sources += 1

            # P04-01: Idempotency Check & In-batch deduplication
            obs_key = (source_record.id, obs_id)
            if obs_key in seen_observations_in_batch:
                deduplicated_observations += 1
                continue

            existing_obs = db.query(SourceObservation).filter(
                SourceObservation.workspace_id == workspace_id,
                SourceObservation.source_record_id == source_record.id,
                SourceObservation.observation_id == obs_id,
            ).first()

            if existing_obs:
                deduplicated_observations += 1
                seen_observations_in_batch.add(obs_key)
                continue

            seen_observations_in_batch.add(obs_key)

            # Record new observation
            obs = SourceObservation(
                workspace_id=workspace_id,
                source_record_id=source_record.id,
                observation_id=obs_id,
                provider_id=provider_id,
                raw_payload_json=json.dumps(raw),
                rights_basis=rights_basis,
                retention_days=retention_days,
                observed_at=observed_at_dt,
            )
            db.add(obs)
            created_observations += 1

            # P04-07: MetricSnapshot validate chat che: tu choi boolean, so am, float
            def parse_metric(val):
                if val is None or val == "NOT_AVAILABLE" or isinstance(val, bool):
                    return None
                try:
                    f_val = float(val)
                    if f_val < 0 or f_val != int(f_val):
                        return None
                    return int(f_val)
                except (ValueError, TypeError):
                    return None

            vc = parse_metric(raw.get("view_count"))
            likes = parse_metric(raw.get("like_count"))
            comments = parse_metric(raw.get("comment_count"))
            shares = parse_metric(raw.get("share_count"))

            snapshot = MetricSnapshot(
                source_record_id=source_record.id,
                observation_id=obs_id,
                view_count=vc,
                like_count=likes,
                comment_count=comments,
                share_count=shares,
                synthetic=synthetic,
                observed_at=observed_at_dt,
            )
            db.add(snapshot)

        db.commit()


        status_result = "OK"
        if quarantined_count > 0 and (created_observations > 0 or deduplicated_observations > 0):
            status_result = "PARTIAL"
        elif quarantined_count > 0:
            status_result = "INVALID_DATA"

        return {
            "total": len(items),
            "created_sources": created_sources,
            "created_observations": created_observations,
            "deduplicated_observations": deduplicated_observations,
            "quarantined_count": quarantined_count,
            "status": status_result,
        }

    def purge_record(
        self,
        workspace_id: str,
        source_record_id: str,
        actor_user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        T044: Deletion & retention expiry purge.
        Purges permitted sensitive fields and logs audit event.
        """
        record = db.query(SourceRecord).filter(
            SourceRecord.workspace_id == workspace_id,
            SourceRecord.id == source_record_id,
        ).first()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "RECORD_NOT_FOUND", "message": f"SourceRecord {source_record_id} not found"},
            )

        now = utc_now()
        # Purge retained text content
        record.caption = "[PURGED_DUE_TO_RETENTION_POLICY]"
        record.title = "[PURGED]"
        record.is_purged = True
        record.purged_at = now

        # Purge raw payloads in observations
        for obs in record.observations:
            obs.is_purged = True
            obs.raw_payload_json = json.dumps({"status": "PURGED", "purged_at": now.isoformat()})

        # Generate mandatory Audit Event
        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_user_id,
            event_type="DATA_RETENTION_PURGE",
            details=f"Record {source_record_id} content purged per retention policy by actor {actor_user_id}",
        )
        db.add(audit)
        db.commit()

        return {
            "status": "PURGED",
            "source_record_id": source_record_id,
            "purged_at": now.isoformat(),
        }

ingestion_service = IngestionService()
