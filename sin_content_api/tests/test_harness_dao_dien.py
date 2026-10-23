import pytest
from src.modules.dieu_phoi_dung.hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    ThoiGianNguon,
    BangChungNguon,
    ChinhSachPhien,
    kiem_tra_ke_hoach,
    LoiHopDong
)
from src.modules.dieu_phoi_dung.dao_dien import (
    DaoDienDung,
    YeuCauPhanHoi,
    RECIPES_CHUAN
)


def tao_sample_snapshot() -> TimelineV2:
    clip1 = ClipV2(
        clip_id="clip_01",
        asset_id="asset_sin_review",
        start_frame=0,
        duration_frames=90,
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
    )
    clip2 = ClipV2(
        clip_id="clip_02",
        asset_id="asset_sin_review",
        start_frame=90,
        duration_frames=90,
        source_in=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=6000, time_base_num=1, time_base_den=1000)
    )
    return TimelineV2(
        tracks=[TrackV2(track_id="trk_v1", track_type="video", layer_index=0, clips=[clip1, clip2])]
    )


def test_plan_chi_dung_nguon_va_evidence_hop_le():
    """
    Kiem tra lap ke hoach chi su dung nguon va evidence hop le da duoc phan tich
    """
    policy = ChinhSachPhien()
    snapshot = tao_sample_snapshot()
    evidence = [
        BangChungNguon(
            evidence_id="ev_hook",
            asset_id="asset_sin_review",
            source_sha256="sha_hook",
            analysis_version="1.0",
            modality="speech",
            source_range={"start_ms": 0, "end_ms": 3000},
            notes="Tra sua ngon nhat khu vuc"
        )
    ]
    brief = {"brief_id": "brief_sin_01", "type": "dung_co_loi"}

    plan = DaoDienDung.lap_ke_hoach(brief, snapshot, evidence, policy)

    assert plan.plan_id.startswith("plan_brief_sin_01")
    assert len(plan.proposed_commands) == 1
    assert plan.proposed_commands[0].evidence_ids == ["ev_hook"]
    assert plan.missing_evidence == []

    # Kiem tra validation hop dong
    errors = kiem_tra_ke_hoach(plan, snapshot, evidence, policy)
    assert errors == []


def test_phan_hoi_neo_revision_va_giu_phan_con_lai():
    """
    Kiem tra phan hoi co chu dich (chinh volume clip_01) chi sinh patch tren dung clip_01 va giu nguyen clip_02
    """
    policy = ChinhSachPhien()
    snapshot = tao_sample_snapshot()
    feedback = YeuCauPhanHoi(
        feedback_id="fb_01",
        target_clip_id="clip_01",
        instruction="Giam volume tieng o doan nay xuong",
        base_revision=1
    )

    plan = DaoDienDung.lap_ke_hoach_sua(feedback, snapshot, [], policy)
    assert len(plan.proposed_commands) == 1
    cmd = plan.proposed_commands[0]
    assert cmd.type == "set_clip_gain"
    assert cmd.payload["clip_id"] == "clip_01"


def test_thieu_y_nghia_can_hoi_lai():
    """
    Kiem tra phan hoi mo ho (vi du: 'chinh lai cho dep hon') khong tu y sua linh tinh,
    ma tra ve thong bao NEEDS_CLARIFICATION de hoi lai nguoi dung
    """
    policy = ChinhSachPhien()
    snapshot = tao_sample_snapshot()
    feedback_ambiguous = YeuCauPhanHoi(
        feedback_id="fb_ambiguous",
        target_clip_id=None,
        timecode_ms=None,
        instruction="Chỉnh lại cho đẹp hơn đi nhìn chán quá",
        base_revision=1
    )

    plan = DaoDienDung.lap_ke_hoach_sua(feedback_ambiguous, snapshot, [], policy)
    assert len(plan.proposed_commands) == 0
    assert "FEEDBACK_AMBIGUOUS_NEEDS_CLARIFICATION" in plan.missing_evidence


def test_vong_lap_dung_khi_khong_tien_trien():
    """
    Kiem tra co che ngat khan cap khi 3 buoc lien tiep khong tien trien hoac trung fingerprint loi
    """
    assert DaoDienDung.kiem_tra_vong_lap_khong_tien_trien(consecutive_identical_errors=3, consecutive_no_change_steps=0) is True
    assert DaoDienDung.kiem_tra_vong_lap_khong_tien_trien(consecutive_identical_errors=0, consecutive_no_change_steps=3) is True
    assert DaoDienDung.kiem_tra_vong_lap_khong_tien_trien(consecutive_identical_errors=1, consecutive_no_change_steps=1) is False


def test_prompt_recipe_co_version():
    """
    Kiem tra 5 recipes chuan deu co recipe_id, version va checklist nghiem ngat
    """
    assert len(RECIPES_CHUAN) == 5
    for key, recipe in RECIPES_CHUAN.items():
        assert recipe.version == "1.0"
        assert len(recipe.checklist) >= 3


def test_json_hop_le_nhung_sai_nguon_van_bi_chan():
    """
    Kiem tra JSON hop le nhung chua evidence_id khong ton tai trong database van bi chan
    """
    policy = ChinhSachPhien()
    snapshot = tao_sample_snapshot()
    evidence_valid = [
        BangChungNguon(
            evidence_id="ev_real",
            asset_id="asset_real",
            source_sha256="sha_real",
            analysis_version="1.0",
            modality="speech"
        )
    ]
    brief = {
        "brief_id": "brief_fake_ev",
        "type": "dung_co_loi",
        "required_evidence_ids": ["ev_fake_non_existent"]  # fake ID
    }

    plan = DaoDienDung.lap_ke_hoach(brief, snapshot, evidence_valid, policy)
    assert "ev_fake_non_existent" in plan.missing_evidence
    errors = kiem_tra_ke_hoach(plan, snapshot, evidence_valid, policy)
    assert any(LoiHopDong.MISSING_EVIDENCE in e for e in errors)
