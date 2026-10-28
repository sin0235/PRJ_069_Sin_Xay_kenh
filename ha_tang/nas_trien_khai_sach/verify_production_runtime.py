"""Kiểm chứng stack Docker thật qua gateway; không bật cờ test trong ứng dụng."""
from __future__ import annotations

import argparse
from array import array
from datetime import datetime, timezone
import hashlib
from http.cookiejar import CookieJar
import io
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
import uuid
import wave

from nas_runtime_ops import DEFAULT_COMPOSE, ROOT, preflight


def request(opener, origin, path, payload=None, *, request_origin=None):
    headers = {"Origin": request_origin or origin}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    started = time.monotonic()
    try:
        response = opener.open(Request(origin + path, data=data, headers=headers), timeout=15)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read()
        return response.status, raw, dict(response.headers), time.monotonic() - started


def wav_evidence(raw):
    with wave.open(io.BytesIO(raw)) as wav:
        if wav.getsampwidth() != 2 or wav.getnchannels() != 1 or wav.getnframes() <= 0:
            raise AssertionError("TTS must return nonempty mono PCM16 WAV")
        samples = array("h", wav.readframes(wav.getnframes()))
        if sys.byteorder != "little":
            samples.byteswap()
        peak = max(abs(item) for item in samples)
        if peak == 0:
            raise AssertionError("TTS returned silence")
        return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "sample_rate": wav.getframerate(), "duration_seconds": wav.getnframes() / wav.getframerate(),
            "channels": 1, "peak_pcm16": peak,
            "clipped_samples": sum(item in {-32768, 32767} for item in samples),
            "listening_review": "NOT_VERIFIED"}


def docker_sample(container_ids):
    result = subprocess.run(["docker", "inspect", *container_ids], capture_output=True, text=True, timeout=15, check=True)
    rows = json.loads(result.stdout)
    sample = {}
    for row in rows:
        service = row["Config"]["Labels"]["com.docker.compose.service"]
        state = row["State"]
        if not state["Running"] or state.get("OOMKilled"):
            raise AssertionError(f"Container unavailable or OOM: {service}")
        # cgroup includes the inference child, FFmpeg, Chromium and shared memory.
        for path in ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
            result = subprocess.run(["docker", "exec", row["Id"], "cat", path],
                capture_output=True, text=True, timeout=15, check=False)
            if result.returncode == 0:
                break
        if result.returncode:
            raise AssertionError(f"Cannot measure cgroup memory: {service}")
        sample[service] = {"memory_bytes": int(result.stdout), "memory_limit_bytes": row["HostConfig"]["Memory"],
            "restart_count": row["RestartCount"], "oom_killed": state.get("OOMKilled", False)}
    return sample


def verify(args):
    config, _ = preflight(args)
    env = config["services"]["api"]["environment"]
    published = config["services"]["gateway"]["ports"][0]
    origin = next((value.strip() for value in env["AUTH_ALLOWED_ORIGINS"].split(",")
        if value.strip().startswith("http://127.0.0.1:") and value.strip().endswith(f":{published['published']}")), None)
    if not origin:
        raise ValueError("Use an isolated loopback HTTP acceptance origin in AUTH_ALLOWED_ORIGINS")
    compose = ["docker", "compose", "--env-file", str(Path(args.env_file).resolve()),
        "-f", str(Path(args.compose_file).resolve())]
    result = subprocess.run([*compose, "ps", "-q", "api", "flow-session-worker", "web", "gateway"],
        capture_output=True, text=True, timeout=15, check=True)
    ids = result.stdout.split()
    if len(ids) != 4:
        raise AssertionError("All four production containers must be running")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "state": "RUNNING", "project": config["name"],
        "app_env": env["APP_ENV"], "testing": env["TESTING"], "dev_auth_bypass": env["DEV_AUTH_BYPASS"],
        "nas_live": "NOT_VERIFIED", "flow_generation": "NOT_VERIFIED", "jobs": [], "samples": []}

    def save():
        temporary = output / "report.json.tmp"
        temporary.write_text(json.dumps(report, indent=2))
        temporary.replace(output / "report.json")

    started = time.monotonic()
    try:
        anonymous = build_opener()
        status, _, _, _ = request(anonymous, origin, "/v1/voice-studio/jobs")
        assert status == 401, "Unauthenticated media access must be denied"
        jar = CookieJar()
        client = build_opener(HTTPCookieProcessor(jar))
        password = Path(config["secrets"]["owner-password"]["file"]).read_text().rstrip("\r\n")
        status, raw, headers, _ = request(client, origin, "/api/auth/login",
            {"email": env["AUTH_OWNER_EMAIL"], "password": password})
        del password
        assert status == 200 and json.loads(raw).get("success"), "Owner password login failed"
        assert "access_token" not in json.loads(raw), "Browser login must not expose the token"
        assert "httponly" in headers.get("Set-Cookie", "").lower(), "Session cookie must be HttpOnly"
        assert any(cookie.name == "baha_auth_token" for cookie in jar), "Missing session cookie"
        status, raw, _, _ = request(client, origin, "/v1/auth/me")
        assert status == 200 and json.loads(raw)["workspace"]["id"] == env["SIN_WORKSPACE_ID"], "Cookie refresh failed"
        status, _, _, _ = request(client, origin, "/v1/voice-studio/jobs", {}, request_origin="https://untrusted.invalid")
        assert status == 403, "Cross-origin cookie writes must be denied"
        status, raw, _, _ = request(client, origin, "/v1/voice-studio/capabilities")
        capabilities = json.loads(raw)
        assert status == 200 and capabilities["providers"]["VIE_NEU_V3_TURBO"]["state"] == "READY", "Prepare real VieNeu model first"
        assert capabilities["worker"]["state"] == "READY", "Media worker is unavailable"
        assert capabilities["providers"]["GWEN_TTS"]["state"] == "NOT_READY", "Unverified Gwen must be unavailable"
        report["auth"] = "PASS"
        deadline = started + args.duration_seconds
        next_job, next_sample = 0.0, 0.0
        current = None
        while time.monotonic() < deadline or current is not None or not report["jobs"]:
            now = time.monotonic()
            if current is None and (now >= next_job) and (now < deadline or not report["jobs"]):
                payload = {"provider": "VIE_NEU_V3_TURBO", "voice_id": "Hải Đăng",
                    "text": "Xin chào. Hệ thống tạo nội dung đang chạy ổn định trong Docker.", "idempotency_key": str(uuid.uuid4())}
                status, raw, _, latency = request(client, origin, "/v1/voice-studio/jobs", payload)
                assert status == 202, "Real TTS enqueue failed"
                job = json.loads(raw)
                status, repeated, _, _ = request(client, origin, "/v1/voice-studio/jobs", payload)
                assert status == 202 and json.loads(repeated)["job_id"] == job["job_id"], "Idempotency did not reuse the job"
                current = {"job_id": job["job_id"], "started": now, "enqueue_seconds": latency}
                next_job = now + 60
            status, raw, _, latency = request(client, origin, "/readyz")
            assert status == 200 and json.loads(raw)["status"] == "ready", "API became unavailable during inference"
            report["max_readyz_seconds"] = max(report.get("max_readyz_seconds", 0), latency)
            if now >= next_sample:
                sample = docker_sample(ids)
                if report["samples"]:
                    baseline = report["samples"][0]["containers"]
                    assert all(row["restart_count"] == baseline[name]["restart_count"] for name, row in sample.items()), "A container restarted during acceptance"
                report["samples"].append({"elapsed_seconds": now - started, "containers": sample})
                next_sample = now + 5
            if current is not None:
                status, raw, _, _ = request(client, origin, f"/v1/voice-studio/jobs/{current['job_id']}")
                assert status == 200, "Could not poll real TTS job"
                job = json.loads(raw)
                if job["state"] == "SUCCEEDED":
                    status, audio, _, _ = request(client, origin, job["asset"]["url"])
                    assert status == 200, "Owner could not download the generated audio"
                    current["audio"] = wav_evidence(audio)
                    current["duration_seconds"] = time.monotonic() - current.pop("started")
                    if not report["jobs"]:
                        (output / "tts.wav").write_bytes(audio)
                    report["jobs"].append(current)
                    current = None
                elif job["state"] in {"FAILED", "CANCELLED", "NEEDS_RECONCILIATION"}:
                    raise AssertionError(f"Real TTS failed: {job.get('error_code')}")
                elif time.monotonic() - current["started"] > 900:
                    raise AssertionError("Real TTS did not finish within 900 seconds")
            save()
            if time.monotonic() >= deadline and current is None:
                break
            time.sleep(2)
        report["state"] = "PASS"
    except Exception as error:
        report["state"] = "FAIL"
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        save()
    print(json.dumps({"state": report["state"], "jobs": len(report["jobs"]), "report": str(output / "report.json")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-file", default=str(DEFAULT_COMPOSE))
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--output", required=True, help="New private evidence directory; never overwrite")
    parser.add_argument("--duration-seconds", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.duration_seconds <= 3600:
        parser.error("duration must be between 1 and 3600 seconds")
    verify(args)


if __name__ == "__main__":
    main()
