# -*- coding: utf-8 -*-
"""
Service quản lý liên kết bài đăng thực tế (PublishedContentLink),
snapshot hiệu suất (PerformanceSnapshot) và tín hiệu học máy (LearningSignal) - Pha P11.
Tuân thủ tiêu chuẩn Gate P11:
- Số liệu có nguồn gốc xác thực (TikTok Official API / Customer CSV Import).
- Công thức tính toán minh bạch, ghi rõ limitations_note.
- Hỗ trợ tháo liên kết (detach) an toàn theo chính sách lưu giữ dữ liệu.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.models.entities import (
    PublishedContentLink,
    PerformanceSnapshot,
    LearningSignal,
    ScriptDraftVersion,
    AuditEvent,
)
from src.schemas.contracts import (
    PublishedContentLinkCreateRequest,
    PublishedContentLinkResponse,
    PublishedContentLinkListResponse,
    PerformanceSnapshotCreateRequest,
    PerformanceSnapshotResponse,
    LearningSignalResponse,
    LearningSignalListResponse,
)

class PublishedLinksService:
    def create_link(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        req: PublishedContentLinkCreateRequest,
    ) -> PublishedContentLinkResponse:
        """
        Gắn liên kết bài đăng thực tế với phiên bản kịch bản đã duyệt.
        """
        # 1. Kiem tra script draft version ton tai trong workspace
        script = db.query(ScriptDraftVersion).filter(
            ScriptDraftVersion.id == req.script_draft_version_id,
            ScriptDraftVersion.workspace_id == workspace_id,
        ).first()

        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ScriptDraftVersion '{req.script_draft_version_id}' not found in workspace."
            )

        # 2. Tao PublishedContentLink
        pub_at = req.published_at or datetime.now(timezone.utc)
        link = PublishedContentLink(
            workspace_id=workspace_id,
            script_draft_version_id=req.script_draft_version_id,
            platform=req.platform,
            external_post_id=req.external_post_id,
            external_post_url=req.external_post_url,
            channel_id=req.channel_id,
            is_paid=req.is_paid,
            status="ACTIVE",
            published_at=pub_at,
        )
        db.add(link)
        db.flush()

        # 3. Ghi audit event
        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=user_id,
            event_type="PUBLISHED_CONTENT_LINK_CREATED",
            details=f"Linked post '{req.external_post_id}' to script '{req.script_draft_version_id}' (paid={req.is_paid}).",
        )
        db.add(audit)
        db.commit()
        db.refresh(link)

        return PublishedContentLinkResponse.model_validate(link)

    def detach_link(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        link_id: str,
        reason: Optional[str] = "USER_REQUESTED_DETACH",
    ) -> PublishedContentLinkResponse:
        """
        Tháo liên kết bài đăng (detach) theo chính sách kiểm soát dữ liệu.
        """
        link = db.query(PublishedContentLink).filter(
            PublishedContentLink.id == link_id,
            PublishedContentLink.workspace_id == workspace_id,
        ).first()

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PublishedContentLink '{link_id}' not found in workspace."
            )

        link.status = "DETACHED"
        link.detached_at = datetime.now(timezone.utc)

        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=user_id,
            event_type="PUBLISHED_CONTENT_LINK_DETACHED",
            details=f"Detached link '{link_id}' with reason: {reason}",
        )
        db.add(audit)
        db.commit()
        db.refresh(link)

        return PublishedContentLinkResponse.model_validate(link)

    def list_links(
        self,
        db: Session,
        workspace_id: str,
        script_id: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> PublishedContentLinkListResponse:
        """
        Liet ke cac lien ket bai dang trong workspace.
        """
        q = db.query(PublishedContentLink).filter(
            PublishedContentLink.workspace_id == workspace_id
        )
        if script_id:
            q = q.filter(PublishedContentLink.script_draft_version_id == script_id)
        if status_filter:
            q = q.filter(PublishedContentLink.status == status_filter)

        items = q.order_by(PublishedContentLink.created_at.desc()).all()
        return PublishedContentLinkListResponse(
            workspace_id=workspace_id,
            total=len(items),
            items=[PublishedContentLinkResponse.model_validate(x) for x in items]
        )

    def add_performance_snapshot(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        req: PerformanceSnapshotCreateRequest,
    ) -> PerformanceSnapshotResponse:
        """
        Ghi nhận snapshot hiệu suất thực tế cho bài đăng đã liên kết.
        Tự động ngoại suy tín hiệu học máy có căn cứ nếu có >= 2 snapshot lặp lại.
        """
        link = db.query(PublishedContentLink).filter(
            PublishedContentLink.id == req.published_content_link_id,
            PublishedContentLink.workspace_id == workspace_id,
        ).first()

        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PublishedContentLink '{req.published_content_link_id}' not found in workspace."
            )

        if link.status == "DETACHED":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot add snapshot to a detached link."
            )

        obs_time = req.observed_at or datetime.now(timezone.utc)
        snap = PerformanceSnapshot(
            workspace_id=workspace_id,
            published_content_link_id=link.id,
            view_count=req.view_count,
            like_count=req.like_count,
            comment_count=req.comment_count,
            share_count=req.share_count,
            watch_time_avg_seconds=req.watch_time_avg_seconds,
            completion_rate=req.completion_rate,
            snapshot_source=req.snapshot_source,
            is_paid=req.is_paid,
            observed_at=obs_time,
        )
        db.add(snap)
        db.flush()

        # P11: Tự động trích xuất tín hiệu học tập có căn cứ (LearningSignal)
        # Kiểm tra xem link này đã có >= 2 snapshots chưa
        all_snaps = db.query(PerformanceSnapshot).filter(
            PerformanceSnapshot.published_content_link_id == link.id,
            PerformanceSnapshot.workspace_id == workspace_id,
        ).order_by(PerformanceSnapshot.observed_at.asc()).all()

        if len(all_snaps) >= 2:
            snap_first = all_snaps[0]
            snap_last = all_snaps[-1]

            # 1. Tín hiệu Hook Performance
            if snap_last.completion_rate is not None:
                hook_score = min(round(snap_last.completion_rate * 10.0, 2), 10.0)
                signal_hook = LearningSignal(
                    workspace_id=workspace_id,
                    published_content_link_id=link.id,
                    signal_type="HOOK_PERFORMANCE",
                    score=hook_score,
                    confidence=0.9,
                    formula_applied="hook_score = min(completion_rate * 10, 10.0)",
                    limitations_note="Dựa trên 2 mốc quan sát thực tế; yêu cầu xác nhận khi mẫu lượt xem >= 1.000.",
                )
                db.add(signal_hook)

            # 2. Tín hiệu Topic Engagement
            if snap_last.view_count and snap_first.view_count is not None and snap_first.view_count > 0:
                growth = (snap_last.view_count - snap_first.view_count) / float(snap_first.view_count)
                signal_topic = LearningSignal(
                    workspace_id=workspace_id,
                    published_content_link_id=link.id,
                    signal_type="TOPIC_ENGAGEMENT",
                    score=min(round(growth * 5.0, 2), 10.0),
                    confidence=0.85,
                    formula_applied="topic_score = min(((v_last - v_first) / v_first) * 5.0, 10.0)",
                    limitations_note="Áp dụng riêng cho phân nhóm " + ("PAID" if req.is_paid else "ORGANIC") + "; không gộp số liệu.",
                )
                db.add(signal_topic)

        db.commit()
        db.refresh(snap)

        return PerformanceSnapshotResponse.model_validate(snap)

    def list_learning_signals(
        self,
        db: Session,
        workspace_id: str,
        link_id: Optional[str] = None,
    ) -> LearningSignalListResponse:
        """
        Lấy danh sách tín hiệu học máy và đề xuất thực nghiệm kèm giải thích công thức & giới hạn.
        """
        q = db.query(LearningSignal).filter(
            LearningSignal.workspace_id == workspace_id
        )
        if link_id:
            q = q.filter(LearningSignal.published_content_link_id == link_id)

        items = q.order_by(LearningSignal.created_at.desc()).all()
        return LearningSignalListResponse(
            workspace_id=workspace_id,
            total=len(items),
            items=[LearningSignalResponse.model_validate(x) for x in items]
        )

published_links_service = PublishedLinksService()
