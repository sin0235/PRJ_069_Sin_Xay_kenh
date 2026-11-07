"""Bộ kiểm thử đơn vị & kiểm định tích hợp cho hệ thống Phụ đề Đa sắc - Đa tầng (Kinetic Multi-Color Captions).

Tuân thủ BAHA_PROJECT_OS_STANDARD_TEMPLATE_V2:
- Ground Truth > Self-report: Kiểm thử thực tế qua pytest và FFmpeg libass.
- 100% Tiếng Việt có dấu chuẩn ngữ pháp.
- Tuyệt đối không dùng emoji (No Emoji - SVG Only).
"""
import subprocess
from pathlib import Path

import pytest

from src.modules.media_studio.ass_captions import build_karaoke_ass
from src.modules.media_studio.phan_tich_phu_de_da_tang import (
    COLOR_ASS_MAP,
    COLOR_HEX_MAP,
    phan_loai_tu_khoa,
    phan_tich_cum_phu_de,
)
from src.modules.tao_video_noi_dung.hf_captions import caption_composition, karaoke_composition
from src.schemas.contracts import KaraokeCaptionSettings


class TestPhanTichNguNghiaTiengViet:
    def test_nhan_dien_con_so_va_kpi(self):
        assert phan_loai_tu_khoa("3") == "METRIC_GOLD"
        assert phan_loai_tu_khoa("100.000") == "METRIC_GOLD"
        assert phan_loai_tu_khoa("85%") == "METRIC_GOLD"
        assert phan_loai_tu_khoa("30 ngày") == "METRIC_GOLD"
        assert phan_loai_tu_khoa("3 lần") == "METRIC_GOLD"
        assert phan_loai_tu_khoa("500k") == "METRIC_GOLD"

    def test_nhan_dien_canh_bao_va_diem_dau(self):
        assert phan_loai_tu_khoa("sai lầm") == "PAIN_CORAL"
        assert phan_loai_tu_khoa("chết người") == "PAIN_CORAL"
        assert phan_loai_tu_khoa("đừng") == "PAIN_CORAL"
        assert phan_loai_tu_khoa("nguy hiểm") == "PAIN_CORAL"
        assert phan_loai_tu_khoa("không tốn") == "PAIN_CORAL"

    def test_nhan_dien_giai_phap_va_tang_truong(self):
        assert phan_loai_tu_khoa("bí quyết") == "GROWTH_EMERALD"
        assert phan_loai_tu_khoa("thành công") == "GROWTH_EMERALD"
        assert phan_loai_tu_khoa("đột phá") == "GROWTH_EMERALD"
        assert phan_loai_tu_khoa("giữ chân") == "GROWTH_EMERALD"

    def test_nhan_dien_thuong_hieu_va_chu_de(self):
        assert phan_loai_tu_khoa("xây kênh") == "BRAND_CYAN"
        assert phan_loai_tu_khoa("TikTok") == "BRAND_CYAN"
        assert phan_loai_tu_khoa("quảng cáo") == "BRAND_CYAN"

    def test_tu_chuc_nang_thong_thuong(self):
        assert phan_loai_tu_khoa("chỉ cần") == "NORMAL_WHITE"
        assert phan_loai_tu_khoa("thay đổi") == "NORMAL_WHITE"
        assert phan_loai_tu_khoa("của bạn") == "NORMAL_WHITE"


class TestPhanTangBoCuc:
    def test_preset_da_sac_phan_tang_chia_dong_va_co_chu(self):
        words = [
            {"text": "Chỉ", "start_ms": 0, "end_ms": 200},
            {"text": "cần", "start_ms": 200, "end_ms": 400},
            {"text": "thay", "start_ms": 400, "end_ms": 600},
            {"text": "đổi", "start_ms": 600, "end_ms": 800},
            {"text": "3", "start_ms": 800, "end_ms": 1100},
            {"text": "giây", "start_ms": 1100, "end_ms": 1400},
            {"text": "đầu", "start_ms": 1400, "end_ms": 1700},
            {"text": "tiên", "start_ms": 1700, "end_ms": 2000},
        ]
        cum = phan_tich_cum_phu_de(words, 0, 2000, preset="da_sac_phan_tang", base_font_size=84)
        assert len(cum.words) == 8
        lines = {w.line_index for w in cum.words}
        assert len(lines) >= 2  # Phải chia tối thiểu 2-3 tầng
        punch_words = [w for w in cum.words if w.is_uppercase]
        assert len(punch_words) > 0  # Có từ khóa được in hoa
        # Cỡ chữ dòng đinh phải lớn hơn dòng dẫn
        assert max(w.font_size for w in cum.words) > min(w.font_size for w in cum.words)

    def test_preset_hop_mau_gan_pill(self):
        words = [
            {"text": "Đừng", "start_ms": 0, "end_ms": 250},
            {"text": "mắc", "start_ms": 250, "end_ms": 500},
            {"text": "sai lầm", "start_ms": 500, "end_ms": 900},
            {"text": "chết người", "start_ms": 900, "end_ms": 1400},
        ]
        cum = phan_tich_cum_phu_de(words, 0, 1400, preset="hop_mau_dong_chinh", base_font_size=84)
        pill_words = [w for w in cum.words if w.is_pill]
        assert len(pill_words) > 0


class TestSinhFileASS:
    def test_build_karaoke_ass_da_sac_hop_le(self):
        captions = [
            {
                "text": "Chỉ cần thay đổi đúng 3 GIÂY ĐẦU TIÊN",
                "start_ms": 100,
                "duration_ms": 2400,
                "words": [
                    {"text": "Chỉ", "start_ms": 100, "end_ms": 350},
                    {"text": "cần", "start_ms": 360, "end_ms": 600},
                    {"text": "thay", "start_ms": 610, "end_ms": 850},
                    {"text": "đổi", "start_ms": 860, "end_ms": 1100},
                    {"text": "đúng", "start_ms": 1110, "end_ms": 1350},
                    {"text": "3", "start_ms": 1360, "end_ms": 1650},
                    {"text": "giây", "start_ms": 1660, "end_ms": 1950},
                    {"text": "đầu", "start_ms": 1960, "end_ms": 2200},
                    {"text": "tiên", "start_ms": 2210, "end_ms": 2500},
                ],
            }
        ]
        ass_script = build_karaoke_ass(
            captions,
            width=1080,
            height=1920,
            settings={"preset": "da_sac_phan_tang", "font_size": 84, "word_pop": True},
        )
        assert "[Script Info]" in ass_script
        assert "Style: Karaoke" in ass_script
        assert "Dialogue: 0," in ass_script
        # Phải chứa thẻ đổi cỡ chữ \fs và thẻ màu \1c
        assert r"\fs" in ass_script
        assert r"\1c" in ass_script
        assert r"\kf" in ass_script
        assert r"\N" in ass_script  # Ngắt dòng đa tầng

    def test_tuong_thich_nguoc_preset_cu(self):
        captions = [
            {
                "text": "Xin chào các bạn",
                "start_ms": 0,
                "duration_ms": 1500,
                "words": [
                    {"text": "Xin", "start_ms": 0, "end_ms": 400},
                    {"text": "chào", "start_ms": 450, "end_ms": 900},
                    {"text": "các", "start_ms": 950, "end_ms": 1200},
                    {"text": "bạn", "start_ms": 1250, "end_ms": 1500},
                ],
            }
        ]
        ass_script = build_karaoke_ass(
            captions,
            width=1080,
            height=1920,
            settings={"preset": "bat_nhip", "font_size": 84, "accent_color": "champagne"},
        )
        assert "Style: Karaoke" in ass_script
        assert r"\kf" in ass_script


class TestHyperFramesIntegration:
    def test_karaoke_composition_da_sac(self):
        words = [
            {"text": "Bí quyết", "start_ms": 100, "end_ms": 500},
            {"text": "tăng", "start_ms": 510, "end_ms": 850},
            {"text": "3 lần", "start_ms": 860, "end_ms": 1300},
            {"text": "doanh thu", "start_ms": 1310, "end_ms": 1800},
        ]
        html_out = karaoke_composition(words, total=2.0, aspect_ratio="9:16")
        assert "data-composition-id=\"captions\"" in html_out
        assert "#FFD54A" in html_out or "#34D399" in html_out
        assert "scale:" in html_out

    def test_caption_composition_tu_khoa_ngu_nghia(self, monkeypatch):
        words = [
            {"text": "Đừng", "start_ms": 100, "end_ms": 400},
            {"text": "mắc", "start_ms": 410, "end_ms": 700},
            {"text": "sai lầm", "start_ms": 710, "end_ms": 1100},
            {"text": "này", "start_ms": 1110, "end_ms": 1400},
        ]
        # Thử nghiệm với karaoke composition
        html_karaoke, _ = caption_composition("karaoke", words, total=1.5, aspect="9:16")
        assert "data-composition-id=\"captions\"" in html_karaoke

        # Thử nghiệm khối mẫu có KEYWORDS
        sample_block = """
        <div id="caption-highlight">
          <script>
            var WORDS = [];
            var KEYWORDS = new Set([0]);
            var DURATION = 5.0;
          </script>
        </div>
        """
        class MockPath:
            def is_file(self):
                return True
            def read_text(self, encoding="utf-8"):
                return sample_block

        monkeypatch.setattr("src.modules.tao_video_noi_dung.hf_captions._block_path", lambda s: MockPath())
        html_out, _ = caption_composition("highlight", words, total=1.5, aspect="9:16")
        assert "KEYWORDS = new Set(" in html_out


class TestRenderThucTeFFmpeg:
    def test_ffmpeg_libass_render_khong_loi(self, tmp_path):
        ass_path = tmp_path / "sub_test.ass"
        out_png = tmp_path / "out_frame.png"
        captions = [
            {
                "text": "Bí quyết tăng 100k follow chỉ sau 30 ngày",
                "start_ms": 0,
                "duration_ms": 3000,
                "words": [
                    {"text": "Bí", "start_ms": 0, "end_ms": 250},
                    {"text": "quyết", "start_ms": 260, "end_ms": 550},
                    {"text": "tăng", "start_ms": 560, "end_ms": 850},
                    {"text": "100k", "start_ms": 860, "end_ms": 1250},
                    {"text": "follow", "start_ms": 1260, "end_ms": 1650},
                    {"text": "chỉ", "start_ms": 1660, "end_ms": 1950},
                    {"text": "sau", "start_ms": 1960, "end_ms": 2250},
                    {"text": "30", "start_ms": 2260, "end_ms": 2600},
                    {"text": "ngày", "start_ms": 2610, "end_ms": 2980},
                ],
            }
        ]
        ass_content = build_karaoke_ass(
            captions,
            width=1080,
            height=1920,
            settings={"preset": "da_sac_phan_tang", "font_size": 84, "word_pop": True},
        )
        ass_path.write_text(ass_content, encoding="utf-8-sig")
        ass_esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=#0B1120:s=1080x1920:d=1",
            "-vf",
            f"subtitles='{ass_esc}'",
            "-frames:v",
            "1",
            str(out_png),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"FFmpeg render lỗi: {result.stderr}"
        assert out_png.exists() and out_png.stat().st_size > 0


class TestDualModeChuanHoa:
    """Kiểm định chuẩn hóa kích thước, font size, safe zone cho cả Mode Dọc (9:16) và Mode Ngang (16:9)."""

    def test_mode_doc_9_16_kich_thuoc_va_safe_zone(self):
        captions = [
            {
                "text": "Bí quyết tăng 300% doanh thu TikTok",
                "start_ms": 0,
                "duration_ms": 2000,
                "words": [
                    {"text": "Bí", "start_ms": 0, "end_ms": 250},
                    {"text": "quyết", "start_ms": 260, "end_ms": 500},
                    {"text": "tăng", "start_ms": 510, "end_ms": 800},
                    {"text": "300%", "start_ms": 810, "end_ms": 1200},
                    {"text": "doanh", "start_ms": 1210, "end_ms": 1500},
                    {"text": "thu", "start_ms": 1510, "end_ms": 1750},
                    {"text": "TikTok", "start_ms": 1760, "end_ms": 2000},
                ],
            }
        ]
        ass_9_16 = build_karaoke_ass(
            captions, width=1080, height=1920,
            settings={"preset": "da_sac_phan_tang"},
        )
        assert "PlayResX: 1080" in ass_9_16
        assert "PlayResY: 1920" in ass_9_16
        assert ",80,80,360,1" in ass_9_16  # MarginV=360px Safe zone TikTok
        assert r"\fs54" in ass_9_16  # Cỡ dòng dẫn 54px
        assert r"\fs70" in ass_9_16  # Cỡ dòng đinh 70px

    def test_mode_ngang_16_9_kich_thuoc_va_safe_zone(self):
        captions = [
            {
                "text": "Bí quyết tăng 300% doanh thu TikTok",
                "start_ms": 0,
                "duration_ms": 2000,
                "words": [
                    {"text": "Bí", "start_ms": 0, "end_ms": 250},
                    {"text": "quyết", "start_ms": 260, "end_ms": 500},
                    {"text": "tăng", "start_ms": 510, "end_ms": 800},
                    {"text": "300%", "start_ms": 810, "end_ms": 1200},
                    {"text": "doanh", "start_ms": 1210, "end_ms": 1500},
                    {"text": "thu", "start_ms": 1510, "end_ms": 1750},
                    {"text": "TikTok", "start_ms": 1760, "end_ms": 2000},
                ],
            }
        ]
        ass_16_9 = build_karaoke_ass(
            captions, width=1920, height=1080,
            settings={"preset": "da_sac_phan_tang"},
        )
        assert "PlayResX: 1920" in ass_16_9
        assert "PlayResY: 1080" in ass_16_9
        assert ",140,140,90,1" in ass_16_9   # MarginV=90px Lower-Third
        assert r"\fs38" in ass_16_9  # Cỡ dòng dẫn 38px
        assert r"\fs50" in ass_16_9  # Cỡ dòng đinh 50px

    def test_render_ffmpeg_ca_hai_mode(self, tmp_path):
        for w, h, name in [(1080, 1920, "doc_9_16"), (1920, 1080, "ngang_16_9")]:
            ass_path = tmp_path / f"test_{name}.ass"
            out_png = tmp_path / f"test_{name}.png"
            captions = [
                {
                    "text": "Kiểm tra render libass chế độ hai khung hình",
                    "start_ms": 0,
                    "duration_ms": 1800,
                    "words": [
                        {"text": "Kiểm", "start_ms": 0, "end_ms": 250},
                        {"text": "tra", "start_ms": 260, "end_ms": 500},
                        {"text": "render", "start_ms": 510, "end_ms": 800},
                        {"text": "libass", "start_ms": 810, "end_ms": 1100},
                        {"text": "chế", "start_ms": 1110, "end_ms": 1300},
                        {"text": "độ", "start_ms": 1310, "end_ms": 1500},
                        {"text": "hai", "start_ms": 1510, "end_ms": 1650},
                        {"text": "khung hình", "start_ms": 1660, "end_ms": 1800},
                    ],
                }
            ]
            ass_txt = build_karaoke_ass(captions, width=w, height=h, settings={"preset": "hop_mau_dong_chinh"})
            ass_path.write_text(ass_txt, encoding="utf-8-sig")
            ass_esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
            cmd = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c=black:s={w}x{h}:d=1",
                "-vf", f"subtitles='{ass_esc}'",
                "-frames:v", "1", str(out_png),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            assert res.returncode == 0, f"FFmpeg render lỗi {name}: {res.stderr}"
            assert out_png.exists() and out_png.stat().st_size > 0


class TestTichHopE2ELuongDungVaTaoVideo:
    """Kiểm định tích hợp E2E hai luồng: Auto Edit và Tạo Video AI."""

    def test_bo_chon_preset_thong_minh_auto_edit(self):
        from src.modules.dieu_phoi_dung.dung_video_dai import _chon_preset_phu_de
        # 1. Đoạn có số liệu tài chính / KPI -> Bento
        assert _chon_preset_phu_de("Doanh thu quý 3 đạt 500 triệu đồng") == "bento_ba_tang"
        # 2. Đoạn kể chuyện / câu hỏi -> Inline Pop
        assert _chon_preset_phu_de("Tại sao người làm kinh doanh lại hay thất bại?") == "inline_pop_trai"
        # 3. Đoạn xu hướng / mẹo -> Hộp màu pill
        assert _chon_preset_phu_de("Mẹo cập nhật xu hướng AI nhanh nhất hôm nay") == "hop_mau_dong_chinh"
        # 4. Mặc định bán hàng / viral -> Đa sắc
        assert _chon_preset_phu_de("Món bán chạy nhất cửa hàng đang được ưu đãi") == "da_sac_phan_tang"
        # 5. Nếu user chỉ định cụ thể thì ưu tiên tuyệt đối
        assert _chon_preset_phu_de("Doanh thu 500 triệu", user_preset="inline_pop_trai") == "inline_pop_trai"

    def test_tao_timeline_auto_edit_chuan_hoa_hai_mode(self):
        from src.modules.dieu_phoi_dung.dung_video_dai import ClipTuDong, _tao_timeline
        clip = ClipTuDong(
            clip_id="c01",
            title="Món bán chạy nhất",
            reason="Mở đầu gây chú ý cao",
            start_ms=0,
            end_ms=5000,
        )
        words = [
            {"id": "w01", "text": "Món", "start_ms": 0, "end_ms": 300},
            {"id": "w02", "text": "bán", "start_ms": 310, "end_ms": 600},
            {"id": "w03", "text": "chạy", "start_ms": 610, "end_ms": 900},
            {"id": "w04", "text": "nhất", "start_ms": 910, "end_ms": 1300},
        ]
        # Test Mode Dọc 9:16
        tl_doc = _tao_timeline("src_id", clip, words, width=1080, height=1920, caption_preset="da_sac_phan_tang")
        assert tl_doc["width"] == 1080
        assert tl_doc["height"] == 1920
        assert tl_doc["karaoke_settings"]["preset"] == "da_sac_phan_tang"
        assert tl_doc["karaoke_settings"]["font_size"] == 70

        # Test Mode Ngang 16:9
        tl_ngang = _tao_timeline("src_id", clip, words, width=1920, height=1080, caption_preset="bento_ba_tang")
        assert tl_ngang["width"] == 1920
        assert tl_ngang["height"] == 1080
        assert tl_ngang["karaoke_settings"]["preset"] == "bento_ba_tang"
        assert tl_ngang["karaoke_settings"]["font_size"] == 50

    def test_runner_luong_tao_video_karaoke_captions_hai_mode(self):
        from src.modules.tao_video_noi_dung.runner import _karaoke_captions
        words = [
            {"text": "Bí quyết", "start_ms": 0, "end_ms": 400},
            {"text": "xây kênh", "start_ms": 410, "end_ms": 800},
            {"text": "triệu view", "start_ms": 810, "end_ms": 1400},
        ]
        # Mode Dọc: font_size 70px
        caps_doc = _karaoke_captions(words, height=1920, width=1080)
        assert len(caps_doc) > 0
        assert caps_doc[0].font_size == 70

        # Mode Ngang: font_size 50px
        caps_ngang = _karaoke_captions(words, height=1080, width=1920)
        assert len(caps_ngang) > 0
        assert caps_ngang[0].font_size == 50
