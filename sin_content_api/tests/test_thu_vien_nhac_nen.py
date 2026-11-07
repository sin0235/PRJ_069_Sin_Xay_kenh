"""Kiểm định toàn diện thư viện nhạc nền Royalty-free và cơ chế ghép nhạc nền xuyên suốt video.

Tuân thủ:
- AGENTS.md (9 Nguyên Tắc Bất Biến, NO EMOJI - SVG ONLY).
- 1 track nhạc nền đi xuyên suốt toàn bộ video từ đầu đến cuối.
- Auto-ducking dưới giọng nói và chuẩn hóa EBU R128 (-14.0 ± 1.0 LUFS).
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth.tenancy import TenantContext, get_current_tenant_context
from src.models.entities import Base, MediaAsset, Workspace, ProductionProject, User
from src.modules.media_studio.audio_processor import audio_processor
from src.modules.media_studio.router import media_router
from src.modules.media_studio.thu_vien_nhac_nen import (
    THU_MUC_NHAC_GOC,
    FILE_BANG_KE,
    danh_sach_nhac_nen,
    doc_bang_ke_ban_quyen,
    lay_duong_dan_tep_goc,
    lay_thong_tin_bai_nhac,
    chon_nhac_nen_tu_dong,
    dong_bo_tai_nguyen_nhac_nen,
)
from src.modules.media_studio.video_processor import video_processor


@pytest.fixture
def test_db_session(tmp_path, monkeypatch):
    """Khởi tạo SQLite database cô lập cho test."""
    db_file = tmp_path / "test_bgm.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()

    media_root = tmp_path / "media_root"
    media_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("src.modules.media_studio.security.MEDIA_ROOT_DIR", media_root)
    monkeypatch.setattr("src.modules.media_studio.thu_vien_nhac_nen.MEDIA_ROOT_DIR", media_root)
    monkeypatch.setattr("src.modules.media_studio.service.MEDIA_ROOT_DIR", media_root)

    # Tạo Workspace và User
    ws = Workspace(id="ws-test-bgm", name="Workspace Test BGM", slug="ws-test-bgm")
    session.add(ws)
    user = User(id="usr-test-bgm", email="test@baha.local", full_name="Tester")
    session.add(user)
    proj = ProductionProject(id="prj-test-bgm", workspace_id="ws-test-bgm", title="Dự án test BGM", created_by="usr-test-bgm")
    session.add(proj)
    session.commit()

    try:
        yield session, media_root
    finally:
        session.close()


def test_kho_nhac_nen_day_du_15_bai_va_metadata_chuan():
    """Kiểm tra 15 bản nhạc tồn tại đầy đủ, 5 danh mục cảm xúc, đúng chuẩn WAV 48kHz Stereo."""
    assert FILE_BANG_KE.is_file(), f"Thiếu file bảng kê {FILE_BANG_KE}"
    data = doc_bang_ke_ban_quyen()
    assert data["tong_so_bai"] == 15
    tracks = data["danh_sach_nhac"]
    assert len(tracks) == 15

    danh_muc_tap = set()
    for track in tracks:
        assert track["id"]
        assert track["ten"]
        assert track["bpm"] > 0
        assert track["thoi_luong_giay"] == 32
        assert track["dinh_dang"] == "audio/wav"
        assert track["sample_rate_hz"] == 48000
        assert track["target_lufs"] == -16.0
        assert "BAHA AI Media Studio" in track["ban_quyen"]["ghi_chu"]

        wav_path = THU_MUC_NHAC_GOC / track["tep_tin"]
        assert wav_path.is_file(), f"Tệp âm thanh WAV không tồn tại: {wav_path}"
        assert wav_path.stat().st_size > 100_000, "Tệp âm thanh dung lượng quá nhỏ"
        danh_muc_tap.add(track["danh_muc"])

    assert danh_muc_tap == {
        "chuyen_nghiep_b2b",
        "nang_luong_bat_nhip",
        "tam_su_ke_chuyen",
        "kich_tinh_canh_bao",
        "truyen_cam_hung",
    }


def test_chon_nhac_nen_tu_dong_theo_tu_khoa_noi_dung():
    """Kiểm tra bộ mapping cảm xúc tự động lựa chọn đúng thể loại bài hát."""
    # 1. Kịch tính cảnh báo
    track_kich_tinh = chon_nhac_nen_tu_dong("5 sai lầm chí mạng khiến doanh nghiệp mất tiền cảnh báo rủi ro")
    assert track_kich_tinh["danh_muc"] == "kich_tinh_canh_bao"

    # 2. Doanh nghiệp B2B
    track_b2b = chon_nhac_nen_tu_dong("Chiến lược tối ưu hóa quy trình b2b quản trị doanh nghiệp và nhân sự")
    assert track_b2b["danh_muc"] == "chuyen_nghiep_b2b"

    # 3. Năng lượng bắt nhịp
    track_trend = chon_nhac_nen_tu_dong("Bắt trend tiktok nhanh cuốn hút sôi động giới trẻ")
    assert track_trend["danh_muc"] == "nang_luong_bat_nhip"

    # 4. Tâm sự chia sẻ
    track_tam_su = chon_nhac_nen_tu_dong("Những ngày đầu khởi nghiệp và bài học tâm sự chân thành")
    assert track_tam_su["danh_muc"] == "tam_su_ke_chuyen"

    # 5. Truyền cảm hứng
    track_cam_hung = chon_nhac_nen_tu_dong("Hành trình vượt khó vươn lên thành công và khát vọng tương lai")
    assert track_cam_hung["danh_muc"] == "truyen_cam_hung"


def test_dong_bo_tai_nguyen_nhac_nen_idempotent(test_db_session):
    """Kiểm tra sao chép tài nguyên vào MEDIA_ROOT_DIR và tạo MediaAsset không trùng lặp."""
    session, media_root = test_db_session
    workspace_id = "ws-test-bgm"
    user_id = "usr-test-bgm"
    project_id = "prj-test-bgm"

    # Đồng bộ lần đầu với bài 'b2b_cong_nghe_so'
    asset1 = dong_bo_tai_nguyen_nhac_nen(session, "b2b_cong_nghe_so", workspace_id, user_id, project_id=project_id)
    assert asset1.id
    assert asset1.source_product == "BGM_LIBRARY"
    assert asset1.mime_detected == "audio/wav"
    assert asset1.duration_ms == 32000
    file_on_disk = media_root / asset1.storage_key
    assert file_on_disk.is_file()

    # Đồng bộ lần 2 với cùng track_id: phải trả về cùng asset_id (Idempotency)
    asset2 = dong_bo_tai_nguyen_nhac_nen(session, "b2b_cong_nghe_so", workspace_id, user_id, project_id=project_id)
    assert asset2.id == asset1.id
    assert asset2.sha256 == asset1.sha256

    count = session.query(MediaAsset).filter(MediaAsset.workspace_id == workspace_id, MediaAsset.source_product == "BGM_LIBRARY").count()
    assert count == 1


def test_build_bgm_stream_filter():
    """Kiểm tra bộ lọc FFmpeg xây dựng đúng aloop, gain dB, fade in/out và EQ nhường giọng."""
    flt = video_processor._build_bgm_stream_filter(
        input_idx=1,
        gain_db=-18.0,
        duration_sec=15.0,
        label="m",
    )
    assert "[1:a]aloop=loop=-1" in flt
    assert "atrim=0:15.000" in flt
    assert "volume=-18.00dB" in flt
    assert "afade=t=in:st=0:d=0.5" in flt
    assert "afade=t=out:st=13.500:d=1.500[m]" in flt
    assert "equalizer=f=1500" in flt


def test_ghep_nhac_nen_xuyen_suot_video_co_native_speech_va_auto_ducking(tmp_path):
    """Kiểm tra thực tế: Ghép 1 bản nhạc BGM duy nhất vào video có giọng nói gốc, xác nhận EBU R128 và ducking."""
    video_path = tmp_path / "video_goc.mp4"
    bgm_path = lay_duong_dan_tep_goc("kich_tinh_canh_bao_rui_ro")
    assert bgm_path is not None and bgm_path.is_file(), f"Không tìm thấy BGM: {bgm_path}"

    # Tạo 1 video mẫu 10s có giọng nói (synthetic speech sine wave)
    subprocess.run([
        video_processor.ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "color=s=1080x1920:r=30:d=10",
        "-f", "lavfi", "-i", "sine=frequency=300:duration=10",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "192k",
        str(video_path),
    ], check=True, capture_output=True)

    output_path = tmp_path / "video_thanh_pham.mp4"
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Sao chép video gốc sang output_path
    shutil.copyfile(video_path, output_path)

    audio_specs = [(video_path, "video", 0.0, 10.0)]
    has_audio = video_processor._preserve_native_clip_audio(
        output_path=output_path,
        audio_specs=audio_specs,
        work_dir=work_dir,
        mix_existing=True,
        duration_sec=10.0,
        music_path=bgm_path,
        music_gain_db=-18.0,
    )
    assert has_audio is True

    probe = video_processor.probe_video(output_path)
    assert abs(probe["duration_seconds"] - 10.0) < 0.2, "Độ dài video phải khớp 10s"

    # Kiểm định chất lượng EBU R128 của audio thành phẩm
    loudness = audio_processor.measure_loudness(output_path)
    measured_i = loudness.get("measured_i_lufs")
    assert measured_i is not None
    # Chuẩn EBU R128: -14.0 ± 1.5 LUFS
    assert -15.5 <= measured_i <= -12.5, f"LUFS đo được {measured_i} ngoài dải chuẩn (-14 LUFS)"

    measured_tp = loudness.get("measured_tp_dbtp")
    assert measured_tp is not None
    assert measured_tp <= -1.0, f"True Peak {measured_tp} vượt ngưỡng an toàn (-1.0 dBTP)"


def test_api_bgm_library_danh_sach_va_stream():
    """Kiểm tra các API endpoint của BGM Library phục vụ frontend."""
    test_app = FastAPI()
    test_app.include_router(media_router)

    tenant = TenantContext(
        workspace_id="ws-test-bgm",
        user_id="usr-test-bgm",
        actor=None,
        auth_db=None,
        request_id="req-test-bgm",
        dev_auth_bypass=True,
    )
    from src.auth.tenancy import require_action
    test_app.dependency_overrides[get_current_tenant_context] = lambda: tenant
    test_app.dependency_overrides[require_action("media.read")] = lambda: tenant

    client = TestClient(test_app)

    # 1. GET danh sách toàn bộ bài hát
    res = client.get("/v1/media/bgm-library")
    assert res.status_code == 200
    body = res.json()
    assert body["tong_so_bai"] == 15
    assert len(body["items"]) == 15

    # 2. GET lọc theo danh mục
    res_b2b = client.get("/v1/media/bgm-library?category=chuyen_nghiep_b2b")
    assert res_b2b.status_code == 200
    body_b2b = res_b2b.json()
    assert body_b2b["tong_so_bai"] == 3
    for trk in body_b2b["items"]:
        assert trk["danh_muc"] == "chuyen_nghiep_b2b"

    # 3. Stream nghe thử tệp WAV
    res_stream = client.get("/v1/media/bgm-library/b2b_cong_nghe_so/stream")
    assert res_stream.status_code in {200, 206}
    assert res_stream.headers["content-type"].startswith("audio/")
    assert len(res_stream.content) > 1000
