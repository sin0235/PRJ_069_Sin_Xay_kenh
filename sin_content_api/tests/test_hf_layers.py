"""Kiểm thử các hàm quản lý lớp phủ (hf_layers) cho HyperFrames:
Đặc tả OverlaySpec, dựng host div, tính ổn định theo seed của lớp môi trường,
không bịa tên diễn giả, không chứa URL ngoài, lớp phủ môi trường trong suốt,
và bảng tên lower third không che khuất vùng chữ chính (top 55%).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest
from PIL import Image

from src.modules.tao_video_noi_dung import hf_blocks, hf_layers, hf_vendor
from src.modules.tao_video_noi_dung.hf_layers import (
    KEPT_LT_BLOCKS,
    LT_SAMPLE_NAME,
    LT_SAMPLE_ROLE,
    OverlaySpec,
    ambient_for_video,
    lower_third_for_shot,
    overlay_host,
)
from src.modules.tao_video_noi_dung.hf_project import (
    VIETSUB_FONT_PATH,
    hyperframes_cli,
)
from src.modules.tao_video_noi_dung.render_engines import _node, engines_dir

# Khóa tránh chạy đồng thời nhiều tiến trình Chrome render trên máy 8 GB RAM
_CHROME_LOCK = threading.Lock()


def _setup_test_project(proj_dir: Path, compositions: dict[str, str], index_html: str) -> None:
    """Tạo cấu trúc dự án HyperFrames tối thiểu phục vụ kiểm thử snapshot."""
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "hyperframes.json").write_text(
        json.dumps({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}),
        encoding="utf-8",
    )
    (proj_dir / "package.json").write_text(
        json.dumps({"name": "test-overlay", "private": True, "type": "module"}),
        encoding="utf-8",
    )

    comp_dir = proj_dir / "compositions"
    comp_dir.mkdir(parents=True, exist_ok=True)
    for cid, html_content in compositions.items():
        (comp_dir / f"{cid}.html").write_text(html_content, encoding="utf-8")

    vendor_dir = proj_dir / "assets" / "vendor"
    fonts_dir = proj_dir / "assets" / "fonts"
    vendor_dir.mkdir(parents=True, exist_ok=True)
    fonts_dir.mkdir(parents=True, exist_ok=True)

    eng_vendor = engines_dir() / "vendor"
    shutil.copy(eng_vendor / "gsap.min.js", vendor_dir / "gsap.min.js")
    shutil.copy(eng_vendor / "CustomEase.min.js", vendor_dir / "CustomEase.min.js")
    shutil.copy(VIETSUB_FONT_PATH, fonts_dir / "be_vietnam_pro_semibold.ttf")

    (proj_dir / "index.html").write_text(index_html, encoding="utf-8")


def test_ambient_on_dinh_theo_seed():
    """Cùng seed trả về danh sách specs giống hệt nhau; khác seed có thể khác; tất cả opacity <= 0.35 và duration bằng total."""
    seed_a = "video_gioi_thieu_baha_2026"
    seed_b = "video_huong_dan_nguoi_dung"

    specs_a1 = ambient_for_video(seed_a, 12.5, "16:9")
    specs_a2 = ambient_for_video(seed_a, 12.5, "16:9")
    assert specs_a1 == specs_a2, "Cùng seed phải cho ra kết quả đặc tả lớp phủ giống hệt nhau"

    assert len(specs_a1) >= 1
    for spec in specs_a1:
        assert isinstance(spec, OverlaySpec)
        assert spec.start == 0.0
        assert spec.duration == 12.5, "Thời lượng lớp môi trường phải bằng tổng độ dài video"
        assert spec.opacity <= 0.35, f"Độ mờ đục lớp phủ quá cao ({spec.opacity} > 0.35), có nguy cơ che cảnh"
        assert spec.literals == {}

    # Kiểm tra tính đa dạng trên tập hạt giống khác nhau
    results = [ambient_for_video(f"seed_{i}", 10.0, "16:9") for i in range(10)]
    assert any(r != results[0] for r in results[1:]), "Các seed khác nhau phải có khả năng sinh biến thể khác nhau"


def test_lower_third_khong_bia_ten():
    """Không có tên -> None; có tên -> spec chứa tên trong literals và không còn chuỗi mẫu cũ trong composition html; vắng role -> thay thế/xóa chuỗi mẫu role."""
    # 1. Không có tên hoặc tên rỗng -> bắt buộc trả về None (không bao giờ tự bịa tên)
    assert lower_third_for_shot({}) is None
    assert lower_third_for_shot({"role": "Diễn giả"}) is None
    assert lower_third_for_shot({"name": "", "role": "Chuyên gia"}) is None
    assert lower_third_for_shot({"name": "   ", "seconds": 5.0}) is None

    # 2. Có tên và role đầy đủ
    shot_du = {
        "name": "TS. Nguyễn Văn An",
        "role": "Giám đốc Vận hành · Công ty Baha",
        "start_seconds": 2.0,
        "seconds": 6.0,
    }
    spec_du = lower_third_for_shot(shot_du)
    assert spec_du is not None
    assert isinstance(spec_du, OverlaySpec)
    assert spec_du.block in KEPT_LT_BLOCKS
    assert spec_du.start == 2.4  # start + 0.4
    assert spec_du.duration == 4.0  # min(4.0, 6.0 - 0.8)
    assert spec_du.literals[LT_SAMPLE_NAME] == "TS. Nguyễn Văn An"
    assert spec_du.literals[LT_SAMPLE_ROLE] == "Giám đốc Vận hành · Công ty Baha"

    comp_html, host_html = overlay_host(spec_du, "lt_test_01", "16:9")
    assert LT_SAMPLE_NAME not in comp_html, "Chuỗi tên mẫu ban đầu chưa được thay thế trong composition HTML"
    assert LT_SAMPLE_ROLE not in comp_html, "Chuỗi chức vụ mẫu ban đầu chưa được thay thế trong composition HTML"
    assert "TS. Nguyễn Văn An" in comp_html
    assert "Giám đốc Vận hành · Công ty Baha" in comp_html

    # 3. Có tên nhưng vắng role
    shot_khong_role = {
        "name": "Trần Thị Mai",
        "start_seconds": 1.0,
        "seconds": 4.5,
    }
    spec_khong_role = lower_third_for_shot(shot_khong_role)
    assert spec_khong_role is not None
    assert spec_khong_role.start == 1.4
    assert spec_khong_role.duration == pytest.approx(3.7)  # 4.5 - 0.8
    assert LT_SAMPLE_NAME in spec_khong_role.literals
    assert LT_SAMPLE_ROLE in spec_khong_role.literals
    assert spec_khong_role.literals[LT_SAMPLE_ROLE] == ""

    comp_kr_html, _ = overlay_host(spec_khong_role, "lt_test_02", "16:9")
    assert LT_SAMPLE_NAME not in comp_kr_html
    assert LT_SAMPLE_ROLE not in comp_kr_html
    assert "Trần Thị Mai" in comp_kr_html


def test_overlay_host_khong_url_ngoai():
    """hf_vendor.scan_external của composition html rỗng; host html chứa pointer-events:none và data-start/data-duration."""
    shot = {"name": "Lê Hoàng Long", "role": "Kỹ sư Trưởng", "start_seconds": 0.5, "seconds": 5.0}
    lt_spec = lower_third_for_shot(shot)
    assert lt_spec is not None

    for aspect in ("16:9", "9:16"):
        comp_html, host_html = overlay_host(lt_spec, "ov_host_01", aspect)
        remaining_urls = hf_vendor.scan_external(comp_html)
        assert remaining_urls == [], f"Phát hiện URL ngoài trong composition: {remaining_urls}"

        assert "pointer-events:none" in host_html
        assert 'data-start="0.900"' in host_html
        assert 'data-duration="4.000"' in host_html
        assert 'data-composition-id="ov_host_01"' in host_html

        expected_w, expected_h = (1080, 1920) if aspect == "9:16" else (1920, 1080)
        assert f'data-width="{expected_w}"' in host_html
        assert f'data-height="{expected_h}"' in host_html

    # Kiểm tra tương tự đối với các khối môi trường
    amb_specs = ambient_for_video("test_clean_urls", 8.0, "16:9")
    for idx, amb_spec in enumerate(amb_specs):
        amb_comp, amb_host = overlay_host(amb_spec, f"amb_host_{idx}", "16:9")
        assert hf_vendor.scan_external(amb_comp) == []
        assert "pointer-events:none" in amb_host
        assert 'data-start="0.000"' in amb_host
        assert 'data-duration="8.000"' in amb_host


@pytest.mark.browser
def test_lop_phu_trong_suot(tmp_path: Path):
    """MỘT lần render Chrome: dựng dự án với nền #bg magenta (#ff00ff) và các host overlay môi trường chồng lên; pixel tâm (960, 540) vẫn nằm trong khoảng 60 mỗi kênh màu của magenta."""
    ambient_blocks = ["starfield", "grain-field", "organic-light-leak-overlay"]
    proj_dir = tmp_path / "proj_magenta"
    seg_duration = 2.0
    total_duration = seg_duration * len(ambient_blocks)

    compositions = {}
    hosts_html = []
    snap_times = []

    for idx, block_name in enumerate(ambient_blocks):
        cid = f"amb_{idx:02d}"
        t_start = idx * seg_duration
        spec = OverlaySpec(
            block=block_name,
            start=t_start,
            duration=seg_duration,
            variables={"density": "sparse"} if block_name == "starfield" else {"density": "fine"},
            literals={},
            z_index=10 + idx,
            opacity=0.20,
        )
        comp_html, host_html = overlay_host(spec, cid, "16:9")
        compositions[cid] = comp_html
        hosts_html.append(host_html)
        snap_times.append(f"{t_start + seg_duration / 2:.3f}")

    index_html = (
        '<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=1920, height=1080">\n'
        '<script src="assets/vendor/gsap.min.js"></script>\n<script src="assets/vendor/CustomEase.min.js"></script>\n'
        '<style>html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#000}'
        '#bg{position:absolute;inset:0;background:#ff00ff;z-index:0}</style>\n'
        '</head>\n<body>\n'
        f'<div id="root" data-composition-id="main" data-start="0" data-duration="{total_duration:.3f}" data-width="1920" data-height="1080">\n'
        f'<div id="bg"></div>\n{"".join(hosts_html)}</div>\n'
        '<script>\nwindow.__timelines = window.__timelines || {};\n'
        'const tl = gsap.timeline({ paused: true });\nwindow.__timelines["main"] = tl;\n'
        '</script>\n</body>\n</html>\n'
    )

    _setup_test_project(proj_dir, compositions, index_html)

    snap_out = tmp_path / "magenta_snaps"
    snap_out.mkdir(parents=True, exist_ok=True)

    cli = hyperframes_cli()
    node_bin = _node()
    snap_cmd = [
        node_bin,
        str(cli),
        "snapshot",
        "--at",
        ",".join(snap_times),
        "--no-end",
        "-o",
        str(snap_out),
    ]

    with _CHROME_LOCK:
        proc = subprocess.run(snap_cmd, cwd=proj_dir, capture_output=True, text=True, timeout=180)
        assert proc.returncode == 0, f"hyperframes snapshot thất bại: {proc.stderr}"

    frames = sorted(snap_out.glob("frame-*.png"))
    assert len(frames) == len(ambient_blocks), f"Không đủ số khung hình chụp được: {len(frames)}"

    # Kiểm tra pixel tại tọa độ giữa màn hình (960, 540)
    for block_name, frame_file in zip(ambient_blocks, frames):
        with Image.open(frame_file) as im:
            rgb = im.convert("RGB")
            pixel = rgb.getpixel((960, 540))
            r_diff = abs(pixel[0] - 255)
            g_diff = abs(pixel[1] - 0)
            b_diff = abs(pixel[2] - 255)
            assert r_diff <= 60, f"Khối {block_name} kênh Red ({pixel[0]}) lệch quá 60 so với 255"
            assert g_diff <= 60, f"Khối {block_name} kênh Green ({pixel[1]}) lệch quá 60 so với 0"
            assert b_diff <= 60, f"Khối {block_name} kênh Blue ({pixel[2]}) lệch quá 60 so với 255"


@pytest.mark.browser
@pytest.mark.parametrize("block_name", KEPT_LT_BLOCKS)
def test_lower_third_khong_che_vung_chu_chinh(tmp_path: Path, block_name: str):
    """MỘT lần render cho mỗi khối lower third: chụp giữa thời gian hiển thị và kiểm tra 55% phần trên khung hình (y < 600) không đổi so với khung hình không có overlay."""
    proj_dir = tmp_path / f"proj_{block_name}"
    shot = {
        "name": "TS. NGUYỄN VĂN AN",
        "role": "CHUYÊN GIA DỰNG VIDEO · BAHA",
        "start_seconds": 0.0,
        "seconds": 4.0,
    }
    # Khối bắt đầu hiển thị tại 0.4s và kết thúc tại 3.6s
    spec = OverlaySpec(
        block=block_name,
        start=0.4,
        duration=3.2,
        variables={},
        literals={
            LT_SAMPLE_NAME: shot["name"],
            LT_SAMPLE_ROLE: shot["role"],
        },
        z_index=50,
        opacity=1.0,
    )
    cid = f"lt_{block_name.replace('-', '_')}"
    comp_html, host_html = overlay_host(spec, cid, "16:9")

    # Nền chuẩn gradient navy
    index_html = (
        '<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=1920, height=1080">\n'
        '<script src="assets/vendor/gsap.min.js"></script>\n<script src="assets/vendor/CustomEase.min.js"></script>\n'
        '<style>@font-face{font-family:"Viet";src:url(assets/fonts/be_vietnam_pro_semibold.ttf);font-weight:100 900}'
        'html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#0a1c2b}'
        '#bg{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,#12324a 0%,#0a1c2b 62%,#06131d 100%)}</style>\n'
        '</head>\n<body>\n'
        '<div id="root" data-composition-id="main" data-start="0" data-duration="4.000" data-width="1920" data-height="1080">\n'
        f'<div id="bg"></div>\n{host_html}</div>\n'
        '<script>\nwindow.__timelines = window.__timelines || {};\n'
        'const tl = gsap.timeline({ paused: true });\nwindow.__timelines["main"] = tl;\n'
        '</script>\n</body>\n</html>\n'
    )

    _setup_test_project(proj_dir, {cid: comp_html}, index_html)

    snap_out = tmp_path / f"snaps_{block_name}"
    snap_out.mkdir(parents=True, exist_ok=True)

    cli = hyperframes_cli()
    node_bin = _node()
    # Chụp t=0.1s (chưa có lower third, nền thuần) và t=2.0s (giữa thời gian hiển thị lower third)
    snap_cmd = [
        node_bin,
        str(cli),
        "snapshot",
        "--at",
        "0.100,2.000",
        "--no-end",
        "-o",
        str(snap_out),
    ]

    with _CHROME_LOCK:
        proc = subprocess.run(snap_cmd, cwd=proj_dir, capture_output=True, text=True, timeout=180)
        assert proc.returncode == 0, f"hyperframes snapshot thất bại cho {block_name}: {proc.stderr}"

    frames = sorted(snap_out.glob("frame-*.png"))
    assert len(frames) == 2, f"Cần đúng 2 khung hình để so sánh: {len(frames)}"

    with Image.open(frames[0]) as im_base, Image.open(frames[1]) as im_overlay:
        rgb_base = im_base.convert("RGB")
        rgb_overlay = im_overlay.convert("RGB")

        # Kiểm tra vùng 55% trên khung hình (y < 600) không đổi
        max_diff = 0
        for y in range(0, 600, 15):
            for x in range(0, 1920, 30):
                p_base = rgb_base.getpixel((x, y))
                p_overlay = rgb_overlay.getpixel((x, y))
                diff = max(abs(a - b) for a, b in zip(p_base, p_overlay))
                if diff > max_diff:
                    max_diff = diff

        assert max_diff <= 2, f"Khối {block_name} làm thay đổi vùng nội dung chính (y < 600), độ lệch tối đa: {max_diff}"
