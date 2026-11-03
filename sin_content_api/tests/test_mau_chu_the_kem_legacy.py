"""Cảnh sơ đồ (diagram_scene.html): chữ vẽ trên thẻ giấy nền kem phải dùng màu chữ tối, không dùng COL.ink (#F2EEE6, màu sáng cho nền tối)."""
import re
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "src/modules/tao_video_noi_dung/diagram_scene.html").read_text(encoding="utf-8")


def test_card_ink_is_dark_and_ink_is_light():
    assert 'ink: "#F2EEE6"' in SOURCE and 'cardInk: "#1b2a41"' in SOURCE


def test_kpi_and_process_rail_card_text_uses_dark_ink():
    for name in ("sceneKpi", "sceneProcessRail"):
        body = SOURCE[SOURCE.index(f"function {name}("):]
        body = body[:body.index("\nfunction ", 10)] if "\nfunction " in body[10:] else body
        texts = re.findall(r"<text[^>]*fill=\"' \+ (COL\.\w+) \+ '\"", body)
        assert "COL.cardInk" in texts, name
