# -*- coding: utf-8 -*-
"""
Bộ kiểm thử mở rộng cho Pha P11: Khắc phục triệt để 9 phát hiện rà soát độc lập (P11-01 đến P11-09)
và hoàn thiện 100% tiêu chuẩn Cổng nghiệm thu Gate P11 (MASTER_PLAN & CONTRACTS).

Bao gồm:
1. P11-01: Không trả số liệu cố định/giả mạo khi chưa có quan sát thực tế.
2. P11-02: Kênh hết hạn/thu hồi trả về trạng thái hết hạn và metrics = None.
3. P11-03: View count bị thiếu (None) giữ nguyên None, không biến thành 0 hay sinh vận tốc giả mạo.
4. P11-04: Tính lại cùng cặp snapshot đảm bảo tính Idempotent, không nhân bản dòng làm lệch trung bình.
5. P11-05: Ingestion bảo toàn trường is_paid và channel_id, không làm lẫn bài quảng cáo vào tự nhiên.
6. P11-06: Nguồn đã purge hoặc synthetic không được dùng để tính vận tốc / phản hồi hiệu suất.
7. P11-07: Chu trình hoàn chỉnh PublishedContentLink, PerformanceSnapshot, LearningSignal & Detach.
8. P11-08: Khoảng cách quan sát < 60s không đổi ngầm khoảng thời gian bằng hằng số.
9. P11-09: Bộ lọc cohort (ORGANIC vs PAID) lọc kết quả thực sự.
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "sqlite:///file:sin_content_p11_gate_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = (
    "sqlite:///file:baha_auth_p11_gate_test?mode=memory&cache=shared&uri=true"
)
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-p11-gate-secret-key-2026"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "sin-auth-p11-gate"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-p11-gate"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    Workspace, User, SourceRecord, MetricSnapshot, OwnedChannel,
    TrendVelocityObservation, ScriptDraftVersion, IdeaCard, BrandBriefVersion,
    PublishedContentLink, PerformanceSnapshot, LearningSignal,
)
from baha_auth.src.database import (
    Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine,
)
from baha_auth.src.models.entities import (
    GlobalUser,
    Membership as AuthMembership,
    Role as AuthRole,
    RoleAssignment,
    Workspace as AuthWorkspace,
)
from src.modules.ingestion.service import ingestion_service

client = TestClient(app)

def tao_token(user_id: str) -> str:
    def encode(val):
        raw = json.dumps(val, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = encode({"alg": "HS256", "typ": "JWT"})
    claims = encode({
        "sub": user_id,
        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],
        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],
        "exp": int(time.time()) + 3600,
    })
    sig = hmac.new(
        os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"),
        f"{header}.{claims}".encode("ascii"),
        hashlib.sha256
    ).digest()
    return f"{header}.{claims}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode('ascii')}"

@pytest.fixture
def p11_gate_fixture():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)

    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    slug = f"p11-gate-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        ws = Workspace(id=ws_id, name="P11 Gate Workspace", slug=slug)
        user = User(id=user_id, email=f"{slug}@baha.vn", full_name="P11 Owner")
        db.add_all([ws, user])
        db.commit()

    with AuthSessionLocal() as auth_db:
        aws = AuthWorkspace(id=ws_id, name="P11 Gate Workspace", slug=slug)
        gu = GlobalUser(id=user_id, email=f"{slug}@baha.vn", full_name="P11 Owner")
        auth_db.add_all([aws, gu])
        auth_db.flush()

        role = auth_db.query(AuthRole).filter(AuthRole.code == "WORKSPACE_OWNER").first()
        if not role:
            role = AuthRole(code="WORKSPACE_OWNER", name="Owner", workspace_id=None, is_template=True, status="ACTIVE")
            auth_db.add(role)
            auth_db.flush()

        mem_id = str(uuid.uuid4())
        mem = AuthMembership(id=mem_id, user_id=user_id, workspace_id=ws_id, status="ACTIVE")
        auth_db.add(mem)
        auth_db.flush()

        ra = RoleAssignment(
            workspace_id=ws_id,
            membership_id=mem_id,
            role_id=role.id,
            scope_type="WORKSPACE",
            scope_id=ws_id,
            status="ACTIVE",
        )
        auth_db.add(ra)
        auth_db.commit()

    token = tao_token(user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": ws_id,
        "X-User-Id": user_id,
    }

    return {"workspace_id": ws_id, "user_id": user_id, "headers": headers}

# ==============================================================================
# TESTS CHO CÁC PHÁT HIỆN P11-01 ĐẾN P11-09 & WORKFLOW PUBLISHED LINKS
# ==============================================================================

def test_p11_01_no_fabricated_metrics_without_observations(p11_gate_fixture):
    """P11-01: Kênh kết nối không được bịa đặt metrics cố định khi chưa có quan sát."""
    ws_id = p11_gate_fixture["workspace_id"]
    headers = p11_gate_fixture["headers"]

    with SessionLocal() as db:
        chan = OwnedChannel(
            workspace_id=ws_id,
            channel_id="chan_clean_no_obs",
            channel_name="Clean Channel",
            platform="tiktok",
            status="CONNECTED",
            has_metrics_scope=True,
            oauth_scopes_json=json.dumps(["user.info.basic", "channel:metrics"]),
            follower_count=None, # Khong co quan sat
        )
        db.add(chan)
        db.commit()

    resp = client.get(f"/v1/feedback/channels/chan_clean_no_obs/performance?workspace_id={ws_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CONNECTED"
    assert data["metrics"] is None, "Khi chua co quan sat thuc te, metrics bat buoc phai la None!"
    assert "chưa có quan sát" in data["message"]

def test_p11_02_expired_connection_returns_expired_status(p11_gate_fixture):
    """P11-02: Kênh hết hạn token trả về TOKEN_EXPIRED và metrics=None."""
    ws_id = p11_gate_fixture["workspace_id"]
    headers = p11_gate_fixture["headers"]

    with SessionLocal() as db:
        chan = OwnedChannel(
            workspace_id=ws_id,
            channel_id="chan_token_expired_1",
            channel_name="Expired Channel",
            platform="tiktok",
            status="TOKEN_EXPIRED",
            has_metrics_scope=True,
            oauth_scopes_json=json.dumps(["user.info.basic", "channel:metrics"]),
            follower_count=10000,
        )
        db.add(chan)
        db.commit()

    resp = client.get(f"/v1/feedback/channels/chan_token_expired_1/performance?workspace_id={ws_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "TOKEN_EXPIRED"
    assert data["has_metrics_scope"] is False
    assert data["metrics"] is None

def test_p11_03_null_views_not_converted_to_zero(p11_gate_fixture):
    """P11-03: Snapshot có lượt xem None giữ nguyên None, không biến thành 0 hay tính vận tốc giả mạo."""
    ws_id = p11_gate_fixture["workspace_id"]
    headers = p11_gate_fixture["headers"]

    with SessionLocal() as db:
        sr = SourceRecord(workspace_id=ws_id, provider_id="test", raw_external_id="sr_null_view", title="Post")
        db.add(sr)
        db.flush()
        t1 = datetime.now(timezone.utc) - timedelta(days=2)
        t2 = datetime.now(timezone.utc)
        s1 = MetricSnapshot(source_record_id=sr.id, observation_id="obs_null_1", view_count=None, observed_at=t1)
        s2 = MetricSnapshot(source_record_id=sr.id, observation_id="obs_null_2", view_count=100, observed_at=t2)
        db.add_all([s1, s2])
        db.commit()
        sr_id = sr.id

    resp = client.post(
        "/v1/feedback/velocity/calculate",
        json={"source_record_id": sr_id, "from_observation_id": "obs_null_1", "to_observation_id": "obs_null_2"},
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rate_status"] == "NOT_AVAILABLE"
    assert data["delta_views"] is None
    assert data["velocity_views_per_day"] is None
    assert data["from_views"] is None

def test_p11_04_idempotent_velocity_calculation(p11_gate_fixture):
    """P11-04: Gọi lại phép tính vận tốc trên cùng cặp snapshot không sinh thêm dòng làm lệch thống kê."""
    ws_id = p11_gate_fixture["workspace_id"]
    headers = p11_gate_fixture["headers"]

    with SessionLocal() as db:
        sr = SourceRecord(workspace_id=ws_id, provider_id="test", raw_external_id="sr_idemp_1", title="Post", is_paid=False)
        db.add(sr)
        db.flush()
        t1 = datetime.now(timezone.utc) - timedelta(days=3)
        t2 = datetime.now(timezone.utc)
        s1 = MetricSnapshot(source_record_id=sr.id, observation_id="obs_idemp_1", view_count=1000, observed_at=t1)
        s2 = MetricSnapshot(source_record_id=sr.id, observation_id="obs_idemp_2", view_count=4000, observed_at=t2)
        db.add_all([s1, s2])
        db.commit()
        sr_id = sr.id

    payload = {"source_record_id": sr_id, "from_observation_id": "obs_idemp_1", "to_observation_id": "obs_idemp_2"}
    # Goi 3 lan lien tiep
    resp1 = client.post("/v1/feedback/velocity/calculate", json=payload, headers=headers)
    resp2 = client.post("/v1/feedback/velocity/calculate", json=payload, headers=headers)
    resp3 = client.post("/v1/feedback/velocity/calculate", json=payload, headers=headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp3.status_code == 200

    with SessionLocal() as db:
        count = db.query(TrendVelocityObservation).filter(
            TrendVelocityObservation.source_record_id == sr_id,
            TrendVelocityObservation.from_observation_id == "obs_idemp_1",
            TrendVelocityObservation.to_observation_id == "obs_idemp_2"
        ).count()
        assert count == 1, "Idempotent upsert bat buoc chi duy tri 1 ban ghi duy nhat!"

def test_p11_05_ingestion_preserves_is_paid_and_channel_id(p11_gate_fixture):
    """P11-05: Ingestion giữ nguyên phân loại trả phí (is_paid) và channel_id."""
    ws_id = p11_gate_fixture["workspace_id"]
    with SessionLocal() as db:
        res = ingestion_service.ingest_batch(
            workspace_id=ws_id,
            items=[{
                "observation_id": "obs_paid_001",
                "external_id": "paid_post_p11_ext",
                "title": "Quang cao TikTok",
                "is_paid": True,
                "channel_id": "kenh_paid_999",
                "view_count": 50000,
            }],
            actor_user_id=p11_gate_fixture["user_id"],
            is_production=False,
            db=db,
        )
        assert res['created_sources'] == 1
        sr = db.query(SourceRecord).filter(SourceRecord.raw_external_id == "paid_post_p11_ext").first()
        assert sr is not None
        assert sr.is_paid is True
        assert sr.channel_id == "kenh_paid_999"

def test_p11_06_purged_source_rejected(p11_gate_fixture):
    """P11-06: Nguồn đã purge bị từ chối tính toán vận tốc."""
    ws_id = p11_gate_fixture["workspace_id"]
    headers = p11_gate_fixture["headers"]

    with SessionLocal() as db:
        sr = SourceRecord(workspace_id=ws_id, provider_id="test", raw_external_id="sr_purged_1", title="Post", is_purged=True)
        db.add(sr)
        db.flush()
        t1 = datetime.now(timezone.utc) - timedelta(days=1)
        t2 = datetime.now(timezone.utc)
        s1 = MetricSnapshot(source_record_id=sr.id, observation_id="obs_p_1", view_count=10, observed_at=t1)
        s2 = MetricSnapshot(source_record_id=sr.id, observation_id="obs_p_2", view_count=20, observed_at=t2)
        db.add_all([s1, s2])
        db.commit()
        sr_id = sr.id

    resp = client.post(
        "/v1/feedback/velocity/calculate",
        json={"source_record_id": sr_id, "from_observation_id": "obs_p_1", "to_observation_id": "obs_p_2"},
        headers=headers
    )
    assert resp.status_code == 422
    assert "purged" in resp.text.lower()

def test_p11_07_published_content_links_workflow(p11_gate_fixture):
    """P11-07: Luồng hoàn chỉnh gắn link bài đăng thực tế, snapshot hiệu suất, tín hiệu học máy và detach."""
    ws_id = p11_gate_fixture["workspace_id"]
    headers = p11_gate_fixture["headers"]

    # 1. Tao ScriptDraftVersion approved
    with SessionLocal() as db:
        brief = BrandBriefVersion(
            workspace_id=ws_id,
            version=1,
            brand_name="BAHA",
            objective="Xay kenh TikTok",
            voice_description="Giong chuyen gia",
            current_audience="Khan gia 18-35",
            target_audience="Khach hang muc tieu",
            status="APPROVED",
        )
        db.add(brief)
        db.flush()
        card = IdeaCard(
            workspace_id=ws_id,
            brief_version_id=brief.id,
            title="Idea 1",
            target_need="Need 1",
            hook="Hook 1",
            content_angle="Angle 1",
            status="APPROVED",
        )
        db.add(card)
        db.flush()
        script = ScriptDraftVersion(
            workspace_id=ws_id,
            idea_id=card.id,
            version=1,
            title="Approved Script",
            status="APPROVED",
        )
        db.add(script)
        db.commit()
        script_id = script.id

    # 2. Tao PublishedContentLink
    create_resp = client.post(
        "/v1/feedback/published-links",
        json={
            "script_draft_version_id": script_id,
            "platform": "tiktok",
            "external_post_id": "tt_post_123456",
            "external_post_url": "https://www.tiktok.com/@baha/video/123456",
            "channel_id": "chan_baha_official",
            "is_paid": False,
        },
        headers=headers
    )
    assert create_resp.status_code == 200
    link_data = create_resp.json()
    link_id = link_data["id"]
    assert link_data["status"] == "ACTIVE"
    assert link_data["script_draft_version_id"] == script_id

    # 3. List published links
    list_resp = client.get(f"/v1/feedback/published-links?script_id={script_id}", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    # 4. Them 2 snapshot hieu suat cach nhau
    t1 = datetime.now(timezone.utc) - timedelta(days=1)
    t2 = datetime.now(timezone.utc)
    snap1_resp = client.post(
        "/v1/feedback/performance-snapshots",
        json={
            "published_content_link_id": link_id,
            "view_count": 5000,
            "like_count": 400,
            "comment_count": 50,
            "completion_rate": 0.45,
            "observed_at": t1.isoformat(),
        },
        headers=headers
    )
    assert snap1_resp.status_code == 200

    snap2_resp = client.post(
        "/v1/feedback/performance-snapshots",
        json={
            "published_content_link_id": link_id,
            "view_count": 15000,
            "like_count": 1200,
            "comment_count": 180,
            "completion_rate": 0.62,
            "observed_at": t2.isoformat(),
        },
        headers=headers
    )
    assert snap2_resp.status_code == 200

    # 5. Kiem tra LearningSignals duoc sinh tu dong tu >= 2 snapshot
    signals_resp = client.get(f"/v1/feedback/learning-signals?link_id={link_id}", headers=headers)
    assert signals_resp.status_code == 200
    signals_data = signals_resp.json()
    assert signals_data["total"] >= 1
    hook_signal = next((s for s in signals_data["items"] if s["signal_type"] == "HOOK_PERFORMANCE"), None)
    assert hook_signal is not None
    assert hook_signal["score"] > 0
    assert "completion_rate" in hook_signal["formula_applied"]
    assert hook_signal["limitations_note"] is not None

    # 6. Thao lien ket (Detach link) theo chinh sach bao mat
    detach_resp = client.post(f"/v1/feedback/published-links/{link_id}/detach?reason=CAMPAIGN_ENDED", headers=headers)
    assert detach_resp.status_code == 200
    detach_data = detach_resp.json()
    assert detach_data["status"] == "DETACHED"
    assert detach_data["detached_at"] is not None

def test_p11_08_window_under_60s_returns_not_available(p11_gate_fixture):
    """P11-08: Khoảng thời gian < 60s trả về NOT_AVAILABLE, không đổi ngầm thời gian."""
    ws_id = p11_gate_fixture["workspace_id"]
    headers = p11_gate_fixture["headers"]

    with SessionLocal() as db:
        sr = SourceRecord(workspace_id=ws_id, provider_id="test", raw_external_id="sr_short_window", title="Post")
        db.add(sr)
        db.flush()
        t1 = datetime.now(timezone.utc) - timedelta(seconds=10)
        t2 = datetime.now(timezone.utc)
        s1 = MetricSnapshot(source_record_id=sr.id, observation_id="obs_short_1", view_count=100, observed_at=t1)
        s2 = MetricSnapshot(source_record_id=sr.id, observation_id="obs_short_2", view_count=105, observed_at=t2)
        db.add_all([s1, s2])
        db.commit()
        sr_id = sr.id

    resp = client.post(
        "/v1/feedback/velocity/calculate",
        json={"source_record_id": sr_id, "from_observation_id": "obs_short_1", "to_observation_id": "obs_short_2"},
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rate_status"] == "NOT_AVAILABLE"
    assert data["velocity_views_per_day"] is None
    assert "less than 60 seconds" in data["notes"]

def test_p11_09_cohort_filter_actually_filters(p11_gate_fixture):
    """P11-09: Tham số filter cohort=ORGANIC thực sự lọc bỏ paid cohort."""
    ws_id = p11_gate_fixture["workspace_id"]
    headers = p11_gate_fixture["headers"]

    with SessionLocal() as db:
        sr_org = SourceRecord(workspace_id=ws_id, provider_id="test", raw_external_id="sr_filter_org", title="Org", is_paid=False)
        sr_paid = SourceRecord(workspace_id=ws_id, provider_id="test", raw_external_id="sr_filter_paid", title="Paid", is_paid=True)
        db.add_all([sr_org, sr_paid])
        db.flush()
        t = datetime.now(timezone.utc)
        s1 = MetricSnapshot(source_record_id=sr_org.id, observation_id="s_org", view_count=500, observed_at=t)
        s2 = MetricSnapshot(source_record_id=sr_paid.id, observation_id="s_paid", view_count=5000, observed_at=t)
        db.add_all([s1, s2])
        db.commit()

    resp = client.get(f"/v1/feedback/cohorts/summary?cohort=ORGANIC&workspace_id={ws_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["filter_applied"] == "ORGANIC"
    assert data["organic_cohort"]["total_posts"] == 1
    assert data["organic_cohort"]["total_views"] == 500
    assert data["paid_cohort"]["total_posts"] == 0, "Khi filter=ORGANIC, paid_cohort phai duoc loc bo!"
    assert data["paid_cohort"]["total_views"] == 0
