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


def v4_data():
    data = baseline()
    data["brief"] = brief_data()
    data["brief"]["needs_ui_demo"] = False
    data["shots"] = data["shots"][:2]
    for shot, beat, mid in zip(data["shots"], ["PAIN", "SOLUTION"], ["p1", "s1"]):
        shot.update(prompt_contract_version=4, beat=beat, message_ids=[mid],
                    action_beats=[{"start_s": 0, "end_s": 10, "action": "Nhân viên trả lời khách."}])
    return data


STYLE = {"style_name": "Origami", "visual_rules": "Giấy gấp ổn định.", "palette": ["navy"], "aspect_ratio": "9:16"}


def test_generate_storyboard_retries_once_on_weak_storyboard():
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    weak = v4_data()
    weak["shots"][0]["beat"] = "HOOK"
    client = Client(brief_data() | {"needs_ui_demo": False}, weak, v4_data())
    board, model = generate_storyboard("Trợ lý giúp nhân viên hỗ trợ khách hỏi ngoài giờ làm việc.", 20, STYLE, client)
    assert board.shots[0].beat == "PAIN" and model == "test-model"
    assert len(client.calls) == 3
    assert "NO_PAIN_BEAT" in client.calls[-1][0][-1]["content"]


def test_generate_storyboard_accepts_weak_storyboard_after_one_retry():
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    weak = v4_data()
    weak["shots"][0]["message_ids"] = []
    client = Client(brief_data() | {"needs_ui_demo": False}, weak, weak)
    board, _ = generate_storyboard("Nội dung về trợ lý hỗ trợ khách hàng.", 20, STYLE, client)
    assert board.shots[0].message_ids == [] and len(client.calls) == 3


@pytest.mark.parametrize("content", ["Nội dung thuần thông tin về cách dùng tài liệu.", "a" * 12000])
def test_generate_storyboard_signature_unchanged(content):
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    client = Client(brief_data() | {"needs_ui_demo": False}, v4_data())
    board, model = generate_storyboard(content, 20, STYLE, client)
    assert model == "test-model" and sum(s.duration_seconds for s in board.shots) == 20
    request = json.loads(client.calls[1][0][1]["content"])
    assert "required_shot_durations" not in request
    assert request["target_duration_seconds"] == 20
    assert board.brief.pains[0].source == "inferred"


def test_generate_storyboard_rejects_bad_duration_before_spending_llm_quota():
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    client = Client()
    with pytest.raises(ValueError):
        generate_storyboard("Nội dung đủ dài để tạo một bản thử nghiệm.", 19, STYLE, client)
    assert not client.calls


def test_generate_storyboard_rejects_narration_digits_but_allows_written_ui_text():
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    data = v4_data()
    data["shots"][1].update(shot_kind="UI_SIM", action_beats=[], ui_scene={"layout": "CHAT", "messages": [
        {"role": "customer", "text": "AI hoạt động lúc 2 giờ?", "at_s": 0},
        {"role": "ai", "text": "Tôi hỗ trợ 24/7.", "at_s": 3}]})
    board, _ = generate_storyboard("Trợ lý hỗ trợ khách hàng.", 20, STYLE, Client(brief_data(), data))
    assert "24/7" in board.shots[1].ui_scene.messages[1].text
    data["shots"][1]["narration"] = "Hỗ trợ 24/7."
    with pytest.raises(ValueError, match="TTS"):  # lỗi lời đọc được thử lại một lần; vẫn sai thì báo lỗi
        generate_storyboard("Trợ lý hỗ trợ khách hàng.", 20, STYLE, Client(brief_data(), data, data))


@pytest.mark.parametrize("bad_root", [[], None, "không phải đối tượng"])
def test_generate_storyboard_reports_invalid_json_root(bad_root):
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    with pytest.raises(ValueError, match="STORYBOARD_JSON_OBJECT_REQUIRED"):
        generate_storyboard("Nội dung thuần thông tin về lưu trữ tài liệu.", 20, STYLE,
                            Client(brief_data(), bad_root))


def test_planning_requests_carry_baha_b2b_and_silent_visual_brief():
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    client = Client(brief_data() | {"needs_ui_demo": False}, v4_data())
    generate_storyboard("Trợ lý giúp doanh nghiệp tiếp nhận yêu cầu của khách hàng.", 20, STYLE, client)
    brief_rules = client.calls[0][0][0]["content"]
    storyboard_rules = client.calls[1][0][0]["content"]
    assert "Baha" in brief_rules and "B2B" in brief_rules
    assert "Baha" in storyboard_rules and "B2B" in storyboard_rules
    assert "tắt tiếng" in storyboard_rules
    assert "tiền cảnh" in storyboard_rules and "hậu cảnh" in storyboard_rules
    assert "trạng thái trước" in storyboard_rules and "kết quả nhìn thấy" in storyboard_rules
    assert "Không dùng ẩn dụ trừu tượng" in storyboard_rules
    assert "không có người" in storyboard_rules
    assert "Chỉ thêm nhân vật khi" in storyboard_rules
    assert "chuỗi hành động có nguyên nhân và kết quả" in storyboard_rules
    assert "không phải lý do để giảm chuyển động" in storyboard_rules
    assert "không chỉ đứng, vẫy tay, chỉ tay" in storyboard_rules


def test_new_plan_style_allows_object_only_scenes_without_changing_saved_plans():
    from src.modules.tao_video_noi_dung.service import _PILOT_STYLE_SNAPSHOT
    assert "không bắt buộc có nhân vật" in _PILOT_STYLE_SNAPSHOT.visual_rules
    assert "nếu có nhân vật" in _PILOT_STYLE_SNAPSHOT.visual_rules


@pytest.mark.parametrize("narration", ["Tăng 20% doanh thu.", "Hỗ trợ 24/7."])
def test_v4_edit_rejects_digits_and_symbols_in_narration_but_allows_original_ui_text(narration):
    data = v4_data()
    data["shots"][1].update(shot_kind="UI_SIM", action_beats=[], ui_scene={"layout": "CHAT", "messages": [
        {"role": "customer", "text": "AI will answer customer requests 24/7?", "at_s": 0},
        {"role": "ai", "text": "Yes, here is the dashboard.", "at_s": 3}]})
    Storyboard.model_validate(data)
    data["shots"][1]["narration"] = narration
    with pytest.raises(ValueError, match="TTS_"):
        Storyboard.model_validate(data)


def test_v4_phonetic_vietnamese_and_ascii_vietnamese_words_remain_legal():
    data = v4_data()
    data["shots"][0]["narration"] = "Ai cho anh xem vi-đê-ô về mác-két-ting? Ba-ha có giải pháp cho doanh nghiệp."
    assert Storyboard.model_validate(data).shots[0].narration == data["shots"][0]["narration"]


def test_unresolved_pronunciations_skip_acronyms_and_report_english_words():
    from src.modules.tao_video_noi_dung.planner import unresolved_pronunciations
    assert unresolved_pronunciations("Công nghệ AI giúp CEO bán hàng.") == []
    assert unresolved_pronunciations("Công nghệ AI và chatbot giúp CEO.") == ["chatbot"]
    data = v4_data()
    data["shots"][0]["narration"] = "Công nghệ AI và chatbot giúp CEO."
    assert Storyboard.model_validate(data)  # chỉ cảnh báo, không chặn lưu hay chạy


def test_brand_baha_is_not_reported_but_unknown_uppercase_words_are():
    from src.modules.tao_video_noi_dung.planner import unresolved_pronunciations
    assert unresolved_pronunciations("BAHA và BaHa giúp CEO dùng AI.") == []
    assert unresolved_pronunciations("Dùng ABC để bán hàng.") == ["ABC"]


def test_generate_storyboard_retries_with_the_offending_english_word():
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    bad = v4_data()
    bad["shots"][1]["narration"] = "Ba-ha Group giúp doanh nghiệp."
    client = Client(brief_data() | {"needs_ui_demo": False}, bad, v4_data())
    board, _ = generate_storyboard("Nội dung về trợ lý hỗ trợ khách hàng.", 20, STYLE, client)
    assert "Group" not in board.shots[1].narration
    feedback = client.calls[-1][0][-1]["content"]
    assert "TTS_PRONUNCIATION_REQUIRED" in feedback and "Group" in feedback


def test_generate_storyboard_repairs_mechanical_mistakes_instead_of_rejecting():
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    data = v4_data()
    data["shots"][0]["message_ids"] = ["p1", "khong-co"]
    data["shots"][0]["action_beats"] = [{"start_s": 1, "end_s": 4, "action": "A."}, {"start_s": 4, "end_s": 9, "action": "B."}]
    data["shots"][1]["duration_seconds"] = 7
    client = Client(brief_data() | {"needs_ui_demo": False}, data)
    board, _ = generate_storyboard("Nội dung về trợ lý hỗ trợ khách hàng.", 20, STYLE, client)
    assert board.shots[0].message_ids == ["p1"]
    assert [(b.start_s, b.end_s) for b in board.shots[0].action_beats] == [(0, 4), (4, 10)]
    assert sum(shot.duration_seconds for shot in board.shots) == 20 and len(client.calls) == 2


def test_generate_storyboard_retries_once_when_a_shot_has_no_spoken_words():
    from src.modules.tao_video_noi_dung.planner import generate_storyboard
    bad = v4_data()
    bad["shots"][1]["narration"] = "..."
    client = Client(brief_data() | {"needs_ui_demo": False}, bad, v4_data())
    board, _ = generate_storyboard("Nội dung về trợ lý hỗ trợ khách hàng.", 20, STYLE, client)
    assert any(char.isalpha() for char in board.shots[1].narration)
    assert "TTS_NARRATION_EMPTY" in client.calls[-1][0][-1]["content"]


@pytest.mark.parametrize("decorate", [
    lambda raw: raw + "\n\nGhi chú thêm của mô hình.",
    lambda raw: "```json\n" + raw + "\n```",
    lambda raw: raw + '{"thua": 1}',
])
def test_generate_storyboard_ignores_text_around_the_json_object(decorate):
    from src.modules.tao_video_noi_dung.planner import generate_storyboard

    class DecoratedClient(Client):
        def complete(self, messages, max_tokens):
            result = super().complete(messages, max_tokens)
            return SimpleNamespace(content=decorate(result.content), model=result.model)

    client = DecoratedClient(brief_data() | {"needs_ui_demo": False}, v4_data())
    board, _ = generate_storyboard("Nội dung về trợ lý hỗ trợ khách hàng.", 20, STYLE, client)
    assert len(board.shots) == 2
