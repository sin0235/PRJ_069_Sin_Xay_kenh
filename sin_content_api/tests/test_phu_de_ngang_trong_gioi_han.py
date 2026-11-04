"""Cỡ chữ phụ đề video ngang trong runner không được vượt giới hạn của TimelineCaption (từng làm hỏng bài 07 ở bước dựng cuối)."""
from __future__ import annotations

import re
from pathlib import Path

from src.schemas.contracts import TimelineCaption

RUNNER = Path(__file__).resolve().parents[1] / "src" / "modules" / "tao_video_noi_dung" / "runner.py"


def _gioi_han_toi_da() -> int:
    for meta in TimelineCaption.model_fields["font_size"].metadata:
        if hasattr(meta, "le"):
            return int(meta.le)
    raise AssertionError("TimelineCaption.font_size không có giới hạn le")


def test_co_chu_ngang_va_doc_trong_gioi_han():
    sizes = [int(x) for x in re.findall(r"font_size=(\d+) if height > width else (\d+)", RUNNER.read_text(encoding="utf-8")) for x in x]
    assert sizes, "không thấy cỡ chữ phụ đề nào trong runner"
    assert max(sizes) <= _gioi_han_toi_da()


def test_co_chu_72_hop_le():
    caption = TimelineCaption(text="x", start_ms=0, duration_ms=1000, font_size=72)
    assert caption.font_size == 72


def test_phu_de_ass_video_ngang_dung_co_chu_70():
    """Cỡ chữ ASS do karaoke_settings quyết định: 70 trên khung 1080 cao ra 39 px (mặc định 56 chỉ ra 32 px)."""
    from src.modules.media_studio.ass_captions import build_karaoke_ass
    cap = [{"text": "x", "start_ms": 0, "duration_ms": 1000, "words": [{"text": "x", "start_ms": 0, "end_ms": 500}]}]
    to = build_karaoke_ass(cap, 1920, 1080, settings={"font_size": 70})
    mac_dinh = build_karaoke_ass(cap, 1920, 1080)
    assert re.search(r"Style: Karaoke,[^,]*,39,", to)
    assert re.search(r"Style: Karaoke,[^,]*,32,", mac_dinh)


def test_runner_dat_karaoke_settings_cho_video_ngang():
    """Runner phải đặt karaoke_settings cho cả hai TimelineDocument; font_size của từng dòng không điều khiển cỡ chữ ASS."""
    source = RUNNER.read_text(encoding="utf-8")
    assert "KaraokeCaptionSettings(font_size=70) if width > height" in source
    assert "karaoke_settings=timeline.karaoke_settings" in source
