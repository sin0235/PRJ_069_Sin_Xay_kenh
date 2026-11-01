"""Chữ thương hiệu và từ tiếng Anh: chữ HIỂN THỊ (phụ đề, chữ trong cảnh) giữ nguyên BAHA, Group, video...; chữ ĐỌC (đưa vào TTS và căn mốc từ)
là cách đọc tiếng Việt. Mỗi mục thay đúng một từ bằng đúng một từ (không có khoảng trắng bên trong) nên số từ không đổi: mốc thời gian căn theo
chữ đọc dùng lại được cho chữ hiển thị."""
from __future__ import annotations

import re

# tên hiển thị -> cách đọc. Chỉ thêm từ mà TTS đọc sai khi để nguyên.
LEXICON = {
    "BAHA": "Ba-ha", "Group": "Gờ-rúp", "marketing": "mác-két-ting", "video": "vi-đê-ô", "YouTube": "diu-túp", "Zalo": "Da-lô",
    "Facebook": "Phây-búc", "TikTok": "Tích-tóc", "website": "quép-sai", "email": "i-meo", "online": "on-lai", "offline": "óp-lai",
    "app": "áp", "chatbot": "chát-bót",
}
_BY_LOWER = {name.lower(): (name, spoken) for name, spoken in LEXICON.items()}
_DISPLAY_WORD = re.compile(r"(?<![\w-])(" + "|".join(re.escape(name) for name in sorted(LEXICON, key=len, reverse=True)) + r")(?![\w-])", re.IGNORECASE)
_SPOKEN_FORM = re.compile(r"(?<![\w-])(" + "|".join(re.escape(spoken).replace(r"\-", r"[\s-]?") for spoken in sorted(LEXICON.values(), key=len, reverse=True)) + r")(?![\w-])", re.IGNORECASE)
_BAHA_VARIANT = re.compile(r"(?<![\w-])ba[\s-]?ha(?![\w-])", re.IGNORECASE)
_GROUP_VARIANT = re.compile(r"(?<=BAHA )(?:gờ[\s-]?rúp|gờ[\s-]?rup|grúp|gruup|grup|group)(?![\w-])", re.IGNORECASE)


def to_display(text: str) -> str:
    """Chữ hiển thị: tên thương hiệu luôn là BAHA (và BAHA Group), cách đọc tiếng Việt do LLM hay viết lại được trả về chữ gốc."""
    text = _BAHA_VARIANT.sub("BAHA", text)
    text = _GROUP_VARIANT.sub("Group", text)
    for name, spoken in LEXICON.items():
        if name in ("BAHA", "Group"):
            continue
        text = re.sub(r"(?<![\w-])" + re.escape(spoken).replace(r"\-", r"[\s-]?") + r"(?![\w-])", name, text, flags=re.IGNORECASE)
    return text


def to_spoken(text: str) -> str:
    """Chữ đọc cho TTS và căn mốc từ: BAHA thành Ba-ha, Group thành Gờ-rúp... (mỗi từ vẫn là một từ)."""
    def replace(match: re.Match) -> str:
        return _BY_LOWER[match.group(1).lower()][1]
    return _DISPLAY_WORD.sub(replace, _BAHA_VARIANT.sub("BAHA", text))


def restore_display_words(display_words: list[str], aligned: list[dict]) -> list[dict]:
    """Mốc từ căn theo chữ đọc nhưng phụ đề phải hiện chữ hiển thị; số từ phải bằng nhau (mỗi mục trong LEXICON là một từ)."""
    if len(display_words) != len(aligned):
        return aligned
    return [{**item, "text": word} for word, item in zip(display_words, aligned)]


def display_json(value):
    """Áp to_display cho mọi chuỗi trong một cấu trúc JSON (tiêu đề, nhãn, cụm neo của cảnh giấy)."""
    if isinstance(value, str):
        return to_display(value)
    if isinstance(value, list):
        return [display_json(item) for item in value]
    if isinstance(value, dict):
        return {key: display_json(item) for key, item in value.items()}
    return value
