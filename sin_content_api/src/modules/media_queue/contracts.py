from dataclasses import dataclass


@dataclass(frozen=True)
class DeferredMediaJob:
    request_payload_json: str
    status_message: str
