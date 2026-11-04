"""Kiểm thử tính tự cấp (self-contained) của các khối HyperFrames và thư viện vendor.

Bảo đảm mọi URL ngoài (CDN, Google Fonts, @font-face từ xa) được bóc tách hoàn toàn
và thay thế bằng tệp cục bộ trong engines/vendor/.
"""
from pathlib import Path

from src.modules.tao_video_noi_dung import hf_blocks, hf_project, hf_vendor
from src.modules.tao_video_noi_dung.planner import DiagramSpec, UiScene

SAMPLE_REMOTE_HTML = """
<!doctype html>
<html>
<head>
  <!-- <script src="https://cdn.jsdelivr.net/npm/hidden@1.0.0/dist/hidden.min.js"></script> -->
  <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>
    @import url("https://fonts.googleapis.com/css2?family=Inter");
    @font-face {
      font-family: 'Inter';
      font-style: normal;
      font-weight: 500;
      src: url(https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-500-normal.woff2) format('woff2');
    }
  </style>
</head>
<body>
</body>
</html>
"""


def test_scan_external_tim_cdn_font_va_import():
    """scan_external tìm chính xác các URL từ xa ở src, @import, url; bỏ qua comment và xmlns."""
    urls = hf_vendor.scan_external(SAMPLE_REMOTE_HTML)
    assert urls == [
        "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js",
        "https://fonts.googleapis.com/css2?family=Inter",
        "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-500-normal.woff2",
    ]


def test_localize_go_thu_vien_va_font():
    """localize gỡ bỏ thư viện CDN, @import, @font-face từ xa; trả về báo cáo chuẩn."""
    clean_text, report = hf_vendor.localize(SAMPLE_REMOTE_HTML)

    assert hf_vendor.scan_external(clean_text) == []
    assert report.files == ("gsap.min.js",)
    assert "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js" in report.removed
    assert "https://fonts.googleapis.com/css2?family=Inter" in report.removed
    assert "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-500-normal.woff2" in report.removed
    assert report.unresolved == ()


def test_moi_khoi_trong_kho_khong_con_url_ngoai():
    """Mọi khối trong blocks/*.html sau khi chuẩn bị không còn chứa bất kỳ URL ngoài nào."""
    html_files = sorted(hf_blocks.BLOCKS_DIR.glob("*.html"))
    assert len(html_files) > 0
    for block_file in html_files:
        name = block_file.stem
        text = hf_blocks.prepare_block(name, "s01", 5.0)
        remaining = hf_vendor.scan_external(text)
        assert remaining == [], f"Khối {name} vẫn còn URL ngoài: {remaining}"


def test_vendor_files_ton_tai():
    """Mọi tệp khai báo trong VENDOR_LIBS đều tồn tại dưới engines/vendor/."""
    vendor_dir = Path(hf_blocks.__file__).resolve().parents[3] / "engines" / "vendor"
    assert vendor_dir.is_dir()
    for marker, filename in hf_vendor.VENDOR_LIBS.items():
        file_path = vendor_dir / filename
        assert file_path.is_file(), f"Thiếu tệp vendor: {filename}"
        assert file_path.stat().st_size > 0, f"Tệp vendor rỗng: {filename}"


def test_build_project_chep_thu_vien_can_dung(tmp_path, monkeypatch):
    """build_project sao chép tệp vendor bổ sung mà khối sử dụng và thêm thẻ script vào index.html."""
    tmp_blocks = tmp_path / "blocks"
    tmp_blocks.mkdir()

    # Tạo một khối tối giản có thẻ script CDN d3
    d3_block_html = (
        '<template>\n'
        '<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>\n'
        '<div id="chart-story" data-composition-id="chart-story" data-duration="5.0"></div>\n'
        '<script>\n'
        'window.__timelines = window.__timelines || {};\n'
        'window.__timelines["chart-story"] = gsap.timeline({ paused: true });\n'
        '</script>\n'
        '</template>\n'
    )
    (tmp_blocks / "chart-story.html").write_text(d3_block_html, encoding="utf-8")
    starfield_src = hf_blocks.BLOCKS_DIR / "starfield.html"
    if starfield_src.is_file():
        (tmp_blocks / "starfield.html").write_text(starfield_src.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(hf_blocks, "BLOCKS_DIR", tmp_blocks)

    chart_scene = UiScene(
        layout="CHART_STORY",
        diagram=DiagramSpec(
            title="Doanh thu",
            labels=["Q1", "Q2", "Q3", "Q4"],
            series=[{"name": "dt", "values": [12.0, 24.0, 36.0, 48.0]}],
            unit="%",
        ),
    )
    shot = {
        "seconds": 5.0,
        "scene": chart_scene,
        "events": {},
        "narration": "lời đọc cảnh",
        "start_seconds": 0.0,
    }

    out_dir = tmp_path / "proj"
    hf_project.build_project(out_dir, [shot], None, None, transitions=False, aspect_ratio="16:9")

    # Kiểm tra d3.min.js được sao chép vào assets/vendor/
    vendor_d3 = out_dir / "assets" / "vendor" / "d3.min.js"
    assert vendor_d3.is_file()
    assert vendor_d3.stat().st_size > 0

    # Kiểm tra index.html tham chiếu đến d3.min.js sau các script sẵn có
    index_html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert '<script src="assets/vendor/d3.min.js"></script>' in index_html
    gsap_pos = index_html.find('assets/vendor/gsap.min.js')
    custom_ease_pos = index_html.find('assets/vendor/CustomEase.min.js')
    d3_pos = index_html.find('assets/vendor/d3.min.js')
    assert -1 < gsap_pos < custom_ease_pos < d3_pos
