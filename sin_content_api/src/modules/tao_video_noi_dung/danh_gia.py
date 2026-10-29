"""Chấm cấu trúc kể chuyện; không chứng nhận chất lượng hình ảnh thực tế."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .brief import ContentBrief
    from .planner import Storyboard


@dataclass
class StoryboardScore:
    coverage: float
    pain_before_solution: bool
    static_shot_ratio: float
    text_dependent_shots: int
    issues: list[str]


def score_storyboard(storyboard: Storyboard, brief: ContentBrief | None = None) -> StoryboardScore:
    brief = brief or getattr(storyboard, "brief", None)
    required = {message.id for message in brief.all_messages()} if brief else set()
    covered = {mid for shot in storyboard.shots for mid in getattr(shot, "message_ids", [])}
    coverage = len(required & covered) / len(required) if required else 1.0
    beats = [getattr(shot, "beat", None) for shot in storyboard.shots]
    has_pain = "PAIN" in beats
    ordered = has_pain and ("SOLUTION" not in beats or beats.index("PAIN") < beats.index("SOLUTION"))
    issues = []
    if not has_pain:
        issues.append("NO_PAIN_BEAT")
    elif not ordered:
        issues.append("PAIN_AFTER_SOLUTION")
    if coverage < 1.0:
        issues.append("LOW_COVERAGE")
    static = sum(shot.duration_seconds > 3 and len(getattr(shot, "action_beats", [])) <= 1 for shot in storyboard.shots)
    return StoryboardScore(
        coverage, ordered, static / len(storyboard.shots),
        sum(getattr(shot, "shot_kind", None) == "UI_SIM" for shot in storyboard.shots), issues,
    )
