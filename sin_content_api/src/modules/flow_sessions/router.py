"""Owner-authenticated Flow profiles, login sessions, and desktop gateway."""

from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.tenancy import (
    TenantContext,
    _canonical_auth_modules,
    authorize_action,
    get_current_tenant_context,
    require_action,
)
from src.database import SessionLocal, get_db
from . import service
from .models import FlowLoginSession, FlowProfile

router = APIRouter(prefix="/v1/media/flow", tags=["Flow profiles"])
_DESKTOP_COOKIE = "flow_desktop"
_DESKTOP_COOKIE_MAX_AGE = 300
_DESKTOP_WS_MAX_MESSAGE_SIZE = 16 * 1024 * 1024
_DESKTOP_WS_RECHECK_SECONDS = 5


class ProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ProfileRequest(BaseModel):
    profile_id: str | None = None


def _http_error(status_code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code, "message": message},
    )


def _has_workspace_owner(tenant: TenantContext, user_id: str | None = None) -> bool:
    actor = tenant.actor
    if (
        tenant.dev_auth_bypass
        or tenant.auth_db is None
        or actor is None
        or actor.user_id != (user_id or tenant.user_id)
        or actor.workspace_id != tenant.workspace_id
        or actor.membership_status != "ACTIVE"
        or actor.user_status != "ACTIVE"
        or actor.workspace_status != "ACTIVE"
    ):
        return False
    return any(
        role.get("role_code") == "WORKSPACE_OWNER"
        and role.get("scope_type") == "WORKSPACE"
        and role.get("scope_id") in {None, tenant.workspace_id}
        and role.get("assignment_status") == "ACTIVE"
        and role.get("role_status") == "ACTIVE"
        and role.get("is_active") is True
        for role in (actor.roles or [])
    )


def _require_owner(tenant: TenantContext) -> str:
    if not _has_workspace_owner(tenant):
        raise _http_error(403, "FLOW_WORKSPACE_OWNER_REQUIRED", "An active workspace owner is required.")
    return tenant.user_id


def _secure_cookie() -> bool:
    value = os.getenv("AUTH_COOKIE_SECURE", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _recheck_workspace_owner(workspace_id: str, user_id: str) -> bool:
    """Re-read Baha membership for each cookie-authorized desktop proxy request."""
    auth = _canonical_auth_modules()
    generator = auth["get_auth_db"]()
    db = None
    try:
        db = next(generator)
        auth["set_tenant_context"](workspace_id, db)
        actor = auth["load_actor_for_user"](db, workspace_id=workspace_id, user_id=user_id)
        tenant = TenantContext(
            workspace_id=workspace_id,
            user_id=user_id,
            actor=actor,
            auth_db=db,
            request_id="flow-desktop-membership-recheck",
        )
        if actor is None or not _has_workspace_owner(tenant, user_id):
            return False
        authorize_action(tenant, "media.read")
        return True
    except Exception:
        return False
    finally:
        if db is not None:
            try:
                db.rollback()
            except Exception:
                pass
            try:
                auth["clear_tenant_context"](db)
            except Exception:
                pass
        try:
            close = getattr(generator, "close", None)
            if close:
                close()
        except Exception:
            pass
        try:
            auth["clear_tenant_context"]()
        except Exception:
            pass


def _profile_out(profile: FlowProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "is_active": profile.is_active,
        "state": profile.state,
        "flow_music_state": profile.flow_music_state,
        "google_flow_state": profile.google_flow_state,
        "last_checked_at": profile.last_checked_at,
        "error_code": profile.error_code,
    }


def _session_out(session: FlowLoginSession) -> dict[str, Any]:
    return {
        "id": session.id,
        "profile_id": session.profile_id,
        "status": session.status,
        "error_code": session.error_code,
        "expires_at": session.expires_at,
        "started_at": session.started_at,
        "closed_at": session.closed_at,
    }


def _command_out(command) -> dict[str, Any]:
    import json

    result = None
    if command.result_json:
        try:
            result = json.loads(command.result_json)
        except (TypeError, ValueError):
            result = None
    return {
        "id": command.id,
        "profile_id": command.profile_id,
        "session_id": command.session_id,
        "kind": command.kind,
        "state": command.state,
        "result": result,
        "error_code": command.error_code,
        "created_at": command.created_at,
        "finished_at": command.finished_at,
    }


@router.get("/profiles")
def list_flow_profiles(
    tenant: TenantContext = Depends(require_action("media.read")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    return [_profile_out(row) for row in service.list_profiles(db, tenant.workspace_id)]


@router.get("/profiles/current")
def get_current_flow_profile(
    tenant: TenantContext = Depends(require_action("media.read")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    return _profile_out(service.current_profile(db, tenant.workspace_id))


@router.post("/profiles", status_code=status.HTTP_201_CREATED)
def create_flow_profile(
    payload: ProfileCreateRequest,
    tenant: TenantContext = Depends(require_action("media.upload")),
    db: Session = Depends(get_db),
):
    user_id = _require_owner(tenant)
    return _profile_out(service.create_profile(db, tenant.workspace_id, payload.name, user_id))


@router.post("/profiles/{profile_id}/activate")
def activate_flow_profile(
    profile_id: str,
    tenant: TenantContext = Depends(require_action("media.upload")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    return _profile_out(service.activate_profile(db, tenant.workspace_id, profile_id))


@router.post("/profiles/{profile_id}/check", status_code=status.HTTP_202_ACCEPTED)
def check_flow_profile(
    profile_id: str,
    tenant: TenantContext = Depends(require_action("media.upload")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    return _command_out(service.request_profile_check(db, tenant.workspace_id, profile_id))


@router.post("/profiles/check", status_code=status.HTTP_202_ACCEPTED)
def check_current_flow_profile(
    payload: ProfileRequest,
    tenant: TenantContext = Depends(require_action("media.upload")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    return _command_out(service.request_profile_check(db, tenant.workspace_id, payload.profile_id))


@router.get("/commands/{command_id}")
def get_flow_command(
    command_id: str,
    tenant: TenantContext = Depends(require_action("media.read")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    return _command_out(service.get_command(db, tenant.workspace_id, command_id))


@router.post("/login-sessions/start", status_code=status.HTTP_202_ACCEPTED)
def start_flow_login_session(
    payload: ProfileRequest,
    tenant: TenantContext = Depends(require_action("media.upload")),
    db: Session = Depends(get_db),
):
    user_id = _require_owner(tenant)
    return _session_out(service.request_login(db, tenant.workspace_id, payload.profile_id, user_id))


@router.get("/login-sessions/current")
def get_current_flow_login_session(
    tenant: TenantContext = Depends(require_action("media.read")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    session = service.current_login_session(db, tenant.workspace_id)
    return _session_out(session) if session else None


@router.get("/login-sessions/{session_id}")
def get_flow_login_session(
    session_id: str,
    tenant: TenantContext = Depends(require_action("media.read")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    session = (
        db.query(FlowLoginSession)
        .filter(FlowLoginSession.id == session_id, FlowLoginSession.workspace_id == tenant.workspace_id)
        .first()
    )
    if session is None:
        raise _http_error(404, "FLOW_SESSION_NOT_FOUND", "The Flow login session was not found in this workspace.")
    return _session_out(session)


@router.post("/login-sessions/{session_id}/close", status_code=status.HTTP_202_ACCEPTED)
def close_flow_login_session(
    session_id: str,
    response: Response,
    tenant: TenantContext = Depends(require_action("media.upload")),
    db: Session = Depends(get_db),
):
    _require_owner(tenant)
    result = service.request_close(db, tenant.workspace_id, session_id)
    response.delete_cookie(
        key=_DESKTOP_COOKIE,
        path=f"/v1/media/flow/desktop/{session_id}/",
        secure=_secure_cookie(),
        httponly=True,
        samesite="strict",
    )
    return _session_out(result)


@router.post("/login-sessions/{session_id}/desktop-access")
def create_flow_desktop_access(
    session_id: str,
    response: Response,
    tenant: TenantContext = Depends(require_action("media.read")),
    db: Session = Depends(get_db),
):
    user_id = _require_owner(tenant)
    raw_token, grant = service.create_desktop_grant(db, tenant.workspace_id, session_id, user_id)
    cookie_path = f"/v1/media/flow/desktop/{session_id}/"
    response.set_cookie(
        key=_DESKTOP_COOKIE,
        value=raw_token,
        max_age=_DESKTOP_COOKIE_MAX_AGE,
        httponly=True,
        secure=_secure_cookie(),
        samesite="strict",
        path=cookie_path,
    )
    # noVNC prepends "/" to this value, so a leading slash would produce "//v1/..." and lose the scoped cookie.
    path = f"v1/media/flow/desktop/{session_id}/websockify"
    desktop_url = f"/v1/media/flow/desktop/{session_id}/vnc.html?{urlencode({'autoconnect': '1', 'resize': 'scale', 'path': path})}"
    return {"url": desktop_url, "expires_at": grant.expires_at}


def _desktop_base_url() -> str:
    raw = os.getenv("FLOW_DESKTOP_URL", "http://flow-session-worker:6080").rstrip("/")
    try:
        parsed = urlsplit(raw)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
    except ValueError as exc:
        raise _http_error(503, "FLOW_DESKTOP_CONFIG_INVALID", "The internal Flow desktop endpoint is invalid.") from exc
    return raw


def _desktop_origin_for_request(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return origin
    referer = request.headers.get("referer")
    if not referer:
        return None
    parsed = urlsplit(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def _validate_desktop_path(path: str) -> str:
    normalized = path.lstrip("/")
    parts = normalized.split("/")
    if (
        not normalized
        or "\\" in normalized
        or "\x00" in normalized
        or any(part in {"", ".", ".."} for part in parts)
        or (normalized not in {"vnc.html", "favicon.ico", "websockify"}
            and not normalized.startswith(("app/", "core/", "vendor/")))
    ):
        raise _http_error(404, "FLOW_DESKTOP_PATH_NOT_FOUND", "The requested Flow desktop resource was not found.")
    return normalized


def _authorize_desktop_request(
    db: Session,
    session_id: str,
    raw_token: str | None,
    origin: str | None,
):
    if not raw_token:
        raise _http_error(401, "FLOW_DESKTOP_ACCESS_EXPIRED", "The Flow desktop access has expired or been revoked.")
    grant = service.validate_desktop_grant(db, session_id, raw_token, origin)
    if not _recheck_workspace_owner(grant.workspace_id, grant.user_id):
        raise _http_error(403, "FLOW_WORKSPACE_OWNER_REQUIRED", "An active workspace owner is required.")
    return grant


def require_flow_desktop_read(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    flow_desktop: str | None = Cookie(default=None, alias=_DESKTOP_COOKIE),
):
    return _authorize_desktop_request(db, session_id, flow_desktop, _desktop_origin_for_request(request))


require_flow_desktop_read.required_action = "media.read"  # type: ignore[attr-defined]


@router.api_route(
    "/desktop/{session_id}/{path:path}",
    methods=["GET", "HEAD"],
    include_in_schema=False,
    dependencies=[Depends(require_flow_desktop_read)],
)
async def proxy_flow_desktop_http(
    session_id: str,
    path: str,
    request: Request,
):
    safe_path = _validate_desktop_path(path)
    if safe_path == "websockify":
        raise _http_error(426, "FLOW_DESKTOP_WEBSOCKET_REQUIRED", "Use a WebSocket connection for the Flow desktop stream.")
    try:
        import httpx

        headers = {
            key: request.headers[key]
            for key in ("accept", "accept-encoding", "if-none-match", "if-modified-since", "range")
            if key in request.headers
        }
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                f"{_desktop_base_url()}/{safe_path}",
                params=request.query_params,
                headers=headers,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise _http_error(502, "FLOW_DESKTOP_UPSTREAM_UNAVAILABLE", "The internal Flow desktop is unavailable.") from exc
    response_headers = {
        key: upstream.headers[key]
        for key in ("content-type", "cache-control", "etag", "last-modified", "accept-ranges", "content-range")
        if key in upstream.headers
    }
    return Response(
        content=b"" if request.method == "HEAD" else upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )


@router.websocket("/desktop/{session_id}/{path:path}")
async def proxy_flow_desktop_websocket(
    websocket: WebSocket,
    session_id: str,
    path: str,
    db: Session = Depends(get_db),
):
    try:
        safe_path = _validate_desktop_path(path)
        if safe_path != "websockify":
            raise _http_error(404, "FLOW_DESKTOP_PATH_NOT_FOUND", "The Flow desktop stream was not found.")
        raw_token = websocket.cookies.get(_DESKTOP_COOKIE)
        origin = websocket.headers.get("origin")
        _authorize_desktop_request(
            db,
            session_id,
            raw_token,
            origin,
        )
        import websockets

        upstream_scheme = "wss" if _desktop_base_url().startswith("https:") else "ws"
        upstream_base = _desktop_base_url().split("://", 1)[1]
        query = f"?{websocket.url.query}" if websocket.url.query else ""
        upstream_url = f"{upstream_scheme}://{upstream_base}/{safe_path}{query}"
        protocols = [protocol for protocol in websocket.scope.get("subprotocols", []) if protocol == "binary"]
        async with websockets.connect(
            upstream_url,
            origin=origin,
            subprotocols=protocols or None,
            close_timeout=2,
            max_size=_DESKTOP_WS_MAX_MESSAGE_SIZE,
            max_queue=4,
        ) as upstream:
            await websocket.accept(subprotocol=upstream.subprotocol)
            async def send_upstream() -> None:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if message.get("text") is not None:
                        await upstream.send(message["text"])
                    elif message.get("bytes") is not None:
                        await upstream.send(message["bytes"])

            async def send_client() -> None:
                async for message in upstream:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            async def recheck_access() -> None:
                while True:
                    await asyncio.sleep(_DESKTOP_WS_RECHECK_SECONDS)
                    def check():
                        with SessionLocal() as grant_db:
                            _authorize_desktop_request(grant_db, session_id, raw_token, origin)
                    await asyncio.to_thread(check)

            tasks = [asyncio.create_task(send_upstream()), asyncio.create_task(send_client()), asyncio.create_task(recheck_access())]
            try:
                done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    exception = task.exception()
                    if exception and not isinstance(exception, WebSocketDisconnect):
                        raise exception
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except HTTPException as exc:
        await websocket.close(code=4403 if exc.status_code == 403 else 4401)
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            pass
