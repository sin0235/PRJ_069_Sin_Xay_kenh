# -*- coding: utf-8 -*-
"""Client tương tác tự động với Google Flow (Flow Creative Agent).
Sử dụng Playwright persistent browser context trên ổ cục bộ C: (ngăn chặn lỗi khóa SMB NAS).
Tự động biên dịch bộ lệnh sang mô hình video Omni 1.1 Flash (10 giây), tự động phê duyệt credits,
và tải file MP4 10s nguyên bản về máy.
"""

import hashlib
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Dict, Optional
from urllib.parse import quote

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
    BROWSER_CHANNEL,
    BROWSER_PROFILE_DIR,
    LOCAL_BROWSER_PROFILE_DIR,
    DEFAULT_TIMEOUT_MS,
    GOOGLE_FLOW_URL,
    MEDIA_ASSETS_DIR,
    POLL_INTERVAL_SEC,
    sync_browser_profile,
    sync_local_to_nas,
)
from profile_guard import ensure_profile_free
from session_manager import FlowLoginRequired

_FLOW_MUTEX = threading.Lock()

class GoogleFlowClient:
    """Client tự động hóa Google Flow qua giao diện web với hồ sơ người dùng cục bộ."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    @staticmethod
    def _media_redirect_url(media_name: str) -> str:
        flow_input = json.dumps({"json": {"name": media_name}}, separators=(",", ":"))
        return "https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?input=" + quote(flow_input, safe="")

    def create_video(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        workspace_id: str = "default_ws",
        timeout_sec: int = 240,
        start_image_path: Optional[pathlib.Path] = None,
    ) -> Dict[str, Any]:
        """
        Gửi yêu cầu tạo video 16:9 (10s) tới Google Flow Omni Flash,
        tự động phê duyệt credits, chờ máy chủ hoàn thành và tải MP4 thật 10s về.
        """
        if (os.getenv("TESTING") == "1" or os.getenv("APP_ENV") == "test") and not os.getenv("FORCE_FLOW"):
            target_dir = MEDIA_ASSETS_DIR / "workspaces" / workspace_id / "media"
            target_dir.mkdir(parents=True, exist_ok=True)
            dest_filename = f"flow_real_ai_{uuid.uuid4().hex[:8]}_test.mp4"
            dest_path = target_dir / dest_filename
            ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
            cmd = [
                ffmpeg_bin, "-y", "-f", "lavfi",
                "-i", "color=c=0x1E293B:s=1920x1080:d=10",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                str(dest_path)
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return {
                "status": "SUCCEEDED",
                "filename": dest_filename,
                "storage_path": str(dest_path)
            }

        with _FLOW_MUTEX:
            # 1. Đồng bộ và sử dụng thư mục profile cục bộ trên ổ C: để tránh lỗi đóng kết nối do SQLite SMB locking
            profile_dir = sync_browser_profile()
            ensure_profile_free(profile_dir)

            clean_prompt = prompt.strip()
            print(f"[GOOGLE FLOW OMNI] Bắt đầu tạo video 10s: '{clean_prompt[:70]}...'", flush=True)

            target_dir = MEDIA_ASSETS_DIR / "workspaces" / workspace_id / "media"
            target_dir.mkdir(parents=True, exist_ok=True)

            downloaded_file: Optional[pathlib.Path] = None
            captured_media_name: Optional[str] = None
            is_generation_complete: bool = False

            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    channel=BROWSER_CHANNEL,
                    headless=self.headless,
                    viewport={"width": 1400, "height": 900},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox"
                    ],
                    downloads_path=str(target_dir),
                    accept_downloads=True
                )

                try:
                    page = context.pages[0] if context.pages else context.new_page()

                    # Lắng nghe sự kiện download qua browser
                    def on_download(download):
                        nonlocal downloaded_file
                        clean_name = download.suggested_filename.replace(" ", "_")
                        dest_filename = f"flow_real_ai_{uuid.uuid4().hex[:8]}_{clean_name}"
                        dest_path = target_dir / dest_filename
                        download.save_as(str(dest_path))
                        downloaded_file = dest_path
                        print(f"[GOOGLE FLOW] Đã nhận file qua browser: {dest_path.name} ({dest_path.stat().st_size} bytes)", flush=True)

                    page.on("download", on_download)

                    # Lắng nghe network responses từ Google Flow
                    def on_response(response):
                        nonlocal captured_media_name, is_generation_complete
                        try:
                            url = response.url
                            if "batchAsyncGenerateVideo" in url:
                                body = response.json()
                                media_list = body.get("media", [])
                                if media_list and isinstance(media_list, list):
                                    captured_media_name = media_list[0].get("name")
                                    print(f"[GOOGLE FLOW NETWORK] Media task: {captured_media_name}", flush=True)
                                else:
                                    print(f"[GOOGLE FLOW NETWORK] Phản hồi tạo video không có media (HTTP {response.status}).", flush=True)
                            elif "batchCheckAsyncVideoGenerationStatus" in url:
                                body = response.json()
                                media_items = body.get("media", [])
                                seen_statuses = []
                                for item in media_items:
                                    status_obj = item.get("mediaMetadata", {}).get("mediaStatus", {})
                                    gen_status = status_obj.get("mediaGenerationStatus")
                                    if gen_status:
                                        seen_statuses.append(gen_status)
                                    if gen_status in ("MEDIA_GENERATION_STATUS_SUCCESSFUL", "SUCCESSFUL"):
                                        is_generation_complete = True
                                        print("[GOOGLE FLOW NETWORK] Video hoàn tất render trên Google Cloud!", flush=True)
                                if not is_generation_complete and seen_statuses:
                                    print(f"[GOOGLE FLOW NETWORK] Trạng thái render: {', '.join(seen_statuses[-3:])}", flush=True)
                        except Exception as response_err:
                            if "batchAsyncGenerateVideo" in response.url or "batchCheckAsyncVideoGenerationStatus" in response.url:
                                print(f"[GOOGLE FLOW NETWORK] Không đọc được trạng thái phản hồi ({type(response_err).__name__}).", flush=True)

                    page.on("response", on_response)

                    # Mở Google Flow với domcontentloaded để không bị timeout bởi heavy streaming
                    page.goto(GOOGLE_FLOW_URL, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(4000)

                    # Kiểm tra trạng thái đăng nhập
                    is_logged_in = "accounts.google.com" not in page.url and "/about" not in page.url
                    if not is_logged_in and "/about" in page.url:
                        create_landing_btn = page.locator("text='Create with Google Flow'").first
                        if create_landing_btn.count() > 0:
                            create_landing_btn.click()
                            page.wait_for_timeout(3000)
                        is_logged_in = "accounts.google.com" not in page.url and "/about" not in page.url

                    if not is_logged_in:
                        raise FlowLoginRequired(
                            "Chưa phát hiện phiên đăng nhập Google AI Pro trong Flow Profile. "
                            "Vui lòng chạy '00_DANG_NHAP_GOOGLE_FLOW.cmd' một lần để đăng nhập."
                        )

                    # 1. Điều hướng vào dự án
                    if "/project/" not in page.url:
                        project_link = page.locator("a[href*='/project/']").first
                        if project_link.count() > 0:
                            project_link.click()
                            page.wait_for_timeout(4000)
                        else:
                            new_proj_btn = page.locator("button:has-text('Start Creating'), button:has-text('Dự án mới')").first
                            if new_proj_btn.count() > 0:
                                new_proj_btn.click()
                                page.wait_for_timeout(4000)

                    if start_image_path:
                        self._ensure_video_mode(page)
                        self._attach_start_image(page, start_image_path, timeout_sec)

                    # 2. Nhập bộ lệnh video vào ProseMirror editor (ô hiển thị đầu tiên)
                    input_box = page.locator(
                        'div[role="textbox"][data-slate-editor="true"], '
                        'div.ProseMirror[contenteditable="true"]'
                    ).first
                    try:
                        input_box.wait_for(state="visible", timeout=20000)
                    except Exception as editor_err:
                        raise RuntimeError(
                            f"Không tìm thấy khung soạn thảo văn bản trên giao diện Google Flow (URL: {page.url})."
                        ) from editor_err
                    input_box.click()
                    page.wait_for_timeout(500)
                    input_box.fill(clean_prompt)
                    page.wait_for_timeout(1000)

                    # Bấm nút Bắt đầu tạo (Submit button)
                    gen_btn = page.locator('button[aria-label="Bắt đầu tạo"], button[type="submit"]:has(i:text("arrow_forward")), button[type="submit"]:has(mat-icon:has-text("arrow_forward"))').last
                    if gen_btn.count() > 0 and gen_btn.is_enabled():
                        gen_btn.click()
                        print("[GOOGLE FLOW] Đã gửi bộ lệnh sang Google Flow AI qua nút 'Bắt đầu tạo'.", flush=True)
                    else:
                        input_box.press("Enter")
                        print("[GOOGLE FLOW] Đã gửi bộ lệnh sang Google Flow AI qua phím Enter.", flush=True)

                    # 3. Theo dõi tiến trình render và tải video 10s
                    print(f"[GOOGLE FLOW] Đang theo dõi máy chủ Google render video 10s (timeout={timeout_sec}s)...", flush=True)
                    start_time = time.time()

                    while time.time() - start_time < timeout_sec:
                        page.wait_for_timeout(POLL_INTERVAL_SEC * 1000)

                        if downloaded_file and downloaded_file.exists() and downloaded_file.stat().st_size > 100000:
                            break

                        # TỰ ĐỘNG PHÊ DUYỆT TÍN DỤNG (Nếu Flow hiển thị thông báo hỏi xác nhận)
                        active_approval = page.locator('div[role="radio"]:not(.read-only):has-text("Luôn phê duyệt"), div[role="radio"]:not(.read-only):has-text("Phê duyệt")').last
                        if active_approval.count() > 0 and active_approval.is_visible():
                            try:
                                active_approval.click()
                                print("[GOOGLE FLOW] Đã tự động nhấn 'Luôn phê duyệt' để Flow bắt đầu render!", flush=True)
                            except Exception:
                                pass

                        # Kiểm tra xem có video đã hoàn tất trên canvas chưa (qua ảnh thumbnail + biểu tượng play)
                        thumbs = page.locator("img.thumbnail").all()
                        play_icons = page.locator("mat-icon:has-text('play_circle')").all()
                        if len(thumbs) > 0 and len(play_icons) > 0:
                            try:
                                # Nhấn vào thumbnail để mở viewer
                                thumbs[0].click(force=True, timeout=3000)
                                page.wait_for_timeout(1500)

                                # Tìm nút download trong viewer
                                dl_trigger = page.locator("button[aria-label*='Tải'], button[aria-label*='Download']").first
                                if dl_trigger.count() > 0 and dl_trigger.is_visible():
                                    dl_trigger.click(timeout=3000)
                                    page.wait_for_timeout(800)

                                    # Chọn 720p gốc
                                    opt_720p = page.locator("[role='menuitem']:has-text('720p'), .mat-mdc-menu-item:has-text('720p')").first
                                    if opt_720p.count() > 0:
                                        with page.expect_download(timeout=60000) as download_info:
                                            opt_720p.click()
                                        dl = download_info.value
                                        clean_sugg = dl.suggested_filename.replace(" ", "_")
                                        dest_path = target_dir / f"flow_omni_10s_{uuid.uuid4().hex[:8]}_{clean_sugg}"
                                        dl.save_as(str(dest_path))
                                        downloaded_file = dest_path
                                        print(f"[GOOGLE FLOW THÀNH CÔNG] Đã tải video MP4 10s thật: {dest_path.name} ({dest_path.stat().st_size} bytes)", flush=True)
                                        break
                            except Exception as dl_err:
                                pass

                        # Direct TRPC redirect fallback nếu có media_name
                        if is_generation_complete and captured_media_name and not downloaded_file:
                            try:
                                dl_url = self._media_redirect_url(captured_media_name)
                                dest_path = target_dir / f"flow_omni_10s_{uuid.uuid4().hex[:8]}.mp4"
                                resp = context.request.get(dl_url)
                                if resp.ok and len(resp.body()) > 100000:
                                    dest_path.write_bytes(resp.body())
                                    downloaded_file = dest_path
                                    print(f"[GOOGLE FLOW THÀNH CÔNG] Đã tải video thật 10s từ Cloud: {dest_path.name}", flush=True)
                                    break
                                print(f"[GOOGLE FLOW DOWNLOAD] Không tải được media {captured_media_name}: HTTP {resp.status}, {resp.text()[:300]}", flush=True)
                            except Exception as dl_err:
                                print(f"[GOOGLE FLOW DOWNLOAD] Lỗi tải media {captured_media_name}: {dl_err}", flush=True)

                    if not downloaded_file or not downloaded_file.exists() or downloaded_file.stat().st_size < 100000:
                        raise RuntimeError(
                            f"FLOW_DOWNLOAD_TIMEOUT: Flow chưa chuyển được video về hệ thống trong {timeout_sec}s. "
                            "Video có thể đã tạo xong trong Flow nhưng bước tự động tải hoặc nhận kết quả bị lỗi; kiểm tra log Google Flow trước khi tạo lại."
                        )

                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
                    # Đồng bộ cookie/session mới nhất về NAS để backup an toàn
                    try:
                        sync_local_to_nas(LOCAL_BROWSER_PROFILE_DIR, BROWSER_PROFILE_DIR)
                    except Exception:
                        pass

            data = downloaded_file.read_bytes()
            sha256_hash = hashlib.sha256(data).hexdigest()
            byte_size = len(data)

            duration_ms = 10000
            try:
                probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(downloaded_file)]
                out = subprocess.check_output(probe_cmd, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
                if out:
                    duration_ms = int(float(out) * 1000)
            except Exception:
                pass

            return {
                "status": "SUCCEEDED",
                "provider": "GOOGLE_FLOW",
                "source_product": "GOOGLE_FLOW_OMNI",
                "filename": downloaded_file.name,
                "storage_path": str(downloaded_file),
                "relative_storage_key": f"workspaces/{workspace_id}/media/{downloaded_file.name}",
                "sha256": sha256_hash,
                "byte_size": byte_size,
                "mime_detected": "video/mp4",
                "duration_ms": duration_ms,
                "aspect_ratio": "16:9",
                "actual_cost": 0.0,
                "cost_currency": "USD",
                "credits_source": "GOOGLE_FLOW_PRO"
            }

    @staticmethod
    def _ensure_video_mode(page) -> None:
        page.locator(
            'div[role="textbox"][data-slate-editor="true"], '
            'div.ProseMirror[contenteditable="true"]'
        ).first.wait_for(state="visible", timeout=20000)
        trigger = page.locator(
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_16_9')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_9_16')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_square')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_portrait')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_landscape')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_original'))"
        ).first
        if trigger.count() == 0:
            raise RuntimeError("Google Flow chưa sẵn sàng trình chỉnh sửa video.")
        trigger.click(timeout=5000)
        page.wait_for_timeout(800)
        video_tab = page.locator(
            "[role='tab'][id$='-trigger-VIDEO'], "
            "[role='tab'][aria-controls$='-content-VIDEO'], "
            "[role='menu'] [role='tab']:has(i:text('play_circle')), "
            "[role='menu'] [role='tab']:has-text('Video'), "
            "[role='menu'] [role='tab']:has-text('Vídeo')"
        ).first
        if video_tab.count() == 0:
            raise RuntimeError("Google Flow không hiển thị lựa chọn chế độ Video.")
        video_tab.click(timeout=5000)
        page.wait_for_timeout(1200)

    @staticmethod
    def _attach_start_image(page, image_path: pathlib.Path, timeout_sec: int) -> None:
        if not image_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy ảnh tham chiếu: {image_path}")

        slots = page.locator(
            "div[type='button'][aria-haspopup='dialog'], button[aria-haspopup='dialog'], "
            "[role='button'][aria-haspopup='dialog']"
        )
        slot_count = slots.count()
        if slot_count == 0:
            raise RuntimeError("Google Flow không hiển thị ô ảnh khung hình đầu.")
        slots.first.click(timeout=5000)
        page.wait_for_timeout(1000)

        upload_buttons = (
            "[role='dialog'][data-state='open'] button:has(i.google-symbols:text-is('upload'))",
            "[role='dialog'][data-state='open'] button:has-text('Upload media')",
        )
        chooser = None
        for selector in upload_buttons:
            try:
                with page.expect_file_chooser(timeout=8000) as chooser_info:
                    page.locator(selector).first.click(timeout=4000)
                chooser = chooser_info.value
                break
            except Exception:
                continue
        if chooser is None:
            raise RuntimeError("Không mở được hộp thoại tải ảnh tham chiếu lên Google Flow.")

        with page.expect_response(lambda response: "uploadImage" in response.url, timeout=timeout_sec * 1000) as upload_info:
            chooser.set_files(str(image_path))
        if not upload_info.value.ok:
            raise RuntimeError(f"Google Flow từ chối ảnh tham chiếu (HTTP {upload_info.value.status}).")

        dialog = page.locator("[role='dialog'][data-state='open']").last
        add_button = dialog.locator("button").filter(has_not=page.locator("i.google-symbols")).last
        if add_button.count() == 0:
            raise RuntimeError("Không tìm thấy nút xác nhận ảnh tham chiếu trong Google Flow.")
        add_button.click(timeout=5000)
        dialog.wait_for(state="hidden", timeout=15000)
        page.wait_for_timeout(1000)
        if page.locator(
            "div[type='button'][aria-haspopup='dialog'], button[aria-haspopup='dialog'], "
            "[role='button'][aria-haspopup='dialog']"
        ).count() >= slot_count:
            raise RuntimeError("Google Flow chưa gắn ảnh vào khung hình đầu; đã hủy yêu cầu tạo video.")
