import os
import sys
import subprocess
import socket
from pathlib import Path
import pytest

BRIDGE = Path(__file__).resolve().parents[2] / "cong_cu_tu_dong" / "flow_bridge"
sys.path.insert(0, str(BRIDGE))


def _start_singleton_process(profile_dir: Path, *, hold_managed_lock: bool):
    script = (
        "import os,socket,sys,time; from pathlib import Path; "
        "sys.path.insert(0,sys.argv[1]); from profile_guard import profile_lock; "
        "profile=Path(sys.argv[2]); "
        "profile.mkdir(parents=True,exist_ok=True); "
        "guard=profile_lock(profile) if sys.argv[4]=='managed' else None; "
        "guard.__enter__() if guard else None; "
        "(profile/'SingletonLock').symlink_to(f'{socket.gethostname()}-{os.getpid()}'); "
        "print('READY',flush=True); time.sleep(60)"
    )
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(BRIDGE),
            str(profile_dir),
            f"--user-data-dir={profile_dir}",
            "managed" if hold_managed_lock else "unmanaged",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def test_ensure_profile_free_preserves_chromium_singleton(tmp_path):
    from profile_guard import ensure_profile_free

    singleton = tmp_path / "SingletonLock"
    singleton.write_text("live chromium owner", encoding="utf-8")

    ensure_profile_free(tmp_path)

    assert singleton.read_text(encoding="utf-8") == "live chromium owner"


def test_profile_lock_serializes_other_process_and_releases_after_exit(tmp_path):
    import profile_guard

    lock = getattr(profile_guard, "profile_lock", None)
    busy = getattr(profile_guard, "ProfileBusy", None)
    assert callable(lock) and isinstance(busy, type), "profile guard must provide a process-shared lock"

    profile_dir = tmp_path / "profile"
    script = (
        "import sys,time; sys.path.insert(0,sys.argv[1]); "
        "from profile_guard import profile_lock; "
        "guard=profile_lock(sys.argv[2]); guard.__enter__(); "
        "print('READY', flush=True); time.sleep(30)"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(BRIDGE), str(profile_dir)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "READY"
        with pytest.raises(busy):
            with lock(profile_dir):
                pass
    finally:
        child.terminate()
        child.wait(timeout=10)

    with lock(profile_dir):
        pass


def test_profile_lock_preserves_live_chromium_and_recovers_after_crash(tmp_path):
    from profile_guard import ProfileBusy, profile_lock

    profile_dir = tmp_path / "profile"
    child = _start_singleton_process(profile_dir, hold_managed_lock=False)
    singleton = profile_dir / "SingletonLock"
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "READY"
        command_line = Path(f"/proc/{child.pid}/cmdline").read_bytes().split(b"\0")
        assert f"--user-data-dir={profile_dir}".encode() in command_line
        with pytest.raises(ProfileBusy):
            with profile_lock(profile_dir):
                pass
        assert singleton.is_symlink()
    finally:
        child.kill()
        child.wait(timeout=10)

    with profile_lock(profile_dir):
        assert not singleton.is_symlink()


def test_profile_lock_crash_releases_managed_lock_and_cleans_dead_singleton(tmp_path):
    from profile_guard import ProfileBusy, profile_lock

    profile_dir = tmp_path / "profile"
    child = _start_singleton_process(profile_dir, hold_managed_lock=True)
    singleton = profile_dir / "SingletonLock"
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "READY"
        with pytest.raises(ProfileBusy):
            with profile_lock(profile_dir):
                pass
        assert singleton.is_symlink()
    finally:
        child.kill()
        child.wait(timeout=10)

    with profile_lock(profile_dir):
        assert not singleton.is_symlink()


def test_profile_lock_refuses_unknown_singleton_owner(tmp_path):
    from profile_guard import ProfileBusy, profile_lock

    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    singleton = profile_dir / "SingletonLock"
    singleton.symlink_to(f"other-host-{os.getpid()}")

    with pytest.raises(ProfileBusy):
        with profile_lock(profile_dir):
            pass

    assert singleton.is_symlink()


def test_profile_directory_is_workspace_scoped_and_rejects_traversal(tmp_path):
    from profile_guard import profile_dir_for

    assert profile_dir_for(tmp_path, "profile-1", "workspace-1") == (
        tmp_path / "workspaces" / "workspace-1" / "profiles" / "profile-1"
    )
    assert profile_dir_for(tmp_path, "profile-1", "workspace-2") != profile_dir_for(
        tmp_path, "profile-1", "workspace-1"
    )
    with pytest.raises(ValueError):
        profile_dir_for(tmp_path, "../outside", "workspace-1")
