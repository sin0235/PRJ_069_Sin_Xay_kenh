import json
from types import SimpleNamespace

import numpy as np
import pytest

from src.modules.tao_video_noi_dung import runner
from src.modules.tao_video_noi_dung.contracts import CreateRunRequest
from src.modules.tao_video_noi_dung.service import _tts_config
from src.modules.tao_video_noi_dung.tts_provider import TTSProviderManager


def test_clone_defaults_to_no_denoising_and_honors_explicit_override():
    calls = []
    model = SimpleNamespace(sample_rate=8000, infer=lambda text, **kw: calls.append(kw) or np.ones(800))
    TTSProviderManager._infer("VIE_NEU_V3_TURBO", model, {}, "Xin chào.", "ref.wav")
    assert calls[-1]["denoise"] is False
    assert calls[-1]["max_chars"] == 128
    TTSProviderManager._infer("VIE_NEU_V3_TURBO", model, {"advanced": {"denoise_reference": True}}, "Xin chào.", "ref.wav")
    assert calls[-1]["denoise"] is True


def test_flow_snapshots_no_denoising():
    request = CreateRunRequest(plan_id="plan", tts_provider="VIE_NEU_V3_TURBO", idempotency_key="tts-test-123")
    assert _tts_config(request)["advanced"]["denoise_reference"] is False


@pytest.mark.parametrize("edge_samples,expected_padding", [(0, 4000), (2400, 0)])
def test_shot_join_preserves_audio_and_resume_does_not_duplicate_pause(monkeypatch, tmp_path, edge_samples, expected_padding):
    # Hai mép 0,3s đã đủ nghỉ; hai mép không im lặng thì cần bù 0,5s.
    monkeypatch.setenv("CONTENT_VIDEO_TTS_MOT_LAN", "0")   # test của chế độ sinh từng shot
    first = np.concatenate([np.full(800, .1, dtype=np.float32), np.zeros(edge_samples, dtype=np.float32)])
    second = np.concatenate([np.zeros(edge_samples, dtype=np.float32), np.full(800, -.1, dtype=np.float32)])
    queue = iter([first, second])
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr(runner, "_tts_reference_path", lambda *a: None)
    monkeypatch.setattr(runner.tts_provider_manager, "synthesize", lambda *a: (next(queue), 8000))
    monkeypatch.setattr(runner, "_save_run", lambda db, run, steps: setattr(run, "steps_json", json.dumps(steps)))
    db = SimpleNamespace(commit=lambda: None)
    run = SimpleNamespace(id="run", workspace_id="ws", steps_json=json.dumps([{}, {}]))
    shots = [SimpleNamespace(shot_id="a", narration="Câu thứ nhất."), SimpleNamespace(shot_id="b", narration="Câu thứ hai.")]
    config = {"provider": "VIE_NEU_V3_TURBO"}
    audio, rate = runner._prepare_run_tts(db, run, shots, config, "token")
    np.testing.assert_array_equal(audio, np.concatenate([first, np.zeros(expected_padding), second]))
    steps = json.loads(run.steps_json)
    assert steps[0]["tts_audio"]["pause_after_ms"] == expected_padding / 8
    assert steps[1]["tts_audio"]["pause_after_ms"] == 0
    assert steps[0]["tts_audio"]["duration_ms"] == len(first) / 8
    assert rate == 8000
    # Lần sau chỉ dùng cache; iterator đã hết, synthesize lại sẽ làm test lỗi.
    repeated, _ = runner._prepare_run_tts(db, run, shots, config, "new-token")
    np.testing.assert_array_equal(repeated, audio)


def test_diagram_word_times_include_pause_between_shots(monkeypatch, tmp_path):
    import hashlib
    path = tmp_path / "shot.npz"
    np.savez(path, audio=np.ones(16000, dtype=np.float32) * .1, sample_rate=8000)
    steps = [
        {"tts_audio": {"duration_ms": 1000, "pause_after_ms": 500}},
        {"tts_audio": {"duration_ms": 2000, "pause_after_ms": 0,
                       "storage_key": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}},
    ]
    shots = [SimpleNamespace(duration_seconds=1.5), SimpleNamespace(duration_seconds=2, narration="Xin chào", shot_id="second")]
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr(runner, "transcribe_words_cached", lambda *a: [
        {"text": "Xin", "start_ms": 0, "end_ms": 400},
        {"text": "chào", "start_ms": 500, "end_ms": 900},
    ])
    assert runner._diagram_word_times(shots, steps, 1) == [0, .5]
