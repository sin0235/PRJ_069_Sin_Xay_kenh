# BẢN ÁNH XẠ ENGINE & ĐỊNH HƯỚNG TÍCH HỢP NLE (PHASE H02)
*Thời gian ban hành:* 23/10/2026 11:45 (GMT+7)  
*Tiêu chuẩn quản trị:* BAHA_PROJECT_OS_STANDARD_TEMPLATE_V2 & AGENTS.md  
*Mã Phase:* H02 — Task T02  
*Trạng thái Gate:* **H02-ENGINE PASSED &bull; H02-PROVIDER OFFLINE-CONTRACT FROZEN (STANDBY LIVE KEYS)**

---

## 1. ĐỐI SOÁT & QUYẾT ĐỊNH LỰA CHỌN ENGINE DỰNG VÀ HẬU KỲ

| Ứng Viên | Giấy Phép | Khả Năng Thực Tế Trên Môi Trường BAHA (CPU i5, RAM 8GB) | Kết Luận Thẩm Định |
|---|---|---|---|
| **BAHA Native Engine (FastAPI + FFmpeg CPU)** | Bản quyền nội bộ BAHA Group | Chạy thực tế 100%, kiểm thử 38/38 tests passed. Render H.264/AAC 1080x1920 30fps mượt mà, hỗ trợ burn-in phụ đề tiếng Việt có dấu, auto-ducking và đo đạc EBU R128 (-14.2 LUFS). Không đòi hỏi GPU, tiêu thụ RAM thấp, an toàn tuyệt đối. | **ĐƯỢC CHỌN LÀM ENGINE CHÍNH (PRIMARY SSOT ENGINE)** |
| **FableCut** | MIT (Commit `f130cd3c5485af7682c0f8f6ff680599a38b66ba`) | Kiến trúc patch ops (split, trim, ripple, slip, insert, overwrite) rất tốt. Tuy nhiên phiên bản web có cờ `force` có thể ghi đè khóa và thiếu xác thực tenancy. | **KẾ THỪA Ý TƯỞNG THIẾT KẾ SCHEMA PATCH OPS VÀO BAHA NATIVE ENGINE**; không kéo cả repo ngoài vào SSOT. |
| **OpenChatCut** | AGPL-3.0-or-later (Commit `7fa4b7903e7ebecf832a36249f0c0c755200cc17`) | Xung đột giấy phép AGPL với mã nguồn đóng SaaS của BAHA. Hơn nữa, chứa dependency tải mô hình AI cục bộ (whisper-cli, MediaPipe) vi phạm nghiêm ngặt Non-negotiable Requirement 2. | **REJECTED (TỪ CHỐI TÁI SỬ DỤNG MÃ)**; chỉ tham khảo mô hình draft review session và QA verification logic. |
| **DaVinci Resolve Studio** | Thương mại (Blackmagic Design) | Không cài đặt trực tiếp trên máy chủ backend (CPU i5-4590 không có card GPU chuyên dụng). Editor hoàn thiện màu sắc trên trạm dựng cá nhân riêng. | **ĐƯỢC CHỌN LÀM NLE FINISHING THÔNG QUA ADAPTER BÀN GIAO GÓI DỰ ÁN (EXCHANGE BUNDLE)**. |

---

## 2. QUY CHUẨN DANH MỤC THAO TÁC CỐT LÕI (CALLABLE EDITING OPS)

Toàn bộ các thao tác điều phối dựng được thực thi qua tập lệnh chuẩn `LenhDung` với schema định kiểu nghiêm ngặt (typed payload):

| Mã Thao Tác (`type`) | Tham Số Đầu Vào Bắt Buộc | Miền Giá Trị Hợp Lệ (Range) | Hành Vi & Readback Kiểm Chứng |
|---|---|---|---|
| `split_clip` | `track_id: str, clip_id: str, split_time_ms: int` | `split_time_ms` nằm giữa `[start_ms + 100, end_ms - 100]` | Chia 1 clip thành 2 clips độc lập, giữ nguyên source map và linked captions. |
| `trim_clip` | `track_id: str, clip_id: str, trim_in_ms: int, trim_out_ms: int` | `0 <= trim_in_ms < trim_out_ms`, thời lượng tối thiểu 500ms | Cắt gọt đầu/cuối của clip, cập nhật thời lượng phân cảnh chính xác. |
| `insert_clip` | `track_id: str, asset_id: str, at_time_ms: int, duration_ms: int` | `duration_ms > 0`, asset phải thuộc cùng workspace | Chèn clip mới vào timeline, đẩy các clip phía sau sang phải (ripple insert). |
| `overwrite_clip` | `track_id: str, asset_id: str, at_time_ms: int, duration_ms: int` | `duration_ms > 0`, asset tồn tại và hợp lệ | Ghi đè lên timeline tại vị trí chỉ định, không làm thay đổi tổng thời lượng nếu cùng độ dài. |
| `ripple_delete` | `track_id: str, clip_id: str` | Clip tồn tại trên track | Xóa clip và tự động kéo toàn bộ các clip phía sau về trước, đồng bộ cả track âm thanh/caption liên kết. |
| `slip_clip` | `track_id: str, clip_id: str, slip_delta_ms: int` | Không vượt quá độ dài tệp gốc của asset | Giữ nguyên vị trí và độ dài clip trên timeline nhưng dịch chuyển cửa sổ thời gian nguồn (source in/out). |
| `set_clip_gain` | `track_id: str, clip_id: str, gain_db: float` | `[-60.0, +12.0]` dB | Điều chỉnh âm lượng clip âm thanh, kiểm tra không gây bể tiếng (True Peak <= -1.5 dBTP). |
| `set_caption_text` | `caption_id: str, text: str, safe_zone: bool` | Text UTF-8 tiếng Việt không rỗng, tối đa 2 dòng | Cập nhật phụ đề tiếng Việt sắc nét, định vị vào Safe Zone TikTok. |
| `apply_color_lut` | `track_id: str, clip_id: str, lut_asset_id: str` | Tệp LUT `.cube` hợp lệ trong workspace | Áp dụng bảng màu điện ảnh cho phân cảnh đã chọn. |
| `set_retime_speed` | `track_id: str, clip_id: str, speed_ratio: float` | `[0.25, 4.0]`, float hữu hạn dương | Thay đổi tốc độ phát clip (slow-motion hoặc fast-forward), map PTS nguồn chính xác. |

---

## 3. CƠ CHẾ GIAO TIẾP VÀ BÀN GIAO NLE (NLE ROUNDTRIP)

Khi dự án chuyển sang trạng thái `representation_mode = "NATIVE_BOUND"`:
1. **Xuất gói bàn giao (`GoiBanGiao`):**
   - Tạo thư mục gói chứa: Bản sao hoặc symlink tệp media nguồn, tệp mô tả timeline Final Cut XML / EDL, tệp JSON metadata BAHA, và báo cáo tổn thất hiệu ứng `loss_report.json`.
2. **Editor xử lý trên NLE:**
   - Editor mở dự án trên DaVinci Resolve, tinh chỉnh color grading, âm thanh chuyên sâu.
3. **Nhập lại và sửa tiếp:**
   - Hệ thống ghi nhận `native_project_asset_id` và mã băm SHA256 của file dự án native đã sửa.
   - Khi Agent tiếp tục sửa các thao tác được hỗ trợ (như chỉnh lời thoại caption, đổi volume nhạc nền), engine sẽ thực thi đồng bộ và giữ nguyên lớp màu sắc native đã được Editor phê duyệt.
