"""Chuẩn bị VieNeu cố định revision và suy luận trong tiến trình có thể dừng."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

MODEL_REVISIONS = {
    "pnnbao-ump/VieNeu-TTS-v3-Turbo": "61b85e3d937fbbacb387714180e8182823512523",
    "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX": "ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae",
}


def cache_home() -> Path:
    return Path(os.environ.get("PRJ069_VIENU_HF_HOME", str(Path.home() / ".cache/prj069-vieneu")))


def require_provider(provider: str) -> None:
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError
    if provider != "VIE_NEU_V3_TURBO":
        raise TTSProviderError("TTS_PROVIDER_NOT_READY")


def model_status(*, verify_hashes: bool = False) -> dict:
    # Khi giọng được đẩy sang GitHub Actions (REMOTE_COMPUTE_MODE=github), máy này không nạp mô hình;
    # runner trên Actions (REMOTE_ENGINE_CHILD=1) vẫn kiểm mô hình cục bộ như thường.
    if (not verify_hashes and os.environ.get("REMOTE_COMPUTE_MODE") == "github"
            and os.environ.get("REMOTE_ENGINE_CHILD") != "1"):
        return {"state": "READY", "provider": "VIE_NEU_V3_TURBO", "mode": "REMOTE_GITHUB"}
    try:
        manifest = json.loads((cache_home() / "nas-model.json").read_text())
        if manifest["revisions"] != MODEL_REVISIONS or not manifest.get("files") or manifest.get("warmup") != "SUCCEEDED":
            raise ValueError("manifest")
        for item in manifest["files"]:
            path = (cache_home() / item["path"]).resolve()
            if not path.is_relative_to(cache_home().resolve()) or path.stat().st_size != item["size"]:
                raise ValueError("model file")
            if verify_hashes:
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                        raise ValueError("model hash")
        return {"state": "READY", "provider": "VIE_NEU_V3_TURBO", "revisions": MODEL_REVISIONS}
    except (OSError, ValueError, KeyError, TypeError):
        return {"state": "NOT_READY", "error_code": "TTS_MODEL_NOT_READY"}


def synthesize_isolated(config: dict, text: str, reference_path: str | None = None):
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError
    require_provider(config["provider"])
    if model_status()["state"] != "READY":
        raise TTSProviderError("TTS_MODEL_NOT_READY")
    return _run_inference(config, text, reference_path, offline=True)


def _run_inference(config: dict, text: str, reference_path: str | None, *, offline: bool):
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="prj069-tts-") as directory:
        request = Path(directory) / "request.json"
        output = Path(directory) / "audio.npz"
        request.write_text(json.dumps({"config": config, "text": text, "reference_path": reference_path}), encoding="utf-8")
        request.chmod(0o600)
        child_env = {**os.environ, "TTS_INFERENCE_CHILD": "1", "HF_HUB_OFFLINE": "1" if offline else "0",
            "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2",
            "HF_HOME": str(cache_home()), "HF_HUB_CACHE": str(cache_home() / "hub")}
        timeout = max(1, min(float(os.getenv("TTS_JOB_TIMEOUT_SECONDS", "600")), 1800))
        try:
            # Logs stay out of API error payloads: provider logs can contain private narration.
            with (Path(directory) / "inference.log").open("w") as log:
                result = subprocess.run([sys.executable, "-m", "src.model_runtime", "infer", str(request), str(output)],
                    env=child_env, stdout=log, stderr=log, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise TTSProviderError("TTS_INFERENCE_TIMEOUT") from exc
        if result.returncode != 0 or not output.is_file():
            raise TTSProviderError("TTS_SYNTHESIS_FAILED")
        with np.load(output, allow_pickle=False) as data:
            audio, rate = data["audio"].copy(), int(data["sample_rate"])
        if not audio.size or not np.isfinite(audio).all() or rate <= 0:
            raise TTSProviderError("TTS_AUDIO_INVALID")
        return audio, rate


def prepare() -> None:
    from huggingface_hub import snapshot_download
    cache_home().mkdir(parents=True, exist_ok=True)
    hub = cache_home() / "hub"
    files = []
    for repo, revision in MODEL_REVISIONS.items():
        patterns = (["onnx_update/*", "config.json", "voices_v3_turbo.json", "speaker_encoder.onnx", "denoiser.onnx"]
            if "VieNeu" in repo else ["*.onnx", "*.data", "codec_browser_onnx_meta.json"])
        snapshot = Path(snapshot_download(repo, revision=revision, cache_dir=hub, allow_patterns=patterns))
        refs = snapshot.parent.parent / "refs"
        refs.mkdir(exist_ok=True)
        (refs / "main").write_text(revision)
        for path in sorted(snapshot.rglob("*")):
            if path.is_symlink() and path.is_file():
                # ONNX Runtime rejects external data that resolves outside the model directory.
                link = path.with_name(path.name + ".tmp-link")
                os.link(path.resolve(), link)
                os.replace(link, path)
            if path.is_file():
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                files.append({"path": str(path.relative_to(cache_home())), "size": path.stat().st_size, "sha256": digest})
    audio, rate = _run_inference({"provider": "VIE_NEU_V3_TURBO", "voice_id": "Hải Đăng"},
        "Xin chào, hệ thống tạo giọng nói đã sẵn sàng.", None, offline=True)
    import wave
    import numpy as np
    with wave.open(str(cache_home() / "warmup.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    manifest = {"revisions": MODEL_REVISIONS, "files": files, "warmup": "SUCCEEDED", "sample_rate": rate}
    temporary = cache_home() / "nas-model.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2))
    temporary.replace(cache_home() / "nas-model.json")
    print(json.dumps(model_status(verify_hashes=True)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "status", "infer"])
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "status":
        result = model_status(verify_hashes=True)
        print(json.dumps(result))
        raise SystemExit(0 if result["state"] == "READY" else 1)
    else:
        from src.modules.tao_video_noi_dung.tts_provider import tts_provider_manager
        import numpy as np
        payload = json.loads(Path(args.paths[0]).read_text(encoding="utf-8"))
        audio, rate = tts_provider_manager.synthesize(payload["config"], payload["text"], payload["reference_path"])
        np.savez(args.paths[1], audio=np.asarray(audio, dtype=np.float32), sample_rate=rate)


if __name__ == "__main__":
    main()
