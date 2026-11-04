"""Cac ham thuan tao ma lenh GSAP dieu khien camera va con tro tren khung hinh HyperFrames."""
from __future__ import annotations

import math
from typing import Sequence

CAMERA_KINDS: tuple[str, ...] = ("push_in", "pull_back", "shake", "rack_focus")

# Bang do lech co dinh danh cho chuyen dong rung may (shake), khong dung bat dinh / ngau nhien.
# Bien do toi da theo yeu cau: |x| <= 6px, |y| <= 4px, |rotation| <= 0.4deg.
# Khoa tween cuoi cung (chi so 5) tro ve x: 0, y: 0, rotation: 0 chinh xac.
SHAKE_OFFSETS: tuple[tuple[float, float, float], ...] = (
    (-3.5, 2.2, -0.25),
    (4.8, -3.1, 0.35),
    (-5.2, 1.8, -0.30),
    (2.7, -2.5, 0.20),
    (-1.8, 1.2, -0.12),
    (0.0, 0.0, 0.0),
)


def _format_num(val: float) -> str:
    """Dinh dang so toa do gon gang cho ma nguon JavaScript."""
    if isinstance(val, (int, float)) and float(val).is_integer():
        return str(int(val))
    return f"{val:.3f}".rstrip("0").rstrip(".")


def camera_motion_js(kind: str, target: str, start: float, duration: float) -> str:
    """Tao chuoi cau lenh GSAP dong thoi gian dieu khien may quay tren phan tu target.

    Cac loai camera:
      - push_in: phong to tu scale 1 len 1.06 trong thoi luong duration, transformOrigin "50% 50%", ease "sine.inOut".
      - pull_back: thu nho tu scale 1.08 ve 1 trong thoi luong duration, ease "power2.out".
      - shake: rung may gom 6 keyframe co do lech co dinh, tween cuoi cung ve x: 0, y: 0, rotation: 0.
      - rack_focus: mo nho filter blur(8px) ve blur(0px) va dat filter thanh "none" vao cuoi thoi luong.

    Dinh dang thoi gian theo 3 chu so thap phan ({value:.3f}).
    """
    if kind not in CAMERA_KINDS:
        raise ValueError("HYPERFRAMES_CAMERA_KIND_INVALID")
    if not math.isfinite(start) or not math.isfinite(duration) or start < 0 or duration <= 0:
        raise ValueError("HYPERFRAMES_CAMERA_TIMING_INVALID")

    if kind == "push_in":
        return (
            f'tl.fromTo("{target}", {{ scale: 1, transformOrigin: "50% 50%" }}, '
            f'{{ scale: 1.06, duration: {duration:.3f}, ease: "sine.inOut" }}, {start:.3f});\n'
        )

    if kind == "pull_back":
        return (
            f'tl.fromTo("{target}", {{ scale: 1.08, transformOrigin: "50% 50%" }}, '
            f'{{ scale: 1, duration: {duration:.3f}, ease: "power2.out" }}, {start:.3f});\n'
        )

    if kind == "shake":
        lines: list[str] = []
        step_dur = duration / 6.0
        for i, (dx, dy, drot) in enumerate(SHAKE_OFFSETS):
            t_start = start + i * step_dur
            t_dur = (start + duration) - t_start if i == len(SHAKE_OFFSETS) - 1 else step_dur
            if i == len(SHAKE_OFFSETS) - 1:
                lines.append(
                    f'tl.to("{target}", {{ x: 0, y: 0, rotation: 0, '
                    f'duration: {t_dur:.3f}, ease: "sine.inOut" }}, {t_start:.3f});\n'
                )
            else:
                lines.append(
                    f'tl.to("{target}", {{ x: {_format_num(dx)}, y: {_format_num(dy)}, '
                    f'rotation: {_format_num(drot)}, duration: {t_dur:.3f}, ease: "sine.inOut" }}, {t_start:.3f});\n'
                )
        return "".join(lines)

    # kind == "rack_focus"
    return (
        f'tl.fromTo("{target}", {{ filter: "blur(8px)" }}, '
        f'{{ filter: "blur(0px)", duration: {duration:.3f}, ease: "power2.out" }}, {start:.3f});\n'
        f'tl.set("{target}", {{ filter: "none" }}, {start + duration:.3f});\n'
    )


def cursor_path(
    points: list[tuple[float, float]] | Sequence[tuple[float, float]],
    start: float,
    selector: str = "#cursor",
    seconds_per_leg: float = 0.6,
) -> str:
    """Di chuyen phan tu con tro dinh vi tuyet doi qua cac toa do (x, y) voi ease "power2.inOut".

    Cau lenh dau tien su dung tl.set dat vi tri tai points[0] o thoi diem start.
    Moi doan tiep theo su dung tl.to di chuyen den diem tiep theo trong seconds_per_leg giay.
    """
    if not points or len(points) < 2:
        raise ValueError("HYPERFRAMES_CURSOR_POINTS_INVALID")
    if not math.isfinite(start) or not math.isfinite(seconds_per_leg) or start < 0 or seconds_per_leg <= 0:
        raise ValueError("HYPERFRAMES_CAMERA_TIMING_INVALID")

    x0 = _format_num(points[0][0])
    y0 = _format_num(points[0][1])
    lines: list[str] = [
        f'tl.set("{selector}", {{ x: {x0}, y: {y0} }}, {start:.3f});\n'
    ]

    for idx in range(1, len(points)):
        xi = _format_num(points[idx][0])
        yi = _format_num(points[idx][1])
        leg_start = start + (idx - 1) * seconds_per_leg
        lines.append(
            f'tl.to("{selector}", {{ x: {xi}, y: {yi}, duration: {seconds_per_leg:.3f}, '
            f'ease: "power2.inOut" }}, {leg_start:.3f});\n'
        )

    return "".join(lines)
