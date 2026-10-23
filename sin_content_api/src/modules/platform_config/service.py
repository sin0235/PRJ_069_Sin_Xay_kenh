# Service quan ly cau hinh LLM Singleton va kiem tra ket noi 9Router (Gate 2 & 3)
import time
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import httpx
from fastapi import HTTPException, status

from src.models.entities import PlatformLLMConfig, AuditEvent
from src.modules.platform_config.contracts import (
    PlatformLLMConfigOut, PlatformLLMConfigUpdate,
    PlatformLLMProbeRequest, PlatformLLMProbeResult,
    PlatformLLMPublicStatus
)
from src.modules.platform_config.crypto_vault import (
    encrypt_secret, decrypt_secret, compute_key_fingerprint
)
from src.config import settings

SINGLETON_CONFIG_ID = "default_platform_llm_config"

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class PlatformConfigService:
    def get_or_create_config(self, db: Session) -> PlatformLLMConfig:
        """Lay ban ghi cau hinh duy nhat (Singleton) hoac tao moi neu chua ton tai."""
        cfg = db.query(PlatformLLMConfig).filter(PlatformLLMConfig.id == SINGLETON_CONFIG_ID).first()
        if not cfg:
            # Khoi tao tu settings neu co
            initial_ciphertext = None
            initial_fingerprint = None
            if settings.llm_api_key:
                try:
                    initial_ciphertext = encrypt_secret(settings.llm_api_key)
                    initial_fingerprint = compute_key_fingerprint(settings.llm_api_key)
                except Exception:
                    initial_ciphertext = None

            cfg = PlatformLLMConfig(
                id=SINGLETON_CONFIG_ID,
                is_enabled=settings.llm_enabled,
                base_url=settings.llm_base_url or "http://127.0.0.1:20128/v1",
                model=settings.llm_model or "gpt-4o-mini",
                api_key_ciphertext=initial_ciphertext,
                key_fingerprint=initial_fingerprint,
                timeout_seconds=settings.llm_timeout_seconds,
                max_output_tokens=settings.llm_max_output_tokens,
                max_input_bytes=settings.llm_max_input_bytes,
                input_usd_per_1k_tokens=settings.llm_input_usd_per_1k_tokens,
                output_usd_per_1k_tokens=settings.llm_output_usd_per_1k_tokens,
                budget_units_per_usd=settings.llm_budget_units_per_usd,
                updated_by="SYSTEM_INIT",
                updated_at=utc_now()
            )
            db.add(cfg)
            db.commit()
            db.refresh(cfg)
        return cfg

    def get_config_out(self, db: Session) -> PlatformLLMConfigOut:
        """Tra ve thong tin cau hinh da loai bo 100% bi mat (chi tra fingerprint)."""
        cfg = self.get_or_create_config(db)
        return PlatformLLMConfigOut(
            is_configured=bool(cfg.api_key_ciphertext and cfg.model),
            is_enabled=bool(cfg.is_enabled),
            base_url=cfg.base_url,
            model=cfg.model,
            key_fingerprint=cfg.key_fingerprint or "",
            has_api_key=bool(cfg.api_key_ciphertext),
            timeout_seconds=cfg.timeout_seconds,
            max_output_tokens=cfg.max_output_tokens,
            max_input_bytes=cfg.max_input_bytes,
            input_usd_per_1k_tokens=cfg.input_usd_per_1k_tokens,
            output_usd_per_1k_tokens=cfg.output_usd_per_1k_tokens,
            budget_units_per_usd=cfg.budget_units_per_usd,
            updated_at=cfg.updated_at.isoformat() if cfg.updated_at else None,
            updated_by=cfg.updated_by
        )

    def get_public_status(self, db: Session) -> PlatformLLMPublicStatus:
        """Tra ve trang thai cong LLM toi gian cho phep nguoi dung thong thuong xem."""
        cfg = self.get_or_create_config(db)
        return PlatformLLMPublicStatus(
            is_configured=bool(cfg.api_key_ciphertext and cfg.model),
            is_enabled=bool(cfg.is_enabled),
            model=cfg.model
        )

    def update_config(self, db: Session, user_id: str, payload: PlatformLLMConfigUpdate) -> PlatformLLMConfigOut:
        """Cap nhat cau hinh danh rieng cho Platform Owner."""
        cfg = self.get_or_create_config(db)

        # 1. Xu ly khoa xac thuc
        if payload.new_api_key and payload.new_api_key.strip():
            clean_key = payload.new_api_key.strip()
            cfg.api_key_ciphertext = encrypt_secret(clean_key)
            cfg.key_fingerprint = compute_key_fingerprint(clean_key)
        # Neu new_api_key la None hoac "" -> giu nguyen khoa cu

        # 2. Neu bat is_enabled=True, bat buoc phai co API key da luu
        if payload.is_enabled:
            if not cfg.api_key_ciphertext:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Không thể bật cổng LLM khi chưa có Khóa Xác Thực (API Key)."
                )
            if not payload.model or not payload.model.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Không thể bật cổng LLM khi chưa có Định Danh Mô Hình (Model ID)."
                )

        cfg.is_enabled = payload.is_enabled
        cfg.base_url = payload.base_url.strip()
        cfg.model = payload.model.strip()
        cfg.timeout_seconds = payload.timeout_seconds
        cfg.max_output_tokens = payload.max_output_tokens
        cfg.max_input_bytes = payload.max_input_bytes
        cfg.input_usd_per_1k_tokens = payload.input_usd_per_1k_tokens
        cfg.output_usd_per_1k_tokens = payload.output_usd_per_1k_tokens
        cfg.budget_units_per_usd = payload.budget_units_per_usd
        cfg.updated_by = user_id
        cfg.updated_at = utc_now()

        # 3. Ghi audit event khong chua thong tin bi mat
        audit = AuditEvent(
            workspace_id="platform",
            actor_id=user_id,
            event_type="PLATFORM_LLM_CONFIG_UPDATE",
            details=json.dumps({
                "is_enabled": cfg.is_enabled,
                "base_url": cfg.base_url,
                "model": cfg.model,
                "key_fingerprint": cfg.key_fingerprint,
                "key_rotated": bool(payload.new_api_key and payload.new_api_key.strip())
            }, ensure_ascii=False)
        )
        db.add(audit)
        db.commit()
        db.refresh(cfg)

        return self.get_config_out(db)

    def get_runtime_llm_credentials(self, db: Session) -> Optional[Dict[str, Any]]:
        """Giai ma thong tin xac thuc LLM de Client backend thuc thi (Khong bao gio tra ra API frontend)."""
        cfg = self.get_or_create_config(db)
        if not cfg.is_enabled:
            return {"is_enabled": False}
        if not cfg.api_key_ciphertext:
            return None

        try:
            raw_key = decrypt_secret(cfg.api_key_ciphertext)
        except Exception:
            return None

        return {
            "is_enabled": True,
            "base_url": cfg.base_url,
            "model": cfg.model,
            "api_key": raw_key,
            "timeout_seconds": cfg.timeout_seconds,
            "max_output_tokens": cfg.max_output_tokens,
            "max_input_bytes": cfg.max_input_bytes,
            "input_usd_per_1k_tokens": cfg.input_usd_per_1k_tokens,
            "output_usd_per_1k_tokens": cfg.output_usd_per_1k_tokens,
            "budget_units_per_usd": cfg.budget_units_per_usd
        }

    def probe_gateway(
        self,
        db: Session,
        req: PlatformLLMProbeRequest,
        transport: Optional[httpx.BaseTransport] = None
    ) -> PlatformLLMProbeResult:
        """Kiem tra ket noi den gateway 9Router ma khong phat sinh chi phi token."""
        cfg = self.get_or_create_config(db)
        target_url = (req.base_url or cfg.base_url).strip().rstrip("/")
        probe_endpoints = [
            f"{target_url}/models",
            f"{target_url}/health",
            target_url
        ]

        start_time = time.perf_counter()
        last_resp = None
        discovered_models: List[str] = []

        try:
            with httpx.Client(transport=transport, timeout=5.0) as client:
                for probe_endpoint in probe_endpoints:
                    try:
                        resp = client.get(probe_endpoint)
                        last_resp = resp
                        if resp.status_code == 200:
                            latency = round((time.perf_counter() - start_time) * 1000, 2)
                            try:
                                data = resp.json()
                                if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                                    discovered_models = [m["id"] for m in data["data"] if isinstance(m, dict) and "id" in m]
                            except Exception:
                                pass

                            msg = f"Kết nối thành công tới cổng 9Router ({latency}ms)."
                            if discovered_models:
                                msg += f" Phát hiện {len(discovered_models)} mô hình sẵn sàng."
                            return PlatformLLMProbeResult(
                                reachable=True,
                                latency_ms=latency,
                                status_code=resp.status_code,
                                message=msg,
                                models_discovered=discovered_models
                            )
                    except (httpx.HTTPStatusError, httpx.RequestError):
                        continue

                latency = round((time.perf_counter() - start_time) * 1000, 2)
                code = last_resp.status_code if last_resp else None
                return PlatformLLMProbeResult(
                    reachable=False,
                    latency_ms=latency,
                    status_code=code,
                    message=f"Gateway trả mã trạng thái {code}." if code else "Không nhận được phản hồi hợp lệ từ Gateway."
                )
        except httpx.ConnectTimeout:
            return PlatformLLMProbeResult(
                reachable=False,
                message="ConnectTimeout: Cổng 20128 chưa được khởi động hoặc từ chối kết nối."
            )
        except httpx.ConnectError:
            return PlatformLLMProbeResult(
                reachable=False,
                message="ConnectError: Không thể thiết lập kết nối tới cổng 9Router."
            )
        except Exception as exc:
            return PlatformLLMProbeResult(
                reachable=False,
                message=f"Lỗi kiểm tra kết nối: {type(exc).__name__}."
            )

platform_config_service = PlatformConfigService()
