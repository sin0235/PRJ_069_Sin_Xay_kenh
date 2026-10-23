import time
import pytest
from src.modules.dieu_phoi_dung.hop_dong import DonSuaCanh, LoiHopDong
from src.modules.dieu_phoi_dung.sua_bang_flow import (
    QuanLySuaCanh,
    CapabilityProvider
)


def tao_sample_don(route: str = "ASSISTED_UI") -> DonSuaCanh:
    return DonSuaCanh(
        request_id="req_test_flow_01",
        project_id="prj_sin_flow",
        draft_id="draft_01",
        source_asset_id="asset_footage_01",
        source_sha256="sha_footage_01",
        target_clip_id="clip_01",
        prompt="Doi phong nen sang bai bien mua he",
        preserve_list=["khuon_mat_sin", "trang_phuc", "giong_doc"],
        route=route,
        reference_asset_ids=["asset_ref_beach_img"]
    )


def test_route_ui_va_api_doc_lap():
    """
    Kiem tra 2 route ASSISTED_UI va API_DIRECT hoan toan doc lap,
    khong duoc gui nham don UI sang capability API va nguoc lai
    """
    cap_ui = CapabilityProvider(
        provider_name="FLOW_BROWSER_ASSISTED",
        route="ASSISTED_UI",
        model="Google-Flow-Omni-Flash"
    )
    don_api = tao_sample_don(route="API_DIRECT")

    # Don route API_DIRECT khong the chay tren capability ASSISTED_UI
    with pytest.raises(ValueError) as exc:
        QuanLySuaCanh.tao_don_sua_canh(don_api, cap_ui)
    assert "khong khop voi capability" in str(exc.value)

    # Don route ASSISTED_UI chay dung tren capability ASSISTED_UI
    don_ui = tao_sample_don(route="ASSISTED_UI")
    st = QuanLySuaCanh.tao_don_sua_canh(don_ui, cap_ui)
    assert st.status == "PENDING"


def test_capability_het_han_khong_duoc_goi():
    """
    Kiem tra capability da het han (expired) khong duoc phep goi
    """
    cap_expired = CapabilityProvider(
        provider_name="GEMINI_OMNI",
        route="API_DIRECT",
        model="gemini-omni-flash",
        expiry_epoch=time.time() - 3600  # het han 1 gio truoc
    )
    don = tao_sample_don(route="API_DIRECT")

    with pytest.raises(ValueError) as exc:
        QuanLySuaCanh.tao_don_sua_canh(don, cap_expired)
    assert "da het han" in str(exc.value)


def test_reference_khong_bi_nham_nguon_edit():
    """
    Kiem tra reference asset khong duoc phep trung voi source video can sua
    """
    cap = CapabilityProvider(
        provider_name="FLOW_ASSISTED",
        route="ASSISTED_UI",
        model="Flow"
    )
    don_trung = DonSuaCanh(
        request_id="req_trung",
        project_id="prj_1",
        draft_id="d1",
        source_asset_id="asset_same_id",
        source_sha256="sha1",
        target_clip_id="c1",
        prompt="Sua canh",
        preserve_list=[],
        route="ASSISTED_UI",
        reference_asset_ids=["asset_same_id"]  # Trung source
    )

    with pytest.raises(ValueError) as exc:
        QuanLySuaCanh.tao_don_sua_canh(don_trung, cap)
    assert "Reference asset khong duoc trung" in str(exc.value)


def test_output_sai_request_hoac_workspace_bi_chan():
    """
    Kiem tra nhan ket qua sai request_id hoac sai workspace bi chan
    """
    with pytest.raises(ValueError) as exc:
        QuanLySuaCanh.nhan_ket_qua_canh(
            request_id="req_unknown_non_existent",
            output_asset_id="asset_out",
            workspace_id="ws_01",
            duration_ms=5000,
            expected_duration_ms=5000
        )
    assert "Khong tim thay request_id" in str(exc.value)


def test_ket_qua_khac_duration_bi_chan():
    """
    Kiem tra ket qua render tra ve sai duration bi chan dung, khong duoc phep chap nhan
    """
    cap = CapabilityProvider(provider_name="FLOW", route="ASSISTED_UI", model="Flow")
    don = tao_sample_don(route="ASSISTED_UI")
    don.request_id = "req_dur_check"
    QuanLySuaCanh.tao_don_sua_canh(don, cap)

    # Expected la 5000ms nhung ket qua tra ve 8000ms (lech 3000ms > tolerance 200ms)
    with pytest.raises(ValueError) as exc:
        QuanLySuaCanh.nhan_ket_qua_canh(
            request_id="req_dur_check",
            output_asset_id="asset_wrong_dur",
            workspace_id="ws_01",
            duration_ms=8000,
            expected_duration_ms=5000
        )
    assert "khong khop voi expected" in str(exc.value)


def test_timeout_khong_ro_trang_thai():
    """
    Kiem tra khi provider timeout chua ro trang thai thi chuyen sang NEEDS_RECONCILIATION,
    khong resubmit mu
    """
    cap = CapabilityProvider(provider_name="FLOW", route="ASSISTED_UI", model="Flow")
    don = tao_sample_don(route="ASSISTED_UI")
    don.request_id = "req_timeout_test"
    QuanLySuaCanh.tao_don_sua_canh(don, cap)

    st = QuanLySuaCanh.xu_ly_timeout_khong_ro_trang_thai("req_timeout_test")
    assert st.status == "NEEDS_RECONCILIATION"


def test_bao_toan_phan_khong_yeu_cau_sua():
    """
    Kiem tra preserve list duoc ghi nhan day du trong don de bao toan cac phan khong sua
    """
    don = tao_sample_don()
    assert "khuon_mat_sin" in don.preserve_list
    assert "trang_phuc" in don.preserve_list
    assert "giong_doc" in don.preserve_list


def test_session_het_han_tiep_tuc_tu_asset_da_luu():
    """
    Kiem tra khi session provider het han, tiep tuc tu asset cuc bo da luu ma khong lam mat ket qua
    """
    cap = CapabilityProvider(provider_name="FLOW", route="ASSISTED_UI", model="Flow")
    don = tao_sample_don(route="ASSISTED_UI")
    don.request_id = "req_session_expired"
    QuanLySuaCanh.tao_don_sua_canh(don, cap)

    st = QuanLySuaCanh.khoi_phuc_tu_asset_da_luu("req_session_expired", "asset_local_cached_01")
    assert st.status == "COMPLETED"
    assert st.output_asset_id == "asset_local_cached_01"
