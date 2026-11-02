import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "src/modules/media_studio/audio_processor.py"
SPEC = importlib.util.spec_from_file_location("audio_processor_memory_test", MODULE_PATH)
AUDIO_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIO_MODULE)


def test_audio_qc_does_not_read_entire_media_file(tmp_path, monkeypatch):
    media = tmp_path / "video_lon.mp4"
    media.write_bytes(b"x" * 2048)
    monkeypatch.setattr(Path, "read_bytes", lambda *_: pytest.fail("không được đọc toàn bộ media vào RAM"))
    processor = AUDIO_MODULE.AudioProcessor()
    monkeypatch.setattr(processor, "probe_audio", lambda _: {
        "codec_name": "aac", "channels": 2, "duration_seconds": 1,
        "sample_rate_hz": 44100,
    })
    monkeypatch.setattr(processor, "measure_loudness", lambda _: {
        "measured_i_lufs": -14.0, "measured_tp_dbtp": -2.0, "measured_lra_lu": 3.0,
    })

    result = processor.verify_audio_qc(media)

    assert result["passed"]
    assert result["byte_size"] == 2048
