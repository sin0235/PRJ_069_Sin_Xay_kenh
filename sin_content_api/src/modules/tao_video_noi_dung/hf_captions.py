"""Quản lý các kiểu phụ đề động (selectable caption styles) cho HyperFrames.

Cung cấp kiểu mặc định 'karaoke' (đổi màu từng từ trên nền GSAP) và các kiểu phụ đề
dựng từ kho khối HyperFrames registry (pill_karaoke, highlight, clip_wipe, kinetic_slam,
weight_shift, particle_burst) đồng bộ chính xác theo mốc thời gian thực của từng từ.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import hf_vendor

BLOCKS_DIR = Path(__file__).resolve().parents[3] / "engines" / "hyperframes" / "blocks"

# Danh sách kiểu phụ đề được hỗ trợ đầy đủ tiếng Việt ở 16:9 và 9:16
CAPTION_STYLES: tuple[str, ...] = (
    "karaoke",
    "pill_karaoke",
    "highlight",
    "clip_wipe",
    "kinetic_slam",
    "weight_shift",
    "particle_burst",
)

# Danh sách kiểu phụ đề trong kho catalog chưa được hỗ trợ kèm lý do kỹ thuật ngắn gọn
CAPTION_UNSUPPORTED: dict[str, str] = {
    "blend_difference": "Mã mẫu CSS mix-blend-mode thụ động, không phải khối timeline phụ đề độc lập nhận mốc từ.",
    "camera_follow": "Không hỗ trợ mốc thời gian thực của từng từ (bỏ qua start/end timestamp, tự chia đều theo thời lượng).",
    "emoji_pop": "Chỉ hỗ trợ bộ biểu tượng emoji và từ khóa tiếng Anh cố định, không tương thích với từ vựng tiếng Việt tự do.",
    "texture": "Phụ thuộc tệp ảnh vân bề mặt ngoài (dung nham, đá hoa, kim loại...), không tự khép kín trong gói phụ đề.",
    "editorial_emphasis": "Bố cục kiểu chữ tĩnh định hình riêng cho câu mẫu tiếng Anh cố định, không tự co giãn theo câu tiếng Việt bất kỳ.",
    "parallax_layers": "Phân tầng chữ 3D trước/sau định hình cố định theo câu mẫu tiếng Anh, không tự động nhận diện ngữ pháp tiếng Việt.",
    "matrix_decode": "Hiệu ứng giải mã ma trận ký tự ngẫu nhiên làm xáo trộn dấu thanh tiếng Việt trước khi hiển thị.",
    "neon_glow": "Màu phát sáng neon phụ thuộc danh sách từ khóa cố định tiếng Anh, không tối ưu cho bảng màu thương hiệu.",
    "neon_accent": "Hiệu ứng rung drift và đổi màu ngẫu nhiên làm rung lắc dấu thanh tiếng Việt ở khung hình dọc.",
    "glitch_rgb": "Hiệu ứng tách kênh RGB làm nhòe và vỡ nét dấu phụ tiếng Việt (mũ, móc, thanh điệu).",
    "gradient_fill": "Dải màu gradient phụ thuộc nhóm từ cố định, chưa tối ưu an toàn vùng hiển thị ở tỉ lệ dọc 9:16.",
}


def caption_groups(words: list[dict], max_words: int = 5, pause_ms: int = 220) -> list[list[dict]]:
    """Gom các từ thành từng cụm hiển thị theo ngưỡng số từ tối đa hoặc khoảng lặng ngắt nghỉ."""
    groups, current = [], []
    for index, word in enumerate(words):
        current.append(word)
        gap = words[index + 1]["start_ms"] - word["end_ms"] if index + 1 < len(words) else 10 ** 6
        if len(current) >= max_words or word["text"].rstrip().endswith((".", "!", "?", "…")) or (gap >= pause_ms and len(current) >= 3):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def karaoke_composition(words: list[dict], total: float, aspect_ratio: str = "16:9") -> str:
    """Bản dựng phụ đề karaoke nguyên bản của dự án: đổi màu vàng kim theo mốc từng từ."""
    portrait = aspect_ratio == "9:16"
    width, height = (1080, 1920) if portrait else (1920, 1080)
    groups = caption_groups(words, max_words=3 if portrait else 5)
    markup, code = "", ""
    for g, group in enumerate(groups):
        start, end = max(.1, group[0]["start_ms"] / 1000 - .05), group[-1]["end_ms"] / 1000 + .1
        if g:
            start = max(start, groups[g - 1][-1]["end_ms"] / 1000 + .02)
        if g + 1 < len(groups):
            end = min(end, max(start + .3, groups[g + 1][0]["start_ms"] / 1000 - .08))
        spans = "".join(f'<span class="w" id="cap-{g}-{i}">{html.escape(w["text"])}</span> ' for i, w in enumerate(group))
        markup += f'<div class="g" id="cap-g{g}">{spans}</div>\n'
        code += f'tl.set("#cap-g{g}", {{ opacity: 0, visibility: "hidden" }}, 0);\ntl.set("#cap-g{g}", {{ visibility: "visible" }}, {start:.3f});\n'
        code += f'tl.fromTo("#cap-g{g}", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: .16, ease: "power3.out" }}, {start:.3f});\n'
        for i, w in enumerate(group):
            code += f'tl.to("#cap-{g}-{i}", {{ color: "#FFD54A", duration: .06, ease: "none" }}, {w["start_ms"] / 1000:.3f});\n'
        code += f'tl.to("#cap-g{g}", {{ opacity: 0, duration: .12, ease: "power2.in" }}, {end - .12:.3f});\ntl.set("#cap-g{g}", {{ opacity: 0, visibility: "hidden" }}, {end:.3f});\n'
    left, right, bottom, font_size = (120, 120, 340, 44) if portrait else (0, 0, 38, 54)
    return (f'<template>\n<style>@font-face{{font-family:"Viet";src:url(\'assets/fonts/be_vietnam_pro_semibold.ttf\');font-weight:400 800}}\n'
            '[data-composition-id="captions"]{position:absolute;inset:0;font-family:"Viet",sans-serif}\n'
            f'[data-composition-id="captions"] .g{{position:absolute;left:{left}px;right:{right}px;bottom:{bottom}px;text-align:center;font-size:{font_size}px;font-weight:700;color:#fff;white-space:nowrap;opacity:0;visibility:hidden;'
            '-webkit-text-stroke:9px #06131d;paint-order:stroke fill;overflow:visible}</style>\n'
            f'<div id="root" data-composition-id="captions" data-width="{width}" data-height="{height}">\n{markup}</div>\n'
            f'<script>\nconst tl = gsap.timeline({{ paused: true }});\n{code}window.__timelines["captions"] = tl;\n</script>\n</template>\n')


def _block_path(style: str) -> Path:
    kebab = style.replace("_", "-")
    path = BLOCKS_DIR / f"caption-{kebab}.html"
    if not path.is_file():
        raise FileNotFoundError(f"HYPERFRAMES_CAPTION_BLOCK_MISSING:{style}")
    return path


def caption_composition(style: str, words: list[dict], total: float, aspect: str = "16:9") -> tuple[str, str]:
    """Tạo mã HTML và thuộc tính bổ sung cho thẻ host của phụ đề theo kiểu được chọn.

    Trả về: (composition_html, host_extra_attributes).
    Ném lỗi ValueError("HYPERFRAMES_CAPTION_STYLE_INVALID") nếu style không nằm trong danh mục hỗ trợ.
    """
    if style not in CAPTION_STYLES:
        raise ValueError("HYPERFRAMES_CAPTION_STYLE_INVALID")

    if style == "karaoke":
        return karaoke_composition(words, total, aspect), ""

    portrait = aspect == "9:16"
    width, height = (1080, 1920) if portrait else (1920, 1080)

    text = _block_path(style).read_text(encoding="utf-8")
    text, _ = hf_vendor.localize(text)

    # Chuẩn hóa danh sách từ và mốc thời gian sang giây
    words_data = [
        {
            "text": str(w.get("text", "")),
            "start": round(float(w.get("start_ms", 0)) / 1000.0, 3),
            "end": round(float(w.get("end_ms", 0)) / 1000.0, 3),
        }
        for w in words
    ]
    words_json = json.dumps(words_data, ensure_ascii=False)

    # Thay mảng từ mẫu bằng mảng từ thật
    if "var WORDS =" in text:
        text = re.sub(r'var\s+WORDS\s*=\s*\[[\s\S]*?\];', f'var WORDS = {words_json};', text)
    if "var TRANSCRIPT =" in text:
        text = re.sub(r'var\s+TRANSCRIPT\s*=\s*\[[\s\S]*?\];', f'var TRANSCRIPT = {words_json};', text)

    # Cập nhật phân nhóm động cho các khối dùng RAW_GROUPS
    if "RAW_GROUPS" in text:
        max_words = 3 if portrait else 4
        groups = caption_groups(words, max_words=max_words)
        raw_groups = []
        cur = 0
        for g in groups:
            raw_groups.append([cur, cur + len(g) - 1])
            cur += len(g)
        text = re.sub(r'var\s+RAW_GROUPS\s*=\s*\[[\s\S]*?\];', f'var RAW_GROUPS = {json.dumps(raw_groups)};', text)

    # Cập nhật từ khóa nhấn mạnh cho các khối dùng KEYWORDS
    if "var KEYWORDS =" in text:
        kw = [i for i in range(len(words)) if i % 3 == 0]
        text = re.sub(r'var\s+KEYWORDS\s*=\s*new\s+Set\(\[[^\]]*\]\);', f'var KEYWORDS = new Set({json.dumps(kw)});', text)

    # Cập nhật thời lượng thật vào mã và thuộc tính data-duration
    text = re.sub(r'var\s+DURATION\s*=\s*[\d.]+;', f'var DURATION = {total:.3f};', text)
    text = re.sub(r'(data-(?:composition-)?duration=")[\d.]+(")', fr'\g<1>{total:.3f}\g<2>', text)
    text = re.sub(r'(dataset\.duration\s*\|\|\s*")[\d.]+(")', fr'\g<1>{total:.3f}\g<2>', text)

    # Đổi định danh thành 'captions' để timeline và host điều khiển đúng
    comp_prefix = f"caption-{style.replace('_', '-')}"
    short_id = style.replace("_", "-")
    text = re.sub(r'data-composition-id="[^"]+"', 'data-composition-id="captions"', text)
    text = re.sub(rf'id="{short_id}"', 'id="captions"', text)
    text = re.sub(rf'id="{comp_prefix}"', 'id="captions"', text)
    text = re.sub(rf'#{short_id}\b', '#captions', text)
    text = re.sub(rf'#{comp_prefix}\b', '#captions', text)
    text = re.sub(r'window\.__timelines\[["\'][^"\']+["\']\]', 'window.__timelines["captions"]', text)

    # Điều chỉnh kích thước và tỉ lệ khung hình
    text = text.replace('data-width="1920"', f'data-width="{width}"')
    text = text.replace('data-height="1080"', f'data-height="{height}"')
    text = re.sub(r'(width:\s*)1920px;', rf'\g<1>{width}px;', text)
    text = re.sub(r'(height:\s*)1080px;', rf'\g<1>{height}px;', text)

    if portrait:
        text = re.sub(r'(bottom:\s*)1[024]0px;', r'\g<1>340px;', text)
        text = re.sub(r'width:\s*(?:1400|1600)px;', 'width: 960px;', text)
        text = re.sub(r'max-width:\s*(?:1400|1600)px;', 'max-width: 960px;', text)
        text = re.sub(r'var\s+SAFE_ZONE_WIDTH\s*=\s*\d+;', 'var SAFE_ZONE_WIDTH = 920;', text)
        text = re.sub(r'var\s+PILL_MAX_WIDTH\s*=\s*\d+;', 'var PILL_MAX_WIDTH = 920;', text)
        text = re.sub(r'var\s+BASE_FONT_SIZE\s*=\s*\d+;', 'var BASE_FONT_SIZE = 54;', text)
        text = re.sub(r'var\s+CAPTION_FONT_SIZE\s*=\s*\d+;', 'var CAPTION_FONT_SIZE = 54;', text)

    # Đồng bộ font chữ tiếng Việt Be Vietnam Pro
    for old_font in ["Anton", "Space Grotesk", "Montserrat", "Poppins", "Outfit", "Inter"]:
        text = text.replace(f'"{old_font}"', '"Viet"')
        text = text.replace(f"'{old_font}'", "'Viet'")

    font_face_css = """
@font-face {
  font-family: "Viet";
  src: url('assets/fonts/be_vietnam_pro_semibold.ttf');
  font-weight: 100 900;
}
@font-face {
  font-family: "Anton";
  src: local('Arial');
}
* {
  font-family: "Viet", sans-serif !important;
}
"""
    text = text.replace("<style>", f"<style>{font_face_css}\n")

    # Khoác bảng màu thương hiệu Baha (vàng kim #ffd54a, xanh navy #0a1c2b / #12324a, ngọc lam #5cc8c0, muted #9fb4c4)
    text = re.sub(r'#FFD700\b', '#ffd54a', text)
    text = text.replace("background: #e7e5e7;", "background: #12324a; border: 2px solid rgba(255,255,255,0.18);")
    if "var COLOR_ACTIVE =" in text:
        text = re.sub(r'var\s+COLOR_ACTIVE\s*=\s*"[^"]*";', 'var COLOR_ACTIVE = "#ffd54a";', text)
    if "var COLOR_INACTIVE =" in text:
        text = re.sub(r'var\s+COLOR_INACTIVE\s*=\s*"[^"]*";', 'var COLOR_INACTIVE = "#9fb4c4";', text)

    # Kiểm tra an toàn: không còn bất kỳ URL ngoài nào
    remaining_urls = hf_vendor.scan_external(text)
    if remaining_urls:
        raise ValueError(f"HYPERFRAMES_CAPTION_EXTERNAL_URL:{style}:{remaining_urls[0]}")

    return text, ""
