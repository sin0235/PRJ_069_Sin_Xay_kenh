"""Process-shared locking and path checks for persistent Chromium profiles."""

from contextlib import contextmanager
from functools import wraps
import errno
import os
from pathlib import Path
import re
import socket
import threading


class ProfileBusy(RuntimeError):
    """The persistent profile is already owned by another operation."""


_thread_locks_guard = threading.Lock()
_thread_locks: dict[str, threading.RLock] = {}
_lock_state = threading.local()
_CHROMIUM_SINGLETON_LOCK = "SingletonLock"


def validate_profile_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("Invalid Flow profile id.")
    return value


def profile_dir_for(root: str | Path, profile_id: str, workspace_id: str | None = None) -> Path:
    profile_id = validate_profile_id(profile_id)
    path = Path(root)
    if workspace_id is not None:
        path /= "workspaces" / Path(validate_profile_id(workspace_id)) / "profiles"
    return path / profile_id


def _pid_is_live(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError as exc:
        return exc.errno != errno.ESRCH
    return True


def _process_uses_profile(pid: int, profile_dir: Path) -> bool:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    args = [arg.decode("utf-8", errors="surrogateescape") for arg in raw.split(b"\0") if arg]
    for index, arg in enumerate(args):
        if arg.startswith("--user-data-dir="):
            candidate = arg.partition("=")[2]
        elif arg == "--user-data-dir" and index + 1 < len(args):
            candidate = args[index + 1]
        else:
            continue
        try:
            if Path(candidate).resolve() == profile_dir:
                return True
        except (OSError, RuntimeError):
            continue
    return False


def _remove_stale_chromium_singleton(profile_dir: Path) -> None:
    """Remove only a dead lock from this host; unknown and live owners fail closed."""
    singleton = profile_dir / _CHROMIUM_SINGLETON_LOCK
    try:
        singleton_info = singleton.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ProfileBusy("Chromium profile lock state is unknown.") from exc

    if not singleton_info or not singleton.is_symlink():
        raise ProfileBusy("Chromium profile lock state is unknown.")

    try:
        owner = os.readlink(singleton)
    except OSError as exc:
        raise ProfileBusy("Chromium profile lock state is unknown.") from exc
    hostname, separator, pid_text = owner.rpartition("-")
    if not separator or hostname != socket.gethostname() or not pid_text.isdecimal():
        raise ProfileBusy("Chromium singleton owner is unknown.")
    pid = int(pid_text)
    if pid <= 0:
        raise ProfileBusy("Chromium singleton owner is unknown.")

    if _pid_is_live(pid):
        if _process_uses_profile(pid, profile_dir):
            raise ProfileBusy("Chromium still owns this Flow profile.")
        raise ProfileBusy("Chromium singleton owner is unknown.")

    try:
        if not singleton.is_symlink() or os.readlink(singleton) != owner:
            raise ProfileBusy("Chromium singleton owner changed during recovery.")
        singleton.unlink()
    except OSError as exc:
        raise ProfileBusy("Chromium stale profile lock could not be recovered.") from exc


@contextmanager
def profile_lock(profile_dir: str | Path):
    path = Path(profile_dir).resolve()
    key = str(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        path.chmod(0o700)
    with _thread_locks_guard:
        thread_lock = _thread_locks.setdefault(key, threading.RLock())
    if not thread_lock.acquire(blocking=False):
        raise ProfileBusy("Flow profile is busy.")

    held = getattr(_lock_state, "held", {})
    depth = held.get(key, 0)
    lock_file = None
    try:
        if depth == 0:
            lock_file = (path / ".flow_profile.lock").open("a+b")
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"0")
                    lock_file.flush()
                lock_file.seek(0)
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise ProfileBusy("Flow profile is busy.") from exc
            else:
                import fcntl

                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ProfileBusy("Flow profile is busy.") from exc
            held = dict(held)
            _lock_state.held = held
            held[key] = 0
        held[key] += 1
        if depth == 0 and os.name == "posix":
            _remove_stale_chromium_singleton(path)
        yield
    finally:
        if key in held:
            held[key] -= 1
            if held[key] == 0:
                del held[key]
                if lock_file is not None:
                    if os.name == "nt":
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        if lock_file is not None:
            lock_file.close()
        thread_lock.release()


def profile_locked(profile_path):
    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            with profile_lock(profile_path()):
                return function(*args, **kwargs)

        return guarded

    return decorate


def ensure_profile_free(profile_dir: str | Path) -> None:
    """Retain lock files; stale SingletonLock recovery runs only under profile_lock."""
