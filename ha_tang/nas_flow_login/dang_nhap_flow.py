import os
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright
from profile_guard import profile_dir_for, profile_lock

FLOW_MUSIC_URL = "https://www.flowmusic.app/"
GOOGLE_FLOW_URL = "https://flow.google.com/"


def main() -> None:
    profile_dir = (profile_dir_for(os.environ["FLOW_PROFILE_ROOT"], os.environ.get("FLOW_PROFILE_ID", "mac_dinh"))
                   if os.environ.get("FLOW_PROFILE_ROOT") else Path(os.environ["LOCAL_BROWSER_PROFILE_DIR"]))
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser_executable = playwright.chromium.executable_path

    command = [
        browser_executable,
        f"--user-data-dir={profile_dir}",
        "--no-sandbox",
        "--no-first-run",
        "--no-default-browser-check",
        "--password-store=basic",
        "--new-window",
        FLOW_MUSIC_URL,
        GOOGLE_FLOW_URL,
    ]

    print("Đăng nhập Google trong Chromium; đóng cửa sổ để lưu phiên.", flush=True)
    with profile_lock(profile_dir):
        raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    main()
