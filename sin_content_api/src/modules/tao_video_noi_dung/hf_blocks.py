"""Kho khối dựng sẵn của HyperFrames (registry chính thức, Apache-2.0, HeyGen) nối vào cảnh dựng bằng mã.

Mỗi khối là một sub-composition có biến (`data-composition-variables`) và đọc giá trị qua `window.__hyperframes.getVariables()`.
Ở đây khối được: (1) bỏ phần tải GSAP và font từ CDN (dự án dùng GSAP cục bộ và font Be Vietnam Pro có dấu tiếng Việt),
(2) đổi định danh theo từng lần dùng để nhiều lần dùng trong một video không đè nhau, (3) khoác bảng màu thương hiệu qua biến CSS.

Hai cách dùng:
- Cảnh kể chuyện: `BLOCK_SCENES[layout]` gồm vài biến thể khối; `scene_composition()` chọn một biến thể ổn định theo nội dung
  rồi điền biến từ `diagram`. Cùng layout ở hai video khác nhau cho vẻ ngoài khác nhau mà cùng nội dung vẫn ra cùng kết quả.
- Lớp phủ và chuyển cảnh: `overlay()` cho nền động, hạt phim, rò sáng... đặt chồng lên cảnh.
Danh sách khối đã kiểm bằng ảnh chụp nằm trong blocks/catalog.json (xem tools_catalog)."""
from __future__ import annotations

import html
import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

BLOCKS_DIR = Path(__file__).resolve().parents[3] / "engines" / "hyperframes" / "blocks"
CATALOG_FILE = BLOCKS_DIR / "catalog.json"

# Biến CSS mà các khối đọc (--fg, --bg, --brand, --accent...). Bảng màu khớp "Origami Editorial Motion B2B v1": navy, ngà, ngọc lam, vàng, đỏ san hô.
THEME_STYLE = ("--bg:#0a1c2b;--fg:#f6efe0;--surface:#12324a;--border:rgba(255,255,255,.16);--brand:#ffd54a;--accent:#5cc8c0;"
               "--accent-2:#e8695a;--muted:#9fb4c4;--font-display:'Viet',sans-serif;--font-body:'Viet',sans-serif;--font-mono:'Viet',monospace")
_CDN_GSAP = re.compile(r'<script[^>]+src="https://cdn\.jsdelivr\.net/npm/gsap@[^"]+/(?:gsap|CustomEase)\.min\.js"[^>]*></script>\s*')   # CustomEase nạp cục bộ ở index
_CDN_FONT = re.compile(r'<link[^>]+fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*')

# Chữ mẫu tiếng Anh có sẵn trong mã khối -> tiếng Việt (khối không có biến cho các chữ này).
_VIETNAMESE_TEXT: dict[str, dict[str, str]] = {
    "overwhelm-surround": {
        "Inbox": "Hộp thư", "Due": "Hạn chót", "@you": "@bạn", "ASAP": "GẤP", "Review": "Duyệt", "Call": "Gọi lại", "3 pings": "3 tin", "Sync": "Đồng bộ",
        "Today": "Hôm nay", "Reply": "Trả lời", "8 tabs": "8 tab", "Update": "Cập nhật", "Now": "Ngay", "Draft": "Soạn", "4 alerts": "4 cảnh báo",
        "Fix": "Sửa", "Follow up": "Theo dõi", "Queue": "Hàng chờ", "2 min": "2 phút", "Waiting": "Đang chờ",
    },
    "notification-pileup": {
        "Messages": "Tin nhắn", "Can you take a quick look?": "Anh xem giúp em một chút?", "Calendar": "Lịch", "Stand-up moved to 10:30": "Họp giao ban dời sang 10:30",
        "Mail": "Thư", "Five new replies in your thread": "Năm phản hồi mới trong chuỗi", "Updates": "Cập nhật", "A new version is ready": "Có bản mới cần duyệt",
        "Tasks": "Công việc", "Deadline changed to today": "Hạn nộp đổi sang hôm nay", "Drive": "Kho tệp", "Someone requested access": "Có người xin quyền truy cập",
        "Security": "Bảo mật", "New sign-in needs review": "Đăng nhập mới cần duyệt", "Social": "Mạng xã hội", "You have twelve new mentions": "Mười hai lượt nhắc mới",
        "Notes": "Ghi chú", "Shared checklist was updated": "Danh sách chung vừa đổi", "Reminders": "Nhắc việc", "Follow up before end of day": "Theo dõi trước cuối ngày",
    },
}


def block_path(name: str) -> Path:
    path = BLOCKS_DIR / f"{name}.html"
    if not path.is_file():
        raise FileNotFoundError(f"HYPERFRAMES_BLOCK_MISSING:{name}")
    return path


def prepare_block(name: str, cid: str, duration: float | None = None, literals: dict[str, str] | None = None) -> str:
    """Mã khối cho MỘT lần dùng: bỏ CDN, đổi định danh `name` thành `cid`. Khối đọc độ dài D từ `data-duration` của chính nó
    (không lấy từ thẻ host) nên phải ghi D thật vào đó, nếu không khối thoát cảnh theo độ dài mặc định."""
    text = block_path(name).read_text(encoding="utf-8")
    text = _CDN_GSAP.sub("", text)
    text = _CDN_FONT.sub("", text)
    if duration is not None:
        text = re.sub(r'(data-(?:composition-)?duration=")[\d.]+(")', lambda m: f"{m.group(1)}{duration:.3f}{m.group(2)}", text)
        # Khi chạy, runtime không để lại data-duration trên #root nên khối rơi về giá trị mặc định trong mã: `dataset.duration || "3.5"`.
        text = re.sub(r'(dataset\.duration\s*\|\|\s*")[\d.]+(")', lambda m: f"{m.group(1)}{duration:.3f}{m.group(2)}", text)
    for english, vietnamese in _VIETNAMESE_TEXT.get(name, {}).items():
        text = text.replace(f'"{english}"', f'"{vietnamese}"')
    for old, new in (literals or {}).items():   # chữ cố định trong mã khối mà khối không có biến: thay bằng nội dung của cảnh
        if old not in text:
            raise ValueError(f"HYPERFRAMES_BLOCK_LITERAL_MISSING:{name}:{old[:30]}")
        text = text.replace(old, new)   # new do hàm dựng literals tự escape phần nội dung
    return re.sub(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9_])", cid, text)


def host_attrs(variables: dict | None = None) -> str:
    """Thuộc tính thêm cho thẻ host: giá trị biến của khối (JSON trong dấu nháy đơn)."""
    if not variables:
        return ""
    return " data-variable-values='" + json.dumps(variables, ensure_ascii=False).replace("&", "&amp;").replace("'", "&#39;") + "'"


def load_catalog() -> dict:
    try:
        return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"blocks": {}}


def _words(text: str) -> list[str]:
    return text.split()


def _accent_index(title: str, tag: str | None) -> int:
    """Chỉ số chữ cần nhấn trong tiêu đề: chữ đầu tiên của `tag` nằm trong title; không có thì chữ cuối."""
    words = _words(title)
    if tag:
        first = _words(tag)[0].casefold().strip(".,!?:;") if _words(tag) else ""
        for index, word in enumerate(words):
            if word.casefold().strip(".,!?:;") == first:
                return index
    return max(0, len(words) - 1)


@dataclass(frozen=True)
class Variant:
    block: str
    variables: Callable[[dict], dict]
    max_chars: int = 999   # khối cỡ chữ cố định chỉ hợp tiêu đề ngắn
    literals: Callable[[dict], dict] | None = None   # chữ cố định trong mã khối cần thay theo nội dung cảnh


def _num(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _headline(d):
    return {"text": d["title"], "accent_word_index": _accent_index(d["title"], d.get("tag")), "accent": "green", "shadow": True}


def _plain(d):
    return {"text": d["title"], "accent": "green", "spread": "tight"}


def _shutter(d):
    return {"text": d["title"].upper(), "accent": "green", "blur": "shutter", "exit": "none"}


def _mark(style):
    def build(d):
        return {"text": d["title"], "emphasis_word": d.get("tag") or d["title"].split()[-1], "style": style, "draw_at": 0.9, "accent": "violet", "exit": "none"}
    return build


def _vox(d):
    return {"text": d["title"], "keyword": d.get("tag") or d["title"].split()[-1], "note": d.get("caption") or "", "style": "highlight", "draw_at": 0.9, "accent": "violet", "exit": "none"}


def _swap(d):
    options = list(d.get("steps") or [])
    return {"prefix": d["title"], "options": ",".join(options), "suffix": d.get("caption") or "", "accent": "green", "exit": "none"}


def _overwhelm(d):
    return {"count": int(min(24, max(8, _num(d.get("value"), 16)))), "centerLabel": d["title"][:14], "intensity": 1}


def _notify(d):
    return {"count": int(min(12, max(5, _num(d.get("value"), 8)))), "speed": 1, "showBadges": "yes"}


def _ring(d):
    value = _num(d.get("to_value"), _num(d.get("value"), 60))
    return {"progress": int(min(100, max(0, value))), "thickness": 14, "label": f'{int(min(100, max(0, value)))}%'}


def _chart(kind):
    def build(d):
        series = (d.get("series") or [{}])[0]
        values = [str(round(v, 1)).rstrip("0").rstrip(".") for v in series.get("values", [])]
        labels = list(d.get("labels") or [])
        return {"type": kind, "data": ", ".join(values), "labels": ", ".join(labels), "emphasize": max(0, len(values) - 1), "unit": d.get("unit") or "", "accent": "green", "exit": "none"}
    return build


def _titlecard(d):
    return {"headline": d["title"], "kicker": (d.get("caption") or d.get("tag") or "").upper()}


def _center_build(d):
    return {"text": d["title"], "font_size": 96, "color": "#f6efe0", "font_weight": "700"}


def _rank(d):
    steps = list(d.get("steps") or [])
    return {"prompt": d["title"], "lead": d.get("caption") or "Đây là các gợi ý hàng đầu:", "rowA": steps[0], "rowB": steps[1], "rowC": steps[2],
            "brand": d.get("tag") or "Doanh nghiệp bạn", "brandRank": str(int(d.get("pick") or 0) + 1), "accent": "#e8a50a", "ink": "#16283d", "ground": "#fbf3df"}


def _drag(d):
    return {"card_label": d["steps"][0], "accent": "#e8a50a", "tone": "dark"}


def _e(value) -> str:
    return html.escape(str(value), quote=False)


def _drag_literals(d):
    steps, days = [_e(s) for s in d["steps"]], ("T2", "T3", "T4")
    chip = "Việc"
    return {
        "To do <span": f"{_e(d['title'])} <span", "In progress <span": f"{_e(d.get('caption') or 'Đang làm')} <span",
        '--chip: #d9480f">Marketing<': f'--chip: #d9480f">{chip}<', '--chip: #2b8a3e">Video<': f'--chip: #2b8a3e">{chip}<',
        '--chip: #1971c2">Docs<': f'--chip: #1971c2">{chip}<', '--chip: #c2255c">Bug<': '--chip: #c2255c">Gấp<',
        "Draft onboarding email": steps[1], "Record product walkthrough": steps[2], "Update pricing FAQ": steps[3],
        "Thu <span": f"{days[0]} <span", "Mon <span": f"{days[1]} <span", "Tue <span": f"{days[2]} <span", "Today <span": "Nay <span",
    }


def _shift(d):
    steps = list(d["steps"])
    return {"label_a": steps[0], "label_b": steps[1], "accent": "green"}


def _shift_literals(d):
    return {"</span>Workspace</span>": f"</span>{_e(d['title'])}</span>"}


def _match_cut(d):
    words = d["title"].split()
    half = max(1, len(words) // 2)
    return {"text_a": " ".join(words[:half]), "text_b": d["title"], "mode": "scale-down", "sweep": "on", "background": "transparent"}


# layout -> các biến thể khối (chọn một theo nội dung). Chỉ liệt kê khối đã dựng và xem bằng ảnh chụp (xem blocks/catalog.json).
BLOCK_SCENES: dict[str, list[Variant]] = {
    "KINETIC_TITLE": [Variant("headline-slam", _headline, 14), Variant("char-slam-explode", _plain, 16), Variant("shutter-slam", _shutter, 22), Variant("titlecard-calm", _titlecard),
                      Variant("kinetic-center-build", _center_build), Variant("text-match-cut", _match_cut)],
    "MARK_PHRASE": [Variant("marker-highlight", _mark("highlight")), Variant("marker-highlight", _mark("circle")), Variant("vox-annotate", _vox), Variant("marker-highlight", _mark("underline"))],
    "WORD_SWAP": [Variant("kinetic-type-swap", _swap)],
    "PILE_UP": [Variant("overwhelm-surround", _overwhelm)],
    "STAT_RING": [Variant("conic-progress-ring", _ring)],
    "CHART_STORY": [Variant("chart-story", _chart("bars")), Variant("chart-story", _chart("line"))],
    "AI_RANK": [Variant("ai-answer-rank", _rank)],
    "DRAG_TASKS": [Variant("cursor-drag-drop", _drag, literals=_drag_literals)],
    "CARD_SHIFT": [Variant("focus-rack", _shift, literals=_shift_literals)],
}


# hệ số phóng cảnh khối ở khung 9:16 (đã xem bằng ảnh chụp)
PORTRAIT_SCALE = {"MARK_PHRASE": 1.5, "WORD_SWAP": 1.5, "CHART_STORY": 1.25}
SQUARE_BLOCKS = ("AI_RANK",)   # ai-answer-rank vẽ trong khung vuông 1080x1080


def pick_variant(layout: str, data: dict) -> Variant:
    variants = [v for v in BLOCK_SCENES[layout] if len(str(data.get("title") or "")) <= v.max_chars] or BLOCK_SCENES[layout][-1:]
    key = json.dumps([layout, data.get("title"), data.get("tag")], ensure_ascii=False, sort_keys=True)
    return variants[zlib.crc32(key.encode("utf-8")) % len(variants)]


def scene_composition(layout: str, cid: str, data: dict, duration: float | None = None) -> tuple[str, str, str]:
    """(mã composition, thuộc tính host, style host) cho một cảnh khối; style host mang bảng màu thương hiệu."""
    variant = pick_variant(layout, data)
    scale = PORTRAIT_SCALE.get(layout, 1.0) if data.get("portrait") else 1.0   # khung 9:16 hẹp hơn nên khối cỡ chữ theo chiều ngang trông nhỏ
    style = THEME_STYLE + (f";transform:scale({scale});transform-origin:50% 50%" if scale != 1.0 else "")
    if layout in SQUARE_BLOCKS:   # khối vuông 1080x1080 đặt giữa khung
        style += ";transform:translate(0,420px)" if data.get("portrait") else ";transform:translate(420px,0)"
    return prepare_block(variant.block, cid, duration, variant.literals(data) if variant.literals else None), host_attrs(variant.variables(data)), style
