import json
import hashlib
import uuid
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.entities import AIGenerationJob, ContentVideoPlan, ContentVideoRun, MediaAsset, ProductionProject, Workspace
from src.modules.media_studio import security
from src.modules.media_studio.audio_processor import audio_processor
from src.modules.media_studio.video_processor import video_processor
from src.media_process import run_media_command
from src.modules.dieu_phoi_dung.dung_video_dai import (
    ClipTuDong,
    TaoKeHoachDungVideo,
    YTuongDienHoaFlow,
    _take_evidence,
    _caption_track,
    _cut_intervals,
    _kiem_tra_khung_den,
    danh_dau_clip_nhip_hinh_yeu,
    danh_dau_storyboard_nhip_hinh_yeu,
    _build_clip_manifest,
    _replace_clip_words,
    _retranscribe_candidates,
    _tao_timeline,
    chon_va_nhom_take,
    chon_dien_hoa,
    tao_y_tuong_dien_hoa_flow,
    tao_ke_hoach_dung_video,
)


@pytest.mark.parametrize(
    ("effect", "callouts", "visual_actions", "expected"),
    [("none", [], [], True), ("punch_in", [], [], False), ("none", ["w1"], [], False),
     ("none", [], [{"mode": "CUTAWAY"}], False)],
)
def test_nhip_hinh_danh_dau_clip_dai_thieu_diem_nhan(effect, callouts, visual_actions, expected):
    clip = ClipTuDong(
        clip_id="part1_01", start_ms=0, end_ms=45_000, title="Một ý", reason="Đủ ý.",
        effect=effect, callout_word_ids=callouts,
    )

    flagged = danh_dau_clip_nhip_hinh_yeu(clip, 40_000, visual_actions)

    assert flagged is expected
    assert clip.needs_review is expected
    assert ("thiếu điểm nhấn hình ảnh" in clip.selection_reason) is expected


def test_storyboard_danh_dau_clip_dai_khong_co_visual():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=40_000, title="Một ý", reason="Đủ ý.")

    flagged = danh_dau_storyboard_nhip_hinh_yeu(clip, [], [])

    assert flagged is True
    assert clip.needs_review is True
    assert "Storyboard có khoảng dài thiếu hình minh họa" in clip.selection_reason


def test_storyboard_cho_qua_khi_visual_neo_chia_deu_khoang_thoai():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=40_000, title="Một ý", reason="Đủ ý.")
    words = [
        {"id": "w1", "start_ms": 5_000, "end_ms": 10_000},
        {"id": "w2", "start_ms": 25_000, "end_ms": 30_000},
    ]
    visuals = [
        {"target_clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1"},
        {"target_clip_id": "part1_01", "start_word_id": "w2", "end_word_id": "w2"},
    ]

    flagged = danh_dau_storyboard_nhip_hinh_yeu(clip, words, visuals)

    assert flagged is False
    assert clip.needs_review is False


def test_storyboard_danh_dau_clip_dai_khi_visual_de_khoang_trong_qua_lau():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=40_000, title="Một ý", reason="Đủ ý.")
    words = [{"id": "w1", "start_ms": 25_000, "end_ms": 35_000}]
    visuals = [{"target_clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1"}]

    flagged = danh_dau_storyboard_nhip_hinh_yeu(clip, words, visuals)

    assert flagged is True
    assert clip.needs_review is True


def test_storyboard_khong_danh_dau_clip_ngan_chi_co_mot_y():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=30_000, title="Một ý", reason="Đủ ý.")

    flagged = danh_dau_storyboard_nhip_hinh_yeu(clip, [], [])

    assert flagged is False
    assert clip.needs_review is False


def test_storyboard_tinh_callout_don_le_la_mot_diem_chu_khong_phu_day_clip():
    clip = ClipTuDong(
        clip_id="part1_01", start_ms=0, end_ms=40_000, title="Một ý", reason="Đủ ý.",
        callout_word_ids=["w1"],
    )
    words = [{"id": "w1", "start_ms": 5_000, "end_ms": 6_000}]

    flagged = danh_dau_storyboard_nhip_hinh_yeu(clip, words, [])

    assert flagged is True
    assert clip.needs_review is True


def test_qc_khung_den_dung_ffmpeg_decode_va_tra_ve_khoang_can_ra_soat(monkeypatch, tmp_path):
    commands = []

    def ffmpeg(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(
            returncode=0,
            stderr="[blackdetect @ 0x1] black_start:2.000 black_end:4.125 black_duration:2.125\n",
        )

    monkeypatch.setattr("src.modules.dieu_phoi_dung.dung_video_dai.run_media_command", ffmpeg)

    segments = _kiem_tra_khung_den(tmp_path / "clip.mp4")

    assert segments == [{"start_ms": 2000, "end_ms": 4125, "duration_ms": 2125}]
    assert any("blackdetect=d=1.5:pix_th=0.02" in item for item in commands[0])
    assert "-xerror" in commands[0]


def test_qc_khung_den_dung_lai_neu_ffmpeg_decode_that_bai(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.modules.dieu_phoi_dung.dung_video_dai.run_media_command",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr="decoder failed"),
    )

    with pytest.raises(ValueError, match="AUTO_EDIT_FULL_DECODE_FAILED"):
        _kiem_tra_khung_den(tmp_path / "clip.mp4")


def test_qc_khung_den_bat_duoc_video_den_bang_ffmpeg_that(tmp_path):
    black_video = tmp_path / "video_den.mp4"
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=black:s=270x480:r=30:d=2.2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(black_video),
    ], capture_output=True, check=True)

    segments = _kiem_tra_khung_den(black_video)

    assert len(segments) == 1
    assert segments[0]["duration_ms"] >= 1500


class LLMGia:
    model = "model-kiem-thu"
    max_input_bytes = 9000
    max_output_tokens = 1200

    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = []

    def complete(self, messages, max_tokens=None):
        self.messages.append(messages)
        return type("KetQua", (), {"content": json.dumps(next(self.responses), ensure_ascii=False)})()


def tu(so, chu, bat_dau, ket_thuc):
    return {"id": f"w{so}", "text": chu, "start_ms": bat_dau, "end_ms": ket_thuc}


def test_moc_tu_id_transcript_sinh_timecode_tu_bien_tu_goc():
    from src.modules.dieu_phoi_dung import dung_video_dai as editor

    moc = getattr(editor, "_moc_tu_id_transcript", None)
    assert callable(moc)
    assert moc([
        tu(1, "mở", 1200, 1500),
        tu(2, "câu", 2200, 2700),
        tu(3, "kết", 11200, 12000),
    ], "w1", "w3") == (1200, 12000)


def test_manifest_luu_nguyen_timeline_edit_duoc_va_asset_dau_ra():
    from src.modules.dieu_phoi_dung import dung_video_dai as editor

    clip = ClipTuDong(
        clip_id="part1_01", start_ms=1000, end_ms=12000, title="Kịch bản",
        reason="Đủ ý.", effect="punch_in",
    )
    timeline = {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "clips": [{
            "clip_id": "part1_01_0", "asset_id": "source", "audio_asset_id": "source",
            "audio_trim_in_ms": 1000, "media_type": "video", "start_ms": 0,
            "duration_ms": 4000, "trim_in_ms": 1000, "trim_out_ms": 5000,
            "fit": "cover", "effect": "punch_in",
        }],
        "overlays": [{"asset_id": "paper-alpha", "start_ms": 1000, "duration_ms": 3000,
                       "x": 640, "y": 260, "width": 320, "height": 480}],
        "captions": [{"text": "Nhãn", "start_ms": 1000, "duration_ms": 1500,
                       "font_size": 50, "position_y_px": 660, "visual_type": "callout"}],
        "caption_style": "vietsub_v1",
        "transition_seconds": 0.16,
    }

    visual_actions = [{"asset_id": "paper-alpha", "mode": "OVERLAY", "start_ms": 1000,
                       "end_ms": 4000, "reason": "Nhấn vào số liệu", "layout_position": "center_left",
                       "layout_size": "small"}]
    manifest_clip = _build_clip_manifest("rendered-asset", clip, visual_actions, timeline, 4000)

    assert manifest_clip["output_asset_id"] == "rendered-asset"
    assert manifest_clip["visual_actions"] == visual_actions
    assert manifest_clip["timeline"] == timeline


def test_moc_tu_id_transcript_tu_choi_id_khong_ton_tai_va_nguoc_thu_tu():
    from src.modules.dieu_phoi_dung import dung_video_dai as editor

    words = [tu(1, "mở", 1200, 1500), tu(2, "kết", 11200, 12000)]
    with pytest.raises(ValueError, match="UNKNOWN_CLIP_WORD"):
        editor._moc_tu_id_transcript(words, "w1", "w3")
    with pytest.raises(ValueError, match="CLIP_WORD_RANGE_INVALID"):
        editor._moc_tu_id_transcript(words, "w2", "w1")


def test_llm_that_lap_ke_hoach_nhieu_clip_va_chi_cat_tu_dem_thua():
    words = [
        tu(1, "Ừm", 0, 300),
        tu(2, "cách", 500, 900),
        tu(3, "này", 11500, 12000),
    ]
    client = LLMGia([{
        "clips": [{
            "start_word_id": "w1",
            "end_word_id": "w3",
            "title": "Cách làm rõ ràng",
            "reason": "Đoạn có hướng dẫn hoàn chỉnh.",
            "cut_word_ids": ["w1"],
            "callout_word_ids": ["w2"],
            "effect": "none",
        }]
    }])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=15000)

    assert isinstance(plan, TaoKeHoachDungVideo)
    assert plan.clips[0].cut_word_ids == ["w1"]
    callouts = [item for item in _caption_track(plan.clips[0], words, []) if item.get("visual_type") == "callout"]
    assert callouts == [{"text": "cách", "start_ms": 500, "duration_ms": 1300, "font_size": 50, "position_y_px": 1050, "visual_type": "callout"}]
    assert "Chỉ chọn các đoạn" in client.messages[0][0]["content"]
    assert "start_word_id và end_word_id" in client.messages[0][1]["content"]
    assert "chỉ dùng punch_in một lần cho ý nhấn mạnh" in client.messages[0][1]["content"]
    assert "Không làm mịn, biến dạng, tái tạo khuôn mặt" in client.messages[0][1]["content"]


def test_llm_chon_duoc_chuyen_canh_cho_clip():
    words = [tu(1, "Mở", 0, 500), tu(2, "đầu", 11500, 12000)]
    client = LLMGia([{"clips": [{
        "start_word_id": "w1", "end_word_id": "w2", "title": "Mở đầu",
        "reason": "Đủ ý.", "cut_word_ids": [], "effect": "none",
        "transition": "wipeleft",
    }]}])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=15000)

    assert plan.clips[0].transition == "wipeleft"
    assert _tao_timeline("source", plan.clips[0], words)["transition_type"] == "wipeleft"


def test_callout_sau_title_dung_vung_tren_khung_hinh():
    clip = ClipTuDong(
        clip_id="part1_01", start_ms=0, end_ms=6000, title="Một ý", reason="Đủ ý.",
        callout_word_ids=["w4"],
    )

    callouts = [item for item in _caption_track(clip, [tu(4, "đơn", 4000, 4500)], [])
                if item.get("visual_type") == "callout"]

    assert callouts[0]["position_y_px"] == 280


def test_llm_duoc_nhac_sua_clip_ngan_hon_10_giay_mot_lan():
    words = [tu(1, "hướng", 0, 500), tu(2, "dẫn", 11500, 12000)]
    clip = {
        "start_word_id": "w1", "title": "Hướng dẫn", "reason": "Đủ ý",
        "cut_word_ids": [], "effect": "none",
    }
    client = LLMGia([
        {"clips": [{**clip, "end_word_id": "w1"}]},
        {"clips": [{**clip, "end_word_id": "w2"}]},
    ])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=12000)

    assert plan.clips[0].end_ms - plan.clips[0].start_ms == 12000
    assert len(client.messages) == 2
    assert "CLIP_DURATION_INVALID" in client.messages[1][1]["content"]


def test_ke_hoach_thu_lai_khi_llm_chon_id_tu_khong_ton_tai():
    words = [tu(1, "hướng", 0, 500), tu(2, "dẫn", 11500, 12000)]
    client = LLMGia([
        {"clips": [{"start_word_id": "w999", "end_word_id": "w2", "title": "Hướng dẫn", "reason": "Đủ ý."}]},
        {"clips": [{"start_word_id": "w1", "end_word_id": "w2", "title": "Hướng dẫn", "reason": "Đủ ý."}]},
    ])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=12000)

    assert (plan.clips[0].start_ms, plan.clips[0].end_ms) == (0, 12000)
    assert "UNKNOWN_CLIP_WORD" in client.messages[1][1]["content"]


def test_ke_hoach_thu_lai_khi_llm_khong_chon_clip():
    words = [tu(1, "hướng", 0, 500), tu(2, "dẫn", 11500, 12000)]
    client = LLMGia([
        {"clips": []},
        {"clips": [{"start_word_id": "w1", "end_word_id": "w2", "title": "Hướng dẫn", "reason": "Đủ ý."}]},
    ])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=12000)

    assert len(plan.clips) == 1
    assert "NO_CLIP_SELECTED" in client.messages[1][1]["content"]


@pytest.mark.parametrize(("word_field", "valid_id"), [("cut_word_ids", "w1"), ("callout_word_ids", "w2")])
def test_ke_hoach_thu_lai_khi_id_cat_tu_hoac_callout_khong_ton_tai(word_field, valid_id):
    words = [tu(1, "ừm", 0, 300), tu(2, "cách", 500, 900), tu(3, "này", 11500, 12000)]
    base = {"start_word_id": "w1", "end_word_id": "w3", "title": "Cách làm", "reason": "Đủ ý."}
    client = LLMGia([
        {"clips": [{**base, word_field: ["w999"]}]},
        {"clips": [{**base, word_field: [valid_id]}]},
    ])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=12000)

    assert len(plan.clips) == 1
    assert plan.clips[0].model_dump()[word_field] == [valid_id]
    assert "UNKNOWN_PLAN_WORD_ID" in client.messages[1][1]["content"]


def test_callout_ngoai_clip_bi_bo():
    words = [tu(1, "mở", 0, 300), tu(2, "cách", 1000, 1500), tu(3, "kết", 11500, 12000)]
    client = LLMGia([{"clips": [{
        "start_word_id": "w2", "end_word_id": "w3", "title": "Cách làm", "reason": "Đủ ý.",
        "callout_word_ids": ["w1"],
    }]}])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=12000)

    assert plan.clips[0].callout_word_ids == []
    assert not any(item.get("visual_type") == "callout" for item in _caption_track(plan.clips[0], words, []))


def test_chan_llm_cat_tu_co_y_nghia():
    words = [tu(1, "thì", 0, 300), tu(2, "được", 11500, 12000)]
    client = LLMGia([{
        "clips": [{
            "start_word_id": "w1",
            "end_word_id": "w2",
            "title": "Tiêu đề",
            "reason": "Có ý nghĩa.",
            "cut_word_ids": ["w1"],
            "effect": "none",
        }]
    }])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=15000)

    assert plan.clips[0].cut_word_ids == []
    assert plan.clips[0].needs_review is True


def test_chan_timecode_vuot_nguon_video():
    words = [tu(1, "xin", 0, 300), tu(2, "chào", 11500, 12000)]
    client = LLMGia([{
        "clips": [{
            "start_word_id": "w1",
            "end_word_id": "w2",
            "title": "Tiêu đề",
            "reason": "Có ý nghĩa.",
            "cut_word_ids": [],
            "effect": "none",
        }]
    }])

    with pytest.raises(ValueError, match="SOURCE_RANGE_INVALID"):
        tao_ke_hoach_dung_video(words, client, source_duration_ms=10000)


def test_chan_llm_tao_nhan_dien_hoa_tu_khong_co_trong_nguon():
    words = [tu(1, "xin", 0, 300), tu(2, "chào", 11500, 12000)]
    base = {"start_word_id": "w1", "end_word_id": "w2", "title": "Tiêu đề", "reason": "Có ý nghĩa."}
    client = LLMGia([
        {"clips": [{**base, "callout_word_ids": ["w999"]}]},
        {"clips": [{**base, "callout_word_ids": ["w2"]}]},
    ])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=15000)

    assert plan.clips[0].callout_word_ids == ["w2"]
    assert "UNKNOWN_PLAN_WORD_ID" in client.messages[1][1]["content"]


def test_bo_goi_y_callout_sai_thu_tu_nhung_van_giu_ke_hoach():
    words = [tu(index, f"từ{index}", index * 800, index * 800 + 500) for index in range(15)]
    client = LLMGia([{"clips": [{
        "start_word_id": "w0", "end_word_id": "w14", "title": "Thông điệp", "reason": "Đủ ý",
        "cut_word_ids": [], "callout_word_ids": ["w8", "w3"], "effect": "none",
    }]}])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=12000)
    timeline = _tao_timeline("speaker", plan.clips[0], words)

    assert plan.clips[0].callout_word_ids == []
    assert timeline["clips"][0]["asset_id"] == "speaker"


def test_can_canh_dien_hoa_van_dung_tieng_va_timecode_nguoi_noi():
    clip = ClipTuDong(clip_id="part1_01", start_ms=1000, end_ms=9000, title="Thông điệp", reason="Đủ ý")
    words = [tu(index, f"từ{index}", 1000 + index * 800, 1000 + index * 800 + 500) for index in range(10)]

    timeline = _tao_timeline("speaker", clip, words, visual_actions=[{
        "clip_id": "part1_01", "asset_id": "paper", "mode": "CUTAWAY", "start_ms": 3400,
        "end_ms": 5000, "reason": "Khớp lời nói",
    }])
    cutaway = next(item for item in timeline["clips"] if item["asset_id"] == "paper")

    assert cutaway["audio_asset_id"] == "speaker"
    assert cutaway["audio_trim_in_ms"] == 3400
    assert cutaway["trim_in_ms"] == 0
    assert cutaway["duration_ms"] == 1600


def test_speaker_pip_uses_paper_as_background_and_keeps_speaker_inset():
    clip = ClipTuDong(clip_id="part1_01", start_ms=1000, end_ms=9000, title="Một ý", reason="Đủ ý")
    words = [tu(index, f"từ{index}", 1000 + index * 800, 1000 + index * 800 + 500) for index in range(10)]

    timeline = _tao_timeline("speaker", clip, words, visual_actions=[{
        "clip_id": "part1_01", "asset_id": "paper", "mode": "SPEAKER_PIP", "start_ms": 3400,
        "end_ms": 5000, "reason": "Giữ người nói trên nền hoạt họa",
    }])
    background = next(item for item in timeline["clips"] if item["asset_id"] == "paper")

    assert background["audio_asset_id"] == "speaker"
    assert timeline["overlays"] == [{
        "asset_id": "speaker", "mode": "speaker_pip", "trim_in_ms": 3400,
        "start_ms": 2400, "duration_ms": 1600, "x": 600, "y": 320, "width": 360, "height": 640,
    }]


def test_speaker_pip_splits_source_inset_across_removed_pause():
    clip = ClipTuDong(clip_id="part1_01", start_ms=1000, end_ms=9000, title="Một ý", reason="Đủ ý")
    words = [tu(index, f"từ{index}", 1000 + index * 800, 1000 + index * 800 + 500) for index in range(10)]

    timeline = _tao_timeline("speaker", clip, words, pause_intervals=[(4000, 5500)], visual_actions=[{
        "clip_id": "part1_01", "asset_id": "paper", "mode": "SPEAKER_PIP", "start_ms": 3400,
        "end_ms": 6000, "reason": "Giữ người nói trên nền hoạt họa",
    }])

    assert timeline["overlays"] == [
        {"asset_id": "speaker", "mode": "speaker_pip", "trim_in_ms": 3400,
         "start_ms": 2400, "duration_ms": 725, "x": 600, "y": 320, "width": 360, "height": 640},
        {"asset_id": "speaker", "mode": "speaker_pip", "trim_in_ms": 5375,
         "start_ms": 3125, "duration_ms": 625, "x": 600, "y": 320, "width": 360, "height": 640},
    ]


def test_llm_duoc_huong_dan_dung_overlay_co_hoac_khong_co_alpha():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Thông điệp", reason="Đủ ý")
    words = [tu(1, "doanh thu", 0, 900), tu(2, "tăng", 1000, 1800)]
    client = LLMGia([{"actions": [{
        "clip_id": "part1_01", "asset_id": "paper-alpha", "mode": "OVERLAY",
        "start_word_id": "w1", "end_word_id": "w2", "reason": "Minh họa khi người nói giải thích",
        "layout_position": "center_left", "layout_size": "small",
    }]}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "paper-alpha", "scene": "Tờ giấy doanh thu gấp lớp",
        "narration": "Minh họa doanh thu", "duration_seconds": 6, "has_alpha": True,
    }], client)
    request = json.loads(client.messages[0][1]["content"])

    assert actions[0]["mode"] == "OVERLAY"
    assert (actions[0]["layout_position"], actions[0]["layout_size"]) == ("center_left", "small")
    assert _tao_timeline("speaker", clip, words, visual_actions=actions)["overlays"] == [{
        "asset_id": "paper-alpha", "start_ms": 0, "duration_ms": 1800,
        "x": 120, "y": 640, "width": 240, "height": 360,
    }]
    assert any("OVERLAY" in requirement and "asset đục" in requirement and "asset alpha" in requirement
               for requirement in request["yeu_cau"])

    opaque_client = LLMGia([{"actions": [{
        "clip_id": "part1_01", "asset_id": "paper-opaque", "mode": "OVERLAY",
        "start_word_id": "w1", "end_word_id": "w2", "reason": "Khung giấy nổi trên video người nói",
    }]}])
    opaque_actions = chon_dien_hoa([clip], words, [{
        "asset_id": "paper-opaque", "scene": "Thẻ giấy gấp có nền màu",
        "narration": "Minh họa doanh thu", "duration_seconds": 6, "has_alpha": False,
    }], opaque_client)
    assert opaque_actions[0]["mode"] == "OVERLAY"


def test_llm_uu_tien_checklist_alpha_nho_de_phu_len_video_nguoi_noi():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Checklist", reason="CÃ³ cÃ¡c bÆ°á»›c")
    words = [tu(1, "bÆ°á»›c má»™t", 0, 900), tu(2, "bÆ°á»›c hai", 1000, 1800)]
    client = LLMGia([{"actions": [{
        "clip_id": "part1_01", "asset_id": "checklist-alpha", "mode": "OVERLAY",
        "start_word_id": "w1", "end_word_id": "w2", "reason": "Checklist lÃ  minh há»a phá»¥",
        "layout_position": "upper_right", "layout_size": "small",
    }]}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "checklist-alpha", "scene": "Checklist giáº¥y gáº¥p hiá»‡n tá»«ng má»¥c",
        "narration": "bÆ°á»›c má»™t bÆ°á»›c hai", "duration_seconds": 4, "has_alpha": True,
        "renderer": "HYPERFRAMES", "visual_kind": "diagram", "aspect_ratio": "9:16",
        "target_clip_id": "part1_01", "target_start_word_id": "w1", "target_end_word_id": "w2",
    }], client)
    requirements = json.loads(client.messages[0][1]["content"])["yeu_cau"]
    timeline = _tao_timeline("speaker", clip, words, visual_actions=actions)

    assert actions[0]["mode"] == "OVERLAY"
    assert timeline["overlays"][0]["asset_id"] == "checklist-alpha"
    assert (timeline["overlays"][0]["width"], timeline["overlays"][0]["height"]) == (270, 480)
    assert any("checklist" in item.casefold() and "tag" in item.casefold()
               and "OVERLAY" in item and "small" in item for item in requirements)


def test_llm_duoc_nhac_lai_khi_bo_qua_asset_hyperframes_dung_target():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Checklist", reason="Các bước")
    words = [tu(1, "ghi giá bán", 0, 900), tu(2, "tiền thực nhận", 1000, 1800)]
    client = LLMGia([{"actions": []}, {"actions": [{
        "clip_id": "part1_01", "asset_id": "checklist-alpha", "mode": "OVERLAY",
        "start_word_id": "w1", "end_word_id": "w2", "reason": "Checklist bổ trợ lời nói",
        "layout_position": "upper_right", "layout_size": "small",
    }]}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "checklist-alpha", "scene": "Checklist giấy gấp", "narration": "Ghi giá bán và tiền thực nhận",
        "duration_seconds": 4, "has_alpha": True, "renderer": "HYPERFRAMES", "visual_kind": "diagram",
        "target_clip_id": "part1_01", "target_start_word_id": "w1", "target_end_word_id": "w2",
    }], client)

    retry_request = json.loads(client.messages[1][1]["content"])
    assert len(actions) == 1 and actions[0]["mode"] == "OVERLAY"
    assert any("checklist-alpha" in item and "bỏ qua" in item for item in retry_request["yeu_cau"])


def test_checklist_alpha_dung_overlay_nho_neu_llm_van_bo_qua():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Checklist", reason="Các bước")
    words = [tu(1, "ghi giá bán", 0, 900), tu(2, "tiền thực nhận", 1000, 1800)]
    client = LLMGia([{"actions": []}, {"actions": []}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "checklist-alpha", "scene": "Checklist giấy gấp", "narration": "Ghi giá bán và tiền thực nhận",
        "duration_seconds": 4, "has_alpha": True, "renderer": "HYPERFRAMES", "visual_kind": "diagram",
        "target_clip_id": "part1_01", "target_start_word_id": "w1", "target_end_word_id": "w2",
    }], client)

    assert len(actions) == 1
    assert actions[0]["mode"] == "OVERLAY" and actions[0]["layout_size"] == "small"
    assert clip.needs_review is True


def test_checklist_alpha_overlay_khong_che_mat_khi_llm_chon_large_ben_phai():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Checklist", reason="Các bước")
    words = [tu(1, "ghi giá bán", 500, 1200), tu(2, "trừ chi phí", 1400, 2200)]
    client = LLMGia([{"actions": [{
        "clip_id": "part1_01", "asset_id": "checklist-alpha", "mode": "OVERLAY",
        "start_word_id": "w1", "end_word_id": "w2", "reason": "Checklist hỗ trợ lời nói",
        "layout_position": "upper_right", "layout_size": "large",
    }]}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "checklist-alpha", "scene": "Checklist giấy gấp", "narration": "Ghi giá bán, trừ chi phí",
        "duration_seconds": 4, "has_alpha": True, "renderer": "HYPERFRAMES", "visual_kind": "diagram",
        "aspect_ratio": "9:16", "target_clip_id": "part1_01",
        "target_start_word_id": "w1", "target_end_word_id": "w2",
    }], client)

    assert actions[0]["mode"] == "OVERLAY"
    assert (actions[0]["layout_position"], actions[0]["layout_size"]) == ("upper_left", "medium")
    assert _tao_timeline("speaker", clip, words, visual_actions=actions)["overlays"] == [{
        "asset_id": "checklist-alpha", "start_ms": 500, "duration_ms": 1700,
        "x": 120, "y": 280, "width": 360, "height": 640,
    }]


def test_asset_target_duoc_dat_dung_clip_neu_llm_gan_nham_clip_khac():
    clips = [
        ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Kết quả", reason="Clip một"),
        ClipTuDong(clip_id="part1_02", start_ms=5000, end_ms=10000, title="Checklist", reason="Clip hai"),
    ]
    words = [tu(1, "mở đầu", 500, 900), tu(2, "ghi giá bán", 5500, 5900),
             tu(3, "trừ chi phí", 6500, 6900)]
    wrong_clip_action = {
        "clip_id": "part1_01", "asset_id": "checklist-alpha", "mode": "CUTAWAY",
        "start_word_id": "w2", "end_word_id": "w3", "reason": "LLM gán nhầm clip",
    }
    client = LLMGia([{"actions": [wrong_clip_action]}, {"actions": [wrong_clip_action]}])

    actions = chon_dien_hoa(clips, words, [{
        "asset_id": "checklist-alpha", "scene": "Checklist giấy gấp", "narration": "Ghi giá bán, trừ chi phí",
        "duration_seconds": 2, "has_alpha": True, "renderer": "HYPERFRAMES", "visual_kind": "diagram",
        "target_clip_id": "part1_02", "target_start_word_id": "w2", "target_end_word_id": "w3",
    }], client)

    assert any(action["clip_id"] == "part1_02" and action["asset_id"] == "checklist-alpha"
               and action["mode"] == "OVERLAY" for action in actions)


def test_llm_co_the_chon_speaker_pip_voi_asset_giay_nen_duc():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Thông điệp", reason="Đủ ý")
    words = [tu(1, "doanh thu", 0, 900), tu(2, "tăng", 1000, 1800)]
    client = LLMGia([{"actions": [{
        "clip_id": "part1_01", "asset_id": "paper", "mode": "SPEAKER_PIP",
        "start_word_id": "w1", "end_word_id": "w2", "reason": "Giữ người nói trên nền giấy",
        "layout_position": "center_left", "layout_size": "small",
    }]}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "paper", "scene": "Nhân vật giấy bên bàn", "narration": "Bàn làm việc",
        "duration_seconds": 6, "has_alpha": False,
    }], client)
    request = json.loads(client.messages[0][1]["content"])

    assert actions[0]["mode"] == "SPEAKER_PIP"
    assert (actions[0]["layout_position"], actions[0]["layout_size"]) == ("center_left", "small")
    assert _tao_timeline("speaker", clip, words, visual_actions=actions)["overlays"] == [{
        "asset_id": "speaker", "mode": "speaker_pip", "trim_in_ms": 0,
        "start_ms": 0, "duration_ms": 1800, "x": 120, "y": 600, "width": 270, "height": 480,
    }]
    assert any("layout_position" in item and "layout_size" in item for item in request["yeu_cau"])


def test_giam_lap_lai_asset_dien_hoa_khi_co_nhieu_lua_chon():
    clips = [ClipTuDong(clip_id=f"part1_0{i}", start_ms=(i - 1) * 6000,
                        end_ms=i * 6000, title="Thông điệp", reason="Đủ ý") for i in range(1, 4)]
    words = [tu(i, f"từ{i}", (i - 1) * 6000, (i - 1) * 6000 + 500) for i in range(1, 4)]
    assets = [
        {"asset_id": "paper-desk", "scene": "Nhân vật giấy bên bàn", "narration": "Bàn làm việc",
         "duration_seconds": 10, "has_alpha": False},
        {"asset_id": "paper-folder", "scene": "Nhân vật giấy mở hồ sơ", "narration": "Hồ sơ",
         "duration_seconds": 10, "has_alpha": False},
    ]
    client = LLMGia([{"actions": [{
        "clip_id": clip.clip_id, "asset_id": "paper-desk", "mode": "CUTAWAY",
        "start_word_id": f"w{i}", "end_word_id": f"w{i}", "reason": "Khớp lời nói",
    } for i, clip in enumerate(clips, start=1)]}])

    actions = chon_dien_hoa(clips, words, assets, client)

    assert [action["clip_id"] for action in actions] == ["part1_01", "part1_02"]
    assert clips[2].needs_review is True
    request = json.loads(client.messages[0][1]["content"])
    assert any("tránh lặp lại cùng một asset" in requirement for requirement in request["yeu_cau"])
    assert any("hệ thống sẽ bỏ lựa chọn vượt giới hạn" in requirement for requirement in request["yeu_cau"])


def test_hyperframes_diagram_duoc_ghep_thanh_panel_ngang_trong_video_doc():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Đơn hàng", reason="Có dữ kiện")
    words = [tu(1, "giảm", 1000, 1300), tu(2, "số", 5000, 5200),
             tu(3, "đơn", 9000, 9200), tu(4, "hàng", 10800, 11000)]
    client = LLMGia([{"actions": [{
        "clip_id": clip.clip_id, "asset_id": "diagram-1", "mode": "OVERLAY",
        "start_word_id": "w1", "end_word_id": "w1", "layout_position": "center_left",
        "layout_size": "large", "reason": "Biểu đồ so sánh được nói ở đây",
    }]}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "diagram-1", "scene": "So sánh trước và sau", "narration": "Giảm",
        "duration_seconds": 6, "has_alpha": False, "renderer": "HYPERFRAMES", "visual_kind": "diagram",
        "target_start_word_id": "w2", "target_end_word_id": "w4",
        "style_snapshot_hash": "a" * 64,
    }], client)

    timeline = _tao_timeline("speaker", clip, words, [], actions)

    assert actions[0]["renderer"] == "HYPERFRAMES"
    assert actions[0]["style_snapshot_hash"] == "a" * 64
    assert actions[0]["start_word_id"] == "w2" and actions[0]["end_word_id"] == "w4"
    assert timeline["overlays"] == [{
        "asset_id": "diagram-1", "start_ms": 5000, "duration_ms": 6000,
        "x": 120, "y": 820, "width": 840, "height": 472,
    }]


def test_hyperframes_diagram_co_the_lam_nen_va_giu_nguoi_noi_trong_goc():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Đơn hàng", reason="Có dữ kiện")
    words = [tu(1, "giảm", 1000, 1300)]
    client = LLMGia([{"actions": [{
        "clip_id": clip.clip_id, "asset_id": "diagram-1", "mode": "SPEAKER_PIP",
        "start_word_id": "w1", "end_word_id": "w1", "layout_position": "center_right",
        "layout_size": "large", "reason": "Giữ nguyên gương mặt khi giải thích số liệu",
    }]}])
    asset = {
        "asset_id": "diagram-1", "scene": "Biểu đồ so sánh", "narration": "Giảm",
        "duration_seconds": 10, "has_alpha": False, "renderer": "HYPERFRAMES",
        "visual_kind": "diagram", "style_snapshot_hash": "a" * 64,
        "width": 1920, "height": 1080, "aspect_ratio": "16:9",
    }

    actions = chon_dien_hoa([clip], words, [asset], client)
    timeline = _tao_timeline("speaker", clip, words, [], actions)

    assert actions[0]["mode"] == "SPEAKER_PIP"
    assert actions[0]["layout_position"] == "center_right"
    assert actions[0]["layout_size"] == "large"
    background = next(item for item in timeline["clips"] if item["asset_id"] == "diagram-1")
    assert background["fit"] == "contain"
    assert background["pad_color"] == "0B1F2A"
    assert timeline["overlays"][0] == {
        "asset_id": "speaker", "mode": "speaker_pip", "trim_in_ms": 1000,
        "start_ms": 1000, "duration_ms": 300, "x": 555, "y": 600, "width": 405, "height": 720,
    }
    request = json.loads(client.messages[0][1]["content"])
    assert any("chọn OVERLAY khi sơ đồ là panel bổ trợ" in item for item in request["yeu_cau"])
    assert any("không ép mặc định một cỡ" in item for item in request["yeu_cau"])
    assert any("asset 9:16 có chữ hoặc số liệu" in item for item in request["yeu_cau"])
    assert request["assets_dien_hoa_giay_cung_du_an"][0]["aspect_ratio"] == "16:9"


def test_hyperframes_diagram_duoc_cataway_toan_khung_va_giu_tieng_nguoi_noi():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12_000, title="Đơn hàng", reason="Có dữ kiện")
    words = [tu(1, "trước", 1000, 1400), tu(2, "sau", 6000, 6400), tu(3, "giảm", 10_000, 10_400)]
    client = LLMGia([{"actions": [{
        "clip_id": clip.clip_id, "asset_id": "diagram-1", "mode": "CUTAWAY",
        "start_word_id": "w1", "end_word_id": "w3", "reason": "Sơ đồ là trọng tâm của phép so sánh",
        "layout_position": "upper_right", "layout_size": "medium",
    }]}])
    asset = {
        "asset_id": "diagram-1", "scene": "So sánh trước và sau", "narration": "Doanh thu giảm",
        "duration_seconds": 10, "has_alpha": False, "renderer": "HYPERFRAMES",
        "visual_kind": "diagram", "style_snapshot_hash": "a" * 64,
    }

    actions = chon_dien_hoa([clip], words, [asset], client)
    timeline = _tao_timeline("speaker", clip, words, [], actions)
    cutaway = next(item for item in timeline["clips"] if item["asset_id"] == "diagram-1")

    assert actions[0]["mode"] == "CUTAWAY"
    assert cutaway["fit"] == "contain"
    assert cutaway["pad_color"] == "0B1F2A"
    assert cutaway["audio_asset_id"] == "speaker"
    assert timeline["overlays"] == []


def test_hyperframes_child_dang_ky_asset_da_probe_trong_workspace(monkeypatch, tmp_path):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor
    from src.modules.tao_video_noi_dung.service import _PILOT_STYLE_SNAPSHOT

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    workspace_id = "ws-hyperframes-child"
    media_root = tmp_path / "media"
    output_dir = media_root / "workspaces" / workspace_id / "media"
    output_dir.mkdir(parents=True)
    monkeypatch.setattr(editor, "MEDIA_ROOT_DIR", media_root)
    monkeypatch.setattr(editor, "get_workspace_storage_dir", lambda _workspace: output_dir)
    monkeypatch.setattr(editor.video_processor, "probe_video", lambda _path: {
        "width": 1080, "height": 1920, "frame_rate": 30, "duration_seconds": 10, "has_alpha": False,
    })
    monkeypatch.setattr(editor, "run_media_command", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stderr=""))

    rendered = {}
    def render(_scene, _style, _duration, _ratio, out_path, **kwargs):
        rendered["word_times"] = kwargs.get("word_times")
        rendered["aspect_ratio"] = _ratio
        out_path.write_bytes(b"h" * 24_000)
        return {"render_engine": "hyperframes"}

    from src.modules.tao_video_noi_dung import render_engines
    monkeypatch.setattr(render_engines, "render_scene", render)

    style = _PILOT_STYLE_SNAPSHOT.model_dump(mode="json")
    style_hash = hashlib.sha256(json.dumps(
        style, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    request = {"operation": "render_auto_edit_diagram", "backend_provider": "BAHA_AUTO_EDIT", "parameters": {
        "target_clip_id": "part1_01", "duration_seconds": 10, "narration": "trước và sau",
        "narration_word_times": [0.2, 0.8],
        "ui_scene": {
            "layout": "BEFORE_AFTER",
            "diagram": {
                "title": "Đơn hàng", "docs": [
                    {"title": "Trước", "label": "Đơn", "value": "100"},
                    {"title": "Sau", "label": "Đơn", "value": "60"},
                ],
                "diff_label": "Giảm 40", "on": {"before": "trước", "after": "sau", "delta": "giảm"},
            },
        },
        "style_snapshot": style, "style_snapshot_hash": style_hash,
    }}
    job = SimpleNamespace(provider="MEDIA_VIDEO", workspace_id=workspace_id, project_id=None, created_by="user-hyperframes")
    try:
        db.add(Workspace(id=workspace_id, name="HyperFrames child", slug=workspace_id))
        db.commit()

        asset = editor.render_auto_edit_diagram(db, job, request)

        path = media_root / asset.storage_key
        assert asset.workspace_id == workspace_id
        assert asset.source_product == "AUTO_EDIT_HYPERFRAMES"
        assert asset.byte_size == 24_000 and asset.sha256 == editor.hash_file(path)[0]
        assert path.is_relative_to(media_root) and path.is_file()
        assert rendered["aspect_ratio"] == "9:16"
        assert rendered["word_times"] == [0.2, 0.8]
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_tao_y_tuong_flow_giu_style_giay_ghep_va_clip_duoc_chon():
    from src.modules.tao_video_noi_dung.service import _CONTENT_VIDEO_STYLE_SNAPSHOT, _PILOT_STYLE_SNAPSHOT

    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Bài học", reason="Đủ ý")
    client = LLMGia([{"visuals": [{
        "clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1",
        "renderer": "FLOW",
        "scene": "Một ngọn núi giấy gấp nổi trên mây",
        "action": "Ngọn núi mở ra thành từng lớp giấy theo chiều dọc",
    }]}])

    visuals = tao_y_tuong_dien_hoa_flow([clip], [tu(1, "kiên trì", 1000, 4000)], [], client)

    assert visuals[0]["target_clip_id"] == clip.clip_id
    assert visuals[0]["duration_seconds"] == 10
    assert visuals[0]["has_alpha"] is False
    assert _PILOT_STYLE_SNAPSHOT.style_name in visuals[0]["prompt"]
    assert all(color in visuals[0]["prompt"] for color in _PILOT_STYLE_SNAPSHOT.palette)
    assert _PILOT_STYLE_SNAPSHOT.style_name == _CONTENT_VIDEO_STYLE_SNAPSHOT.style_name
    assert "origami" not in visuals[0]["prompt"].casefold()
    assert "trọn 10 giây" in visuals[0]["prompt"].casefold()
    assert "2 đến 4 lớp chuyển động" in visuals[0]["prompt"].casefold()
    system_prompt = client.messages[0][0]["content"].casefold()
    assert "đoạn flow và hyperframes đều dài từ 3 đến 6 giây" in system_prompt
    assert "asset nguồn cố định 10 giây" in system_prompt
    assert "hyperframes" in system_prompt and "quy trình" in system_prompt
    assert "không chỉ dành cho biểu đồ" in system_prompt


def test_tao_y_tuong_khong_ghep_fallback_visual_thieu_ngu_canh_tu():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=20000, title="Bai hoc", reason="Du y")
    words = [tu(index, f"tu {index}", 1000 + (index - 1) * 1000, 2000 + (index - 1) * 1000)
             for index in range(1, 9)]
    visual_1 = {
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w4",
        "scene": "Paper layers", "action": "Open the paper layers",
        "renderer": "FLOW",
    }
    visual_2 = {
        "clip_id": clip.clip_id, "start_word_id": "w5", "end_word_id": "w8",
        "scene": "Moving paper shapes", "action": "Fold into a new shape",
        "renderer": "FLOW",
    }
    malformed = {**visual_2, "action": "short"}
    client = LLMGia([{"visuals": [visual_1, visual_2, malformed]}, {"visuals": [visual_1]}])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert len(visuals) == 1
    assert visuals[0]["narration"] == "tu 1 tu 2 tu 3 tu 4"


def test_tao_y_tuong_co_the_dat_nhieu_dien_hoa_vao_cac_doan_rieng_trong_mot_clip():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=20000, title="Kết quả", reason="Đủ ý")
    words = [
        tu(1, "Đầu tư", 1000, 2000), tu(2, "một triệu", 3000, 5000),
        tu(3, "sau đó", 8000, 9000), tu(4, "còn chín trăm", 10000, 12000),
    ]
    client = LLMGia([{"visuals": [
        {"clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w2",
         "scene": "Một xấp tiền giấy đặt trên chiếc bàn giấy", "action": "Xấp tiền mở ra thành từng lớp giấy", "renderer": "FLOW"},
        {"clip_id": "part1_01", "start_word_id": "w3", "end_word_id": "w4",
         "scene": "Một chiếc hộp giấy đựng số tiền còn lại", "action": "Nắp hộp khép lại để lộ phần tiền còn lại", "renderer": "FLOW"},
    ]}])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert [(item["target_start_word_id"], item["target_end_word_id"], item["narration"]) for item in visuals] == [
        ("w1", "w2", "Đầu tư một triệu"), ("w3", "w4", "sau đó còn chín trăm"),
    ]
    request = json.loads(client.messages[0][1]["content"])
    assert "w1" in request["clips"][0]["transcript"]
    assert "w1[1000-2000]=Đầu tư" in client.messages[0][1]["content"]


def test_planner_tu_bo_sung_visual_khi_storyboard_clip_dai_con_khoang_trong_lon():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=60_000, title="Một câu chuyện", reason="Đủ ý")
    words = [
        tu(1, "ý đầu", 10_000, 12_500), tu(2, "kết quả đầu", 12_500, 15_000),
        tu(3, "ý giữa", 28_000, 30_500), tu(4, "kết quả giữa", 30_500, 33_000),
        tu(5, "ý cuối", 45_000, 47_500), tu(6, "kết quả cuối", 47_500, 50_000),
    ]

    def visual(start, end, scene):
        return {
            "clip_id": clip.clip_id, "start_word_id": start, "end_word_id": end,
            "scene": scene, "action": "Các lớp giấy chuyển động theo nguyên nhân và kết quả",
            "renderer": "FLOW",
        }

    sparse = {"visuals": [
        visual("w1", "w2", "Xấp giấy mở theo ý đầu"),
        visual("w5", "w6", "Tờ giấy gấp lại ở kết luận"),
    ]}
    balanced = {"visuals": [visual("w3", "w4", "Thẻ giấy minh họa ý giữa")]}
    client = LLMGia([sparse, balanced])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert len(client.messages) == 2
    repair_request = json.loads(client.messages[1][1]["content"])
    feedback = repair_request["validator_feedback"]
    assert "VISUAL_GAP_ABOVE_TARGET" in feedback
    assert "15.0-45.0s" in feedback
    assert "w3=ý giữa" in feedback and "w4=kết quả giữa" in feedback
    assert [item["start_word_id"] for item in repair_request["visuals_hop_le_can_giu"]] == ["w1", "w5"]
    assert len(visuals) == 3
    assert clip.needs_review is False


def test_planner_danh_dau_ra_soat_neu_llm_khong_sua_khoang_trong_storyboard():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=60_000, title="Một câu chuyện", reason="Đủ ý")
    words = [tu(1, "ý đầu", 10_000, 12_500), tu(2, "kết quả đầu", 12_500, 15_000),
             tu(3, "ý cuối", 45_000, 47_500), tu(4, "kết quả cuối", 47_500, 50_000)]
    sparse = {"visuals": [
        {"clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w2",
         "scene": "Xấp giấy mở theo ý đầu", "action": "Các lớp giấy mở ra theo nguyên nhân và kết quả", "renderer": "FLOW"},
        {"clip_id": clip.clip_id, "start_word_id": "w3", "end_word_id": "w4",
         "scene": "Tờ giấy gấp lại ở kết luận", "action": "Các lớp giấy khép lại theo nguyên nhân và kết quả", "renderer": "FLOW"},
    ]}
    client = LLMGia([sparse, sparse, sparse, sparse])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert len(client.messages) == 4
    assert len(visuals) == 2
    assert clip.needs_review is True
    assert "khoảng trống minh họa trên 16 giây" in clip.selection_reason


def test_planner_giu_checklist_hop_le_khi_flow_cung_ke_hoach_sai_moc():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=60_000, title="Kiểm tra doanh thu", reason="Nêu các bước cần làm")
    response = {"visuals": [
        {"clip_id": clip.clip_id, "start_word_id": "w5", "end_word_id": "w1",
         "scene": "Một tờ giấy mở ra thành các lớp", "action": "Các lớp mở quá xa nhau",
         "renderer": "FLOW"},
        {"clip_id": clip.clip_id, "start_word_id": "w3", "end_word_id": "w5",
         "scene": "Checklist ba bước kiểm tra doanh thu", "action": "Từng bước gấp mở và đóng dấu",
         "renderer": "HYPERFRAMES", "ui_scene": {"layout": "CHECKLIST", "diagram": {
             "title": "Kiểm tra doanh thu", "steps": ["Ghi doanh thu", "Trừ phí sàn", "Trừ chi phí"],
             "on": {"c0": "ghi doanh thu", "c1": "trừ phí sàn", "c2": "trừ chi phí"},
         }}},
    ]}
    words = [tu(1, "mở đầu", 1_000, 1_500), tu(2, "giới thiệu", 9_000, 10_000),
             tu(3, "ghi doanh thu", 12_000, 12_500), tu(4, "trừ phí sàn", 14_000, 14_500),
             tu(5, "trừ chi phí", 15_500, 16_000)]
    client = LLMGia([response, response, response, response])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert len(visuals) == 1
    assert visuals[0]["renderer"] == "HYPERFRAMES"
    assert visuals[0]["ui_scene"]["layout"] == "CHECKLIST"
    assert clip.needs_review is True
    assert len(client.messages) == 4


def test_planner_giu_y_tuong_hop_le_khi_lan_retry_sau_tra_ve_rong():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=60_000,
                      title="Kiểm tra doanh thu", reason="Nêu các bước cần làm")
    valid = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w5",
        "scene": "Checklist giấy gấp nêu các khoản cần kiểm tra",
        "action": "Từng mục mở ra theo lời rồi được đánh dấu",
        "renderer": "HYPERFRAMES", "ui_scene": {"layout": "CHECKLIST", "diagram": {
            "title": "Kiểm tra đơn", "steps": ["Ghi giá bán", "Trừ phí sàn", "Tính chi phí"],
            "on": {"c0": "ghi giá bán", "c1": "trừ phí sàn", "c2": "tính chi phí"},
        }},
    }]}
    client = LLMGia([valid, {"visuals": []}, {"visuals": []}, {"visuals": []}])
    words = [tu(1, "ghi giá bán", 10_000, 10_500), tu(2, "trừ phí sàn", 12_000, 12_500),
             tu(3, "tính chi phí", 14_000, 14_500), tu(4, "kết quả", 16_000, 16_500),
             tu(5, "đơn hàng", 18_000, 18_500)]

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert len(visuals) == 1 and visuals[0]["renderer"] == "HYPERFRAMES"
    assert visuals[0]["target_start_word_id"] == "w1"
    assert clip.needs_review is True


def test_tao_y_tuong_danh_dau_ra_soat_neu_cac_visual_trong_clip_chong_len_nhau():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Kết quả", reason="Đủ ý")
    visual = {"clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w2",
              "scene": "Một xấp tiền giấy đặt trên chiếc bàn giấy", "action": "Xấp tiền mở ra thành từng lớp giấy", "renderer": "FLOW"}
    overlap = {**visual, "start_word_id": "w2", "end_word_id": "w3"}
    invalid_plan = {"visuals": [visual, overlap]}
    client = LLMGia([invalid_plan, invalid_plan, invalid_plan, invalid_plan])

    visuals = tao_y_tuong_dien_hoa_flow(
        [clip], [tu(1, "Đầu tư", 1000, 2000), tu(2, "một triệu", 3000, 4000), tu(3, "còn lại", 7000, 8000)], [], client,
    )

    assert len(visuals) == 1 and visuals[0]["start_word_id"] == "w1"
    assert clip.needs_review is True


def test_tao_y_tuong_co_the_chon_hyperframes_cho_so_do_giay():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Doanh thu", reason="Có số liệu cần giải thích")
    client = LLMGia([{"visuals": [{
        "clip_id": "part1_01",
        "start_word_id": "w1", "end_word_id": "w1",
        "scene": "So sánh đơn hàng trước và sau thay đổi quảng cáo",
        "action": "Hai tập hồ sơ giấy trượt vào và làm lộ chênh lệch",
        "renderer": "HYPERFRAMES",
        "ui_scene": {
            "layout": "BEFORE_AFTER",
            "diagram": {
                "title": "Đơn hàng",
                "docs": [
                    {"title": "Trước", "label": "Đơn", "value": "100"},
                    {"title": "Sau", "label": "Đơn", "value": "60"},
                ],
                "diff_label": "Giảm 40",
                "on": {"before": "trước là một trăm đơn", "after": "sau còn sáu mươi đơn", "delta": "giảm bốn mươi đơn"},
            },
        },
    }]}])

    visuals = tao_y_tuong_dien_hoa_flow(
        [clip], [tu(1, "Trước là một trăm đơn, sau còn sáu mươi đơn, giảm bốn mươi đơn", 1000, 6000)], [], client,
    )

    assert visuals[0]["renderer"] == "HYPERFRAMES"
    assert visuals[0]["ui_scene"]["layout"] == "BEFORE_AFTER"
    assert visuals[0]["style_snapshot_hash"]
    assert "không chỉ dành cho biểu đồ" in client.messages[0][0]["content"].casefold()
    assert "so sánh, quy trình, checklist" in client.messages[0][0]["content"]
    assert "start_word_id đến end_word_id phải bao trùm mọi cụm" in client.messages[0][0]["content"]
    request = json.loads(client.messages[0][1]["content"])
    assert "Mốc sơ đồ HyperFrames phải có căn cứ, tối đa 6 giây" in " ".join(request["yeu_cau"])
    assert "BEFORE_AFTER: đúng 2 docs" in client.messages[0][0]["content"]
    assert "diff_label bắt buộc" in client.messages[0][0]["content"]
    assert "simulated=false" in client.messages[0][0]["content"]


def test_planner_chi_chon_renderer_dang_san_sang():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12_000, title="Đơn hàng", reason="So sánh")
    flow = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w1",
        "scene": "Mô hình giấy cửa hàng", "action": "Chồng đơn origami giảm dần", "renderer": "FLOW",
    }]}
    diagram = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w7",
        "scene": "So sánh số đơn", "action": "Hai tấm giấy lần lượt mở ra", "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Đơn hàng", "simulated": False,
            "docs": [{"title": "Trước", "label": "Đơn", "value": "100"},
                      {"title": "Sau", "label": "Đơn", "value": "60"}],
            "diff_label": "Giảm 40",
            "on": {"before": "Trước 100", "after": "sau còn 60", "delta": "giảm 40"},
        }},
    }]}
    client = LLMGia([flow, diagram])

    visuals = tao_y_tuong_dien_hoa_flow(
        [clip], [tu(1, "Trước", 1_000, 1_500), tu(2, "100", 1_500, 2_000),
                 tu(3, "sau", 2_500, 3_000), tu(4, "còn", 3_000, 3_500),
                 tu(5, "60", 3_500, 4_000), tu(6, "giảm", 5_000, 5_500),
                 tu(7, "40", 5_500, 6_000)], [], client, False,
    )

    assert len(visuals) == 1 and visuals[0]["renderer"] == "HYPERFRAMES"
    assert "VISUAL_RENDERER_UNAVAILABLE" in json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "Google Flow chưa sẵn sàng" in client.messages[1][0]["content"]


def test_planner_giu_visual_hop_le_khi_visual_khac_sai_schema():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12_000, title="Đơn hàng", reason="So sánh")
    response = {"visuals": [
        {"clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w6",
         "scene": "So sánh trước và sau", "action": "Hai tấm giấy hiện lần lượt",
         "renderer": "HYPERFRAMES", "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
             "title": "Đơn hàng", "simulated": False,
             "docs": [{"title": "Trước", "label": "Đơn", "value": "100"},
                      {"title": "Sau", "label": "Đơn", "value": "60"}],
             "diff_label": "Giảm 40",
             "on": {"before": "trước 100", "after": "sau 60", "delta": "giảm 40"},
         }}},
        {"clip_id": clip.clip_id, "start_word_id": "w7", "end_word_id": "w9",
         "scene": "Số đơn", "action": "Đếm từng tờ giấy", "renderer": "HYPERFRAMES",
         "ui_scene": {"layout": "OPEN_NUMBER", "diagram": {"title": "Số đơn", "on": {"count": "số đơn"}}}},
    ]}
    words = [tu(1, "Trước", 1_000, 1_200), tu(2, "100", 1_200, 1_400), tu(3, "sau", 1_400, 1_600),
             tu(4, "60", 1_600, 1_800), tu(5, "giảm", 1_800, 2_000), tu(6, "40", 2_000, 2_200),
             tu(7, "số", 5_000, 5_200), tu(8, "đơn", 5_200, 5_400), tu(9, "giảm", 5_400, 5_600)]
    client = LLMGia([response, response, response])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client, flow_available=False)

    assert len(visuals) == 1 and visuals[0]["ui_scene"]["layout"] == "BEFORE_AFTER"
    assert clip.needs_review is True


def test_tao_y_tuong_tu_choi_so_do_keo_dai_qua_khoang_ke_va_yeu_cau_tach_visual():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=26_740, title="Doanh thu", reason="So sánh trước và sau")
    response = {"visuals": [{
        "clip_id": clip.clip_id,
        "start_word_id": "w1", "end_word_id": "w14",
        "scene": "So sánh doanh thu trước và sau bằng hai tờ giấy",
        "action": "Hai tờ giấy lần lượt mở để so sánh số tiền và phần giảm",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Doanh thu", "simulated": False,
            "docs": [
                {"title": "Trước", "label": "Doanh thu", "value": "1 triệu"},
                {"title": "Sau", "label": "Doanh thu", "value": "900 nghìn"},
            ],
            "diff_label": "Giảm 100 nghìn",
            "on": {"before": "trước đây 100 đơn", "after": "sau còn 900 nghìn", "delta": "giảm 100 nghìn"},
        }},
    }]}
    words = [
        tu(1, "Trước", 1_000, 1_200), tu(2, "đây", 1_200, 1_400), tu(3, "100", 1_400, 1_600),
        tu(4, "đơn", 1_600, 1_800), tu(5, "đang", 4_000, 4_200), tu(6, "tăng", 8_000, 8_200),
        tu(7, "giá", 12_000, 12_200), tu(8, "sau", 16_000, 16_200), tu(9, "còn", 16_200, 16_400),
        tu(10, "900", 16_400, 16_600), tu(11, "nghìn", 16_600, 16_800),
        tu(12, "giảm", 18_000, 18_200), tu(13, "100", 18_200, 18_400), tu(14, "nghìn", 18_400, 18_600),
    ]

    client = LLMGia([response, response, response, response])
    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert visuals == []
    assert clip.needs_review is True
    feedback = json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "tách" in feedback and "6 giây" in feedback


def test_hyperframes_dung_khoang_loi_thoai_ngan_trong_vung_chon_dai():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=20_000, title="Doanh thu", reason="So sánh")
    response = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w10",
        "scene": "So sánh doanh thu", "action": "Mở lần lượt hai tờ giấy",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Doanh thu", "simulated": False,
            "docs": [{"title": "Trước", "label": "Đơn", "value": "100"},
                      {"title": "Sau", "label": "Đơn", "value": "60"}],
            "diff_label": "Giảm 40",
            "on": {"before": "trước 100", "after": "sau còn 900", "delta": "giảm 100 nghìn"},
        }},
    }]}
    words = [tu(1, "trước", 1_000, 1_200), tu(2, "100", 1_200, 1_400),
             tu(3, "đang", 2_000, 2_200), tu(4, "sau", 3_000, 3_200),
             tu(5, "còn", 3_200, 3_400), tu(6, "900", 3_400, 3_600),
             tu(7, "giảm", 4_000, 4_200), tu(8, "100", 4_200, 4_400),
             tu(9, "nghìn", 4_400, 4_600), tu(10, "rồi", 14_000, 14_200)]

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], LLMGia([response]))

    assert len(visuals) == 1
    assert visuals[0]["target_start_word_id"] == "w1"
    assert visuals[0]["target_end_word_id"] == "w9"
    assert visuals[0]["duration_seconds"] == 4


def test_tao_y_tuong_hyperframes_tu_choi_neu_cac_moc_vuot_qua_6_giay():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=30_000, title="Doanh thu", reason="So sánh số liệu")
    response = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w9",
        "scene": "So sánh số liệu trước và sau",
        "action": "Hai tờ giấy lần lượt mở để cho thấy mức thay đổi",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Doanh thu", "simulated": False,
            "docs": [{"title": "Trước", "label": "Tổng", "value": "1 triệu"},
                     {"title": "Sau", "label": "Tổng", "value": "900 nghìn"}],
            "diff_label": "Giảm 100 nghìn",
            "on": {"before": "trước 100 đơn", "after": "sau còn 900", "delta": "giảm 100 nghìn"},
        }},
    }]}
    words = [tu(1, "trước", 1_000, 1_200), tu(2, "100", 1_200, 1_400),
             tu(3, "đơn", 1_400, 1_600), tu(4, "sau", 4_000, 4_200),
             tu(5, "còn", 4_200, 4_400), tu(6, "900", 4_400, 4_600),
             tu(7, "giảm", 7_200, 7_400), tu(8, "100", 7_400, 7_600),
             tu(9, "nghìn", 7_600, 7_800)]

    client = LLMGia([response, response, response, response])
    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert visuals == []
    assert clip.needs_review is True
    assert len(client.messages) == 4
    feedback = json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "6 giây" in feedback


def test_flow_tao_nguon_10_giay_nhung_neo_visual_toi_da_6_giay():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12_000, title="Ket qua", reason="Du y")
    too_long = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w3",
        "scene": "Paper stack", "action": "Paper opens", "renderer": "FLOW",
    }]}
    valid = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w2",
        "scene": "Paper stack", "action": "Paper opens", "renderer": "FLOW",
    }]}
    words = [tu(1, "invest", 1_000, 2_000), tu(2, "one million", 3_000, 5_000),
             tu(3, "later", 7_000, 8_000)]
    client = LLMGia([too_long, valid])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert len(visuals) == 1
    assert visuals[0]["duration_seconds"] == 10
    assert visuals[0]["end_word_id"] == "w2"
    assert "10 giây" in visuals[0]["prompt"]
    assert len(client.messages) == 2
    feedback = json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "3 đến 6 giây" in feedback


def test_tao_y_tuong_goi_dung_hinh_dang_versus_list_sau_loi_schema():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=8_000, title="Shop và khách", reason="Hai phía cùng có lợi")
    malformed = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w22",
        "scene": "So sánh nhu cầu của shop và khách", "action": "Hai tờ giấy mở ra theo hai phía",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "VERSUS_LIST", "diagram": {
            "title": "Hai phía", "simulated": False,
            "docs": [{"title": "Shop", "label": "Mục tiêu", "value": "Giảm chi phí"},
                     {"title": "Khách", "label": "Mục tiêu", "value": "Mua có lợi"}],
            "layers": "Giảm chi phí trên mỗi đơn", "values": ["Mua có lợi", "Không bị ép mua"],
            "diff_label": "Cùng có lợi",
            "on": {"before": "Shop cần giảm chi phí", "after": "khách cần mua có lợi", "delta": "Hai bên cùng có lợi"},
        }},
    }]}
    valid = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w22",
        "scene": "So sánh nhu cầu của shop và khách", "action": "Hai tờ giấy mở ra theo hai phía",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "VERSUS_LIST", "diagram": {
            "title": "Hai phía", "simulated": False,
            "docs": [{"title": "Shop", "label": "Mục tiêu", "value": "Giảm chi phí"},
                     {"title": "Khách", "label": "Mục tiêu", "value": "Mua có lợi"}],
            "layers": ["Giảm chi phí", "Mỗi đơn"], "values": ["Mua có lợi", "Không bị ép mua"],
            "diff_label": "Cùng có lợi",
                "on": {"left": "Shop cần giảm chi phí trên mỗi đơn", "right": "khách cần mua có lợi không bị ép mua", "verdict": "Hai bên cùng có lợi"},
        }},
    }]}
    words = [tu(1, "Shop", 100, 300), tu(2, "cần", 300, 500), tu(3, "giảm", 500, 700),
             tu(4, "chi", 700, 900), tu(5, "phí", 900, 1100), tu(6, "trên", 1100, 1300),
             tu(7, "mỗi", 1300, 1500), tu(8, "đơn", 1500, 1700), tu(9, "khách", 2200, 2400),
             tu(10, "cần", 2400, 2600), tu(11, "mua", 2600, 2800), tu(12, "có", 2800, 3000),
             tu(13, "lợi", 3000, 3200), tu(14, "không", 3300, 3500), tu(15, "bị", 3500, 3700),
             tu(16, "ép", 3700, 3900), tu(17, "mua", 3900, 4100), tu(18, "Hai", 4500, 4700),
             tu(19, "bên", 4700, 4900), tu(20, "cùng", 4900, 5100), tu(21, "có", 5100, 5300),
             tu(22, "lợi", 5300, 5500)]
    client = LLMGia([malformed, valid])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client, flow_available=False)

    assert len(visuals) == 1 and visuals[0]["ui_scene"]["layout"] == "VERSUS_LIST"
    feedback = json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "mảng JSON" in feedback and "left/right/verdict" in feedback


def test_tao_y_tuong_goi_lai_versus_list_neu_noi_dung_chi_la_ten_hai_ben():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=8_000, title="Shop và khách", reason="Hai phía cùng có lợi")
    response = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w21",
        "scene": "Hai phía cùng cần lợi ích", "action": "Hai tấm giấy mở ra và lần lượt hiện lợi ích",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "VERSUS_LIST", "diagram": {
            "title": "Hai phía", "simulated": False,
            "docs": [{"title": "Shop", "label": "Góc nhìn", "value": "Giảm chi phí"},
                     {"title": "Khách", "label": "Góc nhìn", "value": "Mua có lợi"}],
            "layers": ["Shop", "Khách"], "values": ["Giảm chi phí mỗi đơn", "Mua nhiều thật sự có lợi"],
            "diff_label": "Combo có lợi", "on": {"left": "shop cần giảm chi phí trên mỗi đơn", "right": "khách cần mua nhiều thật sự có lợi", "verdict": "hai bên cùng có lợi"},
        }},
    }]}
    valid = json.loads(json.dumps(response, ensure_ascii=False))
    valid["visuals"][0]["ui_scene"]["diagram"]["layers"] = ["Giảm chi phí", "Mỗi đơn"]
    valid["visuals"][0]["ui_scene"]["diagram"]["values"] = ["Mua nhiều thật sự có lợi", "Khách cần mua"]
    words = [tu(1, "shop", 100, 300), tu(2, "cần", 300, 500), tu(3, "giảm", 500, 700),
             tu(4, "chi", 700, 900), tu(5, "phí", 900, 1100), tu(6, "trên", 1100, 1300),
             tu(7, "mỗi", 1300, 1500), tu(8, "đơn", 1500, 1700), tu(9, "khách", 2000, 2200),
             tu(10, "cần", 2200, 2400), tu(11, "mua", 2400, 2600), tu(12, "nhiều", 2600, 2800),
             tu(13, "thật", 2800, 3000), tu(14, "sự", 3000, 3200), tu(15, "có", 3200, 3400),
             tu(16, "lợi", 3400, 3600), tu(17, "hai", 4000, 4200), tu(18, "bên", 4200, 4400),
             tu(19, "cùng", 4400, 4600), tu(20, "có", 4600, 4800), tu(21, "lợi", 4800, 5000)]
    client = LLMGia([response, valid])

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client, flow_available=False)

    assert len(visuals) == 1
    feedback = json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "tên vai trò đơn thuần" in feedback and "cụm thoại có nghĩa" in feedback


def test_tao_y_tuong_hyperframes_cho_phep_after_va_delta_dung_chung_cum_thoai():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12_000, title="Doanh thu", reason="Có phép so sánh")
    event = {"visuals": [{
        "clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w8",
        "scene": "So sánh doanh thu trước và sau",
        "action": "Hai tờ giấy lần lượt mở để thể hiện kết quả",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Doanh thu", "simulated": False,
            "docs": [{"title": "Trước", "label": "Tổng", "value": "1 triệu"},
                     {"title": "Sau", "label": "Tổng", "value": "900 nghìn"}],
            "diff_label": "Giảm 100 nghìn",
            "on": {"before": "trước còn 1 triệu", "after": "sau còn 900 nghìn",
                   "delta": "sau còn 900 nghìn"},
        }},
    }]}
    words = [tu(1, "trước", 1_000, 1_200), tu(2, "còn", 1_200, 1_400),
             tu(3, "1", 1_400, 1_600), tu(4, "triệu", 1_600, 1_800),
             tu(5, "sau", 5_000, 5_200), tu(6, "còn", 5_200, 5_400),
             tu(7, "900", 5_400, 5_600), tu(8, "nghìn", 5_600, 5_800)]

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], LLMGia([event, event, event]))

    assert visuals and visuals[0]["target_start_word_id"] == "w1"
    assert visuals[0]["target_end_word_id"] == "w8"
    from src.modules.tao_video_noi_dung.planner import UiScene, resolve_diagram_times
    times = resolve_diagram_times(
        UiScene.model_validate(visuals[0]["ui_scene"]), visuals[0]["narration"],
        visuals[0]["duration_seconds"], visuals[0]["word_times"],
    )
    assert times["delta"] - times["after"] <= 0.4


def test_tao_y_tuong_hyperframes_thu_lai_khi_on_events_sai():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Đơn hàng", reason="So sánh số liệu")
    visual = {
        "clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1",
        "scene": "So sánh số đơn trước và sau",
        "action": "Hai hồ sơ giấy mở ra để lộ mức chênh lệch",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Đơn hàng",
            "docs": [
                {"title": "Trước", "label": "Đơn", "value": "100"},
                {"title": "Sau", "label": "Đơn", "value": "60"},
            ],
            "diff_label": "Giảm 40",
            "on": {
                "before": "trước là một trăm đơn", "after": "sau còn sáu mươi đơn",
                "delta": "giảm bốn mươi đơn",
            },
        }},
    }
    invalid = json.loads(json.dumps(visual, ensure_ascii=False))
    invalid["ui_scene"]["diagram"]["on"]["extra"] = "không có sự kiện này"
    client = LLMGia([{"visuals": [invalid]}, {"visuals": [visual]}])

    result = tao_y_tuong_dien_hoa_flow(
        [clip], [tu(1, "Trước là một trăm đơn, sau còn sáu mươi đơn, giảm bốn mươi đơn", 1000, 6000)], [], client,
    )

    retry_request = json.loads(client.messages[1][1]["content"])
    assert len(client.messages) == 2
    assert retry_request["validator_feedback"]
    assert "BEFORE_AFTER dùng before, after, delta" in retry_request["validator_feedback"]
    assert result[0]["renderer"] == "HYPERFRAMES"


def test_tao_y_tuong_bo_scene_neu_neo_loi_thoai_khong_con_hop_le(monkeypatch):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor

    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Orders", reason="Before and after")
    words = [tu(i, text, i * 500, i * 500 + 400) for i, text in enumerate(
        ["before", "sales", "were", "100", "after", "they", "were", "60", "difference", "40"], start=1
    )]
    visual = {"clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w10",
              "scene": "Compare two order counts", "action": "Paper cards reveal the change", "renderer": "HYPERFRAMES",
              "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
                  "title": "Orders", "docs": [{"title": "Before", "label": "Orders", "value": "100"},
                                                {"title": "After", "label": "Orders", "value": "60"}],
                  "diff_label": "Down by 40", "on": {"before": "before sales were 100", "after": "after they were 60",
                                                        "delta": "difference 40"},
              }}}
    client = LLMGia([{"visuals": [visual]}])
    resolve = editor.resolve_diagram_times
    calls = 0

    def fail_on_final_check(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("DIAGRAM_PHRASE_NOT_IN_NARRATION:k0")
        return resolve(*args, **kwargs)

    monkeypatch.setattr(editor, "resolve_diagram_times", fail_on_final_check)

    result = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert result == []
    assert clip.needs_review is True


def test_tao_y_tuong_hyperframes_thu_lai_toi_da_ba_lan_khi_llm_sua_tung_loi():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Đơn hàng", reason="So sánh số liệu")
    valid = {
        "clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1",
        "scene": "So sánh số đơn trước và sau",
        "action": "Hai hồ sơ giấy mở ra để lộ mức chênh lệch",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Đơn hàng",
            "docs": [
                {"title": "Trước", "label": "Đơn", "value": "100"},
                {"title": "Sau", "label": "Đơn", "value": "60"},
            ],
            "diff_label": "Giảm 40",
            "on": {
                "before": "trước là một trăm đơn", "after": "sau còn sáu mươi đơn",
                "delta": "giảm bốn mươi đơn",
            },
        }},
    }
    invalid_steps = {"visuals": [{**valid, "ui_scene": {"layout": "PROCESS_RAIL", "diagram": {
        "title": "Quy trình", "steps": ["Mở", "Chốt"], "on": {"stations": "mở và chốt", "block": "đang kẹt", "release": "thu tiền"},
    }}}]}
    invalid_events = json.loads(json.dumps({"visuals": [valid]}, ensure_ascii=False))
    invalid_events["visuals"][0]["ui_scene"]["diagram"]["on"]["extra"] = "không có sự kiện này"
    client = LLMGia([invalid_steps, invalid_events, {"visuals": [valid]}])

    result = tao_y_tuong_dien_hoa_flow(
        [clip], [tu(1, "Trước là một trăm đơn, sau còn sáu mươi đơn, giảm bốn mươi đơn", 1000, 6000)], [], client,
    )

    assert len(client.messages) == 3
    assert "DIAGRAM_EVENTS_MISMATCH" in json.loads(client.messages[2][1]["content"])["validator_feedback"]
    assert result[0]["renderer"] == "HYPERFRAMES"


def test_tao_y_tuong_hyperframes_sai_lan_cuoi_giu_clip_va_danh_dau_ra_soat():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Doanh thu", reason="Có số liệu")
    event = {
        "clip_id": clip.clip_id,
        "start_word_id": "w48", "end_word_id": "w50",
        "scene": "So sánh số liệu trước và sau",
        "action": "Ba lớp giấy lần lượt mở để lộ thay đổi",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Kết quả", "docs": [
                {"title": "Trước", "label": "Đơn", "value": "100"},
                {"title": "Sau", "label": "Đơn", "value": "60"},
            ], "diff_label": "Giảm", "on": {
                "before": "sau", "after": "trước", "delta": "giảm",
            },
        }},
    }
    response = {"visuals": [event]}
    client = LLMGia([response, response, response, response])
    tokens = ["xin chào", *(["đang"] * 46), "trước", "sau", "giảm", *(["nữa"] * 5)]
    words = [tu(index + 1, token, index * 200, index * 200 + 150) for index, token in enumerate(tokens)]

    result = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    assert result == []
    assert len(client.messages) == 4
    assert clip.needs_review is True
    assert "diễn họa" in clip.selection_reason.casefold()


def test_tao_y_tuong_hyperframes_feedback_neu_process_rail_thieu_buoc():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Đơn hàng", reason="So sánh số liệu")
    invalid = {"visuals": [{
        "clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1",
        "scene": "Quy trình thu tiền còn thiếu một bước",
        "action": "Ba lớp giấy mở ra để chỉ vị trí bị chặn",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "PROCESS_RAIL", "diagram": {
            "title": "Quy trình", "steps": ["Mở", "Chốt"], "block_step": 1,
            "on": {"stations": "mở và chốt", "block": "đang kẹt", "release": "thu tiền"},
        }},
    }]}
    corrected = {
        "visuals": [{
            "clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1",
            "scene": "So sánh số đơn trước và sau",
            "action": "Hai hồ sơ giấy mở ra để lộ mức chênh lệch",
            "renderer": "HYPERFRAMES",
            "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
                "title": "Đơn hàng",
                "docs": [
                    {"title": "Trước", "label": "Đơn", "value": "100"},
                    {"title": "Sau", "label": "Đơn", "value": "60"},
                ],
                "diff_label": "Giảm 40",
                "on": {
                    "before": "trước là một trăm đơn", "after": "sau còn sáu mươi đơn",
                    "delta": "giảm bốn mươi đơn",
                },
            }},
        }]
    }
    client = LLMGia([invalid, corrected])

    tao_y_tuong_dien_hoa_flow([clip], [tu(1, "Trước là một trăm đơn, sau còn sáu mươi đơn, giảm bốn mươi đơn", 1000, 6000)], [], client)

    feedback = json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "steps 3 đến 5 bước" in feedback


def test_tao_y_tuong_hyperframes_thu_lai_khi_moc_su_kien_sai_thu_tu():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=10000, title="Đơn hàng", reason="So sánh số liệu")
    base = {
        "clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w11",
        "scene": "So sánh đơn hàng trước và sau",
        "action": "Hai hồ sơ giấy mở ra để lộ mức thay đổi",
        "renderer": "HYPERFRAMES",
    }
    def scene(on):
        return {"visuals": [{**base, "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Đơn hàng",
            "docs": [{"title": "Trước", "label": "Đơn", "value": "100"},
                     {"title": "Sau", "label": "Đơn", "value": "60"}],
            "diff_label": "Giảm 40", "on": on,
        }}}]}
    client = LLMGia([
        scene({"before": "sau", "after": "trước", "delta": "giảm"}),
        scene({"before": "trước", "after": "sau", "delta": "giảm"}),
    ])
    texts = ["mở", "rồi", "nói", "về", "con", "số", "này", "xong", "trước", "sau", "giảm"]
    starts = [i * 1000 for i in range(10)] + [9800]
    words = [tu(i, text, starts[i - 1], starts[i - 1] + 100)
             for i, text in enumerate(texts, start=1)]

    visuals = tao_y_tuong_dien_hoa_flow([clip], words, [], client)

    feedback = json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "EVENT_ORDER" in feedback
    assert visuals[0]["renderer"] == "HYPERFRAMES"
    assert visuals[0]["target_start_word_id"] == "w9"
    assert visuals[0]["target_end_word_id"] == "w11"
    assert len(visuals[0]["word_times"]) == 3


def test_tao_y_tuong_hyperframes_feedback_neu_layout_chu_khong_phai_so_do():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Đơn hàng", reason="Số liệu cần giải thích")
    invalid = {"visuals": [{
        "clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1",
        "scene": "Sơ đồ số đơn trước và sau",
        "action": "Hai hồ sơ giấy mở ra để chỉ mức thay đổi",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "DASHBOARD", "diagram": {"title": "Đơn hàng"}},
    }]}
    corrected = {"visuals": [{
        "clip_id": "part1_01", "start_word_id": "w1", "end_word_id": "w1",
        "scene": "Sơ đồ số đơn trước và sau",
        "action": "Hai hồ sơ giấy mở ra để chỉ mức thay đổi",
        "renderer": "HYPERFRAMES",
        "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
            "title": "Đơn hàng",
            "docs": [
                {"title": "Trước", "label": "Đơn", "value": "100"},
                {"title": "Sau", "label": "Đơn", "value": "60"},
            ],
            "diff_label": "Giảm 40",
            "on": {
                "before": "trước là một trăm đơn", "after": "sau còn sáu mươi đơn",
                "delta": "giảm bốn mươi đơn",
            },
        }},
    }]}
    client = LLMGia([invalid, corrected])

    tao_y_tuong_dien_hoa_flow(
        [clip], [tu(1, "Trước là một trăm đơn, sau còn sáu mươi đơn, giảm bốn mươi đơn", 1000, 6000)], [], client,
    )

    feedback = json.loads(client.messages[1][1]["content"])["validator_feedback"]
    assert "DASHBOARD" in feedback
    assert "DIAGRAM_LAYOUTS" in feedback


def test_tao_y_tuong_hyperframes_feedback_neu_scene_so_do_co_messages():
    from src.modules.tao_video_noi_dung.planner import diagram_feedback

    hints = diagram_feedback("visuals.0.ui_scene\n  Value error, DIAGRAM_SCENE_HAS_NO_MESSAGES [type=value_error]")

    assert "messages phải rỗng" in " ".join(hints)


def test_chan_y_tuong_flow_cho_clip_khong_co_trong_ke_hoach():
    client = LLMGia([{"visuals": [{
        "clip_id": "ngoai_ke_hoach", "start_word_id": "w1", "end_word_id": "w1",
        "renderer": "FLOW",
        "scene": "Một ngọn núi giấy gấp nổi trên mây",
        "action": "Ngọn núi mở ra thành từng lớp giấy theo chiều dọc",
    }]}])
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Bài học", reason="Đủ ý")

    with pytest.raises(ValueError, match="LLM_FLOW_VISUAL_CLIP_INVALID"):
        tao_y_tuong_dien_hoa_flow([clip], [tu(1, "kiên trì", 1000, 1500)], [], client)


def test_prompt_dien_hoa_dai_duoc_chia_nho_theo_gioi_han_llm():
    clips = [ClipTuDong(clip_id=f"part{i}", start_ms=i * 12000, end_ms=(i + 1) * 12000,
                        title="Thông điệp", reason="Đủ ý") for i in range(30)]
    words = [tu(i, "hướng dẫn", i * 12000, i * 12000 + 400) for i in range(30)]
    candidates = [{"asset_id": f"paper{i}", "scene": "Minh họa gấp giấy", "narration": "Gấp từng nếp",
                   "duration_seconds": 10, "has_alpha": False} for i in range(5)]
    client = LLMGia([{"actions": []} for _ in range(30)])
    client.max_input_bytes = 5000

    actions = chon_dien_hoa(clips, words, candidates, client)

    assert actions == []
    assert len(client.messages) > 1
    assert all(sum(len(message["content"].encode("utf-8")) for message in call) <= client.max_input_bytes
               for call in client.messages)


def test_dien_hoa_dai_hon_asset_duoc_cat_theo_bien_tu_va_danh_dau_ra_soat():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=20000, title="Thông điệp", reason="Đủ ý")
    words = [tu(i, f"từ{i}", (i - 1) * 1000, (i - 1) * 1000 + 500) for i in range(1, 16)]
    client = LLMGia([{"actions": [{
        "clip_id": "part1_01", "asset_id": "paper", "mode": "CUTAWAY",
        "start_word_id": "w1", "end_word_id": "w15", "reason": "Minh hoạ nội dung",
    }]}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "paper", "scene": "Nhân vật giấy gấp", "narration": "Minh họa",
        "duration_seconds": 10, "has_alpha": False,
    }], client)

    assert len(actions) == 1
    assert actions[0]["end_ms"] == 9500
    assert actions[0]["end_word_id"] == "w10"
    assert clip.needs_review is True


def test_dien_hoa_chong_len_nhau_bo_action_sau_va_danh_dau_ra_soat():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=10000, title="Thông điệp", reason="Đủ ý")
    words = [tu(i, f"từ{i}", (i - 1) * 1000, (i - 1) * 1000 + 500) for i in range(1, 9)]
    client = LLMGia([{"actions": [
        {"clip_id": "part1_01", "asset_id": "paper", "mode": "CUTAWAY",
         "start_word_id": "w1", "end_word_id": "w4", "reason": "Cảnh đầu"},
        {"clip_id": "part1_01", "asset_id": "paper", "mode": "CUTAWAY",
         "start_word_id": "w3", "end_word_id": "w6", "reason": "Cảnh chồng"},
    ]}])

    actions = chon_dien_hoa([clip], words, [{
        "asset_id": "paper", "scene": "Nhân vật giấy gấp", "narration": "Minh họa",
        "duration_seconds": 10, "has_alpha": False,
    }], client)

    assert len(actions) == 1
    assert actions[0]["start_word_id"] == "w1"
    assert clip.needs_review is True


def test_dien_hoa_tu_choi_asset_id_llm_khong_co_trong_danh_sach():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Thông điệp", reason="Đủ ý")
    words = [tu(1, "doanh thu", 0, 900), tu(2, "tăng", 1000, 1800)]
    client = LLMGia([{"actions": [{
        "clip_id": "part1_01", "asset_id": "asset-khong-ton-tai", "mode": "CUTAWAY",
        "start_word_id": "w1", "end_word_id": "w2", "reason": "Minh họa",
    }]}])

    with pytest.raises(ValueError, match="UNKNOWN_VISUAL_CANDIDATE"):
        chon_dien_hoa([clip], words, [{
            "asset_id": "paper", "scene": "Sơ đồ giấy", "narration": "Doanh thu",
            "duration_seconds": 2, "has_alpha": False,
        }], client)


def test_ung_vien_dien_hoa_nhan_video_alpha_webm(tmp_path, monkeypatch):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    workspace_id, project_id, plan_id, asset_id = "ws-alpha", "project-alpha", "plan-alpha", "paper-alpha"
    media_root = tmp_path / "media"
    media_root.mkdir()
    asset_path = media_root / "paper.webm"
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=red@0.7:s=80x80:r=24:d=2,format=yuva420p", "-an",
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
        "-metadata:s:v:0", "alpha_mode=1", str(asset_path),
    ], capture_output=True, check=True)
    try:
        db.add(Workspace(id=workspace_id, name="Alpha", slug=workspace_id))
        db.add(ProductionProject(id=project_id, workspace_id=workspace_id, title="Alpha", created_by="user"))
        db.add(ContentVideoPlan(
            id=plan_id, workspace_id=workspace_id, project_id=project_id, revision=1,
            source_content="origami", content_sha256="a" * 64, target_duration_seconds=10,
            style_snapshot_json="{}", style_snapshot_sha256="b" * 64,
            storyboard_json=json.dumps({"shots": [{"shot_id": "shot-1", "scene": "Paper", "narration": "Fold", "duration_seconds": 6}]}),
            storyboard_sha256="c" * 64, llm_model="model", created_by="user",
        ))
        db.add(ContentVideoRun(
            id="run-alpha", workspace_id=workspace_id, project_id=project_id, plan_id=plan_id,
            plan_revision=1, storyboard_sha256="c" * 64, style_snapshot_sha256="b" * 64,
            approval_sha256="d" * 64, idempotency_key="alpha", status="COMPLETED",
            steps_json=json.dumps([{"shot_id": "shot-1", "asset_id": asset_id, "state": "SUCCEEDED"}]),
            created_by="user",
        ))
        db.add(MediaAsset(
            id=asset_id, workspace_id=workspace_id, project_id=project_id, storage_key="paper.webm",
            sha256="e" * 64, byte_size=asset_path.stat().st_size, mime_detected="video/webm",
            duration_ms=6000, source_product="GOOGLE_FLOW_I2V", original_filename="paper.webm", created_by="user",
        ))
        db.commit()
        monkeypatch.setattr(editor, "MEDIA_ROOT_DIR", media_root)

        candidates = editor.lay_ung_vien_dien_hoa(db, workspace_id, project_id)

        assert [item["asset_id"] for item in candidates] == [asset_id]
        assert candidates[0]["has_alpha"] is True
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_he_thong_tu_tao_clip_id_khong_dung_id_llm():
    words = [tu(1, "xin", 0, 300), tu(2, "chào", 11500, 12000)]
    client = LLMGia([{
        "clips": [{
            "clip_id": "../../outside",
            "start_word_id": "w1",
            "end_word_id": "w2",
            "title": "Tiêu đề",
            "reason": "Có ý nghĩa.",
            "effect": "none",
        }]
    }])

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=15000)

    assert plan.clips[0].clip_id == "part1_01"


def test_transcript_dai_duoc_chia_theo_byte_ma_giu_nguyen_tu():
    from src.modules.dieu_phoi_dung.dung_video_dai import chia_transcript

    words = [tu(i, "nội dung", i * 1000, i * 1000 + 500) for i in range(40)]

    chunks = chia_transcript(words, max_input_bytes=1500)

    assert len(chunks) > 1
    assert [word["id"] for chunk in chunks for word in chunk] == [word["id"] for word in words]
    assert all(len(json.dumps(chunk, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= 1500 for chunk in chunks)


def test_prompt_ke_hoach_video_tinh_ca_system_schema_va_feedback_trong_gioi_han():
    class ClientGioiHan(LLMGia):
        max_input_bytes = 5500

        def complete(self, messages, max_tokens=None):
            size = sum(len(message["content"].encode("utf-8")) for message in messages)
            assert size <= self.max_input_bytes
            return type("KetQua", (), {"content": '{"clips": []}'})()

    words = [tu(i, f"noi_dung_{i}_" + "x" * 50, i * 700, i * 700 + 400) for i in range(150)]
    client = ClientGioiHan([])

    with pytest.raises(ValueError, match="NO_SOCIAL_CLIPS_SELECTED"):
        tao_ke_hoach_dung_video(words, client, source_duration_ms=110000)


def test_prompt_ke_hoach_video_dai_khong_vuot_gioi_han_llm():
    class ClientGioiHan:
        max_input_bytes = 200000
        max_output_tokens = 1200
        is_enabled = True

        def __init__(self):
            self.messages = []

        def complete(self, messages, max_tokens=None):
            self.messages.append(messages)
            return type("KetQua", (), {"content": '{"clips": []}'})()

    words = [tu(i, "noi_dung_" + "x" * 120, i * 500, i * 500 + 400) for i in range(1400)]
    pauses = [(i * 4000, i * 4000 + 1000) for i in range(200)]
    client = ClientGioiHan()

    with pytest.raises(ValueError, match="NO_SOCIAL_CLIPS_SELECTED"):
        tao_ke_hoach_dung_video(words, client, source_duration_ms=800000, pause_intervals=pauses)

    prompt_sizes = [sum(len(message["content"].encode("utf-8")) for message in call) for call in client.messages]
    assert len(client.messages) > 1
    assert max(prompt_sizes) >= 195000
    assert all(size <= client.max_input_bytes for size in prompt_sizes)


def test_nhom_take_trung_qua_nhieu_chunk_va_giu_lua_chon_tot_nhat():
    candidates = [
        ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Cách chăm sóc", reason="Take đủ ý.", effect="none"),
        ClipTuDong(clip_id="part2_01", start_ms=20000, end_ms=32000, title="Cách chăm sóc", reason="Take vấp và thiếu ý.", effect="none"),
        ClipTuDong(clip_id="part2_02", start_ms=40000, end_ms=52000, title="Cách đóng gói", reason="Kịch bản khác.", effect="none"),
    ]
    client = LLMGia([{"groups": [
        {"clip_ids": ["part1_01", "part2_01"], "selected_clip_id": "part1_01", "reason": "Take đầu đủ ý và rõ hơn.", "needs_review": False},
        {"clip_ids": ["part2_02"], "selected_clip_id": "part2_02", "reason": "Kịch bản độc lập.", "needs_review": True},
    ]}])

    result = chon_va_nhom_take(candidates, client)

    assert [clip.clip_id for clip in result.clips] == ["part1_01", "part2_02"]
    assert result.clips[0].selected_take_id == "part1_01"
    assert [take["take_id"] for take in result.clips[0].take_options] == ["part1_01", "part2_01"]
    assert result.clips[0].needs_review is False
    assert result.clips[1].needs_review is True


def test_nhom_take_truyen_transcript_va_diem_asr_de_danh_dau_take_kem():
    candidates = [
        ClipTuDong(clip_id="clear", start_ms=0, end_ms=12000, title="Cách chăm sóc", reason="Take rõ."),
        ClipTuDong(clip_id="unclear", start_ms=20000, end_ms=32000, title="Cách chăm sóc", reason="Take vấp."),
    ]
    words = [
        {**tu(1, "cây xanh", 0, 200), "probability": 0.96},
        {**tu(2, "mỗi ngày", 300, 500), "probability": 0.92},
        {**tu(3, "cây xanh", 20000, 20200), "probability": 0.40},
        {**tu(4, "mỗi ngày", 20300, 20500), "probability": 0.65},
    ]
    client = LLMGia([{"groups": [{
        "clip_ids": ["clear", "unclear"], "selected_clip_id": "unclear",
        "reason": "Take complete.", "needs_review": False,
    }]}])

    result = chon_va_nhom_take(candidates, client, words)

    payload = json.loads(client.messages[0][1]["content"])["cac_take_ung_vien"]
    assert payload[0]["transcript"] == "cây xanh mỗi ngày"
    assert payload[0]["asr_confidence"] == 0.94
    assert payload[1]["asr_confidence"] == 0.525
    assert payload[1]["low_confidence_word_ratio"] == 0.5
    assert "transcript" in client.messages[0][0]["content"]
    assert "ASR" in client.messages[0][0]["content"]
    assert result.clips[0].needs_review is True
    assert "ASR" in result.clips[0].selection_reason


def test_nhom_take_rut_gon_transcript_de_tuan_thu_gioi_han_llm():
    candidates = [
        ClipTuDong(clip_id="a", start_ms=0, end_ms=12000, title="A", reason="A."),
        ClipTuDong(clip_id="b", start_ms=20000, end_ms=32000, title="B", reason="B."),
    ]
    words = [
        tu(1, "start " + "x" * 6000 + " end", 0, 1000),
        tu(2, "start " + "y" * 6000 + " end", 20000, 21000),
    ]
    client = LLMGia([{"groups": [
        {"clip_ids": ["a"], "selected_clip_id": "a", "reason": "A.", "needs_review": False},
        {"clip_ids": ["b"], "selected_clip_id": "b", "reason": "B.", "needs_review": False},
    ]}])
    client.max_input_bytes = 9000

    chon_va_nhom_take(candidates, client, words)

    user_content = client.messages[0][1]["content"]
    payload = json.loads(user_content)["cac_take_ung_vien"]
    assert len(user_content.encode("utf-8")) <= client.max_input_bytes - 1500
    assert all(item["transcript"].startswith("start") and item["transcript"].endswith("end") for item in payload)
    assert all("..." in item["transcript"] for item in payload)
    assert "..." in client.messages[0][0]["content"]


def test_take_don_le_bat_co_nguong_asr_thap_van_can_ra_soat():
    clip = ClipTuDong(clip_id="single", start_ms=0, end_ms=12000, title="Hướng dẫn", reason="Đủ ý.")
    client = LLMGia([])

    result = chon_va_nhom_take([clip], client, [{**tu(1, "ừm", 100, 300), "probability": 0.35}])

    assert result.clips[0].needs_review is True
    assert "ASR" in result.clips[0].selection_reason
    assert client.messages == []


def test_nguong_asr_12_phan_tram_giam_co_gan_cua_soat():
    clip = ClipTuDong(clip_id="single", start_ms=0, end_ms=12000, title="Title", reason="Reason")

    def evidence(low_count):
        words = [
            {**tu(i, "word", i * 100, i * 100 + 50), "probability": 0.49 if i < low_count else 0.9}
            for i in range(100)
        ]
        return _take_evidence(clip, words)

    assert evidence(11)["needs_review"] is False
    assert evidence(12)["needs_review"] is True


def test_ke_hoach_gom_hai_luot_cung_kich_ban_thanh_mot_clip():
    words = [tu(1, "chăm", 0, 300), tu(2, "sóc", 11500, 12000), tu(3, "chăm", 20000, 20300), tu(4, "sóc", 31500, 32000)]
    client = LLMGia([
        {"clips": [
            {"start_word_id": "w1", "end_word_id": "w2", "title": "Cách chăm sóc", "reason": "Take thiếu ý.", "effect": "none"},
            {"start_word_id": "w3", "end_word_id": "w4", "title": "Cách chăm sóc", "reason": "Take đầy đủ và rõ.", "effect": "none"},
        ]},
        {"groups": [{"clip_ids": ["part1_01", "part1_02"], "selected_clip_id": "part1_02", "reason": "Take sau đầy đủ hơn.", "needs_review": False}]},
    ])

    def retranscribe(candidates, current_words):
        candidates[1].needs_review = True
        candidates[1].transcription_provider = "9router_cx_transcribe"
        return [{**word, "text": "chăm sóc chính xác" if word["id"] == "w1" else word["text"]}
                for word in current_words]

    plan = tao_ke_hoach_dung_video(words, client, source_duration_ms=33000, candidate_transcriber=retranscribe)

    assert len(plan.clips) == 1
    assert plan.clips[0].start_ms == 20000
    assert [take["take_id"] for take in plan.clips[0].take_options] == ["part1_01", "part1_02"]
    assert len(client.messages) == 2
    assert "take_options" not in json.dumps(json.loads(client.messages[0][1]["content"])["schema"])
    take_prompt = json.loads(client.messages[1][1]["content"])
    assert "chăm sóc chính xác" in json.dumps(take_prompt, ensure_ascii=False)
    assert plan.clips[0].needs_review is True
    assert "Cần rà soát." in plan.clips[0].selection_reason


def test_nhom_take_chan_candidate_id_khong_ton_tai():
    candidates = [
        ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Một ý", reason="Đủ ý.", effect="none"),
        ClipTuDong(clip_id="part2_01", start_ms=20000, end_ms=32000, title="Một ý", reason="Take lặp.", effect="none"),
    ]
    client = LLMGia([{"groups": [{
        "clip_ids": ["part1_01", "unknown"], "selected_clip_id": "part1_01", "reason": "Take rõ.", "needs_review": False,
    }]}])

    with pytest.raises(ValueError, match="UNKNOWN_TAKE_CANDIDATE"):
        chon_va_nhom_take(candidates, client)


def test_pause_1800ms_con_lai_250ms():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Một ý", reason="Đủ ý.", effect="none")

    cuts = _cut_intervals(clip, [], [(2000, 3800)])

    assert cuts == [(2125, 3675)]


def test_filler_va_pause_chong_lan_chi_cat_mot_lan():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Một ý", reason="Đủ ý.", cut_word_ids=["w1"], effect="none")

    cuts = _cut_intervals(clip, [tu(1, "ừm", 2500, 2600)], [(2000, 3800)])

    assert cuts == [(2125, 3675)]


def test_caption_sau_cut_duoc_doi_moc_dung():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Một ý", reason="Đủ ý.", effect="none")
    words = [tu(1, "trước.", 500, 800), tu(2, "sau", 4000, 4300)]
    cuts = _cut_intervals(clip, words, [(2000, 3800)])

    captions = _caption_track(clip, words, cuts)

    assert next(caption for caption in captions if caption["text"] == "sau")["start_ms"] == 2450


def test_caption_karaoke_giu_moc_tung_tu_sau_khi_cat_pause():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=5000, title="Một ý", reason="Đủ ý.")
    words = [tu(1, "trước", 500, 700), tu(2, "sau", 4000, 4300)]

    captions = [item for item in _caption_track(clip, words, [(2000, 3800)]) if item.get("words")]

    assert [(item["text"], item["start_ms"]) for item in captions] == [("trước", 500), ("sau", 2200)]
    assert captions[1]["words"] == [{"text": "sau", "start_ms": 2200, "end_ms": 2500}]


def test_caption_karaoke_ghep_token_so_va_giu_nhip_ngan():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=6000, title="Một ý", reason="Đủ ý.")
    texts = ["còn", "10", ".000", "Sau", "các", "chi", "phí", "trực", "tiếp"]
    words = [tu(i, text, i * 500, i * 500 + 300) for i, text in enumerate(texts)]

    captions = [item for item in _caption_track(clip, words, []) if item.get("words")]

    assert "10.000" in [word["text"] for caption in captions for word in caption["words"]]
    assert all(len(caption["words"]) <= 6 for caption in captions)
    assert all(caption["duration_ms"] <= 2800 for caption in captions)


def test_transcript_9router_duoc_can_moc_va_remap_filler_callout():
    clip = ClipTuDong(
        clip_id="part1_01", start_ms=100, end_ms=1700, title="Một ý", reason="Đủ ý.",
        cut_word_ids=["w2"], callout_word_ids=["w3", "w4"], needs_review=True,
    )
    words = [
        tu(0, "trước", 0, 90),
        tu(1, "xin", 100, 300),
        tu(2, "ừm", 400, 500),
        tu(3, "tăng", 800, 1000),
        tu(4, "giả", 1500, 1700),
        tu(5, "sau", 1800, 2000),
    ]

    corrected = _replace_clip_words(clip, words, "xin tăng giá.")

    clip_words = [word for word in corrected if clip.start_ms <= word["start_ms"] and word["end_ms"] <= clip.end_ms]
    assert [word["text"] for word in clip_words] == ["xin", "tăng", "giá."]
    assert all(clip.start_ms <= word["start_ms"] < word["end_ms"] <= clip.end_ms for word in clip_words)
    assert [word["id"] for word in corrected if word["id"] in {"w0", "w5"}] == ["w0", "w5"]
    assert clip.cut_word_ids == []
    assert clip.callout_word_ids == [clip_words[1]["id"], clip_words[2]["id"]]
    assert clip.transcription_provider == "9router_cx_transcribe"
    assert clip.needs_review is True


def test_transcript_9router_remap_id_cua_take_bi_chong_lan():
    first = ClipTuDong(
        clip_id="part1_01", start_ms=100, end_ms=1700, title="Take đầu", reason="Đủ ý.",
        cut_word_ids=["w2"], callout_word_ids=["w3"],
    )
    overlapping = ClipTuDong(
        clip_id="part1_02", start_ms=400, end_ms=1600, title="Take sau", reason="Đủ ý.",
        cut_word_ids=["w2"], callout_word_ids=["w3"],
    )
    words = [
        tu(1, "xin", 100, 300), tu(2, "ừm", 400, 500),
        tu(3, "tăng", 800, 1000), tu(4, "giá", 1500, 1700),
    ]

    corrected = _replace_clip_words(first, words, "xin ừm tăng giá", [first, overlapping])

    assert overlapping.cut_word_ids == ["stt_part1_01_0001"]
    assert overlapping.callout_word_ids == ["stt_part1_01_0002"]
    assert all(word_id in {word["id"] for word in corrected} for word_id in overlapping.cut_word_ids + overlapping.callout_word_ids)


def test_transcript_alignment_rejects_empty_or_missing_local_words():
    clip = ClipTuDong(clip_id="part1_01", start_ms=100, end_ms=1700, title="Một ý", reason="Đủ ý.")

    with pytest.raises(ValueError, match="STT_ALIGNMENT_INPUT_INVALID"):
        _replace_clip_words(clip, [], "xin tăng giá")


def test_retranscribe_every_candidate_uses_router_and_removes_temp_audio(monkeypatch, tmp_path):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor

    audio_path = tmp_path / "nguon.wav"
    audio_path.write_bytes(b"wav")
    clip = ClipTuDong(
        clip_id="part1_01", start_ms=100, end_ms=1700, title="Một ý", reason="Đủ ý.", needs_review=False,
    )
    local = [tu(1, "xin", 100, 300), tu(2, "tăng", 800, 1000), tu(3, "giả", 1500, 1700)]
    calls = []

    def render_audio(args, **_kwargs):
        target = Path(args[-1])
        target.write_bytes(b"mp3")
        return SimpleNamespace(returncode=0)

    class RouterClient:
        def transcribe_audio(self, path):
            calls.append(path)
            return "xin tăng giá."

        def complete(self, messages, max_tokens=None):
            prompt = json.loads(messages[-1]["content"])
            assert prompt["whisper_transcript"] == "xin tăng giả"
            assert prompt["router_transcript"] == "xin tăng giá."
            return type("KetQua", (), {"content": json.dumps({"transcript": "xin tăng giá.", "needs_review": False})})()

    monkeypatch.setattr(editor, "run_media_command", render_audio)
    corrected = _retranscribe_candidates(audio_path, [clip], local, RouterClient())

    assert len(calls) == 1
    assert [word["text"] for word in corrected] == ["xin", "tăng", "giá."]
    assert clip.transcription_provider == "9router_cx_transcribe"
    assert clip.needs_review is False
    assert "Đã nhận dạng bằng 9Router" in clip.selection_reason
    assert "Đã đối chiếu hai bản phiên âm bằng LLM" in clip.selection_reason
    assert not calls[0].exists()


def test_retranscribe_reconciliation_error_keeps_router_transcript_and_marks_review(monkeypatch, tmp_path):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor
    from src.modules.llm.client import LLMResponseError

    audio_path = tmp_path / "nguon.wav"
    audio_path.write_bytes(b"wav")
    clip = ClipTuDong(clip_id="part1_01", start_ms=100, end_ms=1700, title="Một ý", reason="Đủ ý.")
    local = [tu(1, "xin", 100, 300), tu(2, "tăng", 800, 1000), tu(3, "giả", 1500, 1700)]

    def render_audio(args, **_kwargs):
        Path(args[-1]).write_bytes(b"mp3")
        return SimpleNamespace(returncode=0)

    class RouterClient:
        def transcribe_audio(self, _path):
            return "xin tăng giá."

        def complete(self, _messages, max_tokens=None):
            raise LLMResponseError("failed", error_code="UPSTREAM_TIMEOUT")

    monkeypatch.setattr(editor, "run_media_command", render_audio)
    corrected = _retranscribe_candidates(audio_path, [clip], local, RouterClient())

    assert [word["text"] for word in corrected] == ["xin", "tăng", "giá."]
    assert clip.transcription_provider == "9router_cx_transcribe"
    assert clip.needs_review is True
    assert "UPSTREAM_TIMEOUT" in clip.selection_reason


def test_retranscribe_router_error_keeps_whisper_words_and_review_flag(monkeypatch, tmp_path):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor
    from src.modules.llm.client import LLMResponseError

    audio_path = tmp_path / "nguon.wav"
    audio_path.write_bytes(b"wav")
    clip = ClipTuDong(
        clip_id="part1_01", start_ms=100, end_ms=1700, title="Một ý", reason="Đủ ý.", needs_review=True,
    )
    local = [tu(1, "xin", 100, 300)]

    def render_audio(args, **_kwargs):
        Path(args[-1]).write_bytes(b"mp3")
        return SimpleNamespace(returncode=0)

    class RouterClient:
        def transcribe_audio(self, _path):
            raise LLMResponseError("failed", error_code="UPSTREAM_TIMEOUT")

    monkeypatch.setattr(editor, "run_media_command", render_audio)
    corrected = _retranscribe_candidates(audio_path, [clip], local, RouterClient())

    assert corrected == local
    assert clip.transcription_provider == "faster_whisper"
    assert clip.needs_review is True
    assert "UPSTREAM_TIMEOUT" in clip.selection_reason


def test_dung_video_dai_render_luu_nhieu_clip_va_giu_nguyen_nguon(monkeypatch, tmp_path):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    workspace_id = f"ws-auto-edit-{uuid.uuid4().hex[:8]}"
    user_id = f"user-auto-edit-{uuid.uuid4().hex[:8]}"
    job_id = f"auto-edit-empty-visuals-{uuid.uuid4().hex[:8]}"
    media_root = tmp_path / "media"
    source_path = media_root / "workspaces" / workspace_id / "media" / "nguon.mp4"
    source_path.parent.mkdir(parents=True)
    try:
        run_media_command([
            video_processor.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", "color=c=0x1E293B:s=270x480:r=30:d=12",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source_path),
        ], capture_output=True, check=True)
        original_hash, original_size = security.hash_file(source_path)
        source = MediaAsset(
            id=str(uuid.uuid4()), workspace_id=workspace_id,
            storage_key=source_path.relative_to(media_root).as_posix(), sha256=original_hash,
            byte_size=original_size, mime_detected="video/mp4", duration_ms=12_000,
            source_product="UPLOAD", original_filename="nguon.mp4", created_by=user_id,
        )
        db.add(Workspace(id=workspace_id, name="Kiểm thử dựng video", slug=workspace_id))
        db.add(source)
        db.add(AIGenerationJob(
            id=job_id, workspace_id=workspace_id, asset_type="VIDEO", provider="MEDIA_VIDEO",
            provider_mode="QUEUE", model_id="model-kiem-thu", idempotency_key=job_id,
            state="RUNNING", request_payload_json=json.dumps({"parameters": {"profile_id": None}}),
            created_by=user_id,
        ))
        db.commit()
        monkeypatch.setattr(security, "MEDIA_ROOT_DIR", media_root)
        monkeypatch.setattr(editor, "MEDIA_ROOT_DIR", media_root)

        class LLMThat:
            is_enabled = True
            model = "model-kiem-thu"
            max_input_bytes = 9000
            max_output_tokens = 1200

            def complete(self, _messages, max_tokens=None):
                return type("KetQua", (), {"content": json.dumps({
                    "clips": [{
                        "start_word_id": "w000000", "end_word_id": "w000002",
                        "title": "Lời nói nguyên gốc", "reason": "Đoạn tổng hợp để kiểm thử.",
                        "cut_word_ids": ["w000001"], "callout_word_ids": ["w000002"],
                        "effect": "punch_in",
                    }]
                }, ensure_ascii=False)})()

            def transcribe_audio(self, _audio_path):
                return "xin ừm chào"

        transcript = [
            {"text": "xin", "start_ms": 0, "end_ms": 300},
            {"text": "ừm", "start_ms": 6000, "end_ms": 6400},
            {"text": "chào", "start_ms": 11500, "end_ms": 12000},
        ]
        monkeypatch.setattr(editor.LLMClient, "from_db", classmethod(lambda _cls, _db: LLMThat()))
        monkeypatch.setattr(editor, "transcribe_words_cached", lambda *_args: transcript)
        monkeypatch.setattr(editor, "tao_y_tuong_dien_hoa_flow", lambda *_args: [])

        outputs = editor.dung_video_dai(
            db, source_asset_id=source.id, workspace_id=workspace_id, user_id=user_id,
            project_id=None, job_id=job_id,
        )

        videos = [asset for asset in outputs if asset.mime_detected == "video/mp4"]
        subtitles = [asset for asset in outputs if asset.mime_detected == "application/x-subrip"]
        manifests = [asset for asset in outputs if asset.mime_detected == "application/json"]
        assert len(videos) == 1 and len(subtitles) == 1 and len(manifests) == 1
        assert all(asset.approval_state == "UNREVIEWED" for asset in outputs)
        assert videos[0].parent_asset_id == source.id
        assert subtitles[0].parent_asset_id == videos[0].id
        assert manifests[0].parent_asset_id == source.id
        output_path = media_root / videos[0].storage_key
        rendered = video_processor.probe_video(output_path)
        assert rendered["width"] == 1080 and rendered["height"] == 1920
        assert rendered["frame_rate"] == pytest.approx(30, abs=0.1)
        assert rendered["duration_seconds"] == pytest.approx(11.48, abs=0.25)
        assert audio_processor.probe_audio(output_path)["codec_name"] == "aac"
        subtitle_text = (media_root / subtitles[0].storage_key).read_text(encoding="utf-8")
        assert "00:00:00," in subtitle_text and "xin" in subtitle_text and "chào" in subtitle_text
        subtitle_starts = [line.split(" --> ", 1)[0] for line in subtitle_text.splitlines() if " --> " in line]
        assert subtitle_starts == sorted(subtitle_starts)
        manifest = json.loads((media_root / manifests[0].storage_key).read_text(encoding="utf-8"))
        assert manifest["clips"][0]["removed_filler_word_ids"] == ["stt_part1_01_0001"]
        assert manifest["clips"][0]["callout_word_ids"] == ["stt_part1_01_0002"]
        assert manifest["clips"][0]["effect"] == "punch_in"
        assert manifest["clips"][0]["timeline"]["quality_checks"] == {
            "full_decode": "PASS", "long_black_segments": [],
        }
        assert manifest["clips"][0]["timeline"]["brand_end_card"]["logo_asset"] == "logo_doc_mau.png"
        assert security.hash_file(source_path)[0] == original_hash
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_auto_edit_enqueue_hyperframes_diagram_child(monkeypatch, tmp_path):
    from src.modules.dieu_phoi_dung import dung_video_dai as editor
    from src.modules.tao_video_noi_dung.service import _PILOT_STYLE_SNAPSHOT

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    workspace_id, user_id, job_id = "ws-auto-hf", "user-auto-hf", "auto-edit-parent-hf"
    media_root = tmp_path / "media"
    source_path = media_root / "workspaces" / workspace_id / "media" / "source.mp4"
    source_path.parent.mkdir(parents=True)
    try:
        run_media_command([
            video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=0x1E293B:s=270x480:r=30:d=12",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=12", "-shortest", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-c:a", "aac", str(source_path),
        ], capture_output=True, check=True)
        source_hash, source_size = security.hash_file(source_path)
        source = MediaAsset(
            id="source-hf", workspace_id=workspace_id, storage_key=source_path.relative_to(media_root).as_posix(),
            sha256=source_hash, byte_size=source_size, mime_detected="video/mp4", duration_ms=12000,
            source_product="UPLOAD", created_by=user_id,
        )
        db.add(Workspace(id=workspace_id, name="Auto Edit HyperFrames", slug=workspace_id))
        db.add(source)
        parent = AIGenerationJob(
            id=job_id, workspace_id=workspace_id, asset_type="VIDEO", provider="MEDIA_VIDEO",
            provider_mode="QUEUE", model_id="auto-edit", idempotency_key="auto-edit-parent-hf-key",
            state="RUNNING", request_payload_json=json.dumps({"parameters": {"profile_id": None}}),
            created_by=user_id,
        )
        db.add(parent)
        db.commit()
        monkeypatch.setattr(security, "MEDIA_ROOT_DIR", media_root)
        monkeypatch.setattr(editor, "MEDIA_ROOT_DIR", media_root)
        def extract_audio(args, **_kwargs):
            Path(args[-1]).write_bytes(b"wav")
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(editor, "run_media_command", extract_audio)
        words = [
            {"id": f"w{index:06d}", "text": text, "start_ms": index * 3000, "end_ms": index * 3000 + 500}
            for index, text in enumerate(("trước", "là", "một", "trăm", "sau", "còn", "sáu", "mươi"))
        ]
        monkeypatch.setattr(editor, "transcribe_words_cached", lambda *_args: words)
        monkeypatch.setattr(editor, "phat_hien_khoang_nghi", lambda *_args: [])
        monkeypatch.setattr(editor, "tinh_muc_song", lambda *_args: [0])
        monkeypatch.setattr(editor.LLMClient, "from_db", classmethod(lambda _cls, _db: SimpleNamespace(model="real-model")))
        monkeypatch.setattr(editor, "tao_ke_hoach_dung_video", lambda *_args, **_kwargs: TaoKeHoachDungVideo(clips=[
            ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12000, title="Đơn hàng", reason="Có phép so sánh"),
        ]))
        style = _PILOT_STYLE_SNAPSHOT.model_dump(mode="json")
        style_hash = hashlib.sha256(json.dumps(style, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        monkeypatch.setattr(editor, "tao_y_tuong_dien_hoa_flow", lambda *_args: [{
            "clip_id": "part1_01", "target_clip_id": "part1_01", "renderer": "HYPERFRAMES",
            "start_word_id": "w000000", "end_word_id": "w000007",
            "scene": "So sánh số đơn trước và sau", "action": "Hai tấm giấy mở ra để so sánh",
            "narration": "trước là một trăm sau còn sáu mươi", "duration_seconds": 10,
            "has_alpha": False, "style_snapshot": style, "style_snapshot_hash": style_hash,
            "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
                "title": "Đơn hàng", "docs": [
                    {"title": "Trước", "label": "Đơn", "value": "100"},
                    {"title": "Sau", "label": "Đơn", "value": "60"},
                ], "diff_label": "Giảm 40", "on": {"before": "trước", "after": "sau", "delta": "sáu mươi"},
            }},
        }])

        deferred = editor.dung_video_dai(
            db, source_asset_id=source.id, workspace_id=workspace_id, user_id=user_id,
            project_id=None, job_id=job_id,
        )

        parent_request = json.loads(deferred.request_payload_json)
        child_id = parent_request["parameters"]["flow_job_ids"][0]
        child = db.get(AIGenerationJob, child_id)
        child_request = json.loads(child.request_payload_json)
        assert child_request["operation"] == "render_auto_edit_diagram"
        assert child_request["backend_provider"] == "BAHA_AUTO_EDIT"
        assert child_request["parameters"]["style_snapshot_hash"] == style_hash
        assert child_request["parameters"]["target_start_word_id"] == "w000000"
        assert child_request["parameters"]["target_end_word_id"] == "w000007"
        assert parent_request["parameters"]["phase"] == "render"
        assert "HyperFrames" in deferred.status_message
        brief = json.loads((media_root / parent_request["parameters"]["plan_storage_key"]).read_text(encoding="utf-8"))["flow_briefs"][0]
        child.state = "SUCCEEDED"
        child.output_asset_ids_json = json.dumps(["diagram-output"])
        db.add(MediaAsset(
            id="diagram-output", workspace_id=workspace_id, storage_key=source.storage_key,
            sha256=source_hash, byte_size=source_size, mime_detected="video/mp4",
            source_product="AUTO_EDIT_HYPERFRAMES", created_by=user_id,
        ))
        db.commit()
        monkeypatch.setattr(editor, "_resolve_visual_asset", lambda *_args: source_path)
        candidates, failed = editor._visual_candidates_for_jobs(db, [child_id], [brief], workspace_id, None)
        assert failed == []
        assert candidates[0]["target_start_word_id"] == "w000000"
        assert candidates[0]["target_end_word_id"] == "w000007"

        generated_candidate = {**candidates[0], "has_alpha": True, "duration_seconds": 3,
                               "target_start_word_id": "w000000", "target_end_word_id": "w000007"}
        monkeypatch.setattr(editor, "_visual_candidates_for_jobs", lambda *_args: ([generated_candidate], []))
        monkeypatch.setattr(editor, "lay_ung_vien_dien_hoa", lambda *_args: [])
        received = []
        monkeypatch.setattr(editor, "chon_dien_hoa", lambda _clips, _words, assets, _client: received.extend(assets) or [])
        monkeypatch.setattr(editor.LLMClient, "from_db", classmethod(lambda _cls, _db: SimpleNamespace(model="real-model")))
        def fake_render(**kwargs):
            Path(kwargs["output_path"]).write_bytes(b"mp4")
            return {"duration_seconds": 12}

        monkeypatch.setattr(editor.video_processor, "render_timeline_document", fake_render)
        monkeypatch.setattr(editor.video_processor, "probe_video", lambda *_args: {"duration_seconds": 12, "width": 1080, "height": 1920, "frame_rate": 30})
        monkeypatch.setattr(editor, "_kiem_tra_khung_den", lambda *_args: [])
        from src.modules.tao_video_noi_dung import runner
        monkeypatch.setattr(runner, "_add_brand_end_card", lambda *_args: 3)
        editor.dung_video_dai(
            db, source_asset_id=source.id, workspace_id=workspace_id, user_id=user_id,
            project_id=None, job_id=job_id, phase="render", flow_job_ids=[child_id],
            plan_storage_key=parent_request["parameters"]["plan_storage_key"],
        )
        assert received == [generated_candidate]
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()




def test_y_tuong_dien_hoa_requires_explicit_renderer():
    schema = YTuongDienHoaFlow.model_json_schema()
    assert "renderer" in schema["required"]


def test_planner_retries_after_three_unavailable_renderer_choices():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12_000, title="Don hang", reason="So sanh")
    flow = {"visuals": [{"clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w1",
             "scene": "Mo hinh giay cua hang", "action": "Chong don origami giam dan", "renderer": "FLOW"}]}
    diagram = {"visuals": [{"clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w7",
                "scene": "So sanh so don", "action": "Hai tam giay lan luot mo ra", "renderer": "HYPERFRAMES",
                "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
                    "title": "Don hang", "simulated": False,
                    "docs": [{"title": "Truoc", "label": "Don", "value": "100"},
                             {"title": "Sau", "label": "Don", "value": "60"}],
                    "diff_label": "Giam 40",
                    "on": {"before": "truoc 100", "after": "sau con 60", "delta": "giam 40"},
                }} }]}
    client = LLMGia([flow, flow, flow, diagram])

    visuals = tao_y_tuong_dien_hoa_flow(
        [clip], [tu(1, "truoc", 1_000, 1_500), tu(2, "100", 1_500, 2_000),
                 tu(3, "sau", 2_500, 3_000), tu(4, "con", 3_000, 3_500),
                 tu(5, "60", 3_500, 4_000), tu(6, "giam", 5_000, 5_500),
                 tu(7, "40", 5_500, 6_000)], [], client, False,
    )

    assert len(visuals) == 1 and visuals[0]["renderer"] == "HYPERFRAMES"
    assert len(client.messages) == 4

def test_planner_reconsiders_empty_plan_after_flow_is_unavailable():
    clip = ClipTuDong(clip_id="part1_01", start_ms=0, end_ms=12_000, title="Don hang", reason="So sanh")
    flow = {"visuals": [{"clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w1",
             "scene": "Mo hinh giay cua hang", "action": "Chong don origami giam dan", "renderer": "FLOW"}]}
    empty = {"visuals": []}
    diagram = {"visuals": [{"clip_id": clip.clip_id, "start_word_id": "w1", "end_word_id": "w7",
                "scene": "So sanh so don", "action": "Hai tam giay lan luot mo ra", "renderer": "HYPERFRAMES",
                "ui_scene": {"layout": "BEFORE_AFTER", "diagram": {
                    "title": "Don hang", "simulated": False,
                    "docs": [{"title": "Truoc", "label": "Don", "value": "100"},
                             {"title": "Sau", "label": "Don", "value": "60"}],
                    "diff_label": "Giam 40",
                    "on": {"before": "truoc 100", "after": "sau con 60", "delta": "giam 40"},
                }} }]}
    client = LLMGia([flow, empty, diagram])

    visuals = tao_y_tuong_dien_hoa_flow(
        [clip], [tu(1, "truoc", 1_000, 1_500), tu(2, "100", 1_500, 2_000),
                 tu(3, "sau", 2_500, 3_000), tu(4, "con", 3_000, 3_500),
                 tu(5, "60", 3_500, 4_000), tu(6, "giam", 5_000, 5_500),
                 tu(7, "40", 5_500, 6_000)], [], client, False,
    )

    assert len(visuals) == 1 and visuals[0]["renderer"] == "HYPERFRAMES"
    assert len(client.messages) == 3
