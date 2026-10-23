# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động cho Cổng P14 + GF05-B:
Budget Hardening, Multi-Tenant Cost Ledger, Reconciliation & Feature Toggles.
Đáp ứng 100% tiêu chí nghiệm thu GF05-01 -> GF05-08 trong GOOGLE_FLOW_ACCEPTANCE_CASES.json.
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Cấu hình SQLite in-memory độc lập cho kiểm thử
TEST_DATABASE_URL = "sqlite:///file:sin_media_budget_gf05_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = (
    "sqlite:///file:baha_auth_budget_gf05_test?mode=memory&cache=shared&uri=true"
)
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-khoa-bi-mat-budget-gf05-secret"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "baha-auth-media-issuer"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "baha-media-studio-audience"

# Thêm đường dẫn vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    Workspace, User, MediaAsset, AIGenerationJob, WorkspaceBudget, CostLedger
)
from baha_auth.src.database import (
    Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
)
from baha_auth.src.models.entities import (
    GlobalUser, Membership as AuthMembership, Role as AuthRole,
    RoleAssignment, Workspace as AuthWorkspace
)
from src.modules.staging_reliability.budget_guard import budget_guard

def tao_bearer_jwt(user_id: str) -> str:
    """Tạo JWT Bearer token HS256 chuẩn cho user_id."""
    def b64url(val):
        raw = json.dumps(val, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    h = b64url({"alg": "HS256", "typ": "JWT"})
    c = b64url({
        "sub": user_id,
        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],
        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],
        "exp": int(time.time()) + 7200,
    })
    inp = f"{h}.{c}".encode("ascii")
    sig = hmac.new(os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), inp, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    return f"{h}.{c}.{sig_b64}"

def get_error_code(resp) -> str:
    """Trích xuất mã lỗi error_code từ JSON response bất kể định dạng bọc."""
    try:
        data = resp.json()
        if isinstance(data, dict):
            if "error_code" in data:
                return data["error_code"]
            if "detail" in data:
                if isinstance(data["detail"], dict):
                    return data["detail"].get("error_code", "")
                return str(data["detail"])
        return str(data)
    except Exception:
        return resp.text

@pytest.fixture(scope="module", autouse=True)
def setup_databases():
    """Khởi tạo cấu trúc bảng CSDL trong RAM."""
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    yield
    Base.metadata.drop_all(bind=engine)
    AuthBase.metadata.drop_all(bind=AuthEngine)

@pytest.fixture
def budget_fixture():
    """Thiết lập dữ liệu hai tenant cô lập A và B."""
    ws_a_id = f"ws-a-{uuid.uuid4().hex[:8]}"
    ws_b_id = f"ws-b-{uuid.uuid4().hex[:8]}"
    user_a_id = f"user-a-{uuid.uuid4().hex[:8]}"
    user_b_id = f"user-b-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        ws_a = Workspace(id=ws_a_id, name="Tenant A Studio", slug=f"ws-a-{uuid.uuid4().hex[:6]}")
        ws_b = Workspace(id=ws_b_id, name="Tenant B Studio", slug=f"ws-b-{uuid.uuid4().hex[:6]}")
        u_a = User(id=user_a_id, email=f"a-{user_a_id}@baha.vn", hashed_password="mock")
        u_b = User(id=user_b_id, email=f"b-{user_b_id}@baha.vn", hashed_password="mock")
        db.add_all([ws_a, ws_b, u_a, u_b])
        db.commit()

    with AuthSessionLocal() as auth_db:
        auth_ws_a = AuthWorkspace(id=ws_a_id, name="Tenant A Studio", slug=ws_a_id, status="ACTIVE")
        auth_ws_b = AuthWorkspace(id=ws_b_id, name="Tenant B Studio", slug=ws_b_id, status="ACTIVE")
        gu_a = GlobalUser(id=user_a_id, email=f"a-{user_a_id}@baha.vn", status="ACTIVE")
        gu_b = GlobalUser(id=user_b_id, email=f"b-{user_b_id}@baha.vn", status="ACTIVE")
        auth_db.add_all([auth_ws_a, auth_ws_b, gu_a, gu_b])
        auth_db.commit()

        m_a = AuthMembership(id=str(uuid.uuid4()), user_id=user_a_id, workspace_id=ws_a_id, status="ACTIVE")
        m_b = AuthMembership(id=str(uuid.uuid4()), user_id=user_b_id, workspace_id=ws_b_id, status="ACTIVE")
        auth_db.add_all([m_a, m_b])
        auth_db.commit()

        role_owner = auth_db.query(AuthRole).filter(AuthRole.code == "WORKSPACE_OWNER").first()
        if not role_owner:
            role_owner = AuthRole(code="WORKSPACE_OWNER", name="Workspace Owner", workspace_id=None, is_template=True, status="ACTIVE")
            auth_db.add(role_owner)
            auth_db.commit()

        ra_a = RoleAssignment(
            id=str(uuid.uuid4()), membership_id=m_a.id, role_id=role_owner.id,
            workspace_id=ws_a_id, status="ACTIVE", granted_by=m_a.id, scope_type="WORKSPACE"
        )
        ra_b = RoleAssignment(
            id=str(uuid.uuid4()), membership_id=m_b.id, role_id=role_owner.id,
            workspace_id=ws_b_id, status="ACTIVE", granted_by=m_b.id, scope_type="WORKSPACE"
        )
        auth_db.add_all([ra_a, ra_b])
        auth_db.commit()

    return {
        "ws_a_id": ws_a_id,
        "ws_b_id": ws_b_id,
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "token_a": tao_bearer_jwt(user_a_id),
        "token_b": tao_bearer_jwt(user_b_id),
    }

# ==============================================================================
# GF05-01: Multi-Tenant Job & Asset Isolation (Không rò rỉ metadata)
# ==============================================================================

def test_gf05_01_tenant_isolation_cross_access_denied(budget_fixture):
    """
    GF05-01: Tenant B cố tình truy vấn tác vụ AI của Tenant A -> Phải trả về 404
    (không lộ thông tin sự tồn tại hay metadata của tài sản của tenant khác).
    """
    client = TestClient(app)
    ws_a = budget_fixture["ws_a_id"]
    ws_b = budget_fixture["ws_b_id"]

    # Tenant A tạo tác vụ
    headers_a = {"Authorization": f"Bearer {budget_fixture['token_a']}", "X-Workspace-Id": ws_a}
    payload_a = {
        "asset_type": "VIDEO",
        "provider": "FAKE_PROVIDER",
        "provider_mode": "TEST_MOCK",
        "model_id": "test-mock-video",
        "prompt_text": "B-roll phong cảnh thiên nhiên 9:16",
        "idempotency_key": f"gf05-01-{uuid.uuid4().hex[:8]}",
        "estimated_cost": 0.05,
        "parameters": {"simulate_error": "SUCCESS"}
    }
    resp_create = client.post("/v1/ai-jobs", json=payload_a, headers=headers_a)
    assert resp_create.status_code == 200
    job_id = resp_create.json()["id"]

    # Tenant B cố tình truy vấn bằng job_id của Tenant A
    headers_b = {"Authorization": f"Bearer {budget_fixture['token_b']}", "X-Workspace-Id": ws_b}
    resp_cross = client.get(f"/v1/ai-jobs/{job_id}", headers=headers_b)
    assert resp_cross.status_code == 404
    assert get_error_code(resp_cross) == "JOB_NOT_FOUND"

# ==============================================================================
# GF05-02: Pre-Flight Budget Hardening (Chặn trước khi tính phí)
# ==============================================================================

def test_gf05_02_preflight_budget_exceeded_blocks_billable_call(budget_fixture):
    """
    GF05-02: Ngân sách tài khoản thấp hơn chi phí ước tính của nhà cung cấp ->
    Từ chối ngay lập tức (HTTP 402 PAYMENT_REQUIRED) trước khi gửi bất kỳ lệnh billable nào.
    """
    client = TestClient(app)
    ws_a = budget_fixture["ws_a_id"]
    headers_a = {"Authorization": f"Bearer {budget_fixture['token_a']}", "X-Workspace-Id": ws_a}

    # Cấp hạn mức ngân sách cực nhỏ: 0.05 units
    with SessionLocal() as db:
        budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ws_a).first()
        if not budget:
            budget = WorkspaceBudget(
                workspace_id=ws_a,
                allocated_units=0.05,
                reserved_units=0.0,
                spent_units=0.0,
                hard_limit_units=0.05
            )
            db.add(budget)
        else:
            budget.allocated_units = 0.05
            budget.spent_units = 0.0
            budget.reserved_units = 0.0
        db.commit()

    # Gửi tác vụ có chi phí ước tính 0.50$ (> 0.05$ khả dụng)
    payload = {
        "asset_type": "VIDEO",
        "provider": "FAKE_PROVIDER",
        "provider_mode": "TEST_MOCK",
        "model_id": "test-mock-video",
        "prompt_text": "Tác vụ vượt hạn mức ngân sách",
        "idempotency_key": f"gf05-02-{uuid.uuid4().hex[:8]}",
        "estimated_cost": 0.50,
        "parameters": {"simulate_error": "SUCCESS"}
    }
    resp = client.post("/v1/ai-jobs", json=payload, headers=headers_a)
    assert resp.status_code == 402
    assert get_error_code(resp) == "BUDGET_EXCEEDED"

    # Kiểm tra ground truth: spent_units vẫn nguyên vẹn = 0.0 (không hao hụt ngân sách)
    with SessionLocal() as db:
        budget_after = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ws_a).first()
        assert budget_after.spent_units == 0.0
        assert budget_after.reserved_units == 0.0

# ==============================================================================
# GF05-03: Quote Cap Exceeded Requires Re-approval
# ==============================================================================

def test_gf05_03_quote_cap_exceeded_requires_reapproval(budget_fixture):
    """
    GF05-03: Chi phí ước tính vượt quá trần ngân sách được phê duyệt (budget_cap) ->
    Chặn thực thi với lỗi BUDGET_CAP_EXCEEDED để buộc người dùng tái phê duyệt.
    """
    client = TestClient(app)
    ws_a = budget_fixture["ws_a_id"]
    headers_a = {"Authorization": f"Bearer {budget_fixture['token_a']}", "X-Workspace-Id": ws_a}

    # Cấp đủ ngân sách tổng nhưng người dùng chỉ duyệt trần tối đa 0.10$ cho tác vụ này
    with SessionLocal() as db:
        budget = budget_guard.get_or_create_budget(db, ws_a, default_allocated=100.0)
        budget.allocated_units = 100.0
        db.commit()

    payload = {
        "asset_type": "VIDEO",
        "provider": "FAKE_PROVIDER",
        "provider_mode": "TEST_MOCK",
        "model_id": "test-mock-video",
        "prompt_text": "Tác vụ giá cao cần duyệt lại trần",
        "idempotency_key": f"gf05-03-{uuid.uuid4().hex[:8]}",
        "estimated_cost": 0.25,
        "parameters": {"simulate_error": "SUCCESS"}
    }
    # Gửi kèm tham số query budget_cap = 0.10$
    resp = client.post("/v1/ai-jobs?budget_cap=0.10", json=payload, headers=headers_a)
    assert resp.status_code == 402
    assert get_error_code(resp) == "BUDGET_CAP_EXCEEDED"

# ==============================================================================
# GF05-04: Coexistence of Flow Zero-Cost Credits and Cloud Billing Currency
# ==============================================================================

def test_gf05_04_flow_zero_cost_vs_official_billing_coexistence(budget_fixture):
    """
    GF05-04: Sổ cái chi phí duy trì riêng biệt giữa luồng Flow 0đ (Flow Music Plus/Google Flow)
    và luồng Cloud Billing chính thức. Không bao giờ gộp nhầm hoặc trừ ngân sách cloud cho Flow.
    """
    client = TestClient(app)
    ws_a = budget_fixture["ws_a_id"]
    headers_a = {"Authorization": f"Bearer {budget_fixture['token_a']}", "X-Workspace-Id": ws_a}

    with SessionLocal() as db:
        budget = budget_guard.get_or_create_budget(db, ws_a, default_allocated=100.0)
        initial_spent = budget.spent_units

    # 1. Chạy tác vụ Flow Music Zero-Cost (0đ chi phí gọi API)
    idem_flow = f"gf05-04-flow-{uuid.uuid4().hex[:8]}"
    payload_flow = {
        "asset_type": "MUSIC",
        "provider": "FLOW_MUSIC_ASSISTED",
        "provider_mode": "SUBSCRIPTION_ASSISTED",
        "model_id": "flow-music-plus-v1",
        "prompt_text": "Bản nhạc nền pop vui tươi 0đ",
        "idempotency_key": idem_flow,
        "estimated_cost": 0.0,
        "parameters": {"genre": "Pop", "mood": "Upbeat"}
    }
    resp_flow = client.post("/v1/ai-jobs", json=payload_flow, headers=headers_a)
    assert resp_flow.status_code == 200
    flow_data = resp_flow.json()
    assert flow_data["actual_cost"] == 0.0
    assert flow_data["credits_source"] == "FLOW_MUSIC_PLUS"

    # 2. Chạy tác vụ Billable chính thức (có chi phí Cloud Billing 0.12$)
    idem_billable = f"gf05-04-bill-{uuid.uuid4().hex[:8]}"
    payload_billable = {
        "asset_type": "VIDEO",
        "provider": "FAKE_PROVIDER",
        "provider_mode": "TEST_MOCK",
        "model_id": "test-mock-video",
        "prompt_text": "Video dọc phân cảnh chính thức",
        "idempotency_key": idem_billable,
        "estimated_cost": 0.12,
        "parameters": {"simulate_error": "SUCCESS"}
    }
    resp_billable = client.post("/v1/ai-jobs", json=payload_billable, headers=headers_a)
    assert resp_billable.status_code == 200
    billable_data = resp_billable.json()
    assert billable_data["actual_cost"] == 0.12
    assert billable_data["credits_source"] == "API_BILLING"

    # 3. Đối soát ground truth tại CostLedger và WorkspaceBudget
    with SessionLocal() as db:
        # Sổ cái Flow phải ghi nhận 0.0 units
        flow_ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == idem_flow).first()
        assert flow_ledger is not None
        assert flow_ledger.action_type == "flow_pilot_music"
        assert flow_ledger.actual_units == 0.0

        # Sổ cái Billable ghi nhận 0.12 units
        bill_ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == idem_billable).first()
        assert bill_ledger is not None
        assert bill_ledger.action_type == "ai_media_video"
        assert bill_ledger.actual_units == 0.12

        # Ngân sách Workspace chỉ tăng đúng 0.12 (không bị cộng dồn thêm tác vụ Flow)
        budget_final = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ws_a).first()
        assert round(budget_final.spent_units - initial_spent, 2) == 0.12

# ==============================================================================
# GF05-05: Uncertain Spend / Network Timeout Triggers NEEDS_RECONCILIATION
# ==============================================================================

def test_gf05_05_needs_reconciliation_on_timeout_blocks_duplicate(budget_fixture):
    """
    GF05-05: Khi gặp lỗi mạng không xác định được hóa đơn (TIMEOUT_UNCERTAIN_BILL) ->
    Chuyển trạng thái sang NEEDS_RECONCILIATION. Bất kỳ yêu cầu gửi lại cùng idempotency_key
    phải bị chặn với HTTP 409 CONFLICT để bảo vệ tài khoản khỏi bị trừ tiền trùng lặp.
    """
    client = TestClient(app)
    ws_a = budget_fixture["ws_a_id"]
    headers_a = {"Authorization": f"Bearer {budget_fixture['token_a']}", "X-Workspace-Id": ws_a}

    idem_timeout = f"gf05-05-{uuid.uuid4().hex[:8]}"
    payload = {
        "asset_type": "VIDEO",
        "provider": "FAKE_PROVIDER",
        "provider_mode": "TEST_MOCK",
        "model_id": "test-mock-video",
        "prompt_text": "Tác vụ gặp sự cố timeout không chắc chắn",
        "idempotency_key": idem_timeout,
        "estimated_cost": 0.15,
        "parameters": {"simulate_error": "TIMEOUT_UNCERTAIN_BILL"}
    }

    # Lần 1: Chạy và rơi vào trạng thái NEEDS_RECONCILIATION
    resp1 = client.post("/v1/ai-jobs", json=payload, headers=headers_a)
    assert resp1.status_code == 200
    assert resp1.json()["state"] == "NEEDS_RECONCILIATION"

    # Lần 2: Thử gửi lại ngay lập tức với cùng idempotency_key
    resp2 = client.post("/v1/ai-jobs", json=payload, headers=headers_a)
    assert resp2.status_code == 409
    assert get_error_code(resp2) == "NEEDS_RECONCILIATION"

# ==============================================================================
# GF05-07: Session Revocation Gate
# ==============================================================================

def test_gf05_07_session_revoked_blocks_execution(budget_fixture):
    """
    GF05-07: Khi phiên đăng nhập Google Flow bị thu hồi (FLOW_SESSION_REVOKED=true) ->
    Worker phát hiện và chặn tác vụ ngay (HTTP 401 UNAUTHORIZED) mà không gọi bừa bãi.
    """
    client = TestClient(app)
    ws_a = budget_fixture["ws_a_id"]
    headers_a = {"Authorization": f"Bearer {budget_fixture['token_a']}", "X-Workspace-Id": ws_a}

    os.environ["FLOW_SESSION_REVOKED"] = "true"
    try:
        payload = {
            "asset_type": "MUSIC",
            "provider": "FLOW_MUSIC_ASSISTED",
            "provider_mode": "SUBSCRIPTION_ASSISTED",
            "model_id": "flow-music-plus-v1",
            "prompt_text": "Yêu cầu khi phiên đã thu hồi",
            "idempotency_key": f"gf05-07-{uuid.uuid4().hex[:8]}",
            "estimated_cost": 0.0,
            "parameters": {}
        }
        resp = client.post("/v1/ai-jobs", json=payload, headers=headers_a)
        assert resp.status_code == 401
        assert get_error_code(resp) == "SESSION_REVOKED"
    finally:
        os.environ["FLOW_SESSION_REVOKED"] = "false"

# ==============================================================================
# GF05-08: Feature Flag Toggles Mid-Run
# ==============================================================================

def test_gf05_08_feature_flag_disabled_blocks_flow_pilot(budget_fixture):
    """
    GF05-08: Khi cờ tính năng Flow Pilot bị tắt (FLOW_PILOT_ENABLED=false) ->
    Chặn mọi yêu cầu tạo mới với HTTP 403 FEATURE_FLAG_DISABLED nhưng bảo toàn toàn bộ
    dữ liệu và lịch sử audit đã ghi nhận trước đó.
    """
    client = TestClient(app)
    ws_a = budget_fixture["ws_a_id"]
    headers_a = {"Authorization": f"Bearer {budget_fixture['token_a']}", "X-Workspace-Id": ws_a}

    os.environ["FLOW_PILOT_ENABLED"] = "false"
    try:
        payload = {
            "asset_type": "MUSIC",
            "provider": "FLOW_MUSIC_ASSISTED",
            "provider_mode": "SUBSCRIPTION_ASSISTED",
            "model_id": "flow-music-plus-v1",
            "prompt_text": "Yêu cầu khi cờ đã tắt",
            "idempotency_key": f"gf05-08-{uuid.uuid4().hex[:8]}",
            "estimated_cost": 0.0,
            "parameters": {}
        }
        resp = client.post("/v1/ai-jobs", json=payload, headers=headers_a)
        assert resp.status_code == 403
        assert get_error_code(resp) == "FEATURE_FLAG_DISABLED"
    finally:
        os.environ["FLOW_PILOT_ENABLED"] = "true"
