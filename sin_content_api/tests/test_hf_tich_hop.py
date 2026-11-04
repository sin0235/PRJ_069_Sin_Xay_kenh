"""Kiểm thử tích hợp các khối hỗ trợ HyperFrames (Task W):
Chuyển cảnh luân phiên 8 kiểu, camera push-in cho cảnh UI,
lớp phủ môi trường (ambient), bảng tên người nói (lower-third),
phụ đề lùi về karaoke khi sai cấu hình và bảo toàn mặc định.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from src.modules.tao_video_noi_dung import (
    hf_captions,
    hf_layers,
    hf_project,
    hf_transitions,
)
from src.modules.tao_video_noi_dung.planner import BLOCK_LAYOUTS, DiagramSpec, UiScene

SAMPLE_WORDS = [
    {"text": "Một", "start_ms": 100, "end_ms": 400},
    {"text": "nguồn", "start_ms": 400, "end_ms": 800},
    {"text": "sự", "start_ms": 800, "end_ms": 1200},
    {"text": "thật", "start_ms": 1200, "end_ms": 1600},
]


VALID = {
    "KINETIC_TITLE": {"title": "Một nguồn sự thật", "tag": "sự thật"},
    "MARK_PHRASE": {"title": "Mỗi bộ phận giữ một con số khác nhau", "tag": "một con số khác nhau", "caption": "Không ai sai"},
    "WORD_SWAP": {"title": "Báo cáo", "steps": ["chậm", "lệch", "muộn"], "caption": "mỗi tuần"},
    "PILE_UP": {"title": "Chủ shop", "value": "16"},
    "STAT_RING": {"title": "Đơn đúng hạn", "to_value": 86, "caption": "Đơn đúng hạn"},
    "AI_RANK": {"title": "Khách hỏi AI nên mua phần mềm nào", "steps": ["Nhà cung cấp A", "Nhà cung cấp B", "Nhà cung cấp C"], "tag": "Baha", "pick": 0, "caption": "Gợi ý hàng đầu:"},
    "DRAG_TASKS": {"title": "Cần làm", "caption": "Đang xử lý", "steps": ["Báo khách đơn trễ", "Đối chiếu mã hàng", "Ghi giờ bàn giao", "Duyệt hoàn tiền"]},
    "CARD_SHIFT": {"title": "Đơn hàng", "steps": ["Nhập tay", "Tự đồng bộ"]},
    "CHART_STORY": {"title": "Doanh thu", "labels": ["Q1", "Q2", "Q3", "Q4"], "series": [{"name": "dt", "values": [12, 28, 45, 64]}], "unit": "%"},
    "CHAT_THREAD": {"title": "Hội thoại tư vấn", "steps": ["Cần hỗ trợ đơn hàng", "Dạ shop kiểm tra ngay ạ"], "values": ["khách", "ai"]},
    "NOTE_TYPING": {"title": "Ghi chú nhanh", "steps": ["Việc cần làm hôm nay", "Kiểm tra tồn kho"]},
    "CTA_CLOSE": {"title": "Thương hiệu Baha", "caption": "Đồng hành quản lý bán hàng đa kênh"},
    "NOTIFY_STACK": {"title": "Thông báo đơn mới", "steps": ["Đơn #1024 vừa đặt", "Đơn #1023 đang giao", "Đơn #1022 hoàn tất"]},
}


def _tao_canh_mau(layout: str = "KINETIC_TITLE") -> UiScene:
    """Tạo đối tượng cảnh UI hợp lệ phục vụ kiểm thử."""
    data = VALID.get(layout, {"title": "Một nguồn sự thật", "tag": "sự thật"})
    return UiScene(
        layout=layout,
        diagram=DiagramSpec(**data),
    )


def test_chuyen_canh_xoay_vong_du_8_kieu(tmp_path: Path):
    """Dự án 20 cảnh sử dụng đầy đủ 8 kiểu trong TRANSITION_KINDS và không lặp lại hai kiểu giống nhau liền kề ở ranh giới thường."""
    shots, start = [], 0.0
    for idx in range(20):
        layout = list(BLOCK_LAYOUTS)[idx % len(BLOCK_LAYOUTS)]
        shots.append({
            "seconds": 5.0,
            "scene": _tao_canh_mau(layout),
            "events": {},
            "narration": "lời thuyết minh cảnh",
            "start_seconds": start,
        })
        start += 5.0

    info = hf_project.build_project(
        tmp_path / "proj_20_shots",
        shots,
        None,
        None,
        transitions=True,
        aspect_ratio="16:9",
    )

    used_kinds = info["transition_kinds"]
    assert len(used_kinds) >= 8

    # Tất cả 8 kiểu trong TRANSITION_KINDS đều được dùng ít nhất một lần
    for kind in hf_transitions.TRANSITION_KINDS:
        assert kind in used_kinds, f"Kiểu chuyển cảnh {kind} chưa được dùng"

    # Không bao giờ dùng cùng một kiểu ở hai ranh giới liền kề
    for idx in range(len(used_kinds) - 1):
        assert used_kinds[idx] != used_kinds[idx + 1], (
            f"Trùng kiểu chuyển cảnh liền kề tại vị trí {idx}: {used_kinds[idx]}"
        )


def test_camera_bat_tat_bang_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Cờ CONTENT_VIDEO_HF_CAMERA bật/tắt: flag 0 không sinh lệnh camera, flag 1 sinh lệnh push_in cho mỗi cảnh UI."""
    shots, start = [], 0.0
    for idx in range(3):
        shots.append({
            "seconds": 4.0,
            "scene": _tao_canh_mau("KINETIC_TITLE"),
            "events": {},
            "narration": "lời đọc",
            "start_seconds": start,
        })
        start += 4.0

    # 1. Tắt bằng cờ 0
    monkeypatch.setenv("CONTENT_VIDEO_HF_CAMERA", "0")
    info_off = hf_project.build_project(tmp_path / "p_cam_off", shots, None, None)
    assert info_off["camera_scenes"] == 0
    index_off = (tmp_path / "p_cam_off" / "index.html").read_text(encoding="utf-8")
    assert "scale: 1.06" not in index_off

    # 2. Bật bằng cờ 1
    monkeypatch.setenv("CONTENT_VIDEO_HF_CAMERA", "1")
    info_on = hf_project.build_project(tmp_path / "p_cam_on", shots, None, None)
    assert info_on["camera_scenes"] == 3
    index_on = (tmp_path / "p_cam_on" / "index.html").read_text(encoding="utf-8")
    for cid in ("s01", "s02", "s03"):
        assert f'tl.fromTo("#{cid}", {{ scale: 1, transformOrigin: "50% 50%" }}' in index_on


def test_ambient_bat_tat_va_khong_che_canh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Cờ CONTENT_VIDEO_HF_AMBIENT bật/tắt: flag 0 ra 0 lớp, mặc định (không đặt cờ) 0 lớp, cờ 1 thì >= 1 lớp có opacity <= 0.35 và pointer-events:none."""
    shots = [{
        "seconds": 5.0,
        "scene": _tao_canh_mau("KINETIC_TITLE"),
        "events": {},
        "narration": "lời đọc",
        "start_seconds": 0.0,
    }]

    # 1. Tắt bằng cờ 0
    monkeypatch.setenv("CONTENT_VIDEO_HF_AMBIENT", "0")
    info_off = hf_project.build_project(tmp_path / "p_amb_off", shots, None, None)
    assert info_off["ambient_layers"] == 0
    assert not list((tmp_path / "p_amb_off" / "compositions").glob("amb_*.html"))

    # 2. Mặc định (không đặt cờ): tắt
    monkeypatch.delenv("CONTENT_VIDEO_HF_AMBIENT", raising=False)
    info_none = hf_project.build_project(tmp_path / "p_amb_none", shots, None, None)
    assert info_none["ambient_layers"] == 0

    # 3. Bật bằng cờ 1
    monkeypatch.setenv("CONTENT_VIDEO_HF_AMBIENT", "1")
    info_def = hf_project.build_project(tmp_path / "p_amb_def", shots, None, None)
    assert info_def["ambient_layers"] >= 1
    index_def = (tmp_path / "p_amb_def" / "index.html").read_text(encoding="utf-8")

    # Kiểm tra các thẻ host của ambient
    amb_hosts = re.findall(r'<div id="amb_\d+".*?></div>', index_def)
    assert len(amb_hosts) == info_def["ambient_layers"]
    for host in amb_hosts:
        assert "pointer-events:none" in host
        m = re.search(r'opacity:([0-9.]+)', host)
        assert m is not None, f"Không tìm thấy opacity trong {host}"
        opacity_val = float(m.group(1))
        assert opacity_val <= 0.35, f"Opacity {opacity_val} vượt ngưỡng an toàn 0.35"


def test_lower_third_chi_khi_co_ten(tmp_path: Path):
    """Bảng tên chỉ xuất hiện khi shot có khóa 'name', không có 'name' thì không tạo host hay composition."""
    # 1. Không có name
    shots_no_name = [{
        "seconds": 5.0,
        "scene": _tao_canh_mau("KINETIC_TITLE"),
        "events": {},
        "narration": "lời đọc",
        "start_seconds": 0.0,
    }]
    hf_project.build_project(tmp_path / "p_no_lt", shots_no_name, None, None)
    index_no_lt = (tmp_path / "p_no_lt" / "index.html").read_text(encoding="utf-8")
    assert 'id="lt_' not in index_no_lt
    assert not list((tmp_path / "p_no_lt" / "compositions").glob("lt_*.html"))

    # 2. Có name
    shots_has_name = [{
        "seconds": 5.0,
        "scene": _tao_canh_mau("KINETIC_TITLE"),
        "events": {},
        "narration": "lời đọc",
        "start_seconds": 0.0,
        "name": "TS. Nguyễn Văn An",
        "role": "Chuyên gia Vận hành",
    }]
    hf_project.build_project(tmp_path / "p_has_lt", shots_has_name, None, None)
    index_has_lt = (tmp_path / "p_has_lt" / "index.html").read_text(encoding="utf-8")
    assert 'id="lt_s01"' in index_has_lt
    assert (tmp_path / "p_has_lt" / "compositions" / "lt_s01.html").is_file()


def test_caption_style_env_sai_thi_lui_ve_karaoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Khi biến môi trường CONTENT_VIDEO_HF_CAPTION_STYLE chứa giá trị lạ, hàm lùi về karaoke và cảnh báo thay vì ném lỗi."""
    monkeypatch.setenv("CONTENT_VIDEO_HF_CAPTION_STYLE", "kieu_la_khong_ton_tai_123")
    shots = [{
        "seconds": 4.0,
        "scene": _tao_canh_mau("KINETIC_TITLE"),
        "events": {},
        "narration": "lời đọc",
        "start_seconds": 0.0,
    }]

    with pytest.warns(UserWarning, match="kieu_la_khong_ton_tai_123"):
        hf_project.build_project(
            tmp_path / "p_cap_fallback",
            shots,
            None,
            SAMPLE_WORDS,
            caption_style=None,
        )

    captions_file = tmp_path / "p_cap_fallback" / "compositions" / "captions.html"
    assert captions_file.is_file()
    cap_text = captions_file.read_text(encoding="utf-8")
    assert "cap-g0" in cap_text
    assert "#FFD54A" in cap_text


def test_mac_dinh_van_la_karaoke_va_collage(tmp_path: Path):
    """Dự án dựng mặc định vẫn sinh ra chuyển cảnh mảnh giấy xé tr01 và phụ đề karaoke nguyên bản."""
    shots = [
        {
            "seconds": 4.0,
            "scene": _tao_canh_mau("KINETIC_TITLE"),
            "events": {},
            "narration": "lời một",
            "start_seconds": 0.0,
        },
        {
            "seconds": 4.0,
            "scene": _tao_canh_mau("MARK_PHRASE"),
            "events": {},
            "narration": "lời hai",
            "start_seconds": 4.0,
        },
    ]

    info = hf_project.build_project(
        tmp_path / "p_default",
        shots,
        None,
        SAMPLE_WORDS,
        aspect_ratio="16:9",
    )

    index_html = (tmp_path / "p_default" / "index.html").read_text(encoding="utf-8")
    assert 'id="tr01"' in index_html
    assert (tmp_path / "p_default" / "compositions" / "tr01.html").is_file()
    assert info["collage_transitions"] == 1

    captions_file = tmp_path / "p_default" / "compositions" / "captions.html"
    assert captions_file.is_file()
    assert "#FFD54A" in captions_file.read_text(encoding="utf-8")


@pytest.mark.browser
def test_browser_kiem_tra_va_snapshot(tmp_path: Path):
    """Kiểm tra render trình duyệt (duy nhất 1 Chrome render): dự án 6 cảnh 16:9 với mọi cờ bật đạt 0 lỗi check và tạo ảnh snapshot."""
    shots, start = [], 0.0
    for idx in range(6):
        layout = list(BLOCK_LAYOUTS)[idx % len(BLOCK_LAYOUTS)]
        shots.append({
            "seconds": 3.0,
            "scene": _tao_canh_mau(layout),
            "events": {},
            "narration": "lời đọc cảnh kiểm thử trình duyệt",
            "start_seconds": start,
            "name": "Diễn giả Baha" if idx == 0 else None,
        })
        start += 3.0

    proj_dir = tmp_path / "p_browser_6scenes"
    hf_project.build_project(
        proj_dir,
        shots,
        None,
        SAMPLE_WORDS,
        transitions=True,
        aspect_ratio="16:9",
    )

    # 1. Kiểm tra kiểm định hyperframes check --json
    chk = hf_project.check_project(proj_dir)
    errors = chk.get("data", {}).get("lint", {}).get("errorCount", 0)
    assert errors == 0, f"hyperframes check có lỗi lint: {chk.get('data', {}).get('lint', {}).get('findings')}"

    # 2. Chụp snapshot tại hai mốc thời gian
    snap_out = tmp_path / "snaps_browser"
    snap_out.mkdir(parents=True, exist_ok=True)
    cli = hf_project.hyperframes_cli()
    node = hf_project._node()

    with hf_project._RENDER_LOCK:
        cmd = [node, str(cli), "snapshot", "--at", "1.5,4.5", "-o", str(snap_out), "--no-end"]
        res = subprocess.run(cmd, cwd=proj_dir, env=hf_project._env(), capture_output=True, text=True, timeout=120)
        assert res.returncode == 0, f"Lệnh snapshot thất bại: {res.stderr or res.stdout}"

    pngs = sorted(snap_out.glob("*.png"))
    assert len(pngs) >= 2, f"Không đủ ảnh snapshot: {len(pngs)}"
    for png in pngs:
        assert png.stat().st_size > 1000, f"Ảnh snapshot quá nhỏ hoặc rỗng: {png}"
