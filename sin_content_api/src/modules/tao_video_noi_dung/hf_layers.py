"""Các lớp phủ (overlay layers) cho video dựng bằng HyperFrames:
Bảng tên người nói (lower third), nền động môi trường (ambient),
hạt phim và vệt sáng, được xây dựng từ các khối HyperFrames chính thức.
"""
from __future__ import annotations

import html
import zlib
from dataclasses import dataclass

from . import hf_blocks

# Danh sách các khối bảng tên (lower third) đã kiểm định hiển thị dấu tiếng Việt chuẩn
KEPT_LT_BLOCKS: tuple[str, ...] = (
    "lt-clean-bar",
    "lt-accent-underline",
    "lt-side-rule",
    "lt-soft-pill",
)

# Chuỗi mẫu gốc tiếng Anh trong các tệp khối lower third
LT_SAMPLE_NAME = "Dr. Maya Chen"
LT_SAMPLE_ROLE = "Host \u00b7 Neuroscientist"


@dataclass(frozen=True)
class OverlaySpec:
    """Đặc tả một lớp phủ đặt chồng lên dòng thời gian video."""
    block: str
    start: float
    duration: float
    variables: dict
    literals: dict[str, str]
    z_index: int
    opacity: float = 1.0


def overlay_host(spec: OverlaySpec, cid: str, aspect: str) -> tuple[str, str]:
    """Tạo mã HTML cho sub-composition và thẻ div host tương ứng.

    Trả về (composition_html, host_div_html).
    """
    width, height = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    composition_html = hf_blocks.prepare_block(spec.block, cid, spec.duration, spec.literals)
    attrs = hf_blocks.host_attrs(spec.variables)
    host_div_html = (
        f'<div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
        f'data-start="{spec.start:.3f}" data-duration="{spec.duration:.3f}" '
        f'data-width="{width}" data-height="{height}"{attrs} '
        f'style="z-index:{spec.z_index};opacity:{spec.opacity};pointer-events:none;{hf_blocks.THEME_STYLE}"></div>'
    )
    return composition_html, host_div_html


def ambient_for_video(seed: str, total: float, aspect: str) -> list[OverlaySpec]:
    """Chọn các lớp phủ môi trường nhẹ (ambient/grain/starfield/light leak) ổn định theo seed.

    Tất cả các lớp phủ bao phủ toàn bộ thời lượng 0..total với độ mờ đục thấp (<= 0.35),
    không che khuất nội dung các cảnh chính.
    """
    total_duration = float(total)
    hash_val = zlib.crc32(seed.encode("utf-8"))

    # Các tùy chọn lớp hạt nền hoặc bầu trời sao nhẹ
    texture_options = (
        OverlaySpec(
            block="grain-field",
            start=0.0,
            duration=total_duration,
            variables={"density": "fine", "accent": "green"},
            literals={},
            z_index=15,
            opacity=0.15,
        ),
        OverlaySpec(
            block="starfield",
            start=0.0,
            duration=total_duration,
            variables={"density": "sparse", "tone": "warm", "speed": "slow"},
            literals={},
            z_index=15,
            opacity=0.22,
        ),
    )

    chosen_texture = texture_options[hash_val % len(texture_options)]
    result = [chosen_texture]

    # Bổ sung lớp vệt sáng hữu cơ nhẹ dạng vignette nếu phù hợp
    if (hash_val >> 1) % 2 == 1:
        leak_spec = OverlaySpec(
            block="organic-light-leak-overlay",
            start=0.0,
            duration=total_duration,
            variables={},
            literals={},
            z_index=18,
            opacity=0.18,
        )
        result.append(leak_spec)

    return result


def lower_third_for_shot(shot: dict) -> OverlaySpec | None:
    """Tạo bảng tên nhân vật cho cảnh quay nếu có thông tin tên trong nội dung.

    Hàm tuyệt đối không tự bịa tên khi shot không có trường 'name'.
    Hiển thị từ start_seconds + 0.4 trong khoảng min(4.0, seconds - 0.8) giây.
    """
    raw_name = shot.get("name")
    if not raw_name or not str(raw_name).strip():
        return None

    name = str(raw_name).strip()
    raw_role = shot.get("role")
    role = str(raw_role).strip() if raw_role else ""

    start_s = float(shot.get("start_seconds", 0.0))
    duration_s = float(shot.get("seconds", 0.0))

    lt_start = start_s + 0.4
    lt_duration = min(4.0, max(0.0, duration_s - 0.8))

    # Băm ổn định theo tên để chọn kiểu bảng tên nhất quán
    name_hash = zlib.crc32(name.encode("utf-8"))
    block_name = KEPT_LT_BLOCKS[name_hash % len(KEPT_LT_BLOCKS)]

    # Điền giá trị thực tế thay thế các chuỗi mẫu cố định trong khối
    literals = {
        LT_SAMPLE_NAME: html.escape(name, quote=False),
        LT_SAMPLE_ROLE: html.escape(role, quote=False) if role else "",
    }

    return OverlaySpec(
        block=block_name,
        start=lt_start,
        duration=lt_duration,
        variables={},
        literals=literals,
        z_index=80,
        opacity=1.0,
    )
