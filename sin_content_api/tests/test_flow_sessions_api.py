import importlib.util
import uuid
import threading

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as auth_engine
from baha_auth.src.models.entities import Membership as AuthMembership, Workspace as AuthWorkspace
from tests.conftest import setup_test_auth_user, tao_bearer_token
from src.database import Base, SessionLocal, engine
from src.models.entities import Workspace


def _api(*, local_client=False):
    assert importlib.util.find_spec("src.modules.flow_sessions.router") is not None
    from src.modules.flow_sessions.router import router

    app = FastAPI()
    app.include_router(router)
    if local_client:
        return TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50123))
    return TestClient(app)


def _workspace_owner(client, role_code="WORKSPACE_OWNER"):
    workspace_id = f"flow-ws-{uuid.uuid4().hex[:10]}"
    user_id = f"flow-user-{uuid.uuid4().hex[:10]}"
    with SessionLocal() as db:
        db.add(Workspace(id=workspace_id, name="Flow test", slug=f"flow-{uuid.uuid4().hex[:10]}"))
        db.commit()
    with AuthSessionLocal() as db:
        db.add(AuthWorkspace(id=workspace_id, name="Flow test", slug=workspace_id, status="ACTIVE"))
        db.commit()
        setup_test_auth_user(db, workspace_id, user_id, f"{user_id}@example.test", role_code)
    return workspace_id, user_id, {
        "Authorization": f"Bearer {tao_bearer_token(user_id)}",
        "X-Workspace-Id": workspace_id,
    }


def test_owner_can_create_activate_and_enqueue_login_for_only_own_workspace():
    from src.modules.flow_sessions.models import FlowDesktopGrant, FlowLoginSession, FlowProfile, FlowSessionCommand

    Base.metadata.create_all(
        bind=engine,
        tables=[Workspace.__table__, FlowProfile.__table__, FlowLoginSession.__table__, FlowSessionCommand.__table__, FlowDesktopGrant.__table__],
    )
    AuthBase.metadata.create_all(bind=auth_engine)
    client = _api()
    workspace_id, _, owner_headers = _workspace_owner(client)
    other_workspace_id, _, other_headers = _workspace_owner(client)

    created = client.post("/v1/media/flow/profiles", headers=owner_headers, json={"name": "Primary"})
    assert created.status_code == 201
    profile = created.json()
    assert profile["is_active"] is True
    assert client.get("/v1/media/flow/profiles/current", headers=owner_headers).json()["id"] == profile["id"]

    other_created = client.post("/v1/media/flow/profiles", headers=other_headers, json={"name": "Other"})
    assert other_created.status_code == 201
    assert client.post(
        f"/v1/media/flow/profiles/{other_created.json()['id']}/activate", headers=owner_headers
    ).status_code == 404

    started = client.post("/v1/media/flow/login-sessions/start", headers=owner_headers, json={})
    assert started.status_code == 202
    assert started.json()["profile_id"] == profile["id"]
    assert started.json()["status"] == "LOGIN_REQUESTED"
    assert client.get("/v1/media/flow/login-sessions/current", headers=owner_headers).json()["id"] == started.json()["id"]
    assert client.get("/v1/media/flow/login-sessions/current", headers=other_headers).json() is None
    foreign_session = client.get(
        f"/v1/media/flow/login-sessions/{started.json()['id']}", headers=other_headers
    )
    assert foreign_session.status_code == 404
    assert foreign_session.json()["detail"]["error_code"] == "FLOW_SESSION_NOT_FOUND"
    assert workspace_id != other_workspace_id
    with SessionLocal() as db:
        row = db.get(FlowLoginSession, started.json()["id"])
        row.status = "CLOSED"
        row.active_slot = None
        db.commit()
    assert client.get("/v1/media/flow/login-sessions/current", headers=owner_headers).json() is None


def test_non_owner_and_development_bypass_cannot_view_or_create_flow_profiles(monkeypatch):
    from src.modules.flow_sessions.models import FlowProfile

    Base.metadata.create_all(bind=engine, tables=[Workspace.__table__, FlowProfile.__table__])
    AuthBase.metadata.create_all(bind=auth_engine)
    client = _api()
    _, _, guest_headers = _workspace_owner(client, "GUEST")

    denied = client.get("/v1/media/flow/profiles", headers=guest_headers)
    assert denied.status_code == 403
    assert client.get("/v1/media/flow/login-sessions/current", headers=guest_headers).status_code == 403
    assert client.post(
        "/v1/media/flow/profiles", headers=guest_headers, json={"name": "Not allowed"}
    ).status_code == 403
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    bypass_client = _api(local_client=True)
    bypass = bypass_client.get("/v1/media/flow/profiles", headers={"X-Workspace-Id": "flow-dev-ws"})
    assert bypass.status_code == 403
    assert bypass.json()["detail"]["error_code"] == "FLOW_WORKSPACE_OWNER_REQUIRED"


def test_desktop_cookie_secure_flag_is_configurable_but_defaults_to_secure(monkeypatch):
    from src.modules.flow_sessions.router import _secure_cookie

    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    assert _secure_cookie() is True
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    assert _secure_cookie() is False


def test_desktop_cookie_is_bounded_and_revoked_when_owner_membership_ends(monkeypatch):
    from src.modules.flow_sessions.models import FlowDesktopGrant, FlowLoginSession, FlowProfile, FlowSessionCommand

    Base.metadata.create_all(
        bind=engine,
        tables=[
            Workspace.__table__,
            FlowProfile.__table__,
            FlowLoginSession.__table__,
            FlowSessionCommand.__table__,
            FlowDesktopGrant.__table__,
        ],
    )
    AuthBase.metadata.create_all(bind=auth_engine)
    monkeypatch.setenv("FLOW_DESKTOP_ALLOWED_ORIGINS", "http://testserver")
    client = _api()
    workspace_id, user_id, headers = _workspace_owner(client)
    profile = client.post("/v1/media/flow/profiles", headers=headers, json={"name": "Primary"}).json()
    session_response = client.post(
        "/v1/media/flow/login-sessions/start", headers=headers, json={"profile_id": profile["id"]}
    )
    assert session_response.status_code == 202, session_response.text
    session = session_response.json()
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with SessionLocal() as db:
        row = db.get(FlowLoginSession, session["id"])
        row.status = "OPEN"
        db.commit()


    access = client.post(
        f"/v1/media/flow/login-sessions/{session['id']}/desktop-access", headers=headers
    )
    assert access.status_code == 200
    assert access.json()["url"].startswith(f"/v1/media/flow/desktop/{session['id']}/vnc.html?")
    # noVNC prepends "/" to the path parameter; a leading slash would yield "//v1/..." and lose the cookie.
    assert f"path=v1%2Fmedia%2Fflow%2Fdesktop%2F{session['id']}%2Fwebsockify" in access.json()["url"]
    assert "flow_desktop=" in access.headers["set-cookie"]
    cookie = access.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "secure" not in cookie
    assert session["id"] in cookie
    raw_token = client.cookies.get("flow_desktop")
    assert raw_token not in access.json()["url"]
    with SessionLocal() as db:
        grant = db.query(FlowDesktopGrant).filter_by(session_id=session["id"]).one()
        assert grant.user_id == user_id
        assert grant.workspace_id == workspace_id
        assert grant.token_digest != raw_token

    with AuthSessionLocal() as db:
        membership = db.query(AuthMembership).filter_by(workspace_id=workspace_id, user_id=user_id).one()
        membership.status = "INACTIVE"
        db.commit()
    denied = client.get(
        access.json()["url"].split("?", 1)[0],
        headers={"Origin": "http://testserver"},
    )
    assert denied.status_code == 403
    with SessionLocal() as db:
        row = db.get(FlowLoginSession, session["id"])
        row.status = "CLOSED"
        row.active_slot = None
        db.commit()


def test_desktop_websocket_negotiates_binary_relays_and_revokes_live_connection(monkeypatch):
    from datetime import datetime, timezone
    from starlette.websockets import WebSocketDisconnect
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.server import serve
    from src.modules.flow_sessions import router as flow_router
    from src.modules.flow_sessions.models import FlowDesktopGrant, FlowLoginSession

    Base.metadata.create_all(engine)
    AuthBase.metadata.create_all(auth_engine)
    monkeypatch.setenv("FLOW_DESKTOP_ALLOWED_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    monkeypatch.setattr(flow_router, "_DESKTOP_WS_RECHECK_SECONDS", 0.05, raising=False)
    client = _api()
    _, _, headers = _workspace_owner(client)
    profile = client.post("/v1/media/flow/profiles", headers=headers, json={"name": "WS"}).json()
    started = client.post("/v1/media/flow/login-sessions/start", headers=headers, json={"profile_id": profile["id"]})
    assert started.status_code == 202, started.text
    session_id = started.json()["id"]
    with SessionLocal() as db:
        db.get(FlowLoginSession, session_id).status = "OPEN"
        db.commit()
    access = client.post(f"/v1/media/flow/login-sessions/{session_id}/desktop-access", headers=headers)
    assert access.status_code == 200

    observed = []

    def upstream_handler(connection):
        observed.append(connection.subprotocol)
        connection.send(b"RFB 003.008\n")
        try:
            for message in connection:
                connection.send(message)
        except ConnectionClosed:
            pass

    try:
        with serve(upstream_handler, "127.0.0.1", 0, subprotocols=["binary"]) as upstream:
            port = upstream.socket.getsockname()[1]
            monkeypatch.setattr(flow_router, "_desktop_base_url", lambda: f"http://127.0.0.1:{port}")
            thread = threading.Thread(target=upstream.serve_forever, daemon=True)
            thread.start()
            with client.websocket_connect(
                f"/v1/media/flow/desktop/{session_id}/websockify",
                headers={"Origin": "http://testserver"},
                subprotocols=["unsupported", "binary"],
            ) as desktop:
                assert desktop.accepted_subprotocol == "binary"
                assert desktop.receive_bytes() == b"RFB 003.008\n"
                desktop.send_bytes(b"client framebuffer request")
                assert desktop.receive_bytes() == b"client framebuffer request"
                with SessionLocal() as db:
                    db.query(FlowDesktopGrant).filter_by(session_id=session_id).update({"revoked_at": datetime.now(timezone.utc)})
                    db.commit()
                with pytest.raises(WebSocketDisconnect):
                    desktop.receive_bytes()
            upstream.shutdown()
            thread.join(timeout=3)
        assert observed == ["binary"]
    finally:
        with SessionLocal() as db:
            row = db.get(FlowLoginSession, session_id)
            row.status = "CLOSED"
            row.active_slot = None
            db.commit()

