"""Hàng đợi tác vụ offline kiểm tra grant và ghim payload trước side effect."""

import json
import os
import time
import uuid
from threading import Lock
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


# Tên tác vụ nội bộ được ánh xạ tĩnh; không lấy action từ payload của job.
TASK_ACTIONS = {
    "research.run": "research.run",
    "ideas.generate": "ideas.create",
    "media.render": "media.edit",
    "content.publish": "publishing.execute",
}

PAYLOAD_BINDING_FIELDS = (
    "workspace_id",
    "resource_id",
    "resource_type",
    "artifact_version",
    "content_hash",
    "policy_version",
)
RESPONSE_BINDING_FIELDS = {
    "workspace_id": "workspace_id",
    "resource_id": "target_resource",
    "resource_type": "resource_type",
    "artifact_version": "artifact_version",
    "content_hash": "content_hash",
    "policy_version": "policy_version",
}


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _http_open(request: Request, timeout: float):
    return build_opener(_NoRedirectHandler).open(request, timeout=timeout)


def _safe_authz_url(base_url: str) -> bool:
    """Chỉ gửi bearer qua HTTPS, trừ loopback để kiểm thử cục bộ."""
    try:
        parsed = urlsplit(base_url)
        host = (parsed.hostname or "").lower()
        loopback = host in {"localhost", "127.0.0.1", "::1"}
        return (
            parsed.scheme == "https" or (parsed.scheme == "http" and loopback)
        ) and bool(host) and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
    except ValueError:
        return False


def _canonical_payload(payload: Any) -> Optional[str]:
    if not isinstance(payload, dict) or any(not isinstance(key, str) for key in payload):
        return None
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return None


def _payload_binding(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    binding = {field: payload.get(field) for field in PAYLOAD_BINDING_FIELDS}
    if not all(isinstance(binding[field], str) and binding[field].strip() for field in (
        "workspace_id", "resource_id", "resource_type", "content_hash", "policy_version"
    )):
        return None
    version = binding["artifact_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return None
    return binding


def _recheck_job_permission(
    job_id: str,
    action_key: str,
    expected_binding: Dict[str, Any],
) -> bool:
    """Yêu cầu Baha Auth xác nhận grant và toàn bộ binding của resource."""
    base_url = os.getenv("BAHA_AUTHZ_BASE_URL")
    service_token = os.getenv("BAHA_AUTH_WORKER_TOKEN")
    if not base_url or not service_token or not _safe_authz_url(base_url):
        return False

    request = Request(
        base_url.rstrip("/") + "/authz/v1/workers/recheck",
        data=json.dumps({"job_id": job_id, "action_key": action_key}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {service_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with _http_open(request, timeout=2) as response:
            if response.status != 200:
                return False
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return False

    if (
        not isinstance(result, dict)
        or result.get("allowed") is not True
        or result.get("job_id") != job_id
        or result.get("action_key") != action_key
    ):
        return False

    return all(
        result.get(response_field) == expected_binding[payload_field]
        for payload_field, response_field in RESPONSE_BINDING_FIELDS.items()
    )


class OfflineTaskQueue:
    """Hàng đợi trong RAM; mọi thay đổi payload sau enqueue đều bị từ chối."""

    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._payload_snapshots: Dict[str, str] = {}
        self._task_snapshots: Dict[str, str] = {}
        self._attempted_jobs = set()
        self._lock = Lock()

    def enqueue(self, task_name: str, payload: Dict[str, Any]) -> str:
        serialized = _canonical_payload(payload)
        if serialized is None:
            raise ValueError("Payload phải là object JSON hợp lệ")

        job_id = f"job_{uuid.uuid4().hex[:8]}"
        payload_snapshot = json.loads(serialized)
        self.jobs[job_id] = {
            "id": job_id,
            "task_name": task_name,
            "payload": payload_snapshot,
            "status": "QUEUED",
            "progress": 0,
            "created_at": time.time(),
            "error": None,
        }
        self._payload_snapshots[job_id] = serialized
        self._task_snapshots[job_id] = task_name
        return job_id

    def get_status(self, job_id: str) -> Dict[str, Any]:
        job = self.jobs.get(job_id)
        if not job:
            return {"status": "NOT_FOUND"}
        return {
            **job,
            "payload": json.loads(self._payload_snapshots[job_id]),
        }

    def _deny(self, job: Dict[str, Any]) -> None:
        job["status"] = "FAILED"
        job["error"] = "Authorization denied"

    def process_sync(self, job_id: str, handler: Callable[[Dict[str, Any]], Any]) -> Any:
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError("Job not found")

        expected_task = self._task_snapshots.get(job_id)
        expected_payload = self._payload_snapshots.get(job_id)
        action_key = TASK_ACTIONS.get(expected_task or "")
        current_payload = _canonical_payload(job.get("payload"))
        payload_snapshot = json.loads(expected_payload) if expected_payload else None
        binding = _payload_binding(payload_snapshot) if isinstance(payload_snapshot, dict) else None

        if (
            job.get("id") != job_id
            or job.get("task_name") != expected_task
            or current_payload != expected_payload
            or job.get("status") != "QUEUED"
            or not action_key
            or binding is None
        ):
            self._deny(job)
            raise PermissionError("Worker authorization denied")

        if not _recheck_job_permission(job_id, action_key, binding):
            self._deny(job)
            raise PermissionError("Worker authorization denied")

        with self._lock:
            if job_id in self._attempted_jobs:
                self._deny(job)
                raise PermissionError("Worker authorization denied")
            self._attempted_jobs.add(job_id)

        # Handler nhận bản copy từ snapshot đã được grant xác nhận, không nhận dict mutable trong queue.
        job["status"] = "PROCESSING"
        job["progress"] = 20
        try:
            result = handler(json.loads(expected_payload))
            job["status"] = "COMPLETED"
            job["progress"] = 100
            job["result"] = result
            return result
        except Exception as exc:
            job["status"] = "FAILED"
            job["error"] = str(exc)
            raise


task_queue = OfflineTaskQueue()
