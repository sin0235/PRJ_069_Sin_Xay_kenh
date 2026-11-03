from src import model_runtime


def test_remote_mode_reports_ready_without_local_model(monkeypatch, tmp_path):
    monkeypatch.setenv("PRJ069_VIENU_HF_HOME", str(tmp_path))
    monkeypatch.setenv("REMOTE_COMPUTE_MODE", "github")
    monkeypatch.delenv("REMOTE_ENGINE_CHILD", raising=False)
    assert model_runtime.model_status()["state"] == "READY"
    assert model_runtime.model_status()["mode"] == "REMOTE_GITHUB"


def test_runner_on_actions_still_requires_local_model(monkeypatch, tmp_path):
    monkeypatch.setenv("PRJ069_VIENU_HF_HOME", str(tmp_path))
    monkeypatch.setenv("REMOTE_COMPUTE_MODE", "github")
    monkeypatch.setenv("REMOTE_ENGINE_CHILD", "1")
    assert model_runtime.model_status()["state"] == "NOT_READY"


def test_hash_verification_never_shortcuts(monkeypatch, tmp_path):
    monkeypatch.setenv("PRJ069_VIENU_HF_HOME", str(tmp_path))
    monkeypatch.setenv("REMOTE_COMPUTE_MODE", "github")
    monkeypatch.delenv("REMOTE_ENGINE_CHILD", raising=False)
    assert model_runtime.model_status(verify_hashes=True)["state"] == "NOT_READY"


def test_local_mode_without_model_is_not_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("PRJ069_VIENU_HF_HOME", str(tmp_path))
    monkeypatch.delenv("REMOTE_COMPUTE_MODE", raising=False)
    assert model_runtime.model_status()["state"] == "NOT_READY"
