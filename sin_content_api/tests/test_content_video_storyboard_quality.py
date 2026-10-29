import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.modules.tao_video_noi_dung.planner import Storyboard
from src.modules.tao_video_noi_dung.danh_gia import score_storyboard


def baseline():
    return json.loads((Path(__file__).parent / "fixtures/storyboard_ai_sales_v3.json").read_text())


def test_baseline_ai_sales_storyboard_fails_quality_gates():
    score = score_storyboard(Storyboard.model_validate(baseline()))
    assert score.static_shot_ratio == 1.0
    assert score.pain_before_solution is False
    assert "NO_PAIN_BEAT" in score.issues


def brief_data():
    return {"pains": [{"id": "p1", "text": "Nhân viên bỏ sót khách hỏi ban đêm.", "source": "inferred"}],
            "solutions": [{"id": "s1", "text": "Trợ lý trả lời khách.", "source": "content"}],
            "needs_ui_demo": True}


class Client:
    max_output_tokens = 12000

    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def complete(self, messages, max_tokens):
        self.calls.append((list(messages), max_tokens))
        return SimpleNamespace(content=json.dumps(next(self.responses), ensure_ascii=False), model="test-model")


def test_brief_marks_inferred_pains():
    from src.modules.tao_video_noi_dung.brief import generate_brief
    brief = generate_brief("Trợ lý hỗ trợ trả lời khách hỏi ngoài giờ làm việc.", Client(brief_data()))
    assert brief.pains[0].source == "inferred"
    assert {m.id for m in brief.all_messages()} == {"p1", "s1"}


@pytest.mark.parametrize("text", ["Mất 20 khách", "Mất ٢ khách"])
def test_brief_rejects_inferred_pain_with_digits(text):
    from src.modules.tao_video_noi_dung.brief import ContentBrief
    data = brief_data()
    data["pains"][0]["text"] = text
    with pytest.raises(ValueError):
        ContentBrief.model_validate(data)


def test_brief_without_pain_is_invalid():
    from src.modules.tao_video_noi_dung.brief import ContentBrief
    with pytest.raises(ValueError):
        ContentBrief.model_validate({"pains": []})


def test_brief_rejects_duplicate_message_ids():
    from src.modules.tao_video_noi_dung.brief import ContentBrief
    data = brief_data()
    data["solutions"][0]["id"] = "p1"
    with pytest.raises(ValueError, match="MESSAGE_ID_DUPLICATE"):
        ContentBrief.model_validate(data)
