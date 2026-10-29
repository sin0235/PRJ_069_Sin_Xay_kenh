from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.modules.media_studio import router


def _workspace_owner_tenant():
    workspace_id = "ws-flow-login-owner"
    user_id = "user-flow-login-owner"
    owner_role = {
        "role_code": "WORKSPACE_OWNER",
        "scope_type": "WORKSPACE",
        "scope_id": workspace_id,
        "assignment_status": "ACTIVE",
        "role_status": "ACTIVE",
        "is_active": True,
    }
    actor = SimpleNamespace(
        user_id=user_id,
        workspace_id=workspace_id,
        membership_status="ACTIVE",
        user_status="ACTIVE",
        workspace_status="ACTIVE",
        roles=[owner_role],
    )
    return SimpleNamespace(
        user_id=user_id,
        workspace_id=workspace_id,
        actor=actor,
        auth_db=object(),
        dev_auth_bypass=False,
    )


def test_linux_flow_login_starts_session_manager(monkeypatch):
    calls = []
    monkeypatch.setattr(router.sys, "platform", "linux")
    monkeypatch.setattr(router, "_flow_login_session_running", lambda: False)
    monkeypatch.setattr(router.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = router.open_google_flow_login(_workspace_owner_tenant())

    assert result["success"] is True
    args, kwargs = calls[0]
    assert args[0] == [router.sys.executable, str(router.FLOW_SESSION_MANAGER), "--background"]
    assert kwargs["cwd"] == router.FLOW_SESSION_MANAGER.parent
    assert Path(args[0][1]).is_file()


def test_linux_flow_login_reuses_existing_session(monkeypatch):
    monkeypatch.setattr(router.sys, "platform", "linux")
    monkeypatch.setattr(router, "_flow_login_session_running", lambda: True)
    monkeypatch.setattr(router.subprocess, "Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("duplicate launch")))

    result = router.open_google_flow_login(_workspace_owner_tenant())

    assert result["success"] is True
    assert result["already_running"] is True


def test_flow_login_rejects_missing_or_non_owner_actor(monkeypatch):
    monkeypatch.setattr(router.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("unauthorized actor must not launch Flow"))

    with pytest.raises(HTTPException) as missing_actor:
        router.open_google_flow_login(SimpleNamespace(dev_auth_bypass=True))
    assert missing_actor.value.status_code == 403

    tenant = _workspace_owner_tenant()
    tenant.actor.roles = [{
        "role_code": "WORKSPACE_EDITOR",
        "scope_type": "WORKSPACE",
        "scope_id": tenant.workspace_id,
        "assignment_status": "ACTIVE",
        "role_status": "ACTIVE",
        "is_active": True,
    }]
    with pytest.raises(HTTPException) as non_owner:
        router.open_google_flow_login(tenant)
    assert non_owner.value.status_code == 403
