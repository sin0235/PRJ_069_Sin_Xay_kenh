from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TTSAdvancedSettings(BaseModel):
    temperature: float | None = Field(default=None, ge=0.1, le=1.5)
    top_k: int | None = Field(default=None, ge=1, le=100)
    top_p: float | None = Field(default=None, gt=0, le=1)
    repetition_penalty: float | None = Field(default=None, ge=1, le=2.5)
    denoise_reference: bool | None = None
    use_reference_codes: bool | None = None
    max_new_frames: int | None = Field(default=None, ge=50, le=1000)
    max_chars: int | None = Field(default=None, ge=32, le=512)
    max_new_tokens: int | None = Field(default=None, ge=64, le=8192)
    x_vector_only_mode: bool | None = None


class VoiceProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: Literal["GWEN_TTS", "VIE_NEU_V3_TURBO"]
    reference_asset_id: str = Field(min_length=1, max_length=100)
    reference_text: str | None = Field(default=None, max_length=1000)
    voice_clone_consent: bool = False

    @field_validator("name", "reference_text")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_voice(self):
        if not self.name:
            raise ValueError("Tên giọng không được để trống.")
        if not self.voice_clone_consent:
            raise ValueError("Cần xác nhận quyền sử dụng audio để clone giọng.")
        if self.provider == "GWEN_TTS" and not self.reference_text:
            raise ValueError("Gwen-TTS cần bản chép lời chính xác của audio tham chiếu.")
        return self


class VoiceStudioCreateRequest(BaseModel):
    provider: Literal["GWEN_TTS", "VIE_NEU_V3_TURBO"]
    text: str = Field(min_length=1, max_length=5000)
    voice_id: str | None = Field(default=None, max_length=80)
    voice_profile_id: str | None = Field(default=None, max_length=100)
    reference_asset_id: str | None = Field(default=None, max_length=100)
    reference_text: str | None = Field(default=None, max_length=1000)
    voice_clone_consent: bool = False
    pronunciation_dictionary: str | None = Field(default=None, max_length=10000)
    advanced: TTSAdvancedSettings = Field(default_factory=TTSAdvancedSettings)
    idempotency_key: str = Field(min_length=1, max_length=36)

    @field_validator("text", "reference_text")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_voice(self):
        if not self.text:
            raise ValueError("Nội dung cần đọc không được để trống.")
        if self.voice_profile_id and (self.reference_asset_id or self.reference_text):
            raise ValueError("Chọn voice đã lưu hoặc audio tham chiếu trực tiếp.")
        if self.provider == "GWEN_TTS" and not self.voice_profile_id and (not self.reference_asset_id or not self.reference_text):
            raise ValueError("Gwen-TTS cần voice đã lưu hoặc audio tham chiếu và bản chép lời.")
        if self.reference_asset_id and not self.voice_clone_consent:
            raise ValueError("Cần xác nhận quyền sử dụng audio để clone giọng.")
        if self.reference_text and not self.reference_asset_id:
            raise ValueError("Bản chép lời chỉ dùng cùng audio tham chiếu.")
        vietneu_fields = {"denoise_reference", "use_reference_codes", "max_new_frames", "max_chars"}
        gwen_fields = {"max_new_tokens", "x_vector_only_mode"}
        values = self.advanced.model_dump(exclude_none=True)
        if self.provider == "GWEN_TTS" and vietneu_fields.intersection(values):
            raise ValueError("Cài đặt này chỉ áp dụng cho VieNeu v3 Turbo.")
        if self.provider == "VIE_NEU_V3_TURBO" and gwen_fields.intersection(values):
            raise ValueError("Cài đặt này chỉ áp dụng cho Gwen-TTS.")
        return self


class VoiceStudioSettingsUpdateRequest(BaseModel):
    pronunciation_dictionary: str = Field(default="", max_length=10000)
