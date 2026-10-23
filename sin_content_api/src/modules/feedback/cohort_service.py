"""
Cohort Analysis Service for Phase P11 (T112).
Enforces strict cohort separation: Paid vs Organic posts are never pooled together.
Prevents false claims of organic viral growth from paid ad boosts.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.entities import SourceRecord, MetricSnapshot, TrendVelocityObservation
from src.schemas.contracts import CohortSummary, CohortAnalysisResponse

class CohortService:
    def analyze_cohorts(
        self,
        db: Session,
        workspace_id: str,
        filter_cohort: Optional[str] = "ALL"
    ) -> CohortAnalysisResponse:
        """
        T112: paid vs organic posts mixed -> separate cohorts; no pooled inference masquerading as organic results.
        """
        # 1. Truy van cac source record hop le trong workspace (loai bo purged & synthetic - P11-06)
        sources = db.query(SourceRecord).filter(
            SourceRecord.workspace_id == workspace_id,
            SourceRecord.is_purged == False,
            SourceRecord.synthetic == False,
        ).all()

        organic_sources = [s for s in sources if not getattr(s, "is_paid", False)]
        paid_sources = [s for s in sources if getattr(s, "is_paid", False)]

        # 2. Tinh toan chi so cho tung cohort mot cach tach biet hoan toan
        def _compute_cohort_stats(cohort_sources: List[SourceRecord], cohort_name: str) -> CohortSummary:
            if not cohort_sources:
                return CohortSummary(
                    cohort=cohort_name,
                    total_posts=0,
                    total_views=0,
                    average_velocity_views_per_day=0.0,
                    average_engagement_rate=None,
                    is_pooled=False,
                )

            source_ids = [s.id for s in cohort_sources]
            
            # Lay latest snapshots cho tung source trong cohort
            total_views = 0
            for s in cohort_sources:
                latest_snap = db.query(MetricSnapshot).filter(
                    MetricSnapshot.source_record_id == s.id
                ).order_by(MetricSnapshot.observed_at.desc()).first()
                if latest_snap and latest_snap.view_count:
                    total_views += latest_snap.view_count

            # Lay velocity moi nhat cho tung source_record de tranh tinh lai lam lech trung binh (P11-04)
            vel_obs = db.query(TrendVelocityObservation).filter(
                TrendVelocityObservation.workspace_id == workspace_id,
                TrendVelocityObservation.source_record_id.in_(source_ids),
                TrendVelocityObservation.is_paid == (cohort_name == "PAID"),
                TrendVelocityObservation.velocity_per_day.isnot(None),
            ).order_by(TrendVelocityObservation.created_at.desc()).all()

            # Deduplicate per source_record_id (lay ban ghi moi nhat)
            seen_sources = set()
            dedup_vels = []
            for v in vel_obs:
                if v.source_record_id not in seen_sources and v.velocity_per_day is not None:
                    seen_sources.add(v.source_record_id)
                    dedup_vels.append(v.velocity_per_day)

            avg_vel = 0.0
            if dedup_vels:
                avg_vel = round(sum(dedup_vels) / len(dedup_vels), 2)

            return CohortSummary(
                cohort=cohort_name,
                total_posts=len(cohort_sources),
                total_views=total_views,
                average_velocity_views_per_day=avg_vel,
                average_engagement_rate=None, # T111 / T112 an toan
                is_pooled=False, # Khang dinh khong bao gio pool
            )

        # P11-09: Ap dung bo loc filter_cohort thuc su
        filter_mode = (filter_cohort or "ALL").upper()

        if filter_mode == "ORGANIC":
            organic_summary = _compute_cohort_stats(organic_sources, "ORGANIC")
            paid_summary = CohortSummary(
                cohort="PAID",
                total_posts=0,
                total_views=0,
                average_velocity_views_per_day=0.0,
                average_engagement_rate=None,
                is_pooled=False,
            )
        elif filter_mode == "PAID":
            organic_summary = CohortSummary(
                cohort="ORGANIC",
                total_posts=0,
                total_views=0,
                average_velocity_views_per_day=0.0,
                average_engagement_rate=None,
                is_pooled=False,
            )
            paid_summary = _compute_cohort_stats(paid_sources, "PAID")
        else:
            organic_summary = _compute_cohort_stats(organic_sources, "ORGANIC")
            paid_summary = _compute_cohort_stats(paid_sources, "PAID")

        return CohortAnalysisResponse(
            workspace_id=workspace_id,
            filter_applied=filter_mode,
            is_pooled_inference=False, # T112: Cam tuyet doi pooled inference
            organic_cohort=organic_summary,
            paid_cohort=paid_summary,
            warning="Paid boost metrics are strictly isolated from organic discovery signals.",
        )

cohort_service = CohortService()
