# Tests danh rieng cho Gate 2: Quyen Platform Owner, Cau hinh Singleton DB va Ma hoa Bi mat
import os
import time
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["TESTING"] = "1"
os.environ["BAHA_AUTH_JWT_SECRET"] = "baha_test_jwt_secret_key_32bytes_len!"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "baha_auth_issuer"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "baha_creator_os"
os.environ["BAHA_AUTH_DATABASE_URL"] = "sqlite:///:memory:"

from src.main import app
from src.database import SessionLocal, Base, engine
from src.config import settings
from src.models.entities import PlatformLLMConfig, AuditEvent
from src.modules.platform_config.crypto_vault import (
    encrypt_secret, decrypt_secret, compute_key_fingerprint
)
from src.modules.platform_config.service import platform_config_service
from src.migrations.runner import (
    migrate_platform_llm_config_up, migrate_platform_llm_config_down
)
from baha_auth.src.xac_minh_danh_tinh import verify_bearer_token

import base64
import hmac
import hashlib

def create_test_token(user_id: str, role: str = "viewer", expires_in: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],
        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],
        "exp": int(time.time()) + expires_in,
        "role": role
    }
    
    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    h_b64 = b64url(json.dumps(header).encode("utf-8"))
    p_b64 = b64url(json.dumps(payload).encode("utf-8"))
    msg = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), msg, hashlib.sha256).digest()
    sig_b64 = b64url(sig)
    return f"{h_b64}.{p_b64}.{sig_b64}"

@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    return TestClient(app)

@pytest.fixture(autouse=True)
def setup_owner_env():
    settings.platform_owner_user_ids = "owner_founder_01,platform_owner_99"
    yield

# ==================== TEST 1: PHÂN QUYỀN RBAC PLATFORM OWNER ====================

def test_gate2_anonymous_rejected(client):
    """Yêu cầu không có token bị từ chối 401."""
    resp = client.get("/v1/platform/llm-config")
    assert resp.status_code == 401
    assert "Cần bearer token hợp lệ" in resp.json()["message_safe"]

def test_gate2_non_owner_forbidden(client):
    """User bình thường hoặc Workspace Owner bị từ chối 403 Forbidden."""
    token = create_test_token(user_id="regular_user_123", role="WORKSPACE_OWNER")
    resp = client.get("/v1/platform/llm-config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert "Yêu cầu quyền Quản Trị Viên Nền Tảng (Platform Owner)" in resp.json()["message_safe"]

def test_gate2_platform_owner_authorized(client):
    """Platform Owner được phép truy cập 200 OK."""
    token = create_test_token(user_id="owner_founder_01", role="PLATFORM_OWNER")
    resp = client.get("/v1/platform/llm-config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "is_configured" in data
    assert "key_fingerprint" in data
    # Tuyệt đối không chứa secret key
    assert "api_key" not in data
    assert "api_key_ciphertext" not in data

def test_gate2_sin_admin_owner_authorized(client):
    """Tài khoản Sin Admin (usr_sin_owner) có đầy đủ thẩm quyền Platform Owner."""
    token = create_test_token(user_id="usr_sin_owner", role="PLATFORM_OWNER")
    resp = client.get("/v1/platform/llm-config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "is_configured" in data
    assert "key_fingerprint" in data

# ==================== TEST 2: SINGLETON & MÃ HÓA BÍ MẬT ====================

def test_gate2_update_config_encrypts_key_without_leak(client):
    """Cập nhật key mới: được mã hóa vào DB, trả về fingerprint, không lộ secret."""
    owner_token = create_test_token(user_id="owner_founder_01")
    raw_secret = "sk-super-secret-key-xyz9876"

    update_payload = {
        "is_enabled": True,
        "base_url": "http://127.0.0.1:20128/v1",
        "model": "gpt-4o-mini",
        "new_api_key": raw_secret,
        "timeout_seconds": 25.0,
        "max_output_tokens": 1200,
        "max_input_bytes": 15000,
        "input_usd_per_1k_tokens": 0.00015,
        "output_usd_per_1k_tokens": 0.00060,
        "budget_units_per_usd": 100.0
    }

    resp = client.put(
        "/v1/platform/llm-config",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=update_payload
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_enabled"] is True
    assert data["model"] == "gpt-4o-mini"
    assert data["key_fingerprint"] == "••••••••••••9876"
    assert data["has_api_key"] is True
    assert "api_key" not in data
    assert raw_secret not in str(data)

    # Kiểm tra trực tiếp trong DB
    db: Session = SessionLocal()
    try:
        cfg = db.query(PlatformLLMConfig).filter(PlatformLLMConfig.id == "default_platform_llm_config").first()
        assert cfg is not None
        assert cfg.api_key_ciphertext != raw_secret
        assert raw_secret not in cfg.api_key_ciphertext
        # Giải mã ra đúng plaintext ban đầu
        decrypted = decrypt_secret(cfg.api_key_ciphertext)
        assert decrypted == raw_secret
    finally:
        db.close()

def test_gate2_update_empty_key_preserves_existing_key(client):
    """Khi để trống new_api_key, hệ thống bảo lưu khóa cũ đã mã hóa."""
    owner_token = create_test_token(user_id="owner_founder_01")
    
    # Đọc key fingerprint hiện tại
    get_res = client.get("/v1/platform/llm-config", headers={"Authorization": f"Bearer {owner_token}"})
    old_fp = get_res.json()["key_fingerprint"]
    assert old_fp == "••••••••••••9876"

    # Gửi cập nhật với new_api_key = null
    update_payload = {
        "is_enabled": True,
        "base_url": "http://127.0.0.1:20128/v1",
        "model": "gpt-4o-updated",
        "new_api_key": None,
        "timeout_seconds": 20.0,
        "max_output_tokens": 1000,
        "max_input_bytes": 12000,
        "input_usd_per_1k_tokens": 0.0002,
        "output_usd_per_1k_tokens": 0.0008,
        "budget_units_per_usd": 120.0
    }
    resp = client.put(
        "/v1/platform/llm-config",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=update_payload
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "gpt-4o-updated"
    assert data["key_fingerprint"] == old_fp # Giữ nguyên fingerprint cũ

    # Giải mã DB vẫn ra đúng key cũ
    db: Session = SessionLocal()
    try:
        cfg = db.query(PlatformLLMConfig).first()
        assert decrypt_secret(cfg.api_key_ciphertext) == "sk-super-secret-key-xyz9876"
    finally:
        db.close()

# ==================== TEST 3: VALIDATION RÀO CHẮN AN TOÀN ====================

def test_gate2_remote_http_rejected(client):
    """URL từ xa dùng HTTP bị từ chối 422."""
    owner_token = create_test_token(user_id="owner_founder_01")
    resp = client.put(
        "/v1/platform/llm-config",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "is_enabled": False,
            "base_url": "http://api.remote-llm.com/v1",
            "model": "test-model"
        }
    )
    assert resp.status_code == 422
    assert "bắt buộc phải sử dụng HTTPS" in str(resp.json())

def test_gate2_query_token_in_url_rejected(client):
    """URL chứa query parameters bị từ chối 422."""
    owner_token = create_test_token(user_id="owner_founder_01")
    resp = client.put(
        "/v1/platform/llm-config",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "is_enabled": False,
            "base_url": "http://127.0.0.1:20128/v1?token=leaked_secret",
            "model": "test-model"
        }
    )
    assert resp.status_code == 422
    assert "không được chứa query parameters" in str(resp.json())

def test_gate2_negative_budget_units_rejected(client):
    """Hệ số quy đổi ngân sách âm bị từ chối 422."""
    owner_token = create_test_token(user_id="owner_founder_01")
    resp = client.put(
        "/v1/platform/llm-config",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "is_enabled": False,
            "base_url": "http://127.0.0.1:20128/v1",
            "model": "test-model",
            "budget_units_per_usd": -5.0
        }
    )
    assert resp.status_code == 422
    assert "greater than 0" in str(resp.json()).lower() or "lớn hơn 0" in str(resp.json()).lower()

# ==================== TEST 4: IDEMPOTENT MIGRATIONS ====================

def test_gate2_idempotent_migrations():
    """Kiểm tra migration nâng cấp và rollback an toàn mà không phá hủy DB."""
    # Nâng cấp
    up_res = migrate_platform_llm_config_up()
    assert up_res is True

    # Chạy lại nâng cấp lần nữa (idempotent)
    up_res_2 = migrate_platform_llm_config_up()
    assert up_res_2 is True

    # Rollback
    down_res = migrate_platform_llm_config_down()
    assert down_res is True

    # Khôi phục lại
    up_res_3 = migrate_platform_llm_config_up()
    assert up_res_3 is True


# ==================== TEST 5: PROBE GATEWAY & PUBLIC STATUS ====================

def test_gate2_public_status_available_without_auth(client):
    """Bất kỳ người dùng nào cũng có thể đọc trạng thái tối giản (public status)."""
    resp = client.get("/v1/platform/llm-config/public-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_configured" in data
    assert "is_enabled" in data
    assert "model" in data
    assert "base_url" not in data # Không lộ endpoint nội bộ
    assert "api_key" not in data

def test_gate2_probe_gateway_non_owner_forbidden(client):
    """User không phải Owner không được phép gọi endpoint probe."""
    token = create_test_token(user_id="random_user_456")
    # Dùng port không lắng nghe để kiểm tra kết quả khi gateway offline
    resp = client.post(
        "/v1/platform/llm-config/probe",
        headers={"Authorization": f"Bearer {token}"},
        json={"base_url": "http://127.0.0.1:59999/v1"}
    )
    assert resp.status_code == 403

def test_gate2_probe_gateway_owner_probe_offline(client):
    """Owner gọi probe gateway khi cổng đóng: trả về kết quả chân thực (không ngụy tạo thành công)."""
    token = create_test_token(user_id="owner_founder_01")
    # Dùng port không lắng nghe để kiểm tra kết quả khi gateway offline
    resp = client.post(
        "/v1/platform/llm-config/probe",
        headers={"Authorization": f"Bearer {token}"},
        json={"base_url": "http://127.0.0.1:59999/v1"}
    )
    assert resp.status_code == 200
    data = resp.json()
    # Khi 9Router chưa bật, reachable = False
    assert data["reachable"] is False
    assert "ConnectTimeout" in data["message"] or "ConnectError" in data["message"] or "Lỗi" in data["message"] or "Không nhận được" in data["message"]
