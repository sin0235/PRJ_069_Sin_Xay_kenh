import pytest
from src.modules.dieu_phoi_dung.hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    CaptionV2,
    ThoiGianNguon,
    LenhDung,
    LoiHopDong
)
from src.modules.dieu_phoi_dung.phien_dung import QuanLyPhienDung
from src.modules.dieu_phoi_dung.cong_cu import DieuPhoiCongCu


def tao_sample_timeline_t06() -> TimelineV2:
    clip1 = ClipV2(
        clip_id="c1",
        asset_id="asset_v1",
        start_frame=0,
        duration_frames=90,  # 3s
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
    )
    clip2 = ClipV2(
        clip_id="c2",
        asset_id="asset_v2",
        start_frame=90,
        duration_frames=90,  # 3s
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
    )
    track_v = TrackV2(
        track_id="trk_v1",
        track_type="video",
        layer_index=0,
        name="Video 1",
        clips=[clip1, clip2]
    )
    cap = CaptionV2(
        caption_id="cap_01",
        start_ms=1000,
        end_ms=4000,
        text="Noi dung phu de mau"
    )
    return TimelineV2(
        schema_version=2,
        tracks=[track_v],
        captions=[cap]
    )


def test_split_trim_insert_overwrite_ripple_slip():
    """
    Kiem tra 6 thao tac cat gop thoi gian co ban: split, trim, insert, overwrite, ripple_delete, slip
    """
    timeline = tao_sample_timeline_t06()
    phien = QuanLyPhienDung.tao_phien("prj_t06_1", "ws_01", "editor_01", 1, "hash_t06_1")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, timeline)

    # 1. Split clip c1 tai frame 45
    cmd_split = LenhDung(
        operation_id="op_split",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="split_clip",
        payload={"track_id": "trk_v1", "clip_id": "c1", "split_frame": 45}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_split])
    assert res.status == "SUCCESS"
    assert res.revision_after == 2

    draft_after = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    assert len(draft_after.timeline.tracks[0].clips) == 3
    assert draft_after.timeline.tracks[0].clips[0].duration_frames == 45
    assert draft_after.timeline.tracks[0].clips[1].duration_frames == 45

    # 2. Trim clip c1 phan 1 tu 0-1000ms (30 frames)
    cmd_trim = LenhDung(
        operation_id="op_trim",
        draft_id=draft.draft_id,
        expected_draft_revision=2,
        type="trim_clip",
        payload={"track_id": "trk_v1", "clip_id": "c1", "trim_in_ms": 0, "trim_out_ms": 1000}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 2, [cmd_trim])
    assert res.revision_after == 3
    assert draft_after.timeline.tracks[0].clips[0].duration_frames == 30

    # 3. Slip clip c1_part2 sang phai 500ms
    cmd_slip = LenhDung(
        operation_id="op_slip",
        draft_id=draft.draft_id,
        expected_draft_revision=3,
        type="slip_clip",
        payload={"track_id": "trk_v1", "clip_id": "c1_part2", "slip_delta_ms": 500, "max_source_duration_ms": 10000}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 3, [cmd_slip])
    assert res.revision_after == 4
    assert draft_after.timeline.tracks[0].clips[1].source_in.ticks == 2000  # 1500 + 500

    # 4. Overwrite tai frame 120 voi clip moi duration 30 frames
    cmd_ow = LenhDung(
        operation_id="op_ow",
        draft_id=draft.draft_id,
        expected_draft_revision=4,
        type="overwrite_clip",
        payload={"track_id": "trk_v1", "asset_id": "asset_broll", "at_frame": 120, "duration_frames": 30}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 4, [cmd_ow])
    assert res.revision_after == 5

    # 5. Ripple delete clip dau tien
    cmd_ripple = LenhDung(
        operation_id="op_rip",
        draft_id=draft.draft_id,
        expected_draft_revision=5,
        type="ripple_delete",
        payload={"track_id": "trk_v1", "clip_id": "c1"}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 5, [cmd_ripple])
    assert res.revision_after == 6
    # Clip ke tiep phai duoc keo ve frame 0
    assert draft_after.timeline.tracks[0].clips[0].start_frame == 15  # 45 - 30


def test_ba_lop_video_bon_lop_audio():
    """
    Kiem tra ho tro toi thieu 3 video layers va 4 audio layers (Fixture F03)
    """
    timeline = TimelineV2(schema_version=2)
    phien = QuanLyPhienDung.tao_phien("prj_t06_multi", "ws_01", "editor_01", 1, "hash_multi")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, timeline)

    commands = [
        # 3 Video tracks
        LenhDung(operation_id="op_v1", draft_id=draft.draft_id, expected_draft_revision=1, type="add_track", payload={"track_id": "V1", "track_type": "video", "layer_index": 0, "name": "Main Footage"}),
        LenhDung(operation_id="op_v2", draft_id=draft.draft_id, expected_draft_revision=1, type="add_track", payload={"track_id": "V2", "track_type": "video", "layer_index": 1, "name": "B-roll Overlays"}),
        LenhDung(operation_id="op_v3", draft_id=draft.draft_id, expected_draft_revision=1, type="add_track", payload={"track_id": "V3", "track_type": "video", "layer_index": 2, "name": "Logo & Graphics"}),
        # 4 Audio tracks
        LenhDung(operation_id="op_a1", draft_id=draft.draft_id, expected_draft_revision=1, type="add_track", payload={"track_id": "A1", "track_type": "audio", "layer_index": 0, "name": "Voiceover Dialogue"}),
        LenhDung(operation_id="op_a2", draft_id=draft.draft_id, expected_draft_revision=1, type="add_track", payload={"track_id": "A2", "track_type": "audio", "layer_index": 1, "name": "Background Music"}),
        LenhDung(operation_id="op_a3", draft_id=draft.draft_id, expected_draft_revision=1, type="add_track", payload={"track_id": "A3", "track_type": "audio", "layer_index": 2, "name": "Sound Effects 1"}),
        LenhDung(operation_id="op_a4", draft_id=draft.draft_id, expected_draft_revision=1, type="add_track", payload={"track_id": "A4", "track_type": "audio", "layer_index": 3, "name": "Ambient Sound"}),
    ]

    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, commands)
    assert res.status == "SUCCESS"
    assert res.revision_after == 2

    draft_after = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    v_tracks = [t for t in draft_after.timeline.tracks if t.track_type == "video"]
    a_tracks = [t for t in draft_after.timeline.tracks if t.track_type == "audio"]
    assert len(v_tracks) == 3
    assert len(a_tracks) == 4


def test_lock_va_transition_handle():
    """
    Kiem tra:
    1. Track bi khoa (is_locked=True) se chan moi thao tac (OCC_CONFLICT_409)
    2. Transition thieu handle bi tu choi (OOB_RANGE)
    """
    timeline = tao_sample_timeline_t06()
    phien = QuanLyPhienDung.tao_phien("prj_t06_lock", "ws_01", "editor_01", 1, "hash_lock")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, timeline)

    # 1. Transition thieu handle: can 30 frames nhung chi co 10 frames
    cmd_trans_fail = LenhDung(
        operation_id="op_trans_fail",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="add_transition",
        payload={
            "track_id": "trk_v1",
            "clip_id": "c1",
            "handle_frames": 30,
            "available_handle_frames": 10  # thieu
        }
    )
    with pytest.raises(ValueError) as exc:
        DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_trans_fail])
    assert "Transition thieu handle" in str(exc.value)

    # 2. Khoa track V1 va thu thao tac
    draft.timeline.tracks[0].is_locked = True
    cmd_on_locked = LenhDung(
        operation_id="op_lock_fail",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="split_clip",
        payload={"track_id": "trk_v1", "clip_id": "c1", "split_frame": 45}
    )
    with pytest.raises(ValueError) as exc:
        DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_on_locked])
    assert LoiHopDong.OCC_CONFLICT_409 in str(exc.value)
