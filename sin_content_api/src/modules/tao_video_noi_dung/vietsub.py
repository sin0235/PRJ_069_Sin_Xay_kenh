from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import textwrap
import unicodedata
from difflib import SequenceMatcher
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


def _transcribe_isolated(audio_path: Path, mode: str | None = None) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="prj069-vietsub-") as directory:
        output = Path(directory) / "cues.json"
        env = {**os.environ, "VIETSUB_INFERENCE_CHILD": "1", "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"}
        try:
            with (Path(directory) / "asr.log").open("w") as log:
                result = subprocess.run([sys.executable, "-m", __name__, str(audio_path), str(output), *([mode] if mode else [])],
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


def transcribe_words(audio_path: Path) -> list[dict]:
    if os.getenv("APP_ENV", "").lower() == "production" and os.getenv("VIETSUB_INFERENCE_CHILD") != "1":
        return _transcribe_isolated(audio_path, "words")
    try:
        segments, _ = _get_model().transcribe(
            str(audio_path), language="vi", task="transcribe", beam_size=5,
            word_timestamps=True, vad_filter=True, condition_on_previous_text=False,
        )
        segments = list(segments)
    except Exception as exc:
        raise VietsubError("VIETSUB_ASR_FAILED") from exc
    words = []
    for segment in segments:
        for word in getattr(segment, "words", None) or []:
            text = (getattr(word, "word", "") or "").strip()
            start, end = float(getattr(word, "start", 0) or 0), float(getattr(word, "end", 0) or 0)
            if text and 0 <= start < end:
                words.append({"text": text, "start_ms": round(start * 1000), "end_ms": round(end * 1000)})
    if not words:
        raise VietsubError("VIETSUB_WORD_TIMESTAMPS_MISSING")
    return words


def transcribe_words_cached(audio_path: Path, cache_path: Path) -> list[dict]:
    with audio_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("version") == CACHE_VERSION and cached.get("model") == MODEL_SIZE and cached.get("audio_sha256") == digest:
            words = cached.get("words")
            if isinstance(words, list) and words and all(
                isinstance(w, dict) and isinstance(w.get("text"), str)
                and isinstance(w.get("start_ms"), int) and isinstance(w.get("end_ms"), int) and w["end_ms"] > w["start_ms"] >= 0
                for w in words
            ):
                return words
    except (OSError, ValueError, TypeError):
        pass
    words = transcribe_words(audio_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    try:
        temporary_path.write_text(
            json.dumps({"version": CACHE_VERSION, "model": MODEL_SIZE, "audio_sha256": digest, "words": words}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(cache_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return words


def _normalize_token(token: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFC", token).casefold() if ch.isalnum())


def align_script_words(script_words: list[str], asr_words: list[dict]) -> list[dict]:
    """Gán mốc thời gian ASR cho từng từ của kịch bản đã duyệt; từ ASR nghe sai/thiếu thì nội suy theo độ dài chữ."""
    if not script_words or not asr_words:
        raise VietsubError("VIETSUB_ALIGNMENT_INPUT_EMPTY")
    a = [_normalize_token(word) for word in script_words]
    b = [_normalize_token(word["text"]) for word in asr_words]
    count = len(script_words)
    starts: list[int | None] = [None] * count
    ends: list[int | None] = [None] * count
    for tag, i1, i2, j1, _ in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                starts[i1 + offset] = asr_words[j1 + offset]["start_ms"]
                ends[i1 + offset] = asr_words[j1 + offset]["end_ms"]
    index = 0
    while index < count:
        if starts[index] is not None:
            index += 1
            continue
        stop = index
        while stop < count and starts[stop] is None:
            stop += 1
        left = ends[index - 1] if index else asr_words[0]["start_ms"]
        right = starts[stop] if stop < count else asr_words[-1]["end_ms"]
        right = max(right, left + (stop - index) * 80)
        weights = [max(1, len(a[k])) for k in range(index, stop)]
        cursor = float(left)
        for k, weight in zip(range(index, stop), weights):
            starts[k] = round(cursor)
            cursor += (right - left) * weight / sum(weights)
            ends[k] = round(cursor)
        index = stop
    aligned, previous_end = [], 0
    for word, start, end in zip(script_words, starts, ends):
        start = max(start, previous_end)
        end = max(end, start + 60)
        aligned.append({"text": word, "start_ms": start, "end_ms": end})
        previous_end = end
    return aligned


def karaoke_cues(words: list[dict], max_words: int = 6, max_ms: int = 2800) -> list[dict]:
    """Chia từ thành cụm ngắn như phụ đề edit chuyên nghiệp; giữ mốc từng từ cho hiệu ứng tô từ."""
    cues: list[dict] = []
    current: list[dict] = []

    def flush() -> None:
        if current:
            cues.append({
                "text": " ".join(word["text"] for word in current),
                "start_ms": current[0]["start_ms"],
                "duration_ms": current[-1]["end_ms"] - current[0]["start_ms"],
                "words": list(current),
            })
            current.clear()

    for word in words:
        if current and (
            len(current) >= max_words
            or word["end_ms"] - current[0]["start_ms"] > max_ms
            or word["start_ms"] - current[-1]["end_ms"] > 700
        ):
            flush()
        current.append(word)
        text = word["text"]
        if len(current) >= 2 and (text.endswith((".", "!", "?", ";", ":")) or (len(current) >= 4 and text.endswith(","))):
            flush()
    flush()
    for cue, following in zip(cues, cues[1:]):
        gap = following["start_ms"] - (cue["start_ms"] + cue["duration_ms"])
        cue["duration_ms"] += max(0, min(gap, 250))
    return cues


if __name__ == "__main__":
    audio, output = Path(sys.argv[1]), Path(sys.argv[2])
    result = transcribe_words(audio) if sys.argv[3:] == ["words"] else transcribe_vietnamese(audio)
    output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
