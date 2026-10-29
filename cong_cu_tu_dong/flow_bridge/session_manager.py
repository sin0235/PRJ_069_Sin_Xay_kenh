"""Manual Google sign-in and evidence-based Flow profile checks."""

import logging
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import urlsplit

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from playwright.sync_api import sync_playwright

from config import (
    BROWSER_CHANNEL,
    FLOW_MUSIC_URL,
    GOOGLE_FLOW_URL,
    LOCAL_BROWSER_PROFILE_DIR,
    browser_launch_args,
    get_current_browser_profile_dir,
    sync_browser_profile,
)
from profile_guard import profile_locked

logger = logging.getLogger(__name__)


class FlowLoginRequired(RuntimeError):
    """The selected Google profile requires a manual sign-in."""

    error_code = "FLOW_LOGIN_REQUIRED"


class FlowQuotaExceeded(RuntimeError):
    """Google Flow reports that the selected account has no usable quota."""

    error_code = "FLOW_QUOTA_LIMITED"

    def __init__(self, message: str, *, submitted: bool = False):
        super().__init__(message)
        self.submitted = submitted


class FlowSubmissionNotSent(RuntimeError):
    """Flow UI failed before the generation request was submitted."""


def classify_provider_state(
    url: str,
    *,
    authenticated: bool = False,
    login_required: bool = False,
    quota_limited: bool = False,
) -> str:
    if quota_limited:
        return "QUOTA_LIMITED"
    if login_required or "accounts.google.com" in url:
        return "LOGIN_REQUIRED"
    if authenticated:
        return "READY"
    return "UNKNOWN"


def _visible(page, selector: str) -> bool:
    try:
        locator = page.locator(selector).first
        return locator.count() > 0 and locator.is_visible()
    except Exception:
        return False


def _login_prompt_visible(page) -> bool:
    return _visible(page, "button:has-text('Sign in'), button:has-text('Log in'), button:has-text('Đăng nhập')")


def _quota_visible(page) -> bool:
    try:
        body = page.locator("body").inner_text(timeout=3000)
    except Exception:
        return False
    return bool(re.search(r"quota exceeded|out of credits|daily limit reached|hết lượt|vượt hạn mức", body, re.I))


@profile_locked(get_current_browser_profile_dir)
def open_login_session(
    wait_for_close: bool = False,
    *,
    stop_event: threading.Event | None = None,
    on_started=None,
    timeout_sec: int = 900,
) -> None:
    profile_dir = sync_browser_profile()
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel=BROWSER_CHANNEL,
            headless=False,
            args=browser_launch_args("--start-maximized"),
            viewport=None,
        )
        try:
            if on_started:
                on_started()
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(FLOW_MUSIC_URL, wait_until="domcontentloaded", timeout=45000)
            flow_page = context.new_page()
            flow_page.goto(GOOGLE_FLOW_URL, wait_until="domcontentloaded", timeout=45000)
            if wait_for_close:
                deadline = time.monotonic() + timeout_sec
                while not context.is_closed() and time.monotonic() < deadline:
                    if stop_event and stop_event.wait(0.5):
                        break
                    if stop_event is None:
                        time.sleep(0.5)
            else:
                print("Đăng nhập Google Flow và Flow Music trong cửa sổ đang mở.")
                input("Đóng trình duyệt để lưu phiên đăng nhập...")
        finally:
            if not context.is_closed():
                context.close()


@profile_locked(get_current_browser_profile_dir)
def check_login_status() -> dict:
    profile_dir = sync_browser_profile()
    status_result = {
        "state": "UNKNOWN",
        "profile_exists": profile_dir.exists()
        and any(path.name != ".flow_profile.lock" for path in profile_dir.iterdir()),
        "flow_music_state": "UNKNOWN",
        "google_flow_state": "UNKNOWN",
        "flow_music_logged_in": False,
        "google_flow_logged_in": False,
    }
    from src.modules.flow_sessions.context import flow_profile_metadata

    status_result.update(flow_profile_metadata())
    if not status_result["profile_exists"]:
        status_result["state"] = "LOGIN_REQUIRED"
        status_result["flow_music_state"] = "LOGIN_REQUIRED"
        status_result["google_flow_state"] = "LOGIN_REQUIRED"
        return status_result

    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                channel=BROWSER_CHANNEL,
                headless=True,
                args=browser_launch_args(),
            )
            try:
                music_auth = {"authenticated": False, "quota_limited": False}

                def observe_music_response(response):
                    try:
                        if "/__api/" not in response.url:
                            return
                        authorization = response.request.headers.get("authorization", "")
                        if not authorization.startswith("Bearer "):
                            return
                        music_auth["quota_limited"] |= response.status == 429
                        music_auth["authenticated"] |= 200 <= response.status < 300
                    except Exception:
                        return

                music_page = context.pages[0] if context.pages else context.new_page()
                music_page.on("response", observe_music_response)
                music_page.goto(FLOW_MUSIC_URL, wait_until="domcontentloaded", timeout=30000)
                music_page.wait_for_timeout(1500)
                status_result["flow_music_state"] = classify_provider_state(
                    music_page.url,
                    authenticated=music_auth["authenticated"],
                    login_required=_login_prompt_visible(music_page),
                    quota_limited=music_auth["quota_limited"] or _quota_visible(music_page),
                )

                flow_page = context.new_page()
                flow_auth = {"quota_limited": False}

                def observe_flow_response(response):
                    try:
                        if urlsplit(response.url).hostname in {"flow.google.com", "labs.google"} and response.status == 429:
                            flow_auth["quota_limited"] = True
                    except Exception:
                        return

                flow_page.on("response", observe_flow_response)
                flow_page.goto(GOOGLE_FLOW_URL, wait_until="domcontentloaded", timeout=30000)
                flow_page.wait_for_timeout(1500)
                flow_ready = _visible(
                    flow_page,
                    "button:has-text('New project'), button:has-text('Dự án mới')",
                )
                status_result["google_flow_state"] = classify_provider_state(
                    flow_page.url,
                    authenticated=flow_ready,
                    login_required=_login_prompt_visible(flow_page),
                    quota_limited=flow_auth["quota_limited"] or _quota_visible(flow_page),
                )
            finally:
                context.close()

        status_result["flow_music_logged_in"] = status_result["flow_music_state"] == "READY"
        status_result["google_flow_logged_in"] = status_result["google_flow_state"] == "READY"
        states = (status_result["flow_music_state"], status_result["google_flow_state"])
        status_result["state"] = (
            "QUOTA_LIMITED" if "QUOTA_LIMITED" in states
            else "LOGIN_REQUIRED" if "LOGIN_REQUIRED" in states
            else "READY" if all(state == "READY" for state in states)
            else "UNKNOWN"
        )
    except Exception as exc:
        status_result["state"] = "CHECK_FAILED"
        status_result["error_code"] = "FLOW_PROFILE_CHECK_FAILED"
        logger.warning("Flow profile status check failed (%s).", type(exc).__name__)
    return status_result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        print(check_login_status())
    elif len(sys.argv) > 1 and sys.argv[1] == "--background":
        open_login_session(wait_for_close=True)
    else:
        open_login_session()
