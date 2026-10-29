from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .planner import Storyboard


class StyleSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_name: str = Field(min_length=2, max_length=120)
    visual_rules: str = Field(min_length=10, max_length=3000)
    palette: list[str] = Field(min_length=1, max_length=8)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"


class CreatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=40, max_length=12000)
    target_duration_seconds: int = Field(ge=20, le=180)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"


class UpdateStoryboardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storyboard: Storyboard


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
    flow_profile_id: str | None = Field(default=None, min_length=1, max_length=64)
    voice_asset_id: str | None = Field(default=None, min_length=1, max_length=36)
    voice_source: Literal["NONE", "UPLOAD", "TTS"] | None = None
    tts_provider: Literal["GWEN_TTS", "VIE_NEU_V3_TURBO"] | None = None
    tts_voice_id: str | None = Field(default=None, min_length=1, max_length=120)
    tts_reference_asset_id: str | None = Field(default=None, min_length=1, max_length=36)
    tts_reference_text: str | None = Field(default=None, max_length=3000)
    voice_clone_consent: bool = False
    include_subtitles: bool = True
    idempotency_key: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_voice_choice(self):
        tts = self.tts_provider is not None
        if self.voice_asset_id and tts:
            raise ValueError("Chỉ được chọn tải voiceover hoặc TTS.")
        if self.voice_source == "UPLOAD" and (not self.voice_asset_id or tts):
            raise ValueError("Nguồn tải lên cần đúng một voiceover.")
        if self.voice_source == "NONE" and self.voice_asset_id:
            raise ValueError("Nguồn không âm thanh không nhận voiceover tải lên.")
        if self.voice_source == "TTS" and not tts:
            raise ValueError("Nguồn TTS cần chọn một provider.")
        if self.voice_source in {"NONE", "UPLOAD"} and tts:
            raise ValueError("Provider TTS chỉ hợp lệ khi chọn nguồn TTS.")
        if self.voice_source == "UPLOAD" and self.tts_reference_asset_id:
            raise ValueError("Voiceover tải lên không nhận cấu hình TTS.")
        if self.tts_provider == "GWEN_TTS":
            if not self.tts_reference_asset_id or not self.tts_reference_text or not self.voice_clone_consent:
                raise ValueError("Gwen cần audio tham chiếu, bản chép chính xác và xác nhận quyền sử dụng giọng.")
        if self.tts_reference_asset_id and not self.voice_clone_consent:
            raise ValueError("Cần xác nhận quyền sử dụng giọng khi dùng audio tham chiếu.")
        if self.tts_reference_text and not self.tts_reference_asset_id:
            raise ValueError("Bản chép tham chiếu cần audio tham chiếu.")
        if not tts and (self.tts_voice_id or self.tts_reference_asset_id or self.tts_reference_text or self.voice_clone_consent):
            raise ValueError("Cấu hình voice clone chỉ hợp lệ khi chọn TTS.")
        return self


class ResumeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flow_profile_id: str | None = Field(default=None, min_length=1, max_length=64)


class RerenderRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_subtitles: bool


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


class RetryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_ids: list[str] = Field(min_length=1, max_length=30)
    new_flow_project: bool = False
    confirm_no_flow_clip: bool = False
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("shot_ids")
    @classmethod
    def unique_nonblank_shots(cls, shot_ids: list[str]) -> list[str]:
        if any(not shot_id.strip() for shot_id in shot_ids) or len(shot_ids) != len(set(shot_ids)):
            raise ValueError("Danh sách shot phải có mã duy nhất và không để trống.")
        return shot_ids


class ContentVideoRunResponse(BaseModel):
    id: str
    project_id: str
    plan_id: str
    plan_revision: int
    voice_asset_id: str | None = None
    voice_source: Literal["NONE", "UPLOAD", "TTS"] = "NONE"
    tts_provider: Literal["GWEN_TTS", "VIE_NEU_V3_TURBO"] | None = None
    include_subtitles: bool = True
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
