"""Thư viện SFX nội bộ và lịch phát theo hành động đang hiện trên hình."""
from __future__ import annotations

import unicodedata
from pathlib import Path

from .planner import DIAGRAM_LAYOUTS, resolve_diagram_times


_DIR = Path(__file__).with_name("am_thanh_hoat_hoa")
_VOLUME = {
    "xe_giay": .24, "soat_giay": .18, "lat_trang": .20, "go_phim": .18,
    "cho_nhe": .18, "tang_nhip": .12, "tach_nhe": .20, "luot_nhanh": .18,
    "luot_nhe": .16, "xac_nhan": .15, "nhap_chuot": .16, "nhap_chuot_doi": .16,
    "go_nhe": .17, "bat_mo": .18, "viet_but": .16, "dong_dau": .18,
    "thong_bao": .15, "thanh_cong": .14, "canh_bao": .14, "tich_tac": .16,
    "nhap_nut_nhe": .14, "nhap_nut_manh": .13, "ui_mo": .13, "ui_dong": .13,
    "ui_tha": .12, "ui_cuon": .12, "ui_phong_to": .12, "ui_thu_nho": .12,
    "ui_loi": .12, "ui_xac_nhan": .12, "ui_chon": .13, "ui_vet_but": .12,
}
SFX_LIBRARY = tuple(
    {"id": sound_id, "path": _DIR / f"{sound_id}.wav", "volume": volume}
    for sound_id, volume in _VOLUME.items()
)

_ACTIONS = (
    ("xe_giay", ("xé giấy", "xé tờ", "xé tài liệu", "tear paper", "rip paper")),
    ("soat_giay", ("soạt giấy", "sột soạt", "paper rustle")),
    ("lat_trang", ("lật trang", "mở hồ sơ", "mở tài liệu", "turn page")),
    ("go_phim", ("gõ phím", "bàn phím", "đánh máy", "nhập liệu", "type on keyboard")),
    ("nhap_nut_nhe", ("nhấn nút nhẹ", "soft interface click")),
    ("nhap_nut_manh", ("nhấn nút mạnh", "hard interface click")),
    ("nhap_chuot_doi", ("nhấp đúp", "double click")),
    ("nhap_chuot", ("nhấp chuột", "click chuột", "bấm nút", "nhấn nút", "click the button")),
    ("viet_but", ("viết bằng bút", "ghi chú", "ký tên", "vẽ bằng bút", "write with a pen")),
    ("dong_dau", ("đóng dấu", "đóng mộc", "stamp the document")),
    ("ui_loi", ("lỗi giao diện", "interface error")),
    ("ui_xac_nhan", ("âm báo xác nhận", "confirmation tone")),
    ("ui_chon", ("chọn mục giao diện", "select interface item")),
    ("ui_mo", ("mở cửa sổ giao diện", "mở giao diện", "open interface window")),
    ("ui_dong", ("đóng cửa sổ giao diện", "đóng giao diện", "close interface window")),
    ("ui_tha", ("thả thẻ giao diện", "thả mục giao diện", "drop interface card")),
    ("ui_cuon", ("cuộn trang giao diện", "cuộn bảng", "scroll interface")),
    ("ui_phong_to", ("phóng to cửa sổ", "phóng to bảng", "maximize window")),
    ("ui_thu_nho", ("thu nhỏ cửa sổ", "thu nhỏ bảng", "minimize window")),
    ("ui_vet_but", ("vệt bút giao diện", "gạch chân giao diện", "interface scratch")),
    ("canh_bao", ("cảnh báo", "báo lỗi", "lỗi xuất hiện", "alert appears")),
    ("thanh_cong", ("hoàn tất", "thành công", "xác nhận xong", "task complete")),
    ("thong_bao", ("thông báo xuất hiện", "notification appears")),
    ("bat_mo", ("bật lên", "thẻ hiện ra", "hộp thoại xuất hiện", "pop up")),
    ("luot_nhanh", ("quét nhanh", "lướt vụt", "whip pan")),
    ("luot_nhe", ("trượt vào", "lướt qua", "chuyển động lướt", "swoosh")),
    ("tang_nhip", ("dồn nhịp", "cao trào", "build tension")),
    ("cho_nhe", ("chờ xử lý", "đang tải", "loading")),
    ("tach_nhe", ("chạm nhẹ", "nhấn nhẹ", "light tap")),
)

_DIAGRAM_SOUNDS = {
    ("CHECKLIST", "stamp"): "dong_dau",
    ("BEFORE_AFTER", "before"): "cho_nhe",
    ("BEFORE_AFTER", "after"): "luot_nhe",
    ("BEFORE_AFTER", "delta"): "thanh_cong",
    ("HUB_SPOKE", "hub"): "nhap_chuot",
    ("HUB_SPOKE", "link"): "tach_nhe",
    ("OPEN_QUESTION", "ask"): "luot_nhe",
    ("OPEN_QUESTION", "key"): "thong_bao",
    ("OPEN_HOOK", "start"): "luot_nhanh",
    ("OPEN_HOOK", "hit"): "tach_nhe",
    ("END_CARD", "fold"): "xe_giay",
    ("END_CARD", "cta"): "xac_nhan",
    ("FUNNEL", "leak"): "canh_bao",
    ("COMPARE_DOCS", "doc0"): "lat_trang",
    ("COMPARE_DOCS", "doc1"): "lat_trang",
    ("COMPARE_DOCS", "thread"): "soat_giay",
}


def _value(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def _plain(text: str) -> str:
    value = unicodedata.normalize("NFD", text.casefold())
    return "".join(char for char in value if unicodedata.category(char) != "Mn").replace("đ", "d")


def _action_sound(action: str) -> str | None:
    text = _plain(action)
    for sound_id, phrases in _ACTIONS:
        if any(_plain(phrase) in text for phrase in phrases):
            return sound_id
    return None


def _diagram_sound(layout: str, event: str) -> str | None:
    sound = _DIAGRAM_SOUNDS.get((layout, event))
    if sound:
        return sound
    if event == "stamp":
        return "dong_dau"
    if event in {"flag", "alert", "leak", "block"}:
        return "canh_bao"
    if event in {"hit", "final", "delta", "release", "cta", "verdict", "after", "top", "label"}:
        return "thanh_cong"
    if event.startswith(("c", "k", "m", "n", "a", "v")) and event[1:].isdigit():
        return "tich_tac" if layout == "TIMELINE" else "go_nhe"
    if event in {"doc0", "doc1", "v0", "v1", "layers", "explode", "thread"}:
        return "soat_giay"
    if event in {"target", "needle", "line", "ring", "dial", "hub", "key", "found"}:
        return "thong_bao"
    if event in {"stages", "stations", "sources", "uses", "nodes", "cards", "bars", "rows", "levels"}:
        return "bat_mo"
    return None


def plan_sfx_cues(shots, durations: list[float] | None = None, word_times_by_shot=None) -> list[dict]:
    """Tạo cue chỉ khi storyboard nêu hành động có thể nghe thấy hoặc phần tử động vừa xuất hiện."""
    library = {item["id"]: item for item in SFX_LIBRARY}
    cues, offset, seen = [], 0.0, set()
    for index, shot in enumerate(shots):
        duration = float(durations[index] if durations and index < len(durations) else _value(shot, "duration_seconds", 0))
        scene = _value(shot, "ui_scene")
        events = {}
        if scene and _value(scene, "layout") in DIAGRAM_LAYOUTS:
            events = resolve_diagram_times(
                scene,
                _value(shot, "narration", ""),
                duration,
                word_times_by_shot[index] if word_times_by_shot and index < len(word_times_by_shot) else None,
            )
            for event, at in events.items():
                sound_id = _diagram_sound(_value(scene, "layout"), event)
                _append(cues, seen, library, sound_id, offset + at, _value(shot, "shot_id"), event)
        elif scene:
            for message in _value(scene, "messages", []):
                sound_id = "go_phim" if _value(message, "role") in {"ai", "staff"} else "bat_mo"
                _append(cues, seen, library, sound_id, offset + float(_value(message, "at_s", 0)), _value(shot, "shot_id"), "message")
        else:
            for beat in _value(shot, "action_beats", []):
                sound_id = _action_sound(_value(beat, "action", ""))
                _append(cues, seen, library, sound_id, offset + float(_value(beat, "start_s", 0)), _value(shot, "shot_id"), _value(beat, "action", ""))
        offset += duration
    return cues


def transition_sfx_cues(boundaries: list[float], sound_id: str = "luot_nhe") -> list[dict]:
    item = next((sound for sound in SFX_LIBRARY if sound["id"] == sound_id), None)
    if not item or not item["path"].is_file():
        return []
    return [
        {"sound_id": item["id"], "path": Path(item["path"]), "start_seconds": max(0.0, round(at - .15, 3)), "volume": item["volume"]}
        for at in boundaries
    ]


def _append(cues, seen, library, sound_id, at, shot_id, action):
    if sound_id not in library:
        return
    key = (sound_id, round(at, 3))
    if key in seen:
        return
    seen.add(key)
    item = library[sound_id]
    if not item["path"].is_file():
        return
    cues.append({
        "sound_id": sound_id,
        "path": Path(item["path"]),
        "start_seconds": round(max(0.0, at), 3),
        "volume": item["volume"],
        "shot_id": shot_id,
        "action": action,
    })
