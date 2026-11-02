# Cau hinh Pydantic v2 cho API noi dung SIN
import math
from pathlib import Path
from urllib.parse import urlparse
from pydantic import Field, AliasChoices, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = (API_ROOT / "sin_content_offline.db").resolve().as_posix()


def read_llm_api_key_file(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("Không thể đọc LLM_API_KEY_FILE.") from exc
    if len(raw.encode("utf-8")) > 16_384:
        raise ValueError("LLM_API_KEY_FILE vượt quá kích thước cho phép.")

    key_lines = [line for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    known_names = {"base_url", "api-key", "api_key", "llm_api_key"}
    key = ""
    if len(key_lines) == 1:
        name, separator, _ = key_lines[0].partition("=")
        if not separator or name.strip().casefold() not in known_names:
            key = key_lines[0].strip()
    if not key:
        values: dict[str, str] = {}
        for line in key_lines:
            name, separator, value = line.partition("=")
            normalized_name = name.strip().casefold()
            if not separator or normalized_name not in known_names:
                raise ValueError("LLM_API_KEY_FILE có định dạng không hợp lệ.")
            if normalized_name in values:
                raise ValueError("LLM_API_KEY_FILE có khóa bị lặp.")
            values[normalized_name] = value.strip()
        key = values.get("api-key") or values.get("api_key") or values.get("llm_api_key", "")

    if not key or any(char.isspace() for char in key):
        raise ValueError("LLM_API_KEY_FILE phải chứa một khóa hợp lệ trên một dòng.")
    return key


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=API_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    app_name: str = "SIN Content Intelligence API"
    app_version: str = "1.0.0"
    app_env: str = "offline" # offline, staging, production
    debug: bool = False
    
    # Database URL: Mac dinh dung SQLite cuc bo cho offline mode, ho tro Postgres+pgvector khi co URL
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"
    
    # Rate limits & Budget Circuit Breaker
    default_max_cost_usd_per_run: float = 5.0
    synthetic_data_allowed: bool = True

    # Cau hinh LLM 9Router Gateway (Gate 1)
    llm_enabled: bool = Field(default=False, validation_alias=AliasChoices("llm_enabled", "LLM_ENABLED"))
    llm_base_url: str = Field(default="http://127.0.0.1:20128/v1", validation_alias=AliasChoices("llm_base_url", "LLM_BASE_URL"))
    llm_api_key: str = Field(default="", validation_alias=AliasChoices("llm_api_key", "LLM_API_KEY"))
    llm_api_key_file: Path = Field(default=API_ROOT.parent / "9router.env", validation_alias=AliasChoices("llm_api_key_file", "LLM_API_KEY_FILE"))
    llm_model: str = Field(default="", validation_alias=AliasChoices("llm_model", "LLM_MODEL", "llm_default_model", "LLM_DEFAULT_MODEL"))
    llm_timeout_seconds: float = Field(default=30.0, validation_alias=AliasChoices("llm_timeout_seconds", "LLM_TIMEOUT_SECONDS"))
    llm_max_input_bytes: int = Field(default=20000, validation_alias=AliasChoices("llm_max_input_bytes", "LLM_MAX_INPUT_BYTES"))
    llm_max_output_tokens: int = Field(default=1500, validation_alias=AliasChoices("llm_max_output_tokens", "LLM_MAX_OUTPUT_TOKENS"))
    llm_input_usd_per_1k_tokens: float = Field(default=0.0, validation_alias=AliasChoices("llm_input_usd_per_1k_tokens", "LLM_INPUT_USD_PER_1K_TOKENS"))
    llm_output_usd_per_1k_tokens: float = Field(default=0.0, validation_alias=AliasChoices("llm_output_usd_per_1k_tokens", "LLM_OUTPUT_USD_PER_1K_TOKENS"))
    llm_budget_units_per_usd: float = Field(default=1.0, validation_alias=AliasChoices("llm_budget_units_per_usd", "LLM_BUDGET_UNITS_PER_USD"))
    llm_encryption_master_key: str = Field(default="", validation_alias=AliasChoices("llm_encryption_master_key", "LLM_ENCRYPTION_MASTER_KEY"))
    platform_owner_user_ids: str = Field(default="", validation_alias=AliasChoices("platform_owner_user_ids", "PLATFORM_OWNER_USER_IDS"))
    auth_owner_email: str = Field(default="", validation_alias=AliasChoices("auth_owner_email", "AUTH_OWNER_EMAIL"))
    auth_workspace_id: str = Field(default="", validation_alias=AliasChoices("auth_workspace_id", "SIN_WORKSPACE_ID"))
    auth_allowed_origins: str = Field(default="", validation_alias=AliasChoices("auth_allowed_origins", "AUTH_ALLOWED_ORIGINS"))
    auth_cookie_secure: bool = Field(default=True, validation_alias=AliasChoices("auth_cookie_secure", "AUTH_COOKIE_SECURE"))

    @field_validator("llm_base_url")
    @classmethod
    def validate_llm_base_url(cls, v: str) -> str:
        if not v or not v.strip():
            return v
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Scheme không hợp lệ cho LLM_BASE_URL: '{parsed.scheme}'. Chỉ chấp nhận http hoặc https.")
        
        # Cam userinfo, query params va fragment trong base URL de chong ro ri thong tin
        if parsed.username or parsed.password:
            raise ValueError("LLM_BASE_URL không được chứa thông tin xác thực userinfo (username/password). Vui lòng cấu hình qua LLM_API_KEY.")
        if parsed.query:
            raise ValueError("LLM_BASE_URL không được chứa query parameters.")
        if parsed.fragment:
            raise ValueError("LLM_BASE_URL không được chứa fragment (#).")

        host = (parsed.hostname or "").lower()
        # 0.0.0.0 la wildcard address (INADDR_ANY), tuyet doi khong phai loopback
        is_loopback = host in ("127.0.0.1", "localhost", "::1")
        if parsed.scheme == "http" and not is_loopback:
            safe_netloc = parsed.netloc or host
            raise ValueError(f"Endpoint từ xa '{safe_netloc}' bắt buộc phải sử dụng HTTPS. HTTP chỉ cho phép trên loopback (localhost, 127.0.0.1).")
        return v.rstrip("/")

    @field_validator("llm_budget_units_per_usd")
    @classmethod
    def validate_budget_units_per_usd(cls, v: float) -> float:
        if not math.isfinite(v) or v <= 0.0:
            raise ValueError(f"LLM_BUDGET_UNITS_PER_USD phải là số thực hữu hạn lớn hơn 0 (nhận được: {v}).")
        return v

    @field_validator("llm_timeout_seconds")
    @classmethod
    def validate_timeout_seconds(cls, v: float) -> float:
        if not math.isfinite(v) or v <= 0.0 or v > 300.0:
            raise ValueError(f"LLM_TIMEOUT_SECONDS phải là số thực hữu hạn trong khoảng (0, 300] giây (nhận được: {v}).")
        return v

    @field_validator("llm_max_input_bytes")
    @classmethod
    def validate_max_input_bytes(cls, v: int) -> int:
        if v <= 0 or v > 10_000_000:
            raise ValueError(f"LLM_MAX_INPUT_BYTES phải là số nguyên dương và không vượt quá 10,000,000 bytes (nhận được: {v}).")
        return v

    @field_validator("llm_max_output_tokens")
    @classmethod
    def validate_max_output_tokens(cls, v: int) -> int:
        if v < 1 or v > 32_000:
            raise ValueError(f"LLM_MAX_OUTPUT_TOKENS phải nằm trong khoảng [1, 32000] tokens (nhận được: {v}).")
        return v

    @field_validator("llm_input_usd_per_1k_tokens", "llm_output_usd_per_1k_tokens")
    @classmethod
    def validate_token_pricing(cls, v: float) -> float:
        if not math.isfinite(v) or v < 0.0:
            raise ValueError(f"Giá token không được là số âm hoặc vô hạn (nhận được: {v}).")
        return v

    @field_validator("auth_owner_email")
    @classmethod
    def normalize_auth_owner_email(cls, v: str) -> str:
        return v.strip().casefold()

    @field_validator("auth_workspace_id")
    @classmethod
    def validate_auth_workspace_id(cls, v: str) -> str:
        value = v.strip()
        if value and (len(value) > 64 or not all(char.isalnum() or char in "_-" for char in value)):
            raise ValueError("SIN_WORKSPACE_ID chỉ nhận tối đa 64 ký tự chữ, số, gạch dưới hoặc gạch ngang.")
        return value

    @field_validator("auth_allowed_origins")
    @classmethod
    def validate_auth_allowed_origins(cls, v: str) -> str:
        origins = []
        for value in v.split(","):
            origin = value.strip()
            if not origin:
                continue
            parsed = urlparse(origin)
            try:
                parsed.port
            except ValueError as exc:
                raise ValueError("AUTH_ALLOWED_ORIGINS chứa cổng không hợp lệ.") from exc
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("AUTH_ALLOWED_ORIGINS chỉ nhận origin HTTP(S) hợp lệ, không gồm path hoặc credentials.")
            origins.append(f"{parsed.scheme.lower()}://{parsed.netloc.lower()}")
        return ",".join(dict.fromkeys(origins))

    @model_validator(mode="after")
    def validate_llm_activation(self) -> "Settings":
        if self.llm_enabled and not self.llm_api_key.strip() and self.llm_api_key_file.is_file():
            self.llm_api_key = read_llm_api_key_file(self.llm_api_key_file)
        if self.llm_enabled:
            if not self.llm_model or not self.llm_model.strip():
                raise ValueError("LLM_MODEL (hoặc LLM_DEFAULT_MODEL) bắt buộc phải được cấu hình khi LLM_ENABLED=True.")
            if not self.llm_api_key or not self.llm_api_key.strip():
                raise ValueError("LLM_API_KEY bắt buộc phải được cấu hình khi LLM_ENABLED=True.")
        return self

    @model_validator(mode="after")
    def validate_production_auth(self) -> "Settings":
        if self.app_env.casefold() == "production":
            if not self.auth_owner_email:
                raise ValueError("AUTH_OWNER_EMAIL phải được cấu hình khi APP_ENV=production.")
            if not self.auth_workspace_id:
                raise ValueError("SIN_WORKSPACE_ID phải được cấu hình khi APP_ENV=production.")
            if not self.auth_allowed_origins_set:
                raise ValueError("AUTH_ALLOWED_ORIGINS phải được cấu hình khi APP_ENV=production.")
            if not self.auth_cookie_secure and any(
                origin.startswith("https://") for origin in self.auth_allowed_origins_set
            ):
                raise ValueError("AUTH_COOKIE_SECURE=false chỉ được phép khi mọi AUTH_ALLOWED_ORIGINS dùng HTTP.")
        return self

    @property
    def is_llm_enabled(self) -> bool:
        """Kiem tra xem tinh nang LLM da duoc bat va cau hinh day du hay chua."""
        return bool(
            self.llm_enabled
            and self.llm_model
            and self.llm_model.strip()
            and self.llm_base_url
            and self.llm_base_url.strip()
            and self.llm_api_key
            and self.llm_api_key.strip()
        )

    @property
    def platform_owner_ids_set(self) -> set[str]:
        """Tập hợp các user_id được chỉ định là Platform Owner."""
        owners: set[str] = set()
        if self.platform_owner_user_ids:
            owners.update(x.strip() for x in self.platform_owner_user_ids.split(",") if x.strip())
        return owners

    @property
    def auth_allowed_origins_set(self) -> set[str]:
        return {origin for origin in self.auth_allowed_origins.split(",") if origin}

    def __repr__(self) -> str:
        d = dict(self.__dict__)
        if "llm_api_key" in d and d["llm_api_key"]:
            d["llm_api_key"] = "******"
        if "llm_encryption_master_key" in d and d["llm_encryption_master_key"]:
            d["llm_encryption_master_key"] = "******"
        return f"Settings({d})"

settings = Settings()
