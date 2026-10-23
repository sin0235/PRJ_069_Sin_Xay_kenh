# -*- coding: utf-8 -*-
"""Quản lý phiên đăng nhập tài khoản Google AI Pro cho Flow & Flow Music.
Cho phép đăng nhập 1 lần trên Chrome UI thật, lưu vĩnh viễn trong Profile để worker ngầm sử dụng (0đ chi phí).
"""

import os
import pathlib
import sys
import time

CURRENT_DIR = pathlib.Path(__file__).resolve().parent
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
    BROWSER_PROFILE_DIR,
    LOCAL_BROWSER_PROFILE_DIR,
    BROWSER_CHANNEL,
    FLOW_MUSIC_URL,
    GOOGLE_FLOW_URL,
    sync_browser_profile,
    sync_local_to_nas,
)
from profile_guard import ensure_profile_free


class FlowLoginRequired(RuntimeError):
    """Yêu cầu đăng nhập tài khoản Google vào hồ sơ Flow dùng chung."""


def open_login_session():
    """Mở cửa sổ Chrome có giao diện để người dùng đăng nhập tài khoản Google AI Pro."""
    print("=" * 70)
    print("KHỞI TẠO ĐĂNG NHẬP GOOGLE AI PRO (FLOW & FLOW MUSIC)")
    print("=" * 70)
    print(f"Hồ sơ trình duyệt lưu tại: {LOCAL_BROWSER_PROFILE_DIR}")
    print("Đang khởi chạy Microsoft Edge...")

    # Đồng bộ từ NAS về cục bộ và giải phóng khóa
    sync_browser_profile(BROWSER_PROFILE_DIR, LOCAL_BROWSER_PROFILE_DIR)
    ensure_profile_free(LOCAL_BROWSER_PROFILE_DIR)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(LOCAL_BROWSER_PROFILE_DIR),
            channel=BROWSER_CHANNEL,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--start-maximized"
            ],
            viewport=None
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(FLOW_MUSIC_URL)

        # Mở thêm tab Google Flow
        page_flow = context.new_page()
        page_flow.goto(GOOGLE_FLOW_URL)

        print("\n[HƯỚNG DẪN DÀNH CHO BẠN]")
        print("1. Trình duyệt Microsoft Edge đã mở ra với 2 tab:")
        print("   - Tab 1: Google Flow Music (https://www.flowmusic.app/)")
        print("   - Tab 2: Google Flow (https://labs.google/fx/tools/flow)")
        print("2. Vui lòng đăng nhập vào tài khoản Google AI Pro có sẵn của bạn.")
        print("3. Sau khi đăng nhập thành công vào cả hai trang, hãy quay lại terminal này và nhấn ENTER để hoàn tất lưu phiên.")
        print("-" * 70)

        try:
            input("Nhấn phím [ENTER] sau khi bạn đã hoàn tất đăng nhập trên trình duyệt...")
        except EOFError:
            time.sleep(30)

        # Chờ đồng bộ cookie và đóng trình duyệt
        context.close()
        ensure_profile_free(LOCAL_BROWSER_PROFILE_DIR)

        # Đồng bộ ngược từ cục bộ lên NAS để lưu trữ bền vững
        sync_local_to_nas(LOCAL_BROWSER_PROFILE_DIR, BROWSER_PROFILE_DIR)

        print("\n[THÀNH CÔNG] Đã lưu thông tin phiên đăng nhập vào hồ sơ trình duyệt!")
        print("Từ bây giờ, hệ thống BAHA có thể tự động chạy ngầm mà không cần đăng nhập lại.")


def check_login_status() -> dict:
    """Kiểm tra xem hồ sơ trình duyệt đã có phiên đăng nhập hợp lệ hay chưa."""
    sync_browser_profile(BROWSER_PROFILE_DIR, LOCAL_BROWSER_PROFILE_DIR)

    status_result = {
        "profile_exists": LOCAL_BROWSER_PROFILE_DIR.exists() and any(LOCAL_BROWSER_PROFILE_DIR.iterdir()),
        "flow_music_logged_in": False,
        "google_flow_logged_in": False,
    }

    if not status_result["profile_exists"]:
        return status_result

    ensure_profile_free(LOCAL_BROWSER_PROFILE_DIR)

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(LOCAL_BROWSER_PROFILE_DIR),
                channel=BROWSER_CHANNEL,
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            page = context.pages[0] if context.pages else context.new_page()

            # Kiểm tra Flow Music
            page.goto(FLOW_MUSIC_URL, timeout=30000)
            page.wait_for_timeout(3000)
            content = page.content()
            if "Sign in" not in content and "Log in" not in content:
                status_result["flow_music_logged_in"] = True

            # Kiểm tra Google Flow
            page.goto(GOOGLE_FLOW_URL, timeout=30000)
            page.wait_for_timeout(3000)
            content_flow = page.content()
            if "Sign in" not in content_flow:
                status_result["google_flow_logged_in"] = True

            context.close()
    except Exception as e:
        status_result["error"] = str(e)

    return status_result


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        res = check_login_status()
        print(f"Trạng thái phiên đăng nhập: {res}")
    else:
        open_login_session()
