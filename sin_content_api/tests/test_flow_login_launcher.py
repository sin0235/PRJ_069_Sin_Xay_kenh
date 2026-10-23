from pathlib import Path
from types import SimpleNamespace

from src.modules.media_studio import router


def test_linux_flow_login_starts_session_manager(monkeypatch):
    calls = []
    monkeypatch.setattr(router.sys, "platform", "linux")
    monkeypatch.setattr(router, "_flow_login_session_running", lambda: False)
    monkeypatch.setattr(router.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = router.open_google_flow_login(SimpleNamespace(dev_auth_bypass=True))

    assert result["success"] is True
    args, kwargs = calls[0]
    assert args[0] == [router.sys.executable, str(router.FLOW_SESSION_MANAGER), "--background"]
    assert kwargs["cwd"] == router.FLOW_SESSION_MANAGER.parent
    assert Path(args[0][1]).is_file()


def test_linux_flow_login_reuses_existing_session(monkeypatch):
    monkeypatch.setattr(router.sys, "platform", "linux")
    monkeypatch.setattr(router, "_flow_login_session_running", lambda: True)
    monkeypatch.setattr(router.subprocess, "Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("duplicate launch")))

    result = router.open_google_flow_login(SimpleNamespace(dev_auth_bypass=True))

    assert result["success"] is True
    assert result["already_running"] is True
