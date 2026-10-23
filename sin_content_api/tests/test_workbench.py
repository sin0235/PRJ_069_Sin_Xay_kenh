"""
Test Suite cho Phase P10: Content Review Workbench & Metric Verification (T100 -> T102)
Bao gom bo kiem thu Ground Truth cho tat ca cac finding P10-01 den P10-08.
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

# Thiet lap moi truong kiem thu doc lap
TEST_DATABASE_URL = "sqlite:///file:sin_content_p10_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = "sqlite:///file:baha_auth_p10_test?mode=memory&cache=shared&uri=true"
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-bang-khoa-gia-lap"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-nha-cung-cap"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test"

# Them duong dan chua baha_auth vao sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from fastapi.testclient import TestClient
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    AuditEvent, BrandBriefVersion, IdeaCard, MetricSnapshot, SourceRecord, User, Workspace, EvidenceExcerpt
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
def p10_fixture():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)

    workspace_id = str(uuid.uuid4())
    creator_user_id = str(uuid.uuid4())
    reviewer_user_id = str(uuid.uuid4())
    slug = f"p10-{uuid.uuid4().hex[:8]}"

    # 1. Khoi tao Workspace va Users trong he thong SIN
    with SessionLocal() as db:
        ws = Workspace(id=workspace_id, name="P10 Research Workbench WS", slug=slug)
        db.add(ws)
        db.add(User(id=creator_user_id, email=f"creator-{creator_user_id}@test.invalid", hashed_password="mock"))
        db.add(User(id=reviewer_user_id, email=f"reviewer-{reviewer_user_id}@test.invalid", hashed_password="mock"))
        db.commit()

        # Khoi tao 1 Brief Version
        brief = BrandBriefVersion(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            version=1,
            brand_name="Sin Bento Pro",
            objective="Nghien cuu noi dung TikTok cho hop com van phong",
            voice_description="Chan thuc, thuc te",
            language="vi-VN",
            current_audience="Dan van phong an trua",
            target_audience="Nhan vien tre mang com",
            status="APPROVED",
        )
        db.add(brief)
        db.commit()
        brief_id = brief.id

        # Tao nguon va trich doan hop le cho kiem thu bang chung
        source = SourceRecord(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            provider_id="customer_import",
            raw_external_id=f"ext_p10_{uuid.uuid4().hex[:6]}",
            canonical_url="https://tiktok.com/@brand/video/p10_source",
            title="Review Hop Com Chống Tràn",
            caption="Test chống tràn",
            synthetic=False,
            rights_basis="customer_supplied"
        )
        db.add(source)
        db.flush()

        excerpt = EvidenceExcerpt(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            source_record_id=source.id,
            excerpt_text="Nắp hộp này chống tràn rất tốt",
            excerpt_type="COMMENT",
            is_sanitized=True
        )
        db.add(excerpt)
        db.commit()
        excerpt_id = excerpt.id

    # 2. Khoi tao Thuc the va Phan quyen RBAC trong Baha Auth
    with AuthSessionLocal() as auth_db:
        auth_db.add(AuthWorkspace(id=workspace_id, name="P10 WS", slug=f"auth-{slug}", status="ACTIVE"))
        auth_db.add_all([
            GlobalUser(id=creator_user_id, email=f"creator-{creator_user_id}@test.invalid", status="ACTIVE"),
            GlobalUser(id=reviewer_user_id, email=f"reviewer-{reviewer_user_id}@test.invalid", status="ACTIVE"),
        ])
        auth_db.flush()

        creator_mem_id = str(uuid.uuid4())
        reviewer_mem_id = str(uuid.uuid4())
        auth_db.add_all([
            AuthMembership(id=creator_mem_id, workspace_id=workspace_id, user_id=creator_user_id, status="ACTIVE"),
            AuthMembership(id=reviewer_mem_id, workspace_id=workspace_id, user_id=reviewer_user_id, status="ACTIVE"),
        ])
        auth_db.flush()

        role_owner = lay_role(auth_db, "WORKSPACE_OWNER")
        auth_db.add(RoleAssignment(
            workspace_id=workspace_id,
            membership_id=reviewer_mem_id,
            role_id=role_owner.id,
            scope_type="WORKSPACE",
            scope_id=workspace_id,
            status="ACTIVE",
        ))
        auth_db.add(RoleAssignment(
            workspace_id=workspace_id,
            membership_id=creator_mem_id,
            role_id=role_owner.id,
            scope_type="WORKSPACE",
            scope_id=workspace_id,
            status="ACTIVE",
        ))
        auth_db.commit()

    return {
        "workspace_id": workspace_id,
        "creator_user_id": creator_user_id,
        "reviewer_user_id": reviewer_user_id,
        "brief_id": brief_id,
        "excerpt_id": excerpt_id,
        "reviewer_headers": {
            "Authorization": f"Bearer {tao_bearer(reviewer_user_id)}",
            "X-Workspace-Id": workspace_id,
            "X-User-Id": reviewer_user_id,
        },
        "creator_headers": {
            "Authorization": f"Bearer {tao_bearer(creator_user_id)}",
            "X-Workspace-Id": workspace_id,
            "X-User-Id": creator_user_id,
        },
    }

def test_t100_idea_approve_reject_reopen_and_audit_trail(p10_fixture):
    """
    T100: Kiem tra chu trinh duyet y tuong (APPROVE -> REOPEN -> REJECT),
    xac nhan chuyen doi trang thai, ghi nhan ly do danh gia va luu tru day du audit trail.
    """
    ws_id = p10_fixture["workspace_id"]
    creator_id = p10_fixture["creator_user_id"]
    reviewer_id = p10_fixture["reviewer_user_id"]
    brief_id = p10_fixture["brief_id"]
    excerpt_id = p10_fixture["excerpt_id"]
    headers = p10_fixture["reviewer_headers"]

    # 1. Tao 1 the y tuong o trang thai READY_FOR_REVIEW voi bang chung hop le
    card_id = str(uuid.uuid4())
    with SessionLocal() as db:
        card = IdeaCard(
            id=card_id,
            workspace_id=ws_id,
            brief_version_id=brief_id,
            title="Thu thach lac hop com inox chong tran tren duong xoc",
            target_need="Khac phuc su co tran canh khi di chuyen",
            hook="Doc nguoc hop com lac manh 15 phut xem co rot giot canh nao khong",
            content_angle="Stress test thuc te ngoai duong pho",
            confidence_tier="EVIDENCE_BACKED",
            evidence_excerpt_ids_json=json.dumps([excerpt_id]),
            status="READY_FOR_REVIEW",
            overall_score=8.5,
            creator_id=creator_id,
            version=1,
            synthetic=False,
        )
        db.add(card)
        db.commit()

    # 2. Reviewer APPROVE y tuong kem ly do
    approve_res = client.post(
        f"/v1/ideation/cards/{card_id}/review",
        headers=headers,
        json={
            "action": "APPROVE",
            "review_reason": "Y tuong sang tao, da kiem chung trich dan hop le 100%",
            "expected_status": "READY_FOR_REVIEW",
            "expected_version": 1,
        },
    )
    assert approve_res.status_code == 200, approve_res.text
    card_data = approve_res.json()
    assert card_data["status"] == "APPROVED"
    assert card_data["review_reason"] == "Y tuong sang tao, da kiem chung trich dan hop le 100%"
    assert card_data["version"] == 2
    assert card_data["reviewed_by"] == reviewer_id

    # 3. Reviewer REOPEN y tuong de xem xet lai
    reopen_res = client.post(
        f"/v1/ideation/cards/{card_id}/review",
        headers=headers,
        json={
            "action": "REOPEN",
            "review_reason": "Mo lai de cap nhat them chi so quan sat moi",
            "expected_status": "APPROVED",
            "expected_version": 2,
        },
    )
    assert reopen_res.status_code == 200, reopen_res.text
    reopen_data = reopen_res.json()
    assert reopen_data["status"] == "READY_FOR_REVIEW"
    assert reopen_data["review_reason"] == "Mo lai de cap nhat them chi so quan sat moi"
    assert reopen_data["version"] == 3

    # 4. Reviewer REJECT y tuong kem ly do
    reject_res = client.post(
        f"/v1/ideation/cards/{card_id}/review",
        headers=headers,
        json={
            "action": "REJECT",
            "review_reason": "Trung lap voi goc nhin noi dung cua tuan truoc",
            "expected_status": "READY_FOR_REVIEW",
            "expected_version": 3,
        },
    )
    assert reject_res.status_code == 200, reject_res.text
    reject_data = reject_res.json()
    assert reject_data["status"] == "REJECTED"
    assert reject_data["review_reason"] == "Trung lap voi goc nhin noi dung cua tuan truoc"
    assert reject_data["version"] == 4

    # 5. Kiem tra nhat ky kiem toan (Audit Trail) qua endpoint history
    history_res = client.get(
        f"/v1/ideation/cards/{card_id}/history",
        headers=headers,
    )
    assert history_res.status_code == 200, history_res.text
    history = history_res.json()
    event_types = [h["event_type"] for h in history]
    assert "IDEA_APPROVE" in event_types
    assert "IDEA_REOPEN" in event_types
    assert "IDEA_REJECT" in event_types
    for h in history:
        assert h["actor_id"] == reviewer_id
        assert h["workspace_id"] == ws_id

def test_t101_stale_version_approval_rejected_with_409(p10_fixture):
    """
    T101 & P10-02, P10-03: Kiem tra khoa lac quan (Optimistic Concurrency Locking).
    Khi reviewer co tinh duyet dua tren phien ban cu (stale version),
    he thong phai lap tuc tra ve 409 Conflict, khong ap dung phe duyet.
    """
    ws_id = p10_fixture["workspace_id"]
    creator_id = p10_fixture["creator_user_id"]
    brief_id = p10_fixture["brief_id"]
    headers = p10_fixture["reviewer_headers"]

    # 1. Tao the y tuong da duoc chuyen sang trang thai APPROVED (phien ban hien tai la 2)
    card_id = str(uuid.uuid4())
    with SessionLocal() as db:
        card = IdeaCard(
            id=card_id,
            workspace_id=ws_id,
            brief_version_id=brief_id,
            title="Y tuong da duoc phe duyet truoc do",
            target_need="Muc tieu test concurrency",
            hook="Hook test stale version",
            content_angle="Goc nhin test",
            confidence_tier="HYPOTHESIS",
            status="APPROVED",
            overall_score=8.0,
            creator_id=creator_id,
            version=2,
            synthetic=False,
        )
        db.add(card)
        db.commit()

    # 2. Reviewer gui yeu cau review voi expected_status cu ("READY_FOR_REVIEW")
    stale_res = client.post(
        f"/v1/ideation/cards/{card_id}/review",
        headers=headers,
        json={
            "action": "APPROVE",
            "review_reason": "Phe duyet cham tre tren phien ban cu",
            "expected_status": "READY_FOR_REVIEW",
            "expected_version": 1,
        },
    )

    # 3. He thong phai tra ve HTTP 409 Conflict
    assert stale_res.status_code == 409, stale_res.text
    err_body = stale_res.json()
    assert "STALE_VERSION_CONFLICT" in str(err_body)

    # 4. Xac minh trong co so du lieu: Trang thai va phien ban khong he bi thay doi
    with SessionLocal() as db:
        c = db.query(IdeaCard).filter(IdeaCard.id == card_id).first()
        assert c.status == "APPROVED"
        assert c.version == 2

def test_t102_source_missing_metric_or_expired_never_displays_zero_or_trending(p10_fixture):
    """
    T102 & P10-04, P10-05, P10-08: Nguon du lieu thieu chi so hoac het han.
    - MISSING hoac EXPIRED: khong bao gio tra ve 0 hoac trending.
    - P10-04: is_trending yeu cau toi thieu 2 snapshot voi van toc tang truong duong (trend velocity).
    - P10-05: Snapshot tuong lai bi danh dau FUTURE_TIMESTAMP_INVALID.
    - P10-08: view_count=null nhung like_count=123 tra ve PARTIAL va giu lai cac chi so that.
    """
    ws_id = p10_fixture["workspace_id"]
    headers = p10_fixture["reviewer_headers"]
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        # Nguon 1: Thieu chi so do luong (MISSING)
        src_missing = SourceRecord(
            workspace_id=ws_id,
            provider_id="tiktok_organic",
            raw_external_id="tt_post_missing_metric_001",
            canonical_url="https://tiktok.com/@brand/video/001",
            title="Video khong co snapshot chi so",
            rights_basis="customer_supplied",
        )
        db.add(src_missing)

        # Nguon 2: Chi so da het han (EXPIRED) - quan sat tu 45 ngay truoc
        src_expired = SourceRecord(
            workspace_id=ws_id,
            provider_id="tiktok_organic",
            raw_external_id="tt_post_expired_metric_002",
            canonical_url="https://tiktok.com/@brand/video/002",
            title="Video co chi so cu tren 30 ngay",
            rights_basis="customer_supplied",
        )
        db.add(src_expired)
        db.flush()

        old_obs_time = now - timedelta(days=45)
        snap_expired = MetricSnapshot(
            source_record_id=src_expired.id,
            observation_id="obs_old_45d",
            observed_at=old_obs_time,
            view_count=500000,
            like_count=20000,
        )
        db.add(snap_expired)

        # Nguon 3: Chi so hop le co 2 snapshot voi van toc tang truong duong (VALID + TRENDING)
        src_valid = SourceRecord(
            workspace_id=ws_id,
            provider_id="tiktok_organic",
            raw_external_id="tt_post_valid_metric_003",
            canonical_url="https://tiktok.com/@brand/video/003",
            title="Video co 2 snapshot tang truong manh",
            rights_basis="customer_supplied",
        )
        db.add(src_valid)
        db.flush()

        # Snapshot 1 (cach day 3 ngay, 100k views)
        snap_prev = MetricSnapshot(
            source_record_id=src_valid.id,
            observation_id="obs_valid_3d",
            observed_at=now - timedelta(days=3),
            view_count=100000,
            like_count=6000,
        )
        # Snapshot 2 (cach day 2 ngay, 250k views -> +150k trong 24h = 6250 view/h > 1000)
        snap_curr = MetricSnapshot(
            source_record_id=src_valid.id,
            observation_id="obs_valid_2d",
            observed_at=now - timedelta(days=2),
            view_count=250000,
            like_count=15000,
        )
        db.add_all([snap_prev, snap_curr])

        # Nguon 4 (P10-05): Snapshot tuong lai (10 ngay sau)
        src_future = SourceRecord(
            workspace_id=ws_id,
            provider_id="tiktok_organic",
            raw_external_id="tt_post_future_004",
            canonical_url="https://tiktok.com/@brand/video/004",
            title="Video voi snapshot tuong lai",
            rights_basis="customer_supplied",
        )
        db.add(src_future)
        db.flush()

        snap_future = MetricSnapshot(
            source_record_id=src_future.id,
            observation_id="obs_future_10d",
            observed_at=now + timedelta(days=10),
            view_count=250000,
            like_count=15000,
        )
        db.add(snap_future)

        # Nguon 5 (P10-08): Snapshot co view_count=null nhung like_count=123 (PARTIAL)
        src_partial = SourceRecord(
            workspace_id=ws_id,
            provider_id="tiktok_organic",
            raw_external_id="tt_post_partial_005",
            canonical_url="https://tiktok.com/@brand/video/005",
            title="Video khong co view_count nhung co like_count",
            rights_basis="customer_supplied",
        )
        db.add(src_partial)
        db.flush()

        snap_partial = MetricSnapshot(
            source_record_id=src_partial.id,
            observation_id="obs_partial_2d",
            observed_at=now - timedelta(days=2),
            view_count=None,
            like_count=123,
            comment_count=45,
        )
        db.add(snap_partial)
        db.commit()

        missing_id = src_missing.id
        expired_id = src_expired.id
        valid_id = src_valid.id
        future_id = src_future.id
        partial_id = src_partial.id

    # 1. Kiem tra Nguon 1 (MISSING metric)
    res_missing = client.get(f"/v1/sources/records/{missing_id}", headers=headers)
    assert res_missing.status_code == 200, res_missing.text
    data_missing = res_missing.json()
    assert data_missing["metric_status"] == "MISSING"
    assert data_missing["view_count"] is None
    assert data_missing["is_trending"] is None

    # 2. Kiem tra Nguon 2 (EXPIRED metric)
    res_expired = client.get(f"/v1/sources/records/{expired_id}", headers=headers)
    assert res_expired.status_code == 200, res_expired.text
    data_expired = res_expired.json()
    assert data_expired["metric_status"] == "EXPIRED"
    assert data_expired["view_count"] is None
    assert data_expired["is_trending"] is None

    # 3. Kiem tra Nguon 3 (VALID + TRENDING voi 2 snapshot)
    res_valid = client.get(f"/v1/sources/records/{valid_id}", headers=headers)
    assert res_valid.status_code == 200, res_valid.text
    data_valid = res_valid.json()
    assert data_valid["metric_status"] == "VALID"
    assert data_valid["view_count"] == 250000
    assert data_valid["is_trending"] is True

    # 4. P10-05: Kiem tra Nguon 4 (FUTURE_TIMESTAMP_INVALID)
    res_future = client.get(f"/v1/sources/records/{future_id}", headers=headers)
    assert res_future.status_code == 200
    data_future = res_future.json()
    assert data_future["metric_status"] == "FUTURE_TIMESTAMP_INVALID"
    assert data_future["is_trending"] is False

    # 5. P10-08: Kiem tra Nguon 5 (PARTIAL, giu like_count=123)
    res_partial = client.get(f"/v1/sources/records/{partial_id}", headers=headers)
    assert res_partial.status_code == 200
    data_partial = res_partial.json()
    assert data_partial["metric_status"] == "PARTIAL"
    assert data_partial["view_count"] is None
    assert data_partial["like_count"] == 123
    assert data_partial["comment_count"] == 45
    assert data_partial["last_observed_at"] is not None

def test_p10_concurrency_and_audit_isolation(p10_fixture):
    """
    Kiem tra:
    - P10-02: Bo qua expected_version / expected_status bi tu choi
    - P10-03: Hai phien ghi de cung expected_version thi phien thu 2 bi 409
    - P10-07: Get history card A khong lay nham event cua card B nhac card A trong ly do
    """
    ws_id = p10_fixture["workspace_id"]
    creator_id = p10_fixture["creator_user_id"]
    brief_id = p10_fixture["brief_id"]
    headers = p10_fixture["reviewer_headers"]

    card_a_id = str(uuid.uuid4())
    card_b_id = str(uuid.uuid4())

    with SessionLocal() as db:
        card_a = IdeaCard(
            id=card_a_id,
            workspace_id=ws_id,
            brief_version_id=brief_id,
            title="Card A",
            target_need="Need A",
            hook="Hook A",
            content_angle="Angle A",
            confidence_tier="HYPOTHESIS",
            status="READY_FOR_REVIEW",
            overall_score=7.0,
            creator_id=creator_id,
            version=1,
            synthetic=False,
        )
        card_b = IdeaCard(
            id=card_b_id,
            workspace_id=ws_id,
            brief_version_id=brief_id,
            title="Card B",
            target_need="Need B",
            hook="Hook B",
            content_angle="Angle B",
            confidence_tier="HYPOTHESIS",
            status="READY_FOR_REVIEW",
            overall_score=7.0,
            creator_id=creator_id,
            version=1,
            synthetic=False,
        )
        db.add_all([card_a, card_b])
        db.commit()

    # P10-02: Khong gui expected_version -> bi tu choi voi HTTP 422 hoac 409
    res_no_ver = client.post(
        f"/v1/ideation/cards/{card_a_id}/review",
        headers=headers,
        json={
            "action": "APPROVE",
            "review_reason": "Duyet khong truyen expected_version"
        }
    )
    assert res_no_ver.status_code in [409, 422], "Thieu expected_version phai bi tu choi"

    # P10-03: Session 1 duyet Card A thanh cong (v1 -> v2)
    res_s1 = client.post(
        f"/v1/ideation/cards/{card_a_id}/review",
        headers=headers,
        json={
            "action": "APPROVE",
            "review_reason": "Session 1 approve",
            "expected_status": "READY_FOR_REVIEW",
            "expected_version": 1
        }
    )
    assert res_s1.status_code == 200
    assert res_s1.json()["version"] == 2

    # Session 2 cung gui yeu cau tren Card A voi expected_version=1 -> Bi 409 Conflict!
    res_s2 = client.post(
        f"/v1/ideation/cards/{card_a_id}/review",
        headers=headers,
        json={
            "action": "REJECT",
            "review_reason": "Session 2 reject",
            "expected_status": "READY_FOR_REVIEW",
            "expected_version": 1
        }
    )
    assert res_s2.status_code == 409
    assert "STALE_VERSION_CONFLICT" in str(res_s2.json())

    # P10-07: Reviewer reject Card B nhung nhac den ID cua Card A trong review_reason
    res_rb = client.post(
        f"/v1/ideation/cards/{card_b_id}/review",
        headers=headers,
        json={
            "action": "REJECT",
            "review_reason": f"Y tuong nay bi trung voi {card_a_id}, yeu cau lam moi",
            "expected_status": "READY_FOR_REVIEW",
            "expected_version": 1
        }
    )
    assert res_rb.status_code == 200

    # Kiem tra history cua Card A: TUYET DOI KHONG DUOC CHUA event cua Card B!
    hist_a = client.get(f"/v1/ideation/cards/{card_a_id}/history", headers=headers)
    assert hist_a.status_code == 200
    events_a = hist_a.json()
    assert len(events_a) == 1
    details_a = json.loads(events_a[0]["details"])
    assert details_a["idea_id"] == card_a_id
    assert card_b_id not in details_a.get("idea_id", "")

def test_t103_author_self_approval_denied_four_eyes_violation(p10_fixture):
    """
    T103: Tác giả tạo thẻ ý tưởng tuyệt đối KHÔNG ĐƯỢC PHÉP tự phê duyệt ý tưởng của chính mình (Quy tắc Bốn Mắt).
    Ngay cả khi người dùng có quyền Reviewer/Owner, nếu là tác giả tạo card thì vẫn bị chặn 403 SELF_APPROVAL_VIOLATION.
    """
    ws_id = p10_fixture["workspace_id"]
    reviewer_id = p10_fixture["reviewer_user_id"]
    brief_id = p10_fixture["brief_id"]
    excerpt_id = p10_fixture["excerpt_id"]
    reviewer_headers = p10_fixture["reviewer_headers"]

    card_id = str(uuid.uuid4())
    with SessionLocal() as db:
        card = IdeaCard(
            id=card_id,
            workspace_id=ws_id,
            brief_version_id=brief_id,
            title="Thẻ ý tưởng do reviewer tự tạo",
            target_need="Kiểm thử rào chắn Bốn Mắt",
            hook="Hook test four eyes",
            content_angle="Angle test",
            confidence_tier="EVIDENCE_BACKED",
            evidence_excerpt_ids_json=json.dumps([excerpt_id]),
            status="READY_FOR_REVIEW",
            creator_id=reviewer_id,
            version=1,
            synthetic=False,
        )
        db.add(card)
        db.commit()

    # Reviewer cố tình tự APPROVE bài do chính mình tạo -> BẮT BUỘC bị từ chối 403 SELF_APPROVAL_VIOLATION
    res = client.post(
        f"/v1/ideation/cards/{card_id}/review",
        headers=reviewer_headers,
        json={
            "action": "APPROVE",
            "review_reason": "Tự duyệt bài của chính mình",
            "expected_status": "READY_FOR_REVIEW",
            "expected_version": 1,
        },
    )
    assert res.status_code == 403

