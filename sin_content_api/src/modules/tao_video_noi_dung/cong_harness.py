from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from src.models.entities import ContentVideoPlan, ContentVideoRun, MediaAsset
from src.modules.media_studio.video_provider import video_orchestrator
from .planner import StoryboardShot, build_shot_prompt


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def approval_receipt_hash(plan: ContentVideoPlan) -> str:
    return canonical_hash({
        "plan_id": plan.id,
        "revision": plan.revision,
        "approved_by": plan.approved_by,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
        "storyboard_sha256": plan.storyboard_sha256,
        "style_snapshot_sha256": plan.style_snapshot_sha256,
    })


def build_shot_receipt(
    *,
    run_id: str,
    workspace_id: str,
    project_id: str,
    plan: ContentVideoPlan,
    voice_asset_id: str | None,
    shot: StoryboardShot,
    style_snapshot: dict[str, Any],
    continuity_anchor: str,
) -> dict[str, Any]:
    command = {
        "operation_id": str(uuid.uuid4()),
        "workspace_id": workspace_id,
        "project_id": project_id,
        "run_id": run_id,
        "plan_id": plan.id,
        "plan_revision": plan.revision,
        "voice_asset_id": voice_asset_id,
        "shot_id": shot.shot_id,
        "style_snapshot_sha256": plan.style_snapshot_sha256,
        "approval_sha256": approval_receipt_hash(plan),
        "prompt": build_shot_prompt(style_snapshot, shot, continuity_anchor),
        "aspect_ratio": "9:16",
        "duration_seconds": shot.duration_seconds,
    }
    return {**command, "command_sha256": canonical_hash(command), "state": "READY", "asset_id": None}


def verify_shot_receipt(run: ContentVideoRun, plan: ContentVideoPlan, shot: StoryboardShot, step: dict[str, Any]) -> dict[str, Any]:
    if (
        plan.status != "APPROVED"
        or not plan.approved_by
        or not plan.approved_at
        or run.workspace_id != plan.workspace_id
        or run.project_id != plan.project_id
        or run.plan_id != plan.id
        or run.plan_revision != plan.revision
        or run.storyboard_sha256 != plan.storyboard_sha256
        or run.style_snapshot_sha256 != plan.style_snapshot_sha256
        or run.approval_sha256 != approval_receipt_hash(plan)
    ):
        raise RuntimeError("APPROVAL_RECEIPT_INVALID")

    style = json.loads(plan.style_snapshot_json)
    storyboard = json.loads(plan.storyboard_json)
    if canonical_hash(style) != plan.style_snapshot_sha256 or canonical_hash(storyboard) != plan.storyboard_sha256:
        raise RuntimeError("APPROVED_PLAN_HASH_CHANGED")
    if not step.get("operation_id"):
        raise RuntimeError("HARNESS_COMMAND_RECEIPT_INVALID")
    expected = {
        "operation_id": step.get("operation_id"),
        "workspace_id": run.workspace_id,
        "project_id": run.project_id,
        "run_id": run.id,
        "plan_id": plan.id,
        "plan_revision": plan.revision,
        "voice_asset_id": run.voice_asset_id,
        "shot_id": shot.shot_id,
        "style_snapshot_sha256": plan.style_snapshot_sha256,
        "approval_sha256": run.approval_sha256,
        "prompt": build_shot_prompt(style, shot, storyboard["continuity_anchor"]),
        "aspect_ratio": "9:16",
        "duration_seconds": shot.duration_seconds,
    }
    if step.get("state") not in {"READY", "SUBMITTING", "SUCCEEDED", "NEEDS_RECONCILIATION"}:
        raise RuntimeError("HARNESS_COMMAND_STATE_INVALID")
    if any(step.get(key) != value for key, value in expected.items()):
        raise RuntimeError("HARNESS_COMMAND_RECEIPT_INVALID")
    if step.get("command_sha256") != canonical_hash(expected):
        raise RuntimeError("HARNESS_COMMAND_RECEIPT_INVALID")
    return expected


def dispatch_shot(
    *,
    db,
    run: ContentVideoRun,
    plan: ContentVideoPlan,
    shot: StoryboardShot,
    step: dict[str, Any],
    start_image_path=None,
    start_image_asset_id: str | None = None,
    flow_project_url: str | None = None,
    on_flow_project_created=None,
) -> MediaAsset:
    command = verify_shot_receipt(run, plan, shot, step)
    if step.get("state") != "SUBMITTING":
        raise RuntimeError("HARNESS_COMMAND_NOT_CLAIMED")
    return video_orchestrator.generate_video_scene(
        db=db,
        workspace_id=command["workspace_id"],
        user_id=run.created_by,
        project_id=command["project_id"],
        prompt=command["prompt"],
        aspect_ratio=command["aspect_ratio"],
        start_image_path=start_image_path,
        start_image_asset_id=start_image_asset_id,
        remove_watermark=False,
        flow_project_url=flow_project_url,
        on_flow_project_created=on_flow_project_created,
    )
