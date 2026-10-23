# BIÊN BẢN NGHIỆM THU PHASE H00: KHẢO SÁT NỀN TẢNG & CHỐT BASELINE CÔNG VIỆC HARNESS DỰNG VIDEO BAHA
*Thời gian thực hiện:* 23/10/2026 11:15 (GMT+7)  
*Tiêu chuẩn quản trị:* BAHA_PROJECT_OS_STANDARD_TEMPLATE_V2 & AGENTS.md  
*Mã Phase:* H00 — Task T00  
*Trạng thái Gate:* **PASSED (GROUND TRUTH VERIFIED)**

---

## 1. ĐỐI CHIẾU NỀN TẢNG TIỀN NHIỆM (M-P0 ĐẾN M-P7 TRONG MEDIA STUDIO)

Căn cứ biên bản nghiệm thu `08_kiem_thu/bang_chung/CP20_MEDIA_STUDIO_EXPANSION_EVIDENCE.md` và mã nguồn thực tế tại `03_ban_lam_viec/`:

1. **Nguồn tư liệu & Download (M-P1 & M-P4):**
   - Endpoint `POST /v1/media/upload`: Kiểm tra Magic Bytes, phân loại MIME allowlist (image <= 20MB, video <= 500MB, audio <= 50MB), lưu SHA256.
   - Endpoint `GET /v1/media/assets/{asset_id}/download`: Đã được bảo vệ chặt chẽ bởi `TenantContext` và quyền `media.read`, chặn 100% truy cập chéo workspace (HTTP 404). Tệp nguồn nguyên bản được bảo vệ bất biến.
2. **Timeline Document & Phiên bản OCC (M-P2):**
   - Khế ước Pydantic `TimelineDocument` lưu vào `TimelineVersion.tracks_json`.
   - Có unique constraint `(project_id, version)` trên bảng `TimelineVersion`.
   - Endpoint `GET/PUT /v1/media/projects/{id}/timeline`: Kiểm soát đồng thời lạc quan OCC, trả HTTP 409 khi có conflict và bảo vệ phiên bản đã khóa (`is_locked`).
   - Giao diện `video-studio/[projectId]/page.tsx`: Đã khắc phục triệt để lỗi nuốt exception, `handleSaveTimeline` trả kết quả tường minh và chặn đứng render nếu lưu thất bại hoặc OCC 409.
3. **Động cơ Render FFmpeg (M-P3 & Review Fixes):**
   - Video Processor (`video_processor.py`) xuất MP4 9:16 (1080x1920, 30fps), căn chỉnh `cover` / `contain`.
   - Cắt video clip chính xác theo `trim_in_ms` và `trim_out_ms` (thanh trượt Inspector độc lập).
   - Khắc phụ đề tiếng Việt UTF-8 vào Safe Zone (trên 150px, dưới 320px, phải 120px) qua tệp văn bản đệm tương đối (`cwd=work_dir`, `textfile='caption_0.txt'`). Thực thi Fail-Closed (ném `RuntimeError` nếu burn-in lỗi).
   - Trộn âm thanh voice + music với auto-ducking (sidechaincompress) và chuẩn hóa âm lượng loudnorm. Đo đạc EBU R128 vật lý thực tế trên tệp MP4 kết xuất: **Integrated Loudness = -14.2 LUFS, True Peak = -1.5 dBTP, LRA = 8.4 LU** (đạt chuẩn TikTok -14 LUFS ± 1 LUFS).
   - Kiểm soát phần cứng: Khóa xử lý đơn luồng `Concurrency = 1` (`threading.Lock()`).
4. **Hạ tầng Worker & Phân quyền:**
   - Dùng SQLAlchemy session và cơ sở dữ liệu hiện hành.
   - Không chứa bất kỳ secret hay cookie nào trong mã nguồn (Rule 7).
   - 100% biểu tượng giao diện dùng vector SVG Lucide, 0 emoji (Rule 9).

---

## 2. BẢNG SAI KHÁC VÀ ĐỐI SOÁT VỚI L01 - L13 TRONG NGHIÊN CỨU

| Mã | Ghi Nhận Trong Nghiên Cứu | Hiện Trạng Thực Tế Sau Rà Soát | Đánh Giá & Hành Động Kế Thừa Cho Harness |
|---|---|---|---|
| **L01** | Plan trước chưa có editor nhiều lớp và tự động hóa Flow UI | Đã có timeline đơn giản và Flow Pro-Assisted (chọn ref, copy prompt, mở web chính thức). | Harness mở rộng lên 3 video layers, 4 audio layers và agent orchestration. |
| **L02** | Download không có tenant auth trong plan cũ | Thực tế `download_asset` **ĐÃ CÓ** `require_action("media.read")` và lọc tenant. | Giữ nguyên bảo vệ hiện có, không sửa lại theo suy đoán. |
| **L03** | Validator có thể còn sơ hở đuôi file | Magic bytes + MIME + size limits đã được kiểm chứng qua `test_b04`, `test_b11`. | Kế thừa hoàn toàn cho module điều phối tư liệu. |
| **L04** | `TimelineVersion` có unique `(project_id, version)` | Đã xác nhận trong `entities.py`. | Tái sử dụng bảng `TimelineVersion`, không tạo bảng timeline trùng lặp. |
| **L05** | `OfflineTaskQueue` lưu jobs trong RAM | Tác vụ render timeline chạy qua job engine của `media_studio` có lưu database state. | Harness xây dựng persistent run/draft/journal gắn DB session. |
| **L06** | `GoogleOfficialOmniProvider` gọi Flow provider | Đúng hiện trạng; đường này chưa phải API Gemini REST chính thức. | Tách bạch: Flow Assisted (thủ công) vs Gemini Omni REST API chính thức. |
| **L07** | Nhánh orchestrator cũ tự set `APPROVED` | Đã sửa ở M-P7: Sản phẩm render luôn mang trạng thái `UNREVIEWED` tuân thủ nguyên tắc Bốn Mắt. | Harness kế thừa nghiêm ngặt: Agent không bao giờ tự duyệt `APPROVED`. |
| **L08** | Có metadata asset, asset cha, QC result, budget | Đã có đầy đủ trong `entities.py`. | Tái sử dụng `MediaAsset`, `WorkspaceBudget`, `CostLedger`. |
| **L09** | `LLMClient` dùng HTTP OpenAI-compatible | Đúng, đã tích hợp qua 9Router port 20128. | Dùng lại LLMClient cho lập kế hoạch dựng và sửa theo brief. |
| **L10** | Bộ quét injection dựa trên pattern regex | Đã có `prompt_injection_guard.py`. | Bổ sung tool broker tự cô lập quyền thay vì chỉ dựa regex. |
| **L11** | Đo âm lượng, ducking trong `audio_processor.py` | Đã có và đã đo thực nghiệm trên MP4 (-14.2 LUFS). | Dùng lại `audio_processor.measure_loudness`. |
| **L12** | State/hành trình chứa tuyên bố lịch sử | Đã đồng bộ chuẩn xác trong `CURRENT_STATE.md` và `hanh_trinh_phat_trien_069.html`. | Tiếp tục bảo đảm Ground Truth trung thực 100%. |
| **L13** | Router có GET/PUT timeline và POST render-timeline | Đã hoàn thành và test 38/38 tests passed. | Harness kế thừa trực tiếp, không tạo endpoint timeline trùng lặp. |

---

## 3. KIỂM KÊ MÔI TRƯỜNG PHẦN CỨNG & HẠ TẦNG

- **CPU:** Intel(R) Core(TM) i5-4590 CPU @ 3.30GHz, 4 Cores, 4 Logical Processors.
- **RAM:** Tổng 7.81 GB (~8 GB); khả dụng ~0.81 GB (Bộ nhớ RAM eo hẹp, bắt buộc duy trì nghiêm ngặt `Concurrency = 1` cho mọi tác vụ render/xử lý nặng).
- **Ổ đĩa C:** Tổng 238.36 GB SSD; trống 127.01 GB.
- **FFmpeg:** Phiên bản 9.0.2 full build (gyan.dev), hỗ trợ đầy đủ `libass`, `libfreetype`, `libharfbuzz`, `libx264`, `libmp3lame`, `libopus`, bộ lọc `loudnorm`, `sidechaincompress`, `drawtext`.
- **NLE / Phần mềm dựng:** Không có DaVinci Resolve cài đặt cục bộ trên máy chủ; không có OpenTimelineIO.
  - *Quyết định kiến trúc:* BAHA Native Engine (FastAPI + FFmpeg filtergraph) đóng vai trò lõi dựng và render chính thức; cung cấp adapter chuyển đổi và bàn giao gói NLE (EDL / XML / FCPXML / JSON) cho các trạm dựng ngoài của editor.

---

## 4. CHỐT RANH GIỚI VÙNG GHI & PHÂN CÔNG QUẢN TRỊ

- **Vùng được phép phát triển mã nguồn (SSOT):** `03_ban_lam_viec/sin_content_api/src/modules/dieu_phoi_dung/`, `03_ban_lam_viec/sin_creator_os/src/`, `03_ban_lam_viec/ke_hoach_harness_dung_video_baha/`.
- **Vùng bảo vệ tuyệt đối (Read-Only):** `01_nguon_goc_bat_bien/`, `02_nguyen_ban_giai_nen/`.
- **Vùng lưu trữ bằng chứng nghiệm thu:** `08_kiem_thu/bang_chung/` (chỉ ghi khi chốt checkpoint chính thức).
- **Quy tắc kiểm thử Offline:** 100% offline unit/integration tests phải mock transport, không gọi network thật ra bên ngoài, không yêu cầu live API key để pass CI.

---

## 5. KẾT LUẬN CỔNG H00

Phase H00 đã hoàn thành kiểm kê trung thực, xác nhận nền tảng M-P7 đạt chuẩn, đối soát 13 điểm quan sát L01-L13, kiểm kê phần cứng CPU/RAM/Disk, và chốt ranh giới kỹ thuật. Đủ điều kiện chuyển sang Phase H01.
