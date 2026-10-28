# -*- coding: utf-8 -*-
"""
Bộ kiểm thử toàn diện cho 5 hạng mục nâng cấp Điều Phối Dựng Video:
1. Cách ly tài nguyên đa người thuê (Workspace/Tenant Isolation) trên bo_dinh_tuyen.py
2. Phục hồi sau Restart & Đồng bộ Đa Worker từ Kho lưu trữ Bền vững SQLite
3. Luồng Sửa Cảnh Flow/API: Biên nhận Assisted UI thật và Xác minh Tài sản CSDL
4. Bàn giao NLE: Sinh tệp vật lý thật (timeline.xml, manifest.json, loss_report.json) và Relink
5. Nối TimelineV2 với Bộ Render FFmpeg/NLE: Áp LUT thật, Retime thật, chặn thao tác thiếu Adapter
"""
import copy
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.database import Base, SessionLocal, engine
from src.models.entities import Workspace, User, Membership
from src.models.entities import ProductionProject
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from baha_auth.src.models.entities import (
    GlobalUser,
    Membership as AuthMembership,
    Role as AuthRole,
    RoleAssignment,
    Workspace as AuthWorkspace
)
from src.modules.dieu_phoi_dung.hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    CaptionV2,
    ThoiGianNguon,
    LenhDung,
    DonSuaCanh,
    LoiHopDong
)
from src.modules.dieu_phoi_dung.phien_dung import QuanLyPhienDung
from src.modules.dieu_phoi_dung.cong_cu import DieuPhoiCongCu
from src.modules.dieu_phoi_dung.sua_bang_flow import QuanLySuaCanh, CapabilityProvider
from src.modules.dieu_phoi_dung.ket_noi_phan_mem_dung import BoKetNoiPhanMemDung
from src.modules.dieu_phoi_dung.kho_luu_tru import KhoLuuTruDung
from src.modules.dieu_phoi_dung.bo_render import BoRenderDung
from src.modules.dieu_phoi_dung.bo_dinh_tuyen import _kiem_tra_quyen_du_an
from tests.conftest import tao_bearer_token, setup_test_auth_user


@pytest.fixture
def du_lieu_hai_workspace():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)

    with SessionLocal() as db, AuthSessionLocal() as auth_db:
        # Them vao content db
        for ws in ["ws_alpha", "ws_beta"]:
            if not db.query(Workspace).filter(Workspace.id == ws).first():
                db.add(Workspace(id=ws, name=ws, slug=ws))
        db.commit()

        setup_test_auth_user(auth_db, "ws_alpha", "user_alpha", "user_alpha@test.local", "WORKSPACE_OWNER")
        setup_test_auth_user(auth_db, "ws_beta", "user_beta", "user_beta@test.local", "WORKSPACE_OWNER")

    return {
        "token_alpha": tao_bearer_token("user_alpha"),
        "token_beta": tao_bearer_token("user_beta")
    }


def tao_sample_timeline_chuan() -> TimelineV2:
    clip1 = ClipV2(
        clip_id="c_main_1",
        asset_id="asset_video_01",
        start_frame=0,
        duration_frames=90,  # 3s
        source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
        source_out=ThoiGianNguon(ticks=3000, time_base_num=1, time_base_den=1000)
    )
    track_v = TrackV2(
        track_id="trk_v1",
        track_type="video",
        layer_index=0,
        name="Main Video",
        clips=[clip1]
    )
    cap = CaptionV2(
        caption_id="cap_01",
        start_ms=0,
        end_ms=2500,
        text="Trà sữa Sin nguyên bản"
    )
    return TimelineV2(tracks=[track_v], captions=[cap])


def test_dieu_phoi_tu_choi_project_khong_co_trong_database(du_lieu_hai_workspace):
    from fastapi import HTTPException

    with SessionLocal() as db, pytest.raises(HTTPException) as exc_info:
        _kiem_tra_quyen_du_an(db, "project-missing", "ws_alpha")
    assert exc_info.value.status_code == 404


# ==============================================================================
# HẠNG MỤC 1: CÁCH LY TÀI NGUYÊN THEO WORKSPACE (WORKSPACE ISOLATION)
# ==============================================================================

def test_ngan_chan_truy_cap_draft_khac_workspace(du_lieu_hai_workspace):
    """
    Kiem tra Nguoi dung o Workspace B khong the doc hoac sua Draft cua Workspace A
    ngay ca khi biet chinh xac draft_id.
    """
    client = TestClient(app)
    t = tao_sample_timeline_chuan()
    b_hash = QuanLyPhienDung.tinh_hash_timeline(t)

    # 1. Tao phien va draft tai Workspace A
    phien_a = QuanLyPhienDung.tao_phien(
        project_id="prj_alpha",
        workspace_id="ws_alpha",
        actor_id="user_alpha",
        base_revision=1,
        base_hash=b_hash
    )
    draft_a = QuanLyPhienDung.tao_ban_nhap(phien_a.run_id, t)

    headers_ws_beta = {
        "Authorization": f"Bearer {du_lieu_hai_workspace['token_beta']}",
        "X-Workspace-Id": "ws_beta"
    }

    # 2. Workspace B co tinh doc Draft cua Workspace A -> Phai bi chan (403 hoac 404)
    res_get = client.get(
        f"/v1/media/projects/prj_alpha/dung/ban-nhap/{draft_a.draft_id}",
        headers=headers_ws_beta
    )
    assert res_get.status_code in (403, 404)

    # 3. Workspace B co tinh thuc hien lenh sua tren Draft cua Workspace A -> Phai bi 403
    cmd = {
        "expected_draft_revision": 1,
        "commands": [
            {
                "operation_id": "op_hack_01",
                "draft_id": draft_a.draft_id,
                "expected_draft_revision": 1,
                "type": "trim_clip",
                "payload": {"track_id": "trk_v1", "clip_id": "c_main_1", "trim_in_ms": 100, "trim_out_ms": 2000}
            }
        ]
    }
    res_post = client.post(
        f"/v1/media/projects/prj_alpha/dung/ban-nhap/{draft_a.draft_id}/lenh",
        json=cmd,
        headers=headers_ws_beta
    )
    assert res_post.status_code in (403, 400)


def test_ngan_chan_run_khac_workspace(du_lieu_hai_workspace):
    """
    Kiem tra truy cap run_id tu workspace khac bi chan hoan toan.
    """
    client = TestClient(app)
    t = tao_sample_timeline_chuan()
    b_hash = QuanLyPhienDung.tinh_hash_timeline(t)

    phien_a = QuanLyPhienDung.tao_phien(
        project_id="prj_gamma",
        workspace_id="ws_alpha",
        actor_id="user_alpha",
        base_revision=1,
        base_hash=b_hash
    )

    headers_beta = {
        "Authorization": f"Bearer {du_lieu_hai_workspace['token_beta']}",
        "X-Workspace-Id": "ws_beta"
    }

    # Doc trang thai phien
    res_run = client.get(
        f"/v1/media/projects/prj_gamma/dung/phien/{phien_a.run_id}",
        headers=headers_beta
    )
    assert res_run.status_code in (403, 404)

    # Tiep tuc phien
    res_resume = client.post(
        f"/v1/media/projects/prj_gamma/dung/phien/{phien_a.run_id}/tiep-tuc",
        headers=headers_beta
    )
    assert res_resume.status_code in (403, 404)


# ==============================================================================
# HẠNG MỤC 2: PHỤC HỒI SAU RESTART & ĐỒNG BỘ ĐA WORKER TỪ SQLITE
# ==============================================================================

def test_phuc_hoi_sau_restart_tu_kho_ben_vung():
    """
    Mo phong su co service restart (xoa sach dictionary trong RAM).
    Kiem tra he thong doc lai checkpoint, draft, lease va journal tu SQLite.
    """
    initial_timeline = tao_sample_timeline_chuan()
    base_hash = QuanLyPhienDung.tinh_hash_timeline(initial_timeline)

    # 1. Tao phien va ban nhap
    phien = QuanLyPhienDung.tao_phien(
        project_id="prj_persist_01",
        workspace_id="ws_persist",
        actor_id="worker_1",
        base_revision=1,
        base_hash=base_hash
    )
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, initial_timeline)

    # Thuc hien 1 lenh de tang revision len 2
    cmd = LenhDung(
        operation_id="op_persist_01",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="trim_clip",
        payload={"track_id": "trk_v1", "clip_id": "c_main_1", "trim_in_ms": 200, "trim_out_ms": 2500}
    )
    res_cmd = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd])
    assert res_cmd.revision_after == 2

    # 2. GIA LAP SERVICE RESTART: Xoa sach RAM cache cua tien trinh
    QuanLyPhienDung._active_runs.clear()
    QuanLyPhienDung._drafts.clear()
    QuanLyPhienDung._checkpoints.clear()
    QuanLyPhienDung._project_active_writer.clear()
    DieuPhoiCongCu._journal.clear()

    # 3. Kiem tra phuc hoi sau restart:
    # 3.1 Lay lai ban nhap tu disk
    recovered_draft = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    assert recovered_draft.draft_id == draft.draft_id
    assert recovered_draft.draft_revision == 2
    assert recovered_draft.project_id == "prj_persist_01"

    # 3.2 Tiep tuc phien tu checkpoint tren disk
    recovered_cp = QuanLyPhienDung.tiep_tuc_phien(phien.run_id)
    assert recovered_cp.run_id == phien.run_id
    assert recovered_cp.status == "EDITING"
    assert recovered_cp.step_count >= 1

    # 3.3 Idempotency Journal tren disk: Replay lenh cu phai tra ve ket qua cu
    replay_res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 2, [cmd])
    assert replay_res.operation_id == "op_persist_01"
    assert replay_res.revision_after == 2


def test_dong_bo_giua_hai_worker_doc_lap():
    """
    Kiem tra Worker A ghi trang thai, Worker B truy cap lap tuc nhin thay du lieu nhat quan.
    """
    t = tao_sample_timeline_chuan()
    b_hash = QuanLyPhienDung.tinh_hash_timeline(t)

    # Worker A tao phien
    phien_a = QuanLyPhienDung.tao_phien(
        project_id="prj_multi_worker",
        workspace_id="ws_worker",
        actor_id="worker_a",
        base_revision=1,
        base_hash=b_hash
    )
    draft_a = QuanLyPhienDung.tao_ban_nhap(phien_a.run_id, t)

    # Worker B khong co ban ghi trong RAM rieng
    QuanLyPhienDung._drafts.pop(draft_a.draft_id, None)

    # Worker B doc va thuc hien lenh sua tiep tren Draft
    cmd_b = LenhDung(
        operation_id="op_worker_b_01",
        draft_id=draft_a.draft_id,
        expected_draft_revision=1,
        type="set_clip_gain",
        payload={"track_id": "trk_v1", "clip_id": "c_main_1", "gain_db": -3.0}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft_a.draft_id, 1, [cmd_b])
    assert res.status == "SUCCESS"
    assert res.revision_after == 2


# ==============================================================================
# HẠNG MỤC 3: LUỒNG SỬA CẢNH FLOW/API VÀ XÁC MINH TÀI SẢN
# ==============================================================================

def test_tao_don_assisted_ui_sinh_receipt_that():
    """
    Kiem tra route ASSISTED_UI sinh receipt token hop le va huong dan nguoi dung ro rang.
    """
    don = DonSuaCanh(
        request_id="req_assisted_receipt_01",
        project_id="prj_flow_receipt",
        draft_id="draft_flow_01",
        source_asset_id="asset_orig_01",
        source_sha256="sha_orig_01",
        target_clip_id="c_main_1",
        prompt="Doi phong nen sang thanh pho ban dem",
        preserve_list=["khuon_mat_sin"],
        route="ASSISTED_UI",
        reference_asset_ids=["asset_ref_city"]
    )
    cap = CapabilityProvider(
        provider_name="FLOW_BROWSER_ASSISTED",
        route="ASSISTED_UI",
        model="Google-Flow-Omni-Flash"
    )

    st = QuanLySuaCanh.tao_don_sua_canh(don, cap, workspace_id="ws_sin_flow")
    assert st.status == "PENDING"
    assert "rcpt_flow_" in st.notes

    # Kiem tra don duoc luu tren kho ben vung
    don_db = KhoLuuTruDung.lay_don_sua_canh(don.request_id)
    assert don_db is not None
    assert don_db["workspace_id"] == "ws_sin_flow"
    assert "rcpt_flow_" in don_db["receipt_token"]


def test_callback_nhan_ket_qua_sai_workspace_bi_chan():
    """
    Kiem tra callback nhan ket qua canh tu workspace khac bi tu choi bang CROSS_WORKSPACE_ASSET.
    """
    don = DonSuaCanh(
        request_id="req_ws_guard_01",
        project_id="prj_ws_guard",
        draft_id="draft_01",
        source_asset_id="asset_src",
        source_sha256="sha_src",
        target_clip_id="c1",
        prompt="Sua canh",
        preserve_list=[],
        route="ASSISTED_UI",
        reference_asset_ids=[]
    )
    cap = CapabilityProvider(provider_name="FLOW", route="ASSISTED_UI", model="Flow")
    QuanLySuaCanh.tao_don_sua_canh(don, cap, workspace_id="ws_legit")

    # Client o workspace khac goi callback voi request_id nay
    with pytest.raises(ValueError) as exc:
        QuanLySuaCanh.nhan_ket_qua_canh(
            request_id="req_ws_guard_01",
            output_asset_id="asset_rogue_01",
            workspace_id="ws_attacker",
            duration_ms=5000,
            expected_duration_ms=5000,
            project_id="prj_ws_guard"
        )
    assert LoiHopDong.CROSS_WORKSPACE_ASSET in str(exc.value)


# ==============================================================================
# HẠNG MỤC 4: BÀN GIAO NLE SINH TỆP VẬT LÝ VÀ RELINK
# ==============================================================================

def test_xuat_goi_ban_giao_sinh_tep_vat_ly_that():
    """
    Kiem tra BoKetNoiPhanMemDung thuc su sinh timeline.xml, manifest.json va loss_report.json tren disk.
    Kiem tra goi co the relink hop le trong NLE.
    """
    t = tao_sample_timeline_chuan()
    bundle = BoKetNoiPhanMemDung.xuat_goi_ban_giao(
        project_id="prj_real_export",
        revision=1,
        timeline=t,
        adapter_id="FINAL_CUT_XML",
        workspace_id="ws_real_export"
    )

    assert bundle.bundle_id == "bnd_prj_real_export_rev1"
    assert len(bundle.files) == 3

    # Kiem tra su ton tai vat ly cua cac file tren disk
    assert BoKetNoiPhanMemDung.kiem_tra_goi_relink(bundle.bundle_id, "prj_real_export") is True

    # Kiem tra timeline.xml co the parse va chua thong tin clip
    api_root = Path(__file__).resolve().parents[1]
    xml_path = api_root / "exports" / "nle_bundles" / bundle.bundle_id / "timeline.xml"
    assert xml_path.exists()
    tree = ET.parse(str(xml_path))
    root = tree.getroot()
    assert root.tag == "xmeml"
    clipitems = root.findall(".//clipitem")
    assert len(clipitems) == 1
    assert clipitems[0].attrib["id"] == "c_main_1"


# ==============================================================================
# HẠNG MỤC 5: NỐI TIMELINE VỚI RENDERER FFMPEG/NLE (LUT & RETIME THẬT)
# ==============================================================================

def test_apply_color_lut_sinh_filter_that_va_chan_unsupported():
    """
    Kiem tra lenh apply_color_lut gan spec render that (lut3d),
    va tu choi cac hieu ung / format LUT khong co execution adapter.
    """
    t = tao_sample_timeline_chuan()
    phien = QuanLyPhienDung.tao_phien("prj_lut_exec", "ws_lut", "user_1", 1, "hash_lut")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, t)

    # 1. LUT hop le: Phai thuc thi thanh cong va sinh filter spec
    cmd_ok = LenhDung(
        operation_id="op_lut_valid",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="apply_color_lut",
        payload={"track_id": "trk_v1", "clip_id": "c_main_1", "lut_asset_id": "lut_sin_teal_orange"}
    )
    res_ok = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_ok])
    assert res_ok.status == "SUCCESS"

    draft_after = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    clip_after = draft_after.timeline.tracks[0].clips[0]
    assert clip_after.lut_asset_id == "lut_sin_teal_orange"

    # Kiem tra bien dich filtergraph FFmpeg chua dung lut3d
    fg = BoRenderDung.bien_dich_filtergraph_clip(clip_after)
    assert "lut3d=file='lut_sin_teal_orange.cube'" in fg["video_filter_chain"]
    assert fg["has_video_processing"] is True

    # 2. Thao tac LUT khong hop le / khong co adapter phai bi tu choi bang UNSUPPORTED_EFFECT
    cmd_unsupported = LenhDung(
        operation_id="op_lut_unsupported",
        draft_id=draft.draft_id,
        expected_draft_revision=2,
        type="apply_color_lut",
        payload={"track_id": "trk_v1", "clip_id": "c_main_1", "lut_asset_id": "unsupported_neural_grading_cube"}
    )
    with pytest.raises(ValueError) as exc:
        DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 2, [cmd_unsupported])
    assert LoiHopDong.UNSUPPORTED_EFFECT in str(exc.value)


def test_retime_sinh_filter_setpts_va_atempo():
    """
    Kiem tra set_retime_speed sinh day du filter bien doi toc do hinh (setpts) va tieng (atempo).
    """
    t = tao_sample_timeline_chuan()
    phien = QuanLyPhienDung.tao_phien("prj_retime_exec", "ws_retime", "user_1", 1, "hash_retime")
    draft = QuanLyPhienDung.tao_ban_nhap(phien.run_id, t)

    # Tang toc video 2.0x
    cmd_speed = LenhDung(
        operation_id="op_speed_2x",
        draft_id=draft.draft_id,
        expected_draft_revision=1,
        type="set_retime_speed",
        payload={"track_id": "trk_v1", "clip_id": "c_main_1", "speed_ratio": 2.0}
    )
    res = DieuPhoiCongCu.thuc_hien_lenh(draft.draft_id, 1, [cmd_speed])
    assert res.status == "SUCCESS"

    draft_after = QuanLyPhienDung.lay_ban_nhap(draft.draft_id)
    clip_after = draft_after.timeline.tracks[0].clips[0]
    assert clip_after.speed_ratio == 2.0

    fg = BoRenderDung.bien_dich_filtergraph_clip(clip_after)
    assert "setpts=" in fg["video_filter_chain"]
    assert "atempo=" in fg["audio_filter_chain"]
