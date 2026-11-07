from pathlib import Path
import os
import re
import subprocess
import wave
from types import SimpleNamespace

from src.modules.tao_video_noi_dung.contracts import CreatePlanRequest
from src.modules.tao_video_noi_dung.sfx import SFX_LIBRARY, plan_sfx_cues, transition_sfx_cues
from src.modules.media_studio.video_processor import video_processor
from src.schemas.contracts import TimelineAudioTrack, TimelineClip, TimelineDocument


def test_bo_am_thanh_co_ba_muoi_hai_hieu_ung_khac_nhau():
    assert len(SFX_LIBRARY) == 32
    assert len({item["id"] for item in SFX_LIBRARY}) == 32
    assert all(Path(item["path"]).is_file() for item in SFX_LIBRARY)


def test_hieu_ung_ui_moi_duoc_goi_theo_hanh_dong():
    expected = {
        "Nhấn nút nhẹ": "nhap_nut_nhe",
        "Nhấn nút mạnh": "nhap_nut_manh",
        "Mở cửa sổ giao diện": "ui_mo",
        "Đóng cửa sổ giao diện": "ui_dong",
        "Thả thẻ giao diện": "ui_tha",
        "Cuộn trang giao diện": "ui_cuon",
        "Phóng to bảng": "ui_phong_to",
        "Thu nhỏ bảng": "ui_thu_nho",
        "Lỗi giao diện": "ui_loi",
        "Âm báo xác nhận": "ui_xac_nhan",
        "Chọn mục giao diện": "ui_chon",
        "Vệt bút giao diện": "ui_vet_but",
    }
    library = {item["id"] for item in SFX_LIBRARY}
    assert set(expected.values()) <= library
    for action, sound_id in expected.items():
        cues = plan_sfx_cues([SimpleNamespace(action_beats=[SimpleNamespace(start_s=0.2, action=action)], ui_scene=None)], [1.0])
        assert [cue["sound_id"] for cue in cues] == [sound_id]


def test_hyperframes_nhung_nhac_va_sfx_dung_moc(tmp_path, monkeypatch):
    from src.modules.tao_video_noi_dung import hf_project

    engine_dir = tmp_path / "engine"
    (engine_dir / "vendor").mkdir(parents=True)
    (engine_dir / "vendor" / "gsap.min.js").write_text("", encoding="utf-8")
    font = tmp_path / "font.ttf"
    font.write_bytes(b"font")
    brand = tmp_path / "brand"
    brand.mkdir()
    for name in ("utm_helvetins.ttf", "logo_doc_mau.png", "logo_ngang_mau.png", "logo_doc_am_ban.png"):
        (brand / name).write_bytes(b"asset")
    music = tmp_path / "music.mp3"
    music.write_bytes(b"music")
    monkeypatch.setattr(hf_project, "engines_dir", lambda: engine_dir)
    monkeypatch.setattr(hf_project, "VIETSUB_FONT_PATH", font)
    monkeypatch.setattr(hf_project, "BRAND_DIR", brand)
    monkeypatch.setattr(hf_project, "legacy_scene", lambda *_args: "<template></template>")

    scene = SimpleNamespace(layout="TEST", diagram=SimpleNamespace(model_dump=lambda **_kwargs: {}))
    out = tmp_path / "hyperframes"
    hf_project.build_project(
        out,
        [{"scene": scene, "narration": "", "seconds": 2, "events": {}, "word_times": None}],
        None,
        None,
        transitions=False,
        music_path=music,
        sfx_cues=[{"path": SFX_LIBRARY[0]["path"], "start_seconds": 0.6, "volume": 0.24}],
    )

    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'src="assets/music.mp3" data-start="0" data-duration="2.000"' in html
    assert 'src="assets/sfx_001.wav" data-start="0.600"' in html
    assert (out / "assets" / "music.mp3").is_file()
    assert (out / "assets" / "sfx_001.wav").is_file()


def test_hyperframes_ghep_flow_va_do_hoa_o_hai_ty_le(tmp_path, monkeypatch):
    from src.modules.tao_video_noi_dung import hf_project
    from src.modules.tao_video_noi_dung.runner import _use_hyperframes_assembly

    engine_dir = tmp_path / "engine"
    (engine_dir / "vendor").mkdir(parents=True)
    (engine_dir / "vendor" / "gsap.min.js").write_text("", encoding="utf-8")
    font = tmp_path / "font.ttf"
    font.write_bytes(b"font")
    brand = tmp_path / "brand"
    brand.mkdir()
    for name in ("utm_helvetins.ttf", "logo_doc_mau.png", "logo_ngang_mau.png", "logo_doc_am_ban.png"):
        (brand / name).write_bytes(b"asset")
    flow = tmp_path / "flow.mp4"
    flow.write_bytes(b"video")
    scene = SimpleNamespace(layout="BEFORE_AFTER", diagram=SimpleNamespace(model_dump=lambda **_kwargs: {}))
    storyboard = SimpleNamespace(shots=[
        SimpleNamespace(shot_kind="FLOW_ORIGAMI", ui_scene=None),
        SimpleNamespace(shot_kind="UI_SIM", ui_scene=scene),
    ])

    monkeypatch.setattr(hf_project, "engines_dir", lambda: engine_dir)
    monkeypatch.setattr(hf_project, "VIETSUB_FONT_PATH", font)
    monkeypatch.setattr(hf_project, "BRAND_DIR", brand)
    monkeypatch.setattr(hf_project, "legacy_scene", lambda *_args: "<template></template>")
    monkeypatch.setattr(hf_project.hf_scenes, "NATIVE", {})

    for ratio, dimensions in (("9:16", (1080, 1920)), ("16:9", (1920, 1080))):
        style = {"assembly": "hyperframes", "aspect_ratio": ratio}
        assert _use_hyperframes_assembly(storyboard, style)
        out = tmp_path / ratio.replace(":", "_")
        info = hf_project.build_project(out, [
            {"scene": None, "media_path": flow, "media_start_seconds": 1.25, "narration": "", "seconds": 2},
            {"scene": scene, "narration": "", "seconds": 3, "events": {}, "word_times": None},
        ], None, None, transitions=False, aspect_ratio=ratio)

        html = (out / "index.html").read_text(encoding="utf-8")
        assert f'data-width="{dimensions[0]}" data-height="{dimensions[1]}"' in html
        assert 'data-start="0.000" data-duration="2.000" data-media-start="1.250" data-playback-rate="1"' in html
        assert 'muted playsinline' in html
        assert 'data-start="1.700" data-duration="3.300"' in html
        assert (out / "assets" / "video_01.mp4").read_bytes() == b"video"
        assert info["video_scenes"] == ["video_01.mp4"]


def test_hyperframes_du_an_timeline_giu_trim_va_lop_phu(tmp_path, monkeypatch):
    from src.modules.tao_video_noi_dung import hf_project

    engine_dir = tmp_path / "engine"
    (engine_dir / "vendor").mkdir(parents=True)
    (engine_dir / "vendor" / "gsap.min.js").write_text("", encoding="utf-8")
    font = tmp_path / "font.ttf"
    font.write_bytes(b"font")
    brand = tmp_path / "brand"
    brand.mkdir()
    for name in ("utm_helvetins.ttf", "logo_doc_mau.png", "logo_ngang_mau.png", "logo_doc_am_ban.png"):
        (brand / name).write_bytes(b"asset")
    base = tmp_path / "base.mp4"
    base_second = tmp_path / "base_second.mp4"
    overlay = tmp_path / "overlay.mov"
    base.write_bytes(b"base-video")
    base_second.write_bytes(b"second-video")
    overlay.write_bytes(b"alpha-video")
    monkeypatch.setattr(hf_project, "engines_dir", lambda: engine_dir)
    monkeypatch.setattr(hf_project, "VIETSUB_FONT_PATH", font)
    monkeypatch.setattr(hf_project, "BRAND_DIR", brand)

    out = tmp_path / "timeline"
    info = hf_project.build_timeline_project(
        out,
        {
            "width": 1080, "height": 1920, "fps": 30,
            "clips": [{
                "clip_id": "main", "asset_id": "base", "media_type": "video",
                "start_ms": 0, "duration_ms": 4000, "trim_in_ms": 1500, "trim_out_ms": 5500,
                "fit": "cover", "effect": "none",
            }, {
                "clip_id": "second", "asset_id": "base_second", "media_type": "video",
                "start_ms": 4000, "duration_ms": 2000, "trim_in_ms": 5000, "trim_out_ms": 7000,
                "fit": "contain", "effect": "punch_in",
            }],
            "overlays": [{
                "asset_id": "overlay", "x": 120, "y": 240, "width": 360, "height": 640,
                "start_ms": 1250, "duration_ms": 2500, "trim_in_ms": 500,
            }],
        },
        lambda asset_id: {"base": base, "base_second": base_second, "overlay": overlay}[asset_id],
        transition_seconds=0.16,
    )

    html = (out / "index.html").read_text(encoding="utf-8")
    assert abs(info["total_seconds"] - 6.0) < 0.001
    assert 'data-start="0.000" data-duration="4.160" data-media-start="1.500"' in html
    assert 'data-start="4.000" data-duration="2.000" data-media-start="5.000"' in html
    assert 'tl.fromTo("#s02-video", { opacity: 0 }, { opacity: 1, duration: 0.160, ease: "none" }, 4.000);' in html
    assert 'data-start="1.250" data-duration="2.500" data-media-start="0.500"' in html
    assert 'left:120px;top:240px;width:360px;height:640px;object-fit:contain' in html
    assert os.path.samefile(base, out / "assets" / "video_01.mp4")
    assert os.path.samefile(base_second, out / "assets" / "video_02.mp4")
    assert os.path.samefile(overlay, out / "assets" / "overlay_001.mov")


def test_hyperframes_render_mac_dinh_chi_mot_worker(monkeypatch, tmp_path):
    from src.modules.tao_video_noi_dung import hf_project

    captured = {}
    monkeypatch.setattr(hf_project, "_node", lambda: "node")
    monkeypatch.setattr(hf_project, "hyperframes_cli", lambda: Path("hyperframes.mjs"))
    monkeypatch.setattr(hf_project, "_env", lambda: {})
    monkeypatch.setattr(hf_project.subprocess, "run", lambda command, **_kwargs: captured.update(command=command) or SimpleNamespace(returncode=0, stdout="", stderr=""))

    hf_project.render_project(tmp_path / "project", tmp_path / "output.mp4")

    assert captured["command"][captured["command"].index("-w") + 1] == "1"


def test_sfx_duoc_dat_theo_hanh_dong_va_moc_thoi_gian():
    shots = [
        SimpleNamespace(
            shot_kind="FLOW_ORIGAMI",
            action_beats=[
                SimpleNamespace(start_s=0.7, action="Xé giấy dứt khoát"),
                SimpleNamespace(start_s=1.4, action="Nhấp chuột xác nhận"),
                SimpleNamespace(start_s=2.0, action="Máy quay tiến gần"),
            ],
            ui_scene=None,
        )
    ]

    cues = plan_sfx_cues(shots, [3.0])

    assert [(cue["sound_id"], cue["start_seconds"]) for cue in cues] == [
        ("xe_giay", 0.7),
        ("nhap_chuot", 1.4),
    ]
    paper_transition = transition_sfx_cues([2.0], "xe_giay")
    assert (paper_transition[0]["sound_id"], paper_transition[0]["start_seconds"]) == ("xe_giay", 1.85)


def test_chon_chuyen_canh_xe_giay_thua_va_on_dinh():
    from src.modules.tao_video_noi_dung.hf_project import collage_transition_indices

    for shot_count, expected in ((1, []), (2, []), (6, []), (12, [6]), (13, [6, 12]), (30, [6, 12])):
        selected = collage_transition_indices(shot_count)

        assert selected == expected
        assert collage_transition_indices(shot_count) == selected
        assert len(selected) <= 2
        assert all(right - left >= 6 for left, right in zip(selected, selected[1:]))


def test_am_xe_giay_chi_dung_tai_cac_ranh_gioi_hinh_duoc_chon():
    from src.modules.tao_video_noi_dung.hf_project import collage_transition_indices

    boundaries = [index * 2.0 for index in collage_transition_indices(13)]
    cues = transition_sfx_cues(boundaries, "xe_giay")

    assert [(cue["sound_id"], cue["start_seconds"]) for cue in cues] == [
        ("xe_giay", 11.85), ("xe_giay", 23.85),
    ]


def test_hyperframes_van_sinh_hai_canh_xe_giay_thua_sau_12_ranh_gioi(tmp_path, monkeypatch):
    from src.modules.tao_video_noi_dung import hf_project

    engine_dir = tmp_path / "engine"
    (engine_dir / "vendor").mkdir(parents=True)
    (engine_dir / "vendor" / "gsap.min.js").write_text("", encoding="utf-8")
    font = tmp_path / "font.ttf"
    font.write_bytes(b"font")
    brand = tmp_path / "brand"
    brand.mkdir()
    for name in ("utm_helvetins.ttf", "logo_doc_mau.png", "logo_ngang_mau.png", "logo_doc_am_ban.png"):
        (brand / name).write_bytes(b"asset")
    monkeypatch.setattr(hf_project, "engines_dir", lambda: engine_dir)
    monkeypatch.setattr(hf_project, "VIETSUB_FONT_PATH", font)
    monkeypatch.setattr(hf_project, "BRAND_DIR", brand)
    monkeypatch.setattr(hf_project, "legacy_scene", lambda *_args: "<template></template>")
    monkeypatch.setattr(hf_project.hf_scenes, "NATIVE", {})
    scene = SimpleNamespace(layout="TEST", diagram=SimpleNamespace(model_dump=lambda **_kwargs: {}))

    out = tmp_path / "hyperframes"
    info = hf_project.build_project(out, [
        {"scene": scene, "narration": "", "seconds": 1, "events": {}, "word_times": None}
        for _ in range(13)
    ], None, None, transitions=True)

    assert info["collage_transitions"] == 2
    html = (out / "index.html").read_text(encoding="utf-8")
    assert re.findall(r'id="(tr\d+)" data-composition-id=', html) == ["tr06", "tr12"]
    assert (out / "compositions" / "tr06.html").is_file()
    assert (out / "compositions" / "tr12.html").is_file()

    no_transitions = tmp_path / "hyperframes_no_transitions"
    disabled = hf_project.build_project(no_transitions, [
        {"scene": scene, "narration": "", "seconds": 1, "events": {}, "word_times": None}
        for _ in range(13)
    ], None, None, transitions=False)
    assert disabled["collage_transitions"] == 0
    assert not list((no_transitions / "compositions").glob("tr*.html"))


def test_lap_storyboard_co_lua_chon_goi_flow_music():
    request = CreatePlanRequest(
        content="Một nội dung đủ dài để tạo video thử nghiệm có ý nghĩa và âm thanh phù hợp.",
        target_duration_seconds=20,
        generate_flow_music=True,
    )

    assert request.generate_flow_music is True


def test_bo_tron_phat_sfx_tai_dung_moc_thoi_gian(tmp_path):
    video = tmp_path / "video.mp4"
    output = tmp_path / "ket_qua.mp4"
    subprocess.run(
        [video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=black:s=320x568:r=30:d=2", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    sfx_cues = plan_sfx_cues(
        [SimpleNamespace(
            shot_id="s1",
            ui_scene=None,
            action_beats=[SimpleNamespace(start_s=0.9, action="Nhấn nút nhẹ")],
        )],
        [2.0],
    )
    assert len(sfx_cues) == 1 and sfx_cues[0]["sound_id"] == "nhap_nut_nhe"
    timeline = TimelineDocument(
        width=320,
        height=568,
        fps=30,
        clips=[TimelineClip(clip_id="s1", asset_id="video", media_type="video", duration_ms=2000, trim_out_ms=2000)],
    )

    render_meta = video_processor.render_timeline_document(
        timeline,
        lambda _: video,
        output,
        sfx_cues=sfx_cues,
    )
    assert render_meta["audio_normalization"] == "SFX_ONLY_PEAK_LIMITED"
    assert render_meta["audio_true_peak_dbtp"] <= -1.5

    def rms_between(start):
        pcm = tmp_path / f"doan_{start}.wav"
        subprocess.run(
            [video_processor.ffmpeg_bin, "-y", "-v", "error", "-ss", str(start), "-t", "0.2",
             "-i", str(output), "-vn", "-ac", "1", "-ar", "8000", "-c:a", "pcm_s16le", str(pcm)],
            check=True,
        )
        with wave.open(str(pcm), "rb") as handle:
            samples = handle.readframes(handle.getnframes())
        values = [int.from_bytes(samples[i:i + 2], "little", signed=True) for i in range(0, len(samples), 2)]
        return sum(value * value for value in values) / max(1, len(values))

    assert rms_between(0.25) == 0
    assert rms_between(0.9) > 0


def test_nhac_ngan_duoc_dem_silence_den_het_video(tmp_path):
    video = tmp_path / "video.mp4"
    music = tmp_path / "music.wav"
    output = tmp_path / "ket_qua.mp4"
    subprocess.run(
        [video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=black:s=320x568:r=30:d=2", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    subprocess.run(
        [video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
         "sine=frequency=220:duration=0.2", "-c:a", "pcm_s16le", str(music)],
        check=True,
    )
    timeline = TimelineDocument(
        width=320,
        height=568,
        fps=30,
        clips=[TimelineClip(clip_id="s1", asset_id="video", media_type="video", duration_ms=2000, trim_out_ms=2000)],
        music_track=TimelineAudioTrack(asset_id="music", gain_db=0),
    )

    video_processor.render_timeline_document(
        timeline,
        lambda asset_id: music if asset_id == "music" else video,
        output,
    )

    from src.modules.media_studio.audio_processor import audio_processor
    assert audio_processor.probe_audio(output)["duration_seconds"] >= 1.95
