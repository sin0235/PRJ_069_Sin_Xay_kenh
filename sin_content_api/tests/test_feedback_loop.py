"""
Bo kiem thu Pha P11: Owned Channel Feedback Loop & Trend Velocity / Signal Extrapolation
Bao gom cac ca kiem thu nghiem ngat:
- T110: Derived delta references exact observation IDs, equivalent units, delta time,
        va normalized velocity (velocity_views_per_day).
- T111: View count=0 denominator -> rate_status = "NOT_AVAILABLE", growth_rate = None;
        tuyet doi khong bao gio tra ve Infinity, -Infinity, NaN hay gap ZeroDivisionError.
- T112: Paid vs organic posts mixed -> bóc tách thành 2 cohorts riêng rẽ (ORGANIC vs PAID);
        tuyet doi cam gom chung so lieu (no pooled inference masquerading as organic results).
- T113: No channel metrics scope -> status = "FEATURE_UNAVAILABLE" / "NOT_CONNECTED",
        metrics = None; tuyet doi khong sinh du lieu phan hoi gia dinh/bia dat (no fabricated feedback data).
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

# Cau hinh moi truong cho SQLite in-memory de dam bao doc lap hoan toan
TEST_DATABASE_URL = "sqlite:///file:sin_content_p11_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = (
    "sqlite:///file:baha_auth_p11_test?mode=memory&cache=shared&uri=true"
)
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-bang-khoa-gia-lap-p11"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-nha-cung-cap-p11"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test-p11"

# Them duong dan chua baha_auth vao sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    Workspace, User, SourceRecord, MetricSnapshot, OwnedChannel, TrendVelocityObservation
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

client = TestClient(app)


def tao_bearer(user_id: str) -> str:
    def encode(value):
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = encode({"alg": "HS256", "typ": "JWT"})
    claims = encode({
        "sub": user_id,
        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],
        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],
        "exp": int(time.time()) + 3600,
    })
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(
        os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{header}.{claims}.{encoded_signature}"


def lay_role(db, code: str):
    role = db.query(AuthRole).filter(AuthRole.code == code).first()
    if role is None:
        role = AuthRole(code=code, name=code, workspace_id=None, is_template=True, status="ACTIVE")
        db.add(role)
        db.flush()
    return role


@pytest.fixture
def p11_fixture():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)

    workspace_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    slug = f"p11-{uuid.uuid4().hex[:8]}"

    # 1. Khoi tao Workspace va User trong SIN Content
    with SessionLocal() as db:
        ws = Workspace(id=workspace_id, name="P11 Feedback Workspace", slug=slug)
        db.add(ws)
        db.add(User(id=user_id, email=f"p11-user-{user_id}@test.invalid", hashed_password="mock"))
        db.commit()

    # 2. Khoi tao RBAC Canonical trong Baha Auth
    with AuthSessionLocal() as auth_db:
        auth_db.add(AuthWorkspace(id=workspace_id, name="P11 WS", slug=f"auth-{slug}", status="ACTIVE"))
        auth_db.add(GlobalUser(id=user_id, email=f"p11-user-{user_id}@test.invalid", status="ACTIVE"))
        auth_db.flush()

        mem_id = str(uuid.uuid4())
        auth_db.add(AuthMembership(id=mem_id, workspace_id=workspace_id, user_id=user_id, status="ACTIVE"))
        auth_db.flush()

        role_owner = lay_role(auth_db, "WORKSPACE_OWNER")
        auth_db.add(RoleAssignment(
            workspace_id=workspace_id,
            membership_id=mem_id,
            role_id=role_owner.id,
            scope_type="WORKSPACE",
            scope_id=workspace_id,
            status="ACTIVE",
        ))
        auth_db.commit()

    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "headers": {
            "Authorization": f"Bearer {tao_bearer(user_id)}",
            "X-Workspace-Id": workspace_id,
            "X-User-Id": user_id,
        },
    }


def test_t110_valid_two_snapshot_observations_delta_and_units(p11_fixture):
    """
    T110: Tinh van toc tang truong chuan hoa giua 2 snapshot quan sat hop le.
    Kiem tra:
    - Tham chieu chinh xac ca from_observation_id va to_observation_id
    - Don vi do luong tuong duong (equivalent units)
    - Tinh dung delta_time_days va normalized velocity_views_per_day (views/day)
    - Luu vet vao CSDL TrendVelocityObservation
    """
    ws_id = p11_fixture["workspace_id"]
    headers = p11_fixture["headers"]

    source_id = str(uuid.uuid4())
    snap_1_id = f"obs_1_{uuid.uuid4().hex[:8]}"
    snap_2_id = f"obs_2_{uuid.uuid4().hex[:8]}"

    t0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(days=3)  # Cach 3 ngay

    with SessionLocal() as db:
        sr = SourceRecord(
            id=source_id,
            workspace_id=ws_id,
            provider_id="tiktok",
            raw_external_id="tt_t110_vid",
            canonical_url="https://tiktok.com/@brand/video/t110",
            title="Video kiem thu van toc P110",
            observed_at=t0,
            is_paid=False,
        )
        db.add(sr)

        # Tao 2 Snapshots: t0 co 1000 views, t1 co 7000 views (delta = 6000 views / 3 days = 2000 views/day)
        s1 = MetricSnapshot(
            id=str(uuid.uuid4()),
            source_record_id=source_id,
            observation_id=snap_1_id,
            observed_at=t0,
            view_count=1000,
            like_count=50,
            comment_count=10,
            share_count=5,
            synthetic=False,
        )
        s2 = MetricSnapshot(
            id=str(uuid.uuid4()),
            source_record_id=source_id,
            observation_id=snap_2_id,
            observed_at=t1,
            view_count=7000,
            like_count=350,
            comment_count=70,
            share_count=35,
            synthetic=False,
        )
        db.add_all([s1, s2])
        db.commit()

    # Goi API tinh van toc tang truong
    resp = client.post(
        "/v1/feedback/velocity/calculate",
        json={
            "source_record_id": source_id,
            "from_observation_id": snap_1_id,
            "to_observation_id": snap_2_id,
        },
        headers=headers,
    )

    assert resp.status_code == 200, f"Response: {resp.text}"
    data = resp.json()

    # 1. Tham chieu chinh xac ca 2 observation IDs
    assert data["source_record_id"] == source_id
    assert data["from_observation_id"] == snap_1_id
    assert data["to_observation_id"] == snap_2_id

    # 2. Don vi tuong duong va thoi gian delta
    assert data["metric_unit"] == "views"
    assert data["delta_days"] == pytest.approx(3.0, abs=0.01)

    # 3. Van toc chuan hoa theo ngay va growth rate
    assert data["delta_views"] == 6000
    assert data["velocity_views_per_day"] == pytest.approx(2000.0, abs=0.01)
    # growth_rate = (7000 - 1000) / 1000 = 6.0 (+600%)
    assert data["growth_rate"] == pytest.approx(6.0, abs=0.01)
    assert data["rate_status"] == "VALID"

    # 4. Kiem tra luu vet trong CSDL TrendVelocityObservation
    with SessionLocal() as db:
        obs = db.query(TrendVelocityObservation).filter(
            TrendVelocityObservation.from_observation_id == snap_1_id,
            TrendVelocityObservation.to_observation_id == snap_2_id,
        ).first()
        assert obs is not None
        assert obs.delta_value == pytest.approx(6000.0)
        assert obs.velocity_per_day == pytest.approx(2000.0)
        assert obs.growth_rate == pytest.approx(6.0)
        assert obs.rate_status == "VALID"
        assert obs.is_paid is False


def test_t111_view_count_zero_denominator_safe(p11_fixture):
    """
    T111: Mau so bang 0 (view_count = 0) khong gay loi ZeroDivisionError.
    Kiem tra:
    - rate_status = "NOT_AVAILABLE"
    - growth_rate = None
    - Tuyet doi khong tra ve Infinity, -Infinity, NaN
    - Khong crash he thong
    """
    ws_id = p11_fixture["workspace_id"]
    headers = p11_fixture["headers"]

    source_id = str(uuid.uuid4())
    snap_zero_id = f"obs_zero_{uuid.uuid4().hex[:8]}"
    snap_after_id = f"obs_after_{uuid.uuid4().hex[:8]}"

    t0 = datetime(2026, 10, 5, 8, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(days=2)  # Cach 2 ngay

    with SessionLocal() as db:
        sr = SourceRecord(
            id=source_id,
            workspace_id=ws_id,
            provider_id="tiktok",
            raw_external_id="tt_t111_vid",
            canonical_url="https://tiktok.com/@brand/video/t111",
            title="Video bat dau tu 0 view",
            observed_at=t0,
            is_paid=False,
        )
        db.add(sr)

        # Snapshot 1: view_count = 0 (MAU SO BANG 0)
        s0 = MetricSnapshot(
            id=str(uuid.uuid4()),
            source_record_id=source_id,
            observation_id=snap_zero_id,
            observed_at=t0,
            view_count=0,
            like_count=0,
            synthetic=False,
        )
        # Snapshot 2: view_count = 500
        s1 = MetricSnapshot(
            id=str(uuid.uuid4()),
            source_record_id=source_id,
            observation_id=snap_after_id,
            observed_at=t1,
            view_count=500,
            like_count=20,
            synthetic=False,
        )
        db.add_all([s0, s1])
        db.commit()

    resp = client.post(
        "/v1/feedback/velocity/calculate",
        json={
            "source_record_id": source_id,
            "from_observation_id": snap_zero_id,
            "to_observation_id": snap_after_id,
        },
        headers=headers,
    )

    assert resp.status_code == 200, f"Response: {resp.text}"
    raw_text = resp.text

    # Tuyet doi khong chua Infinity, -Infinity hoac NaN trong response raw
    assert "Infinity" not in raw_text
    assert "-Infinity" not in raw_text
    assert "NaN" not in raw_text

    data = resp.json()
    # rate_status phai la NOT_AVAILABLE khi mau so bang 0
    assert data["rate_status"] == "NOT_AVAILABLE"
    assert data["growth_rate"] is None
    assert "Denominator is 0" in data["notes"]

    # Delta va velocity van tinh hop le: 500 views / 2 days = 250 views/day
    assert data["delta_views"] == 500
    assert data["velocity_views_per_day"] == pytest.approx(250.0, abs=0.01)

    # Kiem tra luu CSDL cung ghi nhan NOT_AVAILABLE
    with SessionLocal() as db:
        obs = db.query(TrendVelocityObservation).filter(
            TrendVelocityObservation.from_observation_id == snap_zero_id,
            TrendVelocityObservation.to_observation_id == snap_after_id,
        ).first()
        assert obs is not None
        assert obs.rate_status == "NOT_AVAILABLE"
        assert obs.growth_rate is None


def test_t112_paid_vs_organic_separate_cohorts_no_pooled_inference(p11_fixture):
    """
    T112: Du lieu tron lan bai tra phi (Paid) va tu nhien (Organic)
    phai duoc phan tach thanh 2 cohorts rieng biet.
    Tuyet doi cam gom chung (no pooled inference masquerading as organic results).
    """
    ws_id = p11_fixture["workspace_id"]
    headers = p11_fixture["headers"]

    with SessionLocal() as db:
        # Tao 2 bai Organic
        o1_id = str(uuid.uuid4())
        o2_id = str(uuid.uuid4())
        o1 = SourceRecord(
            id=o1_id,
            workspace_id=ws_id,
            provider_id="tiktok",
            raw_external_id="tt_org_01",
            canonical_url="https://tiktok.com/@brand/vid_o1",
            title="Bai dang Organic 1",
            observed_at=datetime.now(timezone.utc),
            is_paid=False,
        )
        o2 = SourceRecord(
            id=o2_id,
            workspace_id=ws_id,
            provider_id="tiktok",
            raw_external_id="tt_org_02",
            canonical_url="https://tiktok.com/@brand/vid_o2",
            title="Bai dang Organic 2",
            observed_at=datetime.now(timezone.utc),
            is_paid=False,
        )
        # Tao 2 bai Paid
        p1_id = str(uuid.uuid4())
        p2_id = str(uuid.uuid4())
        p1 = SourceRecord(
            id=p1_id,
            workspace_id=ws_id,
            provider_id="tiktok",
            raw_external_id="tt_paid_01",
            canonical_url="https://tiktok.com/@brand/vid_p1",
            title="Bai dang Paid 1",
            observed_at=datetime.now(timezone.utc),
            is_paid=True,
        )
        p2 = SourceRecord(
            id=p2_id,
            workspace_id=ws_id,
            provider_id="tiktok",
            raw_external_id="tt_paid_02",
            canonical_url="https://tiktok.com/@brand/vid_p2",
            title="Bai dang Paid 2",
            observed_at=datetime.now(timezone.utc),
            is_paid=True,
        )
        db.add_all([o1, o2, p1, p2])

        # Gan snapshots view_count
        now = datetime.now(timezone.utc)
        snap_o1 = MetricSnapshot(id=str(uuid.uuid4()), source_record_id=o1_id, observation_id=f"o1_{uuid.uuid4().hex[:6]}", observed_at=now, view_count=10000)
        snap_o2 = MetricSnapshot(id=str(uuid.uuid4()), source_record_id=o2_id, observation_id=f"o2_{uuid.uuid4().hex[:6]}", observed_at=now, view_count=20000)
        snap_p1 = MetricSnapshot(id=str(uuid.uuid4()), source_record_id=p1_id, observation_id=f"p1_{uuid.uuid4().hex[:6]}", observed_at=now, view_count=100000)
        snap_p2 = MetricSnapshot(id=str(uuid.uuid4()), source_record_id=p2_id, observation_id=f"p2_{uuid.uuid4().hex[:6]}", observed_at=now, view_count=200000)
        db.add_all([snap_o1, snap_o2, snap_p1, snap_p2])
        db.commit()

    # Goi API lay tong hop cohort
    resp = client.get(
        f"/v1/feedback/cohorts/summary?workspace_id={ws_id}&cohort=ALL",
        headers=headers,
    )
    assert resp.status_code == 200, f"Response: {resp.text}"
    data = resp.json()

    # CAM KET COT LOI: is_pooled_inference phai bang False
    assert data["is_pooled_inference"] is False, "Khong duoc phep gom chung (pooled inference)"

    # Kiem tra Cohort Organic
    org = data["organic_cohort"]
    assert org is not None
    assert org["cohort"] == "ORGANIC"
    assert org["total_posts"] == 2
    assert org["total_views"] == 30000  # 10,000 + 20,000
    assert org["is_pooled"] is False

    # Kiem tra Cohort Paid
    paid = data["paid_cohort"]
    assert paid is not None
    assert paid["cohort"] == "PAID"
    assert paid["total_posts"] == 2
    assert paid["total_views"] == 300000  # 100,000 + 200,000
    assert paid["is_pooled"] is False

    # XAC NHAN: So lieu Organic KHONG bi lam nhieu hay cong don so lieu Paid
    assert org["total_views"] != 330000, "Loi: So lieu Paid da bi gop vao Organic!"


def test_t113_no_channel_metrics_scope_feature_unavailable_no_fabrication(p11_fixture):
    """
    T113: Khong co scope chi so kenh (no channel metrics scope)
    -> Tra ve FEATURE_UNAVAILABLE / NOT_CONNECTED va metrics = None.
    Tuyet doi khong sinh du lieu phan hoi gia dinh / bia dat (no fabricated feedback data).
    """
    ws_id = p11_fixture["workspace_id"]
    headers = p11_fixture["headers"]

    unknown_channel_id = "tt_chan_chua_ket_noi_999"

    # 1. Kiem tra kenh chua tung ket noi
    resp_unknown = client.get(
        f"/v1/feedback/channels/{unknown_channel_id}/performance?workspace_id={ws_id}",
        headers=headers,
    )
    assert resp_unknown.status_code == 200
    data_unknown = resp_unknown.json()
    assert data_unknown["status"] == "NOT_CONNECTED"
    assert data_unknown["has_metrics_scope"] is False
    assert data_unknown["metrics"] is None, "Kenh chua ket noi khong duoc sinh metrics gia!"

    # 2. Ket noi kenh nhung THIEU scope 'channel:metrics' (chi co user.info.basic)
    chan_no_scope_id = "tt_chan_thieu_scope_113"
    connect_resp = client.post(
        "/v1/feedback/channels/connect",
        json={
            "workspace_id": ws_id,
            "channel_id": chan_no_scope_id,
            "channel_name": "Kenh Thieu Scope P113",
            "platform": "tiktok",
            "oauth_scopes": ["user.info.basic"],  # THIEU channel:metrics
        },
        headers=headers,
    )
    assert connect_resp.status_code == 200
    connect_data = connect_resp.json()
    assert connect_data["status"] == "FEATURE_UNAVAILABLE"
    assert connect_data["has_metrics_scope"] is False
    assert connect_data["metrics"] is None

    # Truy van hieu suat cua kenh thieu scope nay
    resp_no_scope = client.get(
        f"/v1/feedback/channels/{chan_no_scope_id}/performance?workspace_id={ws_id}",
        headers=headers,
    )
    assert resp_no_scope.status_code == 200
    data_no_scope = resp_no_scope.json()

    # CAM KET COT LOI: Status la FEATURE_UNAVAILABLE va metrics phai la None
    assert data_no_scope["status"] == "FEATURE_UNAVAILABLE"
    assert data_no_scope["has_metrics_scope"] is False
    assert data_no_scope["metrics"] is None, "TUYET DOI CAM sinh so lieu gia mao khi thieu scope!"
    assert "channel:metrics" in data_no_scope["message"]

    # 3. Ket noi kenh CO DU scope 'channel:metrics'
    chan_ok_id = "tt_chan_day_du_scope_113"
    client.post(
        "/v1/feedback/channels/connect",
        json={
            "workspace_id": ws_id,
            "channel_id": chan_ok_id,
            "channel_name": "Kenh Day Du Scope P113",
            "platform": "tiktok",
            "oauth_scopes": ["user.info.basic", "channel:metrics"],
        },
        headers=headers,
    )

    # Truy van lai hieu suat
    resp_ok = client.get(
        f"/v1/feedback/channels/{chan_ok_id}/performance?workspace_id={ws_id}",
        headers=headers,
    )
    assert resp_ok.status_code == 200
    data_ok = resp_ok.json()

    assert data_ok["status"] == "CONNECTED"
    assert data_ok["has_metrics_scope"] is True
    assert data_ok["metrics"] is not None
    assert data_ok["metrics"]["follower_count"] > 0
