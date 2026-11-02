import math
import struct
import wave

import pytest

from src.modules.dieu_phoi_dung.phat_hien_khoang_nghi import (
    hop_nhat_khoang_nghi,
    phat_hien_khoang_nghi,
    tinh_muc_song,
)


def tao_wav(path, segments, sample_rate=16000):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        for duration_ms, amplitude in segments:
            count = round(sample_rate * duration_ms / 1000)
            samples = [round(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(count)]
            output.writeframes(struct.pack(f"<{count}h", *samples))


def test_phat_hien_khoang_nghi_nguong_1200ms(tmp_path):
    audio = tmp_path / "nghi.wav"
    tao_wav(audio, [(500, 4000), (1199, 0), (500, 4000), (1200, 0), (500, 4000)])

    intervals = phat_hien_khoang_nghi(audio)

    assert len(intervals) == 1
    assert intervals[0][1] - intervals[0][0] >= 1200
    assert 2190 <= intervals[0][0] <= 2210


def test_hop_nhat_gap_asr_va_silence_khong_cat_trung():
    words = [
        {"text": "một", "start_ms": 100, "end_ms": 300},
        {"text": "hai", "start_ms": 1800, "end_ms": 2000},
        {"text": "ba", "start_ms": 4000, "end_ms": 4200},
    ]

    assert hop_nhat_khoang_nghi(words, [(500, 1600), (1800, 3000)], 5000) == [(300, 4000)]


def test_tinh_muc_song_tao_peak_moi_100ms(tmp_path):
    audio = tmp_path / "song.wav"
    tao_wav(audio, [(250, 1000), (250, 16000)])

    peaks = tinh_muc_song(audio)

    assert len(peaks) == 5
    assert all(0 <= peak <= 100 for peak in peaks)
    assert peaks[0] < peaks[3]


def test_phat_hien_khoang_nghi_bao_loi_khi_ffmpeg_that_bai(tmp_path, monkeypatch):
    from src.modules.dieu_phoi_dung import phat_hien_khoang_nghi as module

    audio = tmp_path / "audio.wav"
    tao_wav(audio, [(1500, 0)])
    monkeypatch.setattr(module, "run_media_command", lambda *_args, **_kwargs: type("Result", (), {"returncode": 1, "stderr": "bad audio"})())
    with pytest.raises(ValueError, match="SILENCE_DETECTION_FAILED"):
        module.phat_hien_khoang_nghi(audio)
