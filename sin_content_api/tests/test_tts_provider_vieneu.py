import os
import sys
from types import ModuleType

import numpy as np

from src.modules.tao_video_noi_dung.tts_provider import TTSProviderManager


def test_vieneu_loads_turbo_on_cpu_with_isolated_non_shared_cache(tmp_path, monkeypatch):
    calls = []
    module = ModuleType("vieneu")
    module.Vieneu = lambda **kwargs: calls.append(kwargs) or object()
    hf_constants = ModuleType("huggingface_hub.constants")
    hf_constants.HF_HOME = "old"
    hf_constants.HF_HUB_CACHE = "old/hub"
    hf_constants.HF_HUB_DISABLE_SHARED_BLOBS = False
    hf_constants.HF_HUB_DISABLE_SYMLINKS = False
    monkeypatch.setenv("PRJ069_VIENU_HF_HOME", str(tmp_path / "vieneu-hf"))
    monkeypatch.setitem(sys.modules, "vieneu", module)
    monkeypatch.setitem(sys.modules, "huggingface_hub.constants", hf_constants)

    TTSProviderManager._load_vieneu()

    assert calls == [{
        "mode": "v3turbo", "device": "cpu", "backend": "onnx",
        "precision": "fp32", "threads": 2,
    }]
    assert os.environ["HF_HOME"] == str(tmp_path / "vieneu-hf")
    assert os.environ["HF_HUB_DISABLE_SYMLINKS"] == "1"
    assert hf_constants.HF_HOME == str(tmp_path / "vieneu-hf")
    assert hf_constants.HF_HUB_CACHE == str(tmp_path / "vieneu-hf" / "hub")
    assert hf_constants.HF_HUB_DISABLE_SHARED_BLOBS is True
    assert hf_constants.HF_HUB_DISABLE_SYMLINKS is True


def test_vieneu_clone_uses_reference_denoising_and_sdk_sample_rate():
    class Model:
        sample_rate = 48_000

        def infer(self, text, **kwargs):
            self.request = (text, kwargs)
            return np.array([0.1, -0.1], dtype=np.float32)

    model = Model()
    audio, sample_rate = TTSProviderManager._infer(
        "VIE_NEU_V3_TURBO", model, {"voice_id": "Hải Đăng"}, "Xin chào", "voice.wav",
    )

    np.testing.assert_allclose(audio, [0.1, -0.1])
    assert sample_rate == 48_000
    assert model.request == ("Xin chào", {
        "ref_audio": "voice.wav", "denoise": True, "use_ref_codes": True,
        "temperature": 0.8, "top_k": 25, "top_p": 0.95,
        "repetition_penalty": 1.2, "max_new_frames": 300, "max_chars": 256,
    })
