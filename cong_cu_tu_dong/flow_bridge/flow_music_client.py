# -*- coding: utf-8 -*-
"""Client điều khiển tự động Flow Music Plus (0đ chi phí - 10.000 credits/tháng).
Sử dụng Playwright với hồ sơ đã đăng nhập sẵn để sinh bài hát thật qua Flow Music (Lyria 3.5)
và tải MP3 chuẩn TikTok (-14 LUFS) về media_assets.
"""

import hashlib
import os
import pathlib
import subprocess
import sys
import time
import uuid
from typing import Dict, Any, Optional

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
    FLOW_MUSIC_URL,
    MEDIA_ASSETS_DIR,
    POLL_INTERVAL_SEC,
    sync_browser_profile,
)
from profile_guard import ensure_profile_free, profile_locked
from session_manager import FlowLoginRequired


class FlowMusicClient:
    def __init__(self, headless: bool = True):
        self.headless = headless

    @profile_locked(lambda: LOCAL_BROWSER_PROFILE_DIR)
    def create_track(
        self,
        prompt: str,
        title: str = "Tác phẩm Flow Music",
        lyrics: Optional[str] = None,
        genre: str = "Pop",
        mood: str = "Upbeat",
        workspace_id: str = "default_ws",
        timeout_sec: int = 150
    ) -> Dict[str, Any]:
        """
        Gửi yêu cầu tạo nhạc tới Flow Music Plus qua API thật, đợi render và tải tệp MP3:
        - Chi phí API bổ sung = 0.0$ (dùng 10.000 credits Pro có sẵn).
        - Chuẩn hóa âm lượng TikTok -14 LUFS.
        - Trả về thông tin tệp MP3 đã tải, mã băm SHA256 và đường dẫn lưu trữ.
        """
        print(f"[FLOW MUSIC] Khởi tạo tác vụ tạo nhạc: '{title}' ({genre} / {mood})")
        print(f"[FLOW MUSIC] Prompt: {prompt[:100]}...")

        # Thư mục đích lưu tệp media cho workspace
        target_dir = MEDIA_ASSETS_DIR / "workspaces" / workspace_id / "media"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Đồng bộ hồ sơ từ NAS về ổ cục bộ để tránh lỗi khóa ProcessSingleton SMB
        sync_browser_profile(BROWSER_PROFILE_DIR, LOCAL_BROWSER_PROFILE_DIR)
        ensure_profile_free(LOCAL_BROWSER_PROFILE_DIR)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(LOCAL_BROWSER_PROFILE_DIR),
                channel=BROWSER_CHANNEL,
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ]
            )

            # Bắt giữ Bearer Token từ các request API của Flow Music
            bearer_token = [None]

            def on_request(req):
                if "/__api/" in req.url and not bearer_token[0]:
                    auth = req.headers.get("authorization")
                    if auth and auth.startswith("Bearer "):
                        bearer_token[0] = auth

            page = context.new_page()
            page.on("request", on_request)
            page.goto(FLOW_MUSIC_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3500)

            token = bearer_token[0]
            if not token:
                for _ in range(5):
                    page.wait_for_timeout(1000)
                    token = bearer_token[0]
                    if token:
                        break

            if not token:
                context.close()
                raise FlowLoginRequired(
                    "[FLOW MUSIC AUTH ERROR] Không tìm thấy phiên đăng nhập hợp lệ tại flowmusic.app. "
                    "Vui lòng chạy 00_DANG_NHAP_GOOGLE_FLOW.cmd để đăng nhập tài khoản Google AI Pro."
                )

            # Sử dụng APIRequestContext để gọi REST endpoints không bị phụ thuộc vào DOM hay page lifecycle
            api = p.request.new_context()  # T?ch request kh?i v?ng ??i Edge khi ch? render.
            request_timeout_ms = max(timeout_sec, 30) * 1000
            headers = {
                "Authorization": token,
                "Content-Type": "application/json"
            }

            # 1. Tạo Project trên Flow Music
            full_prompt = f"{prompt}. Genre: {genre}. Mood: {mood}."
            if lyrics:
                full_prompt += f"\nLyrics:\n{lyrics}"

            project_title = f"{genre} ({mood}) - {title}"[:100]

            proj_resp = api.post(
                "https://www.flowmusic.app/__api/projects",
                headers=headers,
                data={"title": project_title, "description": full_prompt},
                timeout=request_timeout_ms
            )
            if proj_resp.status != 200:
                context.close()
                raise RuntimeError(f"[FLOW MUSIC ERROR] Không thể khởi tạo Project trên Flow Music ({proj_resp.status}): {proj_resp.text()[:200]}")

            proj_data = proj_resp.json()
            project_id = proj_data.get("id")
            print(f"[FLOW MUSIC] Đã tạo Project ID: {project_id}")

            # 2. Khởi tạo Conversation để sinh bài hát
            conv_resp = api.post(
                "https://www.flowmusic.app/__api/conversation",
                headers=headers,
                data={
                    "parts": [{"content": full_prompt, "part_kind": "user-prompt"}],
                    "client_context": {},
                    "project_id": project_id
                },
                timeout=request_timeout_ms
            )
            if conv_resp.status != 200:
                context.close()
                raise RuntimeError(f"[FLOW MUSIC ERROR] Không thể gửi yêu cầu tạo bài hát ({conv_resp.status}): {conv_resp.text()[:200]}")

            conv_data = conv_resp.json()
            job_id = conv_data.get("job_id")
            print(f"[FLOW MUSIC] Đã gửi prompt tạo nhạc (Job ID: {job_id}). Đang chờ Google Lyria render...")

            # 3. Theo dõi quá trình render
            start_time = time.time()
            clip_ids = []

            while time.time() - start_time < timeout_sec:
                time.sleep(POLL_INTERVAL_SEC)

                # Kiểm tra project clips
                p_resp = api.get(
                    f"https://www.flowmusic.app/__api/projects/{project_id}/clips/ids",
                    headers={"Authorization": token},
                    timeout=request_timeout_ms
                )
                if p_resp.status == 200:
                    try:
                        c_data = p_resp.json()
                        ids = c_data.get("clip_ids") or []
                        if not ids and "clips" in c_data:
                            ids = [c["id"] for c in c_data["clips"] if isinstance(c, dict) and "id" in c]
                        if ids:
                            clip_ids = ids
                            print(f"[FLOW MUSIC] Đã tìm thấy các bản nhạc được tạo: {clip_ids}")
                            break
                    except Exception:
                        pass

            # Fallback: Lấy clip vừa tạo từ auth-user nếu project endpoint chưa kịp map
            if not clip_ids:
                u_resp = api.get(
                    "https://www.flowmusic.app/__api/clips/auth-user?limit=3&offset=0&filter=generations",
                    headers={"Authorization": token},
                    timeout=request_timeout_ms
                )
                if u_resp.status == 200:
                    try:
                        u_data = u_resp.json()
                        if "clips" in u_data and u_data["clips"]:
                            clip_ids = [u_data["clips"][0]["id"]]
                            print(f"[FLOW MUSIC] Lấy thành công clip mới nhất: {clip_ids}")
                    except Exception:
                        pass

            if not clip_ids:
                context.close()
                raise RuntimeError(
                    f"[FLOW MUSIC ERROR] Quá thời gian chờ ({timeout_sec}s) render âm nhạc từ Flow Music. "
                    "Hệ thống tuân thủ Ground Truth, không tạo file âm thanh giả lập!"
                )

            chosen_clip_id = clip_ids[0]
            print(f"[FLOW MUSIC] Đang tải bản nhạc (Clip ID: {chosen_clip_id})...")

            # 4. Tải file âm thanh thực tế qua download endpoint
            dl_resp = api.get(
                f"https://www.flowmusic.app/__api/download/audio/{chosen_clip_id}?format=m4a",
                headers={"Authorization": token},
                timeout=request_timeout_ms
            )

            if dl_resp.status != 200:
                context.close()
                raise RuntimeError(f"[FLOW MUSIC ERROR] Không thể tải dữ liệu âm thanh của clip {chosen_clip_id} ({dl_resp.status}).")

            audio_data = dl_resp.body()
            api.dispose()
            context.close()

            if len(audio_data) < 50000:
                raise RuntimeError("[FLOW MUSIC ERROR] Tệp âm thanh tải về quá nhỏ, không hợp lệ.")

            # Lưu tệp thô m4a tạm thời
            raw_filename = f"flowmusic_{chosen_clip_id[:12]}_raw.m4a"
            raw_path = target_dir / raw_filename
            raw_path.write_bytes(audio_data)

            # Chuẩn hóa âm lượng sang MP3 chuẩn TikTok -14 LUFS bằng FFmpeg
            final_filename = f"flowmusic_{uuid.uuid4().hex[:12]}_output.mp3"
            final_path = target_dir / final_filename

            cmd = [
                "ffmpeg", "-y",
                "-i", str(raw_path),
                "-af", "loudnorm=I=-14:LRA=7:tp=-1.5",
                "-b:a", "192k",
                str(final_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)

            # Xóa file m4a thô sau khi chuyển đổi thành công
            try:
                raw_path.unlink()
            except Exception:
                pass

            data = final_path.read_bytes()
            sha256_hash = hashlib.sha256(data).hexdigest()
            byte_size = len(data)

            duration_ms = 60000
            try:
                probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)]
                probe_out = subprocess.check_output(probe_cmd, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
                if probe_out:
                    duration_ms = int(float(probe_out) * 1000)
            except Exception:
                pass

            print(f"[FLOW MUSIC] Hoàn tất tạo nhạc AI thật: {final_path.name} ({byte_size} bytes, {duration_ms}ms)")

            return {
                "status": "SUCCEEDED",
                "provider": "FLOW_MUSIC_ASSISTED",
                "source_product": "FLOW_MUSIC",
                "title": f"Bản nhạc {genre} ({mood})",
                "filename": final_filename,
                "storage_path": str(final_path),
                "relative_storage_key": f"workspaces/{workspace_id}/media/{final_filename}",
                "sha256": sha256_hash,
                "byte_size": byte_size,
                "mime_detected": "audio/mpeg",
                "duration_ms": duration_ms,
                "actual_cost": 0.0,
                "cost_currency": "USD",
                "credits_source": "FLOW_MUSIC_PLUS"
            }


flow_music_client = FlowMusicClient(headless=True)
