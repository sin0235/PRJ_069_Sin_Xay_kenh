import sys
import subprocess
from types import SimpleNamespace

from src.modules.tao_video_noi_dung import vietsub


def test_transcribe_vietnamese_uses_cpu_small_and_preserves_diacritics(monkeypatch, tmp_path):
    calls = {}

    class FakeModel:
        def __init__(self, model_size, device, compute_type):
            calls["model"] = (model_size, device, compute_type)

        def transcribe(self, audio_path, **options):
            calls["audio"] = audio_path
            calls["options"] = options
            words = [
                SimpleNamespace(word="Xin", start=0.0, end=0.3),
                SimpleNamespace(word=" chào", start=0.3, end=0.7),
                SimpleNamespace(word=" mọi", start=0.7, end=1.0),
                SimpleNamespace(word=" người.", start=1.0, end=1.4),
            ]
            return iter([SimpleNamespace(start=0.0, end=1.4, text="Xin chào mọi người.", words=words)]), None

    monkeypatch.setattr(vietsub, "_load_model", lambda: FakeModel("small", "cpu", "int8"))
    monkeypatch.setattr(vietsub, "_model", None)
    audio = tmp_path / "voice.wav"

    cues = vietsub.transcribe_vietnamese(audio)

    assert calls["model"] == ("small", "cpu", "int8")
    assert calls["audio"] == str(audio)
    assert calls["options"]["language"] == "vi"
    assert calls["options"]["word_timestamps"] is True
    assert cues == [{"text": "Xin chào mọi người.", "start_ms": 0, "duration_ms": 1400}]


def test_vietsub_model_loader_is_cpu_only(monkeypatch):
    calls = []
    fake_module = SimpleNamespace(WhisperModel=lambda *args, **kwargs: calls.append((args, kwargs)) or "model")
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    assert vietsub._load_model() == "model"
    assert calls == [(('small',), {"device": "cpu", "compute_type": "int8", "cpu_threads": 2, "num_workers": 1})]


def test_production_asr_times_out_in_child_process(monkeypatch, tmp_path):
    import pytest

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("VIETSUB_INFERENCE_CHILD", raising=False)
    calls = []

    def timeout(command, **options):
        calls.append((command, options))
        raise subprocess.TimeoutExpired(command, options["timeout"])

    monkeypatch.setattr(vietsub.subprocess, "run", timeout)
    monkeypatch.setattr(vietsub, "_get_model", lambda: pytest.fail("worker must not load ASR in-process"))
    with pytest.raises(vietsub.VietsubError, match="VIETSUB_ASR_TIMEOUT"):
        vietsub.transcribe_vietnamese(tmp_path / "voice.wav")
    assert calls[0][1]["timeout"] == 600
    assert calls[0][1]["env"]["VIETSUB_INFERENCE_CHILD"] == "1"


def test_production_asr_uses_durable_model_cache(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PRJ069_VIENU_HF_HOME", str(tmp_path / "vieneu"))
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(
        WhisperModel=lambda *args, **options: calls.append(options)))
    vietsub._load_model()
    assert calls[0]["download_root"] == str(tmp_path / "whisper")


def test_vietsub_cache_reuses_matching_audio_and_srt_is_valid(tmp_path, monkeypatch):
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"audio-one")
    cache = tmp_path / "vietsub.json"
    calls = []
    expected = [{"text": "Giữ đúng dấu tiếng Việt.", "start_ms": 250, "duration_ms": 1250}]
    monkeypatch.setattr(vietsub, "transcribe_vietnamese", lambda _path: calls.append(1) or expected)

    first = vietsub.transcribe_cached(audio, cache)
    second = vietsub.transcribe_cached(audio, cache)

    assert first == second == expected
    assert calls == [1]
    assert vietsub.to_srt(second) == "1\n00:00:00,250 --> 00:00:01,500\nGiữ đúng dấu tiếng Việt.\n"

    audio.write_bytes(b"audio-two")
    vietsub.transcribe_cached(audio, cache)
    assert calls == [1, 1]


def test_vietsub_splits_long_cues_at_word_boundaries():
    words = [
        SimpleNamespace(word=f" từ{i}", start=float(i), end=float(i) + 0.8)
        for i in range(9)
    ]

    cues = vietsub.group_words(words)

    assert [cue["text"] for cue in cues] == ["từ0 từ1 từ2 từ3 từ4 từ5", "từ6 từ7 từ8"]
    assert all(cue["duration_ms"] <= 6000 for cue in cues)


def test_vietsub_preset_renders_vietnamese_with_bundled_font(tmp_path):
    from src.modules.media_studio.video_processor import video_processor
    from src.schemas.contracts import TimelineCaption, TimelineClip, TimelineDocument, TimelineMediaType

    source = tmp_path / "source.mp4"
    output = tmp_path / "captioned.mp4"
    created = subprocess.run(
        [video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=navy:s=320x568:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr

    timeline = TimelineDocument(
        width=320,
        height=568,
        clips=[TimelineClip(clip_id="clip_1", asset_id="asset_1", media_type=TimelineMediaType.VIDEO, duration_ms=1000, trim_out_ms=1000)],
        captions=[TimelineCaption(text="Giữ đúng dấu tiếng Việt.", start_ms=0, duration_ms=900, font_size=24)],
    )

    video_processor.render_timeline_document(
        timeline,
        lambda _asset_id: source,
        output,
        caption_style="vietsub_v1",
    )

    assert output.is_file() and output.stat().st_size > 0


def test_content_video_export_includes_srt_for_timeline_captions(tmp_path):
    import hashlib
    import json
    import zipfile

    from src.modules.tao_video_noi_dung.runner import _write_export_package
    from src.schemas.contracts import TimelineCaption, TimelineDocument

    video = tmp_path / "final.mp4"
    video.write_bytes(b"final video")
    package = tmp_path / "export.zip"
    run = SimpleNamespace(id="run-vietsub", voice_asset_id="voice-1")
    plan = SimpleNamespace(id="plan-1", revision=1, source_content="Nội dung nguồn", storyboard_json="{}", style_snapshot_sha256="style-hash")
    timeline = TimelineDocument(captions=[TimelineCaption(text="Giữ đúng dấu tiếng Việt.", start_ms=250, duration_ms=1250, font_size=52)])

    _write_export_package(package, video, run, plan, timeline, {"vietsub_status": "GENERATED_UNREVIEWED"}, [], [], None)

    with zipfile.ZipFile(package) as archive:
        srt = archive.read("subtitles/vietsub.srt").decode("utf-8")
        manifest = json.loads(archive.read("manifest.json"))
    assert srt == "1\n00:00:00,250 --> 00:00:01,500\nGiữ đúng dấu tiếng Việt.\n"
    assert manifest["files"]["subtitles/vietsub.srt"] == hashlib.sha256(srt.encode("utf-8")).hexdigest()
