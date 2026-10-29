import json
from pathlib import Path

from src.modules.tao_video_noi_dung.planner import Storyboard
from src.modules.tao_video_noi_dung.danh_gia import score_storyboard


def baseline():
    return json.loads((Path(__file__).parent / "fixtures/storyboard_ai_sales_v3.json").read_text())


def test_baseline_ai_sales_storyboard_fails_quality_gates():
    score = score_storyboard(Storyboard.model_validate(baseline()))
    assert score.static_shot_ratio == 1.0
    assert score.pain_before_solution is False
    assert "NO_PAIN_BEAT" in score.issues
