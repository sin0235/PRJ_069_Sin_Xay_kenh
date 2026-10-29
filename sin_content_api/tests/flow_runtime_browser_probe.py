"""Run inside the built browser image; credentials arrive only through stdin.

This opens the real production UI and noVNC, without submitting any Google job.
The caller must close the returned login session or use it for restart recovery.
"""

import json
import sys
import uuid

from playwright.sync_api import sync_playwright


def main():
    credentials = json.load(sys.stdin)
    origin = credentials["origin"].rstrip("/")
    stage = "browser_start"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(viewport={"width": 1440, "height": 1100})
            page = context.new_page()
            stage = "owner_login"
            page.goto(f"{origin}/auth/login?redirect=/flow-sessions", wait_until="domcontentloaded")
            page.locator("#login-email").fill(credentials["email"])
            page.locator("input[name=password]").fill(credentials["password"])
            page.locator("button[type=submit]").click()
            page.wait_for_url("**/flow-sessions", timeout=45000)
            stage = "create_profile"
            page.locator("#flow-profile-name").fill(f"Docker proof {uuid.uuid4().hex[:8]}")
            with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith("/v1/media/flow/profiles")) as created:
                page.get_by_role("button", name="Tạo hồ sơ", exact=True).click()
            assert created.value.status == 201
            stage = "open_desktop"
            with page.expect_response(lambda response: response.url.endswith("/v1/media/flow/login-sessions/start")) as started:
                page.get_by_role("button", name="Mở phiên đăng nhập", exact=True).click()
            assert started.value.status == 202
            session_id = started.value.json()["id"]
            frame = page.frame_locator('iframe[title="Desktop đăng nhập Google Flow"]')
            frame.locator("html.noVNC_connected").wait_for(state="attached", timeout=90000)
            stage = "desktop_screenshot"
            page.locator('iframe[title="Desktop đăng nhập Google Flow"]').screenshot(path="/tmp/flow-desktop-connected.png")
            stage = "session_reload_hydration"
            page.reload(wait_until="domcontentloaded")
            frame.locator("html.noVNC_connected").wait_for(state="attached", timeout=45000)
            browser.close()
        print(json.dumps({"status": "CONNECTED_AND_REHYDRATED", "session_id": session_id, "google_auth": "NOT_VERIFIED"}))
        return 0
    except Exception as exc:
        # Never render browser request bodies, cookies, credentials, or exception text.
        print(json.dumps({"status": "FAILED", "stage": stage, "error_type": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
