# Tests cho Gate 3: LLMClient dung cau hinh trung tam tu Database va kiem tra Gateway
import os
import json
import pytest
import httpx
from sqlalchemy.orm import Session

os.environ["TESTING"] = "1"

from src.database import SessionLocal, Base, engine
from src.models.entities import PlatformLLMConfig
from src.modules.llm.client import (
    LLMClient, CompletionResult, LLMConfigError, LLMTimeoutError,
    LLMNetworkError, LLMResponseError
)
from src.modules.platform_config.crypto_vault import encrypt_secret

@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    yield db
    db.close()

# ==================== TEST 1: KHỞI TẠO TỪ DATABASE SINGLETON ====================

def test_gate3_client_from_db_active(db_session):
    """LLMClient nạp cấu hình active từ DB, tự động giải mã API Key an toàn."""
    # Thiết lập cấu hình active trong DB
    raw_key = "sk-live-central-token-12345"
    cfg = db_session.query(PlatformLLMConfig).filter(
        PlatformLLMConfig.id == "default_platform_llm_config"
    ).first()
    if not cfg:
        cfg = PlatformLLMConfig(id="default_platform_llm_config")
        db_session.add(cfg)

    cfg.is_enabled = True
    cfg.base_url = "http://127.0.0.1:20128/v1"
    cfg.model = "gpt-4o-mini"
    cfg.api_key_ciphertext = encrypt_secret(raw_key)
    cfg.key_fingerprint = "••••••••••••2345"
    cfg.timeout_seconds = 15.0
    cfg.max_output_tokens = 800
    cfg.max_input_bytes = 10000
    db_session.commit()

    # Khởi tạo client từ DB
    client = LLMClient.from_db(db_session)
    assert client.is_enabled is True
    assert client.base_url == "http://127.0.0.1:20128/v1"
    assert client.model == "gpt-4o-mini"
    assert client.api_key == raw_key # Giải mã chính xác
    assert client.timeout_seconds == 15.0
    assert client.max_output_tokens == 800

def test_gate3_client_from_db_disabled(db_session):
    """Khi cấu hình trong DB bị tắt (is_enabled=False), client ở trạng thái disabled."""
    cfg = db_session.query(PlatformLLMConfig).first()
    cfg.is_enabled = False
    db_session.commit()

    client = LLMClient.from_db(db_session)
    assert client.is_enabled is False

def test_gate3_client_from_db_missing_key(db_session):
    """Khi cấu hình thiếu key, client ở trạng thái disabled."""
    cfg = db_session.query(PlatformLLMConfig).first()
    cfg.is_enabled = True
    cfg.api_key_ciphertext = None
    db_session.commit()

    client = LLMClient.from_db(db_session)
    assert client.is_enabled is False

# ==================== TEST 2: GỌI COMPLETION VỚI CLIENT TỪ DB ====================

def test_gate3_complete_via_centralized_client(db_session):
    """Gửi completion qua client trung tâm với MockTransport thành công."""
    raw_key = "sk-central-auth-test"
    cfg = db_session.query(PlatformLLMConfig).first()
    cfg.is_enabled = True
    cfg.api_key_ciphertext = encrypt_secret(raw_key)
    cfg.model = "gpt-4o-central"
    db_session.commit()

    def mock_gateway(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://127.0.0.1:20128/v1/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {raw_key}"
        body = json.loads(request.read())
        assert body["model"] == "gpt-4o-central"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Ý tưởng nội dung từ Gateway 9Router"}}],
            "model": "gpt-4o-central",
            "usage": {"prompt_tokens": 50, "completion_tokens": 25}
        })

    client = LLMClient.from_db(db_session, transport=httpx.MockTransport(mock_gateway))
    res = client.complete([{"role": "user", "content": "Gợi ý kịch bản"}])
    assert res.content == "Ý tưởng nội dung từ Gateway 9Router"
    assert res.prompt_tokens == 50
    assert res.completion_tokens == 25
    assert res.usage_valid is True

# ==================== TEST 3: TRUY VẤN DANH SÁCH MODELS (LIST_MODELS) ====================

def test_gate3_list_models_queries_gateway_without_altering_config(db_session):
    """Hàm list_models truy vấn GET /v1/models mà không làm thay đổi model mặc định của client."""
    def mock_models_endpoint(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://127.0.0.1:20128/v1/models"
        return httpx.Response(200, json={
            "data": [
                {"id": "gpt-4o-mini", "object": "model"},
                {"id": "gemini-1.5-flash", "object": "model"},
                {"id": "claude-3-5-sonnet", "object": "model"}
            ]
        })

    client = LLMClient.from_db(db_session, transport=httpx.MockTransport(mock_models_endpoint))
    original_model = client.model
    models = client.list_models()
    assert models == ["gpt-4o-mini", "gemini-1.5-flash", "claude-3-5-sonnet"]
    assert client.model == original_model # Model mặc định giữ nguyên
