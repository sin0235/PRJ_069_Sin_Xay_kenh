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
