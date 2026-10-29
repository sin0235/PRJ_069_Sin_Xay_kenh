from __future__ import annotations

import gc
import os
import threading
import sys
from pathlib import Path


class TTSProviderError(RuntimeError):
    pass


class TTSProviderManager:
    def __init__(self, loaders: dict | None = None):
        self._loaders = loaders or {"GWEN_TTS": self._load_gwen, "VIE_NEU_V3_TURBO": self._load_vieneu}
        self._lock = threading.Lock()
        self._provider = None
        self._model = None

    def synthesize(self, config: dict, text: str, reference_path: str | None = None):
        provider = config["provider"]
        if os.getenv("APP_ENV", "").lower() == "production" and os.getenv("TTS_INFERENCE_CHILD") != "1":
            from src.model_runtime import synthesize_isolated
            return synthesize_isolated(config, text, reference_path)
        with self._lock:
            if provider not in self._loaders:
                raise TTSProviderError("TTS_PROVIDER_UNSUPPORTED")
            if provider != self._provider:
                self._unload()
                try:
                    self._model = self._loaders[provider]()
                    self._provider = provider
                except Exception as exc:
                    self._unload()
                    raise TTSProviderError("TTS_PROVIDER_UNAVAILABLE") from exc
            try:
                return self._infer(provider, self._model, config, text, reference_path)
            except TTSProviderError:
                raise
            except Exception as exc:
                raise TTSProviderError("TTS_SYNTHESIS_FAILED") from exc

    def _unload(self):
        self._model = None
        self._provider = None
        gc.collect()
        try:
            torch = sys.modules.get("torch")
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    @staticmethod
    def _load_gwen():
        try:
            import torch
            from qwen_tts import Qwen3TTSModel
        except ImportError as exc:
            raise TTSProviderError("TTS_PROVIDER_UNAVAILABLE") from exc
        cuda = torch.cuda.is_available()
        return Qwen3TTSModel.from_pretrained(
            "g-group-ai-lab/gwen-tts-0.6B",
            device_map="cuda:0" if cuda else "cpu",
            dtype=torch.bfloat16 if cuda else torch.float32,
        )

    @staticmethod
    def _load_vieneu():
        try:
            cache_home = Path(os.environ.get("PRJ069_VIENU_HF_HOME") or (
                Path.home() / ".cache" / "prj069-vieneu"
            )).expanduser()
            hub_cache = cache_home / "hub"
            os.environ["HF_HOME"] = str(cache_home)
            os.environ["HF_HUB_CACHE"] = str(hub_cache)
            os.environ["HF_HUB_DISABLE_SHARED_BLOBS"] = "1"
            os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
            import huggingface_hub.constants as hf_constants
            hf_constants.HF_HOME = str(cache_home)
            hf_constants.HF_HUB_CACHE = str(hub_cache)
            hf_constants.HF_HUB_DISABLE_SHARED_BLOBS = True
            hf_constants.HF_HUB_DISABLE_SYMLINKS = True
            from vieneu import Vieneu
        except ImportError as exc:
            raise TTSProviderError("TTS_PROVIDER_UNAVAILABLE") from exc
        return Vieneu(
            mode="v3turbo", device="cpu", backend="onnx", precision="fp32", threads=2,
        )

    @staticmethod
    def _infer(provider: str, model, config: dict, text: str, reference_path: str | None):
        advanced = config.get("advanced") or {}
        if provider == "GWEN_TTS":
            audio, sample_rate = model.generate_voice_clone(
                text=text,
                language="Vietnamese",
                ref_audio=reference_path,
                ref_text=config["reference_text"],
                x_vector_only_mode=advanced.get("x_vector_only_mode", False),
                temperature=advanced.get("temperature", 0.3),
                top_k=advanced.get("top_k", 20),
                top_p=advanced.get("top_p", 0.9),
                max_new_tokens=advanced.get("max_new_tokens", 4096),
                repetition_penalty=advanced.get("repetition_penalty", 2.0),
            )
            return audio[0], sample_rate
        options = {"ref_audio": reference_path} if reference_path else {"voice": config.get("voice_id") or "Hải Đăng"}
        audio = model.infer(
            text, **options,
            denoise=advanced.get("denoise_reference", True),
            use_ref_codes=advanced.get("use_reference_codes", True),
            temperature=advanced.get("temperature", 0.8),
            top_k=advanced.get("top_k", 25),
            top_p=advanced.get("top_p", 0.95),
            max_new_frames=advanced.get("max_new_frames", 300),
            repetition_penalty=advanced.get("repetition_penalty", 1.2),
            # 256 pushed a 233-char voice-clone shot past the 3.5 GiB worker limit (OOM); 100 keeps the peak bounded.
            max_chars=advanced.get("max_chars", 100),
        )
        return audio, model.sample_rate


tts_provider_manager = TTSProviderManager()
