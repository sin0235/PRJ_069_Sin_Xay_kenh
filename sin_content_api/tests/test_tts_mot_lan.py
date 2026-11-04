"""Giọng sinh một lần cho cả bài, chia theo shot ở chỗ im (không cắt ngang chữ, không chỉnh âm)."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from src.modules.tao_video_noi_dung import runner

RATE = 24000


def _shots(*texts):
    return [SimpleNamespace(narration=text, shot_id=f"s{i + 1}") for i, text in enumerate(texts)]


def _giong_co_khoang_lang(do_dai_giay, cho_lang_giay):
    """Âm 220 Hz liền, chèn khoảng lặng 0,3 giây tại các mốc cho trước."""
    n = round(do_dai_giay * RATE)
    audio = (0.4 * np.sin(2 * np.pi * 220 * np.arange(n) / RATE)).astype(np.float32)
    for giay in cho_lang_giay:
        audio[round(giay * RATE): round((giay + 0.3) * RATE)] = 0
    return audio


def test_cat_dung_cho_im_gan_diem_ty_le():
    audio = _giong_co_khoang_lang(10, [3.4, 6.6])   # lời đều nhau nên điểm lý thuyết là 3,33 s và 6,67 s
    shots = _shots("a" * 30, "b" * 30, "c" * 30)
    lengths = runner._tach_giong_theo_shot(audio, RATE, shots)
    assert sum(lengths) == len(audio) and all(length > 0 for length in lengths)
    first_cut = lengths[0] / RATE
    second_cut = (lengths[0] + lengths[1]) / RATE
    assert 3.4 <= first_cut <= 3.7      # rơi vào khoảng lặng 3,4 đến 3,7
    assert 6.6 <= second_cut <= 6.9


def test_khong_co_cho_im_van_chia_hop_le():
    audio = _giong_co_khoang_lang(6, [])
    lengths = runner._tach_giong_theo_shot(audio, RATE, _shots("x" * 20, "y" * 40))
    assert sum(lengths) == len(audio) and min(lengths) >= round(0.5 * RATE)


def test_mot_shot_duy_nhat_nhan_tron_ban_giong():
    audio = _giong_co_khoang_lang(4, [])
    assert runner._tach_giong_theo_shot(audio, RATE, _shots("chỉ một shot")) == [len(audio)]


def test_mac_dinh_goi_che_do_mot_lan(monkeypatch):
    goi = {}
    monkeypatch.setattr(runner, "_prepare_run_tts_mot_lan", lambda *a: goi.setdefault("mot_lan", True) or ("m", 1))
    monkeypatch.delenv("CONTENT_VIDEO_TTS_MOT_LAN", raising=False)
    runner._prepare_run_tts(None, None, [], {}, "tok")
    assert goi == {"mot_lan": True}


def test_mốc_từ_cắt_đúng_đoạn_của_shot_khi_giọng_sinh_một_lần(monkeypatch, tmp_path):
    """Mỗi shot nhận đúng đoạn của mình từ bản giọng liền, không KeyError storage_key như trước."""
    import hashlib
    import wave

    audio = _giong_co_khoang_lang(6, [])
    path = tmp_path / "workspaces" / "w" / "media" / ".tts" / "mot_lan.npz"
    path.parent.mkdir(parents=True)
    np.savez(path, audio=audio, sample_rate=RATE)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    steps = [
        {"tts_audio": {"storage_key": "workspaces/w/media/.tts/mot_lan.npz", "sha256": sha, "duration_ms": 2000, "pause_after_ms": 0, "mot_lan": True}},
        {"tts_audio": {"duration_ms": 1000, "pause_after_ms": 0, "mot_lan": True}},
        {"tts_audio": {"duration_ms": 3000, "pause_after_ms": 0, "mot_lan": True}},
    ]
    shots = [SimpleNamespace(narration="một hai", shot_id="s1", duration_seconds=2),
             SimpleNamespace(narration="ba bốn", shot_id="s2", duration_seconds=1),
             SimpleNamespace(narration="năm sáu", shot_id="s3", duration_seconds=3)]
    seen = []

    def gia_asr(wav_path, cache):
        with wave.open(str(wav_path)) as wav:
            seen.append(wav.getnframes() / wav.getframerate())
        return [{"text": "x", "start_ms": 100, "end_ms": 200}]

    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr(runner, "transcribe_words_cached", gia_asr)
    monkeypatch.setattr(runner, "align_script_words", lambda words, asr: [{"start_ms": 100 * (i + 1)} for i, _ in enumerate(words)])
    for index in range(3):
        assert runner._diagram_word_times(shots, steps, index, per_clip=True) is not None
    assert [round(x, 2) for x in seen] == [2.0, 1.0, 3.0]
