from __future__ import annotations

import math
from enum import Enum
from typing import Any, List, Optional, Dict
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LoiHopDong(str, Enum):
    INVALID_RATIONAL = "INVALID_RATIONAL"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    OOB_RANGE = "OOB_RANGE"
    CROSS_WORKSPACE_ASSET = "CROSS_WORKSPACE_ASSET"
    UNSUPPORTED_EFFECT = "UNSUPPORTED_EFFECT"
    OCC_CONFLICT_409 = "OCC_CONFLICT_409"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    NATIVE_EDIT_REQUIRED = "NATIVE_EDIT_REQUIRED"
    BUDGET_OVERRUN = "BUDGET_OVERRUN"
    NAN_VALUE_REJECTED = "NAN_VALUE_REJECTED"
    INVALID_OPERATION_TYPE = "INVALID_OPERATION_TYPE"


class ThoiGianNguon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticks: int = Field(ge=0, description="So tick nguyen duong")
    time_base_num: int = Field(gt=0, description="Tu so cua time base")
    time_base_den: int = Field(gt=0, description="Mau so cua time base")

    @field_validator("ticks", "time_base_num", "time_base_den", mode="before")
    @classmethod
    def validate_int_not_bool(cls, v: Any) -> int:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError("Gia tri thoi gian bat buoc la so nguyen int, khong phai bool hoac float")
        return v

    def to_seconds(self) -> float:
        return (self.ticks * self.time_base_num) / float(self.time_base_den)

    def to_ms(self) -> int:
        return int(round(self.to_seconds() * 1000.0))


class BangChungNguon(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    asset_id: str
    source_sha256: str
    analysis_version: str
    modality: str = Field(description="audio | visual | speech | text")
    source_range: Dict[str, Any] = Field(default_factory=dict)
    word_ids: List[str] = Field(default_factory=list)
    frame_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    notes: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v) or not (0.0 <= v <= 1.0):
                raise ValueError("Confidence phai nam trong doan [0.0, 1.0] va khong duoc la NaN/Inf")
        return v


class ChinhSachPhien(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str = "POLICY_V1_2026_10_23"
    max_turns: int = Field(default=20, ge=1, le=100)
    max_tool_calls: int = Field(default=80, ge=1, le=300)
    max_auto_repairs: int = Field(default=2, ge=0, le=10)
    max_cost_usd: float = Field(default=10.0, gt=0.0)
    deadline_seconds: int = Field(default=1800, ge=60)
    allowed_actions: List[str] = Field(default_factory=lambda: ["split", "trim", "insert", "overwrite", "ripple", "slip", "gain", "caption", "lut", "retime"])
    allowed_providers: List[str] = Field(default_factory=lambda: ["BAHA_FFMPEG", "FLOW_ASSISTED", "GEMINI_OMNI"])

    @field_validator("max_cost_usd")
    @classmethod
    def validate_cost(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v <= 0.0:
            raise ValueError("Chi phi phai la so thuc huu han duong")
        return v


class DinhDanhPhien(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    workspace_id: str
    actor_id: str
    base_revision: int = Field(ge=1)
    base_hash: str
    policy_version: str = "POLICY_V1_2026_10_23"


class LenhDung(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    draft_id: str
    expected_draft_revision: int = Field(ge=1)
    type: str = Field(description="split | trim | insert | overwrite | ripple | slip | gain | caption | lut | retime")
    payload: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = {
            "split_clip", "trim_clip", "insert_clip", "overwrite_clip",
            "ripple_delete", "slip_clip", "set_clip_gain", "set_caption_text",
            "apply_color_lut", "set_retime_speed", "add_track", "add_transition"
        }
        if v not in valid_types:
            raise ValueError(f"Lenh dung {v} khong hop le hoac chua duoc ho tro")
        return v


class KetQuaCongCu(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    status: str = Field(description="SUCCESS | FAILED | REJECTED")
    revision_after: int = Field(ge=1)
    hash_after: str
    changed_ids: List[str] = Field(default_factory=list)
    cost_units: int = Field(default=0, ge=0)
    error_code: Optional[str] = None
    message: str = ""


class ClipV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clip_id: str
    asset_id: str
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    source_in: ThoiGianNguon
    source_out: ThoiGianNguon
    fit_mode: str = Field(default="cover", description="cover | contain")
    gain_db: float = Field(default=0.0, ge=-60.0, le=12.0)
    speed_ratio: float = Field(default=1.0, gt=0.0, le=10.0)
    effects: List[Dict[str, Any]] = Field(default_factory=list)
    lut_asset_id: Optional[str] = None

    @field_validator("gain_db", "speed_ratio")
    @classmethod
    def validate_finite_numbers(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("Gia tri khong duoc la NaN hoac Infinity")
        return v


class TrackV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id: str
    track_type: str = Field(description="video | audio")
    layer_index: int = Field(ge=0)
    name: str = ""
    clips: List[ClipV2] = Field(default_factory=list)
    is_locked: bool = False
    is_muted: bool = False


class CaptionV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caption_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str
    safe_zone: bool = True
    font_name: str = "Arial"

    @model_validator(mode="after")
    def validate_range(self) -> "CaptionV2":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms bat buoc phai lon hon start_ms")
        return self


class TimelineV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 2
    fps_num: int = Field(default=30, gt=0)
    fps_den: int = Field(default=1, gt=0)
    width: int = Field(default=1080, gt=0)
    height: int = Field(default=1920, gt=0)
    tracks: List[TrackV2] = Field(default_factory=list)
    captions: List[CaptionV2] = Field(default_factory=list)
    representation_mode: str = Field(default="CANONICAL", description="CANONICAL | NATIVE_BOUND")
    native_project_asset_id: Optional[str] = None
    native_hash: Optional[str] = None

    def calculate_total_frames(self) -> int:
        total = 0
        for track in self.tracks:
            for clip in track.clips:
                end_frame = clip.start_frame + clip.duration_frames
                if end_frame > total:
                    total = end_frame
        return total

    def calculate_duration_seconds(self) -> float:
        fps = float(self.fps_num) / float(self.fps_den)
        return float(self.calculate_total_frames()) / fps if fps > 0 else 0.0


class KeHoachDung(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    brief_id: str
    base_revision: int = Field(ge=1)
    proposed_commands: List[LenhDung] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)

    @field_validator("estimated_cost_usd")
    @classmethod
    def validate_cost(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError("estimated_cost_usd phai la so thuc huu han")
        return v


class DonSuaCanh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    project_id: str
    draft_id: str
    source_asset_id: str
    source_sha256: str
    source_range: Dict[str, Any] = Field(default_factory=dict)
    target_clip_id: str
    prompt: str
    preserve_list: List[str] = Field(default_factory=list)
    route: str = Field(description="ASSISTED_UI | API_DIRECT")
    reference_asset_ids: List[str] = Field(default_factory=list)


class TrangThaiDonSua(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: str = Field(description="PENDING | COMPLETED | REJECTED | NEEDS_RECONCILIATION")
    output_asset_id: Optional[str] = None
    notes: str = ""


class KetQuaNhapCanh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: str
    asset_id: str
    duration_ms: int
    verified: bool


class BienBanKiemDinh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeline_hash: str
    render_hash: Optional[str] = None
    is_passed: bool
    checks: Dict[str, bool] = Field(default_factory=dict)
    measured_loudness_lufs: Optional[float] = None
    measured_true_peak_dbtp: Optional[float] = None
    reviewer: str = "QA_BOT"
    status: str = Field(default="UNREVIEWED", description="UNREVIEWED | APPROVED | REJECTED")


class GoiBanGiao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    project_id: str
    revision: int
    timeline_hash: str
    export_format: str = "FINAL_CUT_XML"
    files: List[str] = Field(default_factory=list)
    loss_report: Dict[str, Any] = Field(default_factory=dict)


def kiem_tra_ke_hoach(
    plan: KeHoachDung,
    snapshot: TimelineV2,
    evidence: List[BangChungNguon],
    policy: ChinhSachPhien
) -> List[str]:
    errors: List[str] = []

    if plan.estimated_cost_usd > policy.max_cost_usd:
        errors.append(f"{LoiHopDong.BUDGET_OVERRUN}: Uoc tinh chi phi {plan.estimated_cost_usd} vuot han muc {policy.max_cost_usd}")

    if plan.missing_evidence:
        errors.append(f"{LoiHopDong.MISSING_EVIDENCE}: Thieu bang chung can thiet: {', '.join(plan.missing_evidence)}")

    evidence_ids = {e.evidence_id for e in evidence}
    for cmd in plan.proposed_commands:
        for eid in cmd.evidence_ids:
            if eid not in evidence_ids:
                errors.append(f"{LoiHopDong.MISSING_EVIDENCE}: Evidence ID {eid} khong ton tai trong tap bang chung")

        # Kiem tra effect ho tro
        if cmd.type == "apply_color_lut":
            lut_id = cmd.payload.get("lut_asset_id")
            if not lut_id:
                errors.append(f"{LoiHopDong.UNSUPPORTED_EFFECT}: Lenh apply_color_lut thieu lut_asset_id")

    return errors
