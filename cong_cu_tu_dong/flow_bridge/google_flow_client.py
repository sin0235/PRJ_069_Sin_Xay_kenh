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
import re
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional
from urllib.parse import quote, urlsplit

CURRENT_DIR = pathlib.Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from config import (
    BROWSER_CHANNEL,
    DEFAULT_TIMEOUT_MS,
    GOOGLE_FLOW_URL,
    MEDIA_ASSETS_DIR,
    POLL_INTERVAL_SEC,
    browser_launch_args,
    get_current_browser_profile_dir,
    sync_browser_profile,
)
from profile_guard import ensure_profile_free, profile_locked
from session_manager import (
    FlowLoginRequired,
    FlowQuotaExceeded,
    FlowSubmissionNotSent,
    _login_prompt_visible,
    _quota_visible,
    _visible,
    classify_provider_state,
)
from src.modules.flow_sessions.context import (
    assert_flow_profile_workspace,
    current_flow_profile,
    flow_profile_metadata,
    validate_flow_project_url,
)

_FLOW_MUTEX = threading.Lock()
_FLOW_PROJECT_TIMEOUT_MS = 120_000
_FLOW_PROJECT_RETRIES = 1


def _has_successful_generation(media_items: list[dict], media_name: str) -> bool:
    return any(
        item.get("name") == media_name
        and item.get("mediaMetadata", {}).get("mediaStatus", {}).get("mediaGenerationStatus")
        in ("MEDIA_GENERATION_STATUS_SUCCESSFUL", "SUCCESSFUL")
        for item in media_items
    )


def _new_flow_prompt_bubble_index(bubble_texts: list[str], existing_count: int, prompt: str) -> Optional[int]:
    prompt = " ".join(prompt.split())
    return next(
        (index for index, text in enumerate(bubble_texts[existing_count:], existing_count)
         if prompt in " ".join(text.split())),
        None,
    )


def _new_flow_video_tile_index(existing_sources: list[str], current_sources: list[str]) -> Optional[int]:
    return next((index for index, source in enumerate(current_sources) if source and source not in existing_sources), None)


class GoogleFlowClient:
    """Client tự động hóa Google Flow qua giao diện web với hồ sơ người dùng cục bộ."""

    def __init__(self, headless: bool = True):
        self.headless = headless

    @staticmethod
    def _flow_page_state(page) -> str:
        flow_ready = _visible(page, "button:has-text('New project'), button:has-text('Dự án mới')")
        if "/project/" in page.url:
            flow_ready = flow_ready or _visible(page, "[role='textbox']")
        return classify_provider_state(
            page.url,
            authenticated=flow_ready,
            login_required=_login_prompt_visible(page),
            quota_limited=_quota_visible(page),
        )

    @staticmethod
    def _goto_flow_page(page, url: str) -> None:
        for attempt in range(_FLOW_PROJECT_RETRIES + 1):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=_FLOW_PROJECT_TIMEOUT_MS)
                return
            except PlaywrightTimeoutError:
                current = urlsplit(page.url)
                target = urlsplit(url)
                if (current.scheme, current.netloc, current.path) == (target.scheme, target.netloc, target.path):
                    return
                if attempt == _FLOW_PROJECT_RETRIES:
                    raise

    @staticmethod
    def _open_flow_project(page, project_url: Optional[str] = None) -> str:
        if project_url:
            try:
                validate_flow_project_url(project_url)
            except ValueError as exc:
                raise RuntimeError("FLOW_PROJECT_URL_INVALID") from exc
            if "/project/" not in urlsplit(project_url).path:
                raise RuntimeError("FLOW_PROJECT_URL_INVALID")
            GoogleFlowClient._goto_flow_page(page, project_url)
        else:
            GoogleFlowClient._goto_flow_page(page, GOOGLE_FLOW_URL)
            new_project = page.locator(
                "button:has-text('New project'), button:has-text('Dự án mới')"
            ).first
            for attempt in range(_FLOW_PROJECT_RETRIES + 1):
                try:
                    new_project.wait_for(state="visible", timeout=_FLOW_PROJECT_TIMEOUT_MS)
                    break
                except PlaywrightTimeoutError as exc:
                    if attempt == _FLOW_PROJECT_RETRIES:
                        raise RuntimeError("FLOW_NEW_PROJECT_BUTTON_UNAVAILABLE") from exc
                    GoogleFlowClient._goto_flow_page(page, GOOGLE_FLOW_URL)
            new_project.click(timeout=_FLOW_PROJECT_TIMEOUT_MS)
            for attempt in range(_FLOW_PROJECT_RETRIES + 1):
                try:
                    page.wait_for_url("**/project/**", timeout=_FLOW_PROJECT_TIMEOUT_MS)
                    break
                except PlaywrightTimeoutError as exc:
                    if "/project/" in urlsplit(page.url).path:
                        break
                    if attempt == _FLOW_PROJECT_RETRIES:
                        raise RuntimeError("FLOW_NEW_PROJECT_INIT_TIMEOUT: Google Flow chưa mở project sau hai lần chờ, mỗi lần 120 giây.") from exc

        project_url = page.url.split("/edit/", 1)[0].rstrip("/")
        try:
            validate_flow_project_url(project_url)
        except ValueError as exc:
            raise RuntimeError("FLOW_PROJECT_URL_INVALID") from exc
        if page.url.rstrip("/") != project_url:
            GoogleFlowClient._goto_flow_page(page, project_url)
        return project_url

    @staticmethod
    def _media_redirect_url(media_name: str) -> str:
        flow_input = json.dumps({"json": {"name": media_name}}, separators=(",", ":"))
        return "https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?input=" + quote(flow_input, safe="")

    @staticmethod
    def _download_current_flow_video(page, target_dir: pathlib.Path) -> pathlib.Path:
        download_button = page.get_by_role("button", name="Tải nội dung nghe nhìn xuống")
        download_button.wait_for(state="visible", timeout=15000)
        deadline = time.monotonic() + 120
        while not download_button.is_enabled() and time.monotonic() < deadline:
            page.wait_for_timeout(1000)
        if not download_button.is_enabled():
            raise RuntimeError("FLOW_VIDEO_NOT_READY: Flow chưa bật nút tải cho video vừa tạo.")
        download_button.click(timeout=10000)
        quality = page.locator("[role='menuitem']:has-text('720p')").first
        quality.wait_for(state="visible", timeout=10000)
        with page.expect_download(timeout=90000) as download_info:
            quality.click(timeout=10000)
        download = download_info.value
        filename = download.suggested_filename.replace(" ", "_")
        path = target_dir / f"flow_omni_10s_{uuid.uuid4().hex[:8]}_{filename}"
        download.save_as(str(path))
        print(f"[GOOGLE FLOW DOWNLOAD] Đã tải video mới từ Flow: {path.name} ({path.stat().st_size} bytes)", flush=True)
        return path

    @staticmethod
    def _download_flow_video_card(page, video_card, target_dir: pathlib.Path) -> pathlib.Path:
        video_card.click(timeout=15000)
        page.wait_for_url("**/edit/**", timeout=20000)
        return GoogleFlowClient._download_current_flow_video(page, target_dir)

    @profile_locked(get_current_browser_profile_dir)
    def create_video(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        workspace_id: str = "default_ws",
        timeout_sec: int = 240,
        start_image_path: Optional[pathlib.Path] = None,
        flow_project_url: Optional[str] = None,
        on_flow_project_created: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Tạo video theo tỷ lệ được chọn, chờ Flow hoàn tất rồi tải MP4 về.
        """
        if aspect_ratio not in {"9:16", "16:9"}:
            raise ValueError(f"FLOW_ASPECT_RATIO_UNSUPPORTED: {aspect_ratio}")
        assert_flow_profile_workspace(workspace_id)
        selected_profile = current_flow_profile()
        flow_project_url = flow_project_url or (selected_profile.project_url if selected_profile else None)
        with _FLOW_MUTEX:
            # The profile lives on the persistent volume; never copy its cookies to another home directory.
            profile_dir = sync_browser_profile()
            ensure_profile_free(profile_dir)

            clean_prompt = prompt.strip()
            print(f"[GOOGLE FLOW OMNI] Bắt đầu tạo video 10s: '{clean_prompt[:70]}...'", flush=True)

            target_dir = MEDIA_ASSETS_DIR / "workspaces" / workspace_id / "media"
            target_dir.mkdir(parents=True, exist_ok=True)

            downloaded_file: Optional[pathlib.Path] = None
            captured_media_name: Optional[str] = None
            is_generation_complete: bool = False
            generation_submitted = False
            generation_response_received = False
            quota_limited = False

            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    channel=BROWSER_CHANNEL,
                    headless=self.headless,
                    viewport={"width": 1400, "height": 900},
                    args=browser_launch_args(),
                    downloads_path=str(target_dir),
                    accept_downloads=True
                )

                try:
                    page = context.pages[0] if context.pages else context.new_page()

                    # Lắng nghe network responses từ Google Flow
                    def on_response(response):
                        nonlocal captured_media_name, is_generation_complete, generation_response_received, quota_limited
                        try:
                            url = response.url
                            if "batchAsyncGenerateVideo" in url:
                                if not generation_submitted:
                                    return
                                generation_response_received = True
                                if response.status == 429:
                                    quota_limited = True
                                    return
                                body = response.json()
                                response_text = json.dumps(body).lower()
                                if any(marker in response_text for marker in ("quota exceeded", "out of credits", "daily limit")):
                                    quota_limited = True
                                    return
                                media_list = body.get("media", [])
                                if media_list and isinstance(media_list, list):
                                    captured_media_name = media_list[0].get("name")
                                    print(f"[GOOGLE FLOW NETWORK] Media task: {captured_media_name}", flush=True)
                                else:
                                    print(f"[GOOGLE FLOW NETWORK] Phản hồi tạo video không có media (HTTP {response.status}).", flush=True)
                            elif "batchCheckAsyncVideoGenerationStatus" in url:
                                if not generation_submitted or not captured_media_name:
                                    return
                                body = response.json()
                                media_items = body.get("media", [])
                                seen_statuses = []
                                for item in media_items:
                                    status_obj = item.get("mediaMetadata", {}).get("mediaStatus", {})
                                    gen_status = status_obj.get("mediaGenerationStatus")
                                    if gen_status:
                                        seen_statuses.append(gen_status)
                                    if _has_successful_generation([item], captured_media_name):
                                        is_generation_complete = True
                                        print("[GOOGLE FLOW NETWORK] Video hoàn tất render trên Google Cloud!", flush=True)
                                if not is_generation_complete and seen_statuses:
                                    print(f"[GOOGLE FLOW NETWORK] Trạng thái render: {', '.join(seen_statuses[-3:])}", flush=True)
                        except Exception as response_err:
                            if "batchAsyncGenerateVideo" in response.url or "batchCheckAsyncVideoGenerationStatus" in response.url:
                                print(f"[GOOGLE FLOW NETWORK] Không đọc được trạng thái phản hồi ({type(response_err).__name__}).", flush=True)

                    page.on("response", on_response)

                    def approve_pending_generation() -> None:
                        active_approval = page.locator(
                            'div[role="radio"]:not(.read-only):has-text("Luôn phê duyệt"), '
                            'div[role="radio"]:not(.read-only):has-text("Phê duyệt")'
                        ).last
                        if (
                            active_approval.count() > 0
                            and active_approval.is_visible()
                            and active_approval.is_enabled()
                        ):
                            active_approval.click()
                            print("[GOOGLE FLOW] Đã duyệt xác nhận tạo video trong request này.", flush=True)

                    # Mở Google Flow với domcontentloaded để không bị timeout bởi heavy streaming
                    self._goto_flow_page(page, GOOGLE_FLOW_URL)
                    page.wait_for_timeout(4000)

                    # A missing sign-in prompt is not evidence that this profile is authenticated.
                    provider_state = self._flow_page_state(page)
                    if provider_state == "UNKNOWN" and "/about" in page.url:
                        create_landing_btn = page.locator("text='Create with Google Flow'").first
                        if create_landing_btn.count() > 0:
                            create_landing_btn.click()
                            page.wait_for_timeout(3000)
                        provider_state = self._flow_page_state(page)

                    if provider_state == "LOGIN_REQUIRED":
                        raise FlowLoginRequired(
                            "FLOW_LOGIN_REQUIRED: Google Flow needs a manual sign-in for this profile."
                        )
                    if provider_state == "QUOTA_LIMITED":
                        raise FlowQuotaExceeded("FLOW_QUOTA_LIMITED")
                    if provider_state != "READY":
                        raise RuntimeError("FLOW_PROVIDER_STATE_UNKNOWN")

                    requested_project_url = flow_project_url
                    flow_project_url = self._open_flow_project(page, flow_project_url)
                    if not requested_project_url and on_flow_project_created:
                        on_flow_project_created(flow_project_url)

                    self._ensure_video_mode(page, aspect_ratio)
                    if start_image_path:
                        self._attach_start_image(page, start_image_path, timeout_sec)

                    flow_bubbles = page.locator("flow-chat-bubble")
                    existing_flow_bubble_count = flow_bubbles.count()
                    flow_tile_grid = page.locator(".tiles-container")
                    if flow_tile_grid.count():
                        flow_tile_grid.evaluate("element => { element.scrollTop = element.scrollHeight; }")
                        page.wait_for_timeout(750)
                        flow_tile_grid.evaluate("element => { element.scrollTop = 0; }")
                    flow_tiles = page.locator("flow-grid-tile-container:has(flow-video-tile)")
                    existing_flow_video_sources = []
                    stable_reads = 0
                    for _ in range(12):
                        current_sources = flow_tiles.locator("img.thumbnail").evaluate_all(
                            "images => images.map(image => image.currentSrc || image.src).filter(Boolean)"
                        )
                        stable_reads = stable_reads + 1 if current_sources == existing_flow_video_sources else 0
                        existing_flow_video_sources = current_sources
                        if stable_reads >= 5:
                            break
                        page.wait_for_timeout(500)

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
                    credit_warning = page.locator(
                        "button[aria-label*='không đủ tín dụng'], button:has-text('không đủ tín dụng')"
                    ).first
                    if credit_warning.count() and credit_warning.is_visible():
                        raise RuntimeError(
                            "FLOW_CREDITS_INSUFFICIENT: Google Flow báo không đủ tín dụng; shot chưa được gửi."
                        )
                    gen_btn = page.get_by_role("button", name="Bắt đầu tạo")
                    if gen_btn.count() == 0 or not gen_btn.is_enabled():
                        raise RuntimeError(
                            "FLOW_SUBMIT_BUTTON_UNAVAILABLE: Không tìm thấy nút 'Bắt đầu tạo' đang bật sau khi nhập prompt."
                        )
                    generation_submitted = True
                    gen_btn.click()
                    print("[GOOGLE FLOW] Đã bấm nút 'Bắt đầu tạo'. Đang xác nhận phản hồi của Flow...", flush=True)
                    approve_pending_generation()

                    response_deadline = time.monotonic() + timeout_sec
                    new_video_card = None
                    prompt_bubble_confirmed = False
                    while time.monotonic() < response_deadline:
                        page.wait_for_timeout(500)
                        approve_pending_generation()
                        bubble_texts = flow_bubbles.all_text_contents()
                        prompt_bubble_index = _new_flow_prompt_bubble_index(
                            bubble_texts, existing_flow_bubble_count, clean_prompt
                        )
                        if prompt_bubble_index is not None:
                            if not prompt_bubble_confirmed:
                                print("[GOOGLE FLOW] Đã xác nhận Flow nhận prompt mới của request này.", flush=True)
                                prompt_bubble_confirmed = True
                            card_selector = "[role='button'][aria-label='Mở video trong trình chỉnh sửa']"
                            for bubble_index in range(prompt_bubble_index + 1, len(bubble_texts)):
                                cards = flow_bubbles.nth(bubble_index).locator(card_selector)
                                if cards.count():
                                    new_video_card = cards.first
                                    print("[GOOGLE FLOW] Đã có video card thuộc bubble prompt mới.", flush=True)
                                    break
                        if new_video_card is None:
                            current_sources = flow_tiles.locator("img.thumbnail").evaluate_all(
                                "images => images.map(image => image.currentSrc || image.src).filter(Boolean)"
                            )
                            tile_index = _new_flow_video_tile_index(existing_flow_video_sources, current_sources)
                            if tile_index is not None:
                                new_video_card = flow_tiles.nth(tile_index)
                                print("[GOOGLE FLOW] Đã nhận thẻ video mới từ giao diện Flow.", flush=True)
                        if new_video_card is not None or (generation_response_received and captured_media_name):
                            break
                    if new_video_card is not None:
                        downloaded_file = self._download_flow_video_card(page, new_video_card, target_dir)
                        is_generation_complete = True
                    elif not generation_response_received or not captured_media_name:
                        raise RuntimeError(
                            "FLOW_SUBMIT_NOT_CONFIRMED: Google Flow không trả media ID cho yêu cầu vừa gửi; "
                            "không có thẻ video mới để tải; không lấy lại video cũ làm kết quả."
                        )

                    # 3. Theo dõi tiến trình render và tải video 10s
                    print(f"[GOOGLE FLOW] Đang theo dõi máy chủ Google render video 10s (timeout={timeout_sec}s)...", flush=True)
                    start_time = time.time()

                    while time.time() - start_time < timeout_sec:
                        page.wait_for_timeout(POLL_INTERVAL_SEC * 1000)

                        if quota_limited:
                            raise FlowQuotaExceeded("FLOW_QUOTA_LIMITED", submitted=True)

                        if downloaded_file and downloaded_file.exists() and downloaded_file.stat().st_size > 100000:
                            break

                        # Flow can request confirmation after returning the media ID too.
                        try:
                            approve_pending_generation()
                        except Exception:
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

                except (FlowLoginRequired, FlowQuotaExceeded):
                    raise
                except Exception as exc:
                    if not generation_submitted:
                        raise FlowSubmissionNotSent(str(exc)) from exc
                    raise
                finally:
                    try:
                        context.close()
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
                **flow_profile_metadata(flow_project_url),
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
                "aspect_ratio": aspect_ratio,
                "actual_cost": 0.0,
                "cost_currency": "USD",
                "credits_source": "GOOGLE_FLOW_PRO"
            }

    @staticmethod
    def _ensure_video_mode(page, aspect_ratio: str = "16:9") -> None:
        agent_toggle = page.locator("button.agent-mode-chip")
        if agent_toggle.count():
            agent_toggle.wait_for(state="visible", timeout=_FLOW_PROJECT_TIMEOUT_MS)
        if agent_toggle.count() and agent_toggle.get_attribute("aria-pressed") == "true":
            agent_toggle.click(timeout=5000)

        generation_settings = page.locator(
            "button.settings-trigger-button, button[aria-label*='settings']"
        ).first
        try:
            generation_settings.wait_for(state="visible", timeout=_FLOW_PROJECT_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass
        if not generation_settings.count():
            generation_settings = page.locator(
                "button:has-text('Nano Banana'), button:has-text('Video'), button:has-text('Veo')"
            ).first
        model_button_count = page.locator(
            "button:has-text('Nano Banana'),button:has-text('Video'),button:has-text('Veo')"
        ).count()
        textbox_count = page.locator('[role="textbox"]').count()
        print(
            "[FLOW MODE] "
            f"agent={agent_toggle.count()}:{agent_toggle.get_attribute('aria-pressed') if agent_toggle.count() else 'missing'} "
            f"settings={generation_settings.count()} "
            f"model_buttons={model_button_count} textboxes={textbox_count}",
            flush=True,
        )
        if generation_settings.count() and generation_settings.is_visible():
            generation_settings.click(timeout=5000)
            page.get_by_role("radio", name="Video", exact=True).click(timeout=5000)
            page.get_by_role("radio", name=aspect_ratio, exact=True).click(timeout=5000)
            page.get_by_role("radio", name=re.compile(r"^\s*10\b", re.I)).click(timeout=5000)
            page.keyboard.press("Escape")
            page.get_by_role("radio", name="Video", exact=True).wait_for(state="hidden", timeout=5000)
            return

        editor = page.locator(
            'div[role="textbox"][data-slate-editor="true"], '
            'div.ProseMirror[contenteditable="true"]'
        ).first
        for attempt in range(_FLOW_PROJECT_RETRIES + 1):
            try:
                editor.wait_for(state="visible", timeout=_FLOW_PROJECT_TIMEOUT_MS)
                break
            except PlaywrightTimeoutError as exc:
                if attempt == _FLOW_PROJECT_RETRIES:
                    raise RuntimeError("FLOW_PROJECT_EDITOR_INIT_TIMEOUT: Trình chỉnh sửa Flow chưa sẵn sàng sau hai lần chờ, mỗi lần 120 giây.") from exc
                project_url = page.url.split("/edit/", 1)[0].rstrip("/")
                GoogleFlowClient._goto_flow_page(page, project_url)
        trigger = page.locator(
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_16_9')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_9_16')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_square')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_portrait')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_landscape')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_original'))"
        ).first
        if trigger.count() == 0:
            agent_settings = page.locator(
                "button.agent-action-button[aria-label='Settings'], "
                "button.agent-action-button[aria-label='Cài đặt']"
            ).first
            if aspect_ratio == "16:9" and agent_settings.count() and agent_settings.is_visible():
                return
            raise RuntimeError(
                "FLOW_VIDEO_MODE_SELECTOR_NOT_FOUND: "
                f"agent={agent_toggle.count()} "
                f"settings={generation_settings.count()} "
                f"model_buttons={model_button_count} "
                f"textboxes={textbox_count}"
            )
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
        trigger = page.locator(
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_16_9')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_9_16')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_square')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_portrait')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_landscape')), "
            "button[aria-haspopup='menu']:has(i.google-symbols:text('crop_original'))"
        ).first
        if trigger.count() == 0:
            raise RuntimeError("FLOW_ASPECT_RATIO_UNAVAILABLE: KhÃ´ng tÃ¬m tháº¥y bá»™ chá»n khung hÃ¬nh.")
        trigger.click(timeout=5000)
        aspect_tab_selector = (
            "[role='menu'] [role='tab'][id$='-trigger-PORTRAIT'], "
            "[role='menu'] [role='tab']:has(i.google-symbols:text-is('crop_9_16'))"
            if aspect_ratio == "9:16" else
            "[role='menu'] [role='tab'][id$='-trigger-LANDSCAPE'], "
            "[role='menu'] [role='tab']:has(i.google-symbols:text-is('crop_16_9'))"
        )
        aspect_tab = page.locator(aspect_tab_selector).first
        if aspect_tab.count() == 0:
            raise RuntimeError(f"FLOW_ASPECT_RATIO_UNAVAILABLE: Flow khÃ´ng hiá»ƒn thá»‹ lá»±a chá»n {aspect_ratio}.")
        aspect_tab.click(timeout=5000)
        page.wait_for_timeout(800)

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
            add_media = page.locator(
                "button[aria-label='Thêm thành phần vào ô nhập câu lệnh'], "
                "button[aria-label='Add content to prompt']"
            ).first
            if not add_media.count():
                raise RuntimeError("Google Flow không hiển thị chỗ thêm ảnh tham chiếu.")
            add_media.click(timeout=5000)
            page.wait_for_timeout(500)
            image_item = page.locator("[role='option']").filter(has_text=image_path.stem).last
            if image_item.count() == 0:
                upload_button = page.locator("button.sidebar-upload-btn")
                upload_button.wait_for(state="visible", timeout=15000)
                with page.expect_file_chooser(timeout=8000) as chooser_info:
                    upload_button.first.click(timeout=5000)
                chooser_info.value.set_files(str(image_path))
                # Flow asks the uploader to confirm usage rights before it lists the image.
                consent = page.get_by_role("dialog").get_by_role("button", name=re.compile(r"^(Tôi đồng ý|I agree)$"))
                try:
                    consent.first.wait_for(state="visible", timeout=8000)
                    consent.first.click(timeout=5000)
                except PlaywrightTimeoutError:
                    pass
            image_item.wait_for(state="visible", timeout=30000)
            image_item.click(timeout=5000)
            attached = page.locator(
                "flow-base-prompt-box button.chip-container, button:has-text('Thành phần')"
            ).first
            if attached.count() == 0:
                try:
                    attached.wait_for(state="visible", timeout=1500)
                except Exception:
                    add_button = page.get_by_role("button", name="Thêm vào câu lệnh")
                    if add_button.count() == 0:
                        add_button = page.get_by_role("button", name="Add to prompt")
                    try:
                        add_button.click(timeout=5000, force=True)
                    except Exception:
                        if attached.count() == 0:
                            raise
            attached.wait_for(state="visible", timeout=15000)
            page.keyboard.press("Escape")
            page.locator(".cdk-overlay-backdrop-showing").wait_for(state="hidden", timeout=5000)
            page.wait_for_timeout(500)
            return
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
