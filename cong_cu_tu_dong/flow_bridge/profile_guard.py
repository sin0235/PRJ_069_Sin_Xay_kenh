# -*- coding: utf-8 -*-
"""Khóa liên tiến trình để bảo vệ hồ sơ trình duyệt."""
import os
from contextlib import contextmanager
from pathlib import Path


class ProfileBusy(RuntimeError):
    """Hồ sơ đang được trình duyệt khác sử dụng."""


@contextmanager
def profile_lock(profile_dir):
    profile_dir = Path(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    with (profile_dir / ".baha_profile.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ProfileBusy("Hồ sơ Flow đang được sử dụng.") from exc
        else:
            import fcntl
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ProfileBusy("Hồ sơ Flow đang được sử dụng.") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def ensure_profile_free(profile_dir):
    """Chromium tự xử lý khóa của nó; không xóa khóa hoặc dừng tiến trình."""


def profile_locked(profile_path):
    from functools import wraps

    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            with profile_lock(profile_path()):
                return function(*args, **kwargs)
        return guarded
    return decorate


def validate_profile_id(value):
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("Tên hồ sơ Flow chỉ được gồm chữ không dấu, số, gạch dưới hoặc gạch ngang.")
    return value


def profile_dir_for(root, profile_id):
    return Path(root) / validate_profile_id(profile_id)
