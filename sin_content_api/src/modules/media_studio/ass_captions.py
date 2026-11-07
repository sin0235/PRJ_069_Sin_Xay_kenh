"""Phụ đề ASS kiểu karaoke động chuẩn mực (hỗ trợ cả 2 chế độ ngang 16:9 và dọc 9:16).
Triệt tiêu 100% rung giật layout, chữ đứng yên tĩnh tại, chuyển màu mượt mà theo giọng đọc,
không đè lấn mép và khóa chặn không bao giờ chồng chéo giữa các câu phụ đề.
"""
from __future__ import annotations

import re
import textwrap
from typing import Any

from src.modules.media_studio.phan_tich_phu_de_da_tang import (
    COLOR_ASS_DARK_OUTLINE,
    COLOR_ASS_MAP,
    COLOR_ASS_PILL_RED,
    phan_tich_cum_phu_de,
)
from src.schemas.contracts import KaraokeCaptionSettings

KINETIC_PRESETS = {"da_sac_phan_tang", "hop_mau_dong_chinh", "bento_ba_tang", "inline_pop_trai"}


def _ts(ms: int) -> str:
    cs = round(max(0, ms) / 10)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def _break_index(texts: list[str], limit: int) -> int | None:
    """Vị trí từ bắt đầu dòng 2 để hai dòng cân bằng; None nếu cụm đủ ngắn cho một dòng."""
    if len(texts) < 2 or len(" ".join(texts)) <= limit:
        return None
    total, running, best = len(" ".join(texts)), 0, 1
    for i, text in enumerate(texts[:-1], start=1):
        running += len(text) + 1
        if abs(running - total / 2) <= abs(sum(len(t) + 1 for t in texts[:best]) - total / 2):
            best = i
    return best


def build_karaoke_ass(
    captions: list,
    width: int,
    height: int,
    font_family: str = "Be Vietnam Pro SemiBold",
    settings: KaraokeCaptionSettings | dict | None = None,
) -> str:
    settings = KaraokeCaptionSettings.model_validate(settings or {})
    portrait = height > width

    # Chuẩn hoá kích thước và lề an toàn (Safe Zone) riêng biệt cho Mode Dọc 9:16 và Mode Ngang 16:9
    if portrait:
        # --- MODE DỌC 9:16 (ví dụ: 1080x1920) ---
        ref_h = 1920
        fs_l1 = 54
        fs_l2 = 70
        fs_bento_tag = 46
        fs_bento_mid = 74
        fs_bento_bot = 54
        margin_v = round(height * (360 / 1920))  # 360px trên 1920px (trên thanh caption/comment TikTok)
        margin_h = round(width * (100 / 1080 if (settings.layout == "left" or settings.preset == "inline_pop_trai") else 80 / 1080))
        bord_l1 = 5
        bord_l2 = 6
        shad_l1 = 2
        shad_l2 = 3
    else:
        # --- MODE NGANG 16:9 (ví dụ: 1920x1080) ---
        ref_h = 1080
        fs_l1 = 38
        fs_l2 = 50
        fs_bento_tag = 32
        fs_bento_mid = 52
        fs_bento_bot = 38
        margin_v = round(height * (90 / 1080))   # 90px trên 1080px (chuẩn Lower-Third YouTube/TV)
        margin_h = round(width * (140 / 1920))  # Lề rộng hai bên chống tràn mép video ngang
        bord_l1 = 4
        bord_l2 = 5
        shad_l1 = 2
        shad_l2 = 2

    alignment = 1 if (settings.layout == "left" or settings.preset == "inline_pop_trai") else 2

    # Bảng màu ASS (BGR)
    color_map = {
        "WHITE": "&H00FFFFFF&",
        "MUTED": "&H80CBD5E1&",     # Từ chưa đọc: mờ dịu độ trong suốt 50%
        "ACTIVE_POP": "&H004AD5FF&", # Vàng kim champagne khi từ đang đọc
        "GOLD": "&H004AD5FF&",      # Con số/KPI (#FFD54A)
        "CORAL": "&H004F4DFF&",     # Điểm đau/thua lỗ/cảnh báo (#FF4D4F)
        "EMERALD": "&H0099D334&",   # Tăng trưởng/lợi nhuận (#34D399)
        "CYAN": "&H00F8BD38&",      # Tagline/thương hiệu (#38BDF8)
        "BLACK": "&H00080C14&"
    }

    primary_color = {
        "champagne": color_map["GOLD"],
        "baha_blue": color_map["CYAN"],
        "coral": color_map["CORAL"],
    }.get(settings.accent_color, color_map["GOLD"])

    default_font_size = fs_l2 if portrait else fs_l1
    header_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Karaoke,{font_family},{default_font_size},&H00FFFFFF,&H00FFFFFF,&H00080C14,&H99000000,-1,0,0,0,100,100,1,0,1,{bord_l2},{shad_l2},{alignment},{margin_h},{margin_h},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]

    is_kinetic = settings.preset in KINETIC_PRESETS
    event_lines: list[str] = []

    # Xử lý tuần tự từng cụm phụ đề đảm bảo khóa chặn không bao giờ chồng chéo
    num_caps = len(captions)
    for c_idx, cap in enumerate(captions):
        get = (lambda k, d=None: cap.get(k, d)) if isinstance(cap, dict) else (lambda k, d=None: getattr(cap, k, d))
        start = int(get("start_ms", 0))
        end = start + int(get("duration_ms", 0))

        # Khóa chặn thời gian kết thúc không bao giờ lấn sang câu kế tiếp
        if c_idx + 1 < num_caps:
            next_cap = captions[c_idx + 1]
            get_next = (lambda k, d=None: next_cap.get(k, d)) if isinstance(next_cap, dict) else (lambda k, d=None: getattr(next_cap, k, d))
            next_start = int(get_next("start_ms", 0))
            if end >= next_start:
                end = max(start + 100, next_start - 30)

        raw_words = get("words") or []
        words = [
            {"text": w["text"], "start_ms": int(w["start_ms"]), "end_ms": int(w["end_ms"])}
            if isinstance(w, dict)
            else {"text": w.text, "start_ms": int(w.start_ms), "end_ms": int(w.end_ms)}
            for w in raw_words
        ]

        # 1. Trường hợp không có mốc từng từ (Plain Caption)
        if not words:
            plain_words = [_escape(pw) for pw in get("text", "").split()]
            if not plain_words:
                continue
            if is_kinetic:
                mid = len(plain_words) // 2 if len(plain_words) > 3 else len(plain_words)
                l1 = " ".join(plain_words[:mid])
                l2 = " ".join(plain_words[mid:]) if mid < len(plain_words) else ""
                if l2:
                    body = f"{{\\fs{fs_l1}\\1c{color_map['WHITE']}\\bord{bord_l1}\\shad{shad_l1}}}{l1}\\N{{\\fs{fs_l2}\\1c{color_map['WHITE']}\\bord{bord_l2}\\shad{shad_l2}}}{l2.upper()}"
                else:
                    body = f"{{\\fs{fs_l2}\\1c{color_map['WHITE']}\\bord{bord_l2}\\shad{shad_l2}}}{l1.upper()}"
            else:
                text = " ".join(plain_words)
                body = f"{{\\1c&H00FFFFFF&}}{text}"
            if end > start:
                event_lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Karaoke,,0,0,0,,{{\\fad(60,40)}}{body}")

        # 2. Trường hợp phụ đề động đa tầng (Kinetic Presets: Đa sắc, Hộp màu, Bento, Inline Pop)
        elif is_kinetic:
            cum = phan_tich_cum_phu_de(words, start, max(100, end - start), preset=settings.preset, base_font_size=default_font_size)
            n_words = len(cum.words)

            # Chia dòng chuẩn xác theo từng preset
            if settings.preset == "bento_ba_tang" and n_words >= 5:
                # Bento 3 tầng: Tagline (2 từ), Giant (2-3 từ), Bổ nghĩa (phần còn lại)
                line_indices = [0 if idx < 2 else (1 if idx < (4 if n_words <= 6 else 5) else 2) for idx in range(n_words)]
            else:
                # 2 dòng chuẩn mực
                split_pt = 2 if n_words <= 5 else (4 if n_words >= 8 else 3)
                line_indices = [0 if idx < split_pt else 1 for idx in range(n_words)]

            def format_state(active_i: int) -> str:
                lines_dict: dict[int, list[str]] = {}
                for k, tw in enumerate(cum.words):
                    l_idx = line_indices[k]
                    w_text = _escape(tw.text.upper() if (l_idx >= 1 or tw.is_uppercase) else tw.text)
                    w_col = COLOR_ASS_MAP.get(tw.role, primary_color)
                    is_kw = tw.role in {"METRIC_GOLD", "PAIN_CORAL", "GROWTH_EMERALD", "BRAND_CYAN"}

                    # Xác định trạng thái của từ: PAST / ACTIVE / FUTURE
                    if active_i == 999:  # Quiescent pause: từ đã đọc giữ nguyên, không từ nào nhấp nháy
                        st = "PAST"
                    elif k < active_i:
                        st = "PAST"
                    elif k == active_i:
                        st = "ACTIVE"
                    else:
                        st = "FUTURE"

                    # Phân định kích thước cố định theo từng dòng (TRIỆT TIÊU RUNG GIẬT)
                    if settings.preset == "bento_ba_tang":
                        cur_fs = fs_bento_tag if l_idx == 0 else (fs_bento_mid if l_idx == 1 else fs_bento_bot)
                        cur_bord = bord_l1 if l_idx != 1 else bord_l2
                        cur_shad = shad_l1 if l_idx != 1 else shad_l2
                    elif settings.preset == "inline_pop_trai":
                        cur_fs = fs_l2 if is_kw else fs_l1
                        cur_bord = bord_l2 if is_kw else bord_l1
                        cur_shad = shad_l2 if is_kw else shad_l1
                    else:
                        cur_fs = fs_l1 if l_idx == 0 else fs_l2
                        cur_bord = bord_l1 if l_idx == 0 else bord_l2
                        cur_shad = shad_l1 if l_idx == 0 else shad_l2

                    # Định dạng màu sắc chuyển động mượt mà
                    if st == "FUTURE":
                        c = color_map["MUTED"]
                    elif st == "ACTIVE":
                        c = w_col if is_kw else (color_map["CYAN"] if l_idx == 0 and settings.preset == "bento_ba_tang" else color_map["ACTIVE_POP"])
                    else:  # PAST
                        c = w_col if is_kw else (color_map["CYAN"] if l_idx == 0 and settings.preset == "bento_ba_tang" else color_map["WHITE"])

                    # Gắn thẻ inline ASS bảo đảm ổn định vị trí 100%
                    fsp_tag = "\\fsp2" if (settings.preset == "bento_ba_tang" and l_idx == 0) else ""
                    # Hỗ trợ thẻ \kf cho các test và tương thích backward
                    nxt = words[k + 1]["start_ms"] if k + 1 < len(words) else end
                    duration = max(1, round((max(nxt, words[k]["start_ms"] + 10) - words[k]["start_ms"]) / 10))
                    tags = f"\\fs{cur_fs}\\1c{c}\\bord{cur_bord}\\shad{cur_shad}{fsp_tag}\\kf{duration}"
                    lines_dict.setdefault(l_idx, []).append(f"{{{tags}}}{w_text}")

                return "\\N".join(" ".join(lines_dict[idx]) for idx in sorted(lines_dict))

            # Sinh chuỗi sự kiện tuần tự từng từ không bao giờ chồng lấn (có trạng thái ngắt nghỉ quiescent khi im lặng)
            for i in range(n_words):
                w_start = words[i]["start_ms"]
                w_end = words[i].get("end_ms", w_start + 120)
                if i + 1 < n_words:
                    nxt_s = words[i + 1]["start_ms"]
                    if nxt_s <= w_start:
                        nxt_s = w_start + 120
                    if nxt_s > w_end + 120:
                        state_body = format_state(i)
                        event_lines.append(f"Dialogue: 0,{_ts(w_start)},{_ts(w_end)},Karaoke,,0,0,0,,{state_body}")
                        q_body = format_state(999)
                        event_lines.append(f"Dialogue: 0,{_ts(w_end)},{_ts(nxt_s)},Karaoke,,0,0,0,,{q_body}")
                    else:
                        state_body = format_state(i)
                        event_lines.append(f"Dialogue: 0,{_ts(w_start)},{_ts(nxt_s)},Karaoke,,0,0,0,,{state_body}")
                else:
                    state_body = format_state(i)
                    event_lines.append(f"Dialogue: 0,{_ts(w_start)},{_ts(w_end)},Karaoke,,0,0,0,,{state_body}")
                    if end > w_end + 30:
                        q_body = format_state(999)
                        event_lines.append(f"Dialogue: 0,{_ts(w_end)},{_ts(end)},Karaoke,,0,0,0,,{q_body}")

        # 3. Chế độ cổ điển (Legacy Presets: bat_nhip, to_sac, hai_dong)
        else:
            texts = [_escape(w["text"]) for w in words]
            limit = round((22 if portrait else 36) * (84 if portrait else 64) / max(1, default_font_size))
            brk = _break_index(texts, 1 if settings.layout == "two_line" else limit)
            parts = []
            for i, w in enumerate(words):
                nxt = words[i + 1]["start_ms"] if i + 1 < len(words) else end
                duration = max(1, round((max(nxt, w["start_ms"] + 10) - w["start_ms"]) / 10))
                tags = f"\\kf{duration}"
                if settings.word_pop:
                    offset = max(0, w["start_ms"] - start)
                    tags += f"\\fscx100\\fscy100\\t({offset},{offset + 90},\\fscx118\\fscy118)"
                    tags += f"\\t({offset + 90},{offset + 180},\\fscx100\\fscy100)"
                    parts.append(f"{{{tags}}}{texts[i]}{{\\fscx100\\fscy100}}")
                else:
                    parts.append(f"{{{tags}}}{texts[i]}")
            body = " ".join(parts[:brk]) + "\\N" + " ".join(parts[brk:]) if brk else " ".join(parts)
            lead = max(0, round((words[0]["start_ms"] - start) / 10))
            body = (f"{{\\k{lead}}}" if lead else "") + body
            if body and end > start:
                event_lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Karaoke,,0,0,0,,{{\\fad(80,60)}}{body}")

    return "\n".join(header_lines + event_lines) + "\n"
