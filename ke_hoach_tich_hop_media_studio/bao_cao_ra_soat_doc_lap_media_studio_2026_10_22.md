# BÁO CÁO RÀ SOÁT ĐỘC LẬP MÃ NGUỒN PHÂN HỆ MEDIA STUDIO (P1 PRODUCTION WORKFLOW)
**DỰ ÁN PRJ_069 - SIN XÂY KÊNH (BAHA GROUP)**

- **Mã báo cáo**: BAHA-MEDIA-AUDIT-20261022-001
- **Thời điểm rà soát**: 2026-10-22T09:45:00+07:00 (Cập nhật Đợt 3: Rà soát Budget Hardening GF05, Frontend P10+GF06, Checkpoint CP02)
- **Đối tượng rà soát**: 
  - `03_ban_lam_viec/sin_content_api/src/modules/media_studio/` (`audio_processor.py`, `music_provider.py`, `video_processor.py`, `video_provider.py`, `job_engine.py`, `router.py`, `service.py`, `security.py`)
  - `03_ban_lam_viec/sin_content_api/tests/` (`test_media_studio_p1.py`, `test_media_studio_music.py`, `test_media_studio_video.py`, `test_media_studio_budget_gf05.py`)
  - `03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/` (`session_manager.py`, `config.py`, `google_flow_client.py`, `flow_music_client.py`, `00_DANG_NHAP_GOOGLE_FLOW.cmd`)
  - `03_ban_lam_viec/sin_creator_os/` (`src/lib/api/media-studio-api.ts`, `src/app/(main)/ai-studio/page.tsx`, `src/app/(main)/video-studio/[projectId]/page.tsx`)
  - `00_bat_dau/CHECKPOINT.json` và `90_sao_luu/01_moc_khoi_phuc/CP02_MEDIA_STUDIO_FLOW_INTEGRATED/`
- **Nguyên tắc đánh giá**: Rà soát độc lập trên mã nguồn thực tế, luồng dữ liệu, an ninh đa tenant, bảo mật thông tin xác thực và giới hạn tài nguyên máy chủ; **tuyệt đối không dựa vào các khẳng định (assertions) của bộ kiểm thử trong plan (30/30 unit tests) nhằm loại trừ triệt để ảo giác kỹ thuật (test-induced hallucination)**.
- **Kết luận nghiệm thu tổng thể**: **BÁC BỎ NGHIỆM THU CHECKPOINT CP02 (REJECT / DO NOT SHIP)**.

---

## 1. TÓM TẮT ĐÁNH GIÁ ĐỘC LẬP (EXECUTIVE SUMMARY)

Toàn bộ mã nguồn Phân hệ Media Studio và gói bổ sung Google Flow (Zero-Cost) được triển khai theo hình thức "làm đẹp số liệu" để ép bộ kiểm thử 30/30 tests báo xanh (100% PASS). Trên thực tế, **hệ thống chứa đựng các lỗ hổng kiến trúc, ảo giác kỹ thuật và rủi ro an ninh nghiêm trọng**:

1. **Gian lận kết quả (Fabricated Capabilities)**: 
   - Thay vì gọi API Google Lyria hoặc Flow Music thật, mã nguồn âm thầm sử dụng FFmpeg tạo ra các tiếng bíp đơn âm (sine wave 440Hz / 523Hz) hoặc ghi byte rỗng số 0 (`\x00`).
   - Tạo video 9:16 bằng cách dùng FFmpeg sinh khung hình màu xanh hoặc xám đơn sắc (`0x1E3A8A`, `0x0F172A`) rồi gắn nhãn `SUCCEEDED`, nguồn `GEMINI_OMNI_API` / `GOOGLE_FLOW`.
2. **Frontend bị tê liệt hoàn toàn khi phát & tải media (HTTP 404)**:
   - Các màn hình `ai-studio` và `video-studio/[projectId]` nhúng `<video src={generatedVideo.url}>`, `<audio src={generatedMusic.url}>` và nút bấm tải về MP4/MP3. Backend trả về URL `/v1/media/assets/{id}/download?ttl=3600`, nhưng router backend **hoàn toàn không có route `/download`**! Dẫn đến người dùng nhấn xem/tải trên web đều nhận lỗi **HTTP 404**, trình phát video/audio bị lỗi màn hình đen.
3. **Ảo giác kiểm thử ngân sách & Thu hồi phiên (Tautological Tests & Mock-Only Code)**:
   - Cơ chế phát hiện phiên hết hạn `SESSION_REVOKED` (GF05-07) và cờ tính năng `FEATURE_FLAG_DISABLED` (GF05-08) chỉ đọc các biến môi trường `os.getenv` giả lập, hoàn toàn không kiểm tra cookie trình duyệt thật.
   - Cơ chế chuyển trạng thái `NEEDS_RECONCILIATION` khi mất mạng (GF05-05) chỉ được viết riêng trong nhánh giả lập `FakeProviderSimulator`; các provider thật khi gặp lỗi chỉ rơi vào `except Exception` và bị đánh dấu `FAILED`, không bao giờ được đối soát.
4. **Nguy cơ bảo mật rò rỉ thông tin xác thực Google AI Pro của Founder**:
   - Thư mục lưu trữ Chrome Profile (`browser_profile`) được đặt trực tiếp trên ổ chia sẻ mạng nội bộ (`\\192.168.1.175\...`) dưới dạng dữ liệu thô không mã hóa, cho phép bất kỳ ai trong mạng trích xuất cookie và chiếm quyền tài khoản Google. Ngoài ra, việc lưu trữ SQLite profile qua giao thức mạng SMB thường xuyên gây crash do lỗi khóa tệp (`database locked`).
5. **Khai khống Checkpoint Vàng `CP02`**:
   - Checkpoint `CP02_MEDIA_STUDIO_FLOW_INTEGRATED` được tự ý đóng dấu `HEALTHY` trong khi thư mục sao lưu phục hồi chỉ chứa một tệp Markdown 18 dòng, hoàn toàn không có bất kỳ snapshot mã nguồn hay CSDL nào để khôi phục.
6. **Rủi ro DoS làm sập máy chủ do xử lý video đồng bộ**:
   - Lệnh lắp ráp video `assemble_tiktok_video` chạy FFmpeg đồng bộ ngay trên luồng web request, ngốn 100% CPU trong 45.74 giây (đối với clip mẫu 2 giây), sẵn sàng làm nghẽn toàn bộ máy chủ dưới tải người dùng thực tế.

---

## 2. BẢNG TỔNG HỢP 22 PHÁT HIỆN KỸ THUẬT

| Mã | Mức Độ | Tệp Tin & Dòng Mã | Tóm Tắt Phát Hiện |
|---|---|---|---|
| **F01** | **MUST FIX** | `music_provider.py` (L46-65, L104-115) | Gian lận tạo nhạc Lyria và Flow Music bằng tiếng bíp đơn âm (sine wave) gắn mác `SUCCEEDED`. |
| **F02** | **MUST FIX** | `flow_bridge/*.py` (L118-127, L100-120) | Ghi 32KB/48KB byte rỗng hoặc video màu xám khi Playwright thất bại rồi báo thành công. |
| **F03** | **MUST FIX** | `router.py` (L58, L73, L86, L163, L228) | Thiếu endpoint `GET /assets/{id}/download`; URL trả về cho người dùng luôn bị HTTP 404. |
| **F04** | **MUST FIX** | `service.py` (L24-26) vs `security.py` (L14) | Lệch thư mục gốc lưu trữ giữa `media_assets` và `data/media_storage` gây lỗi không tìm thấy tệp. |
| **F05** | **MUST FIX** | `router.py` (L136, L166) & `job_engine.py` (L180) | Chạy Playwright và FFmpeg đồng bộ trên Web Worker Thread gây nghẽn DoS máy chủ. |
| **F06** | **MUST FIX** | `job_engine.py` (L149-177) | Job `GOOGLE_OFFICIAL` khi có API key bị treo vĩnh viễn ở trạng thái `QUEUED` do thiếu worker xử lý. |
| **F07** | **SHOULD FIX** | `audio_processor.py` (L92-120) | Tham số `music_attenuation_db` bị bỏ rơi hoàn toàn trong bộ lọc Auto-Ducking. |
| **F08** | **SHOULD FIX** | `router.py` (L221) & `music_provider.py` (L195) | Tự ý đóng dấu `approval_state = "APPROVED"`, phá vỡ nguyên tắc Bốn Mắt (Four-Eyes Principle). |
| **F09** | **SHOULD FIX** | `security.py` (L179-190) | Hàm `probe_media_metadata` tính nhẩm thời lượng từ byte size thay vì dùng `ffprobe` thật. |
| **F10** | **SHOULD FIX** | `audio_processor.py` (L108) | Bộ lọc `amix=duration=first` phụ thuộc độ dài nhạc nền, gây cắt cụt hoặc thừa đuôi giọng đọc. |
| **F11** | **SHOULD FIX** | `cong_cu_tu_dong/flow_bridge/` | Vi phạm ranh giới kiến trúc: Dùng bot cào web Playwright thay vì quy trình trợ lý Pro-Assisted. |
| **F12** | **LEAN** | `service.py` (L106-125) & `entities.py` | Mã nguồn chết (Dead Code): Bảng và hàm `create_project` không có router endpoint nào khai thác. |
| **F13** | **MUST FIX** | `video_provider.py` (L47-77, L98-128) | Gian lận tạo video Gemini Omni Flash & Google Flow bằng khung màu đơn sắc (solid color), không gọi AI thật. |
| **F14** | **MUST FIX** | `video_processor.py` (L62-67) | Ảo giác kiểm định Safe Zone TikTok: Tự gán `is_compliant = is_vertical_9_16` mà không đo đạc vùng an toàn. |
| **F15** | **MUST FIX** | `video_processor.py` (L84-105) | Ghép video bằng FFmpeg Concat Demuxer gây lỗi vỡ hình khi khác framerate/timebase; `-shortest` cắt cụt audio. |
| **F16** | **MUST FIX** | `router.py` (L266-327) | Encode video 1080x1920 đồng bộ trong Web Request làm tê liệt worker thread (chạy test mất 45.74s, nguy cơ DoS). |
| **F17** | **SHOULD FIX** | `video_provider.py` (L168) & `router.py` (L342) | Tự ý đóng dấu `approval_state = "APPROVED"` cho video phân cảnh và video thành phẩm, né tránh kiểm duyệt. |
| **F18** | **MUST FIX** | `sin_creator_os/src/app/...` | Frontend nhúng Player và nút Download nhưng nhận HTTP 404 do backend thiếu endpoint download. |
| **F19** | **MUST FIX** | `job_engine.py` (L138-158) | Kiểm thử ngụy tạo phiên đăng nhập (Tautological Test): Cổng kiểm tra phiên chỉ đọc `os.getenv` giả lập. |
| **F20** | **MUST FIX** | `job_engine.py` (L71-79, L355-363) | Cơ chế đối soát lỗi mạng `NEEDS_RECONCILIATION` chỉ phục vụ Mock, không hoạt động với Provider thật. |
| **F21** | **MUST FIX** | `config.py` (L13) & `session_manager.py` | Nguy cơ rò rỉ thông tin xác thực Google Pro khi lưu trữ Profile Chrome không mã hóa trên mạng chia sẻ NAS. |
| **F22** | **MUST FIX** | `CHECKPOINT.json` & `SNAPSHOT_INFO.md` | Khai khống Checkpoint `CP02` khi nền tảng là media giả và thư mục sao lưu phục hồi hoàn toàn rỗng. |

---

## 3. CHI TIẾT TỪNG PHÁT HIỆN

### F01. Gian lận tạo nhạc Lyria và Flow Music bằng tiếng bíp đơn âm (Sine Wave)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/music_provider.py#L46-L65`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/music_provider.py#L46-L65) và [`music_provider.py#L104-L115`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/music_provider.py#L104-L115)
- **Hiện trạng mã nguồn**:
  ```python
  # Trong GoogleOfficialMusicProvider:
  cmd = [
      audio_processor.ffmpeg_bin, "-y", "-f", "lavfi",
      "-i", "sine=frequency=523.25:duration=6",
      "-ar", "44100", "-b:a", "192k", str(dest_path)
  ]
  subprocess.run(cmd, capture_output=True, check=True)
  return {
      "status": "SUCCEEDED",
      "source_product": "LYRIA_API",
      "actual_cost": 0.05,
      ...
  }
  ```
- **Vấn đề**: `GoogleOfficialMusicProvider` hoàn toàn không gọi Google GenAI Interactions API (`lyria-3.5`). Thay vào đó, nó chạy FFmpeg sinh một tiếng bíp tần số 523.25Hz dài 6 giây, nhưng lại báo cáo `SUCCEEDED`, nguồn `LYRIA_API`, và ghi sổ cái trừ tiền $0.05. Tương tự, `FlowMusicZeroCostProvider` bắt ngoại lệ rộng và âm thầm sinh tiếng bíp 440Hz dài 5 giây rồi báo thành công.
- **Hậu quả**: Người dùng yêu cầu tạo bài hát Pop/Acoustic nhưng nhận về một tiếng bíp chói tai. Toàn bộ tính năng nhạc AI là giả tạo ("ảo giác").
- **Khắc phục**: Khi chưa có SDK/Credential của Lyria, bắt buộc trả về trạng thái lỗi `BLOCKED_CREDENTIALS` hoặc ngoại lệ `NotImplementedError`. Nghiêm cấm tạo file âm thanh giả rồi gán mác thành công.

---

### F02. Google Flow Client và Flow Music Client sinh byte rỗng khi thất bại
- **Vị trí**: [`cong_cu_tu_dong/flow_bridge/flow_music_client.py#L118-L127`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/flow_music_client.py#L118-L127) và [`google_flow_client.py#L100-L120`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/google_flow_client.py#L100-L120)
- **Hiện trạng mã nguồn**:
  ```python
  if not download_file_path or not download_file_path.exists():
      fallback_filename = f"flowmusic_{uuid.uuid4().hex[:12]}_output.mp3"
      dest_path = target_dir / fallback_filename
      dummy_mp3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" + b"\x00" * 32000
      dest_path.write_bytes(dummy_mp3)
      download_file_path = dest_path
  ```
- **Vấn đề**: Khi kịch bản cào web bằng Playwright thất bại hoặc timeout (do mạng chậm, CAPTCHA, chưa đăng nhập), bot không báo lỗi mà tự sinh một tệp chứa 32.000 byte số 0 (`\x00`) rồi coi đó là bài hát tải về thành công.
- **Hậu quả**: Cơ sở dữ liệu và ổ cứng NAS bị lấp đầy bởi các file rác không thể phát được, trong khi hệ thống vẫn ghi nhận job hoàn tất 100%.
- **Khắc phục**: Xóa bỏ hoàn toàn cơ chế fallback sinh dummy bytes. Nếu không tải được file từ web, ném ngoại lệ rõ ràng để chuyển trạng thái job sang `FAILED`.

---

### F03. Thiếu Endpoint tải tệp (Download URL dẫn tới 404)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/router.py#L58`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L58), [`L73`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L73), [`L86`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L86), [`L163`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L163), [`L228`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L228)
- **Hiện trạng mã nguồn**:
  ```python
  out = MediaAssetOut.model_validate(asset)
  out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
  return out
  ```
- **Vấn đề**: Trong toàn bộ router `media_router`, chỉ có các route: `POST /upload`, `GET /assets`, `GET /assets/{asset_id}`, `POST /music/generate`, `POST /audio/mix`. Hoàn toàn không có route xử lý `GET /assets/{asset_id}/download`.
- **Hậu quả**: Bất kỳ người dùng hoặc trình phát frontend nào gọi vào `out.url` đều bị `404 Not Found`. Tham số `ttl=3600` chỉ là chuỗi ký tự trang trí, không có cơ chế ký số HMAC chống giả mạo hay kiểm tra hạn dùng.
- **Khắc phục**: Triển khai route `GET /v1/media/assets/{asset_id}/download` sử dụng `FileResponse`, kiểm tra quyền đọc của tenant, và xác thực chữ ký token thời hạn.

---

### F04. Lệch thư mục gốc lưu trữ giữa các module gây lỗi không tìm thấy tệp
- **Vị trí**: [`sin_content_api/src/modules/media_studio/service.py#L24-L26`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/service.py#L24-L26) đối chiếu [`security.py#L14`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/security.py#L14) và [`router.py#L194-L195`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L194-L195)
- **Vấn đề**:
  - `service.py`: Ghi tệp tải lên vào `03_ban_lam_viec/media_assets/workspaces/{ws_id}/media/...`
  - `security.py`: Định nghĩa `MEDIA_ROOT_DIR` trỏ về `03_ban_lam_viec/sin_content_api/data/media_storage/`.
  - `router.py`: Khi thực hiện lệnh mix âm thanh lại tìm file tại `MEDIA_ROOT_DIR / voice.storage_key`.
- **Hậu quả**: Hai đường dẫn lưu trữ khác nhau hoàn toàn. Khi người dùng upload giọng đọc qua API rồi truyền ID vào `/audio/mix`, hệ thống sẽ ném lỗi vì file không tồn tại trong thư mục mà `router.py` đang tìm kiếm.
- **Khắc phục**: Định nghĩa một đường dẫn thống nhất thông qua biến cấu hình `MEDIA_STORAGE_ROOT` chung cho toàn bộ dự án.

---

### F05. Chạy Playwright và FFmpeg đồng bộ trên Web Worker Thread gây nghẽn DoS máy chủ
- **Vị trí**: [`sin_content_api/src/modules/media_studio/router.py#L136`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L136), [`L166`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L166) và [`job_engine.py#L180-L208`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/job_engine.py#L180-L208)
- **Vấn đề**: Các hàm thực thi tạo nhạc, hòa âm ducking và chạy bot cào web đều là các hàm đồng bộ (synchronous). Khi client gửi request, FastAPI giữ kết nối HTTP mở và block worker thread suốt thời gian Playwright mở Chrome hoặc FFmpeg render.
- **Hậu quả**: Máy chủ chỉ cần tiếp nhận 3–4 yêu cầu tạo media cùng lúc sẽ bị cạn kiệt thread pool. Các API khác (đăng nhập, xem kịch bản, xem dashboard) sẽ bị nghẽn hoàn toàn và trả về lỗi 504 Gateway Timeout.
- **Khắc phục**: Toàn bộ thao tác chạy FFmpeg và gọi AI provider phải được đẩy vào hàng đợi tác vụ nền (Background Worker / Task Queue) với cơ chế giới hạn concurrency = 1 để bảo vệ tài nguyên máy chủ.

---

### F06. Job `GOOGLE_OFFICIAL` bị treo vĩnh viễn ở trạng thái `QUEUED`
- **Vị trí**: [`sin_content_api/src/modules/media_studio/job_engine.py#L149-L177`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/job_engine.py#L149-L177)
- **Vấn đề**: Trong hàm `submit_job()`, khi cấu hình provider là `GOOGLE_OFFICIAL` và có API key, hàm tạo job với trạng thái `QUEUED` rồi kết thúc hàm. Sau dòng code này, không hề có bất kỳ tiến trình hay hàm nào được kích hoạt để thực sự gọi API Google GenAI.
- **Hậu quả**: Client kiểm tra trạng thái job qua API `GET /v1/ai-jobs/{job_id}` sẽ thấy job mãi mãi ở trạng thái `QUEUED` mà không có kết quả đầu ra.
- **Khắc phục**: Xây dựng worker consumer chuyên biệt để lấy các job `QUEUED` và gọi API `@google/genai` hoặc `google-genai` thật.

---

### F07. Tham số `music_attenuation_db` bị bỏ rơi hoàn toàn trong Auto-Ducking
- **Vị trí**: [`sin_content_api/src/modules/media_studio/audio_processor.py#L92-L120`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/audio_processor.py#L92-L120)
- **Vấn đề**: Hàm `apply_auto_ducking(..., music_attenuation_db: float = -18.0)` khai báo tham số này, nhưng chuỗi filter của FFmpeg gán cứng:
  ```python
  filter_complex = (
      "[0:a][1:a]sidechaincompress="
      "threshold=0.12:ratio=4:attack=20:release=350[ducked];"
      "[ducked][1:a]amix=inputs=2:duration=first:dropout_transition=2[out]"
  )
  ```
- **Hậu quả**: Dù người dùng trên giao diện truyền vào `-6.0`, `-18.0` hay `-30.0` dB, âm lượng nhạc nền vẫn bị nén theo một tỷ lệ cố định không đổi.
- **Khắc phục**: Quy đổi tham số decibel sang giá trị threshold hoặc dùng filter `volume` để điều chỉnh âm lượng chính xác theo yêu cầu.

---

### F08. Tự ý đóng dấu `approval_state = "APPROVED"` vi phạm nguyên tắc Bốn Mắt
- **Vị trí**: [`sin_content_api/src/modules/media_studio/router.py#L221`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L221) và [`music_provider.py#L195`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/music_provider.py#L195)
- **Vấn đề**: Khi tạo bản nhạc hoặc tệp hòa âm mới, mã nguồn tự động gán `approval_state = "APPROVED"`.
- **Hậu quả**: Vi phạm nghiêm trọng nguyên tắc Bốn Mắt (Four-Eyes Principle / No Self-Approval) và quy định thẩm định bản quyền (Rights Gate) của BAHA Group. Tài sản truyền thông chưa qua kiểm duyệt chất lượng (QC) và rà soát quyền tác giả đã bị xem là hợp lệ để xuất bản.
- **Khắc phục**: Mặc định tài sản mới tạo phải ở trạng thái `UNREVIEWED`. Chỉ người có quyền `production.approve_final` độc lập mới được phép ký duyệt.

---

### F09. Hàm `probe_media_metadata` tính nhẩm thời lượng từ byte size thay vì dùng `ffprobe`
- **Vị trí**: [`sin_content_api/src/modules/media_studio/security.py#L179-L190`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/security.py#L179-L190)
- **Vấn đề**: Thay vì chạy lệnh `ffprobe` (đã được cài đặt sẵn trên máy chủ), hàm này tính thời lượng bằng công thức chia nhẩm:
  ```python
  estimated_duration_ms = max(int((byte_size / 16000) * 1000), 1000) if mime_type == "audio/mpeg" else 30000
  ```
- **Hậu quả**: Nếu người dùng tải lên file MP3 chất lượng cao (320kbps = 40KB/s), thời lượng lưu vào CSDL sẽ bị ước tính sai gấp 2.5 lần thực tế (ví dụ file 1 phút bị tính thành 2.5 phút), làm hỏng toàn bộ phép tính khớp nối timeline video 9:16.
- **Khắc phục**: Gọi hàm `audio_processor.probe_audio(filepath)` để lấy thời lượng và codec chuẩn xác từ luồng stream nhị phân.

---

### F10. Bộ lọc `amix=duration=first` phụ thuộc độ dài nhạc nền, gây cắt cụt lời thoại
- **Vị trí**: [`sin_content_api/src/modules/media_studio/audio_processor.py#L108`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/audio_processor.py#L108)
- **Vấn đề**: Bộ lọc hòa âm sử dụng `amix=inputs=2:duration=first`. Đầu vào đầu tiên `[0:a]` là file nhạc nền.
- **Hậu quả**: Nếu nhạc nền dài 5 giây mà lời đọc thuyết minh dài 20 giây, âm thanh xuất ra sẽ bị ngắt ngang ở giây thứ 5, làm mất 15 giây lời thoại của kịch bản. Ngược lại, nếu nhạc dài 3 phút còn lời đọc 15 giây, file sẽ thừa 2 phút 45 giây nhạc vô nghĩa.
- **Khắc phục**: Tính toán độ dài lớn nhất hoặc áp dụng cờ `-t` theo độ dài của kịch bản kết hợp hiệu ứng `afade` mượt mà ở đoạn kết thúc.

---

### F11. Vi phạm ranh giới kiến trúc: Dùng bot cào web Playwright thay vì quy trình Pro-Assisted
- **Vị trí**: [`03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/)
- **Vấn đề**: Bản kế hoạch gốc SSOT (`ke_hoach_tich_hop_media_studio.md`, Mục 2) cam kết luồng `SUBSCRIPTION_ASSISTED` là luồng người dùng tự thao tác trên giao diện web chính thức, hệ thống chỉ hỗ trợ sinh prompt và bộ nhập tệp uploader. Mã nguồn triển khai lại tự ý viết bot Playwright cào web tự động bằng profile Chrome có sẵn.
- **Hậu quả**: Rất dễ bị Google chặn bot, khóa tài khoản Pro, và vỡ luồng xử lý khi trang web thay đổi DOM selectors.
- **Khắc phục**: Trả tính năng về đúng bản chất: Luồng chính là giao diện người dùng tự nhập file tải về; công cụ Playwright chỉ lưu trữ ở thư mục công cụ ngoại vi và không nhúng vào luồng nghiệp vụ runtime.

---

### F12. Mã nguồn chết không có API Route (Dead Code)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/service.py#L106-L125`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/service.py#L106-L125)
- **Vấn đề**: Các thực thể `ProductionProject`, `ProductionTask`, `TimelineVersion`, `VoiceConsent`, `MediaQCResult` và hàm `create_project()` đã được viết nhưng không có bất kỳ router endpoint nào gọi đến.
- **Khắc phục**: Xây dựng router quản lý dự án sản xuất hoặc dọn dẹp để tránh phình to mã nguồn không sử dụng.

---

### F13. Gian lận tạo video Gemini Omni Flash & Google Flow bằng khung màu đơn sắc (Color Video)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/video_provider.py#L47-L77`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_provider.py#L47-L77) và [`video_provider.py#L98-L128`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_provider.py#L98-L128)
- **Hiện trạng mã nguồn**:
  ```python
  # Trong GoogleOfficialOmniProvider:
  cmd = [
      video_processor.ffmpeg_bin, "-y", "-f", "lavfi",
      "-i", "color=c=0x1E3A8A:s=1080x1920:d=4",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
      str(dest_path)
  ]
  subprocess.run(cmd, capture_output=True, check=True)
  return {
      "status": "SUCCEEDED",
      "provider": self.provider_id,
      "source_product": "GEMINI_OMNI_API",
      "actual_cost": 0.12,
      ...
  }
  ```
- **Vấn đề**: `GoogleOfficialOmniProvider` hoàn toàn không kết nối mô hình video `gemini-omni-1.1-flash`. Nó dùng lệnh `ffmpeg lavfi` sinh một video màu xanh biển trơn (`0x1E3A8A`) 4 giây, đóng dấu trạng thái `SUCCEEDED`, báo nguồn `GEMINI_OMNI_API`, và ghi sổ cái trừ tiền $0.12. Tương tự, `GoogleFlowZeroCostProvider` khi bắt ngoại lệ thất bại tự sinh video màu xám đen (`0x0F172A`) 3 giây rồi báo thành công 100%.
- **Hậu quả**: Khi người dùng yêu cầu tạo video B-roll (ví dụ "Flycam bãi biển lúc hoàng hôn"), hệ thống trả về một khung màu xám hoặc xanh trơn không có nội dung.
- **Khắc phục**: Trả về lỗi trung thực `NOT_IMPLEMENTED` hoặc `BLOCKED_CREDENTIALS` khi chưa có khóa API Google GenAI thật. Tuyệt đối không sinh video màu trơn để đánh lừa bài test.

---

### F14. Ảo giác kiểm định "Safe Zone TikTok" (Fake Safe Zone Compliance)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/video_processor.py#L62-L67`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_processor.py#L62-L67)
- **Hiện trạng mã nguồn**:
  ```python
  "safe_zone_tiktok": {
      "top_margin_px": 150,
      "bottom_margin_px": 320,
      "right_margin_px": 120,
      "is_compliant": is_vertical_9_16
  }
  ```
- **Vấn đề**: Báo cáo nghiệm thu khẳng định: *"Đo đạc Safe Zone TikTok: Đảm bảo vùng an toàn (Cách mép trên 150px, mép dưới 320px, mép phải 120px) không bị các nút tương tác che khuất"*. Nhưng trong code, hàm `probe_video` không hề phân tích hình ảnh, text hay phụ đề; nó chỉ kiểm tra `if is_vertical_9_16:` thì gán luôn `"is_compliant": True`!
- **Hậu quả**: Video dù có phụ đề bị đè sát mép dưới (bị thanh caption TikTok che) hay góc phải (bị nút Like/Share che) vẫn được hệ thống xác nhận bừa là "Đạt chuẩn Safe Zone", gây lỗi hiển thị nghiêm trọng khi xuất bản lên TikTok thật.
- **Khắc phục**: Nếu chưa có mô hình thị giác máy tính phát hiện text/overlay bounding box, phải trả về `is_compliant = None` (`UNVERIFIED_SAFE_ZONE`) hoặc gắn nhãn `REQUIRES_HUMAN_REVIEW`.

---

### F15. Lỗi kiến trúc ghép video FFmpeg Concat Demuxer và cắt cụt âm thanh với `-shortest`
- **Vị trí**: [`sin_content_api/src/modules/media_studio/video_processor.py#L84-L105`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_processor.py#L84-L105)
- **Hiện trạng mã nguồn**:
  ```python
  cmd = [
      self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
      "-i", str(concat_txt),
      "-i", str(audio_path),
      "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
      "-pix_fmt", "yuv420p", "-shortest",
      str(output_path)
  ]
  ```
- **Vấn đề**:
  1. Bộ ghép `-f concat` qua danh sách text yêu cầu **toàn bộ file video đầu vào phải có chung độ phân giải, framerate, và timebase**. Nếu ghép các video B-roll từ nhiều nguồn khác nhau (ví dụ một clip 30fps và một clip 24fps hoặc variable framerate), FFmpeg sẽ bị giật khung hình hoặc lệch tiếng nghiêm trọng.
  2. Tùy chọn `-shortest` sẽ tự động dừng video ngay khi luồng ngắn nhất kết thúc. Nếu tổng độ dài các scene video là 10 giây nhưng file âm thanh thuyết minh dài 30 giây, video kết quả sẽ bị cắt cụt ở giây thứ 10, làm mất 20 giây thuyết minh của kịch bản!
- **Khắc phục**: Dùng filter complex `scale/concat` (`[0:v]scale=1080:1920,setsar=1[v0]...concat=n=N:v=1:a=0`) để chuẩn hóa trước khi ghép, và căn chỉnh độ dài theo track âm thanh chính kết hợp freeze/loop khung hình cuối.

---

### F16. Lỗ hổng DoS khi Encode Video 1080x1920 đồng bộ trong Web Request
- **Vị trí**: [`sin_content_api/src/modules/media_studio/router.py#L266-L327`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L266-L327)
- **Vấn đề**: Endpoint `POST /v1/media/video/assemble` là synchronous def, gọi trực tiếp lệnh FFmpeg encode nhiều video 1080x1920 với `libx264`. Ngay trong bài test với clip mẫu 2 giây, thời gian chạy đã mất **45.74 giây**! Dưới tải thật (video 30–60s), một request sẽ ngốn 100% CPU trong 2–3 phút.
- **Hậu quả**: Web server FastAPI bị tê liệt hoàn toàn (DoS), rớt kết nối của toàn bộ người dùng khác trên hệ thống.
- **Khắc phục**: Bắt buộc chuyển `assemble_tiktok_video` sang hàng đợi tác vụ nền (Celery/Worker Queue), trả về `job_id` ngay lập tức để client polling tiến độ.

---

### F17. Tự ý đóng dấu `approval_state = "APPROVED"` cho video phân cảnh và video thành phẩm
- **Vị trí**: [`sin_content_api/src/modules/media_studio/video_provider.py#L168`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_provider.py#L168) và [`router.py#L342`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L342)
- **Vấn đề**: Video phân cảnh và video sau khi lắp ráp xong được code tự động gán `approval_state = "APPROVED"`.
- **Hậu quả**: Cho phép video thành phẩm bypass hoàn toàn cổng thẩm định của Content Lead / Reviewer, vi phạm nguyên tắc Bốn Mắt và rào chắn kiểm định bản quyền (Rights Gate) của BAHA Group.
- **Khắc phục**: Mặc định gán `approval_state = "UNREVIEWED"`. Chỉ khi có yêu cầu phê duyệt thông qua endpoint thẩm quyền riêng mới được đổi trạng thái sang `APPROVED`.

---

## 3. CHI TIẾT TỪNG PHÁT HIỆN

### F01. Gian lận tạo nhạc Lyria và Flow Music bằng tiếng bíp đơn âm (Sine Wave)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/music_provider.py#L46-L65`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/music_provider.py#L46-L65) và [`music_provider.py#L104-L115`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/music_provider.py#L104-L115)
- **Hiện trạng mã nguồn**:
  ```python
  # Trong GoogleOfficialMusicProvider:
  cmd = [
      audio_processor.ffmpeg_bin, "-y", "-f", "lavfi",
      "-i", "sine=frequency=523.25:duration=6",
      "-ar", "44100", "-b:a", "192k", str(dest_path)
  ]
  subprocess.run(cmd, capture_output=True, check=True)
  return {
      "status": "SUCCEEDED",
      "source_product": "LYRIA_API",
      "actual_cost": 0.05,
      ...
  }
  ```
- **Vấn đề**: `GoogleOfficialMusicProvider` hoàn toàn không gọi Google GenAI Interactions API (`lyria-3.5`). Thay vào đó, nó chạy FFmpeg sinh một tiếng bíp tần số 523.25Hz dài 6 giây, nhưng lại báo cáo `SUCCEEDED`, nguồn `LYRIA_API`, và ghi sổ cái trừ tiền $0.05. Tương tự, `FlowMusicZeroCostProvider` bắt ngoại lệ rộng và âm thầm sinh tiếng bíp 440Hz dài 5 giây rồi báo thành công.
- **Hậu quả**: Người dùng yêu cầu tạo bài hát Pop/Acoustic nhưng nhận về một tiếng bíp chói tai. Toàn bộ tính năng nhạc AI là giả tạo ("ảo giác").
- **Khắc phục**: Khi chưa có SDK/Credential của Lyria, bắt buộc trả về trạng thái lỗi `BLOCKED_CREDENTIALS` hoặc ngoại lệ `NotImplementedError`. Nghiêm cấm tạo file âm thanh giả rồi gán mác thành công.

---

### F02. Google Flow Client và Flow Music Client sinh byte rỗng khi thất bại
- **Vị trí**: [`cong_cu_tu_dong/flow_bridge/flow_music_client.py#L118-L127`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/flow_music_client.py#L118-L127) và [`google_flow_client.py#L100-L120`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/google_flow_client.py#L100-L120)
- **Hiện trạng mã nguồn**:
  ```python
  if not download_file_path or not download_file_path.exists():
      fallback_filename = f"flowmusic_{uuid.uuid4().hex[:12]}_output.mp3"
      dest_path = target_dir / fallback_filename
      dummy_mp3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" + b"\x00" * 32000
      dest_path.write_bytes(dummy_mp3)
      download_file_path = dest_path
  ```
- **Vấn đề**: Khi kịch bản cào web bằng Playwright thất bại hoặc timeout (do mạng chậm, CAPTCHA, chưa đăng nhập), bot không báo lỗi mà tự sinh một tệp chứa 32.000 byte số 0 (`\x00`) rồi coi đó là bài hát tải về thành công.
- **Hậu quả**: Cơ sở dữ liệu và ổ cứng NAS bị lấp đầy bởi các file rác không thể phát được, trong khi hệ thống vẫn ghi nhận job hoàn tất 100%.
- **Khắc phục**: Xóa bỏ hoàn toàn cơ chế fallback sinh dummy bytes. Nếu không tải được file từ web, ném ngoại lệ rõ ràng để chuyển trạng thái job sang `FAILED`.

---

### F03. Thiếu Endpoint tải tệp (Download URL dẫn tới 404)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/router.py#L58`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L58), [`L73`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L73), [`L86`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L86), [`L163`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L163), [`L228`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L228)
- **Hiện trạng mã nguồn**:
  ```python
  out = MediaAssetOut.model_validate(asset)
  out.url = f"/v1/media/assets/{asset.id}/download?ttl=3600"
  return out
  ```
- **Vấn đề**: Trong toàn bộ router `media_router`, chỉ có các route: `POST /upload`, `GET /assets`, `GET /assets/{asset_id}`, `POST /music/generate`, `POST /audio/mix`. Hoàn toàn không có route xử lý `GET /assets/{asset_id}/download`.
- **Hậu quả**: Bất kỳ người dùng hoặc trình phát frontend nào gọi vào `out.url` đều bị `404 Not Found`. Tham số `ttl=3600` chỉ là chuỗi ký tự trang trí, không có cơ chế ký số HMAC chống giả mạo hay kiểm tra hạn dùng.
- **Khắc phục**: Triển khai route `GET /v1/media/assets/{asset_id}/download` sử dụng `FileResponse`, kiểm tra quyền đọc của tenant, và xác thực chữ ký token thời hạn.

---

### F04. Lệch thư mục gốc lưu trữ giữa các module gây lỗi không tìm thấy tệp
- **Vị trí**: [`sin_content_api/src/modules/media_studio/service.py#L24-L26`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/service.py#L24-L26) đối chiếu [`security.py#L14`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/security.py#L14) và [`router.py#L194-L195`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L194-L195)
- **Vấn đề**:
  - `service.py`: Ghi tệp tải lên vào `03_ban_lam_viec/media_assets/workspaces/{ws_id}/media/...`
  - `security.py`: Định nghĩa `MEDIA_ROOT_DIR` trỏ về `03_ban_lam_viec/sin_content_api/data/media_storage/`.
  - `router.py`: Khi thực hiện lệnh mix âm thanh lại tìm file tại `MEDIA_ROOT_DIR / voice.storage_key`.
- **Hậu quả**: Hai đường dẫn lưu trữ khác nhau hoàn toàn. Khi người dùng upload giọng đọc qua API rồi truyền ID vào `/audio/mix`, hệ thống sẽ ném lỗi vì file không tồn tại trong thư mục mà `router.py` đang tìm kiếm.
- **Khắc phục**: Định nghĩa một đường dẫn thống nhất thông qua biến cấu hình `MEDIA_STORAGE_ROOT` chung cho toàn bộ dự án.

---

### F05. Chạy Playwright và FFmpeg đồng bộ trên Web Worker Thread gây nghẽn DoS máy chủ
- **Vị trí**: [`sin_content_api/src/modules/media_studio/router.py#L136`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L136), [`L166`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L166) và [`job_engine.py#L180-L208`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/job_engine.py#L180-L208)
- **Vấn đề**: Các hàm thực thi tạo nhạc, hòa âm ducking và chạy bot cào web đều là các hàm đồng bộ (synchronous). Khi client gửi request, FastAPI giữ kết nối HTTP mở và block worker thread suốt thời gian Playwright mở Chrome hoặc FFmpeg render.
- **Hậu quả**: Máy chủ chỉ cần tiếp nhận 3–4 yêu cầu tạo media cùng lúc sẽ bị cạn kiệt thread pool. Các API khác (đăng nhập, xem kịch bản, xem dashboard) sẽ bị nghẽn hoàn toàn và trả về lỗi 504 Gateway Timeout.
- **Khắc phục**: Toàn bộ thao tác chạy FFmpeg và gọi AI provider phải được đẩy vào hàng đợi tác vụ nền (Background Worker / Task Queue) với cơ chế giới hạn concurrency = 1 để bảo vệ tài nguyên máy chủ.

---

### F06. Job `GOOGLE_OFFICIAL` bị treo vĩnh viễn ở trạng thái `QUEUED`
- **Vị trí**: [`sin_content_api/src/modules/media_studio/job_engine.py#L149-L177`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/job_engine.py#L149-L177)
- **Vấn đề**: Trong hàm `submit_job()`, khi cấu hình provider là `GOOGLE_OFFICIAL` và có API key, hàm tạo job với trạng thái `QUEUED` rồi kết thúc hàm. Sau dòng code này, không hề có bất kỳ tiến trình hay hàm nào được kích hoạt để thực sự gọi API Google GenAI.
- **Hậu quả**: Client kiểm tra trạng thái job qua API `GET /v1/ai-jobs/{job_id}` sẽ thấy job mãi mãi ở trạng thái `QUEUED` mà không có kết quả đầu ra.
- **Khắc phục**: Xây dựng worker consumer chuyên biệt để lấy các job `QUEUED` và gọi API `@google/genai` hoặc `google-genai` thật.

---

### F07. Tham số `music_attenuation_db` bị bỏ rơi hoàn toàn trong Auto-Ducking
- **Vị trí**: [`sin_content_api/src/modules/media_studio/audio_processor.py#L92-L120`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/audio_processor.py#L92-L120)
- **Vấn đề**: Hàm `apply_auto_ducking(..., music_attenuation_db: float = -18.0)` khai báo tham số này, nhưng chuỗi filter của FFmpeg gán cứng:
  ```python
  filter_complex = (
      "[0:a][1:a]sidechaincompress="
      "threshold=0.12:ratio=4:attack=20:release=350[ducked];"
      "[ducked][1:a]amix=inputs=2:duration=first:dropout_transition=2[out]"
  )
  ```
- **Hậu quả**: Dù người dùng trên giao diện truyền vào `-6.0`, `-18.0` hay `-30.0` dB, âm lượng nhạc nền vẫn bị nén theo một tỷ lệ cố định không đổi.
- **Khắc phục**: Quy đổi tham số decibel sang giá trị threshold hoặc dùng filter `volume` để điều chỉnh âm lượng chính xác theo yêu cầu.

---

### F08. Tự ý đóng dấu `approval_state = "APPROVED"` vi phạm nguyên tắc Bốn Mắt
- **Vị trí**: [`sin_content_api/src/modules/media_studio/router.py#L221`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L221) và [`music_provider.py#L195`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/music_provider.py#L195)
- **Vấn đề**: Khi tạo bản nhạc hoặc tệp hòa âm mới, mã nguồn tự động gán `approval_state = "APPROVED"`.
- **Hậu quả**: Vi phạm nghiêm trọng nguyên tắc Bốn Mắt (Four-Eyes Principle / No Self-Approval) và quy định thẩm định bản quyền (Rights Gate) của BAHA Group. Tài sản truyền thông chưa qua kiểm duyệt chất lượng (QC) và rà soát quyền tác giả đã bị xem là hợp lệ để xuất bản.
- **Khắc phục**: Mặc định tài sản mới tạo phải ở trạng thái `UNREVIEWED`. Chỉ người có quyền `production.approve_final` độc lập mới được phép ký duyệt.

---

### F09. Hàm `probe_media_metadata` tính nhẩm thời lượng từ byte size thay vì dùng `ffprobe`
- **Vị trí**: [`sin_content_api/src/modules/media_studio/security.py#L179-L190`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/security.py#L179-L190)
- **Vấn đề**: Thay vì chạy lệnh `ffprobe` (đã được cài đặt sẵn trên máy chủ), hàm này tính thời lượng bằng công thức chia nhẩm:
  ```python
  estimated_duration_ms = max(int((byte_size / 16000) * 1000), 1000) if mime_type == "audio/mpeg" else 30000
  ```
- **Hậu quả**: Nếu người dùng tải lên file MP3 chất lượng cao (320kbps = 40KB/s), thời lượng lưu vào CSDL sẽ bị ước tính sai gấp 2.5 lần thực tế (ví dụ file 1 phút bị tính thành 2.5 phút), làm hỏng toàn bộ phép tính khớp nối timeline video 9:16.
- **Khắc phục**: Gọi hàm `audio_processor.probe_audio(filepath)` để lấy thời lượng và codec chuẩn xác từ luồng stream nhị phân.

---

### F10. Bộ lọc `amix=duration=first` phụ thuộc độ dài nhạc nền, gây cắt cụt lời thoại
- **Vị trí**: [`sin_content_api/src/modules/media_studio/audio_processor.py#L108`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/audio_processor.py#L108)
- **Vấn đề**: Bộ lọc hòa âm sử dụng `amix=inputs=2:duration=first`. Đầu vào đầu tiên `[0:a]` là file nhạc nền.
- **Hậu quả**: Nếu nhạc nền dài 5 giây mà lời đọc thuyết minh dài 20 giây, âm thanh xuất ra sẽ bị ngắt ngang ở giây thứ 5, làm mất 15 giây lời thoại của kịch bản. Ngược lại, nếu nhạc dài 3 phút còn lời đọc 15 giây, file sẽ thừa 2 phút 45 giây nhạc vô nghĩa.
- **Khắc phục**: Tính toán độ dài lớn nhất hoặc áp dụng cờ `-t` theo độ dài của kịch bản kết hợp hiệu ứng `afade` mượt mà ở đoạn kết thúc.

---

### F11. Vi phạm ranh giới kiến trúc: Dùng bot cào web Playwright thay vì quy trình Pro-Assisted
- **Vị trí**: [`03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/cong_cu_tu_dong/flow_bridge/)
- **Vấn đề**: Bản kế hoạch gốc SSOT (`ke_hoach_tich_hop_media_studio.md`, Mục 2) cam kết luồng `SUBSCRIPTION_ASSISTED` là luồng người dùng tự thao tác trên giao diện web chính thức, hệ thống chỉ hỗ trợ sinh prompt và bộ nhập tệp uploader. Mã nguồn triển khai lại tự ý viết bot Playwright cào web tự động bằng profile Chrome có sẵn.
- **Hậu quả**: Rất dễ bị Google chặn bot, khóa tài khoản Pro, và vỡ luồng xử lý khi trang web thay đổi DOM selectors.
- **Khắc phục**: Trả tính năng về đúng bản chất: Luồng chính là giao diện người dùng tự nhập file tải về; công cụ Playwright chỉ lưu trữ ở thư mục công cụ ngoại vi và không nhúng vào luồng nghiệp vụ runtime.

---

### F12. Mã nguồn chết không có API Route (Dead Code)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/service.py#L106-L125`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/service.py#L106-L125)
- **Vấn đề**: Các thực thể `ProductionProject`, `ProductionTask`, `TimelineVersion`, `VoiceConsent`, `MediaQCResult` và hàm `create_project()` đã được viết nhưng không có bất kỳ router endpoint nào gọi đến.
- **Khắc phục**: Xây dựng router quản lý dự án sản xuất hoặc dọn dẹp để tránh phình to mã nguồn không sử dụng.

---

### F13. Gian lận tạo video Gemini Omni Flash & Google Flow bằng khung màu đơn sắc (Color Video)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/video_provider.py#L47-L77`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_provider.py#L47-L77) và [`video_provider.py#L98-L128`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_provider.py#L98-L128)
- **Hiện trạng mã nguồn**:
  ```python
  # Trong GoogleOfficialOmniProvider:
  cmd = [
      video_processor.ffmpeg_bin, "-y", "-f", "lavfi",
      "-i", "color=c=0x1E3A8A:s=1080x1920:d=4",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
      str(dest_path)
  ]
  subprocess.run(cmd, capture_output=True, check=True)
  return {
      "status": "SUCCEEDED",
      "provider": self.provider_id,
      "source_product": "GEMINI_OMNI_API",
      "actual_cost": 0.12,
      ...
  }
  ```
- **Vấn đề**: `GoogleOfficialOmniProvider` hoàn toàn không kết nối mô hình video `gemini-omni-1.1-flash`. Nó dùng lệnh `ffmpeg lavfi` sinh một video màu xanh biển trơn (`0x1E3A8A`) 4 giây, đóng dấu trạng thái `SUCCEEDED`, báo nguồn `GEMINI_OMNI_API`, và ghi sổ cái trừ tiền $0.12. Tương tự, `GoogleFlowZeroCostProvider` khi bắt ngoại lệ thất bại tự sinh video màu xám đen (`0x0F172A`) 3 giây rồi báo thành công 100%.
- **Hậu quả**: Khi người dùng yêu cầu tạo video B-roll (ví dụ "Flycam bãi biển lúc hoàng hôn"), hệ thống trả về một khung màu xám hoặc xanh trơn không có nội dung.
- **Khắc phục**: Trả về lỗi trung thực `NOT_IMPLEMENTED` hoặc `BLOCKED_CREDENTIALS` khi chưa có khóa API Google GenAI thật. Tuyệt đối không sinh video màu trơn để đánh lừa bài test.

---

### F14. Ảo giác kiểm định "Safe Zone TikTok" (Fake Safe Zone Compliance)
- **Vị trí**: [`sin_content_api/src/modules/media_studio/video_processor.py#L62-L67`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_processor.py#L62-L67)
- **Hiện trạng mã nguồn**:
  ```python
  "safe_zone_tiktok": {
      "top_margin_px": 150,
      "bottom_margin_px": 320,
      "right_margin_px": 120,
      "is_compliant": is_vertical_9_16
  }
  ```
- **Vấn đề**: Báo cáo nghiệm thu khẳng định: *"Đo đạc Safe Zone TikTok: Đảm bảo vùng an toàn (Cách mép trên 150px, mép dưới 320px, mép phải 120px) không bị các nút tương tác che khuất"*. Nhưng trong code, hàm `probe_video` không hề phân tích hình ảnh, text hay phụ đề; nó chỉ kiểm tra `if is_vertical_9_16:` thì gán luôn `"is_compliant": True`!
- **Hậu quả**: Video dù có phụ đề bị đè sát mép dưới (bị thanh caption TikTok che) hay góc phải (bị nút Like/Share che) vẫn được hệ thống xác nhận bừa là "Đạt chuẩn Safe Zone", gây lỗi hiển thị nghiêm trọng khi xuất bản lên TikTok thật.
- **Khắc phục**: Nếu chưa có mô hình thị giác máy tính phát hiện text/overlay bounding box, phải trả về `is_compliant = None` (`UNVERIFIED_SAFE_ZONE`) hoặc gắn nhãn `REQUIRES_HUMAN_REVIEW`.

---

### F15. Lỗi kiến trúc ghép video FFmpeg Concat Demuxer và cắt cụt âm thanh với `-shortest`
- **Vị trí**: [`sin_content_api/src/modules/media_studio/video_processor.py#L84-L105`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_processor.py#L84-L105)
- **Hiện trạng mã nguồn**:
  ```python
  cmd = [
      self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
      "-i", str(concat_txt),
      "-i", str(audio_path),
      "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
      "-pix_fmt", "yuv420p", "-shortest",
      str(output_path)
  ]
  ```
- **Vấn đề**:
  1. Bộ ghép `-f concat` qua danh sách text yêu cầu **toàn bộ file video đầu vào phải có chung độ phân giải, framerate, và timebase**. Nếu ghép các video B-roll từ nhiều nguồn khác nhau (ví dụ một clip 30fps và một clip 24fps hoặc variable framerate), FFmpeg sẽ bị giật khung hình hoặc lệch tiếng nghiêm trọng.
  2. Tùy chọn `-shortest` sẽ tự động dừng video ngay khi luồng ngắn nhất kết thúc. Nếu tổng độ dài các scene video là 10 giây nhưng file âm thanh thuyết minh dài 30 giây, video kết quả sẽ bị cắt cụt ở giây thứ 10, làm mất 20 giây thuyết minh của kịch bản!
- **Khắc phục**: Dùng filter complex `scale/concat` (`[0:v]scale=1080:1920,setsar=1[v0]...concat=n=N:v=1:a=0`) để chuẩn hóa trước khi ghép, và căn chỉnh độ dài theo track âm thanh chính kết hợp freeze/loop khung hình cuối.

---

### F16. Lỗ hổng DoS khi Encode Video 1080x1920 đồng bộ trong Web Request
- **Vị trí**: [`sin_content_api/src/modules/media_studio/router.py#L266-L327`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L266-L327)
- **Vấn đề**: Endpoint `POST /v1/media/video/assemble` là synchronous def, gọi trực tiếp lệnh FFmpeg encode nhiều video 1080x1920 với `libx264`. Ngay trong bài test với clip mẫu 2 giây, thời gian chạy đã mất **45.74 giây**! Dưới tải thật (video 30–60s), một request sẽ ngốn 100% CPU trong 2–3 phút.
- **Hậu quả**: Web server FastAPI bị tê liệt hoàn toàn (DoS), rớt kết nối của toàn bộ người dùng khác trên hệ thống.
- **Khắc phục**: Bắt buộc chuyển `assemble_tiktok_video` sang hàng đợi tác vụ nền (Celery/Worker Queue), trả về `job_id` ngay lập tức để client polling tiến độ.

---

### F17. Tự ý đóng dấu `approval_state = "APPROVED"` cho video phân cảnh và video thành phẩm
- **Vị trí**: [`sin_content_api/src/modules/media_studio/video_provider.py#L168`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_provider.py#L168) và [`router.py#L342`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py#L342)
- **Vấn đề**: Video phân cảnh và video sau khi lắp ráp xong được code tự động gán `approval_state = "APPROVED"`.
- **Hậu quả**: Cho phép video thành phẩm bypass hoàn toàn cổng thẩm định của Content Lead / Reviewer, vi phạm nguyên tắc Bốn Mắt và rào chắn kiểm định bản quyền (Rights Gate) của BAHA Group.
- **Khắc phục**: Mặc định gán `approval_state = "UNREVIEWED"`. Chỉ khi có yêu cầu phê duyệt thông qua endpoint thẩm quyền riêng mới được đổi trạng thái sang `APPROVED`.

---

## 4. GIẢI MÃ NGUYÊN NHÂN TOÀN BỘ 30/30 TESTS BÁO PASS 100%

Toàn bộ 4 suite kiểm thử (`test_media_studio_p1.py`, `test_media_studio_music.py`, `test_media_studio_video.py`, `test_media_studio_budget_gf05.py`) với 30 bài test đều báo kết quả 100% PASS vì 4 cơ chế ảo giác kỹ thuật:

1. **Sử dụng Mock tự chế (Tautological Mocking)**: 
   - Các bài kiểm thử B03, B06, B07, GF05-03, GF05-05 chỉ kiểm thử lớp giả lập `FAKE_PROVIDER`. Khi truyền `simulate_error = "TIMEOUT_UNCERTAIN_BILL"`, chính code mock tự trả về `"needs_reconciliation": True` để bài test assert đạt, hoàn toàn không kiểm tra năng lực giao tiếp với thế giới bên ngoài hay downstream providers thật.
2. **Khẳng định nông cạn (Shallow Assertions)**: 
   - Test GF04-06 (nhạc) và GF03-02 (video) chỉ kiểm tra `resp.status_code == 200` và `"download" in data["url"]`. Các bài test **hoàn toàn không bao giờ gửi request GET tới đường link đó**, do đó bỏ lọt lỗ hổng router bị thiếu endpoint download dẫn đến HTTP 404!
3. **Che giấu lỗi bằng tiếng bíp và khung màu đơn sắc (Color/Sine Fallback)**:
   - Khi chạy test trong môi trường CI/offline không có Playwright hoặc Google account, hàm tạo nhạc rơi vào khối `except:` rồi âm thầm dùng FFmpeg sinh tiếng bíp 5 giây; hàm tạo video sinh khung màu xanh/xám trơn 3–4 giây. Bài test thấy có file MP3/MP4 sinh ra và `id is not None` nên vội vàng xác nhận PASS mà không nhận ra đó là dữ liệu hoàn toàn giả mạo.
4. **Kiểm tra phiên và cờ tính năng bằng biến môi trường ngụy tạo**:
   - Bài test `test_gf05_07` và `test_gf05_08` tự set `os.environ["FLOW_SESSION_REVOKED"] = "true"` và `os.environ["FLOW_PILOT_ENABLED"] = "false"`, rồi gọi API kiểm tra đúng các biến môi trường đó. Bài test tự kiểm tra chính mình mà không có bất kỳ tương tác nào với phiên đăng nhập trình duyệt hay token thật.

---

## 5. KẾT LUẬN & KIẾN NGHỊ HÀNH ĐỘNG

Bộ mã nguồn Phân hệ Media Studio và gói bổ sung Google Flow (Zero-Cost) **CHƯA SẴN SÀNG VẬN HÀNH (NOT PRODUCTION READY)**. 

### Quyết định của Ban Đánh Giá Độc Lập:
1. **BÁC BỎ TOÀN BỘ KẾT QUẢ NGHIỆM THU CỦA CHECKPOINT `CP02_MEDIA_STUDIO_FLOW_INTEGRATED`**.
2. **YÊU CẦU ĐÌNH CHỈ VIỆC TRIỂN KHAI SANG CÁC PHA TIẾP THEO** cho đến khi toàn bộ 15 lỗi Must Fix được khắc phục triệt để.

### Lộ trình 6 bước khắc phục bắt buộc:
1. **Dọn dẹp mã giả lập**: Gỡ bỏ toàn bộ logic tự sinh tiếng bíp (sine wave), khung màu trơn và byte rỗng khi thất bại; trả về mã lỗi trung thực (`BLOCKED_CREDENTIALS` / `DOWNSTREAM_ERROR`).
2. **Bổ sung endpoint tải file**: Viết router `GET /v1/media/assets/{asset_id}/download` hoàn chỉnh kèm xác thực chữ ký token có thời hạn (Signed URL TTL) và phân tách tenant để phục hồi trình phát trên giao diện người dùng.
3. **Đồng nhất đường dẫn lưu trữ**: Thống nhất biến cấu hình `MEDIA_STORAGE_ROOT` trỏ về một thư mục SSOT duy nhất trên máy chủ.
4. **Tách biệt luồng nền**: Đưa FFmpeg render và tác vụ AI sang Background Worker độc lập, tuyệt đối không chạy đồng bộ trong request handler của FastAPI để chống DoS.
5. **Khắc phục lỗ hổng bảo mật Profile Chrome**: Di chuyển thư mục lưu trữ profile trình duyệt khỏi ổ chia sẻ mạng NAS; mã hóa và cô lập quyền truy cập tài khoản.
6. **Xây dựng cơ chế kiểm tra phiên và đối soát thật**: Thay thế việc đọc biến môi trường `os.getenv` bằng cơ chế kiểm tra token/cookie thật và bộ phân loại lỗi mạng downstream trung thực.
