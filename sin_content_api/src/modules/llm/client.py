# Client HTTP giao thuc OpenAI-compatible cho SIN Content API (Gate 2)
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx

from src.config import settings as default_settings, Settings

logger = logging.getLogger("sin_content_api.llm_client")

@dataclass
class CompletionResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    usage_valid: bool = False

class LLMClientError(Exception):
    def __init__(
        self,
        message: str,
        error_code: str = "LLM_ERROR",
        status_code: Optional[int] = None,
        model: str = "",
        duration_ms: float = 0.0,
        request_id: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.model = model
        self.duration_ms = duration_ms
        self.request_id = request_id

class LLMConfigError(LLMClientError):
    pass

class LLMTimeoutError(LLMClientError):
    pass

class LLMNetworkError(LLMClientError):
    pass

class LLMResponseError(LLMClientError):
    pass

class LLMClient:
    """
    Client dong bo su dung httpx de goi toi endpoint OpenAI-compatible /v1/chat/completions (Gate 2 & 3).
    - Khong tu y retry de bao ve ngan sach va chong goi lap.
    - Gioi han input prompt theo byte UTF-8 bao thu.
    - Chuan hoa loi an toan: chi log ma loi, model, thoi luong va request ID. Khong log key/prompt/response tho.
    - Cau hinh lay tu Database Singleton hoac Settings, khong nhan URL/key tu caller request.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        runtime_config: Optional[Dict[str, Any]] = None,
        transport: Optional[httpx.BaseTransport] = None
    ):
        self.transport = transport
        if runtime_config:
            self.base_url = str(runtime_config.get("base_url", "")).rstrip("/")
            self.api_key = str(runtime_config.get("api_key", "")).strip()
            self.model = str(runtime_config.get("model", "")).strip()
            self.timeout_seconds = float(runtime_config.get("timeout_seconds", 30.0))
            self.max_input_bytes = int(runtime_config.get("max_input_bytes", 20000))
            self.max_output_tokens = int(runtime_config.get("max_output_tokens", 1500))
            self.is_enabled = bool(runtime_config.get("is_enabled", False))
        else:
            cfg = settings or default_settings
            self.base_url = cfg.llm_base_url.rstrip("/")
            self.api_key = cfg.llm_api_key.strip() if cfg.llm_api_key else ""
            self.model = cfg.llm_model.strip() if cfg.llm_model else ""
            self.timeout_seconds = float(cfg.llm_timeout_seconds)
            self.max_input_bytes = int(cfg.llm_max_input_bytes)
            self.max_output_tokens = int(cfg.llm_max_output_tokens)
            self.is_enabled = getattr(cfg, "is_llm_enabled", False)

    @classmethod
    def from_db(cls, db: Any, transport: Optional[httpx.BaseTransport] = None) -> "LLMClient":
        """Khoi tao LLMClient tu cau hinh Singleton trong co so du lieu da giai ma bi mat."""
        from src.modules.platform_config.service import platform_config_service
        creds = platform_config_service.get_runtime_llm_credentials(db)
        if not creds:
            client = cls(settings=None, transport=transport)
            client.is_enabled = False
            return client
        client = cls(runtime_config=creds, transport=transport)
        client.is_enabled = bool(creds.get("is_enabled"))
        return client

    def list_models(self) -> List[str]:
        """Truy van danh sach model tu 9Router qua GET /v1/models (chi doc, khong tu thay model)."""
        if not self.api_key:
            raise LLMConfigError("Cần API Key để truy vấn danh mục models.", error_code="API_KEY_NOT_CONFIGURED")
        endpoint = f"{self.base_url}/models"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout_seconds) as client:
                res = client.get(endpoint, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    models = []
                    for item in data.get("data", []):
                        if isinstance(item, dict) and "id" in item:
                            models.append(str(item["id"]))
                    return models
                return []
        except Exception as exc:
            logger.warning("Không thể truy vấn danh sách models: %s", exc)
            return []

    def complete(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None
    ) -> CompletionResult:
        if not self.model:
            raise LLMConfigError(
                "LLM_MODEL chưa được cấu hình. Không thể gửi yêu cầu hoàn thành.",
                error_code="MODEL_NOT_CONFIGURED"
            )
        if not self.api_key:
            raise LLMConfigError(
                "LLM_API_KEY chưa được cấu hình. Yêu cầu Bearer token để xác thực với LLM Gateway.",
                error_code="API_KEY_NOT_CONFIGURED"
            )

        # 1. Gioi han prompt theo UTF-8 byte truoc khi goi (Gate 2)
        total_input_bytes = sum(len(str(m.get("content", "")).encode("utf-8")) for m in messages)
        if total_input_bytes > self.max_input_bytes:
            raise LLMResponseError(
                f"Kích thước prompt ({total_input_bytes} bytes) vượt quá giới hạn cho phép ({self.max_input_bytes} bytes).",
                error_code="INPUT_TOO_LARGE",
                model=self.model
            )

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        tokens_to_request = max_tokens if max_tokens is not None else self.max_output_tokens
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": tokens_to_request,
            "stream": False
        }

        start_time = time.perf_counter()
        req_id: Optional[str] = None
        duration_ms = 0.0

        try:
            with httpx.Client(transport=self.transport, timeout=self.timeout_seconds) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                req_id = response.headers.get("x-request-id") or response.headers.get("request-id")

                # 2. Xu ly ma trang thai HTTP
                if response.status_code == 401:
                    logger.warning("LLM call failed: error_code=UPSTREAM_UNAUTHORIZED, model=%s, duration_ms=%.1f, request_id=%s", self.model, duration_ms, req_id)
                    raise LLMResponseError(
                        "Xác thực với LLM Gateway thất bại (HTTP 401 Unauthorized).",
                        error_code="UPSTREAM_UNAUTHORIZED",
                        status_code=401,
                        model=self.model,
                        duration_ms=duration_ms,
                        request_id=req_id
                    )

                if response.status_code == 429:
                    logger.warning("LLM call failed: error_code=UPSTREAM_RATE_LIMITED, model=%s, duration_ms=%.1f, request_id=%s", self.model, duration_ms, req_id)
                    raise LLMResponseError(
                        "LLM Gateway quá tải hoặc đã đạt giới hạn tần suất (HTTP 429 Rate Limited).",
                        error_code="UPSTREAM_RATE_LIMITED",
                        status_code=429,
                        model=self.model,
                        duration_ms=duration_ms,
                        request_id=req_id
                    )

                if response.status_code >= 500:
                    if response.status_code == 503:
                        try:
                            body = response.json()
                            error = body.get("error", {}) if isinstance(body, dict) else {}
                            upstream_message = error.get("message", "") if isinstance(error, dict) else str(error)
                        except Exception:
                            upstream_message = ""
                        normalized_message = upstream_message.casefold()
                        if "429" in normalized_message and ("usage limit" in normalized_message or "rate limit" in normalized_message):
                            logger.warning("LLM call rate limited: error_code=UPSTREAM_RATE_LIMITED, status=%d, model=%s, duration_ms=%.1f, request_id=%s", response.status_code, self.model, duration_ms, req_id)
                            raise LLMResponseError(
                                "Hạn mức sử dụng 9Router đã đạt. Hãy đợi giới hạn làm mới rồi thử lại.",
                                error_code="UPSTREAM_RATE_LIMITED",
                                status_code=429,
                                model=self.model,
                                duration_ms=duration_ms,
                                request_id=req_id
                            )
                    logger.warning("LLM call failed: error_code=UPSTREAM_SERVER_ERROR, status=%d, model=%s, duration_ms=%.1f, request_id=%s", response.status_code, self.model, duration_ms, req_id)
                    raise LLMResponseError(
                        f"LLM Gateway gặp sự cố máy chủ nội bộ (HTTP {response.status_code}).",
                        error_code="UPSTREAM_SERVER_ERROR",
                        status_code=response.status_code,
                        model=self.model,
                        duration_ms=duration_ms,
                        request_id=req_id
                    )

                if response.status_code != 200:
                    logger.warning("LLM call failed: error_code=UPSTREAM_UNEXPECTED_STATUS, status=%d, model=%s, duration_ms=%.1f, request_id=%s", response.status_code, self.model, duration_ms, req_id)
                    raise LLMResponseError(
                        f"Phản hồi không mong đợi từ LLM Gateway (HTTP {response.status_code}).",
                        error_code="UPSTREAM_UNEXPECTED_STATUS",
                        status_code=response.status_code,
                        model=self.model,
                        duration_ms=duration_ms,
                        request_id=req_id
                    )

                # 3. Parse JSON an toan
                try:
                    data = response.json()
                except Exception as json_err:
                    logger.warning("LLM call failed: error_code=INVALID_RESPONSE_JSON, model=%s, duration_ms=%.1f, request_id=%s", self.model, duration_ms, req_id)
                    raise LLMResponseError(
                        "Phản hồi từ LLM Gateway không phải là JSON hợp lệ.",
                        error_code="INVALID_RESPONSE_JSON",
                        status_code=200,
                        model=self.model,
                        duration_ms=duration_ms,
                        request_id=req_id
                    ) from json_err

        except httpx.TimeoutException as te:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning("LLM call timeout: error_code=UPSTREAM_TIMEOUT, model=%s, duration_ms=%.1f", self.model, duration_ms)
            raise LLMTimeoutError(
                f"Quá thời gian chờ ({self.timeout_seconds}s) khi kết nối với LLM Gateway.",
                error_code="UPSTREAM_TIMEOUT",
                model=self.model,
                duration_ms=duration_ms
            ) from te
        except httpx.RequestError as re:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning("LLM call network error: error_code=NETWORK_ERROR, model=%s, duration_ms=%.1f", self.model, duration_ms)
            raise LLMNetworkError(
                "Lỗi mạng khi kết nối tới LLM Gateway.",
                error_code="NETWORK_ERROR",
                model=self.model,
                duration_ms=duration_ms
            ) from re

        # 4. Kiem tra cau truc choices[0].message.content
        if not isinstance(data, dict):
            raise LLMResponseError(
                "Dữ liệu phản hồi từ LLM Gateway không phải là JSON object.",
                error_code="MALFORMED_RESPONSE_STRUCTURE",
                status_code=200,
                model=self.model,
                duration_ms=duration_ms,
                request_id=req_id
            )

        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            raise LLMResponseError(
                "Phản hồi từ LLM Gateway thiếu danh sách choices hợp lệ.",
                error_code="MISSING_CHOICES",
                status_code=200,
                model=self.model,
                duration_ms=duration_ms,
                request_id=req_id
            )

        choice_obj = choices[0]
        if not isinstance(choice_obj, dict):
            raise LLMResponseError(
                "Phần tử choices[0] không phải là đối tượng hợp lệ.",
                error_code="MALFORMED_CHOICE",
                status_code=200,
                model=self.model,
                duration_ms=duration_ms,
                request_id=req_id
            )

        message_obj = choice_obj.get("message")
        if not isinstance(message_obj, dict):
            raise LLMResponseError(
                "Phần tử choices[0].message không phải là đối tượng hợp lệ.",
                error_code="MALFORMED_MESSAGE",
                status_code=200,
                model=self.model,
                duration_ms=duration_ms,
                request_id=req_id
            )

        content = message_obj.get("content")
        if content is None or not isinstance(content, str) or not content.strip():
            raise LLMResponseError(
                "Nội dung choices[0].message.content bị rỗng hoặc không phải chuỗi ký tự.",
                error_code="EMPTY_CONTENT",
                status_code=200,
                model=self.model,
                duration_ms=duration_ms,
                request_id=req_id
            )

        # 5. Trich xuat usage nghiem ngat: bat buoc du cap nguyen khong am
        usage = data.get("usage")
        prompt_tokens = 0
        completion_tokens = 0
        usage_valid = False

        if isinstance(usage, dict):
            p_tok = usage.get("prompt_tokens")
            c_tok = usage.get("completion_tokens")
            
            # Kiem tra ca hai truong phai la so nguyen khong am (int, not bool)
            is_p_valid = isinstance(p_tok, int) and not isinstance(p_tok, bool) and p_tok >= 0
            is_c_valid = isinstance(c_tok, int) and not isinstance(c_tok, bool) and c_tok >= 0

            if is_p_valid and is_c_valid:
                prompt_tokens = p_tok
                completion_tokens = c_tok
                usage_valid = True
            else:
                logger.warning(
                    "Usage tu LLM Gateway khong hop le hoac thieu truong: prompt_tokens=%s, completion_tokens=%s",
                    type(p_tok).__name__ if p_tok is not None else "None",
                    type(c_tok).__name__ if c_tok is not None else "None"
                )

        resp_model = data.get("model") or self.model

        logger.info(
            "LLM call success: model=%s, prompt_tokens=%d, completion_tokens=%d, usage_valid=%s, duration_ms=%.1f, request_id=%s",
            resp_model, prompt_tokens, completion_tokens, usage_valid, duration_ms, req_id
        )

        return CompletionResult(
            content=content.strip(),
            model=resp_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            usage_valid=usage_valid
        )

    def transcribe_audio(self, audio_path: Path, model: str = "cx/transcribe") -> str:
        if not self.api_key:
            raise LLMConfigError("Cần API Key để gửi audio tới 9Router.", error_code="API_KEY_NOT_CONFIGURED")
        if not model.strip():
            raise LLMConfigError("Thiếu model STT.", error_code="STT_MODEL_NOT_CONFIGURED")
        if not audio_path.is_file():
            raise LLMResponseError("Không tìm thấy tệp audio để nhận dạng.", error_code="AUDIO_FILE_NOT_FOUND")
        if not 0 < audio_path.stat().st_size <= 5 * 1024 * 1024:
            raise LLMResponseError("Tệp audio phải có kích thước từ 1 byte đến 5 MiB.", error_code="AUDIO_FILE_SIZE_INVALID")

        endpoint = f"{self.base_url}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        start_time = time.perf_counter()
        request_id = None
        try:
            with httpx.Client(transport=self.transport, timeout=max(self.timeout_seconds, 60.0)) as client:
                with audio_path.open("rb") as audio:
                    response = client.post(
                        endpoint,
                        headers=headers,
                        data={"model": model, "response_format": "json"},
                        files={"file": (audio_path.name, audio, "audio/mpeg")},
                    )
                request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                if response.status_code != 200:
                    error_code = "UPSTREAM_UNAUTHORIZED" if response.status_code == 401 else (
                        "UPSTREAM_RATE_LIMITED" if response.status_code == 429 else
                        "UPSTREAM_SERVER_ERROR" if response.status_code >= 500 else "UPSTREAM_UNEXPECTED_STATUS"
                    )
                    logger.warning(
                        "STT call failed: error_code=%s, status=%d, model=%s, duration_ms=%.1f, request_id=%s",
                        error_code, response.status_code, model, duration_ms, request_id,
                    )
                    raise LLMResponseError(
                        "Yêu cầu nhận dạng audio tới 9Router thất bại.", error_code=error_code,
                        status_code=response.status_code, model=model, duration_ms=duration_ms, request_id=request_id,
                    )
                try:
                    data = response.json()
                except Exception as exc:
                    raise LLMResponseError(
                        "Phản hồi nhận dạng audio không phải JSON hợp lệ.", error_code="INVALID_RESPONSE_JSON",
                        status_code=200, model=model, duration_ms=duration_ms, request_id=request_id,
                    ) from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                "Quá thời gian chờ khi nhận dạng audio qua 9Router.", error_code="UPSTREAM_TIMEOUT", model=model,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMNetworkError(
                "Lỗi mạng khi nhận dạng audio qua 9Router.", error_code="NETWORK_ERROR", model=model,
            ) from exc

        transcript = data.get("text") if isinstance(data, dict) else None
        if not isinstance(transcript, str) or not transcript.strip():
            raise LLMResponseError(
                "9Router không trả transcript hợp lệ.", error_code="EMPTY_TRANSCRIPTION",
                status_code=200, model=model, request_id=request_id,
            )
        logger.info(
            "STT call success: model=%s, response_chars=%d, duration_ms=%.1f, request_id=%s",
            model, len(transcript), duration_ms, request_id,
        )
        return transcript.strip()
