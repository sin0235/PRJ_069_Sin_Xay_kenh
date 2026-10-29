"""Opt-in API authorization and real noVNC/WebSocket handshake against Docker."""

import os
from pathlib import Path
import subprocess
import time
import uuid

import pytest

from tests.test_flow_sessions_api import _api, _workspace_owner

IMAGE = os.environ.get("FLOW_DESKTOP_TOOLS_IMAGE")
PROJECT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(not IMAGE, reason="Set FLOW_DESKTOP_TOOLS_IMAGE for real noVNC protocol proof")


def _docker(*args, check=True):
    return subprocess.run(["docker", *args], cwd=PROJECT, capture_output=True, text=True, timeout=45, check=check)


def test_real_websockify_rfb_handshake_through_owner_authenticated_api(monkeypatch):
    from src.database import Base, SessionLocal, engine
    from baha_auth.src.database import Base as AuthBase, engine as auth_engine
    from src.modules.flow_sessions import router as flow_router
    from src.modules.flow_sessions.models import FlowLoginSession

    name = f"prj069-flow-vnc-{uuid.uuid4().hex[:10]}"
    script = '''
import subprocess,time,socket
subprocess.Popen(['Xvfb',':99','-screen','0','1280x800x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(1)
subprocess.Popen(['x11vnc','-display',':99','-rfbport','5900','-localhost','-nopw','-forever','-shared'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.Popen(['websockify','--web','/usr/share/novnc','6080','127.0.0.1:5900'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for attempt in range(100):
    try:
        with socket.create_connection(('127.0.0.1',6080),timeout=0.1): break
    except OSError: time.sleep(0.1)
else: raise SystemExit('DESKTOP_START_FAILED')
print('REAL_DESKTOP_READY',flush=True)
while True: time.sleep(1)
'''
    session_id = None
    try:
        _docker(
            "run", "-d", "--name", name, "--user", "10001:10001", "--memory", "256m", "--cpus", "1",
            "-e", "APP_ENV=production", "-e", "TESTING=0", "-e", "DEV_AUTH_BYPASS=0",
            IMAGE, "/usr/bin/python3", "-u", "-c", script,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if "REAL_DESKTOP_READY" in _docker("logs", name).stdout:
                break
            time.sleep(0.25)
        else:
            pytest.fail("Real Docker desktop did not start")
        address = _docker("inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).stdout.strip()
        assert address
        assert _docker("inspect", "-f", "{{json .HostConfig.PortBindings}}", name).stdout.strip() in {"{}", "null"}
        monkeypatch.setattr(flow_router, "_desktop_base_url", lambda: f"http://{address}:6080")
        monkeypatch.setenv("FLOW_DESKTOP_ALLOWED_ORIGINS", "http://testserver")
        monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
        Base.metadata.create_all(engine)
        AuthBase.metadata.create_all(auth_engine)
        client = _api()
        _, _, headers = _workspace_owner(client)
        profile = client.post("/v1/media/flow/profiles", headers=headers, json={"name": "Real desktop"}).json()
        response = client.post("/v1/media/flow/login-sessions/start", headers=headers, json={"profile_id": profile["id"]})
        assert response.status_code == 202
        session_id = response.json()["id"]
        with SessionLocal() as db:
            db.get(FlowLoginSession, session_id).status = "OPEN"
            db.commit()
        response = client.post(f"/v1/media/flow/login-sessions/{session_id}/desktop-access", headers=headers)
        assert response.status_code == 200
        assert client.get(response.json()["url"], headers={"Origin": "http://testserver"}).status_code == 200
        for offered in ([], ["binary"]):
            with client.websocket_connect(
                f"/v1/media/flow/desktop/{session_id}/websockify",
                headers={"Origin": "http://testserver"}, subprotocols=offered,
            ) as desktop:
                assert desktop.accepted_subprotocol == ("binary" if offered else None)
                assert desktop.receive_bytes().startswith(b"RFB 003.")
                desktop.send_bytes(b"RFB 003.008\n")
                assert desktop.receive_bytes() == b"\x01\x01"  # VNC security type: None, protected by the API grant.
        print("REAL_DOCKER_NOVNC_API_RFB_OK binary+optional; no host VNC ports")
    finally:
        _docker("rm", "-f", name, check=False)
        if session_id:
            with SessionLocal() as db:
                session = db.get(FlowLoginSession, session_id)
                session.active_slot = None
                session.status = "CLOSED"
                db.commit()
