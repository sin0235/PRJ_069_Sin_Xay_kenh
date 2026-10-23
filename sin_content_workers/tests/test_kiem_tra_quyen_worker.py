"""Kiểm thử worker từ chối mặc định và ghim binding trước side effect."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import worker
from worker import OfflineTaskQueue


def payload_hop_le():
    return {
        "workspace_id": "tenant-a",
        "resource_id": "resource-a",
        "resource_type": "research_run",
        "artifact_version": 3,
        "content_hash": "a" * 64,
        "policy_version": "rbac-v1",
        "action_key": "publishing.execute",
    }


def binding_response(job_id, action_key, **overrides):
    binding = {
        "allowed": True,
        "job_id": job_id,
        "action_key": action_key,
        "workspace_id": "tenant-a",
        "target_resource": "resource-a",
        "resource_type": "research_run",
        "artifact_version": 3,
        "content_hash": "a" * 64,
        "policy_version": "rbac-v1",
    }
    binding.update(overrides)
    return binding


class JsonResponse:
    status = 200

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.value).encode("utf-8")


def cai_dat_recheck(monkeypatch, response_factory=None, request_log=None):
    monkeypatch.setenv("BAHA_AUTHZ_BASE_URL", "https://authz.test")
    monkeypatch.setenv("BAHA_AUTH_WORKER_TOKEN", "token-gia-lap")

    def fake_http_open(request, timeout):
        if request_log is not None:
            request_log.append((request, timeout))
        request_body = json.loads(request.data.decode("utf-8"))
        response = response_factory(request_body) if response_factory else binding_response(
            request_body["job_id"], request_body["action_key"]
        )
        return JsonResponse(response)

    monkeypatch.setattr(worker, "_http_open", fake_http_open)


def test_worker_khong_chay_khi_thieu_dich_vu_tai_kiem_quyen(monkeypatch):
    monkeypatch.delenv("BAHA_AUTHZ_BASE_URL", raising=False)
    monkeypatch.delenv("BAHA_AUTH_WORKER_TOKEN", raising=False)
    queue = OfflineTaskQueue()
    job_id = queue.enqueue("research.run", payload_hop_le())
    da_chay = False

    def handler(payload):
        nonlocal da_chay
        da_chay = True
        return payload

    with pytest.raises(PermissionError):
        queue.process_sync(job_id, handler)

    assert da_chay is False
    assert queue.get_status(job_id)["status"] == "FAILED"


def test_action_va_binding_den_recheck_khong_lay_tu_payload_gia(monkeypatch):
    request_log = []
    cai_dat_recheck(monkeypatch, request_log=request_log)
    queue = OfflineTaskQueue()
    payload = payload_hop_le()
    expected_payload = dict(payload)
    job_id = queue.enqueue("research.run", payload)
    payload["resource_id"] = "payload-ngoai-hang-doi-da-bi-doi"

    assert queue.process_sync(job_id, lambda received: received) == expected_payload
    request, timeout = request_log[0]
    assert request.get_full_url() == "https://authz.test/authz/v1/workers/recheck"
    assert timeout == 2
    assert request.get_header("Authorization") == "Bearer token-gia-lap"
    assert json.loads(request.data.decode("utf-8")) == {
        "job_id": job_id,
        "action_key": "research.run",
    }


@pytest.mark.parametrize(
    "field, value",
    [
        ("workspace_id", "tenant-khac"),
        ("resource_id", "resource-cua-tenant-khac"),
        ("artifact_version", 4),
    ],
)
def test_payload_sua_trong_queue_sau_enqueue_bi_tu_choi(monkeypatch, field, value):
    monkeypatch.setenv("BAHA_AUTHZ_BASE_URL", "https://authz.test")
    monkeypatch.setenv("BAHA_AUTH_WORKER_TOKEN", "token-gia-lap")
    da_goi_recheck = False

    def khong_duoc_goi(*_args, **_kwargs):
        nonlocal da_goi_recheck
        da_goi_recheck = True
        raise AssertionError("Payload đã đổi thì không gọi dịch vụ recheck")

    monkeypatch.setattr(worker, "_http_open", khong_duoc_goi)
    queue = OfflineTaskQueue()
    job_id = queue.enqueue("research.run", payload_hop_le())
    queue.jobs[job_id]["payload"][field] = value
    da_chay = False

    def handler(_payload):
        nonlocal da_chay
        da_chay = True

    with pytest.raises(PermissionError):
        queue.process_sync(job_id, handler)

    assert da_goi_recheck is False
    assert da_chay is False
    assert queue.get_status(job_id)["status"] == "FAILED"


def test_binding_authz_khac_resource_thi_tu_choi(monkeypatch):
    cai_dat_recheck(
        monkeypatch,
        response_factory=lambda body: binding_response(
            body["job_id"], body["action_key"], target_resource="resource-b"
        ),
    )
    queue = OfflineTaskQueue()
    job_id = queue.enqueue("research.run", payload_hop_le())
    da_chay = False

    def handler(_payload):
        nonlocal da_chay
        da_chay = True

    with pytest.raises(PermissionError):
        queue.process_sync(job_id, handler)

    assert da_chay is False
    assert queue.get_status(job_id)["status"] == "FAILED"


def test_timeout_tai_recheck_khong_goi_handler(monkeypatch):
    monkeypatch.setenv("BAHA_AUTHZ_BASE_URL", "https://authz.test")
    monkeypatch.setenv("BAHA_AUTH_WORKER_TOKEN", "token-gia-lap")
    monkeypatch.setattr(worker, "_http_open", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))
    queue = OfflineTaskQueue()
    job_id = queue.enqueue("research.run", payload_hop_le())
    da_chay = False

    def handler(_payload):
        nonlocal da_chay
        da_chay = True

    with pytest.raises(PermissionError):
        queue.process_sync(job_id, handler)

    assert da_chay is False
    assert queue.get_status(job_id)["status"] == "FAILED"


@pytest.mark.parametrize("overrides", [
    {"action_key": "publishing.execute"},
    {"content_hash": "b" * 64},
    {"artifact_version": 4},
    {"policy_version": "rbac-v2"},
    {"workspace_id": "tenant-b"},
])
def test_binding_authz_khong_khop_job_thi_tu_choi(monkeypatch, overrides):
    cai_dat_recheck(
        monkeypatch,
        response_factory=lambda body: {
            **binding_response(body["job_id"], body["action_key"]),
            **overrides,
        },
    )
    queue = OfflineTaskQueue()
    job_id = queue.enqueue("research.run", payload_hop_le())
    da_chay = False

    def handler(_payload):
        nonlocal da_chay
        da_chay = True

    with pytest.raises(PermissionError):
        queue.process_sync(job_id, handler)

    assert da_chay is False
    assert queue.get_status(job_id)["status"] == "FAILED"


def test_http_toi_may_chu_khong_loopback_khong_duoc_gui_token(monkeypatch):
    monkeypatch.setenv("BAHA_AUTHZ_BASE_URL", "http://authz.example")
    monkeypatch.setenv("BAHA_AUTH_WORKER_TOKEN", "token-gia-lap")
    monkeypatch.setattr(
        worker,
        "_http_open",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Không được gửi bearer qua HTTP")),
    )
    queue = OfflineTaskQueue()
    job_id = queue.enqueue("research.run", payload_hop_le())

    with pytest.raises(PermissionError):
        queue.process_sync(job_id, lambda _payload: pytest.fail("Handler không được chạy"))

    assert queue.get_status(job_id)["status"] == "FAILED"


def test_recheck_khong_theo_redirect_de_khong_ro_token_dich_vu():
    handler = worker._NoRedirectHandler()
    request = worker.Request("https://authz.test/authz/v1/workers/recheck")

    assert handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://other.test/collect",
    ) is None

