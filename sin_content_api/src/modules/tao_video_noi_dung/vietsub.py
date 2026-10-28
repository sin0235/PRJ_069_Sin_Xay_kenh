from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import textwrap
from pathlib import Path
from typing import Iterable

MODEL_SIZE = "small"
CACHE_VERSION = 1
_model = None
_model_lock = threading.Lock()


class VietsubError(RuntimeError):
    pass


def _load_model():
    from faster_whisper import WhisperModel
    options = {"device": "cpu", "compute_type": "int8", "cpu_threads": 2, "num_workers": 1}
    if os.getenv("APP_ENV", "").lower() == "production":
        from src.model_runtime import cache_home
        options["download_root"] = str(cache_home().parent / "whisper")
    return WhisperModel(MODEL_SIZE, **options)


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = _load_model()
    return _model


def _wrap_words(words: list[str]) -> str:
    return textwrap.fill(" ".join(words), width=38, break_long_words=False, break_on_hyphens=False)


def group_words(words: Iterable[object]) -> list[dict]:
    cues: list[dict] = []
    current: list[tuple[str, float, float]] = []

    def flush() -> None:
        if not current:
            return
        text = _wrap_words([item[0] for item in current])
        if text:
            start_ms = max(0, round(current[0][1] * 1000))
            end_ms = max(start_ms + 1, round(current[-1][2] * 1000))
            cues.append({"text": text, "start_ms": start_ms, "duration_ms": end_ms - start_ms})
        current.clear()

    for word in words:
        text = (getattr(word, "word", "") or "").strip()
        start = float(getattr(word, "start", 0) or 0)
        end = float(getattr(word, "end", 0) or 0)
        if not text or start < 0 or end <= start:
            continue

        candidate = [*current, (text, start, end)]
        candidate_text = _wrap_words([item[0] for item in candidate])
        candidate_duration = end - candidate[0][1]
        if current and (candidate_duration > 6 or candidate_text.count("\n") > 1):
            flush()
            candidate = [(text, start, end)]
            candidate_text = text
        current.extend(candidate[len(current):])
        if candidate_duration >= 0.7 and current[-1][0].endswith((".", "!", "?", ":", ";")):
            flush()

    flush()
    return cues


def transcribe_vietnamese(audio_path: Path) -> list[dict]:
    if os.getenv("APP_ENV", "").lower() == "production" and os.getenv("VIETSUB_INFERENCE_CHILD") != "1":
        return _transcribe_isolated(audio_path)
    try:
        segments, _ = _get_model().transcribe(
            str(audio_path),
            language="vi",
            task="transcribe",
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segments = list(segments)
    except Exception as exc:
        raise VietsubError("VIETSUB_ASR_FAILED") from exc

    cues = []
    for segment in segments:
        words = getattr(segment, "words", None) or []
        if words:
            cues.extend(group_words(words))
            continue
        text = (getattr(segment, "text", "") or "").strip()
        start = float(getattr(segment, "start", 0) or 0)
        end = float(getattr(segment, "end", 0) or 0)
        if not text or end <= start or end - start > 6 or len(text) > 76:
            raise VietsubError("VIETSUB_WORD_TIMESTAMPS_MISSING")
        cues.append({"text": _wrap_words(text.split()), "start_ms": max(0, round(start * 1000)), "duration_ms": round((end - start) * 1000)})
    return cues


def _transcribe_isolated(audio_path: Path) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="prj069-vietsub-") as directory:
        output = Path(directory) / "cues.json"
        env = {**os.environ, "VIETSUB_INFERENCE_CHILD": "1", "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
        try:
            with (Path(directory) / "asr.log").open("w") as log:
                result = subprocess.run([sys.executable, "-m", __name__, str(audio_path), str(output)],
                    env=env, stdout=log, stderr=log, timeout=600, check=False)
        except subprocess.TimeoutExpired as error:
            raise VietsubError("VIETSUB_ASR_TIMEOUT") from error
        if result.returncode != 0 or not output.is_file():
            raise VietsubError("VIETSUB_ASR_FAILED")
        return json.loads(output.read_text(encoding="utf-8"))


def transcribe_cached(audio_path: Path, cache_path: Path) -> list[dict]:
    with audio_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("version") == CACHE_VERSION and cached.get("model") == MODEL_SIZE and cached.get("audio_sha256") == digest:
            cues = cached.get("cues")
            if isinstance(cues, list) and all(
                isinstance(cue, dict)
                and isinstance(cue.get("text"), str)
                and isinstance(cue.get("start_ms"), int)
                and isinstance(cue.get("duration_ms"), int)
                and cue["start_ms"] >= 0
                and cue["duration_ms"] > 0
                for cue in cues
            ):
                return cues
    except (OSError, ValueError, TypeError):
        pass

    cues = transcribe_vietnamese(audio_path)
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    try:
        temporary_path.write_text(
            json.dumps({"version": CACHE_VERSION, "model": MODEL_SIZE, "audio_sha256": digest, "cues": cues}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(cache_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return cues


def to_srt(cues: list[dict]) -> str:
    entries = []
    for index, cue in enumerate(cues, start=1):
        start = cue["start_ms"]
        end = start + cue["duration_ms"]
        entries.append(f"{index}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{cue['text']}\n")
    return "\n".join(entries)


def _srt_timestamp(milliseconds: int) -> str:
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


if __name__ == "__main__":
    Path(sys.argv[2]).write_text(json.dumps(transcribe_vietnamese(Path(sys.argv[1])), ensure_ascii=False), encoding="utf-8")
