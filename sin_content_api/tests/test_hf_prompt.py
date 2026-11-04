"""Kiểm thử bảng mô tả lời nhắc cảnh khối HyperFrames và hạn ngạch sử dụng."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from src.modules.tao_video_noi_dung import hf_prompt, planner
from src.modules.tao_video_noi_dung.service import _CONTENT_VIDEO_STYLE_SNAPSHOT

BASE = json.loads((Path(__file__).parent / "fixtures/storyboard_llm_17shots_valid.json").read_text(encoding="utf-8"))
STYLE = _CONTENT_VIDEO_STYLE_SNAPSHOT.model_copy(update={"aspect_ratio": "9:16"}).model_dump(mode="json")
CONTENT = "Báo cáo giao hàng và công nợ rải rác nhiều nơi, người quản lý khó biết đơn nào đang chậm. " * 3


class Client:
    max_output_tokens = 12000

    def __init__(self, brief, *storyboards):
        self.responses = [brief, *storyboards]
        self.calls = []

    def complete(self, messages, max_tokens):
        self.calls.append(messages)
        index = min(len(self.calls), len(self.responses)) - 1
        return SimpleNamespace(content=json.dumps(self.responses[index], ensure_ascii=False), model="test-model")


def test_prompt_giong_ban_cu():
    """Kiểm tra lời nhắc hệ thống mới sinh ra hoàn toàn trùng khớp với chuỗi golden đã lưu trước khi tái cấu trúc."""
    golden_path = Path(__file__).parent / "fixtures/hf_prompt_golden.txt"
    assert golden_path.exists(), "Tệp golden không tồn tại"
    golden = golden_path.read_text(encoding="utf-8")

    client = Client(BASE["brief"], copy.deepcopy(BASE))
    result = planner.generate_storyboard(CONTENT, 100, STYLE, client)
    # Lần gọi 0 là generate_brief, lần gọi 1 là generate_storyboard
    system_prompt = client.calls[1][0]["content"]

    assert system_prompt == golden


def test_moi_layout_khoi_co_mo_ta():
    """Mọi layout trong planner.BLOCK_LAYOUTS đều có bản ghi trong LAYOUT_PROMPTS và xuất hiện trong layout_prompt()."""
    for layout in planner.BLOCK_LAYOUTS:
        assert layout in hf_prompt.LAYOUT_PROMPTS
        assert hf_prompt.LAYOUT_PROMPTS[layout].strip()

    full_prompt = hf_prompt.layout_prompt()
    for layout in planner.BLOCK_LAYOUTS:
        assert layout in full_prompt

    # Kiểm tra khi truyền danh sách giới hạn thì chỉ gồm các layout được chọn
    subset = ["KINETIC_TITLE", "MARK_PHRASE"]
    sub_prompt = hf_prompt.layout_prompt(subset)
    assert "KINETIC_TITLE" in sub_prompt
    assert "MARK_PHRASE" in sub_prompt
    assert "AI_RANK" not in sub_prompt
    assert "DRAG_TASKS" not in sub_prompt
    assert "CARD_SHIFT" not in sub_prompt


def test_block_quota():
    """Hạn ngạch số shot khối: dưới 5 shot thì (0, total); từ 5 trở lên thì (3, max(3, round(total*0.6)))."""
    assert hf_prompt.block_quota(0) == (0, 0)
    assert hf_prompt.block_quota(4) == (0, 4)
    assert hf_prompt.block_quota(5) == (3, 3)
    assert hf_prompt.block_quota(10) == (3, 6)
    assert hf_prompt.block_quota(1) == (0, 1)
    assert hf_prompt.block_quota(6) == (3, 4)
    assert hf_prompt.block_quota(7) == (3, 4)


def test_join_problems_dua_loi_quan_trong_len_dau():
    """Đưa các lỗi quan trọng (DIAGRAM_BLOCK_LAYOUT_MISSING, DIAGRAM_ONLY_VIOLATION...) lên trước các lỗi dài khác."""
    long_narrations = [
        f"NARRATION_LENGTH: shot_{i:02d} có 55 âm tiết, cần 20 đến 35 âm tiết theo thời lượng quy định"
        for i in range(30)
    ]
    missing = (
        "DIAGRAM_BLOCK_LAYOUT_MISSING: video có 5 shot UI_SIM nhưng chỉ 0 shot dùng loại chuyển động dựng sẵn; "
        "đổi ít nhất 3 shot sang KINETIC_TITLE"
    )
    problems = [*long_narrations, missing]

    joined = hf_prompt.join_problems(problems, limit=1400)
    assert len(joined) <= 1400
    assert missing in joined
    assert joined.startswith(missing)


def test_join_problems_khong_cat_giua_chuoi():
    """Không cắt dở dang giữa một chuỗi lỗi khi danh sách còn các lỗi phía sau."""
    problems = [f"PROBLEM_{i:02d}: " + ("x" * 80) for i in range(30)]
    joined = hf_prompt.join_problems(problems, limit=1400)
    assert len(joined) <= 1400

    items = joined.split("; ")
    for item in items:
        assert item in problems
    assert len(items) < len(problems)

    # Trường hợp một chuỗi đơn lẻ vượt quá limit thì cắt ở đúng limit
    single_long = "LONG_ERROR: " + ("a" * 1500)
    assert hf_prompt.join_problems([single_long], limit=1400) == single_long[:1400]
