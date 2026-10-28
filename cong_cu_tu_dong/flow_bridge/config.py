# -*- coding: utf-8 -*-
"""Cấu hình cho Bộ tự động hóa Google Flow & Flow Music (Playwright Persistent Worker).
Ưu tiên chi phí 0đ, tận dụng gói Google AI Pro sẵn có.
"""

import os
import pathlib
import shutil
from profile_guard import profile_dir_for

BASE_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[2]

# Thư mục lưu trữ hồ sơ trình duyệt trên NAS (dùng để lưu trữ bền vững)
FLOW_PROFILE_ROOT = os.environ.get("FLOW_PROFILE_ROOT")
FLOW_PROFILE_ID = os.environ.get("FLOW_PROFILE_ID", "mac_dinh")
BROWSER_PROFILE_DIR = (profile_dir_for(FLOW_PROFILE_ROOT, FLOW_PROFILE_ID) if FLOW_PROFILE_ROOT
                       else pathlib.Path(os.environ.get("BROWSER_PROFILE_DIR", str(BASE_DIR / "browser_profile"))))
BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# Thư mục hồ sơ cục bộ trên ổ đĩa C: (ngăn chặn lỗi khóa ProcessSingleton / SQLite SMB của Windows khi chạy Chromium trên NAS)
LOCAL_BROWSER_PROFILE_DIR = (BROWSER_PROFILE_DIR if FLOW_PROFILE_ROOT else pathlib.Path(os.environ.get(
    "LOCAL_BROWSER_PROFILE_DIR",
    str(pathlib.Path(os.environ.get("LOCALAPPDATA", str(pathlib.Path.home()))) / "BahaFlowBridge" / "browser_profile"),
)))
LOCAL_BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

def sync_browser_profile(src_dir: pathlib.Path = BROWSER_PROFILE_DIR, dst_dir: pathlib.Path = LOCAL_BROWSER_PROFILE_DIR) -> pathlib.Path:
    """Đồng bộ hồ sơ trình duyệt an toàn từ NAS về thư mục cục bộ để Playwright mở không bị lỗi khóa tệp."""
    if src_dir.resolve() == dst_dir.resolve():
        return dst_dir

    dst_default = dst_dir / "Default"
    dst_default.mkdir(parents=True, exist_ok=True)
    (dst_default / "Network").mkdir(parents=True, exist_ok=True)

    src_local_state = src_dir / "Local State"
    if src_local_state.exists():
        try:
            shutil.copy2(src_local_state, dst_dir / "Local State")
        except Exception:
            pass

    src_cookies = src_dir / "Default" / "Network" / "Cookies"
    if src_cookies.exists():
        try:
            shutil.copy2(src_cookies, dst_default / "Network" / "Cookies")
        except Exception:
            pass

    return dst_dir

def sync_local_to_nas(src_dir: pathlib.Path = LOCAL_BROWSER_PROFILE_DIR, dst_dir: pathlib.Path = BROWSER_PROFILE_DIR) -> None:
    """Đồng bộ hồ sơ trình duyệt sau khi đăng nhập từ ổ cục bộ ngược lại lên NAS để lưu trữ vĩnh viễn."""
    if src_dir.resolve() == dst_dir.resolve():
        return

    dst_default = dst_dir / "Default"
    dst_default.mkdir(parents=True, exist_ok=True)
    (dst_default / "Network").mkdir(parents=True, exist_ok=True)

    src_local_state = src_dir / "Local State"
    if src_local_state.exists():
        try:
            shutil.copy2(src_local_state, dst_dir / "Local State")
        except Exception:
            pass

    src_cookies = src_dir / "Default" / "Network" / "Cookies"
    if src_cookies.exists():
        try:
            shutil.copy2(src_cookies, dst_default / "Network" / "Cookies")
        except Exception:
            pass

# Thư mục lưu trữ tệp media tải về
MEDIA_ASSETS_DIR = pathlib.Path(os.environ.get(
    "MEDIA_ROOT_DIR", str(PROJECT_ROOT / "03_ban_lam_viec" / "media_assets")
))
MEDIA_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Địa chỉ nền tảng Google chính thức
FLOW_MUSIC_URL = "https://www.flowmusic.app/"
GOOGLE_FLOW_URL = "https://flow.google.com/"

# Cấu hình trình duyệt (Sử dụng Microsoft Edge)
BROWSER_CHANNEL = os.environ.get("BROWSER_CHANNEL", "msedge")
DEFAULT_TIMEOUT_MS = 240000  # 4 phút cho quá trình render cloud
POLL_INTERVAL_SEC = 3
