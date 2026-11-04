"""Kiểm thử bộ chuyển cảnh thuần GSAP (hf_transitions) cho HyperFrames:
Tính thuần (deterministic), bao phủ hai phần tử, giới hạn thời gian tween,
khôi phục trạng thái tự nhiên, xử lý đầu vào lỗi và cân bằng dấu ngoặc.
"""
import math
import re

import pytest

from src.modules.tao_video_noi_dung import hf_transitions
from src.modules.tao_video_noi_dung.hf_transitions import (
    SHADER_TRANSITIONS_SUPPORTED,
    TRANSITION_KINDS,
    transition_js,
)


def test_transition_js_la_ham_thuan():
    """Hàm thuần: cùng tham số trả về chuỗi giống hệt nhau, không chứa mã ngẫu nhiên hoặc bất đồng bộ."""
    assert isinstance(TRANSITION_KINDS, tuple)
    assert len(TRANSITION_KINDS) == 8
    assert not SHADER_TRANSITIONS_SUPPORTED

    for kind in TRANSITION_KINDS:
        js1 = transition_js(kind, "s01", "s02", 2.5, 0.8)
        js2 = transition_js(kind, "s01", "s02", 2.5, 0.8)
        assert js1 == js2, f"Kết quả không xác định cho {kind}"

        # Kiểm tra không dùng hàm ngẫu nhiên hay phụ thuộc thời gian thực
        for banned in ("Math.random", "Date", "requestAnimationFrame", "setTimeout", "setInterval"):
            assert banned not in js1, f"Phát hiện hàm cấm {banned} trong {kind}"

        # Mỗi lệnh phải kết thúc bằng dấu chấm phẩy và xuống dòng
        lines = [line.strip() for line in js1.splitlines() if line.strip()]
        for line in lines:
            assert line.endswith(";"), f"Lệnh không kết thúc bằng ';' trong {kind}: {line}"


def test_moi_kind_dung_ca_hai_phan_tu():
    """Mọi kiểu chuyển cảnh đều thao tác trên bộ chọn của cả hai phần tử cảnh vào và ra."""
    for kind in TRANSITION_KINDS:
        js = transition_js(kind, "canh_truoc", "canh_sau", 1.0, 0.5)
        assert '"#canh_truoc"' in js, f"Thiếu cảnh ra #canh_truoc trong {kind}"
        assert '"#canh_sau"' in js, f"Thiếu cảnh vào #canh_sau trong {kind}"

        # Đảm bảo xử lý đúng khi id đã có sẵn dấu '#'
        js_hash = transition_js(kind, "#canh_truoc", "#canh_sau", 1.0, 0.5)
        assert '"##' not in js_hash
        assert '"#canh_truoc"' in js_hash
        assert '"#canh_sau"' in js_hash


def test_thoi_gian_nam_trong_cua_so():
    """Mọi tween phải bắt đầu trong [start, start + duration] và kết thúc không vượt quá start + duration + 0.001."""
    test_cases = [
        (0.0, 0.5),
        (1.234, 0.65),
        (10.0, 1.2),
    ]
    for start, duration in test_cases:
        window_end = start + duration
        for kind in TRANSITION_KINDS:
            js = transition_js(kind, "s01", "s02", start, duration)

            # Trích xuất các tween fromTo: duration và start_time
            from_to_matches = re.findall(
                r'tl\.fromTo\([^,]+,\s*\{[^}]*\},\s*\{.*?(?:duration:\s*([0-9.]+)).*?\},\s*([0-9.]+)\);',
                js,
            )
            for dur_str, st_str in from_to_matches:
                t_dur = float(dur_str)
                t_start = float(st_str)
                assert start - 1e-4 <= t_start <= window_end + 1e-4, (
                    f"Tween start {t_start} nằm ngoài [{start}, {window_end}] trong {kind}"
                )
                assert t_start + t_dur <= window_end + 0.00101, (
                    f"Tween kết thúc {t_start + t_dur} vượt quá {window_end} trong {kind}"
                )

            # Trích xuất các tween set: start_time (duration = 0)
            set_matches = re.findall(r'tl\.set\([^,]+,\s*\{[^}]*\},\s*([0-9.]+)\);', js)
            for st_str in set_matches:
                t_start = float(st_str)
                assert start - 1e-4 <= t_start <= window_end + 1e-4, (
                    f"Set time {t_start} nằm ngoài [{start}, {window_end}] trong {kind}"
                )


def test_ket_thuc_o_trang_thai_tu_nhien():
    """Lệnh cuối cùng của phần tử cảnh vào phải khôi phục trạng thái tự nhiên (xPercent 0, scale 1, opacity 1, filter/clipPath none)."""
    for kind in TRANSITION_KINDS:
        js = transition_js(kind, "s01", "s02", 2.0, 0.6)
        end_time_str = f"{2.6:.3f}"

        # Cảnh ra phải ẩn hoàn toàn ở cuối chuyển cảnh
        assert f'tl.set("#s01", {{ opacity: 0 }}, {end_time_str});' in js or (
            f'tl.set("#s01", {{ filter: "none", opacity: 0 }}, {end_time_str});' in js
        ), f"Cảnh ra chưa được đưa về opacity 0 ở cuối {kind}"

        # Kiểm tra trạng thái tự nhiên của cảnh vào
        if kind == "push":
            assert f'tl.set("#s02", {{ xPercent: 0, opacity: 1 }}, {end_time_str});' in js
        elif kind == "cover":
            assert f'tl.set("#s02", {{ xPercent: 0, opacity: 1, boxShadow: "none" }}, {end_time_str});' in js
        elif kind == "scale":
            assert f'tl.set("#s02", {{ scale: 1, opacity: 1 }}, {end_time_str});' in js
        elif kind == "dissolve":
            assert f'tl.set("#s02", {{ opacity: 1 }}, {end_time_str});' in js
        elif kind in {"radial", "grid", "split"}:
            assert f'tl.set("#s02", {{ clipPath: "none", opacity: 1 }}, {end_time_str});' in js
        elif kind == "blur":
            assert f'tl.set("#s02", {{ filter: "none", opacity: 1 }}, {end_time_str});' in js


def test_kind_va_thoi_gian_sai():
    """Kiểm tra báo lỗi với loại chuyển cảnh không hợp lệ hoặc thời lượng/mốc thời gian sai."""
    with pytest.raises(ValueError, match="HYPERFRAMES_TRANSITION_KIND_INVALID"):
        transition_js("khong_ton_tai", "s01", "s02", 0.0, 1.0)

    with pytest.raises(ValueError, match="HYPERFRAMES_TRANSITION_KIND_INVALID"):
        transition_js("", "s01", "s02", 0.0, 1.0)

    # Thời lượng <= 0
    with pytest.raises(ValueError, match="HYPERFRAMES_TRANSITION_TIMING_INVALID"):
        transition_js("push", "s01", "s02", 0.0, 0.0)

    with pytest.raises(ValueError, match="HYPERFRAMES_TRANSITION_TIMING_INVALID"):
        transition_js("push", "s01", "s02", 0.0, -0.5)

    # Mốc thời gian bắt đầu < 0
    with pytest.raises(ValueError, match="HYPERFRAMES_TRANSITION_TIMING_INVALID"):
        transition_js("push", "s01", "s02", -0.1, 0.5)

    # Đầu vào không hữu hạn hoặc không hợp lệ
    with pytest.raises(ValueError, match="HYPERFRAMES_TRANSITION_TIMING_INVALID"):
        transition_js("push", "s01", "s02", float("nan"), 0.5)

    with pytest.raises(ValueError, match="HYPERFRAMES_TRANSITION_TIMING_INVALID"):
        transition_js("push", "s01", "s02", 0.0, float("inf"))

    with pytest.raises(ValueError, match="HYPERFRAMES_TRANSITION_TIMING_INVALID"):
        transition_js("push", "s01", "s02", "sai_moc", 0.5)


def test_ngoac_can_bang():
    """Kiểm tra cân bằng dấu ngoặc đơn, ngoặc nhọn và nháy kép trong mã JavaScript tạo ra."""
    for kind in TRANSITION_KINDS:
        js = transition_js(kind, "s01", "s02", 3.0, 0.8)
        stack = []
        pairs = {")": "(", "}": "{", "]": "["}
        in_string = False

        for char in js:
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue

            if char in "({[":
                stack.append(char)
            elif char in ")}]":
                assert stack, f"Dấu đóng dư '{char}' trong {kind}"
                top = stack.pop()
                assert top == pairs[char], f"Dấu ngoặc không khớp '{top}' với '{char}' trong {kind}"

        assert not in_string, f"Dấu nháy kép chưa đóng trong {kind}"
        assert not stack, f"Còn dấu ngoặc chưa đóng trong {kind}: {stack}"
