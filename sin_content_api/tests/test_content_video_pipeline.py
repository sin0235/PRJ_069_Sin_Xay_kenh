from __future__ import annotations

import pathlib
import sys
import json
import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from src.media_process import run_media_command
from src.modules.media_studio.video_processor import video_processor

API_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.modules.tao_video_noi_dung.planner import build_shot_prompt, generate_storyboard, parse_storyboard
from src.modules.tao_video_noi_dung.contracts import CreatePlanRequest, CreateRunRequest, ReconcileShotRequest
from src.modules.tao_video_noi_dung.runner import _has_duplicate_shot_media, evaluate_shot_qc, evaluate_video_qc
from src.modules.tao_video_noi_dung.runner import _mark_flow_setup_blocked, _add_brand_end_card
from src.modules.tao_video_noi_dung import cong_harness
from src.modules.tao_video_noi_dung import router as content_video_router
from src.modules.tao_video_noi_dung.cong_harness import build_shot_receipt, dispatch_shot
from src.modules.tao_video_noi_dung.planner import StoryboardShot
from src.migrations import runner as migration_runner


def test_content_video_migration_upgrades_existing_run_table(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE content_video_runs (id VARCHAR(36) PRIMARY KEY)"))
            connection.execute(text("INSERT INTO content_video_runs (id) VALUES ('legacy-run')"))
        monkeypatch.setattr(migration_runner, "engine", engine)

        migration_runner.migration_up()

        columns = {column["name"] for column in inspect(engine).get_columns("content_video_runs")}
        assert "voice_asset_id" in columns
        assert "tts_config_json" in columns
        assert "include_subtitles" in columns
        with engine.connect() as connection:
            assert connection.execute(text("SELECT include_subtitles FROM content_video_runs WHERE id = 'legacy-run'")).scalar_one() == 1
        assert {"content_video_plans", "content_video_worker_leases"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_tts_subtitles_follow_storyboard_shot_boundaries_without_asr(monkeypatch):
    from src.modules.tao_video_noi_dung import runner

    shots = [
        SimpleNamespace(shot_id="s1", narration="Lời cảnh một", duration_seconds=10),
        SimpleNamespace(shot_id="s2", narration="Lời cảnh hai", duration_seconds=5),
    ]
    monkeypatch.setattr(runner, "transcribe_cached", lambda *_args: pytest.fail("TTS captions must not use ASR"))

    captions = runner._tts_captions(shots)

    assert [(caption.text, caption.start_ms, caption.duration_ms) for caption in captions] == [
        ("Lời cảnh một", 0, 10000),
        ("Lời cảnh hai", 10000, 5000),
    ]


def test_tts_and_ten_second_video_render_without_flow(monkeypatch, tmp_path):
    import subprocess
    import wave
    import numpy as np
    from src.modules.tao_video_noi_dung import runner
    from src.schemas.contracts import TimelineAudioTrack, TimelineClip, TimelineDocument, TimelineMediaType

    shot = SimpleNamespace(shot_id="s1", narration="Lời dẫn thử nghiệm.", duration_seconds=10)

    def fake_tts(_config, _text, _reference_path):
        sample_count = int(9.3 * 24000)
        samples = np.sin(2 * np.pi * 220 * np.arange(sample_count) / 24000) * 0.08
        return samples.astype(np.float32), 24000

    monkeypatch.setattr(runner.tts_provider_manager, "synthesize", fake_tts)
    fake_video = tmp_path / "fake_video.mp4"
    fake_voice = tmp_path / "fake_voice.wav"
    rendered = tmp_path / "rendered.mp4"
    audio, sample_rate = runner.tts_provider_manager.synthesize({"provider": "fake"}, shot.narration, None)
    subprocess.run([
        runner.video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i",
        "color=c=blue:s=360x640:r=24:d=10", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", "10", str(fake_video),
    ], capture_output=True, check=True, timeout=30)

    with wave.open(str(fake_voice), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
    timeline = TimelineDocument(
        width=360, height=640, fps=24,
        clips=[TimelineClip(
            clip_id=shot.shot_id, asset_id="video", media_type=TimelineMediaType.VIDEO,
            start_ms=0, duration_ms=10000, trim_in_ms=0, trim_out_ms=10000,
        )],
        voice_track=TimelineAudioTrack(asset_id="voice", duration_ms=10000),
        captions=runner._tts_captions([shot], height=640, width=360),
    )
    meta = runner.video_processor.render_timeline_document(
        timeline, lambda asset_id: fake_video if asset_id == "video" else fake_voice,
        rendered, caption_style="vietsub_v1", preserve_voice_audio=True,
    )

    assert rendered.is_file()
    assert abs(meta["duration_seconds"] - 9.3) <= 0.1
    assert abs(runner.audio_processor.probe_audio(rendered)["duration_seconds"] - 9.3) <= 0.1
    assert runner.audio_processor.probe_audio(rendered)["sample_rate_hz"] == sample_rate
    assert meta["audio_normalization"] == "SKIPPED_RAW_TTS"
    assert meta["video_playback_speed"] > 1.0
    assert meta["audio_loudness_lufs"] < -18

    slower_voice = tmp_path / "slower_voice.wav"
    with wave.open(str(slower_voice), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(np.zeros(int(10.7 * sample_rate), dtype="<i2").tobytes())
    slower_meta = runner.video_processor.render_timeline_document(
        timeline, lambda asset_id: fake_video if asset_id == "video" else slower_voice,
        tmp_path / "rendered_slower_video.mp4", caption_style="vietsub_v1", preserve_voice_audio=True,
    )
    assert abs(slower_meta["duration_seconds"] - 10.7) <= 0.1
    assert slower_meta["video_playback_speed"] < 1.0


def test_crossfade_keeps_every_shot_when_clips_are_slightly_shorter_than_nominal(tmp_path):
    import subprocess
    from src.modules.media_studio.video_processor import video_processor
    from src.schemas.contracts import TimelineClip, TimelineDocument, TimelineMediaType

    # Flow clips are 299 frames at 30 fps (9.967s), not exactly 10s; the render must still keep all six.
    video = tmp_path / "video.mp4"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "testsrc2=s=360x640:r=30", "-frames:v", "299", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ], check=True, capture_output=True)
    timeline = TimelineDocument(
        width=360, height=640, fps=30,
        clips=[TimelineClip(
            clip_id=f"s{i}", asset_id="video", media_type=TimelineMediaType.VIDEO,
            start_ms=i * 10000, duration_ms=10000, trim_in_ms=0, trim_out_ms=10000,
        ) for i in range(6)],
    )
    out = tmp_path / "rendered.mp4"
    video_processor.render_timeline_document(timeline, lambda _asset_id: video, out, transition_seconds=0.3)

    frames = subprocess.run(
        [video_processor.ffprobe_bin, "-v", "error", "-count_frames", "-select_streams", "v",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert int(frames) >= 6 * 299 - 5


def test_timeline_overlay_accepts_alpha_or_opaque_asset_and_keeps_source_audio(tmp_path):
    import subprocess
    from src.modules.media_studio.video_processor import video_processor
    from src.modules.media_studio.audio_processor import audio_processor

    speaker = tmp_path / "speaker.mp4"
    illustration = tmp_path / "illustration.mp4"
    alpha_overlay = tmp_path / "alpha_overlay.mov"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=360x640:r=24:d=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(speaker),
    ], check=True, capture_output=True)
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=green:s=360x640:r=24:d=2", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(illustration),
    ], check=True, capture_output=True)
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=red@0.7:s=80x80:r=24:d=2,format=yuva420p", "-an", "-c:v", "qtrle", str(alpha_overlay),
    ], check=True, capture_output=True)

    assert video_processor.probe_video(alpha_overlay)["has_alpha"]
    timeline = {
        "width": 360, "height": 640, "fps": 24,
        "clips": [{"clip_id": "paper_cutaway", "asset_id": "paper", "audio_asset_id": "speaker",
                   "audio_trim_in_ms": 0, "media_type": "video", "duration_ms": 2000,
                   "trim_in_ms": 0, "trim_out_ms": 2000}],
        "overlays": [{"asset_id": "overlay", "start_ms": 0, "duration_ms": 2000,
                      "x": 10, "y": 10, "width": 80, "height": 80}],
    }
    output = tmp_path / "rendered_with_paper_overlay.mp4"
    video_processor.render_timeline_document(
        timeline, lambda asset_id: {"speaker": speaker, "paper": illustration, "overlay": alpha_overlay}[asset_id], output,
    )
    assert audio_processor.probe_audio(output)["codec_name"] != "unknown"

    alpha_overlay_webm = tmp_path / "alpha_overlay.webm"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=red@0.7:s=80x80:r=24:d=2,format=yuva420p", "-an",
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
        "-metadata:s:v:0", "alpha_mode=1", str(alpha_overlay_webm),
    ], check=True, capture_output=True)
    assert video_processor.probe_video(alpha_overlay_webm)["has_alpha"]
    webm_output = tmp_path / "rendered_with_paper_webm_overlay.mp4"
    video_processor.render_timeline_document(
        timeline, lambda asset_id: {"speaker": speaker, "paper": illustration, "overlay": alpha_overlay_webm}[asset_id], webm_output,
    )
    assert audio_processor.probe_audio(webm_output)["codec_name"] != "unknown"

    timeline["overlays"][0]["asset_id"] = "paper"
    opaque_output = tmp_path / "rendered_with_opaque_paper_overlay.mp4"
    video_processor.render_timeline_document(
        timeline, lambda asset_id: {"speaker": speaker, "paper": illustration}[asset_id], opaque_output,
    )
    assert opaque_output.is_file()
    assert audio_processor.probe_audio(opaque_output)["codec_name"] != "unknown"


def test_karaoke_render_keeps_static_title_and_highlights_words(tmp_path):
    import subprocess
    from src.modules.media_studio.video_processor import video_processor

    source = tmp_path / "speaker.mp4"
    output = tmp_path / "karaoke.mp4"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=360x640:r=24:d=1", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    ], check=True, capture_output=True)
    work_dir = tmp_path / "render"
    timeline = {
        "width": 360, "height": 640, "fps": 24,
        "clips": [{"clip_id": "speaker", "asset_id": "speaker", "audio_asset_id": "speaker",
                   "audio_trim_in_ms": 0, "media_type": "video", "duration_ms": 1000,
                   "trim_in_ms": 0, "trim_out_ms": 1000}],
        "captions": [
            {"text": "Tiêu đề", "start_ms": 0, "duration_ms": 700, "font_size": 56, "position_y_px": 150},
            {"text": "Xin chào", "start_ms": 0, "duration_ms": 800, "font_size": 42,
             "words": [{"text": "Xin", "start_ms": 0, "end_ms": 350},
                       {"text": "chào", "start_ms": 350, "end_ms": 800}]},
        ],
    }

    video_processor.render_timeline_document(
        timeline, lambda _: source, output, caption_style="vietsub_karaoke_v2", temp_dir=work_dir,
    )

    ass = (work_dir / "captions.ass").read_text(encoding="utf-8")
    assert ("{\\k35}" in ass or "{\\kf35" in ass) and "Xin" in ass and "chào" in ass
    assert "Tiêu đề" not in ass
    assert (work_dir / "caption_0.txt").read_text(encoding="utf-8") == "Tiêu đề"
    assert output.is_file()


def test_speaker_pip_accepts_opaque_animation_background_and_crops_speaker(tmp_path):
    import subprocess
    from src.modules.media_studio.audio_processor import audio_processor
    from src.modules.media_studio.video_processor import video_processor

    speaker = tmp_path / "speaker.mp4"
    paper = tmp_path / "paper.mp4"
    output = tmp_path / "speaker_pip.mp4"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=red:s=360x640:r=24:d=2", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(speaker),
    ], check=True, capture_output=True)
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=green:s=360x640:r=24:d=2", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(paper),
    ], check=True, capture_output=True)
    timeline = {
        "width": 360, "height": 640, "fps": 24,
        "clips": [{"clip_id": "paper", "asset_id": "paper", "audio_asset_id": "speaker",
                   "audio_trim_in_ms": 250, "media_type": "video", "duration_ms": 1000,
                   "trim_in_ms": 0, "trim_out_ms": 1000}],
        "overlays": [{"asset_id": "speaker", "mode": "speaker_pip", "trim_in_ms": 500,
                      "start_ms": 250, "duration_ms": 750, "x": 10, "y": 20, "width": 80, "height": 120}],
    }

    video_processor.render_timeline_document(
        timeline, lambda asset_id: {"paper": paper, "speaker": speaker}[asset_id], output,
    )
    def pixel(x, y, time_s):
        return subprocess.run([
            video_processor.ffmpeg_bin, "-v", "error", "-ss", str(time_s), "-i", str(output), "-frames:v", "1",
            "-vf", f"crop=1:1:{x}:{y},format=rgb24", "-f", "rawvideo", "pipe:1",
        ], check=True, capture_output=True).stdout

    inside, before, outside = pixel(50, 80, 0.5), pixel(50, 80, 0.1), pixel(200, 200, 0.5)
    assert inside[0] > 150 and inside[1] < 100
    assert before[1] > 60 and before[0] < 100
    assert outside[1] > 60 and outside[0] < 100
    assert audio_processor.probe_audio(output)["codec_name"] != "unknown"


def test_raw_tts_caps_video_retiming_at_speed_limits_without_changing_voice(tmp_path):
    import wave
    import numpy as np
    import subprocess
    from src.modules.media_studio.video_processor import VOICE_SPEED_MAX, VOICE_SPEED_MIN, video_processor
    from src.schemas.contracts import TimelineAudioTrack, TimelineClip, TimelineDocument, TimelineMediaType

    video = tmp_path / "video.mp4"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=360x640:r=24:d=10", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-t", "10", str(video),
    ], check=True, capture_output=True)
    voice = tmp_path / "voice.wav"
    with wave.open(str(voice), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(np.zeros(int(7.0 * 24000), dtype="<i2").tobytes())
    timeline = TimelineDocument(
        width=360, height=640, fps=24,
        clips=[TimelineClip(
            clip_id="s1", asset_id="video", media_type=TimelineMediaType.VIDEO,
            start_ms=0, duration_ms=10000, trim_in_ms=0, trim_out_ms=10000,
        )],
        voice_track=TimelineAudioTrack(asset_id="voice", duration_ms=7000),
    )

    fast_path = tmp_path / "capped_fast_video.mp4"
    fast_meta = video_processor.render_timeline_document(
        timeline, lambda asset_id: video if asset_id == "video" else voice,
        fast_path, preserve_voice_audio=True,
    )
    assert fast_meta["video_playback_speed"] == VOICE_SPEED_MAX
    assert abs(fast_meta["duration_seconds"] - 10 / VOICE_SPEED_MAX) <= 0.1
    assert abs(fast_meta["voice_audio_duration_seconds"] - 7.0) <= 0.1
    assert abs(fast_meta["silent_tail_seconds"] - (10 / VOICE_SPEED_MAX - 7.0)) <= 0.1

    long_voice = tmp_path / "long_voice.wav"
    with wave.open(str(long_voice), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(np.zeros(int(12.4 * 24000), dtype="<i2").tobytes())
    slow_meta = video_processor.render_timeline_document(
        timeline, lambda asset_id: video if asset_id == "video" else long_voice,
        tmp_path / "capped_slow_video.mp4", preserve_voice_audio=True,
    )
    assert slow_meta["video_playback_speed"] == VOICE_SPEED_MIN
    assert abs(slow_meta["duration_seconds"] - 12.4) <= 0.1
    assert abs(slow_meta["frozen_tail_seconds"] - (12.4 - 10 / VOICE_SPEED_MIN)) <= 0.1


def test_full_migration_rollback_preserves_content_video_records(tmp_path, monkeypatch):
    from src import database
    from src.models.entities import ContentVideoPlan

    engine = create_engine(f"sqlite:///{tmp_path / 'rollback.db'}")
    Session = sessionmaker(bind=engine)
    try:
        monkeypatch.setattr(migration_runner, "engine", engine)
        monkeypatch.setattr(database, "SessionLocal", Session)
        migration_runner.migration_up()
        with Session() as db:
            db.add(ContentVideoPlan(
                id="plan-1", workspace_id="workspace-1", project_id="project-1", revision=1,
                source_content="content", content_sha256="content-hash", target_duration_seconds=30,
                style_snapshot_json="{}", style_snapshot_sha256="style-hash",
                storyboard_json="{}", storyboard_sha256="storyboard-hash", llm_model="test", created_by="creator-1",
            ))
            db.commit()

        with pytest.raises(RuntimeError, match="Cannot rollback content-video tables"):
            migration_runner.migration_down()

        with Session() as db:
            assert db.query(ContentVideoPlan).count() == 1
        assert "content_video_plans" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_storyboard_requires_ordered_shots_covering_target_duration():
    storyboard = parse_storyboard(
        '{"title":"Demo","narration":"Lời đọc","continuity_anchor":"Một nhân vật cố định mặc áo xanh trong studio navy, ánh sáng mềm.","shots":['
        '{"shot_id":"s1","scene":"Mở đầu","narration":"Lời mở đầu","prompt":"Cảnh đầu","duration_seconds":10},'
        '{"shot_id":"s2","scene":"Thân bài","narration":"Lời giữa","prompt":"Cảnh giữa","duration_seconds":10},'
        '{"shot_id":"s3","scene":"Kết luận","narration":"Lời kết","prompt":"Cảnh cuối","duration_seconds":10}]}',
        target_duration_seconds=30,
    )

    assert [shot.shot_id for shot in storyboard.shots] == ["s1", "s2", "s3"]
    assert sum(shot.duration_seconds for shot in storyboard.shots) == 30
    prompts = [build_shot_prompt({"style_name": "Studio", "visual_rules": "Consistent cinematic look", "palette": ["navy"]}, shot, storyboard.continuity_anchor) for shot in storyboard.shots]
    assert all(storyboard.continuity_anchor in prompt for prompt in prompts)
    assert all("tùy chọn" in prompt and "clip im lặng vẫn chấp nhận" in prompt for prompt in prompts)
    assert CreateRunRequest(plan_id="plan-1", idempotency_key="native-flow-audio").voice_asset_id is None


def test_twenty_second_storyboard_is_accepted_by_api_and_planner():
    raw = (
        '{"title":"RAG","narration":"Tìm đúng tài liệu trước khi trả lời.",'
        '"continuity_anchor":"Một trợ lý giấy xanh navy đứng cạnh tủ tài liệu trong studio sáng.","shots":['
        '{"shot_id":"s1","scene":"Tìm kiếm","narration":"Tìm tài liệu liên quan.","prompt":"Tài liệu được truy xuất","duration_seconds":8},'
        '{"shot_id":"s2","scene":"Tạo câu trả lời","narration":"Tạo câu trả lời có căn cứ.","prompt":"Câu trả lời gắn với nguồn","duration_seconds":6},'
        '{"shot_id":"s3","scene":"Kết luận","narration":"Đó là RAG.","prompt":"Nguồn và kết quả bên nhau","duration_seconds":6}]}'
    )

    storyboard = parse_storyboard(raw, target_duration_seconds=20)
    plan_request = CreatePlanRequest(content="RAG truy xuất tri thức liên quan rồi mới tạo câu trả lời có căn cứ.", target_duration_seconds=20)

    assert sum(shot.duration_seconds for shot in storyboard.shots) == plan_request.target_duration_seconds == 20


def test_project_history_returns_latest_run_and_its_storyboard(monkeypatch):
    from src.models.entities import ContentVideoPlan, ContentVideoRun
    from src.modules.tao_video_noi_dung import service

    latest_run = SimpleNamespace(plan_id="plan-with-video")
    latest_plan = SimpleNamespace(id="plan-with-video")

    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *_conditions):
            return self

        def order_by(self, *_ordering):
            return self

        def first(self):
            return latest_run if self.model is ContentVideoRun else latest_plan

    class Db:
        def query(self, model):
            return Query(model)

    monkeypatch.setattr(service, "_project", lambda *_args: None)
    monkeypatch.setattr(service, "_response", lambda plan: {"id": plan.id})
    monkeypatch.setattr(service, "_run_response", lambda run: {"plan_id": run.plan_id})

    result = service.get_latest_history(Db(), "project-1", "workspace-1")

    assert result == {"plan": {"id": "plan-with-video"}, "run": {"plan_id": "plan-with-video"}}


def test_create_plan_explains_gateway_rate_limit(monkeypatch):
    from fastapi import HTTPException
    from src.modules.llm.client import LLMResponseError
    from src.modules.tao_video_noi_dung import service

    class EnabledLLM:
        is_enabled = True

    monkeypatch.setattr(service, "_project", lambda *_args: None)
    monkeypatch.setattr(service.LLMClient, "from_db", classmethod(lambda _cls, _db: EnabledLLM()))
    monkeypatch.setattr(
        service,
        "generate_storyboard",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(LLMResponseError("quota", error_code="UPSTREAM_RATE_LIMITED")),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.create_plan(None, "project-1", "workspace-1", "user-1", CreatePlanRequest(
            content="Nội dung đủ dài để tạo video minh họa về cách truy xuất dữ liệu RAG.",
            target_duration_seconds=20,
        ))

    assert exc_info.value.detail["error_code"] == "UPSTREAM_RATE_LIMITED"
    assert "Hạn mức" in exc_info.value.detail["message"]


def _recording_storyboard_client():
    brief = {
        "pains": [{"id": "pain-1", "text": "Khách hàng chờ câu trả lời có căn cứ", "source": "content"}],
    }
    narration = (
        "Doanh nghiệp nhận nhiều câu hỏi nhưng tài liệu nằm ở nhiều nơi. "
        "Nhân viên phải tìm nguồn, kiểm tra rồi mới trả lời. "
        "Cách làm tốn thời gian và dễ bỏ sót căn cứ."
    )
    storyboard = {
        "title": "Tìm đúng nguồn",
        "narration": narration,
        "continuity_anchor": "Trợ lý giấy màu xanh navy bên cạnh tủ tài liệu trong cùng một căn phòng.",
        "shots": [
            {
                "shot_id": "s1", "scene": "Tìm tài liệu", "narration": narration,
                "prompt": "Một thẻ giấy rời khỏi kệ và trượt đến bàn làm việc.",
                "duration_seconds": 10, "continues_previous": False, "prompt_contract_version": 4,
                "beat": "PAIN", "message_ids": ["pain-1"], "shot_kind": "FLOW_ORIGAMI",
                "action_beats": [{"start_s": 0, "end_s": 10, "action": "Thẻ giấy rời khỏi kệ, trượt đến bàn rồi dừng cạnh trợ lý."}],
            },
            {
                "shot_id": "s2", "scene": "Đối chiếu nguồn", "narration": narration,
                "prompt": "Trợ lý giấy mở thẻ tài liệu và đặt cạnh câu trả lời.",
                "duration_seconds": 10, "continues_previous": False, "prompt_contract_version": 4,
                "beat": "SOLUTION", "message_ids": ["pain-1"], "shot_kind": "FLOW_ORIGAMI",
                "action_beats": [{"start_s": 0, "end_s": 10, "action": "Trợ lý mở thẻ, đối chiếu tài liệu rồi đặt thẻ cạnh câu trả lời."}],
            },
        ],
    }

    narration_by_shot = [
        "Mỗi ngày doanh nghiệp nhận nhiều câu hỏi, tài liệu quan trọng nằm rải rác nhiều nơi.",
        "Nhân viên mở từng hệ thống để tìm tài liệu, kiểm tra nguồn rồi mới trả lời khách hàng.",
        "Quy trình tìm kiếm thủ công khiến phản hồi chậm, đôi khi bỏ sót nguồn quan trọng cần thiết.",
        "RAG truy xuất tài liệu liên quan trước, sau đó tạo câu trả lời có căn cứ từ nguồn tìm thấy.",
    ]
    storyboard["shots"] = [
        {
            **storyboard["shots"][index % 2],
            "shot_id": f"s{index + 1}",
            "scene": f"Cảnh {index + 1}",
            "narration": narration,
            "prompt": f"Mô tả cảnh origami chi tiết số {index + 1}.",
            "duration_seconds": 10,
            "action_beats": [{"start_s": 0, "end_s": 10, "action": f"Hành động origami số {index + 1}."}],
        }
        for index, narration in enumerate(narration_by_shot)
    ]

    class RecordingClient:
        max_output_tokens = 6000

        def __init__(self):
            self.calls = 0
            self.messages = []

        def complete(self, messages, max_tokens):
            self.messages = messages
            self.calls += 1
            result = brief if self.calls == 1 else storyboard
            return SimpleNamespace(content=json.dumps(result, ensure_ascii=False), model="test-model")

    return RecordingClient()


def test_storyboard_prompt_generates_short_detailed_shots():
    client = _recording_storyboard_client()
    storyboard, _ = generate_storyboard(
        "RAG truy xuất tài liệu trước khi trả lời có căn cứ.",
        20,
        {"style_name": "Origami", "visual_rules": "Phong cách giấy thống nhất.", "palette": ["navy"]},
        client,
    )

    request = json.loads(client.messages[1]["content"])
    assert request["target_duration_seconds"] == 20
    assert len(storyboard.shots) == 4
    assert all(3 <= shot.duration_seconds <= 6 for shot in storyboard.shots)
    assert sum(shot.duration_seconds for shot in storyboard.shots) == 20
    assert "từ 3 đến 6 giây" in client.messages[0]["content"].lower()


def test_new_content_video_style_uses_baha_identity_and_editorial_motion():
    from src.modules.tao_video_noi_dung.service import _CONTENT_VIDEO_STYLE_SNAPSHOT, _PILOT_STYLE_SNAPSHOT

    shot = StoryboardShot(
        shot_id="s1", scene="Báo giá nằm chờ phản hồi", narration="Báo giá chưa có hồi âm.",
        prompt="Đường chỉ nối báo giá với thẻ việc cần theo dõi.", duration_seconds=5,
        prompt_contract_version=4, shot_kind="FLOW_ORIGAMI", beat="PAIN", continues_previous=False,
        action_beats=[{"start_s": 0, "end_s": 5, "action": "Đường chỉ lần theo báo giá rồi nối với thẻ theo dõi đang bật lên."}],
    )
    prompt = build_shot_prompt(
        _CONTENT_VIDEO_STYLE_SNAPSHOT.model_dump(mode="json"), shot,
        "Bàn giấy sáng, xanh dương BAHA và đường chỉ vàng.",
    ).casefold()

    assert _PILOT_STYLE_SNAPSHOT.style_name == _CONTENT_VIDEO_STYLE_SNAPSHOT.style_name
    assert "xanh navy" in prompt and "vàng kim" in prompt and "đỏ điểm nhấn" in prompt
    assert "không dàn dựng như slide" in prompt
    assert "lớp chuyển động có chủ đích" in prompt
    assert "đường chỉ lần theo báo giá" in prompt


def test_baha_diagrams_default_to_hyperframes_and_keep_legacy_and_fallback(monkeypatch, tmp_path):
    from src.modules.tao_video_noi_dung import render_engines
    from src.modules.tao_video_noi_dung.planner import UiScene
    from src.modules.tao_video_noi_dung.service import _CONTENT_VIDEO_STYLE_SNAPSHOT

    monkeypatch.delenv("CONTENT_VIDEO_RENDER_ENGINE", raising=False)
    style = _CONTENT_VIDEO_STYLE_SNAPSHOT.model_dump(mode="json")
    legacy_style = {"style_name": "Origami giấy gấp", "visual_rules": "Cảnh giấy.", "palette": ["navy"]}
    assert render_engines.selected_engine(style) == "hyperframes"
    assert render_engines.selected_engine(legacy_style) == "playwright"

    scene = UiScene.model_validate({"layout": "BEFORE_AFTER", "diagram": {
        "title": "Đơn hàng", "simulated": False,
        "docs": [{"title": "Trước", "label": "Đơn", "value": "100"}, {"title": "Sau", "label": "Đơn", "value": "60"}],
        "diff_label": "Giảm 40", "on": {"before": "trước", "after": "sau", "delta": "giảm 40"},
    }})
    called = []
    monkeypatch.setattr(render_engines, "BACKENDS", {"hyperframes": lambda *_args: (called.append("hyperframes") or {"width": 1080})})
    result = render_engines.render_scene(scene, style, 5, "9:16", tmp_path / "diagram.mp4")
    assert called == ["hyperframes"]
    assert result["render_engine"] == "hyperframes"

    monkeypatch.setattr(render_engines, "render_ui_scene", lambda *_args, **_kwargs: {"width": 1080})
    chat = UiScene.model_validate({"layout": "CHAT", "messages": [
        {"role": "customer", "text": "Cần tìm tài liệu.", "at_s": 0},
        {"role": "ai", "text": "Đây là nguồn phù hợp.", "at_s": 2},
    ]})
    result = render_engines.render_scene(chat, style, 5, "9:16", tmp_path / "chat.mp4")
    assert result["render_engine"] == "playwright"

    monkeypatch.setenv("CONTENT_VIDEO_RENDER_ENGINE", "playwright")
    assert render_engines.selected_engine(style) == "playwright"


def test_baha_hyperframes_diagrams_use_midnight_champagne_brand_surface():
    from src.modules.tao_video_noi_dung.planner import UiScene
    from src.modules.tao_video_noi_dung.service import _CONTENT_VIDEO_STYLE_SNAPSHOT
    from src.modules.tao_video_noi_dung.ui_sim import _scene_html, hyperframes_composition_html
    from src.modules.tao_video_noi_dung.hf_scenes import BASE_CSS

    scene = UiScene.model_validate({"layout": "BEFORE_AFTER", "diagram": {
        "title": "Đơn hàng", "simulated": False,
        "docs": [{"title": "Trước", "label": "Đơn", "value": "100"},
                  {"title": "Sau", "label": "Đơn", "value": "60"}],
        "diff_label": "Giảm 40", "on": {"before": "trước", "after": "sau", "delta": "giảm 40"},
    }})
    html = hyperframes_composition_html(scene, "Trước 100, sau 60, giảm 40", 5, aspect_ratio="9:16").casefold()

    assert any("#0b0f17" in s.casefold() for s in [_CONTENT_VIDEO_STYLE_SNAPSHOT.visual_rules, html, BASE_CSS])
    assert any("#d9b26a" in color.casefold() for color in _CONTENT_VIDEO_STYLE_SNAPSHOT.palette)
    assert "#0b0f17" in html and "#d9b26a" in html and "#0562af" in html
    assert "panelglass" in html and "fedropshadow" in html
    assert "#faf5e9" not in html

    chat = UiScene.model_validate({"layout": "CHAT", "messages": [
        {"role": "customer", "text": "Need a clear next step.", "at_s": 0},
        {"role": "ai", "text": "Assign one owner.", "at_s": 2},
    ]})
    ui_html = _scene_html(chat, {}).casefold()
    assert "#0b0f17" in ui_html and "#d9b26a" in ui_html and "#0562af" in ui_html
    assert "#f2eee6" in BASE_CSS.casefold() and "#d9b26a" in BASE_CSS.casefold()
    assert "#faf5e9" not in BASE_CSS.casefold()


def test_storyboard_generation_treats_style_snapshot_as_visual_source_of_truth():
    client = _recording_storyboard_client()
    generate_storyboard(
        "Báo giá cần người phụ trách và bước theo dõi rõ ràng.",
        20,
        {"style_name": "BAHA Editorial Motion", "visual_rules": "Cảnh kể chuyện giàu chiều sâu.", "palette": ["xanh dương BAHA"]},
        client,
    )

    prompt = client.messages[0]["content"].casefold()
    assert "style_snapshot là nguồn chuẩn về phong cách hình ảnh" in prompt
    assert "không mặc định origami" in prompt
    assert "ưu tiên ui_sim sơ đồ động để hyperframes" in prompt
    assert "before_after" in prompt and "kpi_cards" in prompt and "versus_list" in prompt


def test_vertical_storyboard_accepts_hyperframes_native_portrait_diagrams():
    from src.modules.tao_video_noi_dung.brief import ContentBrief
    from src.modules.tao_video_noi_dung.planner import Storyboard, StoryboardShot, UiScene, _soft_problems

    narration = "Trước là một trăm đơn, sau còn sáu mươi đơn, giảm bốn mươi đơn."
    shot = StoryboardShot(
        shot_id="s1", scene="So sánh số đơn", narration=narration, prompt="Hai trạng thái hiện ra rồi thay đổi.",
        duration_seconds=5, continues_previous=False, prompt_contract_version=4, beat="INSIGHT", message_ids=["pain-1"], shot_kind="UI_SIM",
        ui_scene=UiScene.model_validate({"layout": "BEFORE_AFTER", "diagram": {
            "title": "Đơn hàng", "simulated": False,
            "docs": [{"title": "Trước", "label": "Đơn", "value": "100"}, {"title": "Sau", "label": "Đơn", "value": "60"}],
            "diff_label": "Giảm 40", "on": {"before": "trước", "after": "sau", "delta": "giảm bốn mươi"},
        }}),
    )
    storyboard = Storyboard(
        title="So sánh", narration=narration, continuity_anchor="Cảnh đồ họa xanh dương, đỏ và vàng.", shots=[shot],
        brief=ContentBrief(pains=[{"id": "pain-1", "text": "Đơn hàng giảm.", "source": "content"}]),
    )

    problems = _soft_problems(storyboard, "9:16")

    assert not any(problem.startswith("DIAGRAM_REQUIRES_16_9") for problem in problems)


def test_brand_end_card_places_official_logo_without_changing_video_duration(tmp_path):
    video_path = tmp_path / "video.mp4"
    pixel_path = tmp_path / "brand-end-card-center.rgb"
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=navy:s=360x640:r=30:d=2",
        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_path),
    ], capture_output=True, text=True, check=True)

    assert _add_brand_end_card(video_path) == pytest.approx(2)

    meta = video_processor.probe_video(video_path)
    assert meta["duration_seconds"] == pytest.approx(2, abs=0.1)
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-ss", "1", "-i", str(video_path),
        "-vf", "crop=1:1:180:320,format=rgb24", "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", str(pixel_path),
    ], capture_output=True, text=True, check=True)
    center = pixel_path.read_bytes()
    assert center[2] >= center[1] >= center[0] and (center[2] - center[0] >= 10 or center[2] > center[0] + 40)
    decoded = run_media_command(
        [video_processor.ffmpeg_bin, "-v", "error", "-i", str(video_path), "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    assert decoded.returncode == 0 and not decoded.stderr.strip()


def test_storyboard_prompts_prevent_distortion_and_allow_optional_flow_audio():
    client = _recording_storyboard_client()
    storyboard, _ = generate_storyboard(
        "RAG tìm nguồn trước khi trả lời.",
        20,
        {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"]},
        client,
    )
    system_prompt = client.messages[0]["content"].lower()
    shot_prompt = build_shot_prompt(
        {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"]},
        storyboard.shots[0],
        storyboard.continuity_anchor,
    ).lower()

    assert "hợp đồng v4" in system_prompt
    assert "action_beats liên tiếp phủ kín" in system_prompt
    assert "không biến hình" in system_prompt
    assert "flow_prompt_en" not in system_prompt
    assert "action_beats" in system_prompt
    assert "không biến hình" in shot_prompt
    assert "không nhân đôi" in shot_prompt
    assert "âm thanh flow tùy chọn" in shot_prompt
    assert "nếu flow tạo giọng dẫn thì đọc nguyên văn bằng tiếng việt" in shot_prompt
    assert "doanh nghiệp nhận nhiều câu hỏi" in shot_prompt
    assert "bắt buộc bật" not in shot_prompt
    no_flow_narration = build_shot_prompt(
        {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"]},
        storyboard.shots[0], storyboard.continuity_anchor, include_narration_audio=False,
    ).lower()
    assert "âm thanh flow tùy chọn" in no_flow_narration
    assert "clip im lặng vẫn chấp nhận" in no_flow_narration
    assert "giọng dẫn đọc nguyên văn" not in no_flow_narration


def test_flow_prompt_uses_vietnamese_and_ignores_legacy_english_prompt():
    shot = StoryboardShot(
        shot_id="s1", scene="Trợ lý origami chào khán giả", narration="Xin chào.",
        prompt="Mô hình trợ lý AI origami hoàn chỉnh vẫy tay một lần.", flow_prompt_en=(
            "A real person folds paper with bare hands."
        ), duration_seconds=7,
    )

    prompt = build_shot_prompt(
        {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"]},
        shot,
        "Một nhân vật giấy cố định trong studio navy.",
    )

    assert "A real person" not in prompt
    assert "mô hình origami đã gấp thành hình hoàn chỉnh" in prompt
    assert "không quay người thật, bàn tay hoặc ngón tay" in prompt.lower()
    assert "không mô tả hoặc thể hiện thao tác gấp giấy" in prompt.lower()
    assert "Không tạo lời nói tiếng Anh" in prompt
    assert "Xin chào." not in prompt
    assert "flow_prompt_en" not in shot.model_dump()


@pytest.mark.parametrize(
    "raw, target",
    [
        ('{"title":"x","narration":"y","continuity_anchor":"Nhân vật và bối cảnh cố định xuyên suốt video.","shots":[]}', 30),
        ('{"title":"x","narration":"y","shots":[{"shot_id":"s1","scene":"A","narration":"a","prompt":"B","duration_seconds":10}]}', 30),
        ('{"title":"x","narration":"y","shots":[{"shot_id":"s1","scene":"A","narration":"a","prompt":"B","duration_seconds":11},{"shot_id":"s2","scene":"C","narration":"c","prompt":"D","duration_seconds":9},{"shot_id":"s3","scene":"E","narration":"e","prompt":"F","duration_seconds":10}]}', 30),
        ('{"title":"x","narration":"y","shots":[{"shot_id":"s1","scene":"A","narration":"a","prompt":"B","duration_seconds":10},{"shot_id":"s1","scene":"C","narration":"c","prompt":"D","duration_seconds":10},{"shot_id":"s3","scene":"E","narration":"e","prompt":"F","duration_seconds":10}]}', 30),
        ('{"title":"x","narration":"y","shots":[{"shot_id":"s1","scene":"A","narration":"a","prompt":"B","duration_seconds":10},{"shot_id":"s2","scene":"C","narration":"c","prompt":"D","duration_seconds":10},{"shot_id":"s3","scene":"E","narration":"e","prompt":"F","duration_seconds":10}]}', 19),
    ],
)
def test_storyboard_rejects_invalid_shot_lists(raw: str, target: int):
    with pytest.raises(ValueError):
        parse_storyboard(raw, target_duration_seconds=target)


def test_video_qc_rejects_wrong_dimensions_and_duration():
    issues = evaluate_video_qc(
        {"width": 720, "height": 1280, "codec_name": "h264", "duration_seconds": 29.0, "frame_rate": 30.0},
        expected_duration_seconds=30,
        decode_ok=True,
    )

    assert "DIMENSIONS" in issues
    assert "DURATION" in issues
    assert "DECODE" not in issues


def test_flow_pre_submit_failure_is_resumable_without_reconciliation():
    run = SimpleNamespace(status="RUNNING", error_code=None, error_message=None, finished_at=None, steps_json="")
    steps = [{"shot_id": "shot_01", "state": "SUBMITTING"}, {"shot_id": "shot_02", "state": "READY"}]

    assert _mark_flow_setup_blocked(run, steps, RuntimeError("video mode control missing"))
    assert run.status == "BLOCKED_FLOW_SETUP"
    assert run.error_code == "FLOW_REQUEST_NOT_SUBMITTED"
    assert run.finished_at is None
    assert steps[0]["state"] == "READY"
    assert not _mark_flow_setup_blocked(run, [{"state": "NEEDS_RECONCILIATION"}], RuntimeError("unknown submission"))


def test_flow_credit_block_is_reported_without_submission():
    run = SimpleNamespace(status="RUNNING", error_code=None, error_message=None, finished_at=None, steps_json="")
    steps = [{"shot_id": "shot_04", "state": "SUBMITTING"}]

    assert _mark_flow_setup_blocked(run, steps, RuntimeError("FLOW_CREDITS_INSUFFICIENT: shot chưa được gửi"))
    assert run.status == "BLOCKED_FLOW_SETUP"
    assert run.error_code == "FLOW_CREDITS_INSUFFICIENT"
    assert steps[0]["state"] == "READY"


@pytest.mark.parametrize("flow_native_audio", [True, False])
@pytest.mark.parametrize("with_tts_voice", [True, False])
@pytest.mark.parametrize("include_subtitles", [True, False])
def test_content_video_render_tracks_native_audio_and_tts_subtitles(monkeypatch, tmp_path, flow_native_audio, with_tts_voice, include_subtitles):
    from src.models.entities import MediaAsset, TimelineVersion
    from src.modules.tao_video_noi_dung import runner

    shot_assets = {
        f"shot-{index}": SimpleNamespace(
            id=f"shot-{index}", sha256=f"hash-{index}", duration_ms=10000,
            workspace_id="ws", project_id="project",
        )
        for index in range(1, 4)
    }

    class Query:
        def __init__(self, model):
            self.model = model
            self.asset_id = None

        def filter(self, *criteria):
            for criterion in criteria:
                if getattr(getattr(criterion, "left", None), "key", None) == "id":
                    self.asset_id = criterion.right.value
            return self

        def order_by(self, *_args):
            return self

        def first(self):
            return None if self.model is TimelineVersion else shot_assets.get(self.asset_id)

    class DB:
        def __init__(self):
            self.added = []

        def query(self, model):
            return Query(model)

        def add(self, item):
            self.added.append(item)

        def commit(self):
            pass

    captured = {}
    def render(timeline, _resolver, output_path, transition_seconds, caption_style, preserve_voice_audio=False, sfx_cues=None, **_kwargs):
        captured["timeline"] = timeline
        captured["transition_seconds"] = transition_seconds
        captured["caption_style"] = caption_style
        captured["preserve_voice_audio"] = preserve_voice_audio
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"rendered video")
        return {"flow_native_audio": flow_native_audio, "duration_seconds": 30.0}

    voice_asset = SimpleNamespace(
        id="tts-asset", sha256="tts-hash", source_product="CONTENT_VIDEO_TTS", duration_ms=30000,
    )
    voice_input = (voice_asset, tmp_path / "tts.wav") if with_tts_voice else None
    monkeypatch.setattr(runner, "_voice_input", lambda *_args: voice_input)
    monkeypatch.setattr(runner, "get_workspace_storage_dir", lambda _workspace: tmp_path)
    monkeypatch.setattr(runner.video_processor, "render_timeline_document", render)
    monkeypatch.setattr(runner.video_processor, "probe_video", lambda _path: {
        "width": 1920, "height": 1080, "codec_name": "h264", "frame_rate": 30.0,
        "duration_seconds": 30.0,
    })
    monkeypatch.setattr(runner, "_add_brand_end_card", lambda _path: 3.0)
    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stderr=""))
    monkeypatch.setattr(
        runner.audio_processor, "verify_audio_qc",
        lambda *_args, **_kwargs: {"passed": True},
    )
    monkeypatch.setattr(
        runner.audio_processor, "probe_audio",
        lambda _path: {"codec_name": "aac", "duration_seconds": 30.0},
    )
    def _asr_unavailable(*_args):
        raise runner.VietsubError("VIETSUB_ASR_FAILED")

    monkeypatch.setattr(runner, "transcribe_words_cached", _asr_unavailable)
    monkeypatch.setattr(runner, "_write_export_package", lambda path, *_args: path.write_bytes(b"export"))

    shots = [SimpleNamespace(shot_id=f"shot-{index}", narration=f"Lời cảnh {index}", duration_seconds=10, prompt_contract_version=3, shot_kind="UI_SIM", ui_scene=None) for index in range(1, 4)]
    storyboard = SimpleNamespace(shots=shots)
    plan = SimpleNamespace(
        target_duration_seconds=30, style_snapshot_sha256="style-hash", source_content="source",
        storyboard_json="{}", style_snapshot_json='{"aspect_ratio":"16:9"}', id="plan", revision=1,
    )
    run = SimpleNamespace(
        id="run", workspace_id="ws", project_id="project", created_by="creator",
        voice_asset_id="tts-asset" if with_tts_voice else None,
        include_subtitles=include_subtitles,
        steps_json=json.dumps([
            {"tts_audio": {"duration_ms": 9500, "pause_after_ms": 500}},
            {"tts_audio": {"duration_ms": 9500, "pause_after_ms": 500}},
            {"tts_audio": {"duration_ms": 10000, "pause_after_ms": 0}},
        ]) if with_tts_voice else "[]",
        output_asset_ids_json="[]",
    )

    runner._render_and_qc(DB(), run, plan, storyboard, list(shot_assets))

    if with_tts_voice and include_subtitles:
        assert [(caption.text, caption.start_ms, caption.duration_ms) for caption in captured["timeline"].captions] == [
            ("Lời cảnh 1", 0, 10000), ("Lời cảnh 2", 10000, 10000), ("Lời cảnh 3", 20000, 10000),
        ]
    else:
        assert captured["timeline"].captions == []
    assert (captured["timeline"].width, captured["timeline"].height) == (1920, 1080)
    assert (captured["timeline"].voice_track is not None) is with_tts_voice
    assert captured["transition_seconds"] == 0.3
    assert captured["caption_style"] == "vietsub_karaoke_v2"
    assert captured["preserve_voice_audio"] is with_tts_voice
    report = json.loads(run.qc_report_json)
    assert report["voice_source"] == ("TTS" if with_tts_voice else "FLOW_NATIVE" if flow_native_audio else "NONE")
    assert report["flow_native_audio"] is flow_native_audio
    assert report["brand_end_card"]["duration_seconds"] == 3.0
    assert report["brand_end_card"]["logo_asset"] in ("logo_doc_mau.png", "logo_ngang_am_ban.png")
    assert report["speech_alignment"] == (
        "TTS_SHOT_TIMELINE" if with_tts_voice and include_subtitles else
        "DISABLED" if with_tts_voice else "NO_AUDIO_FOR_VIETSUB"
    )
    assert report["audio_qc"] == {
        "status": "RAW_TTS_PRESERVED", "reason": "LOUDNESS_NORMALIZATION_DISABLED", "passed": True,
    } if with_tts_voice else {
        "status": "SKIPPED",
        "reason": "FLOW_NATIVE_AUDIO" if flow_native_audio else "NO_AUDIO_SELECTED",
        "passed": True,
    }
    assert run.status == "COMPLETED"


def test_shot_qc_allows_provider_clip_longer_than_used_trim_but_rejects_short_clip():
    meta = {"width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 30.0}

    assert "DURATION" not in evaluate_shot_qc({**meta, "duration_seconds": 10.0}, used_duration_seconds=7)
    assert "DURATION" in evaluate_shot_qc({**meta, "duration_seconds": 6.0}, used_duration_seconds=7)


def test_shot_qc_accepts_native_flow_720p_when_aspect_ratio_matches():
    meta = {
        "width": 720, "height": 1280, "codec_name": "h264", "frame_rate": 24.0,
        "duration_seconds": 10.0,
    }

    assert "DIMENSIONS" not in evaluate_shot_qc(meta, used_duration_seconds=7, aspect_ratio="9:16")
    assert "DIMENSIONS" in evaluate_shot_qc(meta, used_duration_seconds=7, aspect_ratio="16:9")


def test_shot_qc_rejects_wrong_frame_rate():
    meta = {"width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 20.0, "duration_seconds": 10.0}

    assert "FRAME_RATE" in evaluate_shot_qc(meta, used_duration_seconds=10)


def test_shot_qc_rejects_decode_failure():
    meta = {"width": 1080, "height": 1920, "codec_name": "h264", "frame_rate": 30.0, "duration_seconds": 10.0}

    assert "DECODE" in evaluate_shot_qc(meta, used_duration_seconds=10, decode_ok=False)


def test_pipeline_rejects_reused_shot_media_hashes():
    assert _has_duplicate_shot_media(["a", "b", "a"])
    assert not _has_duplicate_shot_media(["a", "b", "c"])


def test_video_qc_accepts_user_selected_landscape_ratio():
    meta = {"width": 1920, "height": 1080, "codec_name": "h264", "frame_rate": 30.0, "duration_seconds": 10.0}

    assert evaluate_video_qc(meta, 10, decode_ok=True, aspect_ratio="16:9") == []


def test_plan_request_persists_user_selected_aspect_ratio():
    request = CreatePlanRequest.model_validate({
        "content": "Một chủ đề đủ dài để tạo video minh họa về công nghệ trí tuệ nhân tạo.",
        "target_duration_seconds": 30,
        "aspect_ratio": "16:9",
    })

    assert request.aspect_ratio == "16:9"
    with pytest.raises(ValueError):
        CreatePlanRequest.model_validate({
            "content": "Một chủ đề đủ dài để tạo video minh họa về công nghệ trí tuệ nhân tạo.",
            "target_duration_seconds": 30,
            "aspect_ratio": "1:1",
        })


def test_plan_request_cannot_override_server_style_profile():
    with pytest.raises(ValueError):
        CreatePlanRequest.model_validate({
            "content": "Một chủ đề có đủ độ dài để lập storyboard nhất quán cho video.",
            "target_duration_seconds": 30,
            "style_snapshot": {"style_name": "random", "visual_rules": "different style", "palette": ["pink"]},
        })


def _approved_harness_shot():
    style = {"style_name": "Pilot", "visual_rules": "Giữ cùng chủ thể và ánh sáng mềm.", "palette": ["navy"], "aspect_ratio": "16:9"}
    anchor = "Một người dẫn mặc áo navy trong studio sáng mềm xuyên suốt video."
    shot = StoryboardShot(
        shot_id="shot-1",
        scene="Mở đầu trong studio",
        narration="Lời dẫn mở đầu.",
        prompt="Người dẫn mở đầu chủ đề.",
        flow_prompt_en="A paper assistant introduces the subject with one small hand gesture.",
        duration_seconds=10,
    )
    storyboard_data = {"continuity_anchor": anchor}
    plan = SimpleNamespace(
        id="plan-1",
        revision=1,
        status="APPROVED",
        approved_by="reviewer-1",
        approved_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        workspace_id="workspace-1",
        project_id="project-1",
        storyboard_sha256=cong_harness.canonical_hash(storyboard_data),
        style_snapshot_sha256=cong_harness.canonical_hash(style),
        style_snapshot_json=json.dumps(style),
        storyboard_json=json.dumps(storyboard_data),
    )
    run = SimpleNamespace(
        id="run-1",
        workspace_id=plan.workspace_id,
        project_id=plan.project_id,
        plan_id=plan.id,
        voice_asset_id="voice-1",
        plan_revision=plan.revision,
        storyboard_sha256=plan.storyboard_sha256,
        style_snapshot_sha256=plan.style_snapshot_sha256,
        approval_sha256=cong_harness.approval_receipt_hash(plan),
        created_by="creator-1",
    )
    step = build_shot_receipt(
        run_id=run.id,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        plan=plan,
        voice_asset_id=run.voice_asset_id,
        shot=shot,
        style_snapshot=style,
        continuity_anchor=anchor,
    )
    step["state"] = "SUBMITTING"
    return run, plan, shot, step


def test_harness_dispatches_only_approved_immutable_shot_receipt(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    calls = []
    expected_asset = object()
    monkeypatch.setattr(
        cong_harness.video_orchestrator,
        "generate_video_scene",
        lambda **kwargs: calls.append(kwargs) or expected_asset,
    )

    result = dispatch_shot(db=object(), run=run, plan=plan, shot=shot, step=step)

    assert result is expected_asset
    assert len(calls) == 1
    assert calls[0]["prompt"] == step["prompt"]
    assert calls[0]["prompt_language"] == "vi"
    assert calls[0]["aspect_ratio"] == "16:9"
    assert calls[0]["include_audio"] is True
    assert calls[0]["project_id"] == run.project_id


def test_harness_accepts_persisted_cleaning_state_for_safe_resume():
    run, plan, shot, step = _approved_harness_shot()
    step["state"] = "CLEANING"

    assert cong_harness.verify_shot_receipt(run, plan, shot, step)["shot_id"] == shot.shot_id


def test_tts_render_output_does_not_change_immutable_flow_command():
    run, plan, shot, _ = _approved_harness_shot()
    run.tts_config_json = '{"provider":"VIE_NEU_V3_TURBO"}'
    step = build_shot_receipt(
        run_id=run.id, workspace_id=run.workspace_id, project_id=run.project_id,
        plan=plan, voice_asset_id=None, shot=shot,
        style_snapshot=json.loads(plan.style_snapshot_json), continuity_anchor="same subject",
        include_narration_audio=False,
    )
    original_hash = step["command_sha256"]
    run.voice_asset_id = "generated-tts-output"
    assert cong_harness.verify_shot_receipt(run, plan, shot, step)["voice_asset_id"] is None
    assert step["command_sha256"] == original_hash
    step["voice_asset_id"] = "unrelated-audio"
    with pytest.raises(RuntimeError, match="HARNESS_COMMAND_RECEIPT_INVALID"):
        cong_harness.verify_shot_receipt(run, plan, shot, step)


def test_harness_accepts_approved_prompt_snapshot_after_prompt_builder_changes(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    monkeypatch.setattr(cong_harness, "build_shot_prompt", lambda *args, **kwargs: "new prompt after approval")

    command = cong_harness.verify_shot_receipt(run, plan, shot, step)

    assert command["prompt"] == step["prompt"]


def test_harness_blocks_tampered_shot_receipt_before_provider_call(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    calls = []
    monkeypatch.setattr(cong_harness.video_orchestrator, "generate_video_scene", lambda **kwargs: calls.append(kwargs))
    step["prompt"] += " chuyển sang anime"

    with pytest.raises(RuntimeError, match="HARNESS_COMMAND_RECEIPT_INVALID"):
        dispatch_shot(db=object(), run=run, plan=plan, shot=shot, step=step)

    assert calls == []


def test_harness_binds_the_selected_voice_asset_before_provider_call(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    calls = []
    monkeypatch.setattr(cong_harness.video_orchestrator, "generate_video_scene", lambda **kwargs: calls.append(kwargs))
    step["voice_asset_id"] = "another-voice"

    with pytest.raises(RuntimeError, match="HARNESS_COMMAND_RECEIPT_INVALID"):
        dispatch_shot(db=object(), run=run, plan=plan, shot=shot, step=step)

    assert calls == []


def test_voice_preflight_rejects_audio_that_does_not_match_target_duration(monkeypatch, tmp_path):
    from src.modules.tao_video_noi_dung import runner

    voice_path = tmp_path / "voice.mp3"
    voice_path.write_bytes(b"audio fixture")
    asset = SimpleNamespace(
        id="voice-1", workspace_id="workspace-1", project_id="project-1",
        storage_key="voice.mp3", mime_detected="audio/mpeg", sha256=hashlib.sha256(voice_path.read_bytes()).hexdigest(),
    )
    query = SimpleNamespace(filter=lambda *args: query, first=lambda: asset)
    db = SimpleNamespace(query=lambda model: query)
    run = SimpleNamespace(id="run-1", voice_asset_id=asset.id, workspace_id=asset.workspace_id, project_id=asset.project_id)
    plan = SimpleNamespace(target_duration_seconds=30)
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr(runner.audio_processor, "probe_audio", lambda path: {"duration_seconds": 29, "codec_name": "mp3"})

    with pytest.raises(RuntimeError, match="VOICE_ASSET_DURATION_MISMATCH"):
        runner._voice_input(db, run, plan)


def test_voice_preflight_rejects_asset_bytes_that_do_not_match_recorded_hash(monkeypatch, tmp_path):
    from src.modules.tao_video_noi_dung import runner

    voice_path = tmp_path / "voice.mp3"
    voice_path.write_bytes(b"changed audio")
    asset = SimpleNamespace(
        id="voice-1", workspace_id="workspace-1", project_id="project-1",
        storage_key="voice.mp3", mime_detected="audio/mpeg", sha256="recorded-hash",
    )
    query = SimpleNamespace(filter=lambda *args: query, first=lambda: asset)
    db = SimpleNamespace(query=lambda model: query)
    run = SimpleNamespace(id="run-1", voice_asset_id=asset.id, workspace_id=asset.workspace_id, project_id=asset.project_id)
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)

    with pytest.raises(RuntimeError, match="VOICE_ASSET_HASH_MISMATCH"):
        runner._voice_input(db, run, SimpleNamespace(target_duration_seconds=30))


def test_export_package_contains_video_editable_plan_qc_and_hash_manifest(tmp_path):
    import zipfile
    from src.modules.tao_video_noi_dung.runner import _write_export_package
    from src.schemas.contracts import TimelineDocument

    video = tmp_path / "final.mp4"
    video.write_bytes(b"video fixture")
    package = tmp_path / "export.zip"
    run = SimpleNamespace(id="run-1", voice_asset_id=None)
    plan = SimpleNamespace(
        id="plan-1", revision=2, source_content="Nội dung nguồn", storyboard_json='{"shots":[]}',
        style_snapshot_sha256="style-hash",
    )
    report = {"status": "PASS", "acceptance_mode": "HYBRID", "speech_alignment": "NOT_MEASURED"}

    _write_export_package(
        package, video, run, plan, TimelineDocument(), report,
        [{"asset_id": "shot-1", "sha256": "shot-hash"}],
        [{"shot_id": "shot-1", "prompt": "Prompt", "command_sha256": "receipt-hash", "asset_id": "shot-1"}],
        None,
    )

    with zipfile.ZipFile(package) as archive:
        assert {"video/final.mp4", "plan/storyboard.json", "timeline/timeline.json", "production/shots.json", "qc/report.json", "manifest.json"} <= set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        qc_report = json.loads(archive.read("qc/report.json"))
        assert manifest["acceptance_mode"] == "HYBRID"
        assert manifest["voice_asset"] is None
        assert manifest["speech_alignment"] == "NOT_MEASURED"
        assert qc_report["acceptance_mode"] == "HYBRID"
        assert manifest["files"]["video/final.mp4"] == hashlib.sha256(video.read_bytes()).hexdigest()


def test_harness_blocks_changed_persisted_style_snapshot(monkeypatch):
    run, plan, shot, step = _approved_harness_shot()
    calls = []
    monkeypatch.setattr(cong_harness.video_orchestrator, "generate_video_scene", lambda **kwargs: calls.append(kwargs))
    plan.style_snapshot_json = json.dumps({"style_name": "Other", "visual_rules": "đổi style", "palette": ["pink"]})

    with pytest.raises(RuntimeError, match="APPROVED_PLAN_HASH_CHANGED"):
        dispatch_shot(db=object(), run=run, plan=plan, shot=shot, step=step)

    assert calls == []


def test_plan_approval_authorizes_the_persisted_plan_as_a_resource(monkeypatch):
    from src.config import settings

    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CONTENT_VIDEO_TEST_SELF_APPROVAL", "1")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "database_url", "sqlite:///./sin_content_e2e_test.db")
    plan = SimpleNamespace(
        id="plan-1",
        created_by="creator-1",
        revision=4,
        storyboard_sha256="storyboard-hash",
    )
    authorization = {}
    monkeypatch.setattr(content_video_router, "get_plan", lambda *args: plan)
    monkeypatch.setattr(
        content_video_router,
        "authorize_resource",
        lambda tenant, action, **resource: authorization.update(
            tenant=tenant, action=action, **resource
        ),
    )
    monkeypatch.setattr(content_video_router, "approve_plan", lambda *args, **_kwargs: "approved")
    tenant = SimpleNamespace(workspace_id="workspace-1", user_id="reviewer-1")

    result = content_video_router.approve_content_video_plan(
        "project-1", "plan-1", db=object(), tenant=tenant
    )

    assert result == "approved"
    assert authorization == {
        "tenant": tenant,
        "action": "media.approve",
        "resource_type": "content_video_plan",
        "resource_id": "plan-1",
        "workspace_id": "workspace-1",
        "creator_id": "creator-1",
        "artifact_version": 4,
        "content_hash": "storyboard-hash",
        "project_id": "project-1",
        "require_creator": True,
    }


def test_plan_creator_can_self_approve_only_in_explicit_e2e_test_mode(monkeypatch):
    plan = SimpleNamespace(id="plan-1", created_by="creator-1", revision=1, storyboard_sha256="hash")
    monkeypatch.setattr(content_video_router, "get_plan", lambda *args: plan)
    monkeypatch.setattr(content_video_router, "approve_plan", lambda *args, **_kwargs: "approved")
    monkeypatch.setattr(content_video_router, "authorize_resource", lambda *_args, **_kwargs: pytest.fail("test mode should allow self-approval"))
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("BAHA_AUTH_APP_ENV", "test")
    monkeypatch.setenv("BAHA_AUTH_ALLOW_SELF_APPROVAL_IN_TEST", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sin_content_e2e_test.db")
    monkeypatch.setenv("BAHA_AUTH_DATABASE_URL", "sqlite:///./baha_auth_e2e_test.db")
    tenant = SimpleNamespace(workspace_id="workspace-1", user_id="creator-1")

    assert content_video_router.approve_content_video_plan("project-1", "plan-1", db=object(), tenant=tenant) == "approved"


def test_local_dev_auth_bypass_allows_storyboard_creator_self_approval(monkeypatch):
    plan = SimpleNamespace(id="plan-1", created_by="dev-user", revision=1, storyboard_sha256="hash")
    approved = {}
    monkeypatch.setattr(content_video_router, "get_plan", lambda *args: plan)
    monkeypatch.setattr(content_video_router, "e2e_test_self_approval_enabled", lambda: False)
    monkeypatch.setattr(
        content_video_router,
        "authorize_resource",
        lambda *_args, **_kwargs: pytest.fail("local dev bypass must not invoke four-eyes authorization"),
    )
    monkeypatch.setattr(
        content_video_router,
        "approve_plan",
        lambda *args, **kwargs: approved.update(allow_self_approval=kwargs.get("allow_self_approval")) or "approved",
    )
    tenant = SimpleNamespace(workspace_id="workspace-1", user_id="dev-user", dev_auth_bypass=True)

    result = content_video_router.approve_content_video_plan("project-1", "plan-1", db=object(), tenant=tenant)

    assert result == "approved"
    assert approved == {"allow_self_approval": True}


def test_creator_can_edit_draft_storyboard_and_updates_hash(monkeypatch):
    from src.modules.tao_video_noi_dung.service import update_plan
    from src.modules.tao_video_noi_dung.planner import Storyboard

    original = Storyboard.model_validate({
        "title": "Bản AI", "narration": "Thoại cũ", "continuity_anchor": "Nhân vật origami xanh navy giữ nguyên xuyên suốt các cảnh.",
        "shots": [
            {"shot_id": "s1", "scene": "Cảnh cũ 1", "narration": "Thoại cũ 1", "prompt": "Cảnh origami thứ nhất.", "duration_seconds": 10},
            {"shot_id": "s2", "scene": "Cảnh cũ 2", "narration": "Thoại cũ 2", "prompt": "Cảnh origami thứ hai.", "duration_seconds": 10},
            {"shot_id": "s3", "scene": "Cảnh cũ 3", "narration": "Thoại cũ 3", "prompt": "Cảnh origami thứ ba.", "duration_seconds": 10},
        ],
    })
    plan = SimpleNamespace(
        id="plan-1", project_id="project-1", workspace_id="workspace-1", revision=1, status="DRAFT",
        source_content="Nội dung nguồn", content_sha256="content-hash", target_duration_seconds=30,
        style_snapshot_json='{"style_name":"Origami","visual_rules":"Quy tắc hình ảnh origami rõ ràng.","palette":["navy"],"aspect_ratio":"9:16"}',
        style_snapshot_sha256="style-hash", storyboard_json=original.model_dump_json(),
        storyboard_sha256="old-hash", llm_model="test", created_by="creator-1", approved_by=None,
        approved_at=None, created_at=datetime.now(timezone.utc),
    )

    class Query:
        def __init__(self, model): self.model = model
        def filter(self, *_args): return self
        def with_for_update(self): return self
        def first(self): return plan

    class DB:
        def query(self, model): return Query(model)
        def commit(self): pass
        def refresh(self, _plan): pass

    changed = original.model_copy(deep=True)
    changed.title = "Bản đã sửa"
    changed.shots[0].narration = "Thoại do người dùng viết lại"
    changed.narration = "Thoại do người dùng viết lại. Thoại cũ 2. Thoại cũ 3."
    before_hash = plan.storyboard_sha256

    result = update_plan(DB(), "project-1", "plan-1", "workspace-1", "creator-1", changed)

    assert result.storyboard.title == "Bản đã sửa"
    assert result.storyboard.shots[0].narration == "Thoại do người dùng viết lại"
    assert result.storyboard_sha256 != before_hash


def test_storyboard_edit_rejects_non_creator_and_changes_to_shot_timing():
    from fastapi import HTTPException
    from src.modules.tao_video_noi_dung.service import update_plan
    from src.modules.tao_video_noi_dung.planner import Storyboard

    storyboard = Storyboard.model_validate({
        "title": "Bản AI", "narration": "Thoại", "continuity_anchor": "Nhân vật origami xanh navy giữ nguyên xuyên suốt các cảnh.",
        "shots": [
            {"shot_id": f"s{i}", "scene": f"Cảnh {i}", "narration": f"Thoại {i}", "prompt": f"Cảnh origami số {i}.", "duration_seconds": 10}
            for i in range(1, 4)
        ],
    })
    plan = SimpleNamespace(id="plan-1", project_id="project-1", workspace_id="workspace-1", status="DRAFT", created_by="creator-1", storyboard_json=storyboard.model_dump_json())

    class Query:
        def filter(self, *_args): return self
        def with_for_update(self): return self
        def first(self): return plan
    class DB:
        def query(self, _model): return Query()

    with pytest.raises(HTTPException) as denied:
        update_plan(DB(), "project-1", "plan-1", "workspace-1", "other-user", storyboard)
    assert denied.value.status_code == 403

    changed = storyboard.model_copy(deep=True)
    changed.shots[0].duration_seconds = 9
    changed.shots[1].duration_seconds = 11
    with pytest.raises(HTTPException) as invalid:
        update_plan(DB(), "project-1", "plan-1", "workspace-1", "creator-1", changed)
    assert invalid.value.status_code == 422



def _content_video_test_database():
    from src.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def _seed_content_video_history(db, run_status="COMPLETED", unfinished_index=None, error_code=None):
    from src.models.entities import ContentVideoPlan, ContentVideoRun, MediaAsset, ProductionProject, Workspace
    from src.modules.tao_video_noi_dung.cong_harness import approval_receipt_hash, build_shot_receipt, canonical_hash
    from src.modules.tao_video_noi_dung.planner import Storyboard
    from src.modules.tao_video_noi_dung.service import _run_response

    style = {"style_name": "Origami", "visual_rules": "Quy tắc hình ảnh origami rõ ràng.", "palette": ["navy"], "aspect_ratio": "9:16"}
    storyboard = Storyboard.model_validate({
        "title": "Video thử nghiệm", "narration": "Lời một. Lời hai. Lời ba.",
        "continuity_anchor": "Nhân vật origami xanh navy giữ nguyên xuyên suốt các cảnh.",
        "shots": [
            {"shot_id": f"s{i}", "scene": f"Cảnh {i}", "narration": f"Lời {i}", "prompt": f"Cảnh origami số {i}.", "duration_seconds": 10}
            for i in range(1, 4)
        ],
    })
    db.add(Workspace(id="workspace-1", name="Workspace", slug="workspace-test"))
    db.add(ProductionProject(id="project-1", workspace_id="workspace-1", title="Dự án video", created_by="creator-1"))
    db.commit()
    plan = ContentVideoPlan(
        id="plan-1", workspace_id="workspace-1", project_id="project-1", revision=1, status="APPROVED",
        source_content="Nội dung nguồn dùng để kiểm tra revision và tạo video.", content_sha256="content-hash",
        target_duration_seconds=30, style_snapshot_json=json.dumps(style, ensure_ascii=False),
        style_snapshot_sha256=canonical_hash(style), storyboard_json=storyboard.model_dump_json(),
        storyboard_sha256=canonical_hash(storyboard.model_dump(mode="json")), llm_model="test",
        created_by="creator-1", approved_by="reviewer-1", approved_at=datetime(2026, 10, 26),
    )
    db.add(plan)
    db.commit()
    db.add_all([
        MediaAsset(
            id=f"asset-s{i}", workspace_id="workspace-1", project_id="project-1",
            storage_key=f"test/shot_{i}.mp4", sha256=f"sha256-shot-{i}", byte_size=10,
            mime_detected="video/mp4", source_product="GOOGLE_FLOW", created_by="creator-1",
        )
        for i in range(1, 4)
    ])
    db.commit()
    steps = [build_shot_receipt(
        run_id="run-1", workspace_id="workspace-1", project_id="project-1", plan=plan,
        voice_asset_id=None, shot=shot, style_snapshot=style,
        continuity_anchor=storyboard.continuity_anchor,
    ) for shot in storyboard.shots]
    for index, step in enumerate(steps):
        step.update({"state": "SUCCEEDED", "asset_id": f"asset-s{index + 1}"})
    steps[0]["flow_project_url"] = "https://flow.google.com/project/existing"
    if unfinished_index is not None:
        for index in range(unfinished_index, len(steps)):
            steps[index].update({"state": "READY", "asset_id": None})
        if run_status == "NEEDS_RECONCILIATION":
            steps[unfinished_index]["state"] = "NEEDS_RECONCILIATION"
    run = ContentVideoRun(
        id="run-1", workspace_id="workspace-1", project_id="project-1", plan_id=plan.id,
        plan_revision=plan.revision, storyboard_sha256=plan.storyboard_sha256,
        style_snapshot_sha256=plan.style_snapshot_sha256, approval_sha256=approval_receipt_hash(plan),
        idempotency_key="original-run-key", status=run_status,
        error_code=error_code,
        steps_json=json.dumps(steps, ensure_ascii=False),
        output_asset_ids_json=json.dumps([step["asset_id"] for step in steps if step["asset_id"]]),
        created_by="creator-1",
    )
    db.add(run)
    db.commit()
    return plan, storyboard, run


def test_owner_direct_creation_is_atomic_and_audited():
    from src.database import Base
    from src.models.entities import AuditEvent
    from src.modules.tao_video_noi_dung.service import create_run
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        plan, storyboard, previous = _seed_content_video_history(db)
        plan.status, plan.approved_by, plan.approved_at = "DRAFT", None, None
        db.commit()
        request = CreateRunRequest(plan_id=plan.id, idempotency_key="owner-direct-run")
        with pytest.raises(Exception) as denied:
            create_run(db, "project-1", "workspace-1", "creator-1", request)
        assert denied.value.status_code == 409
        invalid = request.model_copy(update={"voice_asset_id": "missing"})
        with pytest.raises(Exception):
            create_run(db, "project-1", "workspace-1", "creator-1", invalid, allow_direct_creation=True)
        assert plan.status == "DRAFT"
        result = create_run(db, "project-1", "workspace-1", "creator-1", request, allow_direct_creation=True)
        assert result.status == "QUEUED"
        assert plan.approved_by == "creator-1"
        assert create_run(db, "project-1", "workspace-1", "creator-1", request, allow_direct_creation=True).id == result.id
        event = db.query(AuditEvent).filter_by(event_type="OWNER_DIRECT_CONTENT_VIDEO").one()
        assert json.loads(event.details)["storyboard_sha256"] == plan.storyboard_sha256


def test_resume_account_switch_keeps_completed_shots_and_clears_unsent_project():
    from src.database import Base
    from src.modules.flow_sessions.service import create_profile
    from src.modules.tao_video_noi_dung.service import resume_run
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        plan, storyboard, run = _seed_content_video_history(db, run_status="BLOCKED_FLOW_SETUP", unfinished_index=1)
        old = create_profile(db, "workspace-1", "Old account", "creator-1")
        new = create_profile(db, "workspace-1", "New account", "creator-1")
        steps = json.loads(run.steps_json)
        for step in steps:
            step['flow_profile_id'] = old.id
            step['flow_project_url'] = 'https://flow.google.com/project/old'
        run.steps_json = json.dumps(steps)
        db.commit()
        result = resume_run(db, "project-1", run.id, "workspace-1", profile_id=new.id)
        assert result.steps[0]['asset_id'] == 'asset-s1'
        assert result.steps[0]['flow_profile_id'] == old.id
        assert result.steps[0]['flow_project_url'].endswith('/old')
        assert result.steps[1]['flow_profile_id'] == new.id
        assert not result.steps[1].get('flow_project_url')
        assert result.status == "QUEUED"


def test_retry_run_reuses_completed_shots_and_regenerates_only_selected_shot():
    from src.modules.tao_video_noi_dung.contracts import RetryRunRequest
    from src.modules.tao_video_noi_dung.service import retry_run

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(db)
            result = retry_run(db, "project-1", "run-1", "workspace-1", "operator-1", RetryRunRequest(
                shot_ids=["s2"], idempotency_key="retry-selected-001",
            ))

            assert result.status == "QUEUED"
            assert [step["state"] for step in result.steps] == ["SUCCEEDED", "READY", "SUCCEEDED"]
            assert [step.get("asset_id") for step in result.steps] == ["asset-s1", None, "asset-s3"]
            assert result.steps[0]["flow_project_url"] == "https://flow.google.com/project/existing"
            assert result.final_asset_id is None and result.qc_report is None
    finally:
        engine.dispose()


def test_retry_run_all_shots_discards_every_old_shot_result():
    from src.modules.tao_video_noi_dung.contracts import RetryRunRequest
    from src.modules.tao_video_noi_dung.service import retry_run

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(db)
            result = retry_run(db, "project-1", "run-1", "workspace-1", "operator-1", RetryRunRequest(
                shot_ids=["s1", "s2", "s3"], idempotency_key="retry-all-shots-001",
            ))

            assert [step["state"] for step in result.steps] == ["READY", "READY", "READY"]
            assert all(step.get("asset_id") is None for step in result.steps)
            assert result.output_asset_ids == []
    finally:
        engine.dispose()


def test_retry_run_reuses_raw_clips_and_tts_after_watermark_failure():
    from src.modules.tao_video_noi_dung.contracts import RetryRunRequest
    from src.modules.tao_video_noi_dung.service import retry_run
    from src.models.entities import ContentVideoRun, MediaAsset

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(db, run_status="FAILED")
            run = db.query(ContentVideoRun).filter_by(id="run-1").first()
            steps = json.loads(run.steps_json)
            for step in steps:
                step.update({"state": "CLEANING", "raw_asset_id": step["asset_id"], "watermark_removed": False})
            db.add(MediaAsset(
                id="voice-asset", workspace_id="workspace-1", project_id="project-1",
                storage_key="test/voice.wav", sha256="sha256-voice", byte_size=20,
                mime_detected="audio/wav", duration_ms=30000,
                source_product="CONTENT_VIDEO_TTS", created_by="creator-1",
            ))
            run.voice_asset_id = "voice-asset"
            run.tts_config_json = json.dumps({"provider": "VIE_NEU_V3_TURBO"})
            run.steps_json = json.dumps(steps)
            db.commit()

            result = retry_run(db, "project-1", "run-1", "workspace-1", "operator-1", RetryRunRequest(
                shot_ids=["s1"], idempotency_key="retry-cleaning-shot-001",
            ))

            assert [step["state"] for step in result.steps] == ["CLEANING"] * 3
            assert [step["asset_id"] for step in result.steps] == ["asset-s1", "asset-s2", "asset-s3"]
            assert all(step["watermark_removed"] is False for step in result.steps)
            assert result.voice_asset_id == "voice-asset"
            assert result.tts_provider == "VIE_NEU_V3_TURBO"
            assert result.output_asset_ids == ["asset-s1", "asset-s2", "asset-s3", "voice-asset"]
    finally:
        engine.dispose()


@pytest.mark.parametrize("loi", [False, True])
def test_xoa_watermark_flow_mot_lan_va_khong_nhan_ket_qua_loi(monkeypatch, tmp_path, loi):
    from src.modules.tao_video_noi_dung import runner

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _, _, run = _seed_content_video_history(db)
            raw = db.get(runner.MediaAsset, "asset-s1")
            raw_path = tmp_path / raw.storage_key
            raw_path.parent.mkdir(parents=True)
            raw_path.write_bytes(b"video goc")
            raw.sha256 = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            db.commit()
            monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
            monkeypatch.setattr(runner, "get_workspace_storage_dir", lambda _: tmp_path / "test")
            calls = []

            def xoa(input_video_path, output_video_path, **kwargs):
                calls.append(input_video_path)
                output_video_path.write_bytes(b"video da xu ly")
                return {"status": "SUCCEEDED", "watermark_removed": not loi}

            monkeypatch.setattr(runner.video_processor, "remove_veo_watermark", xoa)
            step = {"state": "CLEANING", "raw_asset_id": raw.id, "asset_id": raw.id}
            if loi:
                with pytest.raises(RuntimeError, match="WATERMARK_REMOVAL_FAILED"):
                    runner._clean_flow_asset(db, run, step)
                assert step["state"] == "CLEANING"
                assert step["asset_id"] == raw.id
            else:
                runner._clean_flow_asset(db, run, step)
                clean_id = step["asset_id"]
                assert clean_id != raw.id
                assert step["watermark_removed"] is True
                assert step["state"] == "SUCCEEDED"
                runner._clean_flow_asset(db, run, step)
                retry_step = {"state": "CLEANING", "raw_asset_id": raw.id, "asset_id": raw.id}
                runner._clean_flow_asset(db, run, retry_step)
                assert retry_step["asset_id"] == clean_id
                assert db.get(runner.MediaAsset, clean_id).parent_asset_id == raw.id
                duplicate = db.get(runner.MediaAsset, "asset-s2")
                duplicate.sha256, duplicate.storage_key = raw.sha256, raw.storage_key
                db.commit()
                duplicate_step = {"state": "CLEANING", "asset_id": duplicate.id}
                runner._clean_flow_asset(db, run, duplicate_step)
                assert duplicate_step["asset_id"] == clean_id
            assert len(calls) == 1
    finally:
        engine.dispose()


def test_resume_run_requeues_saved_tts_render_without_resubmitting_shots():
    from src.models.entities import ContentVideoRun, MediaAsset
    from src.modules.tao_video_noi_dung.service import resume_run

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(db, run_status="FAILED")
            run = db.query(ContentVideoRun).filter_by(id="run-1").first()
            db.add(MediaAsset(
                id="voice-asset", workspace_id="workspace-1", project_id="project-1",
                storage_key="test/voice.wav", sha256="sha256-voice", byte_size=20,
                mime_detected="audio/wav", duration_ms=28000,
                source_product="CONTENT_VIDEO_TTS", created_by="creator-1",
            ))
            run.voice_asset_id = "voice-asset"
            run.tts_config_json = json.dumps({"provider": "VIE_NEU_V3_TURBO"})
            run.error_code = "CONTENT_VIDEO_RUN_FAILED"
            run.error_message = "VOICE_ASSET_DURATION_MISMATCH"
            db.commit()

            result = resume_run(db, "project-1", "run-1", "workspace-1")

            assert result.status == "QUEUED"
            assert result.voice_asset_id == "voice-asset"
            assert result.tts_provider == "VIE_NEU_V3_TURBO"
            assert [step["state"] for step in result.steps] == ["SUCCEEDED"] * 3
    finally:
        engine.dispose()


def test_retry_run_from_failed_shot_keeps_prior_assets_and_new_project_url_is_empty():
    from src.modules.tao_video_noi_dung.contracts import RetryRunRequest
    from src.modules.tao_video_noi_dung.service import retry_run

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(db, run_status="BLOCKED_FLOW_SETUP", unfinished_index=1, error_code="FLOW_REQUEST_NOT_SUBMITTED")
            result = retry_run(db, "project-1", "run-1", "workspace-1", "operator-1", RetryRunRequest(
                shot_ids=["s2"], new_flow_project=True, idempotency_key="retry-new-project-01",
            ))

            assert [step["state"] for step in result.steps] == ["SUCCEEDED", "READY", "READY"]
            assert [step.get("asset_id") for step in result.steps] == ["asset-s1", None, None]
            assert not any(step.get("flow_project_url") for step in result.steps)
    finally:
        engine.dispose()


def test_retry_run_does_not_create_new_flow_project_after_credit_failure():
    from fastapi import HTTPException
    from src.modules.tao_video_noi_dung.contracts import RetryRunRequest
    from src.modules.tao_video_noi_dung.service import retry_run

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(
                db, run_status="BLOCKED_FLOW_SETUP", unfinished_index=1,
                error_code="FLOW_CREDITS_INSUFFICIENT",
            )
            with pytest.raises(HTTPException) as exc_info:
                retry_run(db, "project-1", "run-1", "workspace-1", "operator-1", RetryRunRequest(
                    shot_ids=["s2"], new_flow_project=True, idempotency_key="retry-project-after-credit-failure",
                ))
            assert exc_info.value.status_code == 409
            assert exc_info.value.detail["error_code"] == "FLOW_PROJECT_NOT_UNAVAILABLE"
    finally:
        engine.dispose()


def test_new_flow_project_restarts_only_from_first_unfinished_shot():
    from fastapi import HTTPException
    from src.modules.tao_video_noi_dung.contracts import RetryRunRequest
    from src.modules.tao_video_noi_dung.service import retry_run

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(
                db, run_status="BLOCKED_FLOW_SETUP", unfinished_index=1,
                error_code="FLOW_REQUEST_NOT_SUBMITTED",
            )
            with pytest.raises(HTTPException) as exc_info:
                retry_run(db, "project-1", "run-1", "workspace-1", "operator-1", RetryRunRequest(
                    shot_ids=["s1", "s2", "s3"], new_flow_project=True,
                    idempotency_key="retry-all-in-new-project",
                ))
            assert exc_info.value.status_code == 409
            assert exc_info.value.detail["error_code"] == "NEW_FLOW_PROJECT_MUST_START_AT_FAILED_SHOT"
    finally:
        engine.dispose()


def test_retry_run_requires_confirmation_before_resending_uncertain_shot():
    from fastapi import HTTPException
    from src.modules.tao_video_noi_dung.contracts import RetryRunRequest
    from src.modules.tao_video_noi_dung.service import retry_run

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(db, run_status="NEEDS_RECONCILIATION", unfinished_index=1)
            with pytest.raises(HTTPException) as exc_info:
                retry_run(db, "project-1", "run-1", "workspace-1", "operator-1", RetryRunRequest(
                    shot_ids=["s2"], idempotency_key="retry-uncertain-001",
                ))
            assert exc_info.value.status_code == 409
            assert exc_info.value.detail["error_code"] == "FLOW_RESULT_UNCONFIRMED"
    finally:
        engine.dispose()


def test_approved_storyboard_edit_creates_new_draft_revision_and_hides_old_run():
    from src.models.entities import ContentVideoPlan
    from src.modules.tao_video_noi_dung.service import get_latest_history, update_plan

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            plan, storyboard, _run = _seed_content_video_history(db)
            changed = storyboard.model_copy(deep=True)
            changed.title = "Bản đã sửa"

            saved = update_plan(db, "project-1", plan.id, "workspace-1", "creator-1", changed)
            history = get_latest_history(db, "project-1", "workspace-1")

            assert saved.id != plan.id
            assert saved.revision == 2 and saved.status == "DRAFT"
            assert saved.approved_by is None and saved.approved_at is None
            assert history["plan"].id == saved.id and history["run"] is None
            assert db.get(ContentVideoPlan, plan.id).status == "APPROVED"
    finally:
        engine.dispose()


def test_retry_request_rejects_empty_or_duplicate_shot_selection():
    from pydantic import ValidationError
    from src.modules.tao_video_noi_dung.contracts import RetryRunRequest

    with pytest.raises(ValidationError):
        RetryRunRequest(shot_ids=[], idempotency_key="retry-empty-001")
    with pytest.raises(ValidationError):
        RetryRunRequest(shot_ids=["s1", "s1"], idempotency_key="retry-duplicate-01")


def test_new_flow_project_is_saved_on_first_submitting_shot():
    from src.modules.tao_video_noi_dung.runner import _flow_project_target

    steps = [{"shot_id": "s1", "state": "SUCCEEDED"}, {"shot_id": "s2", "state": "SUBMITTING"}]

    assert _flow_project_target(steps) is steps[1]


def test_reconciliation_route_uses_authenticated_operator_and_project_scope(monkeypatch):
    calls = []
    current_run = object()
    monkeypatch.setattr(content_video_router, "reconcile_shot", lambda *args: calls.append(args))
    monkeypatch.setattr(content_video_router, "get_run", lambda *args: current_run)
    tenant = SimpleNamespace(workspace_id="workspace-1", user_id="operator-1")
    request = ReconcileShotRequest(
        shot_id="shot-1", asset_id="asset-1", reason="Đã so clip trong Flow với đúng shot.",
    )

    result = content_video_router.reconcile_content_video_run(
        "project-1", "run-1", request, db="db", tenant=tenant
    )

    assert result is current_run
    assert calls == [("db", "project-1", "run-1", "workspace-1", "operator-1", request)]

def test_tts_run_contract_requires_one_explicit_provider_and_gwen_reference():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateRunRequest(plan_id="plan-1", idempotency_key="tts-contract-001", voice_source="TTS")
    with pytest.raises(ValidationError):
        CreateRunRequest(plan_id="plan-1", idempotency_key="tts-contract-002", voice_source="TTS", tts_provider="GWEN_TTS")
    with pytest.raises(ValidationError):
        CreateRunRequest(plan_id="plan-1", idempotency_key="tts-contract-003", voice_asset_id="asset-1", voice_source="TTS", tts_provider="VIE_NEU_V3_TURBO")

    request = CreateRunRequest(
        plan_id="plan-1", idempotency_key="tts-contract-004", voice_source="TTS",
        tts_provider="GWEN_TTS", tts_reference_asset_id="reference-1",
        tts_reference_text="Đây là bản ghi tham chiếu chính xác.", voice_clone_consent=True,
    )
    assert request.voice_asset_id is None
    assert request.tts_provider == "GWEN_TTS"
    assert request.include_subtitles is True
    assert CreateRunRequest(
        plan_id="plan-1", idempotency_key="tts-contract-005", include_subtitles=False,
    ).include_subtitles is False


def test_tts_provider_manager_switches_one_loaded_model_without_fallback():
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError, TTSProviderManager

    events = []
    class Model:
        def __init__(self, name):
            self.name = name
            self.sample_rate = 48000
            events.append(f"load:{name}")
        def __del__(self):
            events.append(f"unload:{self.name}")
        def infer(self, text, **kwargs):
            return [(self.name, text, kwargs)]
        def generate_voice_clone(self, **kwargs):
            return [(self.name, kwargs["text"], kwargs)], 48000

    manager = TTSProviderManager({name: (lambda name=name: Model(name)) for name in ("GWEN_TTS", "VIE_NEU_V3_TURBO")})
    assert manager.synthesize({"provider": "GWEN_TTS", "reference_text": "đọc"}, "Xin chào")[0][0] == "GWEN_TTS"
    assert manager.synthesize({"provider": "VIE_NEU_V3_TURBO"}, "Xin chào")[0][0][0] == "VIE_NEU_V3_TURBO"
    assert events == ["load:GWEN_TTS", "unload:GWEN_TTS", "load:VIE_NEU_V3_TURBO"]
    with pytest.raises(TTSProviderError, match="TTS_PROVIDER_UNSUPPORTED"):
        manager.synthesize({"provider": "OTHER"}, "Xin chào")


def test_tts_worker_saves_raw_duration_and_level_project_scoped_asset(tmp_path, monkeypatch):
    import wave
    import numpy as np

    added = []
    db = SimpleNamespace(add=added.append, commit=lambda: None, refresh=lambda _item: None)
    run = SimpleNamespace(
        id="run-tts-1", workspace_id="workspace-1", project_id="project-1", created_by="creator-1",
        tts_config_json='{"provider":"VIE_NEU_V3_TURBO","voice_id":"Hải Đăng"}',
        voice_asset_id=None, output_asset_ids_json="[]",
    )
    monkeypatch.setattr("src.modules.tao_video_noi_dung.runner.MEDIA_ROOT_DIR", tmp_path)

    from src.modules.tao_video_noi_dung.runner import _save_tts_voice
    _save_tts_voice(db, run, np.full(19 * 48000, 0.02, dtype=np.float32), 48000)
    asset = added[0]
    with wave.open(str(tmp_path / asset.storage_key), "rb") as wav:
        saved = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
        assert wav.getframerate() == 48000
        assert wav.getnframes() == 19 * 48000
        assert abs(float(saved[0]) / 32767 - 0.02) < 1 / 32767

    assert asset.workspace_id == run.workspace_id and asset.project_id == run.project_id
    assert asset.source_product == "CONTENT_VIDEO_TTS"
    assert run.voice_asset_id == asset.id
    assert json.loads(run.output_asset_ids_json) == [asset.id]
    assert (tmp_path / asset.storage_key).is_file()


def test_tts_run_idempotency_and_response_keep_reference_text_private():
    from src.modules.tao_video_noi_dung.service import _run_response, _same_run_request

    config = json.dumps({"provider": "GWEN_TTS", "reference_text": "transcript kín"})
    run = SimpleNamespace(
        id="run-1", workspace_id="workspace-1", project_id="project-1", plan_id="plan-1",
        plan_revision=1, voice_asset_id="generated-asset", tts_config_json=config,
        status="QUEUED", current_step=None, steps_json="[]", output_asset_ids_json="[]",
        final_asset_id=None, qc_report_json=None, error_code=None, error_message=None,
        created_at=datetime.now(timezone.utc), started_at=None, finished_at=None,
    )

    assert _same_run_request(run, "workspace-1", "project-1", "plan-1", None, None, config, True)
    assert not _same_run_request(run, "workspace-1", "project-1", "plan-1", None, None, config, False)
    assert not _same_run_request(run, "workspace-1", "project-1", "plan-1", None, None, json.dumps({"provider": "VIE_NEU_V3_TURBO"}), True)
    response = _run_response(run).model_dump_json()
    assert '"tts_provider":"GWEN_TTS"' in response
    assert '"include_subtitles":true' in response
    assert "transcript kín" not in response


def test_video_qc_rejects_video_stream_much_shorter_than_file():
    meta = {"width": 1920, "height": 1080, "codec_name": "h264", "frame_rate": 30.0,
            "duration_seconds": 60.0, "video_stream_duration_seconds": 19.97}

    assert "VIDEO_STREAM_SHORT" in evaluate_video_qc(meta, 60, decode_ok=True, aspect_ratio="16:9")
    assert evaluate_video_qc({**meta, "video_stream_duration_seconds": 59.9}, 60, decode_ok=True, aspect_ratio="16:9") == []


def test_karaoke_captions_follow_asr_words_and_scale_with_speed():
    from src.modules.tao_video_noi_dung import runner, vietsub

    script = "Xin chào các bạn. Hôm nay mình kể chuyện".split()
    asr = [
        {"text": "xin", "start_ms": 100, "end_ms": 300}, {"text": "chào", "start_ms": 300, "end_ms": 600},
        {"text": "bạn", "start_ms": 900, "end_ms": 1100}, {"text": "hôm", "start_ms": 1500, "end_ms": 1700},
        {"text": "nay", "start_ms": 1700, "end_ms": 1900}, {"text": "mình", "start_ms": 1900, "end_ms": 2100},
        {"text": "kể", "start_ms": 2100, "end_ms": 2300}, {"text": "chuyện", "start_ms": 2300, "end_ms": 2800},
    ]
    aligned = vietsub.align_script_words(script, asr)
    assert [w["text"] for w in aligned] == script
    assert aligned[0]["start_ms"] == 100 and aligned[-1]["end_ms"] == 2800
    assert all(a["end_ms"] <= b["start_ms"] for a, b in zip(aligned, aligned[1:]))  # monotonic, "các" interpolated
    captions = runner._karaoke_captions(aligned, 1920, 1080, speed=1.1)
    assert captions[0].text == "Xin chào các bạn." and captions[0].words[0].start_ms == 110
    assert "".join(w.text for c in captions for w in c.words) == "".join(script)


def test_karaoke_ass_marks_each_word_with_centisecond_durations():
    from src.modules.media_studio.ass_captions import build_karaoke_ass

    ass = build_karaoke_ass([{"text": "Xin chào", "start_ms": 0, "duration_ms": 600, "words": [
        {"text": "Xin", "start_ms": 0, "end_ms": 200}, {"text": "chào", "start_ms": 200, "end_ms": 600}]}], 1080, 1920)
    assert "PlayResY: 1920" in ass
    assert ("\\k20" in ass or "\\kf20" in ass) and ("\\k40" in ass or "\\kf40" in ass)
    assert "Xin" in ass and "chào" in ass


def test_rerender_run_requeues_completed_run_with_subtitle_choice_and_rejects_unfinished():
    from fastapi import HTTPException
    from src.models.entities import ContentVideoRun
    from src.modules.tao_video_noi_dung.service import rerender_run

    engine, Session = _content_video_test_database()
    try:
        with Session() as db:
            _seed_content_video_history(db, run_status="COMPLETED")
            result = rerender_run(db, "project-1", "run-1", "workspace-1", include_subtitles=False)
            assert result.status == "QUEUED"
            assert db.query(ContentVideoRun).filter_by(id="run-1").first().include_subtitles is False

            with pytest.raises(HTTPException) as excinfo:
                rerender_run(db, "project-1", "run-1", "workspace-1", include_subtitles=True)
            assert excinfo.value.detail["error_code"] == "RUN_NOT_RERENDERABLE"
    finally:
        engine.dispose()


def test_fit_voice_speed_matches_video_to_voice_inside_range_and_caps_outside():
    from src.modules.media_studio.video_processor import VOICE_SPEED_MAX, VOICE_SPEED_MIN, fit_voice_speed

    assert fit_voice_speed(120, 100) == pytest.approx(1.2)
    assert fit_voice_speed(120, 81.19) == VOICE_SPEED_MAX   # ca thực tế: giọng 81,19s cho video 120s
    assert fit_voice_speed(100, 130) == VOICE_SPEED_MIN


def test_voice_that_cannot_cover_the_video_is_rejected_before_flow_generation():
    import numpy as np
    from src.modules.tao_video_noi_dung import runner
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError

    shots = [SimpleNamespace(duration_seconds=10) for _ in range(12)]
    rate = 24000
    runner._check_voice_fits(np.zeros(int(110 * rate)), rate, shots)          # 110s cho 120s: vừa
    with pytest.raises(TTSProviderError, match="TTS_DURATION_OUT_OF_RANGE") as short:
        runner._check_voice_fits(np.zeros(int(81.19 * rate)), rate, shots)    # ca lỗi thực tế
    assert "quá ngắn" in short.value.detail
    with pytest.raises(TTSProviderError) as long:
        runner._check_voice_fits(np.zeros(int(160 * rate)), rate, shots)
    assert "quá dài" in long.value.detail


def test_diagram_run_clip_length_follows_each_shots_voice(monkeypatch):
    import numpy as np
    from src.modules.tao_video_noi_dung import runner
    from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError

    rate = 24000
    diagram_shot = SimpleNamespace(shot_kind="UI_SIM", ui_scene=SimpleNamespace(layout="CHART_TARGET"))
    flow_shot = SimpleNamespace(shot_kind="FLOW_ORIGAMI", ui_scene=None)
    assert runner._is_diagram_run(SimpleNamespace(shots=[diagram_shot, diagram_shot]))
    assert not runner._is_diagram_run(SimpleNamespace(shots=[diagram_shot, flow_shot]))

    def make_run(seconds):
        steps = [{"tts_audio": {"duration_ms": round(item * 1000), "pause_after_ms": 500 if i == 0 else 0}} for i, item in enumerate(seconds)]
        return SimpleNamespace(steps_json=json.dumps(steps)), sum(round(item * 1000) + (500 if i == 0 else 0) for i, item in enumerate(seconds))

    run, total_ms = make_run([5.1, 8.3])
    audio = np.ones(round(total_ms * rate / 1000), dtype=np.float32)
    saved = {}
    monkeypatch.setattr(runner, "_save_run", lambda db, run_, steps: saved.update(steps=steps))
    padded = runner._fit_diagram_voice(None, run, audio, rate)
    clips = [step["clip_seconds"] for step in saved["steps"]]
    assert clips == [7, 9]                                 # 5,1 + 0,5 + đệm 0,5 -> 7s; 8,3 + 0,5 -> 9s
    assert len(padded) == sum(clips) * rate                # giọng đệm đúng bằng tổng clip nên tốc độ co giãn = 1
    assert padded[: round(0.15 * rate)].max() == 0         # đệm đầu im lặng

    run, total_ms = make_run([20.0])
    with pytest.raises(TTSProviderError, match="TTS_DURATION_OUT_OF_RANGE"):
        runner._fit_diagram_voice(None, run, np.ones(round(total_ms * rate / 1000), dtype=np.float32), rate)


def test_narration_length_budget_flags_short_shots_and_total():
    from src.modules.tao_video_noi_dung.planner import narration_length_problems, narration_syllables

    assert narration_syllables("Ba-ha cung cấp giải pháp AI.") == 7
    ok = ("Doanh nghiệp tăng nhân sự, thêm phần mềm, nhưng công việc vẫn chậm, chi phí tăng và doanh thu chưa như kỳ vọng. "
          "Vấn đề đôi khi không nằm ở nhân viên, mà ở cách vận hành.")  # 37 âm tiết, đúng ngân sách một shot 10 giây
    assert narration_syllables(ok) == 37
    shots = [SimpleNamespace(shot_id=f"s{i}", duration_seconds=10, narration=ok) for i in range(1, 4)]
    assert narration_length_problems(shots) == []
    short = [SimpleNamespace(shot_id="s1", duration_seconds=10, narration="Tìm nguồn."), *shots[1:]]
    problems = narration_length_problems(short)
    assert any(item.startswith("NARRATION_LENGTH: s1") for item in problems)
    assert any(item.startswith("NARRATION_TOTAL") for item in problems)   # video có giọng ngắn hơn hình thì cả video bị báo


# ---- Cảnh giấy dựng bằng mã (CHART_TARGET, CHART_GROWTH, COMPARE_DOCS, PROCESS_RAIL, COST_SLICE) ----
_DIAGRAM_CASES = {
    "CHART_TARGET": (
        "Chi phí tăng đều và doanh thu chưa như kỳ vọng nên còn thiếu so với mục tiêu của quý này.",
        dict(title="Doanh thu và chi phí", unit="triệu", labels=["T1", "T2", "T3", "T4"], target=150, tag="Chi phí tăng",
             series=[{"name": "Chi phí", "values": [60, 80, 100, 118]}, {"name": "Doanh thu", "values": [100, 102, 101, 104]}],
             on={"s0": "chi phí", "s1": "doanh thu", "target": "kỳ vọng", "gap": "còn thiếu"}),
    ),
    "CHART_GROWTH": (
        "Doanh số tăng đều qua từng tháng và chốt ở hai trăm triệu đồng trong tháng cuối cùng.",
        dict(title="Doanh số theo tháng", unit="triệu", labels=["T1", "T2", "T3", "T4"], series=[{"name": "Doanh số", "values": [120, 140, 170, 200]}],
             on={"line": "tăng đều", "final": "hai trăm triệu"}),
    ),
    "COMPARE_DOCS": (
        "Một tài liệu ghi bảy mươi phần trăm. Tài liệu khác lại ghi sáu mươi lăm phần trăm. Hai con số chênh nhau năm điểm, cần xác minh.",
        dict(title="Đối chiếu", docs=[{"title": "Hợp đồng", "label": "Tỷ lệ", "value": "70%"}, {"title": "Biên bản", "label": "Tỷ lệ", "value": "65%"}],
             diff_label="Chênh 5 điểm", stamp="ĐANG XÁC MINH",
             on={"doc0": "Một tài liệu", "v0": "bảy mươi", "doc1": "Tài liệu khác", "v1": "sáu mươi lăm", "thread": "chênh nhau", "label": "năm điểm", "stamp": "xác minh"}),
    ),
    "PROCESS_RAIL": (
        "Hồ sơ đi qua bốn bước tiếp nhận duyệt giao việc hoàn tất. Bước duyệt đang nghẽn nên hồ sơ dồn lại. Khi gỡ nghẽn hồ sơ chảy tiếp.",
        dict(title="Hồ sơ đi qua bốn bước", steps=["Tiếp nhận", "Duyệt", "Giao việc", "Hoàn tất"], block_step=1,
             on={"stations": "bốn bước", "block": "đang nghẽn", "release": "gỡ nghẽn"}),
    ),
    "COST_SLICE": (
        "Đơn bán một triệu đồng. Trừ giá vốn sáu trăm nghìn, phí vận chuyển một trăm năm mươi nghìn. Lãi thật còn hai trăm năm mươi nghìn.",
        dict(title="Lãi thật của đơn hàng", unit="nghìn", total=1000, total_label="đơn hàng", final_label="Lãi thật",
             slices=[{"label": "Giá vốn", "value": 600}, {"label": "Phí vận chuyển", "value": 150}], on={"d0": "giá vốn", "d1": "phí vận chuyển", "final": "lãi thật"}),
    ),
    "CASH_FLOW": (
        "Tiền vào từ bán lẻ, online và đại lý, đổ vào quỹ tiền, rồi tỏa ra nhập hàng, lương và vận hành. Mở khoản nhập hàng để xem chi tiết từng nhà cung cấp.",
        dict(title="Tiền đổ về đâu", unit="triệu", hub_label="Quỹ tiền", drill_use=0,
             sources=[{"label": "Bán lẻ", "value": 140}, {"label": "Online", "value": 115}, {"label": "Đại lý", "value": 70}],
             uses=[{"label": "Nhập hàng", "value": 170}, {"label": "Lương", "value": 80}, {"label": "Vận hành", "value": 50}],
             drill_rows=[{"label": "NCC An Phát", "value": 62}, {"label": "NCC Đại Lợi", "value": 54}, {"label": "NCC Minh Tâm", "value": 38}, {"label": "Khác", "value": 16}],
             on={"sources": "tiền vào", "hub": "quỹ tiền", "uses": "tỏa ra", "drill": "mở khoản nhập hàng"}),
    ),
    "STACK_HEIGHT": (
        "Kho có bốn nhóm hàng, so với định mức thì nhóm C đang thiếu hụt và cần nhập thêm.",
        dict(title="Tồn kho theo nhóm", unit="thùng", target=40,
             items=[{"label": "Nhóm A", "value": 72}, {"label": "Nhóm B", "value": 55}, {"label": "Nhóm C", "value": 18}, {"label": "Nhóm D", "value": 64}],
             on={"stacks": "bốn nhóm hàng", "line": "định mức", "flag": "thiếu hụt"}),
    ),
    "DOC_LAYERS": (
        "Cùng một con số nằm ở bốn tầng chứng từ, nhưng sổ kế toán lại ghi khác nên lệch mười hai tỷ sáu.",
        dict(title="Một con số, nhiều chứng từ", layers=["Hợp đồng", "Báo cáo", "Sổ kế toán", "Biên bản"], values=["184,2", "184,2", "171,6", "184,2"],
             diff_label="Lệch 12,6 tỷ", on={"explode": "bốn tầng chứng từ", "thread": "sổ kế toán", "label": "lệch mười hai"}),
    ),
    "END_CARD": (
        "BAHA đồng hành cùng doanh nghiệp bằng giải pháp AI. Trao đổi cùng BAHA Group.",
        dict(title="Giải pháp AI cho doanh nghiệp", cta="Trao đổi cùng BAHA Group", simulated=False, on={"fold": "đồng hành", "cta": "trao đổi cùng"}),
    ),
    "OPEN_NUMBER": (
        "Ba tiếng trôi qua, con số chờ cứ tăng, và khách hỏi báo giá vẫn chưa ai nhận.",
        dict(title="Ba tiếng chưa ai trả lời", unit="phút chờ", from_value=0, to_value=192, caption="Khách hỏi báo giá, chưa ai nhận",
             on={"count": "ba tiếng", "caption": "chưa ai nhận"}),
    ),
    "OPEN_DRAIN": (
        "Doanh thu ghi nhận chín trăm triệu nhưng tiền thật chỉ còn tám mươi lăm triệu, thấp hơn ngưỡng trả lương.",
        dict(title="Tiền thật còn lại", unit="triệu", from_value=900, to_value=85, target=120, caption="Chưa đủ trả lương",
             on={"drain": "tiền thật", "line": "ngưỡng trả lương"}),
    ),
    "OPEN_QUESTION": (
        "Tiền của doanh nghiệp đang đi đâu mỗi ngày?",
        dict(title="Tiền của doanh nghiệp đang đi đâu?", caption="đi đâu", simulated=False, on={"ask": "tiền của", "key": "đi đâu"}),
    ),
    "FUNNEL": (
        "Một nghìn khách hỏi giá, sáu trăm bốn mươi nhận báo giá, nhưng chỉ một trăm tám mươi chốt đơn nên rơi mạnh nhất ở bước chốt.",
        dict(title="Khách đi qua từng bước", unit="khách", items=[{"label": "Hỏi giá", "value": 1000}, {"label": "Nhận báo giá", "value": 640}, {"label": "Chốt đơn", "value": 180}],
             on={"stages": "một nghìn khách", "leak": "rơi mạnh nhất"}),
    ),
    "TIMELINE": (
        "Tuần đầu khảo sát, tuần hai thiết kế, tuần bốn chạy thử, tuần sáu đưa vào vận hành.",
        dict(title="Lộ trình triển khai", steps=["Khảo sát", "Thiết kế", "Chạy thử", "Vận hành"], labels=["Tuần 1", "Tuần 2", "Tuần 4", "Tuần 6"],
             on={"m0": "tuần đầu khảo sát", "m1": "tuần hai thiết kế", "m2": "tuần bốn chạy thử", "m3": "tuần sáu"}),
    ),
    "BEFORE_AFTER": (
        "Trước đây mỗi yêu cầu mất ba giờ mới trả lời. Sau khi tự động, chỉ còn năm phút, nhanh gấp ba mươi sáu lần.",
        dict(title="Thời gian xử lý một yêu cầu", docs=[{"title": "Trước", "label": "Trả lời", "value": "3 giờ"}, {"title": "Sau", "label": "Trả lời", "value": "5 phút"}],
             diff_label="Nhanh gấp 36 lần", on={"before": "trước đây", "after": "sau khi tự động", "delta": "nhanh gấp"}),
    ),
    "DONUT_SHARE": (
        "Chi phí chia làm bốn phần, nhân sự chiếm gần một nửa, lớn hơn hẳn các khoản còn lại.",
        dict(title="Chi phí đi về đâu", unit="triệu", total_label="Tổng chi", items=[{"label": "Nhân sự", "value": 460}, {"label": "Nhập hàng", "value": 260}, {"label": "Khác", "value": 280}],
             on={"ring": "bốn phần", "top": "nhân sự chiếm"}),
    ),
    "GAUGE": (
        "Tỷ lệ phản hồi đúng hạn cần đạt chín mươi phần trăm, nhưng kim mới chỉ năm mươi tám.",
        dict(title="Tỷ lệ phản hồi đúng hạn", unit="%", from_value=20, to_value=58, target=90, caption="Còn cách ngưỡng 32 điểm",
             on={"dial": "tỷ lệ phản hồi", "line": "chín mươi phần trăm", "needle": "năm mươi tám"}),
    ),
    "CHECKLIST": (
        "Trước khi tự động hóa, hãy liệt kê công đoạn lặp lại, đo thời gian từng công đoạn, rồi chọn công đoạn tốn nhất.",
        dict(title="Ba việc kiểm trước khi tự động hóa", steps=["Liệt kê công đoạn", "Đo thời gian", "Chọn công đoạn tốn nhất"], stamp="SẴN SÀNG",
             on={"c0": "liệt kê công đoạn", "c1": "đo thời gian", "c2": "chọn công đoạn", "stamp": "tốn nhất"}),
    ),
    "HUB_SPOKE": (
        "Dữ liệu nằm rải rác ở Zalo, bảng tính và phần mềm bán hàng, rồi Ba-ha gom về một nơi, nối từng nguồn lại với nhau.",
        dict(title="Dữ liệu rời rạc, nối về một nơi", steps=["Zalo", "Bảng tính", "Phần mềm bán hàng"], hub_label="Một nơi",
             on={"nodes": "rải rác", "hub": "gom về một nơi", "link": "nối từng nguồn"}),
    ),
    "MATRIX_2X2": (
        "Chọn việc xử lý trước theo hai trục, mức ảnh hưởng và độ khẩn cấp. Báo giá chậm vừa ảnh hưởng lớn vừa khẩn cấp nên làm trước.",
        dict(title="Chọn việc xử lý trước", axis_x="Mức ảnh hưởng", axis_y="Độ khẩn cấp", pick=1,
             points=[{"label": "Nhập tay", "x": 25, "y": 72}, {"label": "Báo giá chậm", "x": 82, "y": 86}, {"label": "Báo cáo", "x": 60, "y": 25}],
             on={"axes": "hai trục", "points": "báo giá chậm", "pick": "nên làm trước"}),
    ),
    "RANK_BARS": (
        "Xếp theo độ lớn, nhập hàng đứng đầu với bốn trăm sáu mươi triệu, nhân sự và quảng cáo theo sau.",
        dict(title="Khoản chi lớn nhất", unit="triệu", items=[{"label": "Nhập hàng", "value": 460}, {"label": "Nhân sự", "value": 320}, {"label": "Quảng cáo", "value": 180}],
             on={"bars": "xếp theo độ lớn", "top": "đứng đầu"}),
    ),
    "KPI_CARDS": (
        "Sau một quý, doanh thu đạt một phẩy hai tỷ, thời gian phản hồi còn năm phút, và số khách chốt đơn tăng lên.",
        dict(title="Ba chỉ số sau một quý", cards=[{"title": "Doanh thu", "label": "+18% so với trước", "value": "1,2 tỷ"}, {"title": "Phản hồi", "label": "-92% so với trước", "value": "5 phút"},
                                                   {"title": "Chốt đơn", "label": "+34% so với trước", "value": "241"}],
             on={"k0": "doanh thu", "k1": "thời gian phản hồi", "k2": "khách chốt đơn"}),
    ),
    "ASSIGN_CARDS": (
        "Có ba việc mới về. Gọi lại khách giao cho Lan, gửi báo giá giao cho Minh, đối chiếu hóa đơn giao nốt cho Lan.",
        dict(title="Giao việc đúng người", steps=["Gọi lại khách", "Gửi báo giá", "Đối chiếu hóa đơn"], labels=["Lan", "Minh"], values=["Lan", "Minh", "Lan"],
             on={"cards": "ba việc mới", "a0": "gọi lại khách", "a1": "gửi báo giá", "a2": "đối chiếu hóa đơn"}),
    ),
    "WAIT_CLOCK": (
        "Ba khách đang chờ, trong đó khách C chờ lâu nhất, một trăm chín mươi hai phút, cho tới khi có người nhận.",
        dict(title="Khách đang chờ", stamp="ĐÃ NHẬN", items=[{"label": "Khách A", "value": 12}, {"label": "Khách B", "value": 38}, {"label": "Khách C", "value": 192}],
             on={"queue": "ba khách đang chờ", "alert": "chờ lâu nhất", "stop": "có người nhận"}),
    ),
    "RADAR_SCAN": (
        "Hệ thống quét danh sách khách tiềm năng, và cửa hàng Minh nổi lên với điểm cao nhất.",
        dict(title="Khách tiềm năng nóng nhất", unit="điểm", items=[{"label": "An Phát", "value": 62}, {"label": "Cửa hàng Minh", "value": 88}, {"label": "Đại lý Hưng", "value": 45}],
             on={"sweep": "quét danh sách", "hot": "cửa hàng Minh"}),
    ),
    "RACE_LANES": (
        "Làm tay mất một trăm tám mươi phút, còn tự động chỉ năm phút, nên về đích nhanh gấp ba mươi sáu lần.",
        dict(title="Làm tay hay tự động", unit="phút", items=[{"label": "Làm tay", "value": 180}, {"label": "Tự động", "value": 5}],
             on={"start": "làm tay", "finish": "về đích"}),
    ),
    "TABLE_AUDIT": (
        "Bảng có bốn khoản. Kính lúp rà từng dòng, và dòng tiền đại lý bị lệch so với chứng từ.",
        dict(title="Đối chiếu chứng từ", unit="triệu", pick=2, stamp="LỆCH 12,6", items=[{"label": "Tiền bán lẻ", "value": 140}, {"label": "Tiền online", "value": 115}, {"label": "Tiền đại lý", "value": 70}],
             on={"rows": "bảng có bốn khoản", "scan": "rà từng dòng", "flag": "bị lệch"}),
    ),
    "ALERT_STACK": (
        "Hệ thống gửi ba cảnh báo: báo giá chưa phản hồi, đơn trễ hạn, tồn kho thấp, trong đó đơn trễ hạn là khẩn nhất.",
        dict(title="Cảnh báo gửi quản lý", pick=1, steps=["Báo giá chưa phản hồi", "Đơn trễ hạn", "Tồn kho thấp"],
             on={"n0": "báo giá chưa phản hồi", "n1": "đơn trễ hạn", "n2": "tồn kho thấp", "flag": "khẩn nhất"}),
    ),
    "PYRAMID_LEVELS": (
        "Doanh nghiệp có bốn bậc trưởng thành, từ làm thủ công đến tự động hóa, và hiện đang ở bậc có phần mềm rời.",
        dict(title="Đang ở bậc nào", pick=1, steps=["Làm thủ công", "Có phần mềm rời", "Dữ liệu tập trung", "Tự động hóa"],
             on={"levels": "bốn bậc", "here": "hiện đang ở bậc"}),
    ),
    "VERSUS_LIST": (
        "Hai cách xử lý đơn hàng. Cách làm tay nhập lại từng đơn, còn cách tự động tự đồng bộ dữ liệu, nên tiết kiệm ba giờ mỗi ngày.",
        dict(title="Hai cách xử lý đơn hàng", diff_label="Tiết kiệm ba giờ", docs=[{"title": "Làm tay", "label": "Cách hiện tại", "value": "3 giờ"}, {"title": "Tự động", "label": "Cách mới", "value": "5 phút"}],
             layers=["Nhập lại từng đơn", "Dễ sai số"], values=["Tự đồng bộ dữ liệu", "Báo cáo tức thì"], on={"left": "cách làm tay", "right": "cách tự động", "verdict": "tiết kiệm ba giờ"}),
    ),
    "DOC_SEARCH": (
        "Gõ tên khách vào ô tìm kiếm, hệ thống tìm ra đúng hợp đồng chỉ trong vài giây.",
        dict(title="Tìm đúng tài liệu", caption="hợp đồng An Phát", pick=2, steps=["Báo giá", "Biên bản", "Hợp đồng", "Hóa đơn"],
             on={"query": "ô tìm kiếm", "found": "tìm ra đúng"}),
    ),
    "OPEN_HOOK": (
        "Mười hai khách đang chờ trong hàng, và két tiền vừa mở ra cho thấy con số thật còn lại.",
        dict(title="Két mở ra", variant="VAULTOPEN", value="250", caption="Còn lại hai trăm năm mươi", simulated=True, on={"start": "két tiền", "hit": "con số thật"}),
    ),
}


def _diagram_scene(layout: str):
    from src.modules.tao_video_noi_dung.planner import UiScene
    narration, spec = _DIAGRAM_CASES[layout]
    return narration, UiScene(layout=layout, diagram=spec)


def test_text_ui_scene_serialization_keeps_old_hash_input():
    from src.modules.tao_video_noi_dung.planner import UiScene

    scene = UiScene(layout="CHAT", messages=[{"role": "customer", "text": "a", "at_s": 0}, {"role": "ai", "text": "b", "at_s": 1}])
    assert '"diagram"' not in scene.model_dump_json()   # receipt cũ của cảnh chữ không đổi


@pytest.mark.parametrize("layout", sorted(_DIAGRAM_CASES))
def test_diagram_events_resolve_in_narration_order(layout):
    from src.modules.tao_video_noi_dung.planner import diagram_required_events, resolve_diagram_times

    narration, scene = _diagram_scene(layout)
    times = resolve_diagram_times(scene, narration, 8)
    keys = [key for key in diagram_required_events(layout, scene.diagram) if key in times]
    assert [times[key] for key in keys] == sorted(times[key] for key in keys)
    assert all(0 <= value <= 8 - .4 for value in times.values())


def test_fuzzy_diagram_phrase_alignment_never_runs_past_transcript_end():
    from src.modules.tao_video_noi_dung.planner import _locate_phrase

    words = ["mỗi", "đơn", "giờ", "còn", "lại", "15", "000"]
    phrase = ["số", "đơn", "giờ", "còn", "lại", "15", "000"]

    index = _locate_phrase(words, phrase, 0)

    assert index is not None
    assert index + len(phrase) <= len(words)


def test_diagram_rejects_missing_phrase_wrong_order_and_bad_data():
    from src.modules.tao_video_noi_dung.planner import UiScene, resolve_diagram_times

    narration, scene = _diagram_scene("COMPARE_DOCS")
    spec = scene.diagram.model_dump()
    with pytest.raises(ValueError, match="DIAGRAM_PHRASE_NOT_IN_NARRATION"):
        resolve_diagram_times(UiScene(layout="COMPARE_DOCS", diagram={**spec, "on": {**spec["on"], "label": "không có cụm này"}}), narration, 8)
    with pytest.raises(ValueError, match="DIAGRAM_EVENT_ORDER"):
        resolve_diagram_times(UiScene(layout="COMPARE_DOCS", diagram={**spec, "on": {**spec["on"], "v0": "sáu mươi lăm", "v1": "bảy mươi"}}), narration, 8)
    with pytest.raises(ValueError, match="DIAGRAM_EVENTS_MISMATCH"):
        UiScene(layout="COMPARE_DOCS", diagram={**spec, "on": {"v0": "bảy mươi"}})
    with pytest.raises(ValueError, match="DIAGRAM_SPEC_REQUIRED"):
        UiScene(layout="CHART_GROWTH")
    with pytest.raises(ValueError, match="DIAGRAM_COST_SLICE_FIELDS"):   # tổng khoản chi phải nhỏ hơn tổng
        UiScene(layout="COST_SLICE", diagram=dict(title="C", total=100, final_label="Lãi", slices=[{"label": "a", "value": 60}, {"label": "b", "value": 60}],
                                                  on={"d0": "a", "d1": "b", "final": "c"}))
    with pytest.raises(ValueError, match="DIAGRAM_PROCESS_RAIL_FIELDS"):   # bước nghẽn không được là bước cuối
        UiScene(layout="PROCESS_RAIL", diagram=dict(title="D", steps=["A", "B", "C"], block_step=2, on={"stations": "x", "block": "y", "release": "z"}))


def test_diagram_scene_is_blocked_for_vertical_video(tmp_path):
    from src.modules.tao_video_noi_dung.ui_sim import render_ui_scene

    narration, scene = _diagram_scene("CHART_GROWTH")
    with pytest.raises(ValueError, match="DIAGRAM_REQUIRES_16_9"):
        render_ui_scene(scene, {}, 8, "9:16", tmp_path / "x.mp4", narration=narration)


def test_before_after_hyperframes_has_a_portrait_native_composition():
    from src.modules.tao_video_noi_dung.ui_sim import hyperframes_composition_html

    narration, scene = _diagram_scene("BEFORE_AFTER")
    html = hyperframes_composition_html(scene, narration, 8, aspect_ratio="9:16")

    assert 'data-width="1080" data-height="1920"' in html
    assert 'viewBox="0 0 1080 1920"' in html
    assert "window.PORTRAIT=true" in html
    assert 'x="132" y="390"' in html
    assert 'x="180" y="1180" width="700" height="88"' in html


def test_kpi_cards_hyperframes_has_a_portrait_native_composition():
    from src.modules.tao_video_noi_dung.ui_sim import hyperframes_composition_html

    narration, scene = _diagram_scene("KPI_CARDS")
    html = hyperframes_composition_html(scene, narration, 8, aspect_ratio="9:16")

    assert 'data-width="1080" data-height="1920"' in html
    assert "window.PORTRAIT=true" in html


def test_checklist_hyperframes_uses_dark_ink_on_light_paper():
    from src.modules.tao_video_noi_dung.ui_sim import hyperframes_composition_html

    narration, scene = _diagram_scene("CHECKLIST")
    html = hyperframes_composition_html(scene, narration, 8, aspect_ratio="9:16")
    checklist = html.split("function sceneChecklist", 1)[1].split("/* ----------", 1)[0]

    assert 'font-weight="700" fill="#163344"' in checklist


def test_versus_list_has_folded_paper_reveal_and_animated_verdict(tmp_path):
    from src.modules.tao_video_noi_dung.ui_sim import hyperframes_composition_html, render_ui_scene

    narration, scene = _diagram_scene("VERSUS_LIST")
    html = hyperframes_composition_html(scene, narration, 8, aspect_ratio="9:16")

    assert "window.PORTRAIT=true" in html
    assert "paperFold" in html and "stroke-dashoffset" in html
    assert "paperCheck" in html and "verdictStamp" in html
    assert "valueSeal" in html and "bridgePulse" in html
    assert "sealY = valueY;" in html
    assert "ys = PORTRAIT ? [210, 760]" in html and "vcy = PORTRAIT ? 1380" in html
    assert "vcx = PORTRAIT ? 540" in html
    rendered = render_ui_scene(scene, {}, 8, "9:16", tmp_path / "versus.mp4", narration=narration)
    assert rendered["width"] == 1080 and rendered["height"] == 1920


@pytest.mark.parametrize("layout", sorted(_DIAGRAM_CASES))
def test_diagram_scene_renders_video_of_exact_duration(layout, tmp_path):
    from src.modules.tao_video_noi_dung.ui_sim import render_ui_scene

    narration, scene = _diagram_scene(layout)
    out = tmp_path / f"{layout}.mp4"
    meta = render_ui_scene(scene, {}, 8, "16:9", out, narration=narration)
    assert out.is_file() and out.stat().st_size > 20_000
    assert abs(float(meta["duration_seconds"]) - 8) <= 0.1 and (meta["width"], meta["height"]) == (1920, 1080)


def test_diagram_events_use_real_word_times_when_available():
    from src.modules.tao_video_noi_dung.planner import resolve_diagram_times

    narration, scene = _diagram_scene("COMPARE_DOCS")
    count = len(narration.split())
    times = resolve_diagram_times(scene, narration, 8, word_times=[i * .12 + .2 for i in range(count)])
    assert times["v0"] == pytest.approx(4 * .12 + .2)        # "bảy" là từ thứ 5 trong lời
    assert times["thread"] > times["v1"] > times["v0"]
    # số mốc không khớp số từ thì quay về ước theo vị trí âm tiết
    assert resolve_diagram_times(scene, narration, 8, word_times=[1.0, 2.0]) == resolve_diagram_times(scene, narration, 8)


def test_opening_scenes_only_first_shot_and_end_card_only_last(monkeypatch):
    from types import SimpleNamespace
    from src.modules.tao_video_noi_dung import planner

    monkeypatch.setattr(planner, "score_storyboard", lambda *args, **kwargs: SimpleNamespace(issues=[]))
    _, opening = _diagram_scene("OPEN_QUESTION")
    _, closing = _diagram_scene("END_CARD")
    plain = SimpleNamespace(shot_id="s", narration="Một hai ba", duration_seconds=10, ui_scene=None, shot_kind="UI_SIM")

    def shot(shot_id, scene):
        return SimpleNamespace(shot_id=shot_id, narration="Một hai ba", duration_seconds=10, ui_scene=scene, shot_kind="UI_SIM")

    good = SimpleNamespace(brief=None, shots=[shot("s1", opening), plain, shot("s3", closing)])
    assert not [item for item in planner._soft_problems(good) if item.startswith("DIAGRAM_")]
    bad = SimpleNamespace(brief=None, shots=[plain, shot("s2", opening), shot("s3", closing), plain])
    problems = planner._soft_problems(bad)
    assert "DIAGRAM_OPENING_ONLY_FIRST_SHOT: s2" in problems and "DIAGRAM_END_CARD_ONLY_LAST_SHOT: s3" in problems


def test_new_layouts_reject_bad_data():
    from src.modules.tao_video_noi_dung.planner import UiScene

    def build(layout, **change):
        _, spec = _DIAGRAM_CASES[layout]
        return UiScene(layout=layout, diagram={**spec, **change})

    with pytest.raises(ValueError, match="DIAGRAM_FUNNEL_FIELDS"):
        build("FUNNEL", items=[{"label": "A", "value": 10}, {"label": "B", "value": 50}, {"label": "C", "value": 5}])
    with pytest.raises(ValueError, match="DIAGRAM_TIMELINE_FIELDS"):
        build("TIMELINE", labels=["Tuần 1", "Tuần 2"])
    with pytest.raises(ValueError, match="DIAGRAM_BEFORE_AFTER_FIELDS"):
        build("BEFORE_AFTER", diff_label=None)
    with pytest.raises(ValueError, match="DIAGRAM_DONUT_SHARE_FIELDS"):
        build("DONUT_SHARE", items=[{"label": "A", "value": 50}, {"label": "B", "value": 50}])
    with pytest.raises(ValueError, match="DIAGRAM_GAUGE_FIELDS"):
        build("GAUGE", from_value=58)
    with pytest.raises(ValueError, match="DIAGRAM_CHECKLIST_FIELDS"):
        build("CHECKLIST", steps=["Một", "Hai"])
    with pytest.raises(ValueError, match="DIAGRAM_HUB_SPOKE_FIELDS"):
        build("HUB_SPOKE", hub_label=None)
    with pytest.raises(ValueError, match="DIAGRAM_MATRIX_FIELDS"):
        build("MATRIX_2X2", pick=5)
    with pytest.raises(ValueError, match="DIAGRAM_MATRIX_FIELDS"):
        build("MATRIX_2X2", points=[{"label": "A", "x": 20, "y": 20}, {"label": "B", "x": 24, "y": 26}, {"label": "C", "x": 70, "y": 70}])   # hai điểm chồng nhau
    with pytest.raises(ValueError, match="DIAGRAM_RANK_BARS_FIELDS"):
        build("RANK_BARS", items=[{"label": "A", "value": 5}, {"label": "B", "value": 5}, {"label": "C", "value": 1}])
    with pytest.raises(ValueError, match="DIAGRAM_KPI_CARDS_FIELDS"):
        build("KPI_CARDS", cards=[{"title": "Doanh thu", "label": "+1%", "value": "1"}])
    with pytest.raises(ValueError, match="DIAGRAM_ASSIGN_CARDS_FIELDS"):
        build("ASSIGN_CARDS", values=["Lan", "Minh", "Hùng"])                      # người nhận không có trong labels
    with pytest.raises(ValueError, match="DIAGRAM_WAIT_CLOCK_FIELDS"):
        build("WAIT_CLOCK", items=[{"label": "A", "value": 30}, {"label": "B", "value": 30}])
    with pytest.raises(ValueError, match="DIAGRAM_RADAR_SCAN_FIELDS"):
        build("RADAR_SCAN", items=[{"label": "A", "value": 9}, {"label": "B", "value": 9}, {"label": "C", "value": 1}])
    with pytest.raises(ValueError, match="DIAGRAM_RACE_LANES_FIELDS"):
        build("RACE_LANES", items=[{"label": "A", "value": 10}, {"label": "B", "value": 11}])      # chênh dưới 20%
    with pytest.raises(ValueError, match="DIAGRAM_TABLE_AUDIT_FIELDS"):
        build("TABLE_AUDIT", pick=4)
    with pytest.raises(ValueError, match="DIAGRAM_ALERT_STACK_FIELDS"):
        build("ALERT_STACK", pick=5)
    with pytest.raises(ValueError, match="DIAGRAM_PYRAMID_LEVELS_FIELDS"):
        build("PYRAMID_LEVELS", pick=None)
    with pytest.raises(ValueError, match="DIAGRAM_VERSUS_LIST_FIELDS"):
        build("VERSUS_LIST", layers=["Chỉ một ý"])
    with pytest.raises(ValueError, match="DIAGRAM_DOC_SEARCH_FIELDS"):
        build("DOC_SEARCH", caption=None)


def test_storyboard_layout_variety_rules(monkeypatch):
    from types import SimpleNamespace
    from src.modules.tao_video_noi_dung import planner

    monkeypatch.setattr(planner, "score_storyboard", lambda *args, **kwargs: SimpleNamespace(issues=[]))

    def shot(shot_id, layout):
        _, scene = _diagram_scene(layout)
        return SimpleNamespace(shot_id=shot_id, narration="Một hai ba", duration_seconds=10, shot_kind="UI_SIM", ui_scene=scene)

    def problems(layouts):
        board = SimpleNamespace(brief=None, shots=[shot(f"s{i}", name) for i, name in enumerate(layouts)])
        return [item for item in planner._soft_problems(board, "16:9", True) if item.startswith("DIAGRAM_L") or item.startswith("DIAGRAM_F")]

    assert not problems(["COMPARE_DOCS", "PROCESS_RAIL", "BEFORE_AFTER", "CHECKLIST", "GAUGE"])
    consecutive = problems(["PROCESS_RAIL", "PROCESS_RAIL"])
    assert any(item.startswith("DIAGRAM_LAYOUT_CONSECUTIVE: s1") for item in consecutive)   # cảnh lặp liền nhau bị báo kèm gợi ý đổi
    family = problems(["PROCESS_RAIL", "CHECKLIST"])
    assert any(item.startswith("DIAGRAM_FAMILY_CONSECUTIVE: s1") and "BEFORE_AFTER" in item for item in family)
    many = problems(["PROCESS_RAIL", "GAUGE", "CHECKLIST", "GAUGE", "TIMELINE", "COMPARE_DOCS", "FUNNEL"])
    assert any(item.startswith("DIAGRAM_FAMILY_REPEATED: họ quy_trinh") for item in many)   # bốn shot cùng họ quy trình


def test_page_slides_in_and_out_and_camera_drifts():
    import re
    from src.modules.tao_video_noi_dung import ui_sim

    html = ui_sim.DIAGRAM_TEMPLATE.read_text(encoding="utf-8")
    assert "slide = (1 - intro) * 170 - ex * 190" in html and "drift" in html        # trang trượt vào và ra, camera trôi nhẹ
    assert 'P.kind === "END_CARD"' in html                                              # thẻ kết giữ nguyên đến hết
    assert set(re.findall(r"(\w+): scene\w+", html.split("var SCENES = {")[1].split("}")[0])) >= {"FUNNEL", "TIMELINE", "BEFORE_AFTER", "DONUT_SHARE", "GAUGE", "CHECKLIST", "HUB_SPOKE", "MATRIX_2X2", "RANK_BARS", "KPI_CARDS", "ASSIGN_CARDS", "WAIT_CLOCK", "RADAR_SCAN", "RACE_LANES", "TABLE_AUDIT", "ALERT_STACK", "PYRAMID_LEVELS", "VERSUS_LIST", "DOC_SEARCH"}


def test_repair_diagram_data_fixes_mechanical_llm_mistakes():
    from src.modules.tao_video_noi_dung.planner import _repair_diagram_data

    rail = {"layout": "PROCESS_RAIL", "diagram": {"steps": ["A", "B", "C", "D"], "block_step": 3}}
    _repair_diagram_data(rail)
    assert rail["diagram"]["block_step"] == 2                                   # bậc nghẽn không được là bước cuối
    rail = {"layout": "PROCESS_RAIL", "diagram": {"steps": ["A", "B", "C"], "block_step": 0}}
    _repair_diagram_data(rail)
    assert rail["diagram"]["block_step"] == 1                                   # cũng không được là bước đầu
    chart = {"layout": "CHART_GROWTH", "diagram": {"labels": ["T1", "T2", "T3", "T4"], "series": [{"name": "A", "values": [1, 2, 3]}]}}
    _repair_diagram_data(chart)
    assert chart["diagram"]["labels"] == ["T1", "T2", "T3"] and chart["diagram"]["series"][0]["values"] == [1, 2, 3]
    _repair_diagram_data(None)                                                   # cảnh không có diagram thì bỏ qua
    _repair_diagram_data({"layout": "CHAT", "diagram": None})


def test_opening_scenes_reject_inconsistent_data():
    import pytest as _pytest
    from src.modules.tao_video_noi_dung.planner import UiScene

    _, spec = _DIAGRAM_CASES["OPEN_DRAIN"]
    with _pytest.raises(ValueError, match="DIAGRAM_OPEN_DRAIN_FIELDS"):
        UiScene(layout="OPEN_DRAIN", diagram={**spec, "target": 50})       # ngưỡng phải nằm giữa giá trị cuối và đầu
    _, q = _DIAGRAM_CASES["OPEN_QUESTION"]
    with _pytest.raises(ValueError, match="DIAGRAM_OPEN_QUESTION_FIELDS"):
        UiScene(layout="OPEN_QUESTION", diagram={**q, "caption": "ở đâu"})   # từ khóa phải nằm trong câu hỏi
    _, n = _DIAGRAM_CASES["OPEN_NUMBER"]
    with _pytest.raises(ValueError, match="DIAGRAM_OPEN_NUMBER_FIELDS"):
        UiScene(layout="OPEN_NUMBER", diagram={**n, "to_value": 0})


@pytest.mark.parametrize("variant", ["LIGHTSON", "SPOTLIGHT", "MINIATURE", "SLICE", "MISALIGN", "ENTERAISLE", "VAULTOPEN", "DEVICEWAKE", "TWOTRUTHS"])
def test_open_hook_variants_validate(variant):
    import pytest as _pytest
    from src.modules.tao_video_noi_dung.planner import UiScene

    base = dict(title="Mở đầu", variant=variant, caption="Câu nhấn", on={"start": "một", "hit": "hai"})
    if variant == "TWOTRUTHS":
        UiScene(layout="OPEN_HOOK", diagram={**base, "docs": [{"title": "A", "label": "x", "value": "9"}, {"title": "B", "label": "y", "value": "8"}]})
        with _pytest.raises(ValueError, match="DIAGRAM_OPEN_HOOK_FIELDS"):
            UiScene(layout="OPEN_HOOK", diagram=base)
    else:
        UiScene(layout="OPEN_HOOK", diagram={**base, "value": "12"})
        with _pytest.raises(ValueError, match="DIAGRAM_OPEN_HOOK_FIELDS"):
            UiScene(layout="OPEN_HOOK", diagram=base)
