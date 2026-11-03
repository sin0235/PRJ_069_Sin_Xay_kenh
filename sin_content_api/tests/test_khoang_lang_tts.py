import numpy as np

from src.modules.tao_video_noi_dung.runner import _pause_pad_samples

RATE = 16000


def tone(seconds, silence_end=0.0, silence_start=0.0):
    body = np.full(int(seconds * RATE), 0.3, dtype=np.float32)
    return np.concatenate([np.zeros(int(silence_start * RATE), np.float32), body, np.zeros(int(silence_end * RATE), np.float32)])


def test_full_pause_is_added_between_loud_sentences():
    assert _pause_pad_samples(tone(1), tone(1), RATE, 0.5) == int(0.5 * RATE)


def test_existing_silence_counts_toward_the_pause():
    pad = _pause_pad_samples(tone(1, silence_end=0.2), tone(1, silence_start=0.1), RATE, 0.5)
    assert abs(pad - int(0.2 * RATE)) <= 2


def test_no_pause_requested_adds_nothing():
    assert _pause_pad_samples(tone(1), tone(1), RATE, 0.0) == 0


def test_long_natural_silence_needs_no_padding():
    assert _pause_pad_samples(tone(1, silence_end=0.8), tone(1), RATE, 0.5) == 0
