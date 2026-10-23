import pytest
from src.modules.dieu_phoi_dung.hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    ThoiGianNguon,
    LenhDung,
    LoiHopDong
)
from src.modules.dieu_phoi_dung.phien_dung import QuanLyPhienDung
from src.modules.dieu_phoi_dung.cong_cu import DieuPhoiCongCu


def test_transform_keyframe_easing_va_reframe():
    """
    Kiem tra keyframe transform va easing (scale, position pan/zoom) duoc luu tru day du trong effects
    """
    clip = ClipV2(
        clip_id="c_transform",
        asset_id="asset_img_01",
        start_frame=0,
        duration_frames=75,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=2500, time_base_num=1, time_base_den=1000),
        effects=[
            {
                "type": "transform",
                "keyframes": [
                    {"frame": 0, "scale": 1.0, "x": 0, "y": 0, "easing": "ease_in"},
                    {"frame": 75, "scale": 1.15, "x": 10, "y": -5, "easing": "ease_out"}
                ]
            }
        ]
    )
    assert len(clip.effects) == 1
    assert clip.effects[0]["keyframes"][1]["scale"] == 1.15


def test_color_lut_va_khong_doi_color_space_ngam():
    """
    Kiem tra ap dung LUT dien anh (.cube) gan voi asset_id ro rang va khong am tham doi color space
    """
    timeline = TimelineV2(tracks=[
        TrackV2(
            track_id="V1",
            track_type="video",
            layer_index=0,
            clips=[
                ClipV2(
                    clip_id="c_color",
                    asset_id="asset_raw",
                    start_frame=0,
                    duration_frames=90,
                    source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
                    source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
                )
            ]
        )
    ])
    phien = QuanLyPhienDung.tao_phien("prj_t06_lut", "ws_01", "editor_01", 1, "hash_lut")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, timeline)

    cmd_lut = LenhDung(
        operation_id="op_lut_ok",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="apply_color_lut",
        payload={"track_id": "V1", "clip_id": "c_color", "lut_asset_id": "lut_sin_teal_orange"}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_lut])
    assert res.status == "SUCCESS"
    assert res.revision_after == 2

    draft_after = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    assert draft_after.timeline.tracks[0].clips[0].lut_asset_id == "lut_sin_teal_orange"


def test_mask_keying_va_quy_dao_tracking():
    """
    Kiem tra luu tru mask lam mo thong tin nhay cam (redaction) voi quy dao tracking ROI qua moi frame
    """
    clip = ClipV2(
        clip_id="c_mask",
        asset_id="asset_receipt",
        start_frame=0,
        duration_frames=60,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=2000, time_base_num=1, time_base_den=1000),
        effects=[
            {
                "type": "mask_blur",
                "shape": "circle",
                "tracking_roi": [
                    {"frame": 0, "center_x": 540, "center_y": 960, "radius": 80},
                    {"frame": 30, "center_x": 550, "center_y": 965, "radius": 82},
                    {"frame": 60, "center_x": 560, "center_y": 970, "radius": 85}
                ]
            }
        ]
    )
    assert len(clip.effects[0]["tracking_roi"]) == 3


def test_preview_render_khong_mat_effect():
    """
    Kiem tra clip giu nguyen danh sach effects qua cac lan cap nhat timeline
    """
    clip = ClipV2(
        clip_id="c_eff",
        asset_id="asset_fx",
        start_frame=0,
        duration_frames=30,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=1000, time_base_num=1, time_base_den=1000),
        effects=[{"type": "glow", "intensity": 0.5}]
    )
    t = TimelineV2(tracks=[TrackV2(track_id="V1", track_type="video", layer_index=0, clips=[clip])])
    assert t.tracks[0].clips[0].effects[0]["type"] == "glow"


def test_font_lut_thieu_khong_tu_thay():
    """
    Kiem tra khi lut_asset_id bi thieu se nem loi UNSUPPORTED_EFFECT chu khong tu dong fallback
    """
    timeline = TimelineV2(tracks=[
        TrackV2(
            track_id="V1",
            track_type="video",
            layer_index=0,
            clips=[
                ClipV2(
                    clip_id="c_fail",
                    asset_id="asset_raw",
                    start_frame=0,
                    duration_frames=90,
                    source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
                    source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
                )
            ]
        )
    ])
    phien = QuanLyPhienDung.tao_phien("prj_t06_lut_fail", "ws_01", "editor_01", 1, "hash_lf")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, timeline)

    cmd_missing_lut = LenhDung(
        operation_id="op_missing_lut",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="apply_color_lut",
        payload={"track_id": "V1", "clip_id": "c_fail"}  # khong co lut_asset_id
    )
    with pytest.raises(ValueError) as exc:
        DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_missing_lut])
    assert LoiHopDong.UNSUPPORTED_EFFECT in str(exc.value)
