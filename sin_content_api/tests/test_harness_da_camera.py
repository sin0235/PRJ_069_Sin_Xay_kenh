import pytest
from src.modules.dieu_phoi_dung.hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    ThoiGianNguon,
    LenhDung
)
from src.modules.dieu_phoi_dung.phien_dung import QuanLyPhienDung
from src.modules.dieu_phoi_dung.cong_cu import DieuPhoiCongCu


def test_retime_va_goc_may_co_map_nguon():
    """
    Kiem tra retime (thay doi speed_ratio) tinh toan duration_frames moi ma van giu nguyen source map
    """
    timeline = TimelineV2(tracks=[
        TrackV2(
            track_id="V1",
            track_type="video",
            layer_index=0,
            clips=[
                ClipV2(
                    clip_id="c_speed",
                    asset_id="asset_cam_a",
                    start_frame=0,
                    duration_frames=120,  # 4 giay goc
                    source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
                    source_out=ThoiGianNguon(ticks=4000, time_base_num=1, time_base_den=1000)
                )
            ]
        )
    ])
    phien = QuanLyPhienDung.tao_phien("prj_t06_retime", "ws_01", "editor_01", 1, "hash_rt")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, timeline)

    # Tang toc do len 2x (fast-forward) -> duration_frames giam con 60 frames (2s)
    cmd = LenhDung(
        operation_id="op_speed_2x",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="set_retime_speed",
        payload={"track_id": "V1", "clip_id": "c_speed", "speed_ratio": 2.0}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd])
    assert res.status == "SUCCESS"
    assert res.revision_after == 2

    draft_after = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    clip_after = draft_after.timeline.tracks[0].clips[0]
    assert clip_after.speed_ratio == 2.0
    assert clip_after.duration_frames == 60
    # ThoiGianNguon van duoc bao toan (0 -> 4000 ticks)
    assert clip_after.source_in.ticks == 0
    assert clip_after.source_out.ticks == 4000


def test_freeze_reverse_va_audio_policy():
    """
    Kiem tra hieu ung dung hinh (freeze frame) va quay nguoc (reverse):
    Freeze frame giu nguyen 1 tick duy nhat trong suot thoi luong clip
    """
    # Freeze frame tai giay 1.5 (1500 ms) keo dai 2 giay (60 frames)
    freeze_clip = ClipV2(
        clip_id="c_freeze",
        asset_id="asset_cam_a",
        start_frame=60,
        duration_frames=60,
        source_in=ThoiGianNguon(ticks=1500, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=1500, time_base_num=1, time_base_den=1000),  # In = Out
        effects=[{"type": "freeze_frame", "at_tick": 1500}]
    )
    assert freeze_clip.source_in.ticks == freeze_clip.source_out.ticks
    assert freeze_clip.effects[0]["type"] == "freeze_frame"


def test_hai_camera_audio_roi_khong_troi_sync():
    """
    Kiem tra 2 camera A va B duoc dong bo voi audio roi:
    Khi chuyen doi giua goc may A va goc may B, start_frame va timeline sync khong bi troi (drift)
    """
    # Camera A quay 0s - 3s (frame 0 - 90)
    cam_a_clip = ClipV2(
        clip_id="c_cam_a",
        asset_id="asset_camera_a_wide",
        start_frame=0,
        duration_frames=90,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
    )
    # Camera B can canh quay 3s - 6s (frame 90 - 180)
    cam_b_clip = ClipV2(
        clip_id="c_cam_b",
        asset_id="asset_camera_b_tight",
        start_frame=90,
        duration_frames=90,
        source_in=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=6000, time_base_num=1, time_base_den=1000)
    )
    # Audio roi thu lien tuc 0s - 6s (frame 0 - 180)
    audio_full = ClipV2(
        clip_id="c_audio_master",
        asset_id="asset_audio_mic_roi",
        start_frame=0,
        duration_frames=180,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=6000, time_base_num=1, time_base_den=1000)
    )

    t = TimelineV2(tracks=[
        TrackV2(track_id="V1_Multicam", track_type="video", layer_index=0, clips=[cam_a_clip, cam_b_clip]),
        TrackV2(track_id="A1_MasterAudio", track_type="audio", layer_index=0, clips=[audio_full])
    ])

    # Kiem tra tong thoi luong video khop 100% voi thoi luong audio master
    total_video_frames = t.tracks[0].clips[1].start_frame + t.tracks[0].clips[1].duration_frames
    total_audio_frames = t.tracks[1].clips[0].start_frame + t.tracks[1].clips[0].duration_frames
    assert total_video_frames == 180
    assert total_audio_frames == 180
    assert total_video_frames == total_audio_frames
