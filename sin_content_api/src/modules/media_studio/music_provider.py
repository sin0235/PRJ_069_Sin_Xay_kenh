# -*- coding: utf-8 -*-

"""Động cơ điều phối âm nhạc (Music Engine) cho BAHA Creator Studio (GF04 + P08/GF05).

Kiến trúc Hexagonal tách bạch 3 Adapter:

1. GoogleOfficialLyriaAdapter: Gọi trực tiếp Google Gemini API Interactions REST (Lyria 3 Clip & Lyria 3.5).

2. FlowBrowserPilotAdapter: Edge Playwright Sidecar thử nghiệm nội bộ, tắt mặc định.

3. LocalTestSynthAdapter: Dành riêng cho test fixture offline, gán rõ LOCAL_TEST_SYNTH.



Tuân thủ nghiêm ngặt:

- Ground Truth > Self-Report (Không sinh âm thanh giả mạo rồi dán nhãn Lyria/Flow).

- Audio QC EBU R128 (-14 LUFS ± 1 LUFS, True Peak <= -1.5 dBTP).

- Separation of Duties: approval_state ban đầu là "UNREVIEWED", cấm tự phong APPROVED.

- Quản trị tài nguyên: Concurrency = 1.

"""



import os

import sys

import uuid

import time

import base64

import hashlib

import pathlib

import threading

import subprocess

from typing import Dict, Any, Optional, List

from datetime import datetime, timezone

import httpx

from sqlalchemy.orm import Session



from src.models.entities import MediaAsset, AIGenerationJob, WorkspaceBudget, CostLedger

from src.schemas.contracts import (

    MusicProviderType,

    MusicGenerationMode,

    MusicJobStatus,

    MusicQCReport,

    MusicCapabilityItem,

    MusicCapabilitiesResponse,

)

from src.modules.media_studio.audio_processor import audio_processor

from src.modules.media_studio.security import MEDIA_ROOT_DIR



FLOW_BRIDGE = pathlib.Path(__file__).resolve().parents[4] / "cong_cu_tu_dong" / "flow_bridge"

if str(FLOW_BRIDGE) not in sys.path:

    sys.path.insert(0, str(FLOW_BRIDGE))



try:

    from session_manager import FlowLoginRequired

except ImportError:

    class FlowLoginRequired(RuntimeError):

        pass





class LocalTestSynthAdapter:

    """Bộ chuyển đổi sinh âm thanh thử nghiệm cục bộ (Offline Test Fixture Only).

    Tuyệt đối không mạo nhận là Google Lyria hay Flow Music.

    """



    def __init__(self):

        self.provider_id = "LOCAL_TEST_SYNTH"

        self.model_id = "test-synth-v1"



    def _generate_rich_melody(self, target_path: pathlib.Path, duration_sec: int = 15) -> None:

        """Tạo bản nhạc nền hòa âm 4 hợp âm C-Am-F-G chuẩn TikTok -14 LUFS cho mục đích kiểm thử."""

        dur = max(4, duration_sec)

        filter_complex = (

            "sine=f=261.63:d=4[c1];sine=f=329.63:d=4[c2];sine=f=392.00:d=4[c3];[c1][c2][c3]amix=3[chord_c];"

            "sine=f=220.00:d=4[a1];sine=f=261.63:d=4[a2];sine=f=329.63:d=4[a3];[a1][a2][a3]amix=3[chord_am];"

            "sine=f=174.61:d=4[f1];sine=f=220.00:d=4[f2];sine=f=261.63:d=4[f3];[f1][f2][f3]amix=3[chord_f];"

            "sine=f=196.00:d=4[g1];sine=f=246.94:d=4[g2];sine=f=293.66:d=4[g3];[g1][g2][g3]amix=3[chord_g];"

            f"[chord_c][chord_am][chord_f][chord_g]concat=n=4:v=0:a=1,aloop=loop=-1:size=44100*16,atrim=0:{dur},loudnorm=I=-14:LRA=7:tp=-1.5[out]"

        )

        cmd = [

            audio_processor.ffmpeg_bin,

            "-y",

            "-filter_complex", filter_complex,

            "-map", "[out]",

            "-ar", "44100",

            "-b:a", "192k",

            "-t", str(dur),

            str(target_path)

        ]

        subprocess.run(cmd, capture_output=True, check=True)



    def generate(

        self,

        prompt: str,

        genre: str = "Pop",

        mood: str = "Upbeat",

        lyrics: Optional[str] = None,

        duration_sec: int = 15,

        workspace_id: str = "default_ws"

    ) -> Dict[str, Any]:

        target_dir = MEDIA_ROOT_DIR / "workspaces" / workspace_id / "media"

        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"synth_{uuid.uuid4().hex[:12]}_test.mp3"

        dest_path = target_dir / filename



        self._generate_rich_melody(dest_path, duration_sec=duration_sec)



        data = dest_path.read_bytes()

        sha = hashlib.sha256(data).hexdigest()



        return {

            "status": "SUCCEEDED",

            "provider": self.provider_id,

            "source_product": "LOCAL_TEST_SYNTH",

            "model_id": self.model_id,

            "title": f"Bản nhạc thử nghiệm {genre} ({mood})",

            "filename": filename,

            "storage_path": str(dest_path),

            "relative_storage_key": f"workspaces/{workspace_id}/media/{filename}",

            "sha256": sha,

            "byte_size": len(data),

            "mime_detected": "audio/mpeg",

            "duration_ms": duration_sec * 1000,

            "actual_cost": 0.0,

            "cost_currency": "USD",

            "credits_source": "OFFLINE_TEST",

            "observed_at": datetime.now(timezone.utc).isoformat()

        }



class FlowMusicZeroCostProvider(LocalTestSynthAdapter):

    """Bộ cung cấp âm nhạc 0đ sử dụng Google Flow Web Pilot hoặc Local Test Synth."""



    def __init__(self):

        super().__init__()

        self.provider_id = "FLOW_MUSIC_ZERO_COST"

        self.model_id = "flow-music-web"



    def generate(

        self,

        prompt: str,

        genre: str = "Pop",

        mood: str = "Upbeat",

        lyrics: Optional[str] = None,

        duration_sec: int = 15,

        workspace_id: str = "default_ws"

    ) -> Dict[str, Any]:

        if (os.getenv("TESTING") == "1" or os.getenv("APP_ENV") == "test") and not os.getenv("FORCE_FLOW_MUSIC"):

            return super().generate(prompt, genre, mood, lyrics, duration_sec, workspace_id)



        try:

            from cong_cu_tu_dong.flow_bridge.flow_music_client import FlowMusicClient

            client = FlowMusicClient(headless=True)

            return client.create_track(

                prompt=prompt,

                title=f"Bản nhạc {genre} ({mood})",

                lyrics=lyrics,

                genre=genre,

                mood=mood,

                workspace_id=workspace_id,

                timeout_sec=240

            )

        except Exception as exc:

            if isinstance(exc, FlowLoginRequired):

                raise

            raise RuntimeError(f"FLOW_PILOT_FAILED: {exc}") from exc







class GoogleOfficialLyriaAdapter:

    """Bộ chuyển đổi chính thức Google Lyria qua Gemini API Interactions REST.

    Hỗ trợ:

    - lyria-3-clip-preview: Clip nhạc cố định 30 giây kèm lyrics/structure.

    - lyria-3.5: Bài hát dài có cấu trúc đầy đủ.

    """



    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):

        self.api_key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

        self.base_url = base_url or os.getenv(

            "GOOGLE_LYRIA_API_BASE",

            "https://generativelanguage.googleapis.com/v1beta"

        )

        self.provider_id = "GOOGLE_OFFICIAL"



    def inspect_capabilities(self) -> List[MusicCapabilityItem]:

        now_str = datetime.now(timezone.utc).isoformat()

        has_key = bool(self.api_key and len(self.api_key) > 10)

        is_verified = os.getenv("GOOGLE_GEMINI_API_KEY_VERIFIED", "").lower() in ("true", "1") or os.getenv("TESTING") == "1"

        is_enabled = has_key and is_verified



        blocked_reason = None

        if not has_key:

            blocked_reason = "CREDENTIALS_MISSING: Chưa cấu hình GOOGLE_GEMINI_API_KEY"

        elif not is_verified:

            blocked_reason = "UNVERIFIED_CREDENTIALS: Đã cấu hình khóa API nhưng chưa probe xác thực quyền truy cập model Lyria trên Google AI Studio"



        items = [

            MusicCapabilityItem(

                provider=MusicProviderType.GOOGLE_OFFICIAL,

                mode=MusicGenerationMode.CLIP_30S,

                model_id="lyria-3-clip-preview",

                enabled=is_enabled,

                blocked_reason=blocked_reason,

                max_duration_sec=30,

                cost_per_generation_usd=0.03,

                requires_approval=False,

                observed_at=now_str

            ),

            MusicCapabilityItem(

                provider=MusicProviderType.GOOGLE_OFFICIAL,

                mode=MusicGenerationMode.FULL_SONG,

                model_id="lyria-3.5",

                enabled=is_enabled,

                blocked_reason=blocked_reason,

                max_duration_sec=180,

                cost_per_generation_usd=0.08,

                requires_approval=True,

                observed_at=now_str

            )

        ]

        return items



    def _check_brand_safety_and_rights(self, prompt: str, lyrics: Optional[str] = None) -> None:

        """Kiểm tra câu lệnh và lời bài hát, ngăn ngừa vi phạm bản quyền hoặc đạo nhái nghệ sĩ."""

        full_text = f"{prompt} {lyrics or ''}".lower()

        forbidden_keywords = [

            "hát bằng giọng ca sĩ",

            "impersonate artist",

            "voice clone of",

            "giọng hát taylor swift",

            "giọng hát sơn tùng",

            "đạo nhạc",

            "copyrighted lyrics"

        ]

        for kw in forbidden_keywords:

            if kw in full_text:

                raise RuntimeError(f"PROMPT_SAFETY_VIOLATION: Yêu cầu vi phạm bản quyền hoặc đạo nhái nghệ sĩ: '{kw}'")



    def generate(

        self,

        prompt: str,

        genre: str = "Pop",

        mood: str = "Upbeat",

        lyrics: Optional[str] = None,

        duration_sec: int = 30,

        model_id: str = "lyria-3-clip-preview",

        workspace_id: str = "default_ws",

        client_transport: Optional[httpx.BaseTransport] = None

    ) -> Dict[str, Any]:

        """Gửi yêu cầu tạo nhạc tới Google Gemini Lyria API qua REST endpoint."""

        # 1. Kiểm tra bản quyền & brand safety

        self._check_brand_safety_and_rights(prompt, lyrics)



        # 2. Kiểm tra API Key

        if not self.api_key:

            raise RuntimeError("CREDENTIALS_MISSING: Chưa cấu hình khóa GOOGLE_GEMINI_API_KEY để gọi Google Lyria API.")



        # 3. Ràng buộc thời lượng: lyria-3-clip-preview bắt buộc cố định 30 giây

        if model_id == "lyria-3-clip-preview" and duration_sec != 30:

            duration_sec = 30



        # Ràng buộc model hòa tấu (instrumental limitation)

        if "instrumental" in model_id.lower() and lyrics:

            raise RuntimeError("INSTRUMENTAL_ONLY: Model hòa tấu không hỗ trợ lời bài hát (vocal lyrics).")



        target_dir = MEDIA_ROOT_DIR / "workspaces" / workspace_id / "media"

        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"lyria_{model_id.replace('-', '_')}_{uuid.uuid4().hex[:10]}.mp3"

        dest_path = target_dir / filename



        # 4. Chuẩn bị payload Gemini API Interactions

        constructed_prompt = f"Create a {genre} song with an {mood} mood. Prompt: {prompt}."

        if lyrics:

            constructed_prompt += f"\nLyrics:\n{lyrics}"



        request_body = {

            "model": f"models/{model_id}",

            "input": {

                "prompt": constructed_prompt

            },

            "parameters": {

                "duration_seconds": duration_sec

            }

        }



        url = f"{self.base_url}/interactions"

        headers = {

            "Content-Type": "application/json",

            "x-goog-api-key": self.api_key

        }

        timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)



        # 5. Thực hiện gọi API

        try:

            with httpx.Client(transport=client_transport, timeout=timeout) as client:

                response = client.post(url, json=request_body, headers=headers)

        except httpx.TimeoutException as exc:

            raise RuntimeError(f"UPSTREAM_TIMEOUT: Hết thời gian chờ phản hồi từ Google Lyria API: {exc}") from exc

        except Exception as exc:

            raise RuntimeError(f"PROVIDER_CONNECTION_FAILED: Lỗi kết nối Google Lyria API: {exc}") from exc



        if response.status_code == 401 or response.status_code == 403:

            raise RuntimeError(f"CREDENTIALS_INVALID: Khóa API không hợp lệ hoặc thiếu quyền truy cập ({response.status_code}): {response.text[:200]}")

        if response.status_code == 429:

            raise RuntimeError(f"QUOTA_EXCEEDED: Đã sử dụng hết hạn mức Google Lyria API (429): {response.text[:200]}")

        if response.status_code == 404 or ("model" in response.text.lower() and response.status_code != 200):

            raise RuntimeError(f"MODEL_UNAVAILABLE: Model '{model_id}' không khả dụng trong khu vực hoặc tài khoản: {response.text[:200]}")

        if response.status_code != 200:

            raise RuntimeError(f"PROVIDER_ERROR: Lỗi Google Lyria API ({response.status_code}): {response.text[:200]}")



        res_json = response.json()



        # 6. Kiểm tra lỗi và bộ lọc Safety Filter

        if res_json.get("status") == "FAILED" or "error" in res_json:

            err_info = res_json.get("error", {})

            err_msg = err_info.get("message") if isinstance(err_info, dict) else str(err_info)

            err_msg = err_msg or res_json.get("error_message") or "Lỗi từ Lyria Interactions API"

            if "safety" in err_msg.lower() or "block" in err_msg.lower():

                raise RuntimeError(f"PROMPT_SAFETY_VIOLATION: Google Lyria từ chối sinh nhạc do vi phạm an toàn: {err_msg}")

            raise RuntimeError(f"PROVIDER_ERROR: Google Lyria API: {err_msg}")



        for rating in res_json.get("safety_ratings", []):

            if rating.get("blocked") or rating.get("probability") in ("HIGH", "VERY_HIGH"):

                raise RuntimeError("PROMPT_SAFETY_VIOLATION: Google Lyria từ chối sinh nhạc do vi phạm an toàn.")



        # 7. Bóc tách âm thanh Base64 và siêu dữ liệu theo chuẩn Interactions API

        outputs = res_json.get("outputs") or res_json.get("candidates") or []

        if not outputs:

            prompt_feedback = res_json.get("promptFeedback", {})

            if prompt_feedback.get("blockReason"):

                raise RuntimeError(f"PROMPT_SAFETY_VIOLATION: Yêu cầu bị chặn bởi bộ lọc an toàn Google: {prompt_feedback.get('blockReason')}")

            raise RuntimeError("PROVIDER_EMPTY_RESPONSE: Google Lyria Interactions API không trả về bất kỳ kết quả nào.")



        audio_bytes = None

        structure_text = ""

        watermark_detected = True



        for item in outputs:

            item_type = item.get("type", "")

            mime_type = item.get("mime_type") or item.get("mimeType", "")

            if item_type == "audio" or "audio" in mime_type:

                b64_data = item.get("data") or item.get("inline_data", {}).get("data", "")

                if b64_data:

                    audio_bytes = base64.b64decode(b64_data)

                meta = item.get("metadata", {})

                if "synthid_watermark" in meta:

                    watermark_detected = bool(meta["synthid_watermark"])

            elif item_type == "text" or "text" in item:

                structure_text += (item.get("text") or "") + "\n"

            elif "content" in item:

                # Tương thích cấu trúc candidates parts

                finish_reason = item.get("finishReason")

                if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST"):

                    raise RuntimeError(f"PROMPT_SAFETY_VIOLATION: Google Lyria từ chối sinh nhạc do vi phạm an toàn ({finish_reason}).")

                for part in item["content"].get("parts", []):

                    if "inlineData" in part:

                        audio_bytes = base64.b64decode(part["inlineData"].get("data", ""))

                    elif "text" in part:

                        structure_text += part.get("text", "") + "\n"



        if not audio_bytes or len(audio_bytes) < 1000:

            raise RuntimeError("PROVIDER_INVALID_AUDIO: Phản hồi từ Google Lyria thiếu dữ liệu âm thanh hợp lệ.")



        # Xác định actual cost từ usage receipt

        usage_info = res_json.get("usage", {})

        if "cost_usd" in usage_info:

            actual_cost = float(usage_info["cost_usd"])

        elif "billing_units" in usage_info:

            actual_cost = float(usage_info["billing_units"]) * (0.03 if model_id == "lyria-3-clip-preview" else 0.08)

        else:

            actual_cost = 0.03 if model_id == "lyria-3-clip-preview" else 0.08



        # Lưu tệp thô tạm và chuẩn hóa -14 LUFS

        raw_temp = target_dir / f"raw_{filename}"

        raw_temp.write_bytes(audio_bytes)



        try:

            audio_processor.normalize_loudness(

                input_path=raw_temp,

                output_path=dest_path,

                target_lufs=-14.0

            )

        finally:

            if raw_temp.exists():

                try:

                    raw_temp.unlink()

                except Exception:

                    pass



        final_data = dest_path.read_bytes()

        sha = hashlib.sha256(final_data).hexdigest()



        return {

            "status": "SUCCEEDED",

            "provider": self.provider_id,

            "source_product": "GEMINI_LYRIA_OFFICIAL",

            "model_id": model_id,

            "title": f"Lyria {genre} ({mood})",

            "filename": filename,

            "storage_path": str(dest_path),

            "relative_storage_key": f"workspaces/{workspace_id}/media/{filename}",

            "sha256": sha,

            "byte_size": len(final_data),

            "mime_detected": "audio/mpeg",

            "duration_ms": duration_sec * 1000,

            "actual_cost": actual_cost,

            "cost_currency": "USD",

            "credits_source": "GOOGLE_AI_STUDIO_API",

            "lyrics_metadata": structure_text.strip(),

            "watermark_synthid": watermark_detected,

            "observed_at": datetime.now(timezone.utc).isoformat()

        }





class FlowBrowserPilotAdapter:

    """Bộ chuyển đổi Flow Music Plus Web qua Sidecar Playwright.

    Chỉ kích hoạt khi cờ FLOW_MUSIC_PILOT_ENABLED = true và có phiên đăng nhập của chủ tài khoản.

    """



    def __init__(self):

        self.provider_id = "FLOW_BROWSER_PILOT"



    def is_enabled(self) -> bool:

        return os.getenv("FLOW_MUSIC_PILOT_ENABLED", "false").lower() in ("true", "1", "yes")



    def inspect_capabilities(self) -> List[MusicCapabilityItem]:

        enabled = self.is_enabled()

        item = MusicCapabilityItem(

            provider=MusicProviderType.FLOW_BROWSER_PILOT,

            mode=MusicGenerationMode.PILOT_ASSISTED,

            model_id="flow-music-web",

            enabled=enabled,

            blocked_reason=None if enabled else "PILOT_DISABLED: Flow Music Browser Pilot hiện đang tắt theo chính sách an ninh dự án.",

            max_duration_sec=120,

            cost_per_generation_usd=0.0,

            requires_approval=True,

            observed_at=datetime.now(timezone.utc).isoformat()

        )

        return [item]



    def generate(

        self,

        prompt: str,

        genre: str = "Pop",

        mood: str = "Upbeat",

        lyrics: Optional[str] = None,

        duration_sec: int = 60,

        workspace_id: str = "default_ws"

    ) -> Dict[str, Any]:

        if not self.is_enabled():

            raise RuntimeError("PILOT_DISABLED: Flow Music Browser Pilot hiện đang tắt theo chính sách an ninh dự án.")



        try:

            from cong_cu_tu_dong.flow_bridge.flow_music_client import FlowMusicClient

            client = FlowMusicClient(headless=True)

            res = client.create_track(

                prompt=prompt,

                title=f"Bản nhạc {genre} ({mood})",

                lyrics=lyrics,

                genre=genre,

                mood=mood,

                workspace_id=workspace_id,

                timeout_sec=240

            )

            res["source_product"] = "FLOW_MUSIC_PILOT"

            res["provider"] = self.provider_id

            return res

        except Exception as exc:

            if isinstance(exc, FlowLoginRequired):

                raise

            raise RuntimeError(f"FLOW_PILOT_FAILED: Không thể tạo nhạc từ Flow Music Web: {exc}") from exc





class MusicOrchestrator:

    """Động cơ điều phối âm nhạc trung tâm.

    - Quản lý concurrency = 1 bằng threading lock.

    - Chọn adapter phù hợp.

    - Kiểm tra kiểm định âm lượng EBU R128 (-14 LUFS ± 1 LUFS).

    - Tạo MediaAsset với approval_state = 'UNREVIEWED' (Separation of Duties).

    """



    def __init__(self):

        self.lyria_adapter = GoogleOfficialLyriaAdapter()

        self.pilot_adapter = FlowBrowserPilotAdapter()

        self.synth_adapter = LocalTestSynthAdapter()

        self._execution_lock = threading.Lock()



    def get_capabilities(self, workspace_id: str) -> MusicCapabilitiesResponse:

        """Tổng hợp năng lực các nhà cung cấp âm nhạc hiện hành."""

        items: List[MusicCapabilityItem] = []

        items.extend(self.lyria_adapter.inspect_capabilities())

        items.extend(self.pilot_adapter.inspect_capabilities())



        # Thêm adapter test synth chỉ khi có cấu hình kiểm thử tường minh

        allow_synth = os.getenv("ALLOW_LOCAL_TEST_SYNTH", "").lower() in ("true", "1") or os.getenv("TESTING") == "1"

        if allow_synth:

            items.append(

                MusicCapabilityItem(

                    provider=MusicProviderType.LOCAL_TEST_SYNTH,

                    mode=MusicGenerationMode.SYNTH_FIXTURE,

                    model_id="test-synth-v1",

                    enabled=True,

                    blocked_reason=None,

                    max_duration_sec=30,

                    cost_per_generation_usd=0.0,

                    requires_approval=False,

                    observed_at=datetime.now(timezone.utc).isoformat()

                )

            )



        # Default provider: Tuyệt đối không chọn LOCAL_TEST_SYNTH làm default ngoài môi trường test tường minh

        if any(i.provider == MusicProviderType.GOOGLE_OFFICIAL and i.enabled for i in items):

            default_provider = MusicProviderType.GOOGLE_OFFICIAL

        elif any(i.provider == MusicProviderType.FLOW_BROWSER_PILOT and i.enabled for i in items):

            default_provider = MusicProviderType.FLOW_BROWSER_PILOT

        elif allow_synth:

            default_provider = MusicProviderType.LOCAL_TEST_SYNTH

        else:

            default_provider = MusicProviderType.FLOW_BROWSER_PILOT



        return MusicCapabilitiesResponse(

            workspace_id=workspace_id,

            items=items,

            default_provider=default_provider,

            pilot_enabled=self.pilot_adapter.is_enabled()

        )



    def generate_music_track(

        self,

        db: Session,

        workspace_id: str,

        user_id: str,

        prompt: str,

        genre: str = "Pop",

        mood: str = "Upbeat",

        lyrics: Optional[str] = None,

        duration_sec: int = 30,

        provider: MusicProviderType = MusicProviderType.GOOGLE_OFFICIAL,

        mode: MusicGenerationMode = MusicGenerationMode.CLIP_30S,

        project_id: Optional[str] = None,

        idempotency_key: Optional[str] = None,

        client_transport: Optional[httpx.BaseTransport] = None

    ) -> MediaAsset:

        """Thực hiện tạo bản nhạc mới và lưu trữ asset với rào chắn Bốn Mắt."""

        # 1. Quản trị concurrency = 1

        acquired = self._execution_lock.acquire(timeout=60.0)

        if not acquired:

            raise RuntimeError("CONCURRENCY_LIMIT_EXCEEDED: Hệ thống đang xử lý tác vụ âm nhạc khác. Vui lòng thử lại sau.")



        try:

            # Kiểm tra bản quyền & nhại giọng nghệ sĩ cho toàn bộ các provider
            self.lyria_adapter._check_brand_safety_and_rights(prompt, lyrics)

            # 2. Định tuyến adapter

            is_offline_test = (os.getenv("TESTING") == "1" or os.getenv("APP_ENV") == "test")

            allow_synth = os.getenv("ALLOW_LOCAL_TEST_SYNTH", "").lower() in ("true", "1") or is_offline_test



            if provider == MusicProviderType.LOCAL_TEST_SYNTH:

                if not allow_synth:

                    raise RuntimeError("UNSUPPORTED_PROVIDER: LOCAL_TEST_SYNTH chỉ được phép sử dụng trong môi trường kiểm thử cục bộ.")

                res = self.synth_adapter.generate(

                    prompt=prompt,

                    genre=genre,

                    mood=mood,

                    lyrics=lyrics,

                    duration_sec=duration_sec,

                    workspace_id=workspace_id

                )

            elif provider == MusicProviderType.GOOGLE_OFFICIAL:

                model_id = "lyria-3-clip-preview" if mode == MusicGenerationMode.CLIP_30S else "lyria-3.5"

                res = self.lyria_adapter.generate(

                    prompt=prompt,

                    genre=genre,

                    mood=mood,

                    lyrics=lyrics,

                    duration_sec=duration_sec,

                    model_id=model_id,

                    workspace_id=workspace_id,

                    client_transport=client_transport

                )

            elif provider == MusicProviderType.FLOW_BROWSER_PILOT:

                res = self.pilot_adapter.generate(

                    prompt=prompt,

                    genre=genre,

                    mood=mood,

                    lyrics=lyrics,

                    duration_sec=duration_sec,

                    workspace_id=workspace_id

                )

            else:

                raise RuntimeError(f"UNSUPPORTED_PROVIDER: Nhà cung cấp âm nhạc '{provider}' không được hỗ trợ.")



            # 3. Kiểm định chất lượng âm thanh thật (Audio QC Verification)

            asset_path = pathlib.Path(res["storage_path"])

            # Với Lyria Clip Preview chính thức của Google, thời lượng cố định chuẩn là 30s
            if provider == MusicProviderType.GOOGLE_OFFICIAL and (mode == MusicGenerationMode.CLIP_30S or res.get("model_id") == "lyria-3-clip-preview"):
                expected_duration = 30.0
            elif provider == MusicProviderType.FLOW_BROWSER_PILOT or res.get("source_product") in ("FLOW_MUSIC", "FLOW_MUSIC_PILOT"):
                # Flow Music Web tạo bài hát đầy đủ theo AI (60s - 240s), không gán cứng 30s
                expected_duration = None
            elif mode == MusicGenerationMode.FULL_SONG:
                expected_duration = None
            else:
                expected_duration = float(duration_sec) if (duration_sec and duration_sec > 0) else None



            qc = audio_processor.verify_audio_qc(

                filepath=asset_path,

                expected_duration_sec=expected_duration,

                target_lufs=-14.0,

                lufs_tolerance=1.0,

                max_true_peak_dbtp=-1.5

            )



            if not qc["passed"]:

                try:

                    asset_path.unlink()

                except Exception:

                    pass

                raise RuntimeError(f"AUDIO_QC_FAILED: Tệp âm thanh không đạt chuẩn kỹ thuật TikTok: {qc['reason']}")



            # 4. Tạo bản ghi MediaAsset với approval_state = UNREVIEWED (Separation of Duties)

            asset = MediaAsset(

                id=f"asset-{uuid.uuid4().hex[:12]}",

                workspace_id=workspace_id,

                project_id=project_id,

                storage_key=res["relative_storage_key"],

                sha256=res["sha256"],

                byte_size=res["byte_size"],

                mime_detected="audio/mpeg",

                source_product=res["source_product"],

                original_filename=res["filename"],

                created_by=user_id,

                duration_ms=res.get("duration_ms", duration_sec * 1000),

                approval_state="UNREVIEWED"

            )

            db.add(asset)

            db.commit()

            db.refresh(asset)

            return asset

        finally:

            self._execution_lock.release()





music_orchestrator = MusicOrchestrator()

