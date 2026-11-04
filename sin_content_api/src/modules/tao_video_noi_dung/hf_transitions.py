"""Chuyển cảnh thuần bằng GSAP giữa hai phần tử cảnh HyperFrames (hf_transitions).
Cung cấp các hàm thuần tạo mã GSAP xác định, không phụ thuộc vào trạng thái ngẫu nhiên hay trình duyệt.
"""
from __future__ import annotations

import math

TRANSITION_KINDS: tuple[str, ...] = (
    "push",
    "cover",
    "scale",
    "dissolve",
    "radial",
    "grid",
    "blur",
    "split",
)

SHADER_TRANSITIONS_SUPPORTED: bool = False


def transition_js(kind: str, from_id: str, to_id: str, start: float, duration: float) -> str:
    """Tạo các câu lệnh GSAP (mỗi dòng kết thúc bằng ';\\n', mốc thời gian định dạng {value:.3f})
    điều khiển chuyển cảnh giữa hai phần tử cảnh '#<from_id>' và '#<to_id>'.
    """
    if kind not in TRANSITION_KINDS:
        raise ValueError("HYPERFRAMES_TRANSITION_KIND_INVALID")

    try:
        start_f = float(start)
        duration_f = float(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError("HYPERFRAMES_TRANSITION_TIMING_INVALID") from exc

    if not math.isfinite(start_f) or not math.isfinite(duration_f) or start_f < 0 or duration_f <= 0:
        raise ValueError("HYPERFRAMES_TRANSITION_TIMING_INVALID")

    from_sel = f"#{from_id.lstrip('#')}"
    to_sel = f"#{to_id.lstrip('#')}"
    end = start_f + duration_f

    if kind == "push":
        # Cảnh mới trượt vào từ phải (xPercent 100 -> 0), cảnh cũ trượt sang -30% và mờ về opacity 0.4.
        return (
            f'tl.fromTo("{from_sel}", {{ xPercent: 0, opacity: 1 }}, {{ xPercent: -30, opacity: 0.4, duration: {duration_f:.3f}, ease: "power2.inOut" }}, {start_f:.3f});\n'
            f'tl.fromTo("{to_sel}", {{ xPercent: 100, opacity: 1 }}, {{ xPercent: 0, opacity: 1, duration: {duration_f:.3f}, ease: "power2.inOut" }}, {start_f:.3f});\n'
            f'tl.set("{from_sel}", {{ opacity: 0 }}, {end:.3f});\n'
            f'tl.set("{to_sel}", {{ xPercent: 0, opacity: 1 }}, {end:.3f});\n'
        )

    if kind == "cover":
        # Cảnh mới trượt đè lên cảnh cũ từ bên phải với bóng đổ mềm, cảnh cũ giữ nguyên vị trí rồi ẩn ở cuối.
        return (
            f'tl.set("{from_sel}", {{ opacity: 1 }}, {start_f:.3f});\n'
            f'tl.fromTo("{to_sel}", {{ xPercent: 100, opacity: 1, boxShadow: "-12px 0 30px rgba(0,0,0,0.5)" }}, {{ xPercent: 0, opacity: 1, boxShadow: "-12px 0 30px rgba(0,0,0,0.5)", duration: {duration_f:.3f}, ease: "power2.inOut" }}, {start_f:.3f});\n'
            f'tl.set("{from_sel}", {{ opacity: 0 }}, {end:.3f});\n'
            f'tl.set("{to_sel}", {{ xPercent: 0, opacity: 1, boxShadow: "none" }}, {end:.3f});\n'
        )

    if kind == "scale":
        # Cảnh cũ phóng to 1 -> 1.15 và mờ dần, cảnh mới phóng to 0.92 -> 1 và hiện rõ.
        return (
            f'tl.fromTo("{from_sel}", {{ scale: 1, opacity: 1 }}, {{ scale: 1.15, opacity: 0, duration: {duration_f:.3f}, ease: "power2.inOut" }}, {start_f:.3f});\n'
            f'tl.fromTo("{to_sel}", {{ scale: 0.92, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: {duration_f:.3f}, ease: "power2.inOut" }}, {start_f:.3f});\n'
            f'tl.set("{from_sel}", {{ opacity: 0 }}, {end:.3f});\n'
            f'tl.set("{to_sel}", {{ scale: 1, opacity: 1 }}, {end:.3f});\n'
        )

    if kind == "dissolve":
        # Chuyển cảnh hòa tan chỉ bằng độ mờ (opacity).
        return (
            f'tl.fromTo("{from_sel}", {{ opacity: 1 }}, {{ opacity: 0, duration: {duration_f:.3f}, ease: "power1.inOut" }}, {start_f:.3f});\n'
            f'tl.fromTo("{to_sel}", {{ opacity: 0 }}, {{ opacity: 1, duration: {duration_f:.3f}, ease: "power1.inOut" }}, {start_f:.3f});\n'
            f'tl.set("{from_sel}", {{ opacity: 0 }}, {end:.3f});\n'
            f'tl.set("{to_sel}", {{ opacity: 1 }}, {end:.3f});\n'
        )

    if kind == "radial":
        # Cảnh mới mở ra bằng đường tròn circle(0% at 50% 50%) -> circle(75% at 50% 50%), sau đó khôi phục clipPath 'none'.
        return (
            f'tl.set("{from_sel}", {{ opacity: 1 }}, {start_f:.3f});\n'
            f'tl.fromTo("{to_sel}", {{ clipPath: "circle(0% at 50% 50%)", opacity: 1 }}, {{ clipPath: "circle(75% at 50% 50%)", opacity: 1, duration: {duration_f:.3f}, ease: "power2.out" }}, {start_f:.3f});\n'
            f'tl.set("{from_sel}", {{ opacity: 0 }}, {end:.3f});\n'
            f'tl.set("{to_sel}", {{ clipPath: "none", opacity: 1 }}, {end:.3f});\n'
        )

    if kind == "grid":
        # Cảnh mới lộ dần qua 4 dải sọc dọc so le bằng clipPath inset() với 4 lần tl.fromTo xác định.
        lines = [f'tl.set("{from_sel}", {{ opacity: 1 }}, {start_f:.3f});\n']
        step_dur = duration_f / 4.0
        strip_bounds = [
            ("inset(0 100% 0 0)", "inset(0 75% 0 0)"),
            ("inset(0 75% 0 0)", "inset(0 50% 0 0)"),
            ("inset(0 50% 0 0)", "inset(0 25% 0 0)"),
            ("inset(0 25% 0 0)", "inset(0 0 0 0)"),
        ]
        for i, (from_inset, to_inset) in enumerate(strip_bounds):
            t_start = start_f + i * step_dur
            t_dur = (start_f + duration_f - t_start) if i == 3 else step_dur
            lines.append(
                f'tl.fromTo("{to_sel}", {{ clipPath: "{from_inset}", opacity: 1 }}, {{ clipPath: "{to_inset}", opacity: 1, duration: {t_dur:.3f}, ease: "none" }}, {t_start:.3f});\n'
            )
        lines.append(f'tl.set("{from_sel}", {{ opacity: 0 }}, {end:.3f});\n')
        lines.append(f'tl.set("{to_sel}", {{ clipPath: "none", opacity: 1 }}, {end:.3f});\n')
        return "".join(lines)

    if kind == "blur":
        # Cảnh cũ làm mờ và ẩn dần, cảnh mới nét lại từ độ mờ và hiện rõ, sau đó đặt filter về 'none'.
        return (
            f'tl.fromTo("{from_sel}", {{ filter: "blur(0px)", opacity: 1 }}, {{ filter: "blur(14px)", opacity: 0, duration: {duration_f:.3f}, ease: "power2.inOut" }}, {start_f:.3f});\n'
            f'tl.fromTo("{to_sel}", {{ filter: "blur(14px)", opacity: 0 }}, {{ filter: "blur(0px)", opacity: 1, duration: {duration_f:.3f}, ease: "power2.inOut" }}, {start_f:.3f});\n'
            f'tl.set("{from_sel}", {{ filter: "none", opacity: 0 }}, {end:.3f});\n'
            f'tl.set("{to_sel}", {{ filter: "none", opacity: 1 }}, {end:.3f});\n'
        )

    # kind == "split"
    # Cảnh mới mở ra từ giữa bằng clipPath inset(0 50% 0 50%) -> inset(0 0 0 0), sau đó khôi phục clipPath 'none'.
    return (
        f'tl.set("{from_sel}", {{ opacity: 1 }}, {start_f:.3f});\n'
        f'tl.fromTo("{to_sel}", {{ clipPath: "inset(0 50% 0 50%)", opacity: 1 }}, {{ clipPath: "inset(0 0 0 0)", opacity: 1, duration: {duration_f:.3f}, ease: "power2.inOut" }}, {start_f:.3f});\n'
        f'tl.set("{from_sel}", {{ opacity: 0 }}, {end:.3f});\n'
        f'tl.set("{to_sel}", {{ clipPath: "none", opacity: 1 }}, {end:.3f});\n'
    )
