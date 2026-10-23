"""Ghi sự kiện kiểm toán phân quyền dùng chung theo chế độ chỉ ghi nối tiếp."""

import hashlib
import json
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from baha_auth.src.models.entities import AuthorizationAuditEvent


def hash_resource_id(resource_id: Optional[str]) -> Optional[str]:
    if resource_id is None:
        return None
    return hashlib.sha256(resource_id.encode("utf-8")).hexdigest()


def _safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        output = {}
        for key, item in value.items():
            safe_key = str(key)[:80]
            if any(secret_word in safe_key.lower() for secret_word in ("token", "secret", "cookie", "password", "credential")):
                continue
            output[safe_key] = _safe_value(item)
        return output
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value[:30]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value[:500] if isinstance(value, str) else value
    return str(value)[:500]


def write_audit_event(
    db: Session,
    *,
    workspace_id: Optional[str],
    actor_id: Optional[str],
    actor_type: str,
    action_key: str,
    decision: str,
    reason: str,
    policy_version: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None,
    safe_metadata: Optional[Mapping[str, Any]] = None,
) -> AuthorizationAuditEvent:
    """Thêm sự kiện đã làm sạch vào giao dịch của bên gọi; hàm này không tự commit."""
    if decision not in {"ALLOW", "DENY"}:
        raise ValueError("INVALID_AUDIT_DECISION")
    metadata = _safe_value(safe_metadata or {})
    metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(metadata_json) > 2_000:
        metadata_json = json.dumps({"truncated": True}, separators=(",", ":"))

    event = AuthorizationAuditEvent(
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action_key=action_key[:100],
        resource_type=resource_type[:100] if resource_type else None,
        resource_id_hash=hash_resource_id(resource_id),
        decision=decision,
        internal_reason=reason[:255],
        policy_version=policy_version[:50],
        request_id=request_id[:100] if request_id else None,
        safe_metadata_json=metadata_json,
    )
    db.add(event)
    db.flush()
    return event
