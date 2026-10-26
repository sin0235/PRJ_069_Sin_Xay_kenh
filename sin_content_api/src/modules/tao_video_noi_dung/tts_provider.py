from __future__ import annotations

import gc
import threading


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
            import torch
            if torch.cuda.is_available():
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
            from vieneu import Vieneu
        except ImportError as exc:
            raise TTSProviderError("TTS_PROVIDER_UNAVAILABLE") from exc
        return Vieneu(mode="v3turbo")

    @staticmethod
    def _infer(provider: str, model, config: dict, text: str, reference_path: str | None):
        if provider == "GWEN_TTS":
            audio, sample_rate = model.generate_voice_clone(
                text=text,
                language="Vietnamese",
                ref_audio=reference_path,
                ref_text=config["reference_text"],
                temperature=0.3,
                top_k=20,
                top_p=0.9,
                max_new_tokens=4096,
                repetition_penalty=2.0,
            )
            return audio[0], sample_rate
        options = {"ref_audio": reference_path} if reference_path else {"voice": config.get("voice_id") or "Hải Đăng"}
        return model.infer(text, **options), 48000


tts_provider_manager = TTSProviderManager()
