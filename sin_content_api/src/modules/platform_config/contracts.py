# Contracts cho module cau hinh nen tang Platform Config (Gate 2)
import math
from typing import Optional, List
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator

class PlatformLLMConfigOut(BaseModel):
    """Schema tra ve cho Platform Owner (Tuyet doi khong tra ve API key plaintext hoac ciphertext)."""
    is_configured: bool
    is_enabled: bool
    base_url: str
    model: str
    key_fingerprint: str
    has_api_key: bool
    timeout_seconds: float
    max_output_tokens: int
    max_input_bytes: int
    input_usd_per_1k_tokens: float
    output_usd_per_1k_tokens: float
    budget_units_per_usd: float
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None

class PlatformLLMConfigUpdate(BaseModel):
    """Schema cap nhat cau hinh danh cho Platform Owner."""
    is_enabled: bool
    base_url: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    new_api_key: Optional[str] = None # None hoac chuoi rong de giu nguyen key cu da luu
    timeout_seconds: float = Field(30.0, gt=0, le=1800)
    max_output_tokens: int = Field(1500, ge=1, le=32000)
    max_input_bytes: int = Field(20000, ge=10, le=10000000)
    input_usd_per_1k_tokens: float = Field(0.00015, ge=0)
    output_usd_per_1k_tokens: float = Field(0.00060, ge=0)
    budget_units_per_usd: float = Field(100.0, gt=0)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("base_url không được để trống.")
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Scheme '{parsed.scheme}' không hợp lệ. Chỉ chấp nhận http hoặc https.")
        if parsed.username or parsed.password:
            raise ValueError("base_url không được chứa thông tin xác thực userinfo.")
        if parsed.query:
            raise ValueError("base_url không được chứa query parameters.")
        if parsed.fragment:
            raise ValueError("base_url không được chứa fragment (#).")

        host = (parsed.hostname or "").lower()
        is_loopback = host in ("127.0.0.1", "localhost", "::1")
        if parsed.scheme == "http" and not is_loopback:
            safe_netloc = parsed.netloc or host
            raise ValueError(f"Endpoint từ xa '{safe_netloc}' bắt buộc phải sử dụng HTTPS. HTTP chỉ cho phép trên loopback.")
        return v.rstrip("/")

    @field_validator("budget_units_per_usd")
    @classmethod
    def validate_budget_units(cls, v: float) -> float:
        if not math.isfinite(v) or v <= 0:
            raise ValueError("budget_units_per_usd phải là số thực hữu hạn lớn hơn 0.")
        return v

class PlatformLLMProbeRequest(BaseModel):
    """Schema yeu cau kiem tra ket noi gateway."""
    base_url: Optional[str] = None
    model: Optional[str] = None

class PlatformLLMProbeResult(BaseModel):
    """Ket qua kiem tra ket noi gateway."""
    reachable: bool
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    message: str
    models_discovered: Optional[List[str]] = Field(default_factory=list)

class PlatformLLMPublicStatus(BaseModel):
    """Trang thai cong LLM toi gian cho phep nguoi dung thong thuong xem."""
    is_configured: bool
    is_enabled: bool
    model: str
