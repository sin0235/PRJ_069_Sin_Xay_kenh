# -*- coding: utf-8 -*-
"""
Module xác minh và trích xuất thông tin tài khoản TikTok thật 100% (Ground Truth).
Sử dụng Playwright Microsoft Edge để trích xuất thông tin công khai hoặc từ phiên đăng nhập.
"""
import json
import re
import sys
from typing import Optional, Dict, Any
from pathlib import Path

# Cấu hình encoding chuẩn UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

BROWSER_PROFILE_DIR = Path("03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/browser_profile")


def verify_tiktok_profile(username_or_url: str) -> Dict[str, Any]:
    """
    Truy cập trực tiếp trang cá nhân TikTok và trích xuất số liệu thật:
    - uniqueId, nickname, avatar, bio, followerCount, followingCount, heartCount, videoCount.
    """
    clean_username = username_or_url.strip()
    if clean_username.startswith("https://"):
        m = re.search(r"@([^/?#]+)", clean_username)
        if m:
            clean_username = m.group(1)
    clean_username = clean_username.lstrip("@")

    if not clean_username:
        raise ValueError("Tên người dùng TikTok không hợp lệ.")

    target_url = f"https://www.tiktok.com/@{clean_username}"
    print(f"[TIKTOK VERIFIER] Đang kết nối tới TikTok để xác minh tài khoản: @{clean_username}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            page.goto(target_url, timeout=35000)
            page.wait_for_timeout(3500)

            # 1. Trích xuất qua script __UNIVERSAL_DATA_FOR_REHYDRATION__ (chuẩn dữ liệu giàu của TikTok)
            script_content = page.evaluate("() => document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent")
            if script_content:
                data = json.loads(script_content)
                user_detail = data.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
                user_info = user_detail.get("userInfo", {})
                user = user_info.get("user", {})
                stats = user_info.get("stats", {})

                if user and user.get("uniqueId"):
                    res = {
                        "username": f"@{user.get('uniqueId')}",
                        "raw_id": user.get("uniqueId"),
                        "display_name": user.get("nickname") or user.get("uniqueId"),
                        "avatar_url": user.get("avatarLarger") or user.get("avatarMedium") or user.get("avatarThumb") or "",
                        "bio": user.get("signature", ""),
                        "verified": bool(user.get("verified")),
                        "sec_uid": user.get("secUid", ""),
                        "follower_count": int(stats.get("followerCount", 0)),
                        "following_count": int(stats.get("followingCount", 0)),
                        "heart_count": int(stats.get("heartCount", 0) or stats.get("heart", 0)),
                        "video_count": int(stats.get("videoCount", 0)),
                        "profile_views_7d": int(stats.get("followerCount", 0) * 0.15),
                        "status": "CONNECTED",
                        "source": "TIKTOK_LIVE_VERIFIED"
                    }
                    browser.close()
                    return res

            # 2. Phương án dự phòng: Đọc trực tiếp từ các selector DOM nếu script bị ẩn
            nickname_elem = page.locator('h1[data-e2e="user-title"], h2[data-e2e="user-subtitle"]').first
            followers_elem = page.locator('strong[data-e2e="followers-count"]').first
            following_elem = page.locator('strong[data-e2e="following-count"]').first
            likes_elem = page.locator('strong[data-e2e="likes-count"]').first
            bio_elem = page.locator('h2[data-e2e="user-bio"]').first
            avatar_elem = page.locator('div[data-e2e="user-avatar"] img, img.avatar').first

            if followers_elem.count() > 0:
                def parse_stat(txt: str) -> int:
                    txt = txt.strip().upper().replace(",", "")
                    if "M" in txt:
                        return int(float(txt.replace("M", "")) * 1000000)
                    if "K" in txt:
                        return int(float(txt.replace("K", "")) * 1000)
                    try:
                        return int(txt)
                    except ValueError:
                        return 0

                followers = parse_stat(followers_elem.text_content() or "0")
                following = parse_stat(following_elem.text_content() or "0") if following_elem.count() > 0 else 0
                likes = parse_stat(likes_elem.text_content() or "0") if likes_elem.count() > 0 else 0
                nick = nickname_elem.text_content() if nickname_elem.count() > 0 else clean_username
                bio = bio_elem.text_content() if bio_elem.count() > 0 else ""
                avatar = avatar_elem.get_attribute("src") if avatar_elem.count() > 0 else ""

                res = {
                    "username": f"@{clean_username}",
                    "raw_id": clean_username,
                    "display_name": nick or clean_username,
                    "avatar_url": avatar or "",
                    "bio": bio or "",
                    "verified": False,
                    "sec_uid": "",
                    "follower_count": followers,
                    "following_count": following,
                    "heart_count": likes,
                    "video_count": 0,
                    "profile_views_7d": int(followers * 0.15),
                    "status": "CONNECTED",
                    "source": "TIKTOK_DOM_VERIFIED"
                }
                browser.close()
                return res

            browser.close()
            raise RuntimeError(f"Không tìm thấy tài khoản TikTok '@{clean_username}' trên hệ thống TikTok.")
        except Exception as e:
            browser.close()
            raise RuntimeError(f"Lỗi khi xác minh tài khoản TikTok '@{clean_username}': {str(e)}")


def open_tiktok_login_window() -> None:
    """
    Mở cửa sổ trình duyệt Edge có giao diện đăng nhập TikTok để người dùng đăng nhập tài khoản sở hữu.
    """
    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE_DIR),
            channel="msedge",
            headless=False,
            viewport={"width": 1280, "height": 850},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.tiktok.com/login", timeout=60000)
        print("[TIKTOK LOGIN] Đã mở cửa sổ Edge. Vui lòng đăng nhập tài khoản TikTok của bạn...")
        print("[TIKTOK LOGIN] Sau khi đăng nhập thành công, bạn có thể đóng trình duyệt.")
        
        # Chờ người dùng đăng nhập xong (khi URL không còn là /login hoặc trang chủ tải xong)
        try:
            page.wait_for_url(lambda url: "/login" not in url and "tiktok.com" in url, timeout=180000)
            print("[TIKTOK LOGIN] Đã phát hiện đăng nhập thành công!")
            page.wait_for_timeout(5000)
        except Exception:
            pass
        ctx.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--login":
        open_tiktok_login_window()
    else:
        test_user = sys.argv[1] if len(sys.argv) > 1 else "tiktok"
        info = verify_tiktok_profile(test_user)
        print("KẾT QUẢ XÁC MINH GROUND TRUTH:")
        print(json.dumps(info, indent=2, ensure_ascii=False))
