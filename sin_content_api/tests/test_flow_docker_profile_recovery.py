"""Opt-in real Chromium crash/recreate proof; no Google requests or credentials.

Run with FLOW_DOCKER_IMAGE pointing to the built production backend image.
The probe cookie uses flow-runtime.invalid and is never treated as provider auth.
"""

import os
from pathlib import Path
import subprocess
import time
import uuid

import pytest


PROJECT = Path(__file__).resolve().parents[2]
IMAGE = os.environ.get("FLOW_DOCKER_IMAGE")
pytestmark = pytest.mark.skipif(not IMAGE, reason="Set FLOW_DOCKER_IMAGE for actual Docker Chromium proof")

COMMON = '''
import importlib.metadata, pathlib, sys, time
sys.path.insert(0, '/app/cong_cu_tu_dong/flow_bridge')
from config import browser_launch_args
from profile_guard import profile_lock
from src.modules.flow_sessions.context import profile_context
from playwright.sync_api import sync_playwright
profile = pathlib.Path('/data/flow-profiles/probe')
'''


def _docker(*args, check=True):
    return subprocess.run(
        ["docker", *args], cwd=PROJECT, capture_output=True, text=True, timeout=90, check=check,
    )


def test_real_chromium_profile_survives_killed_container_and_recreate():
    name = f"prj069-flow-crash-{uuid.uuid4().hex[:10]}"
    volume = f"{name}-profiles"
    options = [
        "--hostname", name, "--network", "none", "--memory", "1g", "--cpus", "2",
        "-e", "APP_ENV=production", "-e", "TESTING=0", "-e", "DEV_AUTH_BYPASS=0",
        "-v", f"{volume}:/data/flow-profiles",
    ]
    _docker("volume", "create", volume)
    try:
        _docker(
            "run", "--rm", "--user", "0:0", *options, IMAGE, "python", "-c",
            "import os; os.chown('/data/flow-profiles',10001,10001); os.chmod('/data/flow-profiles',0o700)",
        )
        start = COMMON + '''
with profile_context('probe', 'probe'), profile_lock(profile), sync_playwright() as p:
    context = p.chromium.launch_persistent_context(str(profile), headless=True, args=browser_launch_args())
    context.add_cookies([{'name':'flow_runtime_probe','value':'volume-persistence','domain':'flow-runtime.invalid',
                         'path':'/', 'expires':time.time()+3600, 'secure':True, 'httpOnly':True}])
    context.close()
    context = p.chromium.launch_persistent_context(str(profile), headless=True, args=browser_launch_args())
    assert not context.is_closed()
    print('CHROMIUM_OPEN', flush=True)
    while True:
        time.sleep(1)
'''
        _docker("run", "-d", "--name", name, *options, IMAGE, "python", "-u", "-c", start)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if "CHROMIUM_OPEN" in _docker("logs", name).stdout:
                break
            time.sleep(0.25)
        else:
            pytest.fail("Production Chromium did not open; inspect isolated probe container logs")
        _docker("kill", "--signal", "KILL", name)
        _docker("rm", name)
        recover = COMMON + '''
assert (profile/'SingletonLock').is_symlink(), 'Crash must leave real Chromium SingletonLock'
with profile_context('probe', 'probe'), profile_lock(profile), sync_playwright() as p:
    assert not (profile/'SingletonLock').is_symlink(), 'Dead singleton must be recovered under managed lock'
    context = p.chromium.launch_persistent_context(str(profile), headless=True, args=browser_launch_args())
    assert any(cookie['name']=='flow_runtime_probe' for cookie in context.cookies())
    assert profile.stat().st_uid == 10001
    assert profile.stat().st_mode & 0o777 == 0o700
    context.close()
    print('REAL_CHROMIUM_RECREATE_OK', importlib.metadata.version('playwright'), flush=True)
'''
        result = _docker("run", "--rm", *options, IMAGE, "python", "-u", "-c", recover)
        assert "REAL_CHROMIUM_RECREATE_OK" in result.stdout
        print(result.stdout.strip())
    finally:
        _docker("rm", "-f", name, check=False)
        _docker("volume", "rm", volume, check=False)
