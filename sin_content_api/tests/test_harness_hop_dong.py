import pytest
import math
from pydantic import ValidationError

from src.modules.dieu_phoi_dung.hop_dong import (
    ThoiGianNguon,
    BangChungNguon,
    ChinhSachPhien,
    DinhDanhPhien,
    LenhDung,
    ClipV2,
    TrackV2,
    CaptionV2,
    TimelineV2,
    KeHoachDung,
    kiem_tra_ke_hoach,
    LoiHopDong
)
from src.modules.dieu_phoi_dung.thoi_gian import chuyen_timeline_v1, map_vfr_pts


def test_truong_la_va_thoi_gian_sai_bi_tu_choi():
    """
    Kiem tra truong la (extra field) va thoi gian sai (NaN, float, am, bool-int) bi tu choi boi Pydantic extra='forbid'
    """
    # 1. Truong la bi tu choi
    with pytest.raises(ValidationError):
        ThoiGianNguon(ticks=100, time_base_num=1, time_base_den=1000, unknown_field="invalid")

    # 2. Bool thay vi int bi tu choi
    with pytest.raises(ValidationError):
        ThoiGianNguon(ticks=True, time_base_num=1, time_base_den=1000)

    # 3. Mau so am hoac bang 0 bi tu choi
    with pytest.raises(ValidationError):
        ThoiGianNguon(ticks=100, time_base_num=1, time_base_den=0)

    # 4. NaN bi tu choi trong ClipV2
    with pytest.raises(ValidationError):
        ClipV2(
            clip_id="c1",
            asset_id="a1",
            start_frame=0,
            duration_frames=30,
            source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
            source_out=ThoiGianNguon(ticks=1000, time_base_num=1, time_base_den=1000),
            gain_db=float("nan")
        )

    # 5. Out of bound gain bi tu choi
    with pytest.raises(ValidationError):
        ClipV2(
            clip_id="c1",
            asset_id="a1",
            start_frame=0,
            duration_frames=30,
            source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
            source_out=ThoiGianNguon(ticks=1000, time_base_num=1, time_base_den=1000),
            gain_db=25.0  # limit is 12.0 dB
        )


def test_nguon_ngoai_pham_vi_bi_tu_choi():
    """
    Kiem tra cac gia tri ngoai pham vi (out of bound) bi tu choi
    """
    # Caption end_ms <= start_ms bi tu choi
    with pytest.raises(ValidationError):
        CaptionV2(
            caption_id="cap1",
            start_ms=2000,
            end_ms=1000,
            text="Invalid range"
        )

    # ChinhSachPhien max_cost_usd am bi tu choi
    with pytest.raises(ValidationError):
        ChinhSachPhien(max_cost_usd=-5.0)


def test_v1_v2_giu_nguyen_version_cu():
    """
    Kiem tra chuyen doi TimelineDocument v1 sang TimelineV2 giu nguyen tinh toan va khong sua v1
    """
    v1_doc = {
        "clips": [
            {
                "clip_id": "clip_01",
                "asset_id": "asset_video_01",
                "duration_ms": 4000,
                "trim_in_ms": 1000,
                "trim_out_ms": 4000,
                "fit_mode": "cover"
            },
            {
                "clip_id": "clip_02",
                "asset_id": "asset_video_02",
                "duration_ms": 2000,
                "trim_in_ms": 0,
                "trim_out_ms": 2000,
                "fit_mode": "contain"
            }
        ],
        "audio_tracks": [
            {
                "track_id": "bgm_track",
                "asset_id": "asset_music_01",
                "volume": 0.8
            }
        ],
        "captions": [
            {
                "caption_id": "cap_01",
                "start_ms": 500,
                "end_ms": 3000,
                "text": "Tra sua Sin dam vi truyen thong",
                "safe_zone": True
            }
        ]
    }

    v2_timeline = chuyen_timeline_v1(v1_doc, fps_num=30, fps_den=1)
    
    assert v2_timeline.schema_version == 2
    assert len(v2_timeline.tracks) == 2  # 1 video track + 1 audio track
    assert len(v2_timeline.tracks[0].clips) == 2
    assert v2_timeline.tracks[0].clips[0].source_in.ticks == 1000
    assert v2_timeline.tracks[0].clips[0].source_out.ticks == 4000
    assert v2_timeline.tracks[0].clips[0].duration_frames == 90  # 3s * 30fps
    assert len(v2_timeline.captions) == 1
    assert v2_timeline.captions[0].text == "Tra sua Sin dam vi truyen thong"

    # Kiem tra FPS 24000/1001 (23.976 fps) va 30000/1001 (29.97 fps)
    v2_24fps = chuyen_timeline_v1(v1_doc, fps_num=24000, fps_den=1001)
    assert v2_24fps.fps_num == 24000
    assert v2_24fps.fps_den == 1001
    assert v2_24fps.tracks[0].clips[0].duration_frames == 72  # round(3.0 * 23.976) = 72


def test_vfr_dung_pts_khong_dung_fps_trung_binh():
    """
    Kiem tra VFR su dung PTS tuyet doi sang frame index tren timeline CFR, khong chia avg FPS
    """
    # PTS mau tu video VFR (timebase 1/90000)
    # Day la video co toc do bien thien (khoang cach PTS giua cac frame thay doi)
    time_base_num = 1
    time_base_den = 90000
    # Frame o giay 0, 0.04s, 0.085s, 0.12s, 1.0s, 2.0s
    pts_list = [0, 3600, 7650, 10800, 90000, 180000]

    # Dich la CFR 30 fps (33.33ms moi frame)
    frame_indices = map_vfr_pts(pts_list, time_base_num, time_base_den, target_fps_num=30, target_fps_den=1)

    assert frame_indices[0] == 0  # 0.0s -> frame 0
    assert frame_indices[1] == 1  # 0.04s -> frame 1 (0.04 * 30 = 1.2 -> 1)
    assert frame_indices[2] == 3  # 0.085s -> frame 3 (0.085 * 30 = 2.55 -> 3)
    assert frame_indices[3] == 4  # 0.12s -> frame 4 (0.12 * 30 = 3.6 -> 4)
    assert frame_indices[4] == 30 # 1.0s -> frame 30
    assert frame_indices[5] == 60 # 2.0s -> frame 60


def test_effect_khong_ho_tro_khong_bi_bo_qua():
    """
    Kiem tra validation ke hoach bat dung LoiHopDong khi thieu evidence hoac effect khong ho tro
    """
    policy = ChinhSachPhien(max_cost_usd=5.0)
    snapshot = TimelineV2()
    evidence_list = [
        BangChungNguon(
            evidence_id="ev_01",
            asset_id="asset_01",
            source_sha256="abc123hash",
            analysis_version="1.0",
            modality="speech"
        )
    ]

    # 1. Ke hoach vuot ngan sach
    plan_overbudget = KeHoachDung(
        plan_id="p1",
        brief_id="b1",
        base_revision=1,
        estimated_cost_usd=12.5  # vuot 5.0
    )
    errors = kiem_tra_ke_hoach(plan_overbudget, snapshot, evidence_list, policy)
    assert any(LoiHopDong.BUDGET_OVERRUN in err for err in errors)

    # 2. Ke hoach dung evidence_id khong ton tai
    cmd_invalid_ev = LenhDung(
        operation_id="op_1",
        draft_id="d1",
        expected_draft_revision=1,
        type="split_clip",
        evidence_ids=["ev_non_existent"]
    )
    plan_missing_ev = KeHoachDung(
        plan_id="p2",
        brief_id="b1",
        base_revision=1,
        proposed_commands=[cmd_invalid_ev],
        estimated_cost_usd=1.0
    )
    errors_ev = kiem_tra_ke_hoach(plan_missing_ev, snapshot, evidence_list, policy)
    assert any(LoiHopDong.MISSING_EVIDENCE in err for err in errors_ev)

    # 3. Effect apply_color_lut thieu lut_asset_id
    cmd_lut = LenhDung(
        operation_id="op_2",
        draft_id="d1",
        expected_draft_revision=1,
        type="apply_color_lut",
        payload={"track_id": "v1", "clip_id": "c1"}  # thieu lut_asset_id
    )
    plan_lut = KeHoachDung(
        plan_id="p3",
        brief_id="b1",
        base_revision=1,
        proposed_commands=[cmd_lut],
        estimated_cost_usd=0.5
    )
    errors_lut = kiem_tra_ke_hoach(plan_lut, snapshot, evidence_list, policy)
    assert any(LoiHopDong.UNSUPPORTED_EFFECT in err for err in errors_lut)
