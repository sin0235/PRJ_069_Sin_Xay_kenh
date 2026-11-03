"""Khung 9:16: dùng được mọi loại sơ đồ (dựng ngang rồi mở rộng); shot Flow dài 10 giây, shot sơ đồ 3 đến 6 giây; shot sai hợp đồng đổi sang Flow."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from src.modules.tao_video_noi_dung import planner
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
        index = min(len(self.calls), len(self.responses)) - 1   # hết phản hồi thì lặp lại phản hồi cuối (lượt sửa lời đọc mềm)
        return SimpleNamespace(content=json.dumps(self.responses[index], ensure_ascii=False), model="test-model")


def _with_scene(index, ui_scene):
    data = copy.deepcopy(BASE)
    shot = data["shots"][index]
    shot["shot_kind"], shot["ui_scene"], shot["action_beats"] = "UI_SIM", ui_scene, []
    shot["continues_previous"] = False
    return data


def _process_rail(index):
    words = BASE["shots"][index]["narration"].split()
    return {"layout": "PROCESS_RAIL", "messages": [], "highlight": None, "diagram": {
        "title": "Luồng xử lý", "steps": ["Nhận", "Duyệt", "Giao"], "block_step": 1,
        "on": {"stations": words[0], "block": words[1], "release": words[2]}}}   # sớm trong lời, vì shot sơ đồ có thể co còn 3 giây


def _run(*storyboards):
    client = Client(BASE["brief"], *storyboards)
    result = planner.generate_storyboard(CONTENT, 100, STYLE, client)
    return result, client


def test_portrait_prompt_allows_every_diagram_layout():
    (_, _), client = _run(copy.deepcopy(BASE))
    system = client.calls[-1][0]["content"]
    assert "KHUNG 9:16" in system and "mở rộng thành khung dọc" in system
    assert "chỉ dùng BEFORE_AFTER, KPI_CARDS, VERSUS_LIST, CHECKLIST" not in system
    assert "ĐÚNG 10 giây" in system


def test_landscape_only_layout_is_kept_in_portrait():
    # Độ dài lời đọc lệch ngân sách sau khi co shot có thể kích hoạt thêm lượt thử mềm; cấp sẵn đủ lượt và chỉ kiểm kết quả cuối.
    (storyboard, _), client = _run(*[_with_scene(9, _process_rail(9)) for _ in range(3)])
    assert not any("DIAGRAM_" in str(m.get("content", ""))[-300:] for m in client.calls[-1][-1:])   # không bị báo lỗi sơ đồ
    shot = storyboard.shots[9]
    assert shot.shot_kind == "UI_SIM" and shot.ui_scene.layout == "PROCESS_RAIL"
    assert sum(s.duration_seconds for s in storyboard.shots) == 100
    assert planner.UI_SHOT_MIN_SECONDS <= shot.duration_seconds <= planner.UI_SHOT_MAX_SECONDS


def test_bad_diagram_after_all_attempts_is_demoted_not_fatal():
    bad = {"layout": "CHECKLIST", "messages": [], "highlight": None, "diagram": {"title": "Việc cần làm", "steps": ["chỉ một"]}}
    (storyboard, _), client = _run(*[_with_scene(9, bad) for _ in range(3)])
    assert len(client.calls) == 4   # brief + 3 lượt storyboard
    assert storyboard.shots[9].shot_kind == "FLOW_ORIGAMI"
    assert sum(s.duration_seconds for s in storyboard.shots) == 100


def test_valid_storyboard_keeps_total_duration():
    (storyboard, _), client = _run(copy.deepcopy(BASE))
    assert len(client.calls) == 2
    assert sum(s.duration_seconds for s in storyboard.shots) == 100
    assert all(planner.FLOW_SHOT_MIN_SECONDS <= s.duration_seconds <= planner.FLOW_SHOT_SECONDS for s in storyboard.shots)


def _shots(flow, ui, ui_seconds=6):
    return [{"shot_kind": "FLOW_ORIGAMI", "duration_seconds": 6} for _ in range(flow)] + \
           [{"shot_kind": "UI_SIM", "duration_seconds": ui_seconds} for _ in range(ui)]


def test_flow_shots_stay_near_ten_seconds_and_ui_shots_keep_their_time():
    shots = _shots(6, 7)   # 60 + 42 = 102: thừa 2 giây
    planner._fit_shot_durations(shots, 100)
    assert sum(s["duration_seconds"] for s in shots) == 100
    assert [s["duration_seconds"] for s in shots[6:]] == [6] * 7           # sơ đồ giữ đủ thời gian cho các mốc
    assert all(7 <= s["duration_seconds"] <= 10 for s in shots[:6])        # Flow chỉ bị cắt đuôi nhẹ


def test_ui_shots_grow_when_time_is_short_and_flow_never_exceeds_ten():
    shots = _shots(5, 4, ui_seconds=3)   # 50 + 12 = 62, cần 80: sơ đồ dài thêm (6 giây, rồi tối đa 10 nếu vẫn thiếu); Flow giữ 10
    planner._fit_shot_durations(shots, 80)
    assert [s["duration_seconds"] for s in shots[:5]] == [10] * 5
    assert sum(s["duration_seconds"] for s in shots) == 80
    assert all(3 <= s["duration_seconds"] <= 10 for s in shots[5:])


def test_total_cannot_be_reached_when_everything_is_at_its_maximum():
    shots = _shots(2, 2)   # tối đa 20 + 20 = 40
    planner._fit_shot_durations(shots, 100)
    assert sum(s["duration_seconds"] for s in shots) == 40   # để parse_storyboard báo lỗi và lượt thử lại xử lý


def test_flow_shots_shrink_before_ui_shots_when_far_over():
    shots = _shots(17, 0)
    planner._fit_shot_durations(shots, 100)
    assert sum(s["duration_seconds"] for s in shots) == 100
    assert all(5 <= s["duration_seconds"] <= 10 for s in shots)


def test_flow_shot_after_ui_shot_cannot_continue_it():
    shots = [
        {"shot_kind": "FLOW_ORIGAMI", "duration_seconds": 10, "continues_previous": True},
        {"shot_kind": "UI_SIM", "duration_seconds": 5, "continues_previous": True, "ui_scene": {"layout": "CHECKLIST", "messages": []}},
        {"shot_kind": "FLOW_ORIGAMI", "duration_seconds": 10, "continues_previous": True},
        {"shot_kind": "FLOW_ORIGAMI", "duration_seconds": 10, "continues_previous": True},
    ]
    planner._repair_shot_sequence(shots)
    assert [s["continues_previous"] for s in shots] == [False, False, False, True]   # chỉ giữ khi Flow nối Flow


def test_message_times_are_refit_when_ui_shot_shrinks():
    shots = [{"shot_kind": "UI_SIM", "duration_seconds": 3, "continues_previous": False, "ui_scene": {"layout": "CHAT", "messages": [
        {"role": "customer", "text": "a", "at_s": 0}, {"role": "ai", "text": "b", "at_s": 2.5}, {"role": "ai", "text": "c", "at_s": 4.5}]}}]
    planner._repair_shot_sequence(shots)
    times = [m["at_s"] for m in shots[0]["ui_scene"]["messages"]]
    assert times == sorted(times) and times[0] == 0 and times[-1] < 3


def _storyboard_with(index, ui_scene, seconds):
    data = _with_scene(index, ui_scene) if ui_scene else copy.deepcopy(BASE)
    data["shots"][index]["duration_seconds"] = seconds
    return planner.Storyboard.model_validate(data)


def test_sparse_diagram_is_flagged_when_events_end_early():
    problems = planner._richness_problems(_storyboard_with(9, _process_rail(9), 8))
    assert any(p.startswith("DIAGRAM_SPARSE: s10") for p in problems)


def test_short_diagram_shot_is_not_flagged_for_sparseness():
    assert not [p for p in planner._richness_problems(_storyboard_with(9, _process_rail(9), 4)) if p.startswith("DIAGRAM_SPARSE")]


def test_thin_flow_beats_are_flagged_and_rich_ones_pass():
    data = copy.deepcopy(BASE)
    shot = data["shots"][0]
    shot["duration_seconds"] = 10
    shot["action_beats"] = [{"start_s": 0.0, "end_s": 5.0, "action": "Người quản lý mở báo cáo"}, {"start_s": 5.0, "end_s": 10.0, "action": "Số liệu hiện ra"}]
    assert any(p.startswith(f"FLOW_BEATS_THIN: {BASE['shots'][0]['shot_id']} ") for p in planner._richness_problems(planner.Storyboard.model_validate(data)))
    shot["action_beats"] = [
        {"start_s": 0.0, "end_s": 2.5, "action": "Người quản lý giấy mở tập báo cáo dày trên bàn làm việc"},
        {"start_s": 2.5, "end_s": 5.0, "action": "Các cột số đỏ bật lên khỏi trang giấy và đổ bóng xuống mặt bàn"},
        {"start_s": 5.0, "end_s": 7.5, "action": "Tờ lịch cuối tháng rơi xuống che một nửa tập báo cáo trước mặt người quản lý"},
        {"start_s": 7.5, "end_s": 10.0, "action": "Camera đẩy vào gương mặt lo lắng khi chiếc đồng hồ cát trên bàn đổ hết cát"},
    ]
    assert not [p for p in planner._richness_problems(planner.Storyboard.model_validate(data)) if p.startswith(f"FLOW_BEATS_THIN: {BASE['shots'][0]['shot_id']} ")]


def test_low_content_layouts_stay_short_when_time_allows():
    shots = [{"shot_kind": "FLOW_ORIGAMI", "duration_seconds": 10} for _ in range(8)] + [
        {"shot_kind": "UI_SIM", "duration_seconds": 9, "ui_scene": {"layout": "OPEN_QUESTION"}},
        {"shot_kind": "UI_SIM", "duration_seconds": 9, "ui_scene": {"layout": "END_CARD"}},
        {"shot_kind": "UI_SIM", "duration_seconds": 6, "ui_scene": {"layout": "CHECKLIST"}},
    ]
    planner._fit_shot_durations(shots, 80 + 4 + 5 + 6)
    assert [s["duration_seconds"] for s in shots[8:]] == [4, 5, 6]


def test_layout_caps_are_relaxed_when_total_cannot_otherwise_be_reached():
    shots = [{"shot_kind": "UI_SIM", "duration_seconds": 9, "ui_scene": {"layout": "OPEN_QUESTION"}}]
    planner._fit_shot_durations(shots, 8)
    assert shots[0]["duration_seconds"] == 8   # không báo lỗi tổng; kiểm tra độ giàu nội dung sẽ yêu cầu LLM làm lại


def test_stretched_ui_shot_is_reported_with_suggested_shot_counts():
    problems = planner._richness_problems(_storyboard_with(9, _process_rail(9), 9))
    stretched = [p for p in problems if p.startswith("UI_SHOT_STRETCHED: s10")]
    assert stretched and "khoảng" in stretched[0] and "shot Flow" in stretched[0]


def test_suggested_shot_counts_follow_the_flow_budget():
    flow, ui = planner._suggested_shot_counts(100)
    assert flow * planner.FLOW_SHOT_SECONDS <= 0.7 * 100 and flow * 10 + ui * 6 >= 100
    assert planner._suggested_shot_counts(20) == (1, 2)
