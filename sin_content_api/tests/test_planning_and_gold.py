"""
Test Suite for Phase P05: Query Planning & Human-Reviewed Gold Dataset (T050 -> T052, P05-01 -> P05-10)
Strict Ground Truth Verification.
"""
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
TEST_DATABASE_URL = "sqlite:///file:sin_content_p05_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = "sqlite:///file:baha_auth_planning_test?mode=memory&cache=shared&uri=true"
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-bang-khoa-gia-lap"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-nha-cung-cap"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test"

import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.entities import Workspace, User, Membership, BrandBriefVersion, ResearchRun
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from baha_auth.src.models.entities import (
    GlobalUser, Membership as AuthMembership, Role as AuthRole, RoleAssignment, Workspace as AuthWorkspace
)
from src.modules.research.query_planner import query_planner, ResearchRequest
from src.modules.research.taxonomy import IntentGroup
from src.modules.research.gold_evaluator import gold_manager

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
def setup_p05_env():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    db = SessionLocal()
    auth_db = AuthSessionLocal()
    
    ws_id = str(uuid.uuid4())
    editor_id = str(uuid.uuid4())
    viewer_id = str(uuid.uuid4())

    ws = Workspace(id=ws_id, name="Sin Planning Test WS", slug=f"plan-{uuid.uuid4().hex[:6]}")
    user_editor = User(id=editor_id, email=f"editor_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Editor User", hashed_password="mock")
    user_viewer = User(id=viewer_id, email=f"viewer_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Viewer User", hashed_password="mock")
    
    db.add_all([ws, user_editor, user_viewer])
    db.commit()
    
    m_editor = Membership(workspace_id=ws.id, user_id=user_editor.id, role="editor")
    m_viewer = Membership(workspace_id=ws.id, user_id=user_viewer.id, role="viewer")
    db.add_all([m_editor, m_viewer])
    db.commit()

    # Setup Auth DB
    setup_auth_user(auth_db, ws.id, user_editor.id, user_editor.email, "WORKSPACE_OWNER")
    setup_auth_user(auth_db, ws.id, user_viewer.id, user_viewer.email, "WORKSPACE_OWNER")

    # Create approved brand brief with strict excluded topics (Brand Safety)
    brief = BrandBriefVersion(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        version=1,
        brand_name="Sin Derma Skincare",
        objective="Tăng nhận diện dòng serum phục hồi mụn nhạy cảm",
        voice_description="Khoa học, tận tâm, trung thực, gần gũi",
        current_audience="GenZ và dân văn phòng da mụn",
        target_audience="Khách hàng tìm kiếm giải pháp phục hồi da sau tổn thương",
        topics_included_json=json.dumps(["serum phục hồi", "b5 rau má", "chăm sóc da mụn"]),
        topics_excluded_json=json.dumps(["kem trộn", "rượu thuốc", "hàng giả"]), # Prohibited terms (T050)
        status="APPROVED",
    )
    db.add(brief)
    db.commit()

    token_editor = tao_bearer(user_editor.id)
    token_viewer = tao_bearer(user_viewer.id)

    ctx = {
        "ws_id": ws.id,
        "editor_id": user_editor.id,
        "viewer_id": user_viewer.id,
        "brief_id": brief.id,
        "headers_editor": {
            "Authorization": f"Bearer {token_editor}",
            "X-Workspace-Id": ws.id,
            "X-User-Id": user_editor.id
        },
        "headers_viewer": {
            "Authorization": f"Bearer {token_viewer}",
            "X-Workspace-Id": ws.id,
            "X-User-Id": user_viewer.id
        }
    }
    yield ctx

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

def test_t050_brief_with_excluded_topics_omits_prohibited_terms(setup_p05_env):
    """
    T050: Brief with excluded topics -> query plan and accepted candidates omit prohibited topics.
    P05-07: plan_id == ResearchRun.id -> GET /plans/{plan_id} thanh cong.
    """
    headers = setup_p05_env["headers_editor"]

    req_payload = {
        "workspace_id": setup_p05_env["ws_id"],
        "brief_version_id": setup_p05_env["brief_id"],
        "intent_groups": ["PROBLEMS", "COMPARISONS", "OBJECTIONS", "QUESTIONS"],
        "lookback_days": 30,
        "provider_ids": ["customer_import"],
        "max_results": 50,
        "max_cost_usd": 0.0,
        "mode": "OFFLINE",
        "synthetic": False,
        "query_seed": ["serum b5 phục hồi"],
        "negative_keywords": ["hàng chợ"],
    }

    res = client.post("/v1/research/plans", json=req_payload, headers=headers)
    assert res.status_code == 200, res.text
    plan = res.json()
    plan_id = plan["plan_id"]

    # 1. Negative keywords must contain all brief topics_excluded
    negatives = [k.lower() for k in plan["negative_keywords"]]
    assert "kem trộn" in negatives
    assert "rượu thuốc" in negatives
    assert "hàng giả" in negatives
    assert "hàng chợ" in negatives

    # 2. None of the generated query variants may contain excluded topics
    for variant in plan["query_variants"]:
        q_str = variant["query_string"].lower()
        assert "kem trộn" not in q_str
        assert "rượu thuốc" not in q_str
        assert "hàng giả" not in q_str

    # 3. Candidate admissibility test
    prohibited_sample = "Video hướng dẫn trộn kem trộn trắng da cấp tốc"
    admissible = query_planner.is_candidate_admissible(prohibited_sample, negatives)
    assert admissible is False, "Prohibited candidate must be deemed inadmissible"

    clean_sample = "Video review serum b5 rau má làm dịu da kích ứng"
    assert query_planner.is_candidate_admissible(clean_sample, negatives) is True

    # P05-07: Tra cuu GET /plans/{plan_id} phai thanh cong (200 OK)
    get_res = client.get(f"/v1/research/plans/{plan_id}", headers=headers)
    assert get_res.status_code == 200, get_res.text
    assert get_res.json()["plan_id"] == plan_id

def test_t051_three_briefs_gold_dataset_human_reviewed(setup_p05_env):
    """
    T051: Three distinctly different briefs; >= 30 human-reviewed candidates per brief;
    two independent reviewers and conflict adjudication.
    """
    headers = setup_p05_env["headers_viewer"]

    # 1. List all gold datasets
    res = client.get("/v1/research/gold-sets", headers=headers)
    assert res.status_code == 200, res.text
    summaries = res.json()
    
    # Must have at least 3 distinctly different briefs
    assert len(summaries) >= 3
    brief_ids = [s["brief_id"] for s in summaries]
    assert "brief-bento-01" in brief_ids
    assert "brief-skincare-02" in brief_ids
    assert "brief-audio-03" in brief_ids

    total_candidates = 0
    # 2. Inspect candidates of each brief
    for s in summaries:
        bid = s["brief_id"]
        assert s["total_candidates"] >= 30
        total_candidates += s["total_candidates"]

        res_c = client.get(f"/v1/research/gold-sets/{bid}", headers=headers)
        assert res_c.status_code == 200
        candidates = res_c.json()
        assert len(candidates) >= 30

        for c in candidates:
            assert c["reviewer_1_label"] in ["RELEVANT", "BORDERLINE", "IRRELEVANT"]
            assert c["reviewer_2_label"] in ["RELEVANT", "BORDERLINE", "IRRELEVANT"]
            assert c["adjudication_label"] in ["RELEVANT", "BORDERLINE", "IRRELEVANT"]
            assert len(c["adjudication_reason"]) > 5
            if c["has_veto_violation"]:
                assert c["adjudication_label"] == "IRRELEVANT"
                assert c["final_score"] == 0

    assert total_candidates >= 90

def test_t052_query_planner_respects_max_requests_and_cost_cap(setup_p05_env):
    """
    T052, P05-02, P05-08: Small source budget and high requested count ->
    query planner respects max requests and explicit cost cap.
    """
    headers = setup_p05_env["headers_editor"]

    # Scenario: High requested count (500) but strict budget ceiling ($0.02)
    # tiktok_official costs $0.005/request -> Allows at most 4 queries!
    req_payload = {
        "workspace_id": setup_p05_env["ws_id"],
        "brief_version_id": setup_p05_env["brief_id"],
        "intent_groups": ["PROBLEMS", "COMPARISONS", "OBJECTIONS", "QUESTIONS", "TRENDS"],
        "lookback_days": 30,
        "provider_ids": ["tiktok_official"],
        "max_results": 500,
        "max_cost_usd": 0.02,
        "mode": "OFFLINE",
        "synthetic": False,
    }

    res = client.post("/v1/research/plans", json=req_payload, headers=headers)
    assert res.status_code == 200, res.text
    plan = res.json()

    # Strictly <= 4 queries
    assert len(plan["query_variants"]) <= 4
    assert plan["estimated_cost_usd"] <= 0.02
    assert plan["max_cost_usd"] == 0.02

def test_p05_unapproved_brief_and_prohibited_provider(setup_p05_env):
    """
    P05-03: Brief DRAFT bi tu choi tao plan (HTTP 422).
    P05-04: Sai workspace_id bi tu choi (HTTP 400).
    P05-05: Provider mediacrawler bi chan (HTTP 422).
    P05-02: Ngan sach nho hon don gia 1 query khong ep sinh query tinh phi.
    """
    headers = setup_p05_env["headers_editor"]
    ws_id = setup_p05_env["ws_id"]

    db = SessionLocal()
    try:
        # 1. P05-03: Tao brief DRAFT
        draft_brief = BrandBriefVersion(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            version=2,
            brand_name="Sin Draft",
            objective="Mục tiêu nháp",
            voice_description="Nháp",
            current_audience="GenZ",
            target_audience="GenZ",
            topics_included_json="[]",
            topics_excluded_json="[]",
            status="DRAFT" # CHUA APPROVED
        )
        db.add(draft_brief)
        db.commit()

        req_draft = {
            "workspace_id": ws_id,
            "brief_version_id": draft_brief.id,
            "intent_groups": ["PROBLEMS"],
            "provider_ids": ["customer_import"]
        }
        res_draft = client.post("/v1/research/plans", json=req_draft, headers=headers)
        assert res_draft.status_code == 422
        assert "UNAPPROVED_BRIEF" in str(res_draft.json())

        # 2. P05-04: Sai workspace_id
        req_bad_ws = {
            "workspace_id": "workspace-khac-khong-ton-tai",
            "brief_version_id": setup_p05_env["brief_id"],
            "intent_groups": ["PROBLEMS"],
            "provider_ids": ["customer_import"]
        }
        res_bad_ws = client.post("/v1/research/plans", json=req_bad_ws, headers=headers)
        assert res_bad_ws.status_code == 400
        assert "WORKSPACE_MISMATCH" in str(res_bad_ws.json())

        # 3. P05-05: Prohibited provider "mediacrawler"
        req_bad_prov = {
            "workspace_id": ws_id,
            "brief_version_id": setup_p05_env["brief_id"],
            "intent_groups": ["PROBLEMS"],
            "provider_ids": ["mediacrawler"]
        }
        res_bad_prov = client.post("/v1/research/plans", json=req_bad_prov, headers=headers)
        assert res_bad_prov.status_code == 422
        assert "bị cấm" in str(res_bad_prov.json())

        # 4. P05-02: Ngan sach $0.001 khong du $0.005 cua tiktok_official -> 0 query paid
        req_tiny_budget = {
            "workspace_id": ws_id,
            "brief_version_id": setup_p05_env["brief_id"],
            "intent_groups": ["PROBLEMS"],
            "provider_ids": ["tiktok_official"],
            "max_cost_usd": 0.001
        }
        res_tiny = client.post("/v1/research/plans", json=req_tiny_budget, headers=headers)
        assert res_tiny.status_code == 200
        tiny_plan = res_tiny.json()
        assert len(tiny_plan["query_variants"]) == 0
        assert tiny_plan["estimated_cost_usd"] == 0.0
    finally:
        try:
            db.close()
        except Exception:
            pass
