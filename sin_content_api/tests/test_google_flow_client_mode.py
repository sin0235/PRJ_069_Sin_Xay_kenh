import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cong_cu_tu_dong" / "flow_bridge"))

from google_flow_client import _new_flow_video_tile_index


def test_only_a_new_flow_tile_is_selected():
    existing = ["thumb-a", "thumb-b"]
    assert _new_flow_video_tile_index(existing, ["thumb-a", "thumb-b"]) is None
    assert _new_flow_video_tile_index(existing, ["thumb-a", "thumb-b", "thumb-c"]) == 2


def _client_with_attempts(monkeypatch, outcomes):
    import google_flow_client
    from contextlib import nullcontext

    monkeypatch.setattr("profile_guard.profile_lock", lambda path: nullcontext())
    client = google_flow_client.GoogleFlowClient(headless=True)
    calls = []

    def once(*args, **kwargs):
        calls.append(1)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(client, "_create_video_once", once)
    return client, calls


def test_create_video_retries_once_when_flow_never_received_the_request(monkeypatch):
    from session_manager import FlowSubmissionNotSent
    client, calls = _client_with_attempts(monkeypatch, [FlowSubmissionNotSent("FLOW_SUBMIT_NOT_SENT: x"), {"storage_path": "ok.mp4"}])
    assert client.create_video("prompt") == {"storage_path": "ok.mp4"} and len(calls) == 2


def test_create_video_does_not_retry_when_submission_is_uncertain(monkeypatch):
    import pytest
    client, calls = _client_with_attempts(monkeypatch, [RuntimeError("FLOW_DOWNLOAD_TIMEOUT"), {"storage_path": "ok.mp4"}])
    with pytest.raises(RuntimeError, match="FLOW_DOWNLOAD_TIMEOUT"):
        client.create_video("prompt")
    assert len(calls) == 1
