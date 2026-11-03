"""Thẻ nền kem trong cảnh HyperFrames phải có màu chữ tối riêng; mặc định của cảnh là chữ sáng cho nền tối (chữ sáng trên thẻ kem thì không đọc được)."""
import re

from src.modules.tao_video_noi_dung import hf_scenes

SOURCE = open(hf_scenes.__file__, encoding="utf-8").read()
CREAM_CARDS = (".qc", ".cl", ".ba", ".hn", ".tc", ".ec")


def _rule(selector):
    match = re.search(r"@@S@@ " + re.escape(selector) + r"\{([^{}]*)\}", SOURCE)
    assert match, selector
    return match.group(1)


def test_base_text_is_light_for_dark_backgrounds():
    assert "color:#F2EEE6" in SOURCE


def test_every_cream_card_sets_a_dark_text_color():
    for selector in CREAM_CARDS:
        body = _rule(selector)
        assert re.search(r"(?<![-a-z])color:#1b2a41", body), f"{selector} thiếu màu chữ tối"
