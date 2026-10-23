# -*- coding: utf-8 -*-
"""
Trend Velocity Engine for Phase P11 (T110, T111, P11-03, P11-04, P11-06, P11-08).
Computes truthful growth deltas between exactly two valid snapshot observations.
Safeguards against zero denominators: never outputs Infinity, NaN or crashes.
Enforces idempotency and rejects purged records and intervals under 60 seconds.
"""
import math
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.models.entities import MetricSnapshot, SourceRecord, TrendVelocityObservation
from src.schemas.contracts import VelocityCalculationResponse

class VelocityEngine:
    def calculate_velocity(
        self,
        db: Session,
        workspace_id: str,
        source_record_id: str,
        from_observation_id: str,
        to_observation_id: str,
    ) -> VelocityCalculationResponse:
        """
        T110: Derived delta references both observation IDs and equivalent units.
        T111: view_count=0 denominator -> NOT_AVAILABLE rate; no Infinity/NaN or crash.
        P11-03: Missing view_count remains None, not fabricated 0.
        P11-04: Idempotent upsert so repeated requests do not duplicate observation rows.
        P11-06: Purged sources rejected.
        P11-08: Intervals < 60s return NOT_AVAILABLE instead of artificial time dilation.
        """
        # 1. Kiem tra SourceRecord thuoc workspace va khong bi purge (P11-06)
        source = db.query(SourceRecord).filter(
            SourceRecord.id == source_record_id,
            SourceRecord.workspace_id == workspace_id
        ).first()
        if not source:
            raise HTTPException(status_code=404, detail="SourceRecord not found in workspace")
        if getattr(source, "is_purged", False):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="SourceRecord has been purged. Velocity calculation is not permitted on purged records."
            )

        # 2. Truy van 2 snapshot theo observation_id
        from_snap = db.query(MetricSnapshot).filter(
            MetricSnapshot.source_record_id == source_record_id,
            MetricSnapshot.observation_id == from_observation_id
        ).first()

        to_snap = db.query(MetricSnapshot).filter(
            MetricSnapshot.source_record_id == source_record_id,
            MetricSnapshot.observation_id == to_observation_id
        ).first()

        if not from_snap or not to_snap:
            raise HTTPException(
                status_code=404,
                detail=f"Both observation IDs must exist for source_record '{source_record_id}'. Found: from={bool(from_snap)}, to={bool(to_snap)}"
            )

        # 3. Kiem tra thu tu thoi gian
        from_time = from_snap.observed_at
        to_time = to_snap.observed_at
        if from_time.tzinfo is None:
            from_time = from_time.replace(tzinfo=timezone.utc)
        if to_time.tzinfo is None:
            to_time = to_time.replace(tzinfo=timezone.utc)

        if to_time <= from_time:
            raise HTTPException(
                status_code=422,
                detail=f"Chronological error: to_observation time ({to_time}) must be strictly after from_observation time ({from_time})"
            )

        delta_seconds = (to_time - from_time).total_seconds()
        delta_days = round(delta_seconds / 86400.0, 6)

        # P11-08: Khoang cach thoi gian < 60s khong du dai de ngoai suy theo ngay
        if delta_seconds < 60:
            return VelocityCalculationResponse(
                source_record_id=source_record_id,
                from_observation_id=from_observation_id,
                to_observation_id=to_observation_id,
                metric_unit="views",
                from_views=from_snap.view_count,
                to_views=to_snap.view_count,
                delta_views=None,
                delta_seconds=round(delta_seconds, 2),
                delta_days=round(delta_days, 6),
                velocity_views_per_day=None,
                growth_rate=None,
                rate_status="NOT_AVAILABLE",
                notes="Observation interval is less than 60 seconds. Window is too short for daily velocity extrapolation.",
            )

        # P11-03: Neu thieu view_count o 1 trong 2 snapshot, khong duoc bien None thanh 0
        from_views = from_snap.view_count
        to_views = to_snap.view_count

        if from_views is None or to_views is None:
            delta_views = None
            velocity_views_per_day = None
            growth_rate = None
            rate_status = "NOT_AVAILABLE"
            notes = "Missing view_count in one or both snapshots. Cannot fabricate 0 views."
        else:
            delta_views = to_views - from_views
            velocity_views_per_day = round(delta_views / delta_days, 2)

            # T111: Kiem soat mau so bang 0 (Zero Denominator Safeguard)
            if from_views == 0:
                growth_rate = None
                rate_status = "NOT_AVAILABLE"
                notes = "Denominator is 0 (from_views=0); percentage growth rate cannot be calculated."
            else:
                calc_rate = delta_views / float(from_views)
                if math.isinf(calc_rate) or math.isnan(calc_rate):
                    growth_rate = None
                    rate_status = "NOT_AVAILABLE"
                    notes = "Calculated rate resulted in non-finite value; coerced to NOT_AVAILABLE."
                else:
                    growth_rate = round(calc_rate, 4)
                    rate_status = "VALID"
                    notes = None

        # P11-04: Idempotent upsert - khong nhan ban dong khi goi lai
        existing_obs = db.query(TrendVelocityObservation).filter(
            TrendVelocityObservation.workspace_id == workspace_id,
            TrendVelocityObservation.source_record_id == source_record_id,
            TrendVelocityObservation.from_observation_id == from_observation_id,
            TrendVelocityObservation.to_observation_id == to_observation_id,
            TrendVelocityObservation.metric_name == "VIEW_COUNT"
        ).first()

        if existing_obs:
            existing_obs.from_value = from_views
            existing_obs.to_value = to_views
            existing_obs.delta_value = delta_views
            existing_obs.delta_days = round(delta_days, 4)
            existing_obs.velocity_per_day = velocity_views_per_day
            existing_obs.growth_rate = growth_rate
            existing_obs.rate_status = rate_status
            existing_obs.is_paid = getattr(source, "is_paid", False)
        else:
            vel_obs = TrendVelocityObservation(
                workspace_id=workspace_id,
                source_record_id=source_record_id,
                from_observation_id=from_observation_id,
                to_observation_id=to_observation_id,
                metric_name="VIEW_COUNT",
                from_value=from_views,
                to_value=to_views,
                delta_value=delta_views,
                delta_days=round(delta_days, 4),
                velocity_per_day=velocity_views_per_day,
                growth_rate=growth_rate,
                rate_status=rate_status,
                is_paid=getattr(source, "is_paid", False),
            )
            db.add(vel_obs)

        db.commit()

        return VelocityCalculationResponse(
            source_record_id=source_record_id,
            from_observation_id=from_observation_id,
            to_observation_id=to_observation_id,
            metric_unit="views",
            from_views=from_views,
            to_views=to_views,
            delta_views=delta_views,
            delta_seconds=round(delta_seconds, 2),
            delta_days=round(delta_days, 4),
            velocity_views_per_day=velocity_views_per_day,
            growth_rate=growth_rate,
            rate_status=rate_status,
            notes=notes,
        )

velocity_engine = VelocityEngine()
