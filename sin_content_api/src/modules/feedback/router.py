"""
Router API cho Pha P11: Owned Channel Feedback Loop & Trend Velocity (/v1/feedback)
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import TenantContext, require_action
from src.schemas.contracts import (
    VelocityCalculationRequest,
    VelocityCalculationResponse,
    CohortAnalysisResponse,
    ChannelPerformanceResponse,
    ChannelConnectRequest,
    ChannelVerifyRequest,
    PublishedContentLinkCreateRequest,
    PublishedContentLinkResponse,
    PublishedContentLinkListResponse,
    PerformanceSnapshotCreateRequest,
    PerformanceSnapshotResponse,
    LearningSignalResponse,
    LearningSignalListResponse,
)
from src.modules.feedback.published_links_service import published_links_service
from src.modules.feedback.velocity_engine import velocity_engine
from src.modules.feedback.cohort_service import cohort_service
from src.modules.feedback.channel_service import channel_service

router = APIRouter(prefix="/v1/feedback", tags=["Owned Channel Feedback & Trend Velocity"])

@router.post("/velocity/calculate", response_model=VelocityCalculationResponse)
def calculate_trend_velocity(
    payload: VelocityCalculationRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("analytics.read"))
):
    """
    T110 & T111: Tinh toan van toc tang truong giua 2 snapshot quan sat hop le.
    Tham chieu day du ca 2 observation IDs, kiem soat mau so bang 0 khong bao gio sinh Infinity/NaN/crash.
    """
    return velocity_engine.calculate_velocity(
        db=db,
        workspace_id=tenant.workspace_id,
        source_record_id=payload.source_record_id,
        from_observation_id=payload.from_observation_id,
        to_observation_id=payload.to_observation_id,
    )

@router.get("/cohorts/summary", response_model=CohortAnalysisResponse)
def get_cohort_summary(
    workspace_id: Optional[str] = Query(None),
    cohort: Optional[str] = Query("ALL", pattern="^(ALL|ORGANIC|PAID)$"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("analytics.read"))
):
    if workspace_id and workspace_id != tenant.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot query cohorts across workspaces"
        )
    """
    T112: Phan tich hieu suat theo tung nhom tach biet (Paid vs Organic).
    Tuyet doi cam gop so lieu (no pooled inference) quang cao vao ket qua tu nhien.
    """
    return cohort_service.analyze_cohorts(
        db=db,
        workspace_id=tenant.workspace_id,
        filter_cohort=cohort,
    )

@router.get("/channels", response_model=list[ChannelPerformanceResponse])
def list_workspace_channels(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("channel.read"))
):
    """
    Liet ke danh sach cac kenh TikTok da ket noi trong workspace.
    """
    from src.models.entities import OwnedChannel
    channels = db.query(OwnedChannel).filter(
        OwnedChannel.workspace_id == tenant.workspace_id
    ).all()
    return [
        channel_service.get_channel_performance(db, tenant.workspace_id, c.channel_id)
        for c in channels
    ]

@router.get("/channels/{channel_id}/performance", response_model=ChannelPerformanceResponse)
def get_channel_performance(
    channel_id: str,
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("channel.read"))
):
    """
    T113: Phan tich hieu suat kenh TikTok so huu.
    Neu thieu quyen/scope channel:metrics, tra ve FEATURE_UNAVAILABLE; tuyet doi khong sinh so lieu bia dat.
    """
    if workspace_id and workspace_id != tenant.workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot query channel performance across workspaces"
        )
    return channel_service.get_channel_performance(
        db=db,
        workspace_id=tenant.workspace_id,
        channel_id=channel_id,
    )

@router.post("/channels/verify-and-connect", response_model=ChannelPerformanceResponse)
def verify_and_connect_channel(
    payload: ChannelVerifyRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("channel.connect"))
):
    """
    Xác minh và kết nối kênh TikTok THẬT 100% từ TikTok Live Profile (Ground Truth).
    Trích xuất số lượng follower, following, like, video và avatar thật trực tiếp.
    """
    return channel_service.verify_and_connect_channel(
        db=db,
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        username_or_url=payload.username_or_url
    )

@router.post("/channels/connect", response_model=ChannelPerformanceResponse)
def connect_channel(
    payload: ChannelConnectRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("channel.connect"))
):
    """
    Ket noi kenh TikTok vao workspace va khai bao oauth_scopes duoc cap quyen.
    """
    return channel_service.connect_channel(
        db=db,
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        req=payload,
    )

# ==============================================================================
# P11: PUBLISHED CONTENT LINKS, PERFORMANCE SNAPSHOTS & LEARNING SIGNALS
# ==============================================================================

@router.post("/published-links", response_model=PublishedContentLinkResponse)
def create_published_link(
    payload: PublishedContentLinkCreateRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("publishing.schedule"))
):
    """P11: Gan lien ket bai dang thuc te voi ban kich ban da duyet."""
    return published_links_service.create_link(
        db=db,
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        req=payload,
    )

@router.post("/published-links/{link_id}/detach", response_model=PublishedContentLinkResponse)
def detach_published_link(
    link_id: str,
    reason: Optional[str] = Query("USER_REQUESTED_DETACH"),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("publishing.cancel"))
):
    """P11: Thao lien ket bai dang theo chinh sach du lieu."""
    return published_links_service.detach_link(
        db=db,
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        link_id=link_id,
        reason=reason,
    )

@router.get("/published-links", response_model=PublishedContentLinkListResponse)
def list_published_links(
    script_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("analytics.read"))
):
    """P11: Liet ke cac bai dang thuc te da lien ket trong workspace."""
    return published_links_service.list_links(
        db=db,
        workspace_id=tenant.workspace_id,
        script_id=script_id,
        status_filter=status,
    )

@router.post("/performance-snapshots", response_model=PerformanceSnapshotResponse)
def add_performance_snapshot(
    payload: PerformanceSnapshotCreateRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("analytics.read"))
):
    """P11: Ghi nhan snapshot quan sat hieu suat thuc te cho bai dang da lien ket."""
    return published_links_service.add_performance_snapshot(
        db=db,
        workspace_id=tenant.workspace_id,
        user_id=tenant.user_id,
        req=payload,
    )

@router.get("/learning-signals", response_model=LearningSignalListResponse)
def list_learning_signals(
    link_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("analytics.read"))
):
    """P11: Doc tin hieu hoc may va de xuat thuc nghiem kem giai thich cong thuc & gioi han."""
    return published_links_service.list_learning_signals(
        db=db,
        workspace_id=tenant.workspace_id,
        link_id=link_id,
    )

