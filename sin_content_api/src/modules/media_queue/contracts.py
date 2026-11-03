from dataclasses import dataclass

# Kế hoạch tối đa 100 clip, mỗi clip tối đa 20 cảnh; worker vẫn chạy tuần tự.
GIOI_HAN_TAC_VU_DIEN_HOA = 100 * 20


@dataclass(frozen=True)
class DeferredMediaJob:
    request_payload_json: str
    status_message: str
