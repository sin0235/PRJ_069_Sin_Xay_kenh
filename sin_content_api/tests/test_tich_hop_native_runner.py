from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from src.modules.tao_video_noi_dung import runner, hf_project


def test_native_ui_is_rendered_and_receipt_keeps_renderer_metadata(monkeypatch, tmp_path):
    run = SimpleNamespace(workspace_id="w", project_id="p", created_by="u", id="r")
    plan = SimpleNamespace(style_snapshot_json='{"render_engine":"remotion","remotion_native":true,"assembly":"hyperframes","aspect_ratio":"9:16"}', storyboard_json="{}")
    shot = SimpleNamespace(shot_id="s1", duration_seconds=4, narration="Một hai", ui_scene=SimpleNamespace(layout="CHECKLIST"))
    step = {}
    calls = []
    monkeypatch.setattr(runner, "verify_shot_receipt", lambda *_: None)
    monkeypatch.setattr(runner, "get_workspace_storage_dir", lambda *_: tmp_path)
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr(runner, "_probe_shot_with_qc", lambda *_: ({}, []))
    monkeypatch.setattr(runner, "_file_sha256", lambda *_: "sha")
    monkeypatch.setattr(runner, "native_remotion_enabled", lambda *_: True)
    monkeypatch.setattr(runner, "native_remotion_fingerprint", lambda *_: "fp1")

    def render(scene, style, seconds, ratio, path, **kwargs):
        calls.append((style, seconds, ratio, kwargs))
        path.write_bytes(b"native")
        return {"render_engine": "remotion", "render_variant": "native", "renderer_revision": "rev1",
                "render_fingerprint": "fp1", "timing_source": "word_times"}

    monkeypatch.setattr(runner, "render_scene", render)
    monkeypatch.setattr(runner, "render_placeholder", lambda *_: (_ for _ in ()).throw(AssertionError("placeholder")))
    class DB:
        def add(self, _asset):
            pass

    runner._render_ui_asset(DB(), run, plan, shot, step, [0.2, 1.4], 4, placeholder=True)

    assert calls and calls[0][3]["word_times"] == [0.2, 1.4]
    assert step["render_variant"] == "native"
    assert step["renderer_revision"] == "rev1"
    assert step["render_fingerprint"] == "fp1"
    assert step["requested_render_fingerprint"] == "fp1"
    assert step["timing_source"] == "word_times"


def test_hyperframes_uses_native_ui_clip_and_real_word_times(monkeypatch, tmp_path):
    from src.modules.tao_video_noi_dung import hf_project as project
    from src.modules.tao_video_noi_dung import planner
    scene = SimpleNamespace(layout="CHECKLIST")
    shot = SimpleNamespace(shot_id="s1", shot_kind="UI_SIM", ui_scene=scene, narration="Một hai", duration_seconds=4)
    storyboard = SimpleNamespace(shots=[shot])
    media = {"path": tmp_path / "native.mp4", "media_start_seconds": 0.25,
             "render_metadata": {"render_engine": "remotion", "render_variant": "native", "render_fingerprint": "fp1"}}
    captured = {}
    monkeypatch.setattr(runner, "_diagram_word_times", lambda *_args, **_kwargs: [0.2, 1.4])
    monkeypatch.setattr(planner, "resolve_diagram_times", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(project, "build_project", lambda _p, shots, *_a, **_kw: captured.update(shots=shots) or {"native_scenes": [], "legacy_scenes": []})
    monkeypatch.setattr(project, "render_project", lambda _p, out: out.write_bytes(b"video"))
    monkeypatch.setattr(runner.video_processor, "probe_video", lambda _p: {"duration_seconds": 4, "width": 1080, "height": 1920})

    runner._render_with_hyperframes(storyboard, [{"clip_seconds": 4}], None, None, tmp_path / "out.mp4",
                                    aspect_ratio="9:16", shot_media=[media])

    rendered_shot = captured["shots"][0]
    assert rendered_shot["media_path"] == media["path"]
    assert rendered_shot["media_start_seconds"] == 0.25
    assert rendered_shot["word_times"] == [0.2, 1.4]
    assert rendered_shot["scene"] is None
    assert rendered_shot["render_metadata"]["render_variant"] == "native"


def test_legacy_hyperframes_placeholder_receipt_is_not_a_real_media_clip():
    assert not runner._has_real_ui_clip({"render_engine": "hyperframes_assembly"})
    assert not runner._has_real_ui_clip({"render_engine": "placeholder", "render_variant": "placeholder"})
    assert runner._has_real_ui_clip({"render_engine": "remotion", "render_variant": "native"})


def test_hyperframes_cadence_keeps_collage_limits_and_excludes_captions(monkeypatch, tmp_path):
    from src.modules.tao_video_noi_dung import hf_scenes

    shots = [
        {"shot_id": f"s{i}", "scene": SimpleNamespace(layout="CHECKLIST", diagram=SimpleNamespace(model_dump=lambda **_kw: {})),
         "narration": "", "seconds": 2, "events": [], "word_times": None}
        for i in range(1, 15)
    ]
    monkeypatch.setattr(hf_project.shutil, "copy", lambda *_: None)
    monkeypatch.setattr(hf_project, "display_json", lambda value: value)
    monkeypatch.setattr(hf_project, "legacy_scene", lambda cid, *_: f"scene:{cid}")
    monkeypatch.setattr(hf_project, "collage_block", lambda cid: f"collage:{cid}")
    monkeypatch.setattr(hf_scenes, "NATIVE", {})

    result = hf_project.build_project(tmp_path / "project", shots, None, None, aspect_ratio="9:16")
    index = (tmp_path / "project" / "index.html").read_text(encoding="utf-8")

    assert result["collage_transitions"] == 2
    assert result["total_seconds"] == 28
    assert [item["type"] for item in result["transition_cadence"][:3]] == ["fade", "wipe", "cut"]
    assert 'tl.fromTo("#s02"' in index
    assert 'tl.fromTo("#s03"' in index
    assert 'tl.fromTo("#captions"' not in index

    short_shots = [dict(shots[0]), {**shots[1], "seconds": 0.1}]
    hf_project.build_project(tmp_path / "short", short_shots, None, None, aspect_ratio="9:16")
    short_index = (tmp_path / "short" / "index.html").read_text(encoding="utf-8")
    assert 'duration: 0.100' in short_index

    disabled = hf_project.build_project(tmp_path / "disabled", shots[:2], None, None, transitions=False, aspect_ratio="9:16")
    disabled_index = (tmp_path / "disabled" / "index.html").read_text(encoding="utf-8")
    assert disabled["transition_cadence"] == []
    assert 'tl.fromTo("#s02", { opacity: 0 }' not in disabled_index
    assert 'tl.fromTo("#s02", { clipPath:' not in disabled_index
    if hasattr(hf_project, "hf_camera"):
        assert 'tl.fromTo("#s02", { scale: 1, transformOrigin:' in disabled_index


def test_native_retry_does_not_reuse_stale_placeholder_receipt(monkeypatch):
    from src.modules.tao_video_noi_dung.planner import Storyboard

    shot = SimpleNamespace(shot_id="s1", shot_kind="UI_SIM", ui_scene=SimpleNamespace(layout="CHECKLIST"),
                           narration="Một hai", duration_seconds=4)
    plan = SimpleNamespace(style_snapshot_json='{"render_engine":"remotion","remotion_native":true,"assembly":"hyperframes","aspect_ratio":"9:16"}', storyboard_json="{}")
    storyboard = SimpleNamespace(shots=[shot])
    step = {"state": "SUCCEEDED", "shot_id": "s1", "asset_id": "old", "raw_asset_id": "old",
            "operation_id": "op", "prompt": "đã duyệt", "clip_seconds": 4,
            "render_engine": "placeholder", "requested_render_fingerprint": "old-fingerprint"}
    run = SimpleNamespace(id="r", lease_token="t", status="RUNNING", workspace_id="w", project_id="p",
                          plan_id="plan", plan_revision=1, storyboard_sha256="s", style_snapshot_sha256="ss",
                          approval_sha256="a", steps_json='[{}]', tts_config_json=None, voice_asset_id=None,
                          include_subtitles=True, music_asset_id=None, created_by="u")
    run.steps_json = json.dumps([step])

    class Query:
        def filter(self, *_args):
            return self

        def all(self):
            return [SimpleNamespace(sha256="new-hash")]

    class DB:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def get(self, *_args):
            return run

        def query(self, *_args):
            return Query()

        def rollback(self):
            pass

        def commit(self):
            pass

    class Heartbeat:
        def __init__(self, *_args):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    rerendered = []
    monkeypatch.setattr(runner, "SessionLocal", DB)
    monkeypatch.setattr(runner, "_RunHeartbeat", Heartbeat)
    monkeypatch.setattr(runner, "fence_session", lambda *_: None)
    monkeypatch.setattr(runner, "_release_lease", lambda *_: None)
    monkeypatch.setattr(runner, "_plan_and_project", lambda *_: (plan, None))
    monkeypatch.setattr(Storyboard, "model_validate_json", classmethod(lambda *_: storyboard))
    monkeypatch.setattr(runner, "_voice_input", lambda *_: None)
    monkeypatch.setattr(runner, "_heartbeat", lambda *_: True)
    monkeypatch.setattr(runner, "_save_run", lambda *_: None)
    monkeypatch.setattr(runner, "verify_shot_receipt", lambda *_: {})
    monkeypatch.setattr(runner, "native_remotion_enabled", lambda *_: True)
    monkeypatch.setattr(runner, "native_remotion_fingerprint", lambda *_: "current-fingerprint")
    monkeypatch.setattr(runner, "_use_hyperframes_assembly", lambda *_: True)
    monkeypatch.setattr(runner, "_render_ui_asset", lambda _db, _run, _plan, _shot, current, *_a, **_kw:
                        (rerendered.append(True), current.update(state="SUCCEEDED", asset_id="new", raw_asset_id="new",
                                                                  render_engine="remotion", requested_render_fingerprint="current-fingerprint"),
                         SimpleNamespace(id="new"))[-1])
    monkeypatch.setattr(runner, "_render_and_qc", lambda *_: None)

    runner.process_run("r", "t")

    assert rerendered == [True]


def _exercise_native_audio_timeline(monkeypatch, tmp_path, voice_kind, fail_visual=False):
    from src.modules.media_studio.video_processor import video_processor
    from src.models.entities import MediaAsset, TimelineVersion
    from src.schemas.contracts import TimelineCaption

    shot_asset = SimpleNamespace(id="shot", sha256="shot-hash", duration_ms=10000, workspace_id="w", project_id="p")
    voice_asset = SimpleNamespace(id="voice", sha256="voice-hash", source_product="CONTENT_VIDEO_TTS" if voice_kind == "tts" else "UPLOAD",
                                  duration_ms=10000) if voice_kind else None

    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def first(self):
            return None if self.model is TimelineVersion else shot_asset

    class DB:
        def query(self, model):
            return Query(model)

        def add(self, _item):
            pass

        def commit(self):
            pass

    shot = SimpleNamespace(shot_id="s1", shot_kind="UI_SIM", ui_scene=SimpleNamespace(layout="CHECKLIST"),
                           narration="Đọc nội dung đã duyệt.", duration_seconds=10, action_beats=[])
    storyboard = SimpleNamespace(shots=[shot])
    plan = SimpleNamespace(target_duration_seconds=10, style_snapshot_sha256="style", source_content="nguồn",
                           style_snapshot_json='{"render_engine":"remotion","remotion_native":true,"assembly":"hyperframes","aspect_ratio":"9:16"}',
                           id="plan", revision=1)
    step = {"clip_seconds": 10, "shot_id": "s1", "render_engine": "remotion", "render_variant": "native"}
    if voice_kind == "tts":
        step["tts_audio"] = {"duration_ms": 10000, "pause_after_ms": 0}
    run = SimpleNamespace(id="run", workspace_id="w", project_id="p", created_by="u",
                          voice_asset_id=voice_asset.id if voice_asset else None,
                          include_subtitles=True, steps_json=json.dumps([step]),
                          output_asset_ids_json="[]", music_asset_id=None, tts_config_json=None)
    output = {"timeline_calls": [], "visual_calls": []}

    monkeypatch.setattr(runner, "_voice_input", lambda *_: (voice_asset, tmp_path / "voice.wav") if voice_asset else None)
    monkeypatch.setattr(runner, "_use_hyperframes_assembly", lambda *_: True)
    monkeypatch.setattr(runner, "native_remotion_enabled", lambda *_: True)
    monkeypatch.setattr(runner, "plan_sfx_cues", lambda *_: [])
    monkeypatch.setattr(runner, "transition_sfx_cues", lambda *_: [])
    monkeypatch.setattr(runner, "get_workspace_storage_dir", lambda *_: tmp_path)
    monkeypatch.setattr(runner, "_verified_asset_path", lambda *_: tmp_path / "shot.mp4")
    monkeypatch.setattr(runner, "_add_brand_end_card", lambda *_: 0)
    monkeypatch.setattr(runner, "evaluate_video_qc", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(runner, "_file_sha256", lambda *_: "sha")
    monkeypatch.setattr(runner, "_write_export_package", lambda path, *_args: path.write_bytes(b"export"))
    monkeypatch.setattr(runner, "run_media_command", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr(video_processor, "probe_video", lambda *_: {"width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 30.0, "duration_seconds": 10.0})
    monkeypatch.setattr(runner.audio_processor, "verify_audio_qc", lambda *_args, **_kwargs: {"passed": True})
    monkeypatch.setattr(runner.audio_processor, "probe_audio", lambda *_: {"codec_name": "aac", "duration_seconds": 10.0})
    monkeypatch.setattr(runner, "transcribe_cached", lambda *_: [{"start_ms": 0, "duration_ms": 9000, "text": "Phụ đề tải lên"}])
    monkeypatch.setattr(runner, "_tts_captions", lambda *_args, **_kwargs: [TimelineCaption(caption_id="tts", text="Phụ đề TTS", start_ms=0, duration_ms=9000)])

    def alignment_failure(*_args, **_kwargs):
        raise runner.VietsubError("không căn được từ")

    monkeypatch.setattr(runner, "transcribe_words_cached", alignment_failure)

    def render_hf(_storyboard, _steps, voice_path, words, output_path, **_kwargs):
        output["visual_calls"].append((voice_path, words))
        if fail_visual:
            raise RuntimeError("lỗi dựng mô phỏng")
        output_path.write_bytes(b"visual")
        return {"duration_seconds": 10.0, "scene_renderers": [{"render_engine": "remotion", "render_variant": "native"}]}

    monkeypatch.setattr(runner, "_render_with_hyperframes", render_hf)

    def render_timeline(timeline, _resolve, output_path, **kwargs):
        output["timeline_calls"].append((timeline, kwargs))
        output_path.write_bytes(b"final")
        return {"duration_seconds": 10.0, "flow_native_audio": False}

    monkeypatch.setattr(video_processor, "render_timeline_document", render_timeline)

    return runner._render_and_qc(DB(), run, plan, storyboard, ["shot"]), run, output


def test_native_hyperframes_uploaded_voice_keeps_asr_captions(monkeypatch, tmp_path):
    _, run, output = _exercise_native_audio_timeline(monkeypatch, tmp_path, "upload")

    assert len(output["timeline_calls"]) == 1
    timeline, _kwargs = output["timeline_calls"][0]
    assert [caption.text for caption in timeline.captions] == ["Phụ đề tải lên"]
    assert timeline.voice_track.asset_id == "voice"
    assert timeline.clips[0].asset_id.startswith("hf-visual-")
    assert _kwargs["preserve_voice_audio"] is False
    assert _kwargs["sfx_cues"] == []
    assert output["visual_calls"] == [(None, None)]
    report = json.loads(run.qc_report_json)
    assert report["caption_count"] == 1
    assert report["measured"]["assembly"] == report["measured"]["visual_engine"] == "hyperframes"
    assert report["measured"]["scene_renderers"][0]["render_variant"] == "native"


def test_native_hyperframes_tts_alignment_failure_keeps_shot_captions(monkeypatch, tmp_path):
    _, run, output = _exercise_native_audio_timeline(monkeypatch, tmp_path, "tts")

    assert len(output["timeline_calls"]) == 1
    timeline, kwargs = output["timeline_calls"][0]
    assert [caption.text for caption in timeline.captions] == ["Phụ đề TTS"]
    assert timeline.voice_track.asset_id == "voice"
    assert kwargs["preserve_voice_audio"] is True
    assert kwargs["sfx_cues"] == []
    assert output["visual_calls"] == [(None, None)]
    report = json.loads(run.qc_report_json)
    assert report["caption_count"] == 1
    assert report["measured"]["scene_renderers"][0]["render_variant"] == "native"


def test_native_hyperframes_without_voice_completes_with_optional_audio(monkeypatch, tmp_path):
    _, run, output = _exercise_native_audio_timeline(monkeypatch, tmp_path, None)

    assert len(output["timeline_calls"]) == 1
    timeline, _kwargs = output["timeline_calls"][0]
    assert timeline.voice_track is None
    assert timeline.captions == []
    assert output["visual_calls"] == [(None, None)]
    report = json.loads(run.qc_report_json)
    assert report["caption_count"] == 0
    assert report["measured"]["visual_engine"] == "hyperframes"


def test_native_hyperframes_without_voice_respects_disabled_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTENT_VIDEO_RENDER_FALLBACK", "0")
    with pytest.raises(RuntimeError, match="lỗi dựng mô phỏng"):
        _exercise_native_audio_timeline(monkeypatch, tmp_path, None, fail_visual=True)

