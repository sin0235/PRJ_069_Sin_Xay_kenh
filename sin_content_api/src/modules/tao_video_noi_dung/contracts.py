from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .planner import Storyboard


class StyleSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_name: str = Field(min_length=2, max_length=120)
    visual_rules: str = Field(min_length=10, max_length=3000)
    palette: list[str] = Field(min_length=1, max_length=8)


class CreatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=40, max_length=12000)
    target_duration_seconds: int = Field(ge=30, le=180)


class ContentVideoPlanResponse(BaseModel):
    id: str
    project_id: str
    revision: int
    status: str
    source_content: str
    content_sha256: str
    target_duration_seconds: int
    style_snapshot: StyleSnapshot
    style_snapshot_sha256: str
    storyboard: Storyboard
    storyboard_sha256: str
    llm_model: str
    created_by: str
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1, max_length=36)
    voice_asset_id: str | None = Field(default=None, min_length=1, max_length=36)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ReconcileShotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str = Field(min_length=1, max_length=64)
    asset_id: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=12, max_length=500)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 12:
            raise ValueError("Cần ghi lý do đối soát cụ thể.")
        return value


class ContentVideoRunResponse(BaseModel):
    id: str
    project_id: str
    plan_id: str
    plan_revision: int
    voice_asset_id: str | None = None
    status: str
    current_step: str | None = None
    steps: list[dict]
    output_asset_ids: list[str]
    final_asset_id: str | None = None
    qc_report: dict | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
