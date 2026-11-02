from types import SimpleNamespace

from fastapi import HTTPException, Request
import pytest

from src.auth import tenancy
from src.auth.platform_auth import require_platform_owner
from src.config import settings


def _request(host: str, origin: str | None = None) -> Request:
    headers = [(b"origin", origin.encode())] if origin else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "client": (host, 1234), "server": (host, 8000), "scheme": "http", "query_string": b""})


def test_dev_auth_bypass_skips_identity_membership_and_policy(monkeypatch):
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    monkeypatch.setattr(settings, "app_env", "offline")
    monkeypatch.setattr(tenancy, "_canonical_auth_modules", lambda: pytest.fail("auth store must not load"))
    ctx_generator = tenancy.get_current_tenant_context(
        _request("127.0.0.1"), authorization=None, x_workspace_id=None, content_db=None
    )
    ctx = next(ctx_generator)
    try:
        assert ctx.dev_auth_bypass
        assert ctx.workspace_id == "default_ws"
        assert ctx.user_id == "dev-user"
        tenancy.authorize_action(ctx, "unregistered.test.action")
        assert require_platform_owner(_request("127.0.0.1"), authorization=None) == "dev-user"
    finally:
        ctx_generator.close()


def test_dev_auth_bypass_still_requires_resolved_resource_attribution(monkeypatch):
    monkeypatch.setattr(tenancy, "_canonical_auth_modules", lambda: pytest.fail("auth store must not load"))
    ctx = tenancy.TenantContext(
        workspace_id="workspace-1",
        user_id="dev-user",
        actor=None,
        auth_db=None,
        request_id="request-1",
        dev_auth_bypass=True,
    )

    tenancy.authorize_resource(
        ctx,
        "media.approve",
        resource_type="content_video_plan",
        resource_id="plan-1",
        workspace_id="workspace-1",
        creator_id="creator-1",
        require_creator=True,
    )
    with pytest.raises(Exception) as denied:
        tenancy.authorize_resource(
            ctx,
            "media.approve",
            resource_type="content_video_plan",
            resource_id="plan-1",
            workspace_id="other-workspace",
            require_creator=True,
        )
    assert getattr(denied.value, "status_code", None) == 403


@pytest.mark.parametrize(
    ("app_env", "host", "origin"),
    [("production", "127.0.0.1", None), ("offline", "192.0.2.10", None), ("offline", "127.0.0.1", "https://evil.example")],
)
def test_dev_auth_bypass_is_disabled_outside_local_development(monkeypatch, app_env, host, origin):
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    monkeypatch.setattr(settings, "app_env", app_env)
    assert not tenancy.dev_auth_bypass_enabled(_request(host, origin))


def test_dev_auth_bypass_requires_explicit_flag(monkeypatch):
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    monkeypatch.setattr(settings, "app_env", "offline")
    assert not tenancy.dev_auth_bypass_enabled(_request("127.0.0.1"))


def test_membership_store_failure_logs_original_exception_without_leaking_token(monkeypatch, caplog):
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)

    def broken_auth_db():
        def fail_on_connect():
            raise RuntimeError("auth database unavailable")
            yield
        return fail_on_connect()

    monkeypatch.setattr(tenancy, "_canonical_auth_modules", lambda: {
        "secret": "unused",
        "issuer": "test",
        "audience": "test",
        "set_tenant_context": lambda *args: None,
        "clear_tenant_context": lambda *args: None,
        "verify_bearer_token": lambda *args, **kwargs: SimpleNamespace(
            user_id="user-current", workspace_id="ws-current"
        ),
        "get_auth_db": broken_auth_db,
    })

    with caplog.at_level("ERROR", logger="src.auth.tenancy"):
        with pytest.raises(HTTPException) as error:
            next(tenancy.get_current_tenant_context(
                _request("192.0.2.10"),
                authorization="Bearer secret-test-token",
                x_workspace_id="ws-current",
                content_db=object(),
            ))

    assert error.value.status_code == 503
    assert "auth database unavailable" in caplog.text
    assert "secret-test-token" not in caplog.text
