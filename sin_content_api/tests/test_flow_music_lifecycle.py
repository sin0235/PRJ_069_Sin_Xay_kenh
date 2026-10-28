from pathlib import Path
from types import SimpleNamespace

import pytest

from src.modules.flow_sessions.context import profile_context


def _music_harness(monkeypatch, tmp_path, quota_stage=None, status=429, body="quota exceeded"):
    import flow_music_client as music

    class Response:
        def __init__(self, stage, data):
            self.status = status if quota_stage == stage else 200
            self.data = data

        def json(self):
            return self.data

        def text(self):
            return body if self.status != 200 else ""

        def body(self):
            return b"audio" * 15000

    class API:
        def post(self, url, **_kwargs):
            return Response("project", {"id": "project"}) if url.endswith("/projects") else Response("conversation", {"job_id": "job"})

        def get(self, url, **_kwargs):
            return Response("download", {}) if "/download/" in url else Response("poll", {"clip_ids": ["clip"]})

        def dispose(self):
            pass

    class Page:
        def on(self, _event, callback):
            self.callback = callback

        def goto(self, *_args, **_kwargs):
            self.callback(SimpleNamespace(url="https://www.flowmusic.app/__api/me", headers={"authorization": "Bearer private-unit-token"}))

        def wait_for_timeout(self, _timeout):
            pass

    class Context:
        def new_page(self):
            return Page()

        def close(self):
            pass

    class PlaywrightManager:
        def __enter__(self):
            return SimpleNamespace(
                chromium=SimpleNamespace(launch_persistent_context=lambda **_kwargs: Context()),
                request=SimpleNamespace(new_context=lambda: API()),
            )

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(music, "sync_playwright", PlaywrightManager)
    monkeypatch.setattr(music, "MEDIA_ASSETS_DIR", tmp_path / "assets")
    monkeypatch.setattr(music.time, "sleep", lambda _seconds: None)
    return music


@pytest.mark.parametrize("stage,submitted", [("project", False), ("conversation", True), ("poll", True), ("download", True)])
@pytest.mark.parametrize("status,body", [(429, "limited"), (403, "insufficient credits")])
def test_music_quota_keeps_typed_submission_boundary(monkeypatch, tmp_path, stage, submitted, status, body):
    music = _music_harness(monkeypatch, tmp_path, stage, status, body)
    from session_manager import FlowQuotaExceeded  # on sys.path once the music client is imported

    with profile_context("workspace", "profile", profile_root=tmp_path), pytest.raises(FlowQuotaExceeded) as error:
        music.FlowMusicClient().create_track("prompt", workspace_id="workspace")
    assert error.value.error_code == "FLOW_QUOTA_LIMITED"
    assert error.value.submitted is submitted


def test_music_ffmpeg_has_bounded_process_and_threads(monkeypatch, tmp_path):
    music = _music_harness(monkeypatch, tmp_path)
    observed = []

    def run(command, **kwargs):
        observed.append((command, kwargs))
        Path(command[-1]).write_bytes(b"mp3" * 20000)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(music.subprocess, "run", run)
    monkeypatch.setattr(music.subprocess, "check_output", lambda *_args, **_kwargs: b"60")
    with profile_context("workspace", "profile", profile_root=tmp_path):
        result = music.FlowMusicClient().create_track("prompt", workspace_id="workspace")
    assert result["status"] == "SUCCEEDED"
    command, options = observed[0]
    assert options["timeout"] <= 600
    assert command[command.index("-threads") + 1] == "2"


def test_music_provider_error_does_not_expose_response_secrets(monkeypatch, tmp_path):
    music = _music_harness(monkeypatch, tmp_path, "project", 500, "private-provider-secret")
    with profile_context("workspace", "profile", profile_root=tmp_path), pytest.raises(RuntimeError) as error:
        music.FlowMusicClient().create_track("prompt", workspace_id="workspace")
    assert "private-provider-secret" not in str(error.value)
