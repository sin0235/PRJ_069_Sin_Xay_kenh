"""Phụ đề ASS kiểu karaoke động (hỗ trợ cả ngang 16:9 và dọc 9:16).

Bốn mẫu chính thức: da_sac_phan_tang, hop_mau_dong_chinh, bento_ba_tang, inline_pop_trai;
"tu_dong" chọn mẫu theo từng cụm lời. Chữ luôn căn giữa, chạy theo mốc từng từ,
cỡ chữ tính theo khung thật và tự thu nhỏ nếu tràn lề.
"""
from __future__ import annotations

from src.modules.media_studio.phan_tich_phu_de_da_tang import (
    COLOR_ASS_DARK_OUTLINE,
    COLOR_ASS_MAP,
    COLOR_ASS_MUTED,
    COLOR_ASS_PILL_RED,
    chon_preset_tu_dong,
    phan_tich_cum_phu_de,
)
from src.schemas.contracts import KaraokeCaptionSettings

KINETIC_PRESETS = {"da_sac_phan_tang", "hop_mau_dong_chinh", "bento_ba_tang", "inline_pop_trai"}

# Chuyển động mượt: từ đang đọc nở dần POP% trong TWEEN ms; cụm lời mờ dần vào/ra.
POP = 112
TWEEN = 120
FADE_IN = 140
FADE_OUT = 120


def _ts(ms: int) -> str:
    cs = round(max(0, ms) / 10)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def co_chu_mac_dinh(width: int, height: int) -> int:
    """Cỡ chữ cơ sở (px trên khung thật): dọc 9:16 khác ngang 16:9."""
    return 92 if height > width else 90


def _uoc_luong_rong(text: str, fs: float, upper: bool, tracking: int = 0) -> float:
    return len(text) * (fs * (0.44 if upper else 0.40) + tracking)


def build_karaoke_ass(
    captions: list,
    width: int,
    height: int,
    font_family: str = "Be Vietnam Pro SemiBold",
    settings: KaraokeCaptionSettings | dict | None = None,
) -> str:
    settings = KaraokeCaptionSettings.model_validate(settings or {})
    portrait = height > width
    base = max(settings.font_size, round(co_chu_mac_dinh(width, height) * 0.75))

    if portrait:
        margin_v = round(height * (360 / 1920))   # né thanh caption/comment TikTok
        margin_h = round(width * (80 / 1080))
    else:
        margin_v = round(height * (70 / 1080))    # sát đáy khung ngang, chừa chỗ cho chồng 3 tầng
        margin_h = round(width * (140 / 1920))
    avail = width - 2 * margin_h
    alignment = 1 if settings.layout == "left" else 2

    white, gold, cyan, dark = "&H00FFFFFF&", "&H004AD5FF&", "&H00F8BD38&", "&H00080C14&"
    muted = COLOR_ASS_MUTED
    accent = {"champagne": gold, "baha_blue": cyan, "coral": "&H004F4DFF&"}.get(settings.accent_color, gold)
    margin_left_pop = round(width * (140 / 1920)) if not portrait else round(width * (85 / 1080))
    header_lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Karaoke,{font_family},{base},&H00FFFFFF,&H00FFFFFF,&H00080C14,&H99000000,-1,0,0,0,100,100,0,0,1,{max(3, round(base * 0.07))},{max(1, round(base * 0.03))},{alignment},{margin_h},{margin_h},{margin_v},1",
        "", "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    event_lines: list[str] = []
    num_caps = len(captions)
    for c_idx, cap in enumerate(captions):
        get = (lambda k, d=None, c=cap: c.get(k, d)) if isinstance(cap, dict) else (lambda k, d=None, c=cap: getattr(c, k, d))
        start = int(get("start_ms", 0))
        end = start + int(get("duration_ms", 0))
        if c_idx + 1 < num_caps:
            nxt = captions[c_idx + 1]
            next_start = int(nxt.get("start_ms", 0) if isinstance(nxt, dict) else getattr(nxt, "start_ms", 0))
            if end >= next_start:
                end = max(start + 100, next_start - 30)
        if end <= start:
            continue

        words = [
            {"text": w["text"], "start_ms": int(w["start_ms"]), "end_ms": int(w["end_ms"])} if isinstance(w, dict)
            else {"text": w.text, "start_ms": int(w.start_ms), "end_ms": int(w.end_ms)}
            for w in (get("words") or [])
        ]
        if not words:
            # Không có mốc từng từ: chia đều theo số ký tự để sub vẫn chạy theo lời.
            tokens = [t for t in str(get("text", "")).split() if t]
            if not tokens:
                continue
            total_chars = sum(len(t) + 1 for t in tokens)
            cursor = start
            for t in tokens:
                span = max(30, round((end - start) * (len(t) + 1) / total_chars))
                words.append({"text": t, "start_ms": cursor, "end_ms": min(end, cursor + span)})
                cursor += span
        words = [{**w, "text": _escape(w["text"])} for w in words]

        preset = (
            chon_preset_tu_dong(" ".join(w["text"] for w in words), c_idx)
            if settings.preset == "tu_dong" else settings.preset
        )
        cum = phan_tich_cum_phu_de(words, start, max(100, end - start), preset=preset, base_font_size=base, portrait=portrait)
        n_words = len(cum.words)

        # Ước lượng bề ngang từng dòng, thu nhỏ đều cả cụm nếu tràn lề.
        by_line: dict[int, float] = {}
        for tw in cum.words:
            by_line[tw.line_index] = by_line.get(tw.line_index, 0) + _uoc_luong_rong(
                tw.text, tw.font_size * (1.16 if tw.is_pill else 1.0), tw.is_uppercase, tw.tracking) + tw.font_size * 0.27
        widest = max(by_line.values()) if by_line else 0
        fit = min(1.0, max(0.55, avail * 0.96 / widest)) if widest > 0 else 1.0

        left = settings.layout == "left" or preset == "inline_pop_trai"

        def format_state(active_i: int, prev_i: int | None = None, cum=cum, fit=fit, preset=preset,
                         n_words=n_words, left=left) -> str:
            lines: dict[int, list[str]] = {}
            for k, tw in enumerate(cum.words):
                st = "PAST" if (active_i == 999 or k < active_i) else ("ACTIVE" if k == active_i else "FUTURE")
                fs = max(24, round(tw.font_size * fit))
                bord, shad = max(3, round(fs * 0.07)), max(1, round(fs * 0.03))
                base_col = muted if tw.muted else COLOR_ASS_MAP.get(tw.role, white)
                outline, alpha_out = COLOR_ASS_DARK_OUTLINE, "00"
                if tw.is_pill:
                    bord, shad = max(6, round(fs * 0.2)), 0
                    outline = COLOR_ASS_PILL_RED
                    base_col = white
                alpha = "&H99&" if st == "FUTURE" else "&H00&"
                if st == "FUTURE" and tw.is_pill:
                    alpha_out = "99"
                col = base_col
                a2 = alpha
                # Từ không phải đang đọc: \k0 để libass không gộp vào hiệu ứng quét \kf của từ trước đó.
                anim = r"\fscx100\fscy100\k0"
                if st == "ACTIVE":
                    nxt_ms = words[k + 1]["start_ms"] if k + 1 < n_words else end
                    dur = max(1, round((max(nxt_ms, words[k]["start_ms"] + 10) - words[k]["start_ms"]) / 10))
                    if not tw.is_pill and (tw.muted or tw.role == "NORMAL_WHITE"):
                        col = accent
                    # Từ đến lượt: nở dần 100 -> POP% và sáng dần từ mờ trong TWEEN ms (không nhảy bậc).
                    alpha, a2 = "&H99&", "&H00&"
                    anim = rf"\fscx100\fscy100\t(0,{TWEEN},\fscx{POP}\fscy{POP}\1a&H00&)\kf{dur}"
                elif prev_i is not None and k == prev_i:
                    # Từ vừa đọc xong: thu về cỡ thường dần.
                    anim = rf"\fscx{POP}\fscy{POP}\t(0,{TWEEN},\fscx100\fscy100)\k0"
                text = tw.text.upper() if tw.is_uppercase else tw.text
                lines.setdefault(tw.line_index, []).append(
                    # \2c/\2a: màu "chưa hát tới" của libass. Đặt bằng màu chính để từ chưa đọc không bị trắng đặc;
                    # riêng từ đang đọc thì quét từ màu gốc sang màu nhấn.
                    "{" + rf"\fs{fs}\1c{col}\1a{alpha}\2c{base_col if st == 'ACTIVE' else col}\2a{a2}"
                    rf"\3c{outline}\3a&H{alpha_out}&\bord{bord}\shad{shad}\fsp{tw.tracking}{anim}"
                    + "}" + text)
            return r"\N".join(" ".join(lines[i]) for i in sorted(lines))

        ml, mr, an = (margin_left_pop, margin_h, r"{\an1}") if left else (0, 0, "")
        # Chuỗi sự kiện (bắt đầu, kết thúc, từ đang đọc, từ vừa đọc xong); sự kiện đầu mờ dần vào, cuối mờ dần ra.
        spans: list[tuple[int, int, int, int | None]] = []
        for i in range(n_words):
            w_start = words[i]["start_ms"]
            w_end = max(words[i]["end_ms"], w_start + 30)
            prev = i - 1 if i > 0 else None
            if i + 1 < n_words:
                nxt_s = words[i + 1]["start_ms"]
                if nxt_s <= w_start:
                    nxt_s = w_start + 120
                if nxt_s > w_end + 120:
                    spans.append((w_start, w_end, i, prev))
                    spans.append((w_end, nxt_s, 999, i))
                else:
                    spans.append((w_start, nxt_s, i, prev))
            else:
                spans.append((w_start, w_end, i, prev))
                if end > w_end + 30:
                    spans.append((w_end, end, 999, i))
        for j, (s_ms, e_ms, act, prv) in enumerate(spans):
            fade = ""
            if j == 0:
                fade = r"{\fad(" + str(FADE_IN) + ",0)}"
            elif j == len(spans) - 1:
                fade = r"{\fad(0," + str(FADE_OUT) + ")}"
            event_lines.append(
                f"Dialogue: 0,{_ts(s_ms)},{_ts(e_ms)},Karaoke,,{ml},{mr},0,,{an}{fade}{format_state(act, prv)}")

    return "\n".join(header_lines + event_lines) + "\n"
