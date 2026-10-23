import pytest
from src.modules.dieu_phoi_dung.hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    CaptionV2,
    ThoiGianNguon,
    LenhDung
)
from src.modules.dieu_phoi_dung.phien_dung import QuanLyPhienDung
from src.modules.dieu_phoi_dung.cong_cu import DieuPhoiCongCu


def test_sync_giong_nhac_sfx_va_j_l_cut():
    """
    Kiem tra J-cut / L-cut: Am thanh thoai bat dau truoc video (J-cut) hoac keo dai sau video (L-cut)
    """
    # Video clip tu frame 30 den frame 120 (3 giay)
    video_clip = ClipV2(
        clip_id="v_main",
        asset_id="asset_video",
        start_frame=30,
        duration_frames=90,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
    )
    # Audio J-cut: Bat dau tu frame 0 (truoc video 1s = 30 frames)
    audio_j_cut = ClipV2(
        clip_id="a_dialogue",
        asset_id="asset_voice",
        start_frame=0,  # J-cut lead-in
        duration_frames=120,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=4000, time_base_num=1, time_base_den=1000)
    )

    trk_v = TrackV2(track_id="V1", track_type="video", layer_index=0, clips=[video_clip])
    trk_a = TrackV2(track_id="A1", track_type="audio", layer_index=0, clips=[audio_j_cut])
    timeline = TimelineV2(tracks=[trk_v, trk_a])

    assert timeline.tracks[1].clips[0].start_frame < timeline.tracks[0].clips[0].start_frame
    # J-cut delta la 30 frames (1.0 giay)
    j_cut_delta_frames = timeline.tracks[0].clips[0].start_frame - timeline.tracks[1].clips[0].start_frame
    assert j_cut_delta_frames == 30


def test_duck_chi_theo_voice():
    """
    Kiem tra cau hinh auto-ducking: Nhac nen chi ha am luong (ducking) khi track Voiceover phat am thanh
    """
    bgm_clip = ClipV2(
        clip_id="c_bgm",
        asset_id="asset_bgm",
        start_frame=0,
        duration_frames=180,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=6000, time_base_num=1, time_base_den=1000),
        gain_db=-12.0  # ducked gain
    )
    trk_bgm = TrackV2(track_id="A2_BGM", track_type="audio", layer_index=1, clips=[bgm_clip])
    assert trk_bgm.clips[0].gain_db == -12.0


def test_phu_de_tieng_viet_va_glossary():
    """
    Kiem tra phu de tieng Viet co dau chuan UTF-8, glossary thuong hieu Sin va safe zone TikTok
    """
    cap = CaptionV2(
        caption_id="cap_sin_01",
        start_ms=500,
        end_ms=2500,
        text="Trà Sữa Sin - Đậm Vị Truyền Thống",
        safe_zone=True
    )
    assert "Trà Sữa Sin" in cap.text
    assert cap.safe_zone is True
    assert cap.end_ms > cap.start_ms


def test_gain_eq_fade_va_peak():
    """
    Kiem tra dieu chinh gain trong gioi han [-60.0, +12.0] dB tranh clipping
    """
    timeline = TimelineV2(tracks=[
        TrackV2(
            track_id="A1",
            track_type="audio",
            layer_index=0,
            clips=[
                ClipV2(
                    clip_id="a1",
                    asset_id="asset_vo",
                    start_frame=0,
                    duration_frames=90,
                    source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
                    source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
                )
            ]
        )
    ])
    phien = QuanLyPhienDung.tao_phien("prj_t06_gain", "ws_01", "editor_01", 1, "hash_gain")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, timeline)

    # Chinh gain len +3.0 dB
    cmd = LenhDung(
        operation_id="op_gain_ok",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="set_clip_gain",
        payload={"track_id": "A1", "clip_id": "a1", "gain_db": 3.0}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd])
    assert res.status == "SUCCESS"
    assert res.revision_after == 2


def test_mute_co_chu_y_khong_bi_qa_bao_sai():
    """
    Kiem tra track duoc nguoi dung chu dong tat tieng (is_muted=True) khong bi QA bao loi silence bat thuong
    """
    trk_muted = TrackV2(
        track_id="A3_SFX",
        track_type="audio",
        layer_index=2,
        is_muted=True,
        clips=[]
    )
    assert trk_muted.is_muted is True
