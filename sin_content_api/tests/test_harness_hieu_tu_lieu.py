import pytest
from src.modules.dieu_phoi_dung.hieu_tu_lieu import BoHieuTuLieu, CauHinhPhanTich


def test_tieng_viet_co_word_id_va_nguon():
    """
    Kiem tra transcript tieng Viet co day du word_ids, source range va metadata chuan xac
    """
    transcript = [
        {
            "start_ms": 1000,
            "end_ms": 3500,
            "text": "Trà sữa Sin trân châu hoàng kim",
            "confidence": 0.94,
            "words": [
                {"word_id": "w_0", "text": "Trà", "start_ms": 1000, "end_ms": 1300},
                {"word_id": "w_1", "text": "sữa", "start_ms": 1350, "end_ms": 1600},
                {"word_id": "w_2", "text": "Sin", "start_ms": 1650, "end_ms": 2000},
                {"word_id": "w_3", "text": "trân", "start_ms": 2050, "end_ms": 2400},
                {"word_id": "w_4", "text": "châu", "start_ms": 2450, "end_ms": 2800},
                {"word_id": "w_5", "text": "hoàng", "start_ms": 2850, "end_ms": 3100},
                {"word_id": "w_6", "text": "kim", "start_ms": 3150, "end_ms": 3500}
            ]
        }
    ]

    evidence = BoHieuTuLieu.phan_tich_tu_lieu(
        workspace_id="ws_sin_01",
        asset_id="asset_video_01",
        source_sha256="sha256_mock_f01",
        transcript_data=transcript
    )

    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.modality == "speech"
    assert ev.source_sha256 == "sha256_mock_f01"
    assert ev.word_ids == ["w_0", "w_1", "w_2", "w_3", "w_4", "w_5", "w_6"]
    assert ev.source_range["start_ms"] == 1000
    assert ev.source_range["end_ms"] == 3500
    assert ev.notes == "Trà sữa Sin trân châu hoàng kim"
    assert ev.confidence == 0.94


def test_khong_loi_khong_bia_transcript():
    """
    Kiem tra doan im lang (silence) khong sinh transcript hoac loi thoai bia dat
    """
    transcript_with_silence = [
        {
            "start_ms": 0,
            "end_ms": 2000,
            "text": "",
            "is_silence": True
        },
        {
            "start_ms": 2000,
            "end_ms": 4000,
            "text": "   ",
            "is_silence": False
        }
    ]

    evidence = BoHieuTuLieu.phan_tich_tu_lieu(
        workspace_id="ws_sin_02",
        asset_id="asset_silent_01",
        source_sha256="sha256_silent_01",
        transcript_data=transcript_with_silence
    )

    # 100% khong co evidence modality='speech' duoc sinh ra cho doan im lang
    assert len(evidence) == 0


def test_canh_nhanh_can_xem_bo_sung():
    """
    Kiem tra canh rat nhanh (200ms) voi mau thua (1 FPS) bat buoc phai danh dau can xem bo sung
    """
    scenes = [
        {
            "start_ms": 500,
            "end_ms": 700,  # 200ms
            "label": "B-roll logo Sin chot nhoang",
            "sampled_fps": 1,
            "frame_ids": ["f_quick_01"]
        }
    ]

    evidence = BoHieuTuLieu.phan_tich_tu_lieu(
        workspace_id="ws_sin_03",
        asset_id="asset_quick_01",
        source_sha256="sha256_quick_01",
        scenes_data=scenes
    )

    assert len(evidence) == 1
    ev = evidence[0]
    assert ev.modality == "visual"
    assert "CAN_XEM_BO_SUNG_DENSE_SAMPLING" in (ev.notes or "")


def test_doi_source_lam_het_hieu_luc_evidence():
    """
    Kiem tra khi source_sha256 thay doi (file nguon bi sua), toan bo evidence cu bi vo hieu hoa
    """
    transcript = [{"start_ms": 0, "end_ms": 1000, "text": "Ban dau", "words": [{"word_id": "w1"}]}]
    ev_initial = BoHieuTuLieu.phan_tich_tu_lieu(
        workspace_id="ws_sin_04",
        asset_id="asset_source_change",
        source_sha256="sha_v1",
        transcript_data=transcript
    )
    assert len(ev_initial) == 1
    assert ev_initial[0].notes == "Ban dau"

    # Khi file bi sua (sha thay doi sang sha_v2)
    transcript_new = [{"start_ms": 0, "end_ms": 1000, "text": "Ban moi", "words": [{"word_id": "w2"}]}]
    ev_updated = BoHieuTuLieu.phan_tich_tu_lieu(
        workspace_id="ws_sin_04",
        asset_id="asset_source_change",
        source_sha256="sha_v2",  # SHA thay doi
        transcript_data=transcript_new
    )

    assert len(ev_updated) == 1
    assert ev_updated[0].notes == "Ban moi"
    assert ev_updated[0].source_sha256 == "sha_v2"


def test_cache_khong_dung_cheo_workspace():
    """
    Kiem tra cache evidence duoc co lap tuyet doi theo workspace_id
    """
    transcript = [{"start_ms": 0, "end_ms": 1000, "text": "Du lieu bao mat", "words": [{"word_id": "w1"}]}]
    BoHieuTuLieu.phan_tich_tu_lieu(
        workspace_id="ws_tenant_A",
        asset_id="asset_shared_name",
        source_sha256="sha_same",
        transcript_data=transcript
    )

    # Workspace B truy van cung asset_id nhung khong he co cache tu truoc
    results_ws_b = BoHieuTuLieu.tim_tu_lieu_theo_tu_khoa(
        workspace_id="ws_tenant_B",
        asset_id="asset_shared_name",
        query="Du lieu"
    )
    assert len(results_ws_b) == 0


def test_asr_thieu_confidence_khong_tu_gan():
    """
    Kiem tra neu provider ASR khong tra truong confidence thi giu nguyen None, khong tu bia dat
    """
    transcript_no_conf = [
        {
            "start_ms": 0,
            "end_ms": 1500,
            "text": "Khong co chi so tin cay",
            "words": [{"word_id": "w1"}]
            # khong co 'confidence'
        }
    ]

    evidence = BoHieuTuLieu.phan_tich_tu_lieu(
        workspace_id="ws_sin_05",
        asset_id="asset_no_conf",
        source_sha256="sha_no_conf",
        transcript_data=transcript_no_conf
    )

    assert len(evidence) == 1
    assert evidence[0].confidence is None
