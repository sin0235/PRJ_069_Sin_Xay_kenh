import pytest
from src.modules.dieu_phoi_dung.hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    CaptionV2,
    ThoiGianNguon,
    LoiHopDong
)
from src.modules.dieu_phoi_dung.ket_noi_phan_mem_dung import BoKetNoiPhanMemDung


def tao_sample_timeline_nle() -> TimelineV2:
    clip = ClipV2(
        clip_id="c_nle_1",
        asset_id="asset_source_video_01",
        start_frame=0,
        duration_frames=90,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
    )
    cap = CaptionV2(
        caption_id="cap_01",
        start_ms=0,
        end_ms=2500,
        text="Phu de ban dau"
    )
    return TimelineV2(
        tracks=[TrackV2(track_id="V1", track_type="video", layer_index=0, clips=[clip])],
        captions=[cap]
    )


def test_mo_lai_relink_giu_nguon():
    """
    Kiem tra xuat goi ban giao tao day du files manifest va timeline.xml giu nguyen nguon
    """
    timeline = tao_sample_timeline_nle()
    bundle = BoKetNoiPhanMemDung.xuat_goi_ban_giao(
        project_id="prj_sin_nle",
        revision=1,
        timeline=timeline,
        adapter_id="FINAL_CUT_XML"
    )

    assert bundle.bundle_id == "bnd_prj_sin_nle_rev1"
    assert bundle.export_format == "FINAL_CUT_XML"
    assert len(bundle.files) == 3
    assert any("timeline.xml" in f for f in bundle.files)
    assert any("manifest.json" in f for f in bundle.files)


def test_loss_report_khong_bo_mat_effect():
    """
    Kiem tra bao cao ton that hieu ung (loss report) phan loai ro rang SUPPORTED va HUMAN_REQUIRED
    """
    timeline = tao_sample_timeline_nle()
    bundle = BoKetNoiPhanMemDung.xuat_goi_ban_giao("prj_sin_nle", 1, timeline)

    lr = bundle.loss_report
    assert "cuts" in lr["SUPPORTED"]
    assert "advanced_color_grading" in lr["HUMAN_REQUIRED"]
    assert "rotoscoping" in lr["HUMAN_REQUIRED"]


def test_sua_tiep_native_khong_mat_finishing():
    """
    Kiem tra khi project o che do NATIVE_BOUND (da duoc editor grade mau tren NLE):
    Agent sua caption tiep tuc ma van giu nguyen native_hash va finishing
    """
    timeline = tao_sample_timeline_nle()
    bundle = BoKetNoiPhanMemDung.xuat_goi_ban_giao("prj_sin_nle", 1, timeline)

    # Editor grade mau va nhap lai vao he thong
    native_timeline = BoKetNoiPhanMemDung.nhap_phien_ban_native(
        bundle_id=bundle.bundle_id,
        timeline_base=timeline,
        native_project_asset_id="asset_resolve_drp_project",
        native_hash="sha256_graded_by_editor_999"
    )
    assert native_timeline.representation_mode == "NATIVE_BOUND"
    assert native_timeline.native_hash == "sha256_graded_by_editor_999"

    # Agent sua tiep caption tren ban native
    updated = BoKetNoiPhanMemDung.sua_tiep_tren_native(
        timeline=native_timeline,
        op_type="set_caption_text",
        payload={"caption_id": "cap_01", "text": "Phu de duoc sua boi Agent"}
    )
    assert updated.captions[0].text == "Phu de duoc sua boi Agent"
    # Finishing van duoc bao toan 100%
    assert updated.native_hash == "sha256_graded_by_editor_999"
    assert updated.representation_mode == "NATIVE_BOUND"


def test_native_hash_sai_khong_duoc_render():
    """
    Kiem tra neu ma bam native file khong khop voi snapshot -> Chan render ngay lap tuc
    """
    timeline = tao_sample_timeline_nle()
    bundle = BoKetNoiPhanMemDung.xuat_goi_ban_giao("prj_sin_nle", 1, timeline)
    native_timeline = BoKetNoiPhanMemDung.nhap_phien_ban_native(
        bundle_id=bundle.bundle_id,
        timeline_base=timeline,
        native_project_asset_id="asset_drp",
        native_hash="sha256_expected_hash"
    )

    # File tren disk bi sua trộm hoac khong khop
    with pytest.raises(ValueError) as exc:
        BoKetNoiPhanMemDung.kiem_tra_render_native_bound(
            native_timeline,
            actual_native_file_hash="sha256_tampered_or_stale"
        )
    assert "Xung dot ma bam file native" in str(exc.value)


def test_bake_can_duyet_va_giu_nhanh_goc():
    """
    Kiem tra chuyen tu NATIVE_BOUND ve CANONICAL (bake/fork) bat buoc co approval_id va luu link nhanh goc
    """
    timeline = tao_sample_timeline_nle()
    bundle = BoKetNoiPhanMemDung.xuat_goi_ban_giao("prj_sin_nle", 1, timeline)
    native_timeline = BoKetNoiPhanMemDung.nhap_phien_ban_native(
        bundle_id=bundle.bundle_id,
        timeline_base=timeline,
        native_project_asset_id="asset_drp_original",
        native_hash="sha256_hash_root"
    )

    # Thieu approval_id bi tu choi
    with pytest.raises(ValueError) as exc:
        BoKetNoiPhanMemDung.bake_sang_canonical(native_timeline, approval_id="")
    assert "approval_id" in str(exc.value)

    # Co approval_id hop le
    forked = BoKetNoiPhanMemDung.bake_sang_canonical(native_timeline, approval_id="apr_founder_123")
    assert forked.representation_mode == "CANONICAL"
    assert forked.native_project_asset_id == "asset_drp_original"  # luu provenance


def test_mat_ket_noi_khong_ghi_de_native():
    """
    Kiem tra thao tac khong duoc ho tro tren che do NATIVE_BOUND se tra NATIVE_EDIT_REQUIRED,
    khong ghi de hoac pha vo project native
    """
    timeline = tao_sample_timeline_nle()
    bundle = BoKetNoiPhanMemDung.xuat_goi_ban_giao("prj_sin_nle", 1, timeline)
    native_timeline = BoKetNoiPhanMemDung.nhap_phien_ban_native(
        bundle_id=bundle.bundle_id,
        timeline_base=timeline,
        native_project_asset_id="asset_drp",
        native_hash="sha_native"
    )

    # Yeu cau thao tac chuyen sau (vi du 3d_camera_tracking khong duoc ho tro qua API)
    with pytest.raises(ValueError) as exc:
        BoKetNoiPhanMemDung.sua_tiep_tren_native(
            timeline=native_timeline,
            op_type="apply_3d_camera_tracking",
            payload={}
        )
    assert LoiHopDong.NATIVE_EDIT_REQUIRED in str(exc.value)
