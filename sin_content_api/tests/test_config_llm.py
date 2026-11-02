# Test kiem thu cho Gate 1: Cau hinh kin va tuong thich offline
import pytest
from pydantic import ValidationError
from src.config import API_ROOT, Settings

def test_settings_env_file_is_stable_from_any_working_directory():
    assert Settings.model_config["env_file"] == API_ROOT / ".env"
    assert Settings().llm_api_key_file == API_ROOT.parent / "9router.env"

def test_gate1_default_config_offline_compatible():
    """Gate 1: Mac dinh an toan la chua bat LLM khi thieu cau hinh bat buoc."""
    s = Settings(
        llm_model="",
        llm_api_key="",
        llm_enabled=False,
        llm_timeout_seconds=30.0,
        llm_max_output_tokens=1500,
        _env_file=None
    )
    assert s.is_llm_enabled is False
    assert s.llm_base_url == "http://127.0.0.1:20128/v1"
    assert s.llm_timeout_seconds == 30.0
    assert s.llm_max_output_tokens == 1500
    assert s.llm_budget_units_per_usd == 1.0
    assert s.llm_input_usd_per_1k_tokens == 0.0
    assert s.llm_output_usd_per_1k_tokens == 0.0

def test_gate1_loopback_http_allowed():
    """Gate 1: Scheme http duoc phep cho dia chi loopback (127.0.0.1, localhost, ::1)."""
    s1 = Settings(llm_base_url="http://127.0.0.1:20128/v1/", _env_file=None)
    assert s1.llm_base_url == "http://127.0.0.1:20128/v1"

    s2 = Settings(llm_base_url="http://localhost:9000/v1", _env_file=None)
    assert s2.llm_base_url == "http://localhost:9000/v1"

def test_gate1_wildcard_0000_rejected():
    """Gate 1 & Van de 5: 0.0.0.0 la wildcard address, khong phai loopback va phai bi tu choi."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(llm_base_url="http://0.0.0.0:20128/v1", _env_file=None)
    assert "bắt buộc phải sử dụng HTTPS" in str(exc_info.value)

def test_gate1_userinfo_query_fragment_rejected():
    """Gate 1 & Van de 5: Cấm userinfo, query params va fragment trong base URL."""
    with pytest.raises(ValidationError) as exc1:
        Settings(llm_base_url="http://user:pass@127.0.0.1:20128/v1", _env_file=None)
    assert "không được chứa thông tin xác thực userinfo" in str(exc1.value)

    with pytest.raises(ValidationError) as exc2:
        Settings(llm_base_url="http://127.0.0.1:20128/v1?token=secret123", _env_file=None)
    assert "không được chứa query parameters" in str(exc2.value)

    with pytest.raises(ValidationError) as exc3:
        Settings(llm_base_url="http://127.0.0.1:20128/v1#anchor", _env_file=None)
    assert "không được chứa fragment" in str(exc3.value)

def test_gate1_remote_https_allowed():
    """Gate 1: Endpoint tu xa hop le khi su dung HTTPS."""
    s = Settings(llm_base_url="https://api.openai.com/v1", _env_file=None)
    assert s.llm_base_url == "https://api.openai.com/v1"

def test_gate1_remote_http_rejected():
    """Gate 1: Endpoint tu xa su dung HTTP phai bi tu choi ro rang."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(llm_base_url="http://remote-server.com/v1", _env_file=None)
    assert "bắt buộc phải sử dụng HTTPS" in str(exc_info.value)

def test_gate1_invalid_scheme_rejected():
    """Gate 1: Scheme khong phai http/https phai bi tu choi."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(llm_base_url="ftp://127.0.0.1/v1", _env_file=None)
    assert "Chỉ chấp nhận http hoặc https" in str(exc_info.value)

def test_gate1_secrets_masked_in_repr():
    """Gate 1: Khoa bi mat khong duoc xuat hien trong repr(settings)."""
    secret = "sk-super-secret-key-123456789"
    s = Settings(
        llm_enabled=True,
        llm_model="gpt-4o-mini",
        llm_api_key=secret,
        _env_file=None
    )
    repr_str = repr(s)
    assert secret not in repr_str
    assert "******" in repr_str
    assert s.is_llm_enabled is True

def test_gate1_budget_units_per_usd_must_be_positive():
    """Gate 1 & Van de 1: llm_budget_units_per_usd <= 0 hoac am phai bi tu choi."""
    with pytest.raises(ValidationError) as exc1:
        Settings(llm_budget_units_per_usd=-1.0, _env_file=None)
    assert "phải là số thực hữu hạn lớn hơn 0" in str(exc1.value)

    with pytest.raises(ValidationError) as exc2:
        Settings(llm_budget_units_per_usd=0.0, _env_file=None)
    assert "phải là số thực hữu hạn lớn hơn 0" in str(exc2.value)

def test_gate1_invalid_limits_rejected():
    """Gate 1 & Van de 1: Cac gioi han token, bytes, timeout phai nam trong khoang hop le."""
    with pytest.raises(ValidationError):
        Settings(llm_timeout_seconds=0.0, _env_file=None)

    with pytest.raises(ValidationError):
        Settings(llm_timeout_seconds=1801.0, _env_file=None)

    assert Settings(llm_timeout_seconds=1800.0, _env_file=None).llm_timeout_seconds == 1800.0

    with pytest.raises(ValidationError):
        Settings(llm_max_input_bytes=0, _env_file=None)

    with pytest.raises(ValidationError):
        Settings(llm_max_input_bytes=-10, _env_file=None)

    with pytest.raises(ValidationError):
        Settings(llm_max_output_tokens=0, _env_file=None)

def test_gate1_activation_requires_key_and_model(tmp_path):
    """Gate 1 & Van de 4: Khi llm_enabled=True, bat buoc phai co LLM_MODEL va LLM_API_KEY."""
    with pytest.raises(ValidationError) as exc1:
        Settings(llm_enabled=True, llm_model="", llm_api_key="sk-123", _env_file=None)
    assert "LLM_MODEL (hoặc LLM_DEFAULT_MODEL) bắt buộc" in str(exc1.value)

    with pytest.raises(ValidationError) as exc2:
        Settings(llm_enabled=True, llm_model="gpt-4o", llm_api_key="", llm_api_key_file=tmp_path / "missing", _env_file=None)
    assert "LLM_API_KEY bắt buộc" in str(exc2.value)

def test_gate1_alias_model_supported():
    """Gate 1 & Van de 4: Ho tro ca alias LLM_DEFAULT_MODEL va LLM_MODEL."""
    s = Settings(
        llm_enabled=True,
        LLM_DEFAULT_MODEL="claude-3-5-sonnet",
        llm_api_key="sk-abc-123",
        _env_file=None
    )
    assert s.llm_model == "claude-3-5-sonnet"
    assert s.is_llm_enabled is True

def test_gate1_loads_router_key_from_private_file(tmp_path):
    key_file = tmp_path / "9router.env"
    key_file.write_text("router-secret\n", encoding="utf-8")
    s = Settings(
        llm_enabled=True,
        llm_model="cx/gpt-6-luna",
        llm_api_key_file=key_file,
        _env_file=None,
    )
    assert s.llm_api_key == "router-secret"
    assert s.is_llm_enabled is True

def test_crypto_vault_reads_master_key_from_settings(monkeypatch):
    from src.config import settings
    from src.modules.platform_config.crypto_vault import decrypt_secret, encrypt_secret

    monkeypatch.delenv("LLM_ENCRYPTION_MASTER_KEY", raising=False)
    monkeypatch.setattr(settings, "llm_encryption_master_key", "configured-in-settings")
    encrypted = encrypt_secret("router-secret")
    assert decrypt_secret(encrypted) == "router-secret"
