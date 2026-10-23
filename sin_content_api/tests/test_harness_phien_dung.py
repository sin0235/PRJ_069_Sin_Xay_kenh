import pytest
from src.modules.dieu_phoi_dung.hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    CaptionV2,
    ThoiGianNguon,
    LenhDung,
    LoiHopDong,
    ChinhSachPhien
)
from src.modules.dieu_phoi_dung.phien_dung import QuanLyPhienDung
from src.modules.dieu_phoi_dung.cong_cu import DieuPhoiCongCu


def tao_sample_timeline() -> TimelineV2:
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
        duration_frames=60,  # 2s
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=2000, time_base_num=1, time_base_den=1000)
    )
    track_v = TrackV2(
        track_id="trk_v1",
        track_type="video",
        layer_index=0,
        name="Main Video",
        clips=[clip1, clip2]
    )
    cap = CaptionV2(
        caption_id="cap_01",
        start_ms=0,
        end_ms=2500,
        text="Tra sua Sin nguyen ban"
    )
    return TimelineV2(
        schema_version=2,
        tracks=[track_v],
        captions=[cap]
    )


def test_draft_khong_doi_live():
    """
    Kiem tra Agent thao tac tren BanNhapDung khong lam thay doi Timeline live cua du an
    """
    initial_timeline = tao_sample_timeline()
    base_hash = QuanLyPhienDung.tinh_hash_timeline(initial_timeline)

    phien = QuanLyPhienDung.tao_phien(
        project_id="prj_test_01",
        workspace_id="ws_01",
        actor_id="agent_01",
        base_revision=1,
        base_hash=base_hash
    )

    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, initial_timeline)
    assert draft.draft_revision == 1
    assert draft.base_revision == 1

    # Thuc hien lenh trim clip tren draft
    cmd_trim = LenhDung(
        operation_id="op_trim_01",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="trim_clip",
        payload={
            "track_id": "trk_v1",
            "clip_id": "c1",
            "trim_in_ms": 500,
            "trim_out_ms": 2500
        }
    )
    result = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_trim])
    assert result.status == "SUCCESS"
    assert result.revision_after == 2

    # Snapshot ban dau van giu nguyen ven
    assert initial_timeline.tracks[0].clips[0].duration_frames == 90
    assert initial_timeline.tracks[0].clips[0].source_in.ticks == 0

    # Draft da duoc cap nhat
    updated_draft = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    assert updated_draft.draft_revision == 2
    assert updated_draft.timeline.tracks[0].clips[0].duration_frames == 60  # (2500-500)/1000 * 30fps


def test_lenh_nguyen_tu_va_doc_lai():
    """
    Kiem tra tinh nguyen tu (All-or-Nothing): Neu mot lenh trong batch bi loi,
    toan bo batch bi rollback, khong thay doi snapshot draft
    """
    initial_timeline = tao_sample_timeline()
    phien = QuanLyPhienDung.tao_phien(
        project_id="prj_test_02",
        workspace_id="ws_01",
        actor_id="agent_01",
        base_revision=1,
        base_hash="hash_02"
    )
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, initial_timeline)
    initial_draft_hash = draft.draft_hash

    # Batch gom 2 lenh: lenh 1 hop le, lenh 2 sai out-of-bounds
    cmd_ok = LenhDung(
        operation_id="op_batch_ok",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="set_caption_text",
        payload={"caption_id": "cap_01", "text": "Tra sua sua lai"}
    )
    cmd_fail = LenhDung(
        operation_id="op_batch_fail",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="split_clip",
        payload={"track_id": "trk_v1", "clip_id": "c1", "split_frame": 9999}  # OOB
    )

    with pytest.raises(ValueError) as exc:
        DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_ok, cmd_fail])

    assert "rollback toan bo batch" in str(exc.value)

    # Kiem tra snapshot draft hoan toan giu nguyen (khong doi revision, khong doi caption text)
    draft_after = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    assert draft_after.draft_revision == 1
    assert draft_after.draft_hash == initial_draft_hash
    assert draft_after.timeline.captions[0].text == "Tra sua Sin nguyen ban"


def test_cung_key_khac_payload_xung_dot():
    """
    Kiem tra Idempotency:
    - Cung operation_id + cung payload -> Tra lai ket qua cu (Replay an toan)
    - Cung operation_id + khac payload -> Bao loi xung dot (409 Conflict)
    """
    initial_timeline = tao_sample_timeline()
    phien = QuanLyPhienDung.tao_phien(
        project_id="prj_test_03",
        workspace_id="ws_01",
        actor_id="agent_01",
        base_revision=1,
        base_hash="hash_03"
    )
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, initial_timeline)

    cmd1 = LenhDung(
        operation_id="op_idem_01",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="set_clip_gain",
        payload={"track_id": "trk_v1", "clip_id": "c1", "gain_db": -3.5}
    )
    res1 = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd1])
    assert res1.status == "SUCCESS"
    assert res1.revision_after == 2

    # Goi lai dung op_id do va dung payload -> Tra ve ket qua cu
    res2 = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 2, [cmd1])
    assert res2.operation_id == "op_idem_01"
    assert res2.revision_after == 2

    # Goi lai op_id do nhung doi payload -> Ném lỗi xung đột 409
    cmd_conflict = LenhDung(
        operation_id="op_idem_01",
        draft_id=draft.draft_id,
        expected_draft_revision=2,
        type="set_clip_gain",
        payload={"track_id": "trk_v1", "clip_id": "c1", "gain_db": 5.0}  # Khac payload
    )
    with pytest.raises(ValueError) as exc:
        DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 2, [cmd_conflict])

    assert LoiHopDong.OCC_CONFLICT_409 in str(exc.value)


def test_ghi_stale_hoac_khoa_bi_chan():
    """
    Kiem tra CAS: Expected draft revision sai hoac draft bi khoa bi chan 100%
    """
    initial_timeline = tao_sample_timeline()
    phien = QuanLyPhienDung.tao_phien(
        project_id="prj_test_04",
        workspace_id="ws_01",
        actor_id="agent_01",
        base_revision=1,
        base_hash="hash_04"
    )
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, initial_timeline)

    # Expected revision sai (truyen 5 trong khi draft dang la 1)
    cmd_stale = LenhDung(
        operation_id="op_stale_01",
        draft_id=draft.draft_id,
        expected_draft_revision=5,
        type="set_caption_text",
        payload={"caption_id": "cap_01", "text": "Test"}
    )
    with pytest.raises(ValueError) as exc:
        DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 5, [cmd_stale])
    assert LoiHopDong.OCC_CONFLICT_409 in str(exc.value)

    # Khoa draft
    draft.is_locked = True
    cmd_locked = LenhDung(
        operation_id="op_locked_01",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="set_caption_text",
        payload={"caption_id": "cap_01", "text": "Test"}
    )
    with pytest.raises(ValueError) as exc:
        DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_locked])
    assert LoiHopDong.OCC_CONFLICT_409 in str(exc.value)


def test_khoi_dong_lai_khong_gui_lai():
    """
    Kiem tra tinh nang phuc hoi checkpoint (Resume): Doc lai trang thai da luu qua restart
    """
    initial_timeline = tao_sample_timeline()
    phien = QuanLyPhienDung.tao_phien(
        project_id="prj_test_05",
        workspace_id="ws_01",
        actor_id="agent_01",
        base_revision=1,
        base_hash="hash_05"
    )
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, initial_timeline)

    # Thuc hien 1 lenh
    cmd = LenhDung(
        operation_id="op_resume_01",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="set_retime_speed",
        payload={"track_id": "trk_v1", "clip_id": "c1", "speed_ratio": 2.0}
    )
    DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd])

    # Gia lap khoi dong lai tien trinh va doc lai checkpoint
    cp = QuanLyPhienDung.tiep_tuc_phien(phien.run_id)
    assert cp.run_id == phien.run_id
    assert cp.status == "EDITING"
    assert cp.step_count == 1
    assert draft.draft_id in cp.saved_draft_ids


def test_thu_hoi_grant_truoc_side_effect():
    """
    Kiem tra huy phien (revoke run grant): Ngung moi quyen ghi tren project
    """
    initial_timeline = tao_sample_timeline()
    phien = QuanLyPhienDung.tao_phien(
        project_id="prj_test_06",
        workspace_id="ws_01",
        actor_id="agent_01",
        base_revision=1,
        base_hash="hash_06"
    )
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, initial_timeline)

    # Huy phien
    QuanLyPhienDung.huy_phien(phien.run_id)
    cp = QuanLyPhienDung.tiep_tuc_phien(phien.run_id)
    assert cp.status == "CANCELLED"


def test_khoa_tac_vu_nang_lien_tien_trinh():
    """
    Kiem tra Lease/Lock chong hai writer cung ghi tren 1 project tai 1 thoi diem
    """
    initial_timeline = tao_sample_timeline()
    phien1 = QuanLyPhienDung.tao_phien(
        project_id="prj_test_07_concurrent",
        workspace_id="ws_01",
        actor_id="writer_01",
        base_revision=1,
        base_hash="hash_07"
    )

    # Writer thu hai co gang tao phien tren cung project_id khi phien 1 dang hoat dong
    with pytest.raises(ValueError) as exc:
        QuanLyPhienDung.tao_phien(
            project_id="prj_test_07_concurrent",
            workspace_id="ws_01",
            actor_id="writer_02",
            base_revision=1,
            base_hash="hash_07"
        )
    assert LoiHopDong.OCC_CONFLICT_409 in str(exc.value)
