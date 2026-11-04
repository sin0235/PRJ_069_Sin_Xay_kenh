"""Kiem thu cac ham tinh toan chuyen dong camera va con tro HyperFrames."""
from __future__ import annotations

import re
import pytest

from src.modules.tao_video_noi_dung.hf_camera import (
    CAMERA_KINDS,
    camera_motion_js,
    cursor_path,
)


def test_camera_motion_la_ham_thuan() -> None:
    """Cung tham so dau vao tra ve chuoi giong nhau va khong goi ham bat dinh."""
    forbidden = ["Math.random", "Date", "requestAnimationFrame", "setTimeout", "setInterval"]

    for kind in CAMERA_KINDS:
        out1 = camera_motion_js(kind, "#s01", 1.0, 2.5)
        out2 = camera_motion_js(kind, "#s01", 1.0, 2.5)
        assert out1 == out2
        for token in forbidden:
            assert token not in out1

    points = [(0.0, 0.0), (100.0, 200.0), (300.0, 150.0)]
    c1 = cursor_path(points, start=0.5, selector="#cursor", seconds_per_leg=0.4)
    c2 = cursor_path(points, start=0.5, selector="#cursor", seconds_per_leg=0.4)
    assert c1 == c2
    for token in forbidden:
        assert token not in c1


def test_camera_kinds_deu_hop_le() -> None:
    """Moi loai camera deu chua selector, thoi diem bat dau va ket thuc nam trong gioi han hop le."""
    target = "#scene_host"
    start = 1.25
    duration = 3.6

    for kind in CAMERA_KINDS:
        js = camera_motion_js(kind, target, start, duration)
        assert target in js

        lines = [line.strip() for line in js.strip().splitlines() if line.strip()]
        assert len(lines) >= 1

        for line in lines:
            assert line.startswith("tl.")
            assert line.endswith(");")

            # Parse thoi gian bat dau tween tu so sau dau phay cuoi cung
            last_comma_idx = line.rfind(",")
            assert last_comma_idx != -1
            time_str = line[last_comma_idx + 1 : -2].strip()
            tween_start = float(time_str)

            # Thoi gian bat dau phai nam trong khoang [start, start + duration]
            assert start - 1e-6 <= tween_start <= start + duration + 1e-6

            # Parse do dai thoi gian duration cua tween neu co
            dur_match = re.search(r'duration:\s*([0-9.]+)', line)
            tween_duration = float(dur_match.group(1)) if dur_match else 0.0

            # Thoi diem ket thuc tween khong duoc vuot qua start + duration + 0.001
            assert tween_start + tween_duration <= start + duration + 0.001 + 1e-6


def test_shake_tro_ve_vi_tri_goc() -> None:
    """Tween cuoi cung cua chuyen dong shake phai dua x: 0, y: 0 va rotation: 0 tro ve goc."""
    js = camera_motion_js("shake", "#host_shake", 0.0, 1.2)
    lines = [line.strip() for line in js.strip().splitlines() if line.strip()]
    assert len(lines) == 6

    final_tween = lines[-1]
    assert "x: 0" in final_tween
    assert "y: 0" in final_tween
    assert "rotation: 0" in final_tween


def test_kind_va_thoi_gian_sai() -> None:
    """Kiem tra nem dung ValueError khi truyen loai camera khong hop le hoac thoi gian sai."""
    with pytest.raises(ValueError, match="HYPERFRAMES_CAMERA_KIND_INVALID"):
        camera_motion_js("invalid_camera", "#host", 0.0, 1.0)

    with pytest.raises(ValueError, match="HYPERFRAMES_CAMERA_TIMING_INVALID"):
        camera_motion_js("push_in", "#host", 0.0, 0.0)

    with pytest.raises(ValueError, match="HYPERFRAMES_CAMERA_TIMING_INVALID"):
        camera_motion_js("push_in", "#host", 0.0, -1.5)

    with pytest.raises(ValueError, match="HYPERFRAMES_CAMERA_TIMING_INVALID"):
        camera_motion_js("push_in", "#host", -0.1, 2.0)


def test_cursor_path_so_cau_va_diem_dau() -> None:
    """3 diem tao ra mot tl.set va hai tl.to; thoi diem bat dau cua tl.set bang start; duoi 2 diem nem loi."""
    points = [(10.0, 20.0), (50.0, 80.0), (120.0, 90.0)]
    start = 2.45
    js = cursor_path(points, start=start, selector="#cursor_hand", seconds_per_leg=0.5)

    lines = [line.strip() for line in js.strip().splitlines() if line.strip()]
    assert len(lines) == 3

    set_lines = [l for l in lines if l.startswith("tl.set")]
    to_lines = [l for l in lines if l.startswith("tl.to")]

    assert len(set_lines) == 1
    assert len(to_lines) == 2

    # Thoi diem bat dau cua tl.set bang start
    last_comma_idx = set_lines[0].rfind(",")
    set_start = float(set_lines[0][last_comma_idx + 1 : -2].strip())
    assert abs(set_start - start) < 1e-6

    # Duoi 2 diem phai nem loi HYPERFRAMES_CURSOR_POINTS_INVALID
    with pytest.raises(ValueError, match="HYPERFRAMES_CURSOR_POINTS_INVALID"):
        cursor_path([(10.0, 20.0)], start=0.0)

    with pytest.raises(ValueError, match="HYPERFRAMES_CURSOR_POINTS_INVALID"):
        cursor_path([], start=0.0)


def test_chuoi_gsap_can_bang_ngoac() -> None:
    """Kiem tra so luong ngoac mo va dong '(' == ')' va '{' == '}' cho moi loai chuyen dong."""
    for kind in CAMERA_KINDS:
        js = camera_motion_js(kind, "#target_box", 0.8, 2.2)
        assert js.count("(") == js.count(")")
        assert js.count("{") == js.count("}")

    js_cursor = cursor_path([(0.0, 0.0), (30.0, 40.0), (80.0, 100.0)], start=1.0)
    assert js_cursor.count("(") == js_cursor.count(")")
    assert js_cursor.count("{") == js_cursor.count("}")
