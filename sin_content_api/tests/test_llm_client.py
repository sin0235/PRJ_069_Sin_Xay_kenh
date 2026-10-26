# Test kiem thu cho Gate 2: Client OpenAI-compatible dung httpx
import json
import pytest
import httpx
from pathlib import Path

from src.config import Settings
from src.modules.llm.client import (
    LLMClient,
    CompletionResult,
    LLMClientError,
    LLMConfigError,
    LLMTimeoutError,
    LLMNetworkError,
    LLMResponseError
)

def make_settings(
    model="test-model",
    api_key="sk-test-secret-key-12345",
    base_url="http://127.0.0.1:20128/v1",
    timeout=5.0,
    max_input_bytes=1000,
    max_output_tokens=500
):
    return Settings(
        llm_model=model,
        llm_api_key=api_key,
        llm_base_url=base_url,
        llm_timeout_seconds=timeout,
        llm_max_input_bytes=max_input_bytes,
        llm_max_output_tokens=max_output_tokens,
        llm_api_key_file=Path(__file__).with_name("khong_co_khoa_router.env"),
        _env_file=None
    )

def test_gate2_successful_request():
    """Gate 2: Request thanh cong tra ve CompletionResult day du."""
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["headers"] = dict(request.headers)
        captured_request["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test-123",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "test-model-v1",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Xin chao! Day la y tuong TikTok."
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 42,
                    "completion_tokens": 18,
                    "total_tokens": 60
                }
            },
            headers={"x-request-id": "req-abc-001"}
        )

    transport = httpx.MockTransport(handler)
    client = LLMClient(settings=make_settings(), transport=transport)

    res = client.complete([{"role": "user", "content": "Gợi ý kịch bản"}], max_tokens=200)

    assert isinstance(res, CompletionResult)
    assert res.content == "Xin chao! Day la y tuong TikTok."
    assert res.model == "test-model-v1"
    assert res.prompt_tokens == 42
    assert res.completion_tokens == 18

    # Kiem tra URL va Headers da gui
    assert captured_request["url"] == "http://127.0.0.1:20128/v1/chat/completions"
    assert captured_request["headers"]["authorization"] == "Bearer sk-test-secret-key-12345"
    assert captured_request["body"]["max_tokens"] == 200
    assert captured_request["body"]["stream"] is False

def test_gate2_bearer_header_presence():
    """Gate 2: Header Bearer duoc dinh kem khi co api_key."""
    auth_header_sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        auth_header_sent.append(request.headers.get("authorization"))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5}
            }
        )

    client = LLMClient(
        settings=make_settings(api_key="secret-token-xyz"),
        transport=httpx.MockTransport(handler)
    )
    client.complete([{"role": "user", "content": "test"}])
    assert auth_header_sent == ["Bearer secret-token-xyz"]

def test_gate2_timeout_handling():
    """Gate 2: Timeout nem LLMTimeoutError khong tu retry."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.ReadTimeout("Connection read timed out")

    client = LLMClient(
        settings=make_settings(timeout=1.0),
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(LLMTimeoutError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])
    
    assert exc_info.value.error_code == "UPSTREAM_TIMEOUT"
    assert call_count == 1 # Tuyet doi khong auto-retry

def test_gate2_http_401_unauthorized():
    """Gate 2: Loi 401 tu upstream duoc chuan hoa thanh LLMResponseError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized: Invalid API key")

    client = LLMClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])
    
    assert exc_info.value.error_code == "UPSTREAM_UNAUTHORIZED"
    assert exc_info.value.status_code == 401
    assert "sk-test-secret-key-12345" not in str(exc_info.value)

def test_gate2_http_429_rate_limited():
    """Gate 2: Loi 429 tu upstream duoc chuan hoa thanh LLMResponseError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit exceeded")

    client = LLMClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])
    
    assert exc_info.value.error_code == "UPSTREAM_RATE_LIMITED"
    assert exc_info.value.status_code == 429

def test_gate2_http_5xx_server_error():
    """Gate 2: Loi 5xx tu upstream duoc chuan hoa thanh LLMResponseError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="Bad Gateway")

    client = LLMClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])
    
    assert exc_info.value.error_code == "UPSTREAM_SERVER_ERROR"
    assert exc_info.value.status_code == 502


def test_gate2_maps_gateway_503_with_embedded_429_to_rate_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {"message": "[cx/gpt-6-luna] [429]: The usage limit has been reached (reset after 2m)"}})

    client = LLMClient(settings=make_settings(), transport=httpx.MockTransport(handler))

    with pytest.raises(LLMResponseError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])

    assert exc_info.value.error_code == "UPSTREAM_RATE_LIMITED"
    assert exc_info.value.status_code == 429
    assert "2m" not in str(exc_info.value)

def test_gate2_invalid_json_response():
    """Gate 2: Phản hồi không phải JSON được bắt an toàn."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<HTML>502 Bad Gateway</HTML>", headers={"content-type": "text/html"})

    client = LLMClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])
    
    assert exc_info.value.error_code == "INVALID_RESPONSE_JSON"

def test_gate2_empty_or_missing_content():
    """Gate 2: content rỗng hoặc thiếu bị từ chối an toàn."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})

    client = LLMClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])
    
    assert exc_info.value.error_code == "EMPTY_CONTENT"

def test_gate2_missing_usage_defaults_zero():
    """Gate 2: usage thiếu hoặc rỗng mặc định prompt_tokens=0, completion_tokens=0."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "Nội dung hợp lệ"}}]})

    client = LLMClient(
        settings=make_settings(),
        transport=httpx.MockTransport(handler)
    )

    res = client.complete([{"role": "user", "content": "hello"}])
    assert res.content == "Nội dung hợp lệ"
    assert res.prompt_tokens == 0
    assert res.completion_tokens == 0

def test_gate2_input_bytes_exceeded():
    """Gate 2: Prompt vượt quá max_input_bytes bị chặn trước khi gọi mạng."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    client = LLMClient(
        settings=make_settings(max_input_bytes=20),
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(LLMResponseError) as exc_info:
        client.complete([{"role": "user", "content": "Đây là một câu rất dài chắc chắn vượt quá hai mươi byte UTF-8"}])
    
    assert exc_info.value.error_code == "INPUT_TOO_LARGE"
    assert called is False # Chặn trước mạng

def test_gate2_missing_model_config():
    """Gate 2: Thiếu LLM_MODEL gây ra LLMConfigError an toàn."""
    client = LLMClient(settings=make_settings(model=""))
    with pytest.raises(LLMConfigError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])
    assert exc_info.value.error_code == "MODEL_NOT_CONFIGURED"

def test_gate2_missing_api_key_config():
    """Gate 2 & Vấn đề 4: Thiếu LLM_API_KEY gây ra LLMConfigError an toàn."""
    client = LLMClient(settings=make_settings(api_key=""))
    with pytest.raises(LLMConfigError) as exc_info:
        client.complete([{"role": "user", "content": "hello"}])
    assert exc_info.value.error_code == "API_KEY_NOT_CONFIGURED"

def test_gate2_incomplete_or_invalid_usage_rejected():
    """Gate 2 & Vấn đề 2: Usage thiếu 1 trường hoặc số thập phân/bool bị từ chối; không tính thiếu phí."""
    # 1. Thiếu completion_tokens
    def handler_partial(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 500}
        })
    client1 = LLMClient(settings=make_settings(), transport=httpx.MockTransport(handler_partial))
    res1 = client1.complete([{"role": "user", "content": "hi"}])
    assert res1.usage_valid is False
    assert res1.prompt_tokens == 0
    assert res1.completion_tokens == 0

    # 2. Token dạng float (12.8)
    def handler_float(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 12.8, "completion_tokens": 20}
        })
    client2 = LLMClient(settings=make_settings(), transport=httpx.MockTransport(handler_float))
    res2 = client2.complete([{"role": "user", "content": "hi"}])
    assert res2.usage_valid is False
    assert res2.prompt_tokens == 0

    # 3. Token dạng boolean (True/False)
    def handler_bool(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": True, "completion_tokens": 20}
        })
    client3 = LLMClient(settings=make_settings(), transport=httpx.MockTransport(handler_bool))
    res3 = client3.complete([{"role": "user", "content": "hi"}])
    assert res3.usage_valid is False
    assert res3.prompt_tokens == 0

