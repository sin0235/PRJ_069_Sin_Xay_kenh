from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = ROOT / "ha_tang/nas_trien_khai_sach/compose.yaml"


@unittest.skipUnless(
    os.environ.get("PRJ069_RUNTIME_ENV_FILE"),
    "set PRJ069_RUNTIME_ENV_FILE to run against a live isolated Compose stack",
)
class GatewayReadinessRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env_file = Path(os.environ["PRJ069_RUNTIME_ENV_FILE"]).expanduser().resolve()
        cls.compose_file = Path(os.environ.get("PRJ069_RUNTIME_COMPOSE_FILE", COMPOSE_FILE)).resolve()
        config = cls._compose("config", "--format", "json", check=True)
        rendered = json.loads(config.stdout)
        services = rendered["services"]
        cls.project = rendered["name"]
        published = services["gateway"]["ports"][0]
        host = published.get("host_ip") or "127.0.0.1"
        if host in {"0.0.0.0", "::"}:
            host = "127.0.0.1"
        cls.base_url = f"http://{host}:{published['published']}"
        running = cls._compose("ps", "--status", "running", "--services", check=True).stdout.splitlines()
        if not {"api", "gateway"}.issubset(running):
            raise AssertionError("the isolated API and gateway services must already be running")

    @classmethod
    def _compose(cls, *args, check=False):
        command = ["docker", "compose"]
        if hasattr(cls, "project"):
            command.extend(["--project-name", cls.project])
        result = subprocess.run(
            [
                *command,
                "--env-file",
                str(cls.env_file),
                "-f",
                str(cls.compose_file),
                *args,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode:
            raise AssertionError("Docker Compose runtime readiness check could not run")
        return result

    @classmethod
    def _http_status(cls, path):
        try:
            with urlopen(cls.base_url + path, timeout=4) as response:
                return response.status
        except HTTPError as error:
            return error.code
        except URLError:
            return None

    @classmethod
    def _wait_for_status(cls, path, expected, timeout_seconds):
        deadline = time.monotonic() + timeout_seconds
        last_status = None
        while time.monotonic() < deadline:
            last_status = cls._http_status(path)
            if last_status == expected:
                return last_status
            time.sleep(1)
        raise AssertionError(f"gateway {path} did not return HTTP {expected}; last status={last_status}")

    def test_gateway_health_and_readiness_fail_when_api_is_stopped(self):
        for path in ("/healthz", "/readyz"):
            self._wait_for_status(path, 200, timeout_seconds=15)

        stopped = False
        try:
            self._compose("stop", "--timeout", "15", "api", check=True)
            stopped = True
            deadline = time.monotonic() + 20
            observed = {"/healthz": None, "/readyz": None}
            while time.monotonic() < deadline and any(value is None for value in observed.values()):
                for path in observed:
                    if observed[path] is None:
                        status = self._http_status(path)
                        if status is not None:
                            observed[path] = status
                time.sleep(1)
            self.assertTrue(all(status is not None and status >= 500 for status in observed.values()), observed)
        finally:
            if stopped:
                self._compose("start", "api", check=True)
                for path in ("/healthz", "/readyz"):
                    self._wait_for_status(path, 200, timeout_seconds=90)


if __name__ == "__main__":
    unittest.main()
