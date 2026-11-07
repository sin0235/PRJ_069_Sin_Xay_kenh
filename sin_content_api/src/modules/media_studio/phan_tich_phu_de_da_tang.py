"""Mô-đun phân tích ngữ nghĩa, phân tầng kích thước và tô màu đa sắc cho phụ đề Tiếng Việt.

Tuân thủ BAHA_PROJECT_OS_STANDARD_TEMPLATE_V2:
- 100% Tiếng Việt có dấu chuẩn ngữ pháp.
- Tuyệt đối không dùng emoji (No Emoji - SVG Only).
- Quy chuẩn Safe Zone 9:16 cho video ngắn TikTok/Reels/Shorts.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

SemanticRole = Literal["METRIC_GOLD", "PAIN_CORAL", "GROWTH_EMERALD", "BRAND_CYAN", "NORMAL_WHITE"]


def to_ass_color(hex_rgb: str, alpha: str = "00") -> str:
    """Chuyển mã màu RGB (#RRGGBB) sang định dạng ASS (&HAABBGGRR&)."""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha}{b}{g}{r}&"


# Bảng màu chuẩn thương hiệu & ngữ nghĩa
COLOR_HEX_MAP: dict[SemanticRole, str] = {
    "METRIC_GOLD": "#FFD54A",
    "PAIN_CORAL": "#FF4D4F",
    "GROWTH_EMERALD": "#34D399",
    "BRAND_CYAN": "#38BDF8",
    "NORMAL_WHITE": "#FFFFFF",
}

COLOR_ASS_MAP: dict[SemanticRole, str] = {
    role: to_ass_color(hex_val) for role, hex_val in COLOR_HEX_MAP.items()
}
COLOR_ASS_MUTED: str = to_ass_color("#CBD5E1")
COLOR_ASS_DARK_OUTLINE: str = to_ass_color("#060911")
COLOR_ASS_PILL_RED: str = to_ass_color("#E11D48")

# Từ khóa nhận diện ngữ nghĩa Tiếng Việt (Kiểm soát chặt chẽ, chống nhảy màu tùy tiện)
# Chỉ nhận diện con số có chữ số thực tế, hoặc cụm từ ghép có nghĩa trọn vẹn
RE_METRIC = re.compile(
    r"\b(?:\d+[\d.,]*\s*(?:k|triệu|tỷ|%|\busd\b|\bđ\b|\bđồng\b|\bgiây\b|\bphút\b|\bgiờ\b|\bngày\b|\btuần\b|\btháng\b|\bnăm\b|\blần\b)?|x\d+\b|\bkpi\b|\btop\s*\d+\b)",
    re.IGNORECASE,
)

PAIN_COMPOUNDS = {
    "đừng", "cấm", "sai lầm", "chết người", "thất bại", "nguy hiểm", "cảnh báo",
    "thua lỗ", "kéo shop lỗ", "kéo xốp lỗ", "lỗ nặng", "lỗ", "không tốn", "tốn kém",
    "tụt dốc", "mất tiền", "hỏng bét", "bế tắc",
    "bận rộn", "tiếc công", "tiếc tiền", "nuôi nhầm", "tỷ lệ hoàn",
}

GROWTH_COMPOUNDS = {
    "bí quyết", "thành công", "đột phá", "bứt phá", "doanh thu",
    "lợi nhuận", "có lãi", "tạo tiền", "nuôi cửa hàng", "giữ chân",
    "tối ưu", "hiệu quả", "lên xu hướng", "tăng trưởng", "bán chạy",
}

BRAND_COMPOUNDS = {
    "tiktok", "sin", "baha", "xây kênh", "quảng cáo", "bán hàng",
    "chi phí", "mã hàng",
}


def _normalize(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFC", text).casefold() if ch.isalnum() or ch.isspace()).strip()


def phan_loai_tu_khoa(text: str) -> SemanticRole:
    """Phân loại vai trò ngữ nghĩa của một từ/cụm từ Tiếng Việt có kiểm soát."""
    clean = _normalize(text)
    if not clean:
        return "NORMAL_WHITE"
    # 1. Con số / KPI thực sự
    if RE_METRIC.search(clean) or any(ch.isdigit() for ch in text):
        return "METRIC_GOLD"
    # 2. Cụm điểm đau / rủi ro
    for pw in PAIN_COMPOUNDS:
        if pw in clean or clean in pw.split():
            # Chỉ khớp từ đơn nếu từ đó có ý nghĩa điểm đau mạnh và độc nhất (như 'đừng', 'cấm', 'lỗ')
            if clean in ("đừng", "cấm", "lỗ", "hỏng", "thất bại", "nguy hiểm", "cảnh báo", "bận rộn", "tiếc tiền"):
                return "PAIN_CORAL"
            if pw in clean:
                return "PAIN_CORAL"
    # 3. Cụm tăng trưởng / thành công
    for gw in GROWTH_COMPOUNDS:
        if gw in clean or (clean in ("đột phá", "thành công", "bí quyết", "có lãi", "tạo tiền") and clean in gw):
            return "GROWTH_EMERALD"
    # 4. Cụm thương hiệu / chuyên ngành
    for bw in BRAND_COMPOUNDS:
        if bw in clean:
            return "BRAND_CYAN"
    return "NORMAL_WHITE"


@dataclass
class TuPhuDePhanTang:
    text: str
    start_ms: int
    end_ms: int
    role: SemanticRole = "NORMAL_WHITE"
    line_index: int = 0
    font_size: int = 76
    is_uppercase: bool = False
    is_pill: bool = False
    scale_factor: float = 1.0


@dataclass
class CumPhuDePhanTang:
    start_ms: int
    duration_ms: int
    words: list[TuPhuDePhanTang] = field(default_factory=list)
    preset: str = "da_sac_phan_tang"
    layout: str = "center"


def phan_tich_cum_phu_de(
    words: list[dict[str, Any]],
    start_ms: int,
    duration_ms: int,
    preset: str = "da_sac_phan_tang",
    base_font_size: int = 84,
) -> CumPhuDePhanTang:
    """Phân tích một cụm phụ đề thành cấu trúc đa tầng, đa sắc theo preset được chọn."""
    if not words:
        return CumPhuDePhanTang(start_ms=start_ms, duration_ms=duration_ms, preset=preset)

    parsed_words: list[TuPhuDePhanTang] = []
    seen_roles: set[SemanticRole] = set()

    for w in words:
        text = str(w.get("text", "")).strip()
        s_ms = int(w.get("start_ms", start_ms))
        e_ms = int(w.get("end_ms", start_ms + duration_ms))
        role = phan_loai_tu_khoa(text)
        # Giới hạn tối đa 2 màu nhấn khác nhau trong một cụm để tránh rối mắt
        if role != "NORMAL_WHITE":
            if len(seen_roles) >= 2 and role not in seen_roles:
                role = "NORMAL_WHITE"
            else:
                seen_roles.add(role)
        parsed_words.append(TuPhuDePhanTang(text=text, start_ms=s_ms, end_ms=e_ms, role=role))

    n = len(parsed_words)

    # 1. PRESET: da_sac_phan_tang (Hormozi Viral - 2 hoặc 3 dòng chữ to nhỏ)
    if preset == "da_sac_phan_tang":
        if n <= 3:
            # Câu rất ngắn (1-3 từ): Phóng to đồng đều
            for w in parsed_words:
                w.line_index = 0
                w.font_size = round(base_font_size * 1.15)
                if w.role != "NORMAL_WHITE":
                    w.is_uppercase = True
        elif n <= 6:
            # 4-6 từ: Chia 2 dòng (Dòng 1 dẫn nhỏ, Dòng 2 đinh lớn IN HOA)
            mid = 2 if n == 4 else (2 if n == 5 else 3)
            for i, w in enumerate(parsed_words):
                if i < mid:
                    w.line_index = 0
                    w.font_size = round(base_font_size * 0.72)  # Dòng dẫn nhỏ gọn ~60px
                else:
                    w.line_index = 1
                    w.font_size = round(base_font_size * 1.20)  # Dòng đinh to rực rỡ ~100px
                    w.is_uppercase = True
        else:
            # 7+ từ: Chia 3 dòng Bento (Dẫn nhỏ, Đinh cực đại, Kết vừa)
            l1_end = max(2, n // 3)
            l2_end = max(l1_end + 2, (2 * n) // 3)
            for i, w in enumerate(parsed_words):
                if i < l1_end:
                    w.line_index = 0
                    w.font_size = round(base_font_size * 0.65)
                elif i < l2_end:
                    w.line_index = 1
                    w.font_size = round(base_font_size * 1.25)
                    w.is_uppercase = True
                else:
                    w.line_index = 2
                    w.font_size = round(base_font_size * 0.85)

    # 2. PRESET: hop_mau_dong_chinh (CapCut Pill Box)
    elif preset == "hop_mau_dong_chinh":
        if n <= 3:
            for w in parsed_words:
                w.line_index = 0
                w.font_size = base_font_size
                w.is_pill = (w.role != "NORMAL_WHITE")
        else:
            split_at = n // 2
            for i, w in enumerate(parsed_words):
                if i < split_at:
                    w.line_index = 0
                    w.font_size = round(base_font_size * 0.75)
                else:
                    w.line_index = 1
                    w.font_size = round(base_font_size * 1.10)
                    w.is_pill = (w.role in ("PAIN_CORAL", "METRIC_GOLD", "GROWTH_EMERALD"))
                    w.is_uppercase = True

    # 3. PRESET: bento_ba_tang (Khối chữ Bento 3 tầng)
    elif preset == "bento_ba_tang":
        if n <= 4:
            for i, w in enumerate(parsed_words):
                w.line_index = 0 if i < 2 else 1
                w.font_size = round(base_font_size * 0.65) if w.line_index == 0 else round(base_font_size * 1.22)
                if w.line_index == 1:
                    w.is_uppercase = True
        else:
            l1_cnt = 2
            l2_cnt = 2 if n <= 6 else 3
            for i, w in enumerate(parsed_words):
                if i < l1_cnt:
                    w.line_index = 0
                    w.font_size = round(base_font_size * 0.58)
                    w.role = "BRAND_CYAN"
                    w.is_uppercase = True
                elif i < l1_cnt + l2_cnt:
                    w.line_index = 1
                    w.font_size = round(base_font_size * 1.25)
                    w.role = "METRIC_GOLD" if w.role == "NORMAL_WHITE" else w.role
                    w.is_uppercase = True
                else:
                    w.line_index = 2
                    w.font_size = round(base_font_size * 0.75)

    # 4. PRESET: inline_pop_trai (Căn trái phóng to nội dòng)
    elif preset == "inline_pop_trai":
        mid = max(1, n // 2) if n > 3 else n
        for i, w in enumerate(parsed_words):
            w.line_index = 0 if i < mid else 1
            if w.role != "NORMAL_WHITE":
                w.font_size = round(base_font_size * 1.22)
                w.is_uppercase = True
            else:
                w.font_size = round(base_font_size * 0.75)

    # Legacy: giữ nguyên đồng cỡ
    else:
        for w in parsed_words:
            w.font_size = base_font_size

    return CumPhuDePhanTang(
        start_ms=start_ms,
        duration_ms=duration_ms,
        words=parsed_words,
        preset=preset,
        layout="left" if preset == "inline_pop_trai" else "center",
    )
