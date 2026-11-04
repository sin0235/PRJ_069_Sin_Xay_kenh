"""Kiểm thử các kiểu phụ đề động HyperFrames: tính tương thích ngược của karaoke,
tính toàn vẹn không URL ngoài, mốc từ khớp chính xác và render không vỡ dấu tiếng Việt.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from src.modules.tao_video_noi_dung import hf_captions, hf_project, hf_vendor, planner
from src.modules.tao_video_noi_dung.planner import DiagramSpec, UiScene

SAMPLE_WORDS_6 = [
    {"text": "Một", "start_ms": 120, "end_ms": 450},
    {"text": "nguồn", "start_ms": 450, "end_ms": 890},
    {"text": "sự", "start_ms": 890, "end_ms": 1230},
    {"text": "thật", "start_ms": 1230, "end_ms": 1670},
    {"text": "cho", "start_ms": 1670, "end_ms": 2010},
    {"text": "mọi", "start_ms": 2010, "end_ms": 2450},
]


def test_karaoke_giu_nguyen():
    """Kiểu 'karaoke' phải trả về chính xác nội dung HTML mà hf_project.captions_scene sinh ra."""
    total = 3.2
    html_from_captions, host_extra = hf_captions.caption_composition("karaoke", SAMPLE_WORDS_6, total, "16:9")
    html_from_project = hf_project.captions_scene(SAMPLE_WORDS_6, total, "16:9")
    assert html_from_captions == html_from_project
    assert host_extra == ""


def test_moi_style_hop_le_khong_con_url_ngoai():
    """Mọi kiểu phụ đề hỗ trợ ở cả 16:9 và 9:16 đều không chứa URL ngoài và có composition id là 'captions'."""
    assert len(hf_captions.CAPTION_STYLES) >= 6   # karaoke + ít nhất 5 kiểu từ registry
    for style in hf_captions.CAPTION_STYLES:
        for aspect in ("16:9", "9:16"):
            comp_html, _ = hf_captions.caption_composition(style, SAMPLE_WORDS_6, 3.5, aspect)
            external_urls = hf_vendor.scan_external(comp_html)
            assert external_urls == [], f"Kiểu {style} ({aspect}) còn URL ngoài: {external_urls}"
            assert 'data-composition-id="captions"' in comp_html
            assert 'window.__timelines["captions"]' in comp_html


def test_moc_tu_khop():
    """Mọi từ tiếng Việt và mốc thời gian bắt đầu (giây, tối đa 3 chữ số thập phân) phải khớp trong HTML."""
    total = 3.5
    for style in hf_captions.CAPTION_STYLES:
        comp_html, _ = hf_captions.caption_composition(style, SAMPLE_WORDS_6, total, "16:9")
        for word in SAMPLE_WORDS_6:
            assert word["text"] in comp_html, f"Từ '{word['text']}' không có trong HTML của kiểu {style}"
            start_s = word["start_ms"] / 1000.0
            time_3_decimals = f"{start_s:.3f}"
            time_trimmed = str(round(start_s, 3))
            assert time_3_decimals in comp_html or time_trimmed in comp_html, (
                f"Mốc thời gian {start_s}s của từ '{word['text']}' không tìm thấy trong kiểu {style}"
            )


def test_style_sai():
    """Kiểu phụ đề không tồn tại phải ném lỗi ValueError với mã lỗi chuẩn HYPERFRAMES_CAPTION_STYLE_INVALID."""
    with pytest.raises(ValueError, match="HYPERFRAMES_CAPTION_STYLE_INVALID"):
        hf_captions.caption_composition("kieu_phu_de_la", SAMPLE_WORDS_6, 3.0, "16:9")


@pytest.mark.browser
def test_dau_tieng_viet_khong_vo(tmp_path: Path):
    """Kiểm tra render trình duyệt (duy nhất một tiến trình mỗi thời điểm): snapshot hiển thị tốt và 0 lỗi check."""
    shot = {
        "seconds": 3.0,
        "scene": UiScene(layout="KINETIC_TITLE", diagram=DiagramSpec(title="Một nguồn sự thật", tag="sự thật")),
        "events": {},
        "narration": "Một nguồn sự thật cho mọi đơn hàng",
        "start_seconds": 0.0,
    }
    tested_styles = ["pill_karaoke", "highlight"]
    cli = hf_project.hyperframes_cli()
    node = hf_project._node()

    for style in tested_styles:
        proj_dir = tmp_path / f"proj_{style}"
        snap_dir = tmp_path / f"snap_{style}"
        snap_dir.mkdir(parents=True, exist_ok=True)

        hf_project.build_project(
            proj_dir,
            [shot],
            None,
            SAMPLE_WORDS_6,
            transitions=False,
            aspect_ratio="16:9",
            caption_style=style,
        )

        chk = hf_project.check_project(proj_dir)
        errors = chk.get("data", {}).get("lint", {}).get("errorCount", 0)
        assert errors == 0, f"Khối {style} có lỗi lint: {chk.get('data', {}).get('lint', {}).get('findings')}"

        snap_cmd = [node, str(cli), "snapshot", "--at", "0.6", "-o", str(snap_dir), "--no-end"]
        res = subprocess.run(snap_cmd, cwd=proj_dir, env=hf_project._env(), capture_output=True, text=True, timeout=60)
        assert res.returncode == 0, f"Lệnh snapshot thất bại cho {style}: {res.stderr or res.stdout}"

        pngs = list(snap_dir.glob("*.png"))
        assert len(pngs) == 1, f"Không tạo được ảnh chụp snapshot cho {style}"
        assert pngs[0].stat().st_size > 1000, f"Ảnh chụp snapshot của {style} quá nhỏ hoặc rỗng"
