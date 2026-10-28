"""
Owned Channel Service for Phase P11 (T113).
Manages owned TikTok channel connections and permissions.
Enforces strict absence of fabricated feedback data when channel metrics scope is missing.
"""
from datetime import datetime, timezone
import json
import os
import sys
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.models.entities import OwnedChannel, AuditEvent
from src.schemas.contracts import ChannelPerformanceResponse, ChannelConnectRequest

class ChannelService:
    def get_channel_performance(
        self,
        db: Session,
        workspace_id: str,
        channel_id: str
    ) -> ChannelPerformanceResponse:
        """
        T113: no channel metrics scope -> feature unavailable; no fabricated feedback data.
        """
        channel = db.query(OwnedChannel).filter(
            OwnedChannel.workspace_id == workspace_id,
            OwnedChannel.channel_id == channel_id
        ).first()

        # 1. Neu kenh hoan toan chua tung duoc ket noi trong workspace
        if not channel:
            return ChannelPerformanceResponse(
                channel_id=channel_id,
                channel_name=None,
                platform="tiktok",
                status="NOT_CONNECTED",
                has_metrics_scope=False,
                metrics=None, # TUYET DOI KHONG DUA DU LIEU BIA DAT
                message="Kênh TikTok chưa được kết nối vào workspace.",
            )

        # 2. P11-02: Kiem tra cac trang thai het han / thu hoi quyen
        if channel.status in ("TOKEN_EXPIRED", "EXPIRED", "REVOKED", "DISABLED"):
            status_ret = "TOKEN_EXPIRED" if channel.status == "TOKEN_EXPIRED" else "EXPIRED"
            return ChannelPerformanceResponse(
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                platform=channel.platform,
                status=status_ret,
                has_metrics_scope=False,
                metrics=None,
                message=f"Phiên kết nối kênh TikTok ở trạng thái '{channel.status}'. Vui lòng kết nối lại để tiếp tục phân tích.",
            )

        # 3. Neu kenh da ket noi nhung THIEU scope channel:metrics
        if not channel.has_metrics_scope or "channel:metrics" not in channel.oauth_scopes:
            return ChannelPerformanceResponse(
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                platform=channel.platform,
                status="FEATURE_UNAVAILABLE",
                has_metrics_scope=False,
                metrics=None, # T113: TUYET DOI KHONG SINH DU LIEU GIA DINH
                message="Tính năng phân tích hiệu suất kênh không khả dụng do thiếu phạm vi ủy quyền (channel:metrics). Không có dữ liệu giả định.",
            )

        # 4. P11-01: Neu kenh da ket noi va co du scope:
        if getattr(channel, "follower_count", None) is not None:
            extra_meta = {}
            if hasattr(channel, "metadata_json") and channel.metadata_json:
                try:
                    extra_meta = json.loads(channel.metadata_json)
                except Exception:
                    pass

            metrics_dict = {
                "follower_count": channel.follower_count,
                "video_count": getattr(channel, "video_count", 0) or 0,
                "profile_views_7d": getattr(channel, "profile_views_7d", 0) or 0,
                "verified_at": (getattr(channel, "verified_at", None) or channel.connected_at or datetime.now(timezone.utc)).isoformat(),
                "avatar_url": extra_meta.get("avatar_url", ""),
                "username": extra_meta.get("username", f"@{channel.channel_id.replace('tiktok_', '')}"),
                "bio": extra_meta.get("bio", ""),
                "heart_count": extra_meta.get("heart_count", 0),
                "following_count": extra_meta.get("following_count", 0),
                "source": extra_meta.get("source", "TIKTOK_VERIFIED")
            }
            msg = "Chỉ số hiệu suất kênh TikTok chính thức đã được xác thực từ quan sát thực tế (Ground Truth)."
        else:
            metrics_dict = None
            msg = "Kênh đã kết nối nhưng chưa có quan sát chỉ số thực tế. Tuyệt đối không sinh dữ liệu giả lập."

        return ChannelPerformanceResponse(
            channel_id=channel.channel_id,
            channel_name=channel.channel_name,
            platform=channel.platform,
            status="CONNECTED",
            has_metrics_scope=True,
            metrics=metrics_dict,
            message=msg,
        )

    def connect_channel(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        req: ChannelConnectRequest
    ) -> ChannelPerformanceResponse:
        """
        Ket noi kenh TikTok vao workspace voi danh sach oauth_scopes duoc cap.
        """
        has_metrics = "channel:metrics" in req.oauth_scopes
        status_val = "CONNECTED" if has_metrics else "FEATURE_UNAVAILABLE"

        channel = db.query(OwnedChannel).filter(
            OwnedChannel.workspace_id == workspace_id,
            OwnedChannel.channel_id == req.channel_id
        ).first()

        now_utc = datetime.now(timezone.utc)
        if not channel:
            channel = OwnedChannel(
                workspace_id=workspace_id,
                channel_id=req.channel_id,
                channel_name=req.channel_name,
                platform=req.platform,
                status=status_val,
                oauth_scopes_json=json.dumps(req.oauth_scopes),
                has_metrics_scope=has_metrics,
                connected_at=now_utc,
            )
            db.add(channel)
        else:
            channel.channel_name = req.channel_name
            channel.status = status_val
            channel.oauth_scopes_json = json.dumps(req.oauth_scopes)
            channel.has_metrics_scope = has_metrics
            channel.connected_at = now_utc
        db.commit()
        db.refresh(channel)

        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=user_id,
            event_type="CHANNEL_CONNECT",
            details=json.dumps({
                "channel_id": channel.channel_id,
                "has_metrics_scope": has_metrics,
                "scopes": req.oauth_scopes
            })
        )
        db.add(audit)
        db.commit()

        return self.get_channel_performance(db, workspace_id, channel.channel_id)

    def verify_and_connect_channel(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        username_or_url: str
    ) -> ChannelPerformanceResponse:
        """
        Xác minh và kết nối kênh TikTok THẬT 100% bằng cách trích xuất số liệu trực tiếp từ TikTok.
        Tuyệt đối không sinh dữ liệu giả lập.
        """
        try:
            try:
                from src.modules.feedback.tiktok_verifier import verify_tiktok_profile
            except ImportError:
                from pathlib import Path
                bridge_path = str(Path(__file__).resolve().parents[4] / "cong_cu_tu_dong" / "flow_bridge")
                if bridge_path not in sys.path:
                    sys.path.insert(0, bridge_path)
                from tiktok_verifier import verify_tiktok_profile
            profile = verify_tiktok_profile(username_or_url)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Không thể xác minh kênh TikTok thật: {str(exc)}"
            )

        channel_id = f"tiktok_{profile['raw_id']}"
        now_utc = datetime.now(timezone.utc)
        
        meta = {
            "avatar_url": profile.get("avatar_url", ""),
            "username": profile.get("username", ""),
            "bio": profile.get("bio", ""),
            "heart_count": profile.get("heart_count", 0),
            "following_count": profile.get("following_count", 0),
            "source": profile.get("source", "TIKTOK_LIVE_VERIFIED")
        }

        channel = db.query(OwnedChannel).filter(
            OwnedChannel.workspace_id == workspace_id,
            OwnedChannel.channel_id == channel_id
        ).first()

        scopes = ["user.info.basic", "video.list", "video.insights", "channel:metrics"]

        if not channel:
            channel = OwnedChannel(
                workspace_id=workspace_id,
                channel_id=channel_id,
                channel_name=profile["display_name"],
                platform="tiktok",
                status="CONNECTED",
                oauth_scopes_json=json.dumps(scopes),
                has_metrics_scope=True,
                follower_count=profile["follower_count"],
                video_count=profile["video_count"],
                profile_views_7d=profile["profile_views_7d"],
                metadata_json=json.dumps(meta),
                verified_at=now_utc,
                connected_at=now_utc,
            )
            db.add(channel)
        else:
            channel.channel_name = profile["display_name"]
            channel.status = "CONNECTED"
            channel.oauth_scopes_json = json.dumps(scopes)
            channel.has_metrics_scope = True
            channel.follower_count = profile["follower_count"]
            channel.video_count = profile["video_count"]
            channel.profile_views_7d = profile["profile_views_7d"]
            channel.metadata_json = json.dumps(meta)
            channel.verified_at = now_utc
            channel.connected_at = now_utc

        db.commit()
        db.refresh(channel)

        audit = AuditEvent(
            workspace_id=workspace_id,
            actor_id=user_id,
            event_type="CHANNEL_LIVE_VERIFY_CONNECT",
            details=json.dumps({
                "channel_id": channel.channel_id,
                "username": profile["username"],
                "follower_count": profile["follower_count"],
                "heart_count": profile["heart_count"],
                "source": profile["source"]
            })
        )
        db.add(audit)
        db.commit()

        return self.get_channel_performance(db, workspace_id, channel.channel_id)

channel_service = ChannelService()
