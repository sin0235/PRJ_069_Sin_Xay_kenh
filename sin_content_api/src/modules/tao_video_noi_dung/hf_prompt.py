"""Bảng mô tả lời nhắc và hạn ngạch sử dụng cho các cảnh khối HyperFrames dựng sẵn."""
from __future__ import annotations

from typing import Iterable

# Bảng mô tả chi tiết từng loại cảnh khối dựng sẵn (nguyên văn từ lời nhắc tạo storyboard)
LAYOUT_PROMPTS: dict[str, str] = {
    "KINETIC_TITLE": (
        "câu chốt hoặc tên chương hiện thành chữ lớn: title 2 đến 7 từ tối đa 40 ký tự, "
        "tag tùy chọn là cụm nhấn màu nằm nguyên văn trong title"
    ),
    "MARK_PHRASE": (
        "một câu quan trọng được khoanh hoặc gạch dưới đúng cụm then chốt: title là câu 3 đến 10 từ, "
        "tag là cụm ngắn hơn nằm nguyên văn trong title, caption tùy chọn là ghi chú tối đa 30 ký tự"
    ),
    "WORD_SWAP": (
        "một từ đổi liên tục rồi dừng ở từ cuối, hợp để liệt kê các cách gọi hoặc kết quả: "
        "title là vế đầu tối đa 24 ký tự, steps 3 đến 4 từ khác nhau tối đa 14 ký tự, caption tùy chọn là vế sau"
    ),
    "PILE_UP": (
        "việc, tin nhắn, thông báo dồn dập quanh một người: title là người đó tối đa 14 ký tự, "
        "value là số lượng dạng chữ số từ 8 đến 24"
    ),
    "STAT_RING": (
        "vòng tròn đầy tới một phần trăm: to_value lớn hơn 0 và tối đa 100, caption là nhãn tối đa 30 ký tự"
    ),
    "CHART_STORY": (
        "biểu đồ cột hoặc đường tự kể: series đúng 1 chuỗi {name,values}, labels 3 đến 6 mục tối đa 10 ký tự, "
        "values cùng số lượng và không phẳng, unit tùy chọn"
    ),
    "AI_RANK": (
        "khách hỏi AI và danh sách gợi ý đổi chỗ khi doanh nghiệp xuất hiện: title là câu hỏi 3 đến 10 từ, "
        "steps đúng 3 tên phương án khác nhau tối đa 18 ký tự dùng tên chung như Nhà cung cấp A, "
        "tag là tên doanh nghiệp mình tối đa 18 ký tự, pick là vị trí 0 đến 2 mà tag chen vào, "
        "caption tùy chọn là câu dẫn tối đa 40 ký tự"
    ),
    "DRAG_TASKS": (
        "bảng việc kéo một thẻ sang cột kế: title là tên cột đầu tối đa 14 ký tự, "
        "caption là tên cột sau tối đa 14 ký tự, steps đúng 4 việc tối đa 26 ký tự, việc đầu tiên là việc được kéo"
    ),
    "CARD_SHIFT": (
        "hai thẻ, tiêu điểm chuyển từ thẻ cũ sang thẻ mới: title là nhãn nhỏ tối đa 16 ký tự, "
        "steps đúng 2 nhãn khác nhau tối đa 14 ký tự: lúc đầu rồi lúc sau"
    ),
    "CHAT_THREAD": (
        "hội thoại ngắn giữa khách và trợ lý hiện từng tin nhắn: title là tiêu đề hội thoại tối đa 24 ký tự, "
        "steps 2 đến 5 tin nhắn mỗi tin tối đa 48 ký tự, values cùng số lượng là vai trò từng tin gồm khách, AI hoặc nhân viên"
    ),
    "NOTE_TYPING": (
        "ứng dụng ghi chú đang gõ chữ: title tối đa 24 ký tự, steps 2 đến 5 dòng mỗi dòng tối đa 40 ký tự"
    ),
    "CTA_CLOSE": (
        "thẻ kêu gọi hành động kết video thay cho END_CARD và phải là shot cuối cùng: title là tên thương hiệu tối đa 20 ký tự, "
        "caption là câu mời tối đa 40 ký tự, tag tùy chọn là nhãn phụ tối đa 20 ký tự, value tùy chọn là liên hệ hoặc web tối đa 30 ký tự"
    ),
    "NOTIFY_STACK": (
        "các thông báo dồn chồng lên nhau: title là tên ứng dụng hoặc nguồn phát tối đa 20 ký tự, "
        "steps 3 đến 5 thông báo mỗi thông báo tối đa 40 ký tự"
    ),
}

BLOCK_LAYOUTS: tuple[str, ...] = tuple(LAYOUT_PROMPTS.keys())


def layout_prompt(layouts: Iterable[str] | None = None) -> str:
    """Tạo hai đoạn văn mô tả các cảnh chuyển động khối dựng sẵn kèm quy tắc sử dụng.

    Đoạn 1 gồm sáu loại đầu tiên (KINETIC_TITLE, MARK_PHRASE, WORD_SWAP, PILE_UP, STAT_RING, CHART_STORY).
    Đoạn 2 gồm các loại còn lại (AI_RANK, DRAG_TASKS, CARD_SHIFT) cùng lưu ý khung 9:16 và quy định bắt buộc.
    """
    if layouts is None:
        selected = list(BLOCK_LAYOUTS)
    else:
        layout_set = set(layouts)
        selected = [k for k in BLOCK_LAYOUTS if k in layout_set]

    first_six = selected[:6]
    rest = selected[6:]

    def _fmt(name: str) -> str:
        desc = LAYOUT_PROMPTS.get(name, "").strip()
        if desc.startswith(f"{name} (") and desc.endswith(")"):
            return desc
        if desc.startswith("(") and desc.endswith(")"):
            return f"{name} {desc}"
        return f"{name} ({desc})"

    p1 = (
        "Sáu loại chuyển động dựng sẵn, KHÔNG có mốc bám lời nên diagram.on luôn là {} và không cần cụm neo; "
        "dùng cho nhịp nhấn, chuyển ý, mở chương: "
        + ", ".join(_fmt(k) for k in first_six)
        + ". "
    )
    p2 = ""
    if rest:
        _viet_nums = {1: "Một", 2: "Hai", 3: "Ba", 4: "Bốn", 5: "Năm", 6: "Sáu", 7: "Bảy", 8: "Tám", 9: "Chín", 10: "Mười"}
        prefix = f"{_viet_nums.get(len(rest), str(len(rest)))} loại chuyển động dựng sẵn nữa, cùng quy tắc: "
        p2 = prefix + ", ".join(_fmt(k) for k in rest) + ". "

    suffix = (
        "Các loại này hợp với khung 9:16 và không tốn thời gian dựng như clip Flow; dùng chúng cho các shot nhấn ý ngắn. "
        "BẮT BUỘC: video có từ 5 shot UI_SIM trở lên phải dùng ít nhất 3 shot thuộc sáu loại này, mỗi loại tối đa 2 shot: PILE_UP hoặc WORD_SWAP cho nỗi đau, "
        "KINETIC_TITLE để mở chương hoặc chuyển ý, MARK_PHRASE cho câu insight then chốt, STAT_RING hoặc CHART_STORY cho kết quả hoặc bằng chứng; "
        "đặt chúng xen giữa các sơ đồ thông tin, không đặt hai shot liền nhau cùng loại. "
    )
    return p1 + p2 + suffix


def block_quota(total_ui_shots: int) -> tuple[int, int]:
    """Số lượng cảnh khối tối thiểu và tối đa theo tổng số shot UI_SIM.

    Mỗi loại cảnh khối dùng tối đa 2 shot trong cả video (quy định này được kiểm tra trong _soft_problems).
    - 0 shot UI hoặc dưới 5 shot UI: (0, total)
    - Từ 5 shot UI trở lên: (3, max(3, round(total * 0.6)))
    """
    if total_ui_shots < 5:
        return (0, max(0, total_ui_shots))
    return (3, max(3, round(total_ui_shots * 0.6)))


def _problem_priority(item: str) -> int:
    if item.startswith("DIAGRAM_BLOCK_LAYOUT_MISSING"):
        return 0
    if item.startswith("DIAGRAM_ONLY_VIOLATION"):
        return 1
    if item.startswith("DIAGRAM_FAMILY_"):
        return 2
    if item.startswith("DIAGRAM_LAYOUT_"):
        return 3
    return 4


def join_problems(problems: list[str], limit: int = 1400) -> str:
    """Nối danh sách lỗi bằng '; ' với giới hạn ký tự, ưu tiên đưa lỗi quan trọng lên đầu.

    Thứ tự ưu tiên:
    1. Bắt đầu bằng DIAGRAM_BLOCK_LAYOUT_MISSING
    2. Bắt đầu bằng DIAGRAM_ONLY_VIOLATION
    3. Bắt đầu bằng DIAGRAM_FAMILY_
    4. Bắt đầu bằng DIAGRAM_LAYOUT_
    5. Các lỗi còn lại theo thứ tự ban đầu

    Cắt tỉa chỉ loại bỏ từng chuỗi lỗi nguyên vẹn (không cắt lửng giữa chuỗi),
    trừ trường hợp một chuỗi đơn lẻ đã vượt quá giới hạn limit.
    """
    if not problems or limit <= 0:
        return ""

    ordered = sorted(problems, key=_problem_priority)

    if len(ordered[0]) > limit:
        return ordered[0][:limit]

    selected: list[str] = [ordered[0]]
    current_len = len(ordered[0])

    for item in ordered[1:]:
        if current_len + 2 + len(item) <= limit:
            selected.append(item)
            current_len += 2 + len(item)
        else:
            break

    return "; ".join(selected)
