"""Chỉnh giọng TTS: giữ độ dài, tăng độ rõ dải 3 đến 6 kHz, không chạm trần, lỗi thì trả giọng gốc."""
import numpy as np

from src.modules.tao_video_noi_dung import am_thanh_giong

RATE = 24000


def _giong_nghet(seconds: float = 4.0) -> np.ndarray:
    """Tiếng giống giọng nghẹt: nhiều năng lượng thấp, rất ít trên 3 kHz, có quãng nghỉ."""
    rng = np.random.default_rng(7)
    n = int(RATE * seconds)
    noise = rng.standard_normal(n)
    spectrum = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    spectrum *= 1 / (1 + (freqs / 600.0) ** 2)   # giảm dần theo tần số, gần như hết sau 3 kHz
    voice = np.fft.irfft(spectrum, n)
    voice *= np.where((np.arange(n) // (RATE // 2)) % 4 == 3, 0.0, 1.0)   # quãng nghỉ mỗi 2 giây
    return (voice / np.abs(voice).max() * 0.35).astype(np.float32)


def _dai_ty_le(x: np.ndarray, lo: float, hi: float) -> float:
    spectrum = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / RATE)
    return float(10 * np.log10(spectrum[(freqs >= lo) & (freqs < hi)].sum() / spectrum.sum() + 1e-12))


def test_giu_nguyen_do_dai_va_kieu():
    audio = _giong_nghet()
    out = am_thanh_giong.polish_voice(audio, RATE)
    assert out.dtype == np.float32 and out.shape == audio.shape and np.isfinite(out).all()


def test_tang_do_ro_dai_3_den_6k_va_khong_cham_tran():
    audio = _giong_nghet()
    out = am_thanh_giong.polish_voice(audio, RATE)
    assert _dai_ty_le(out, 1500, 6000) > _dai_ty_le(audio, 1500, 6000) + 4.0
    assert float(np.abs(out).max()) <= 0.95


def test_dua_am_luong_len_gan_muc_phat():
    audio = _giong_nghet() * 0.2
    out = am_thanh_giong.polish_voice(audio, RATE)
    assert np.sqrt(np.mean(out ** 2)) > np.sqrt(np.mean(audio ** 2))


def test_tat_bang_bien_moi_truong(monkeypatch):
    monkeypatch.setenv("CONTENT_VIDEO_VOICE_POLISH", "0")
    audio = _giong_nghet()
    assert np.array_equal(am_thanh_giong.polish_voice(audio, RATE), audio)


def test_ffmpeg_loi_tra_giong_goc():
    audio = _giong_nghet()
    out = am_thanh_giong.polish_voice(audio, RATE, ffmpeg_bin="khong-co-ffmpeg-nay")
    assert np.array_equal(out, audio)


def test_ngu_im_va_mang_rong():
    assert am_thanh_giong.polish_voice(np.zeros(0, dtype=np.float32), RATE).size == 0
