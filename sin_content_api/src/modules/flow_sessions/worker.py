"""Private durable-command worker for Flow profile checks and login sessions."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import update

from src.database import SessionLocal
from .models import FlowDesktopGrant, FlowLoginSession, FlowProfile, FlowSessionCommand
from . import service

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOW_BRIDGE = _PROJECT_ROOT / "cong_cu_tu_dong" / "flow_bridge"
if str(_FLOW_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_FLOW_BRIDGE))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _try_acquire_content_video_lease(token: str) -> bool:
    from src.modules.tao_video_noi_dung.runner import _acquire_lease

    with SessionLocal() as db:
        return _acquire_lease(db, token)


def _heartbeat_content_video_lease(token: str) -> bool:
    from src.modules.tao_video_noi_dung.runner import _heartbeat

    with SessionLocal() as db:
        return _heartbeat(db, token)


def _release_content_video_lease(token: str) -> None:
    from src.modules.tao_video_noi_dung.runner import _release_lease

    with SessionLocal() as db:
        _release_lease(db, token)


def _resolve_executable(env_name: str, default: str) -> str:
    command = os.environ.get(env_name, default)
    resolved = shutil.which(command)
    if resolved is None:
        raise RuntimeError("FLOW_DESKTOP_RUNTIME_UNAVAILABLE")
    return resolved


class DesktopRuntime:
    """Start and stop only the X11/VNC processes owned by this worker session."""

    def __init__(self):
        self.processes: list[subprocess.Popen] = []
        self.display = os.environ.get("DISPLAY", ":99")
        if not re.fullmatch(r":[0-9]{1,3}(?:\.[0-9]+)?", self.display):
            raise RuntimeError("FLOW_DESKTOP_DISPLAY_INVALID")
        self.display_number = int(self.display[1:].split(".", 1)[0])

    @staticmethod
    def _check_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            raise RuntimeError("FLOW_DESKTOP_RUNTIME_START_FAILED")

    def _spawn(self, command: list[str], env: dict[str, str]) -> subprocess.Popen:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        self.processes.append(process)
        time.sleep(0.15)
        self._check_process(process)
        return process

    def start(self) -> None:
        web_root = Path(os.environ.get("FLOW_NOVNC_WEB_ROOT", "/usr/share/novnc")).resolve()
        if not (web_root / "vnc.html").is_file():
            raise RuntimeError("FLOW_DESKTOP_RUNTIME_UNAVAILABLE")
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        size = os.environ.get("FLOW_DESKTOP_SIZE", "1280x800x24")
        if not re.fullmatch(r"[0-9]{3,4}x[0-9]{3,4}x(?:16|24|32)", size):
            raise RuntimeError("FLOW_DESKTOP_DISPLAY_INVALID")

        self._spawn(
            [_resolve_executable("FLOW_XVFB_BIN", "Xvfb"), self.display, "-screen", "0", size, "-nolisten", "tcp"],
            env,
        )
        display_socket = Path(f"/tmp/.X11-unix/X{self.display_number}")
        for _ in range(100):
            if display_socket.exists():
                break
            if self.processes[0].poll() is not None:
                raise RuntimeError("FLOW_DESKTOP_RUNTIME_START_FAILED")
            time.sleep(0.1)
        else:
            raise RuntimeError("FLOW_DESKTOP_RUNTIME_START_FAILED")

        self._spawn(
            [
                _resolve_executable("FLOW_X11VNC_BIN", "x11vnc"),
                "-display",
                self.display,
                "-rfbport",
                "5900",
                "-localhost",
                "-nopw",
                "-forever",
                "-shared",
            ],
            env,
        )
        websockify = _resolve_executable("FLOW_WEBSOCKIFY_BIN", "websockify")
        self._spawn([websockify, "--web", str(web_root), "6080", "127.0.0.1:5900"], env)
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", 6080), timeout=0.1):
                    break
            except OSError:
                if any(process.poll() is not None for process in self.processes):
                    raise RuntimeError("FLOW_DESKTOP_RUNTIME_START_FAILED")
                time.sleep(0.1)
        else:
            raise RuntimeError("FLOW_DESKTOP_RUNTIME_START_FAILED")
        os.environ["DISPLAY"] = self.display

    def stop(self) -> bool:
        stopped = True
        for process in reversed(self.processes):
            if process.poll() is not None:
                continue
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                stopped = False
        return stopped


@dataclass
class _ActiveLogin:
    command_id: str
    session_id: str
    workspace_id: str
    profile_id: str
    lease_token: str
    runtime: DesktopRuntime
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    started_at: float = field(default_factory=time.monotonic)
    heartbeat_at: float = 0.0
    timed_out: bool = False
    lease_lost: bool = False
    error_code: str | None = None


class FlowSessionWorker:
    """Runs committed Flow commands while holding the shared media lease."""

    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active: _ActiveLogin | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="flow-session-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 30) -> None:
        self._stop.set()
        if self._active:
            self._active.stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        while not self._stop.is_set() or self._active is not None:
            try:
                if self._active is not None:
                    self._monitor_login()
                elif not self._stop.is_set():
                    self._recover_orphans()
                    command_id = self._claim_pending_command()
                    if command_id:
                        self._process_command(command_id)
            except Exception as exc:
                logger.error("Flow session manager cycle failed (%s).", type(exc).__name__)
            self._stop.wait(self.poll_interval)

    def _recover_orphans(self) -> None:
        """Fence recovery with the global lease; never infer ownership of legacy rows."""
        if self._active is not None:
            return
        from src.modules.tao_video_noi_dung.runner import LEASE_SECONDS
        from datetime import timedelta

        with SessionLocal() as db:
            if not db.query(FlowSessionCommand.id).filter(FlowSessionCommand.state == "RUNNING").first() and not db.query(
                FlowLoginSession.id
            ).filter(FlowLoginSession.active_slot.is_not(None), FlowLoginSession.lease_token.is_not(None)).first():
                return
        recovery_token = str(uuid.uuid4())
        if not _try_acquire_content_video_lease(recovery_token):
            return
        try:
            with SessionLocal() as db:
                now = _now()
                interrupted = set()
                for session in db.query(FlowLoginSession).filter(
                    FlowLoginSession.active_slot.is_not(None), FlowLoginSession.lease_token.is_not(None)
                ).all():
                    session.status = "INTERRUPTED"
                    session.error_code = "FLOW_SESSION_WORKER_RESTARTED"
                    session.active_slot = None
                    session.closed_at = now
                    interrupted.add(session.id)
                    db.query(FlowDesktopGrant).filter(
                        FlowDesktopGrant.session_id == session.id,
                        FlowDesktopGrant.revoked_at.is_(None),
                    ).update({FlowDesktopGrant.revoked_at: now}, synchronize_session=False)
                for command in db.query(FlowSessionCommand).filter(FlowSessionCommand.state == "RUNNING").all():
                    if command.session_id in interrupted:
                        command.state = "FAILED"
                        command.error_code = "FLOW_SESSION_WORKER_RESTARTED"
                        command.finished_at = now
                    else:
                        session = db.get(FlowLoginSession, command.session_id) if command.session_id else None
                        if session and session.active_slot:
                            # Unknown session ownership requires an operator, even after lease expiry.
                            continue
                        if command.kind == "LOGIN" and command.session_id:
                            command.state = "FAILED"
                            command.error_code = "FLOW_SESSION_NOT_ACTIVE"
                            command.finished_at = now
                            continue
                        if not (command.lease_token or (
                        command.claimed_at and _as_utc(command.claimed_at) < now - timedelta(seconds=LEASE_SECONDS)
                        )):
                            continue
                        command.state = "PENDING"
                        command.lease_token = None
                        command.claimed_at = None
                db.commit()
        finally:
            _release_content_video_lease(recovery_token)

    def _claim_pending_command(self) -> str | None:
        token = str(uuid.uuid4())
        if not _try_acquire_content_video_lease(token):
            return None
        claimed_id = None
        try:
            claimed_id = self._claim_under_lease(token)
            return claimed_id
        finally:
            if claimed_id is None:
                _release_content_video_lease(token)

    def _claim_under_lease(self, token: str) -> str | None:
        with SessionLocal() as db:
            candidate = (
                db.query(FlowSessionCommand.id)
                .filter(FlowSessionCommand.state == "PENDING")
                .order_by(FlowSessionCommand.created_at, FlowSessionCommand.id)
                .first()
            )
            if candidate is None:
                return None
            command_id = candidate[0]
            claimed = db.execute(
                update(FlowSessionCommand)
                .where(FlowSessionCommand.id == command_id, FlowSessionCommand.state == "PENDING")
                .values(
                    state="RUNNING",
                    claimed_at=_now(),
                    lease_token=token,
                    attempts=FlowSessionCommand.attempts + 1,
                )
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount == 1:
                command = db.get(FlowSessionCommand, command_id)
                if command.kind == "LOGIN" and command.session_id:
                    db.query(FlowLoginSession).filter(
                        FlowLoginSession.id == command.session_id,
                        FlowLoginSession.status == "LOGIN_REQUESTED",
                    ).update({FlowLoginSession.lease_token: token}, synchronize_session=False)
            db.commit()
            return command_id if claimed.rowcount == 1 else None

    def _requeue(self, command_id: str) -> None:
        with SessionLocal() as db:
            command = db.get(FlowSessionCommand, command_id)
            token = command.lease_token if command else None
            db.query(FlowSessionCommand).filter(FlowSessionCommand.id == command_id).update(
                {FlowSessionCommand.state: "PENDING", FlowSessionCommand.claimed_at: None, FlowSessionCommand.lease_token: None},
                synchronize_session=False,
            )
            db.commit()
        if token:
            _release_content_video_lease(token)

    def _process_command(self, command_id: str) -> None:
        with SessionLocal() as db:
            command = db.get(FlowSessionCommand, command_id)
            if command is None:
                return
            snapshot = (command.kind, command.session_id, command.workspace_id, command.profile_id)
            token = command.lease_token
        kind, session_id, workspace_id, profile_id = snapshot
        if not token or not _heartbeat_content_video_lease(token):
            return
        if kind == "CLOSE":
            try:
                self._process_close(command_id, session_id)
            finally:
                _release_content_video_lease(token)
            return
        if kind not in {"LOGIN", "CHECK"}:
            self._finish_command(command_id, "FAILED", error_code="FLOW_COMMAND_UNSUPPORTED")
            _release_content_video_lease(token)
            return

        if kind == "LOGIN":
            with SessionLocal() as db:
                session = db.get(FlowLoginSession, session_id)
                if session is None:
                    self._finish_command(command_id, "FAILED", error_code="FLOW_SESSION_NOT_FOUND")
                    _release_content_video_lease(token)
                    return
                if session.status in {"CLOSED", "FAILED", "TIMED_OUT", "INTERRUPTED"}:
                    self._finish_command(command_id, "FAILED", error_code="FLOW_SESSION_NOT_ACTIVE")
                    _release_content_video_lease(token)
                    return
                if session.lease_token != token:
                    self._finish_command(command_id, "FAILED", error_code="FLOW_SESSION_OWNER_UNKNOWN")
                    _release_content_video_lease(token)
                    return
                if session.status == "CLOSE_REQUESTED":
                    session.status = "CLOSED"
                    session.active_slot = None
                    session.closed_at = _now()
                    db.commit()
                    self._finish_command(command_id, "DONE")
                    _release_content_video_lease(token)
                    return
                if _as_utc(session.expires_at) <= _now():
                    session.status = "TIMED_OUT"
                    session.active_slot = None
                    session.error_code = "FLOW_LOGIN_SESSION_EXPIRED"
                    session.closed_at = _now()
                    db.commit()
                    self._finish_command(command_id, "FAILED", error_code="FLOW_LOGIN_SESSION_EXPIRED")
                    _release_content_video_lease(token)
                    return
        if kind == "LOGIN":
            self._start_login(command_id, session_id, workspace_id, profile_id, token)
        else:
            try:
                self._run_profile_check(command_id, workspace_id, profile_id)
            finally:
                _release_content_video_lease(token)

    def _run_profile_check(self, command_id: str, workspace_id: str, profile_id: str) -> None:
        from .context import use_flow_profile
        from session_manager import check_login_status

        try:
            with use_flow_profile(workspace_id, profile_id):
                result = check_login_status()
            with SessionLocal() as db:
                service.record_profile_check(
                    db,
                    workspace_id,
                    profile_id,
                    result.get("flow_music_state", "UNKNOWN"),
                    result.get("google_flow_state", "UNKNOWN"),
                )
            self._finish_command(
                command_id,
                "DONE",
                result_json=json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                error_code=result.get("error_code"),
            )
        except Exception as exc:
            logger.warning("Flow profile check failed (%s).", type(exc).__name__)
            with SessionLocal() as db:
                service.record_profile_state(
                    db,
                    workspace_id,
                    profile_id,
                    state="CHECK_FAILED",
                    error_code="FLOW_PROFILE_CHECK_FAILED",
                )
            self._finish_command(command_id, "FAILED", error_code="FLOW_PROFILE_CHECK_FAILED")

    def _start_login(
        self, command_id: str, session_id: str, workspace_id: str, profile_id: str, lease_token: str
    ) -> None:
        try:
            runtime = DesktopRuntime()
        except Exception as exc:
            self._fail_login_start(command_id, session_id, lease_token, "FLOW_DESKTOP_RUNTIME_UNAVAILABLE")
            logger.warning("Flow desktop runtime setup failed (%s).", type(exc).__name__)
            return
        active = _ActiveLogin(
            command_id=command_id,
            session_id=session_id,
            workspace_id=workspace_id,
            profile_id=profile_id,
            lease_token=lease_token,
            runtime=runtime,
            heartbeat_at=time.monotonic(),
        )
        self._active = active
        with SessionLocal() as db:
            session = db.get(FlowLoginSession, session_id)
            if session is None or session.status == "CLOSE_REQUESTED":
                active.stop_event.set()
            elif session.status == "LOGIN_REQUESTED":
                session.lease_token = lease_token
                session.status = "OPENING"
                db.commit()
        if active.stop_event.is_set():
            self._finish_active_login(active, runtime_stopped=runtime.stop())
            return
        try:
            runtime.start()
        except Exception as exc:
            active.error_code = str(exc) if str(exc).startswith("FLOW_DESKTOP_") else "FLOW_DESKTOP_RUNTIME_START_FAILED"
            active.stop_event.set()
            self._finish_active_login(active, runtime_stopped=runtime.stop())
            return

        thread = threading.Thread(
            target=self._login_browser_thread,
            args=(active,),
            name=f"flow-login-{session_id[:8]}",
            daemon=True,
        )
        active.thread = thread
        thread.start()

    def _fail_login_start(
        self, command_id: str, session_id: str, lease_token: str, error_code: str
    ) -> None:
        with SessionLocal() as db:
            session = db.get(FlowLoginSession, session_id)
            if session is not None:
                session.status = "FAILED"
                session.error_code = error_code
                session.active_slot = None
                session.closed_at = _now()
                db.commit()
        self._finish_command(command_id, "FAILED", error_code=error_code)
        try:
            _release_content_video_lease(lease_token)
        except Exception as exc:
            logger.error("Flow session lease release failed (%s).", type(exc).__name__)

    @staticmethod
    def _login_browser_thread(active: _ActiveLogin) -> None:
        from .context import use_flow_profile
        from session_manager import open_login_session

        def mark_open() -> None:
            with SessionLocal() as db:
                session = db.get(FlowLoginSession, active.session_id)
                if session is None:
                    active.stop_event.set()
                elif session.status in {"LOGIN_REQUESTED", "OPENING"}:
                    session.status = "OPEN"
                    session.started_at = _now()
                    db.commit()
                else:
                    db.rollback()
                    active.stop_event.set()

        try:
            with use_flow_profile(active.workspace_id, active.profile_id):
                with SessionLocal() as db:
                    session = db.get(FlowLoginSession, active.session_id)
                    remaining = max(0.0, (_as_utc(session.expires_at) - _now()).total_seconds()) if session else 0.0
                if remaining <= 0:
                    active.timed_out = True
                    return
                open_login_session(
                    wait_for_close=True,
                    stop_event=active.stop_event,
                    on_started=mark_open,
                    timeout_sec=int(remaining),
                )
        except Exception as exc:
            active.error_code = getattr(exc, "error_code", None) or "FLOW_LOGIN_SESSION_FAILED"
            logger.warning("Flow login session failed (%s).", type(exc).__name__)

    def _monitor_login(self) -> None:
        active = self._active
        if active is None:
            return
        now_mono = time.monotonic()
        with SessionLocal() as db:
            session = db.get(FlowLoginSession, active.session_id)
            if session is None:
                active.stop_event.set()
            elif session.status == "CLOSE_REQUESTED":
                active.stop_event.set()
            elif _as_utc(session.expires_at) <= _now():
                active.timed_out = True
                active.stop_event.set()

        if now_mono - active.heartbeat_at >= 5:
            try:
                lease_ok = _heartbeat_content_video_lease(active.lease_token)
            except Exception:
                lease_ok = False
            active.heartbeat_at = now_mono
            if not lease_ok:
                active.lease_lost = True
                active.stop_event.set()

        if active.thread is None or active.thread.is_alive():
            return
        active.thread.join(timeout=0)
        runtime_stopped = active.runtime.stop()
        self._finish_active_login(active, runtime_stopped=runtime_stopped)

    def _finish_active_login(self, active: _ActiveLogin, *, runtime_stopped: bool) -> None:
        terminal_status = (
            "INTERRUPTED" if active.lease_lost or not runtime_stopped
            else "TIMED_OUT" if active.timed_out
            else "FAILED" if active.error_code
            else "CLOSED"
        )
        error_code = active.error_code or (
            "FLOW_WORKER_LEASE_LOST" if active.lease_lost else
            "FLOW_DESKTOP_SHUTDOWN_FAILED" if not runtime_stopped else
            "FLOW_LOGIN_SESSION_EXPIRED" if active.timed_out else None
        )
        with SessionLocal() as db:
            session = db.get(FlowLoginSession, active.session_id)
            if session is not None:
                session.status = terminal_status
                session.error_code = error_code
                session.closed_at = _now()
                if runtime_stopped:
                    session.active_slot = None
                db.query(FlowDesktopGrant).filter(
                    FlowDesktopGrant.session_id == active.session_id,
                    FlowDesktopGrant.revoked_at.is_(None),
                ).update({FlowDesktopGrant.revoked_at: _now()}, synchronize_session=False)
            db.commit()
        self._finish_command(
            active.command_id,
            "FAILED" if terminal_status in {"FAILED", "INTERRUPTED"} else "DONE",
            error_code=error_code,
        )
        with SessionLocal() as db:
            db.query(FlowSessionCommand).filter(
                FlowSessionCommand.session_id == active.session_id,
                FlowSessionCommand.kind == "CLOSE",
                FlowSessionCommand.state.in_(("PENDING", "RUNNING")),
            ).update(
                {FlowSessionCommand.state: "DONE", FlowSessionCommand.finished_at: _now()},
                synchronize_session=False,
            )
            db.commit()
        if runtime_stopped and not active.lease_lost:
            try:
                _release_content_video_lease(active.lease_token)
            except Exception as exc:
                logger.error("Flow session lease release failed (%s).", type(exc).__name__)
        self._active = None

    def _process_close(self, command_id: str, session_id: str | None) -> None:
        if session_id and self._active and self._active.session_id == session_id:
            self._active.stop_event.set()
            return
        with SessionLocal() as db:
            session = db.get(FlowLoginSession, session_id) if session_id else None
            if session and session.active_slot:
                # Only its original manager may close a live browser. Recovery handles expired owners.
                self._requeue(command_id)
                return
            if session and session.status not in {"CLOSED", "FAILED", "TIMED_OUT", "INTERRUPTED"}:
                session.status = "CLOSED"
                session.active_slot = None
                session.closed_at = _now()
                db.query(FlowDesktopGrant).filter(
                    FlowDesktopGrant.session_id == session_id,
                    FlowDesktopGrant.revoked_at.is_(None),
                ).update({FlowDesktopGrant.revoked_at: _now()}, synchronize_session=False)
            db.commit()
        self._finish_command(command_id, "DONE")

    @staticmethod
    def _finish_command(
        command_id: str,
        state: str,
        *,
        result_json: str | None = None,
        error_code: str | None = None,
    ) -> None:
        with SessionLocal() as db:
            command = db.get(FlowSessionCommand, command_id)
            if command is not None:
                command.state = state
                command.result_json = result_json
                command.error_code = error_code
                command.finished_at = _now()
                db.commit()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    manager = FlowSessionWorker()
    app.state.flow_session_worker = manager
    manager.start()
    try:
        yield
    finally:
        manager.stop()


app = FastAPI(title="Flow session worker", docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)


@app.get("/healthz")
def healthz():
    manager = getattr(app.state, "flow_session_worker", None)
    return {"status": "ok" if manager and manager.running else "starting"}


def start_session_worker() -> FlowSessionWorker:
    """Public parent integration helper; app lifespan normally owns this lifecycle."""
    manager = FlowSessionWorker()
    manager.start()
    return manager
