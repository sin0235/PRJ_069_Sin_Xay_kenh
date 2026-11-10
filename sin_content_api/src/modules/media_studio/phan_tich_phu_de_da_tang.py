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
    muted: bool = False      # chữ dẫn nhạt (xám dịu) như dòng dẫn trong bản mẫu HTML
    tracking: int = 0        # giãn cách chữ (px) cho dòng tagline của mẫu Bento


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
    portrait: bool = False,
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
    B = base_font_size
    per_line = 4 if portrait else 7   # sức chứa một dòng: khung ngang rộng nên nhiều từ hơn khung dọc

    def chia_dong(total: int) -> list[int]:
        """Số từ mỗi dòng theo sức chứa khung: 1 dòng nếu đủ chỗ, 2 dòng, tối đa 3 dòng."""
        if total <= per_line:
            return [total]
        if total <= per_line * 2:
            lead = max(2, round(total * 0.42))
            return [lead, total - lead]
        lead = max(2, round(total * 0.3))
        mid = max(2, round(total * 0.4))
        return [lead, mid, total - lead - mid]

    sizes = chia_dong(n)

    def diem_ngat(prev_w: str, next_w: str) -> int:
        """Điểm cho chỗ ngắt dòng: ngắt sau dấu câu tốt, cắt đôi cụm từ khóa (vd "sai lầm") là xấu."""
        score = 0
        if prev_w.rstrip().endswith((",", ".", ";", ":", "!", "?", "…")):
            score += 2
        if (phan_loai_tu_khoa(f"{prev_w} {next_w}") != "NORMAL_WHITE"
                and phan_loai_tu_khoa(prev_w) == "NORMAL_WHITE" and phan_loai_tu_khoa(next_w) == "NORMAL_WHITE"):
            score -= 3
        return score

    if len(sizes) > 1:
        # dịch ranh giới dòng tối đa 2 từ để ngắt đúng chỗ, mỗi dòng vẫn giữ tối thiểu 2 từ
        bounds = [sum(sizes[: i + 1]) for i in range(len(sizes) - 1)]
        for bi, b in enumerate(bounds):
            lo = (bounds[bi - 1] if bi else 0) + 2
            hi = (bounds[bi + 1] if bi + 1 < len(bounds) else n) - 2
            best, best_score = b, None
            for shift in (0, -1, 1, -2, 2):
                cand = b + shift
                if not lo <= cand <= hi:
                    continue
                sc = diem_ngat(parsed_words[cand - 1].text, parsed_words[cand].text)
                if best_score is None or sc > best_score:
                    best, best_score = cand, sc
            bounds[bi] = best
        edges = [0, *bounds, n]
        sizes = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]

    line_of: list[int] = []
    pos_in_line: list[int] = []
    for li, cnt in enumerate(sizes):
        for k in range(cnt):
            line_of.append(li)
            pos_in_line.append(k)
    n_lines = len(sizes)
    last_line = n_lines - 1

    for i, w in enumerate(parsed_words):
        w.line_index = line_of[i]

    # Tỉ lệ cỡ chữ giữa các tầng chỉ lệch nhẹ (khoảng 1.0 : 1.3) để không chênh quá mức.
    DAN, CHINH, KET, NHAN = 0.80, 1.0, 0.80, 0.95

    # 1. da_sac_phan_tang (Hormozi Viral): dẫn -> đinh vàng/san hô -> kết xanh lục
    if preset == "da_sac_phan_tang":
        for i, w in enumerate(parsed_words):
            li, k, cnt = line_of[i], pos_in_line[i], sizes[line_of[i]]
            if n_lines == 1:
                w.font_size = round(B * CHINH)
                w.is_uppercase = w.role != "NORMAL_WHITE"
            elif li == 0:
                w.font_size = round(B * DAN)
                w.muted = k < 2 and w.role == "NORMAL_WHITE"
            elif li == 1 or (n_lines == 2 and li == last_line):
                w.font_size = round(B * CHINH)
                w.is_uppercase = True
                if w.role == "NORMAL_WHITE":
                    w.role = "METRIC_GOLD" if k < (cnt + 1) // 2 else "PAIN_CORAL"
            else:
                payoff = k >= cnt - 3 if cnt > 3 else k >= cnt - 2
                w.font_size = round(B * (NHAN if payoff else KET))
                w.is_uppercase = payoff
                if payoff and w.role == "NORMAL_WHITE":
                    w.role = "GROWTH_EMERALD"

    # 2. hop_mau_dong_chinh (CapCut Pill Box): dòng giữa bọc hộp san hô, dòng cuối nhấn xanh lam
    elif preset == "hop_mau_dong_chinh":
        for i, w in enumerate(parsed_words):
            li, k, cnt = line_of[i], pos_in_line[i], sizes[line_of[i]]
            if n_lines == 1:
                w.font_size = round(B * NHAN)
                w.is_pill = True
                w.is_uppercase = True
            elif li == 0:
                w.font_size = round(B * DAN)
            elif li == 1 or (n_lines == 2 and li == last_line):
                w.font_size = round(B * NHAN)
                w.is_pill = True
                w.is_uppercase = True
            else:
                big = k >= min(2, cnt - 1)
                w.font_size = round(B * (NHAN if big else KET))
                w.is_uppercase = big
                w.muted = not big
                if big:
                    w.role = "BRAND_CYAN"

    # 3. bento_ba_tang (Bento Stack): tagline xanh lam giãn chữ -> số vàng lớn -> kết câu
    elif preset == "bento_ba_tang":
        for i, w in enumerate(parsed_words):
            li, k, cnt = line_of[i], pos_in_line[i], sizes[line_of[i]]
            if n_lines == 1:
                w.font_size = round(B * 1.05)
                w.is_uppercase = True
                w.role = "METRIC_GOLD"
            elif li == 0:
                w.font_size = round(B * 0.68)
                w.is_uppercase = True
                w.role = "BRAND_CYAN"
                w.tracking = 3
            elif li == 1 or (n_lines == 2 and li == last_line):
                w.font_size = round(B * 1.05)
                w.is_uppercase = True
                w.role = "METRIC_GOLD" if w.role in ("NORMAL_WHITE", "BRAND_CYAN") else w.role
            else:
                hi = 2 <= k < 4 if cnt >= 4 else k == cnt - 1
                w.font_size = round(B * (NHAN if hi else KET))
                w.is_uppercase = hi
                if hi and w.role == "NORMAL_WHITE":
                    w.role = "GROWTH_EMERALD"

    # 4. inline_pop_trai (Inline Pop, căn trái): từ khóa nhỉnh hơn ngay trong dòng, dòng cuối xanh lục
    elif preset == "inline_pop_trai":
        for i, w in enumerate(parsed_words):
            li, k, cnt = line_of[i], pos_in_line[i], sizes[line_of[i]]
            kw = w.role != "NORMAL_WHITE"
            if n_lines > 1 and li == last_line:
                w.font_size = round(B * NHAN)
                w.is_uppercase = True
                w.role = "GROWTH_EMERALD"
            elif kw:
                w.font_size = round(B * CHINH)
                w.is_uppercase = True
            else:
                w.font_size = round(B * DAN)
                w.muted = li == 0
        # cụm không có từ khóa ở dòng đầu: nhấn 2 từ cuối dòng đầu để vẫn có chữ nhỉnh nội dòng
        if not any(w.role != "NORMAL_WHITE" for w in parsed_words[: sizes[0]]):
            for w in parsed_words[max(0, sizes[0] - 2): sizes[0]]:
                w.font_size = round(B * CHINH)
                w.is_uppercase = True
                w.role = "METRIC_GOLD"
                w.muted = False

    # Dự phòng: giữ đồng cỡ
    else:
        for w in parsed_words:
            w.font_size = B

    return CumPhuDePhanTang(
        start_ms=start_ms,
        duration_ms=duration_ms,
        words=parsed_words,
        preset=preset,
        layout="left" if preset == "inline_pop_trai" else "center",
    )


# Bốn mẫu phụ đề chính thức; "tu_dong" chọn mẫu theo từng cụm lời để video dùng đủ cả bốn.
PRESET_CHINH_THUC: tuple[str, ...] = ("da_sac_phan_tang", "hop_mau_dong_chinh", "bento_ba_tang", "inline_pop_trai")
_RE_SO_LIEU = re.compile(r"\d+\s*(?:%|k|triệu|tỷ|đồng|usd|giây|phút|giờ|ngày|tuần|tháng|năm|lần)|\d{2,}", re.IGNORECASE)


def chon_preset_tu_dong(text: str, index: int = 0) -> str:
    """Chọn mẫu cho một cụm lời: số liệu -> bento, câu hỏi/kể chuyện -> inline, còn lại xoay vòng."""
    lower = text.casefold()
    if _RE_SO_LIEU.search(lower):
        return "bento_ba_tang"
    if "?" in text or any(k in lower for k in ("tại sao", "vì sao", "câu chuyện", "bài học", "sự thật", "lý do")):
        return "inline_pop_trai"
    return ("da_sac_phan_tang", "hop_mau_dong_chinh")[index % 2]
