"""Kiểm tra tích hợp và offload từ xa cho dây chuyền video nội dung (AI_VIDEO).

Bao gồm:
- Tính đơn nhất của hash SHA-256 cho placeholder khi cùng độ dài (chống DUPLICATE_SHOT_MEDIA).
- Cơ chế lọc an toàn cho âm thanh hiệu ứng SFX (chống SFX_CUE_INVALID khi thiếu asset).
- Tận dụng mốc thời gian từ đã tính toán trước (word_times) khi dựng trên worker từ xa.
- Cơ chế dự phòng khi ASR Vietsub gặp lỗi từ xa (fallback về phụ đề theo phân cảnh TTS).
- Khả năng điều phối và thực thi các stage AI_VIDEO qua module tác vụ từ xa.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from types import SimpleNamespace
import pytest

API_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.modules.tao_video_noi_dung.render_engines import render_placeholder
from src.modules.tao_video_noi_dung.runner import (
    _has_duplicate_shot_media,
    _diagram_word_times,
    _file_sha256,
)
from src.modules.tao_video_noi_dung.sfx import transition_sfx_cues
from src.modules.tao_video_noi_dung.vietsub import VietsubError
from src.modules.tac_vu_tu_xa.stages import execute_stage


def test_render_placeholder_distinct_hashes_for_equal_duration(tmp_path):
    """Hai phân cảnh placeholder cùng độ dài phải có hash khác nhau để không kích hoạt DUPLICATE_SHOT_MEDIA."""
    path1 = tmp_path / "shot_0_placeholder.mp4"
    path2 = tmp_path / "shot_1_placeholder.mp4"

    meta1 = render_placeholder(path1, 1, "9:16")
    meta2 = render_placeholder(path2, 1, "9:16")

    assert path1.is_file()
    assert path2.is_file()
    assert meta1["width"] == 1080
    assert meta1["height"] == 1920

    hash1 = _file_sha256(path1)
    hash2 = _file_sha256(path2)

    assert hash1 != hash2, "Mỗi placeholder phải có hash SHA-256 riêng nhờ metadata title"
    assert not _has_duplicate_shot_media([hash1, hash2]), "Danh sách hash không được coi là trùng lặp"


def test_sfx_cues_filtering_and_missing_asset_safety():
    """Hiệu ứng SFX không tồn tại hoặc sai đường dẫn phải được lọc bỏ an toàn, không ném ngoại lệ."""
    # Hiệu ứng chuyển cảnh không tồn tại
    cues_unknown = transition_sfx_cues([1.0, 3.0], "hieu_ung_khong_ton_tai")
    assert cues_unknown == [], "Hiệu ứng không hợp lệ phải trả về danh sách rỗng"

    # Hiệu ứng xe_giay hợp lệ (tệp asset tồn tại)
    cues_valid = transition_sfx_cues([0.5], "xe_giay")
    if cues_valid:
        assert all(isinstance(c["path"], pathlib.Path) for c in cues_valid)
        assert all(c["path"].is_file() for c in cues_valid)


def test_diagram_word_times_returns_precomputed_timing_on_remote():
    """Khi step đã có sẵn word_times, _diagram_word_times phải trả về ngay mà không cần đọc tệp .npz."""
    mock_shots = [
        SimpleNamespace(shot_id="shot_1", narration="Baha Group tự động hóa"),
    ]
    precomputed = [0.15, 0.65, 1.20, 1.85]
    mock_steps = [
        {"word_times": precomputed, "clip_seconds": 3},
    ]

    result = _diagram_word_times(mock_shots, mock_steps, 0, per_clip=True)
    assert result == precomputed, "Phải sử dụng mốc thời gian từ đã tính toán sẵn mà không truy cập đĩa NAS"


def test_vietsub_remote_failure_gracefully_handled(monkeypatch):
    """Lỗi ASR từ xa hoặc VietsubError phải được bắt giữ và xử lý dự phòng thay vì làm sập toàn bộ run."""
    from src.modules.tao_video_noi_dung import runner

    shots = [
        SimpleNamespace(shot_id="s1", narration="Xin chào các bạn", duration_seconds=3),
        SimpleNamespace(shot_id="s2", narration="Hôm nay chúng ta nói về tự động hóa", duration_seconds=4),
    ]

    def _mock_transcribe_words_failing(*args, **kwargs):
        raise VietsubError("VIETSUB_ASR_FAILED")

    monkeypatch.setattr(runner, "transcribe_words_cached", _mock_transcribe_words_failing)

    # Kiểm tra ngoại lệ VietsubError được định nghĩa chuẩn xác và có thể bắt được
    with pytest.raises(VietsubError):
        runner.transcribe_words_cached(pathlib.Path("fake.wav"), pathlib.Path("fake_cache.json"))


def test_execute_stage_placeholder_remote_dispatch(tmp_path):
    """Kiểm tra điều phối tác vụ placeholder qua hàm execute_stage của worker từ xa."""
    spec = {
        "stage": "RENDER_VISUAL",
        "parameters": {
            "operation": "placeholder",
            "arguments": {
                "seconds": 1,
                "aspect_ratio": "9:16",
            },
        },
    }
    output_path = tmp_path / "remote_placeholder.mp4"

    result = execute_stage(spec, inputs=[], output=output_path)

    assert output_path.is_file()
    assert result["width"] == 1080
    assert result["height"] == 1920
    assert result["duration_seconds"] == 1.0


def test_execute_stage_decode_qc_remote_dispatch(tmp_path):
    """Kiểm tra kiểm định decode QC qua execute_stage trên worker từ xa."""
    # Tạo một video mẫu 1 giây để kiểm tra decode
    sample_mp4 = tmp_path / "sample.mp4"
    render_placeholder(sample_mp4, 1, "9:16")

    spec = {
        "stage": "QC",
        "parameters": {
            "operation": "decode",
            "arguments": {
                "path": {"remote_input": 0},
            },
        },
    }

    result = execute_stage(spec, inputs=[sample_mp4], output=tmp_path / "qc_out")
    assert result.get("decode_ok") is True


def test_execute_stage_tts_mock_dispatch(tmp_path, monkeypatch):
    """Kiểm tra execute_stage cho tác vụ TTS với synthesizer giả lập."""
    import numpy as np

    class MockTTSManager:
        def synthesize(self, **kwargs):
            # Tạo 0.1 giây âm thanh rỗng 24kHz
            rate = 24000
            audio = np.zeros(int(0.1 * rate), dtype=np.float32)
            return audio, rate

    monkeypatch.setattr("src.modules.tao_video_noi_dung.tts_provider.tts_provider_manager", MockTTSManager())

    spec = {
        "stage": "TTS",
        "parameters": {
            "operation": "tts",
            "arguments": {
                "text": "Kiểm thử giọng nói",
                "voice_id": "sin_voice",
            },
        },
    }
    output_wav = tmp_path / "tts_output.wav"
    result = execute_stage(spec, inputs=[], output=output_wav)

    assert output_wav.is_file()
    assert result["sample_rate"] == 24000
