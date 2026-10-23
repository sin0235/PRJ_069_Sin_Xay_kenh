# Tests cho Pha P07: Truy xuat lai, bo loc phu hop & xep hang tuong minh (T070 -> T073, P07-01 -> P07-11)
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

# Them thu muc goc 03_ban_lam_viec vao sys.path de import baha_auth
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Thiet lap moi truong test cho Baha Auth RBAC
TEST_DATABASE_URL = "sqlite:///file:sin_content_p07_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = "sqlite:///file:baha_auth_retrieval_test?mode=memory&cache=shared&uri=true"
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-bang-khoa-gia-lap"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-nha-cung-cap"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test"

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.entities import Workspace, User, Membership, BrandBriefVersion, SourceRecord, EvidenceExcerpt
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from baha_auth.src.models.entities import (
    GlobalUser, Membership as AuthMembership, Role as AuthRole, RoleAssignment, Workspace as AuthWorkspace
)
from src.modules.retrieval.ranking_service import ranking_service
from src.modules.retrieval.scorer import ExplicitScorer

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
        "exp": int(time.time()) + 300,
    })
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(
        os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{header}.{claims}.{encoded_signature}"

def setup_auth_user(auth_db, ws_id: str, user_id: str, email: str, role_code: str = "WORKSPACE_OWNER"):
    auth_ws = auth_db.query(AuthWorkspace).filter(AuthWorkspace.id == ws_id).first()
    if not auth_ws:
        auth_ws = AuthWorkspace(id=ws_id, name=f"WS-{ws_id[:8]}", slug=f"slug-{ws_id[:8]}", status="ACTIVE")
        auth_db.add(auth_ws)
        auth_db.flush()

    auth_user = auth_db.query(GlobalUser).filter(GlobalUser.id == user_id).first()
    if not auth_user:
        auth_user = GlobalUser(id=user_id, email=email, status="ACTIVE")
        auth_db.add(auth_user)
        auth_db.flush()

    auth_mem = auth_db.query(AuthMembership).filter(
        AuthMembership.workspace_id == ws_id, AuthMembership.user_id == user_id
    ).first()
    if not auth_mem:
        auth_mem = AuthMembership(id=str(uuid.uuid4()), workspace_id=ws_id, user_id=user_id, status="ACTIVE")
        auth_db.add(auth_mem)
        auth_db.flush()

    role = auth_db.query(AuthRole).filter(AuthRole.code == role_code).first()
    if not role:
        role = AuthRole(code=role_code, name=role_code, workspace_id=None, is_template=True, status="ACTIVE")
        auth_db.add(role)
        auth_db.flush()

    ra = auth_db.query(RoleAssignment).filter(
        RoleAssignment.workspace_id == ws_id, RoleAssignment.membership_id == auth_mem.id
    ).first()
    if not ra:
        ra = RoleAssignment(
            workspace_id=ws_id,
            membership_id=auth_mem.id,
            role_id=role.id,
            scope_type="WORKSPACE",
            scope_id=ws_id,
            status="ACTIVE"
        )
        auth_db.add(ra)
        auth_db.flush()

    auth_db.commit()

@pytest.fixture
def p07_fixture():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    db = SessionLocal()
    auth_db = AuthSessionLocal()

    try:
        unique_suffix = uuid.uuid4().hex[:6]
        ws_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        ws = Workspace(id=ws_id, name="P07 Retrieval Workspace", slug=f"p07-{unique_suffix}")
        db.add(ws)
        db.flush()

        user = User(id=user_id, email=f"ranking_analyst_{unique_suffix}@p07.vn", hashed_password="mock", full_name="Ranking Analyst")
        db.add(user)
        db.flush()

        membership = Membership(workspace_id=ws.id, user_id=user.id, role="creator")
        db.add(membership)

        setup_auth_user(auth_db, ws.id, user.id, user.email, "WORKSPACE_OWNER")

        brief = BrandBriefVersion(
            workspace_id=ws.id,
            version=1,
            brand_name="Sin Bento Pro",
            objective="Phát triển nội dung TikTok chứng minh khả năng chống tràn và giữ nhiệt của hộp cơm văn phòng",
            voice_description="Chân thực, đáng tin cậy, hữu ích cho người đi làm",
            language="vi-VN",
            current_audience="Dân văn phòng mang cơm",
            target_audience="Dân văn phòng, người đi xe máy, sinh viên",
            topics_included_json=json.dumps(["hộp cơm giữ nhiệt", "chống tràn canh", "inox 304", "an toàn sức khỏe"]),
            topics_excluded_json=json.dumps(["cháy nổ", "lừa đảo", "hàng giả", "chất độc hại"]),
            production_limits_json=json.dumps(["quay video bằng smartphone", "thời lượng dưới 60s"]),
            status="APPROVED"
        )
        db.add(brief)
        db.commit()

        token = tao_bearer(user.id)

        ctx = {
            "workspace_id": ws.id,
            "user_id": user.id,
            "brief_id": brief.id,
            "brief": brief,
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-Workspace-Id": ws.id,
                "X-User-Id": user.id
            }
        }
        yield ctx
    finally:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass
        try:
            auth_db.close()
        except Exception:
            pass

def test_t070_deterministic_scoring_exact_weights_sum_100(p07_fixture):
    """
    T070: Chấm điểm cùng một bộ bằng chứng và brief cho ra điểm số chính xác lặp lại được (deterministic);
    Tổng trọng số đúng 100% (Audience 30%, Evidence 25%, Objective 20%, Novelty 15%, Feasibility 10%).
    P07-11: Tra ve day du ly do cham diem (component_reasons).
    """
    brief_id = p07_fixture["brief_id"]
    headers = p07_fixture["headers"]

    # 1. Kiem tra ma tran trong so tuong minh
    weights_res = client.get("/v1/retrieval/weights", headers=headers)
    assert weights_res.status_code == 200, weights_res.text
    weights_data = weights_res.json()

    assert weights_data["audience_fit"] == 0.30
    assert weights_data["observed_evidence"] == 0.25
    assert weights_data["brand_objective"] == 0.20
    assert weights_data["content_uniqueness"] == 0.15
    assert weights_data["production_feasibility"] == 0.10
    assert weights_data["total"] == 1.00

    # 2. Cham diem 1 ung vien mau va kiem tra tinh tat dinh
    candidate_payload = {
        "brief_version_id": brief_id,
        "candidate_id": "cand_bento_001",
        "candidate_title": "Review hộp cơm giữ nhiệt Sin Bento Pro chống tràn canh",
        "content_excerpt": "Trải nghiệm mang canh đi xe máy không bị tràn, inox 304 giữ ấm 6 tiếng cho dân văn phòng",
        "evidence_tier": "EVIDENCE_BACKED",
        "observed_vs_inferred": "OBSERVED_DIRECT",
        "snapshots": [
            {"observed_at": "2026-10-21T08:00:00Z", "view_count": 10000},
            {"observed_at": "2026-10-22T08:00:00Z", "view_count": 35000}
        ]
    }

    res1 = client.post("/v1/retrieval/score", headers=headers, json=candidate_payload)
    assert res1.status_code == 200, res1.text
    data1 = res1.json()

    res2 = client.post("/v1/retrieval/score", headers=headers, json=candidate_payload)
    assert res2.status_code == 200
    data2 = res2.json()

    # Tinh tat dinh: 2 lan goi cho cung 1 ung vien phai cho ket qua giong het nhau 100%
    assert data1["breakdown"]["overall_score"] == data2["breakdown"]["overall_score"]
    assert data1["breakdown"]["growth_velocity"] == data2["breakdown"]["growth_velocity"]

    # P07-11: Kiem tra component_reasons khong bi rong
    breakdown = data1["breakdown"]
    assert breakdown["overall_score"] > 7.0
    assert "audience_fit" in breakdown["component_reasons"]
    assert "observed_evidence" in breakdown["component_reasons"]

def test_t071_high_view_count_irrelevant_or_prohibited_rejected_by_veto(p07_fixture):
    """
    T071: Video có view cực cao (50.000.000 views) nhưng không liên quan hoặc nằm trong chủ đề bị cấm;
    hệ thống loại bỏ hoặc cho điểm 0 (View cao không thể qua mặt bộ lọc bắt buộc / Brand Safety Veto).
    """
    brief_id = p07_fixture["brief_id"]
    headers = p07_fixture["headers"]

    # Ung vien A: 50 trieu view nhung chua chu de bi cam "cháy nổ"
    candidate_banned_payload = {
        "brief_version_id": brief_id,
        "candidate_id": "cand_viral_banned",
        "candidate_title": "Video triệu view: Vụ cháy nổ kinh hoàng tại xưởng sản xuất",
        "content_excerpt": "Video viral 50 triệu lượt xem, tai nạn cháy nổ dữ dội",
        "evidence_tier": "EVIDENCE_BACKED",
        "observed_vs_inferred": "OBSERVED_DIRECT",
        "snapshots": [{"observed_at": "2026-10-21T10:00:00Z", "view_count": 50000000}]
    }

    res_banned = client.post("/v1/retrieval/score", headers=headers, json=candidate_banned_payload)
    assert res_banned.status_code == 200, res_banned.text
    banned_data = res_banned.json()

    assert banned_data["breakdown"]["veto_violation"] is True
    assert banned_data["breakdown"]["overall_score"] == 0.0
    assert banned_data["status"] == "REJECTED_VETO"
    assert "cháy nổ" in banned_data["breakdown"]["veto_reason"]

def test_t072_precision_at_10_meets_or_exceeds_80_percent_on_gold_sets(p07_fixture):
    """
    T072: Đánh giá trên 3 tập dữ liệu vàng (Bento Box, Skincare Serum, Noise-cancelling Audio);
    Top 10 ứng viên được duyệt đạt Precision@10 >= 80% (tối thiểu 8/10 ứng viên là RELEVANT),
    0 ứng viên vi phạm Veto lọt vào Top 10.
    P07-01: Cham diem trung thuc, khong cheat bang adjudication_label.
    """
    headers = p07_fixture["headers"]

    gold_sets = [
        "bento_box_gold.json",
        "noise_cancelling_audio_gold.json",
        "skincare_serum_gold.json"
    ]

    for gs in gold_sets:
        res = client.post(f"/v1/retrieval/evaluate-gold?dataset_name={gs}", headers=headers)
        assert res.status_code == 200, res.text
        eval_data = res.json()

        # Tieu chi nghiem thu bat buoc
        assert eval_data["top_10_precision"] >= 0.80, f"Precision@10 for {gs} must be >= 0.80"
        assert eval_data["top_10_veto_count"] == 0, f"No veto violations allowed in Top 10 for {gs}"
        assert eval_data["meets_threshold"] is True

def test_t073_single_snapshot_no_growth_velocity_inferred(p07_fixture):
    """
    T073, P07-06: Chỉ có 1 snapshot số liệu hoặc chuỗi thời gian không hợp lệ; hệ thống không suy diễn tốc độ tăng trưởng,
    giữ nguyên trạng thái chưa rõ (velocity = None / NOT_AVAILABLE).
    Khi có >= 2 snapshots hợp lệ, tốc độ tăng trưởng mới được tính toán tất định.
    """
    brief_id = p07_fixture["brief_id"]
    headers = p07_fixture["headers"]

    # 1. Truong hop chi co 1 snapshot
    single_snap_payload = {
        "brief_version_id": brief_id,
        "candidate_id": "cand_single_snap",
        "candidate_title": "Review hộp cơm trưa",
        "content_excerpt": "Hộp cơm tiện lợi",
        "snapshots": [
            {"observed_at": "2026-10-21T10:00:00Z", "view_count": 15000}
        ]
    }

    res_single = client.post("/v1/retrieval/score", headers=headers, json=single_snap_payload)
    assert res_single.status_code == 200, res_single.text
    single_data = res_single.json()

    assert single_data["breakdown"]["growth_velocity"] is None
    assert single_data["breakdown"]["velocity_status"] == "NOT_AVAILABLE"
    assert single_data["breakdown"]["velocity_confidence"] == "UNVERIFIED_SINGLE_SNAPSHOT"

    # 2. P07-06: Truong hop 2 snapshots nhung khong co observed_at hoac cung observed_at
    invalid_snap_payload = {
        "brief_version_id": brief_id,
        "candidate_id": "cand_invalid_snap",
        "candidate_title": "Review hộp cơm",
        "content_excerpt": "Hộp cơm tiện lợi",
        "snapshots": [
            {"view_count": 100},
            {"view_count": 1000}
        ]
    }
    res_inv = client.post("/v1/retrieval/score", headers=headers, json=invalid_snap_payload)
    assert res_inv.status_code == 200
    inv_data = res_inv.json()
    assert inv_data["breakdown"]["growth_velocity"] is None
    assert inv_data["breakdown"]["velocity_status"] == "NOT_AVAILABLE"
    assert inv_data["breakdown"]["velocity_confidence"] == "INVALID_SNAPSHOT_TIMESTAMPS"

    # 3. Truong hop co 2 snapshots hop le -> Tinh toan velocity
    multi_snap_payload = {
        "brief_version_id": brief_id,
        "candidate_id": "cand_multi_snap",
        "candidate_title": "Review hộp cơm",
        "content_excerpt": "Hộp cơm tiện lợi",
        "snapshots": [
            {"observed_at": "2026-10-20T10:00:00Z", "view_count": 10000},
            {"observed_at": "2026-10-22T10:00:00Z", "view_count": 30000}
        ]
    }

    res_multi = client.post("/v1/retrieval/score", headers=headers, json=multi_snap_payload)
    assert res_multi.status_code == 200
    multi_data = res_multi.json()

    assert multi_data["breakdown"]["growth_velocity"] == 10000.0 # (30000-10000)/2 days
    assert multi_data["breakdown"]["velocity_status"] == "CALCULATED"
    assert multi_data["breakdown"]["velocity_confidence"] == "VERIFIED_MULTI_SNAPSHOT"

def test_p07_path_traversal_and_draft_brief_rejection(p07_fixture):
    """
    P07-02: Path traversal tren dataset_name bi chan HTTP 400.
    P07-07: Brief o trang thai DRAFT bi chan khong cho score/search (HTTP 422).
    """
    headers = p07_fixture["headers"]
    ws_id = p07_fixture["workspace_id"]

    # 1. P07-02: Path traversal
    res_trav = client.post("/v1/retrieval/evaluate-gold?dataset_name=../../etc/passwd", headers=headers)
    assert res_trav.status_code == 400
    assert "INVALID_DATASET_NAME" in (res_trav.json().get("error_code") or str(res_trav.json()))

    # 2. P07-07: Brief DRAFT
    db = SessionLocal()
    try:
        draft_brief = BrandBriefVersion(
            workspace_id=ws_id,
            version=3,
            brand_name="Draft Brief",
            objective="Mục tiêu nháp",
            voice_description="Nháp",
            current_audience="Dân văn phòng",
            target_audience="Dân văn phòng",
            topics_included_json="[]",
            topics_excluded_json="[]",
            status="DRAFT" # CHUA APPROVED
        )
        db.add(draft_brief)
        db.commit()

        score_payload = {
            "brief_version_id": draft_brief.id,
            "candidate_id": "cand_draft_test",
            "candidate_title": "Test draft",
            "content_excerpt": "Test draft excerpt"
        }
        res_score = client.post("/v1/retrieval/score", headers=headers, json=score_payload)
        assert res_score.status_code == 422
        assert "chưa được phê duyệt" in (res_score.json().get("message") or res_score.json().get("detail") or str(res_score.json()))
    finally:
        try:
            db.close()
        except Exception:
            pass
