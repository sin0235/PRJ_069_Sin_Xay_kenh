"""Phụ đề ASS kiểu karaoke tô từ (chữ lớn, viền đen, đổ bóng, từ đang đọc đổi màu)."""
from __future__ import annotations

import textwrap

from src.schemas.contracts import KaraokeCaptionSettings


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
    size = round(height * settings.font_size / 1920)
    margin_v = round(height * (0.17 if portrait else 0.08))
    margin_h = round(max(width * 0.08, height * 120 / 1920))
    outline = round(size * 0.09, 1) if settings.outline else 0
    shadow = round(size * 0.04, 1) if settings.shadow else 0
    alignment = 1 if settings.layout == "left" else 2
    limit = round((18 if portrait else 34) * 56 / settings.font_size)
    primary_color = {
        "champagne": "&H006AB2D9",
        "baha_blue": "&H00D65724",
        "coral": "&H006871F0",
    }[settings.accent_color]
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Karaoke,{font_family},{size},{primary_color},&H00FFFFFF,&H00000000,&H99000000,0,0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},{margin_h},{margin_h},{margin_v},1",
        "", "[Events]", "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for cap in captions:
        get = (lambda k, d=None: cap.get(k, d)) if isinstance(cap, dict) else (lambda k, d=None: getattr(cap, k, d))
        start, end = int(get("start_ms", 0)), int(get("start_ms", 0)) + int(get("duration_ms", 0))
        words = [{"text": w["text"], "start_ms": w["start_ms"], "end_ms": w["end_ms"]} if isinstance(w, dict)
                 else {"text": w.text, "start_ms": w.start_ms, "end_ms": w.end_ms} for w in (get("words") or [])]
        if not words:
            plain_words = _escape(get("text", "")).split()
            if settings.layout == "two_line":
                split_at = _break_index(plain_words, 1)
                text = " ".join(plain_words)
                if split_at:
                    text = " ".join(plain_words[:split_at]) + "\\N" + " ".join(plain_words[split_at:])
            else:
                text = "\\N".join(textwrap.wrap(" ".join(plain_words), limit))
            body = f"{{\\1c&H00FFFFFF&}}{text}" if text else ""
        else:
            texts = [_escape(w["text"]) for w in words]
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
            lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Karaoke,,0,0,0,,{{\\fad(80,60)}}{body}")
    return "\n".join(lines) + "\n"
