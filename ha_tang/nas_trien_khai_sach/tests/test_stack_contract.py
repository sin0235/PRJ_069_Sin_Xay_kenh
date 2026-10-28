import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = ROOT / "ha_tang/nas_trien_khai_sach/compose.yaml"


COPY_OVERLAY = ROOT / "ha_tang/nas_trien_khai_sach/compose.bootstrap-copy.yaml"


def render_compose(cookie_secure="true", bootstrap_mode=None, overlay=False, source_dir=None):
    env = os.environ.copy()
    env.pop("PRJ069_BOOTSTRAP_MODE", None)
    env.pop("PRJ069_BOOTSTRAP_SOURCE_HOST_DIR", None)
    env.update(
        {
            "AUTH_OWNER_EMAIL": "runtime-test@example.invalid",
            "AUTH_OWNER_PASSWORD_SECRET_FILE": "/dev/null",
            "SIN_WORKSPACE_ID": "00000000-0000-4000-8000-000000000001",
            "SIN_WORKSPACE_NAME": "runtime contract test",
            "AUTH_ALLOWED_ORIGINS": "https://runtime-test.example.invalid",
            "AUTH_COOKIE_SECURE": cookie_secure,
            "BAHA_AUTH_JWT_SECRET": "test-only-not-a-production-secret-0123456789abcdef",
            "BAHA_AUTH_JWT_ISSUER": "prj069-runtime-test",
            "BAHA_AUTH_JWT_AUDIENCE": "prj069-runtime-test",
            "LLM_ENCRYPTION_MASTER_KEY": "test-only-not-a-production-key-0123456789abcdef",
            "PRJ069_DATA_VOLUME": "prj069-contract-data",
            "PRJ069_PROFILE_VOLUME": "prj069-contract-profiles",
            "PRJ069_MODEL_VOLUME": "prj069-contract-models",
            "PRJ069_COMPOSE_PROJECT_NAME": "prj069-contract",
        }
    )
    if bootstrap_mode is not None:
        env["PRJ069_BOOTSTRAP_MODE"] = bootstrap_mode
    if source_dir is not None:
        env["PRJ069_BOOTSTRAP_SOURCE_HOST_DIR"] = str(source_dir)
    compose_files = [COMPOSE_FILE]
    if overlay:
        compose_files.append(COPY_OVERLAY)
    args = ["docker", "compose", "-p", "prj069-contract"]
    for compose_file in compose_files:
        args.extend(["-f", str(compose_file)])
    args.extend(["config", "--format", "json"])
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(f"docker compose config failed: {result.stderr}")
    return json.loads(result.stdout)


class ProductionStackContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not COMPOSE_FILE.is_file():
            raise AssertionError("production Compose file is missing")
        cls.config = render_compose()
        cls.services = cls.config["services"]

    def test_backend_and_web_memory_caps_are_exact(self):
        self.assertEqual(int(self.services["api"]["mem_limit"]), 512 * 1024 * 1024)
        self.assertEqual(int(self.services["flow-session-worker"]["mem_limit"]), 3584 * 1024 * 1024)
        self.assertEqual(int(self.services["web"]["mem_limit"]), 512 * 1024 * 1024)

    def test_all_services_disable_additional_swap(self):
        for name in ("init", "api", "flow-session-worker", "web", "gateway"):
            with self.subTest(service=name):
                self.assertEqual(int(self.services[name]["memswap_limit"]), int(self.services[name]["mem_limit"]))

    def test_production_flags_and_durable_paths_are_explicit(self):
        api_env = self.services["api"]["environment"]
        self.assertEqual(api_env["APP_ENV"], "production")
        self.assertEqual(api_env["TESTING"], "0")
        self.assertEqual(api_env["DEV_AUTH_BYPASS"], "0")
        self.assertEqual(api_env["AUTH_COOKIE_SECURE"], "true")
        self.assertEqual(api_env["CONTENT_VIDEO_WORKER_ENABLED"], "0")
        self.assertEqual(api_env["DATABASE_URL"], "sqlite:////data/sin_content_production.db")
        self.assertEqual(api_env["BAHA_AUTH_DATABASE_URL"], "sqlite:////data/baha_auth_production.db")
        self.assertEqual(api_env["SIN_DUNG_DB_PATH"], "/data/sin_dieu_phoi_dung.db")
        self.assertEqual(api_env["MEDIA_ROOT_DIR"], "/data/media_assets")
        self.assertEqual(api_env["PRJ069_VIENU_HF_HOME"], "/models/vieneu")
        self.assertEqual(api_env["BROWSER_CHANNEL"], "chromium")
        self.assertEqual(api_env["SYNTHETIC_DATA_ALLOWED"], "false")
        self.assertEqual(api_env["FLOW_DESKTOP_ALLOWED_ORIGINS"], api_env["AUTH_ALLOWED_ORIGINS"])
        self.assertNotIn("AUTH_OWNER_PASSWORD_FILE", api_env)
        self.assertEqual(self.services["api"]["depends_on"]["init"]["condition"], "service_completed_successfully")
        self.assertEqual(self.services["flow-session-worker"]["depends_on"]["init"]["condition"], "service_completed_successfully")
        self.assertEqual(self.services["init"]["environment"]["AUTH_OWNER_PASSWORD_FILE"], "/run/secrets/owner-password")
        self.assertEqual(self.services["init"]["user"], "0:0")
        self.assertEqual(self.services["init"]["entrypoint"], ["/app/ha_tang/nas_runtime/init-entrypoint.sh"])
        self.assertEqual(self.services["init"]["command"], ["python", "/app/scripts/khoi_tao_production_noi_bo.py"])

    def test_default_bootstrap_adopts_existing_volume_without_seed_mount(self):
        init = self.services["init"]
        self.assertEqual(init["environment"]["PRJ069_BOOTSTRAP_MODE"], "adopt")
        self.assertFalse(any(volume.get("target") == "/seed" for volume in init["volumes"]))
        self.assertFalse(any(volume.get("target", "").startswith("/data/") for volume in init["volumes"]))
        profile_volume = next(volume for volume in init["volumes"] if volume.get("target") == "/profile-volume-staging")
        self.assertEqual(profile_volume["type"], "volume")

    def test_copy_bootstrap_mounts_only_an_explicit_read_only_source(self):
        source_dir = ROOT / "ha_tang/nas_trien_khai_sach/seed"
        config = render_compose(overlay=True, source_dir=source_dir)
        init = config["services"]["init"]
        self.assertEqual(init["environment"]["PRJ069_BOOTSTRAP_MODE"], "copy")
        self.assertEqual(init["environment"]["PRJ069_BOOTSTRAP_SOURCE_DIR"], "/seed")
        seed_mount = next(volume for volume in init["volumes"] if volume.get("target") == "/seed")
        self.assertEqual(seed_mount["source"], str(source_dir))
        self.assertTrue(seed_mount["read_only"])

    def test_worker_is_internal_only_and_uses_the_separate_entrypoint(self):
        worker = self.services["flow-session-worker"]
        command = worker["command"]
        self.assertEqual(command[-3:], ["python", "-m", "src.worker_runtime"])
        self.assertFalse(worker.get("ports"))
        self.assertEqual({port.split("/", 1)[0] for port in worker.get("expose", [])}, {"6080", "8090"})
        self.assertEqual(worker["environment"]["WORKER_HEARTBEAT_PATH"], "/data/runtime/worker.json")
        self.assertEqual(worker["environment"]["PRJ069_VIENU_HF_HOME"], "/models/vieneu")
        self.assertEqual(worker["environment"]["FLOW_PROFILE_ROOT"], "/data/flow-profiles")
        self.assertEqual(worker["environment"]["FLOW_NOVNC_WEB_ROOT"], "/usr/share/novnc")
        self.assertFalse(any("/var/run/docker.sock" in str(item) for item in worker.get("volumes", [])))
        self.assertIn("api-worker", worker["networks"])
        self.assertNotIn("api-worker", self.services["web"]["networks"])
        self.assertNotIn("api-worker", self.services["gateway"]["networks"])
        self.assertNotIn("worker-egress", self.services["api"]["networks"])
        api_env = self.services["api"]["environment"]
        self.assertEqual(api_env["FLOW_CONTROL_URL"], "http://flow-session-worker:8090")
        self.assertEqual(api_env["FLOW_DESKTOP_URL"], "http://flow-session-worker:6080")

    def test_flow_worker_has_stable_project_scoped_hostname(self):
        self.assertEqual(self.services["flow-session-worker"]["hostname"], "prj069-contract-flow-worker")

    def test_worker_cpu_and_native_thread_use_are_bounded(self):
        worker = self.services["flow-session-worker"]
        self.assertEqual(float(worker["cpus"]), 2.0)
        for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            self.assertEqual(worker["environment"][variable], "2")
        self.assertNotIn("cpus", self.services["api"])
        self.assertNotIn("cpus", self.services["web"])

    def test_api_has_no_host_port_and_web_uses_internal_api_origin(self):
        self.assertFalse(self.services["api"].get("ports"))
        web_env = self.services["web"]["environment"]
        self.assertEqual(web_env["API_INTERNAL_URL"], "http://api:8000")
        self.assertEqual(web_env["AUTH_ALLOWED_ORIGINS"], "https://runtime-test.example.invalid")
        self.assertEqual(web_env["AUTH_COOKIE_SECURE"], "true")

    def test_gateway_forwards_api_websockets_without_bypassing_api_auth(self):
        config = (ROOT / "ha_tang/nas_runtime/nginx.conf").read_text(encoding="utf-8")
        self.assertIn("location /v1/", config)
        self.assertIn("proxy_set_header Upgrade $http_upgrade;", config)
        self.assertIn("proxy_pass http://api:8000", config)
        self.assertNotIn("auth_request", config)
        self.assertIn("$uri", config)
        self.assertNotIn("$request_uri", config)
        self.assertNotIn('"$request ', config)
        self.assertIn("worker_processes 1;", config)
        self.assertIn("client_max_body_size 501m;", config)
        self.assertNotIn("client_max_body_size 0", config)
        gateway_targets = {port["target"] for port in self.services["gateway"].get("ports", [])}
        self.assertNotIn(6080, gateway_targets)
        self.assertNotIn(8090, gateway_targets)

    def test_gateway_health_routes_reflect_api_health_and_readiness(self):
        config = (ROOT / "ha_tang/nas_runtime/nginx.conf").read_text(encoding="utf-8")
        for path in ("healthz", "readyz"):
            self.assertIn(f"location = /{path}", config)
            self.assertIn(f"proxy_pass http://api:8000/{path};", config)
        gateway_probe = " ".join(self.services["gateway"]["healthcheck"]["test"])
        self.assertIn("127.0.0.1:8080/readyz", gateway_probe)
        self.assertNotIn("/gateway-healthz", gateway_probe)

    def test_http_local_cookie_override_is_explicitly_supported(self):
        config = render_compose(cookie_secure="false")
        self.assertEqual(config["services"]["api"]["environment"]["AUTH_COOKIE_SECURE"], "false")
        self.assertEqual(config["services"]["web"]["environment"]["AUTH_COOKIE_SECURE"], "false")

    def test_runtime_lock_uses_onnx_playwright_without_torch(self):
        lock = (ROOT / "sin_content_api/requirements.nas.lock").read_text(encoding="utf-8").lower()
        self.assertIn("playwright==1.64.1", lock)
        self.assertIn("vieneu==3.8.3", lock)
        self.assertIn("onnxruntime==1.28.0", lock)
        self.assertIn("websockets==17.3", lock)
        self.assertNotIn("torch==", lock)

    def test_backend_build_retries_slow_pypi_downloads_without_baking_cache(self):
        dockerfile = (ROOT / "ha_tang/nas_runtime/Dockerfile.backend").read_text(encoding="utf-8")
        self.assertIn("type=cache,id=prj069-nas-pip,target=/root/.cache/pip", dockerfile)
        self.assertIn("--cache-dir=/root/.cache/pip", dockerfile)
        self.assertIn("--timeout 120", dockerfile)
        self.assertIn("--retries 8", dockerfile)


if __name__ == "__main__":
    unittest.main()
