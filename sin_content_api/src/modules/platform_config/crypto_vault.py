# Module ma hoa va bao ve bi mat API Key cua Cong LLM 9Router (Gate 2)
# Tuan thu nghiem ngat: Zero Plaintext Secrets, Khoa luu ngoai repo, 100% Khong ro ri
import os
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

DEFAULT_TEST_MASTER_KEY = "baha_platform_llm_test_master_key_32bytes!"

def _derive_fernet_key(raw_key: str) -> bytes:
    """Bien doi chuoi khoa chu thanh khoa 32-byte url-safe base64 chuan Fernet qua SHA-256."""
    h = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(h)

def _get_master_key(master_key: Optional[str] = None) -> str:
    if master_key and master_key.strip():
        return master_key.strip()
    env_key = os.environ.get("LLM_ENCRYPTION_MASTER_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    # Che do kiem thu offline
    if os.environ.get("TESTING") == "1" or os.environ.get("PYTEST_CURRENT_TEST"):
        return DEFAULT_TEST_MASTER_KEY
    raise RuntimeError(
        "LLM_ENCRYPTION_MASTER_KEY chưa được cấu hình trong biến môi trường hoặc Secret Vault."
    )

def encrypt_secret(plaintext: str, master_key: Optional[str] = None) -> str:
    """Ma hoa khoa bi mat sang dang ciphertext (Fernet token)."""
    if not plaintext:
        return ""
    key_bytes = _derive_fernet_key(_get_master_key(master_key))
    f = Fernet(key_bytes)
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")

def decrypt_secret(ciphertext: str, master_key: Optional[str] = None) -> str:
    """Giai ma ciphertext de lay plaintext API key phuc vu goi backend upstream."""
    if not ciphertext:
        return ""
    key_bytes = _derive_fernet_key(_get_master_key(master_key))
    f = Fernet(key_bytes)
    try:
        data = f.decrypt(ciphertext.encode("utf-8"))
        return data.decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Không thể giải mã khóa bí mật: Ciphertext không hợp lệ hoặc sai khóa chủ (Master Key)."
        ) from exc

def compute_key_fingerprint(secret: str) -> str:
    """Sinh dau che van tay an toan hien thi tren giao dien (chi 4 ky tu cuoi, khong the dao nguoc)."""
    if not secret:
        return ""
    clean = secret.strip()
    if len(clean) <= 4:
        return "••••••••••••"
    return f"••••••••••••{clean[-4:]}"
