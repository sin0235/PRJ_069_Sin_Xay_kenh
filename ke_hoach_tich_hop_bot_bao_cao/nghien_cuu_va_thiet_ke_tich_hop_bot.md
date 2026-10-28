# NGHIÊN CỨU & THIẾT KẾ TÍCH HỢP BOT BÁO CÁO TIẾN ĐỘ CUỐI BUỔI
# DỰ ÁN: PRJ_069_Sin_Xay_kenh (HỆ THỐNG XÂY DỰNG & PHÁT TRIỂN KÊNH TIKTOK SIN)
# THAM CHIẾU: PRJ_021 (BÁO CÁO & KIỂM SOÁT HIỆU SUẤT NHÂN VIÊN) VÀ PRJ_011 (TỔNG HÀNH DINH AI)

- **Mã tài liệu:** `PRJ069-BOT-INTEGRATION-STUDY-01`
- **Ngày lập:** 28/10/2026
- **Kỹ sư phụ trách:** Trịnh Công Sơn (Sin / @sin0235)
- **Người nhận báo cáo:** Sếp Nguyễn Cảnh Diệu (@dieubaha, Telegram ID: `7775586213`)
- **Trạng thái:** HOÀN THÀNH NGHIÊN CỨU & ĐÃ THIẾT LẬP CÔNG CỤ TÍCH HỢP

---

## I. TỔNG QUAN VÀ MỤC TIÊU NGHIÊN CỨU

Hệ thống `PRJ_069_Sin_Xay_kenh` đang trong giai đoạn phát triển tích cực với các module xử lý video đa cảnh, sinh phụ đề tự động (Faster-Whisper), giọng đọc AI (Gwen-TTS / VieNeu) và kết nối Google Flow.

Để đảm bảo Sếp Nguyễn Cảnh Diệu (@dieubaha) luôn nắm bắt chính xác tiến độ thực tế theo thời gian thực (Ground Truth) mà không cần phải vào server kiểm tra thủ công, dự án tiến hành nghiên cứu cơ chế thông báo điều hành từ `PRJ_021_bao_cao_kiem_soat_hieu_suat_nhan_vien` để xây dựng công cụ báo cáo tiến độ tự động cuối buổi / cuối ngày.

---

## II. KẾT QUẢ KHẢO SÁT HỆ THỐNG PRJ_021 & PRJ_011

Qua rà soát chuyên sâu mã nguồn và tài liệu kiến trúc tại `Z:\01_du_an\PRJ_021_bao_cao_kiem_soat_hieu_suat_nhan_vien`:

### 1. Danh tính Bot Điều Hành Chuẩn (Bot Identity SSOT)
- **Bot hợp lệ duy nhất:** `@BAHA_DieuHanh_bot` (Numeric Bot ID: `8684276925`).
- **Bot chấm công nghiêm cấm:** `Baha_ChamCongBot` (Numeric Bot ID: `8660244994`).
  *Mã nguồn PRJ_021 đã cài đặt chốt chặn fail-closed `PROHIBITED_BOT_REJECTED` để ngăn ngừa việc gửi nhầm bot.*
- **Ranh giới kênh nhận:**
  - Người nhận hợp lệ: Nguyễn Cảnh Diệu (Founder / CEO), Telegram ID `7775586213`, username `@dieubaha`.
  - Loại chat bắt buộc: `private` (1-1 trực tiếp).
  - Nghiêm cấm gửi vào các nhóm/supergroup có ID âm (như nhóm `-5485402333`), mã chặn `GROUP_RECIPIENT_REJECTED`.

### 2. Điểm Nguồn Chân Lý Dữ Liệu Nghiệp Vụ (Business SSOT)
- Cơ sở dữ liệu tập trung đặt trên NAS tại:  
  `Z:\01_du_an\PRJ_021_bao_cao_kiem_soat_hieu_suat_nhan_vien\07_du_lieu\baha_baocao.db` (SQLite WAL mode).
- Bảng quản lý dự án: `project_registry` đã có đăng ký chính thức:
  - `project_code`: `PRJ_069`
  - `project_name`: `Sin Xay Kenh`
  - `canonical_path`: `//192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh`
- Bảng tài khoản nhân sự:
  - `id`: `usr-emp-5553`
  - `username`: `son.trinh`
  - `full_name`: `Trịnh Công Sơn`
  - `department`: `it`
- Bảng lưu báo cáo ngày: `daily_reports` và `daily_report_items`.
- Bảng hàng đợi thông báo: `notifications_outbox`.

### 3. Hạ Tầng Vận Chuyển Thông Báo (Transport Engine)
- PRJ_011 đóng vai trò cổng gateway Telegram.
- Cổng tiếp nhận webhook n8n trên NAS đang hoạt động tại cổng 5678:  
  `http://192.168.1.175:5678/webhook/prj011-gateway-webhook` (đã kiểm tra kết nối TCP thành công).
- Hoặc phát trực tiếp qua Telegram Bot API với bot `@BAHA_DieuHanh_bot` (`8684276925`).

### 4. Chính Sách Chống Nhiễu (Anti-Noise Policy)
- Không spam tin lẻ, không gửi tin vụn vặt khi lưu nháp.
- Mỗi cuối buổi/cuối ngày chỉ gửi 1 bản tin báo cáo tiến độ tổng hợp rõ ràng:
  - Tên dự án và ca làm việc.
  - Các hạng mục đã hoàn thành có bằng chứng đối soát.
  - Tình trạng checkpoint và hạ tầng kỹ thuật.
  - Điểm nghẽn (Blockers) nếu có và phương án đề xuất hỗ trợ.
  - Kế hoạch cụ thể cho ca tiếp theo.

---

## III. THIẾT KẾ KIẾN TRÚC TÍCH HỢP VÀO PRJ_069

Dựa trên các phát hiện trên, hệ thống báo cáo tiến độ cuối buổi của `PRJ_069` được thiết kế theo mô hình 3 tầng độc lập nhưng kết nối đồng bộ:

```
[PRJ_069 Workspace]
  |-- 00_bat_dau/CURRENT_STATE.md (Nội dung ca làm việc mới nhất)
  |-- 00_bat_dau/CHECKPOINT.json  (Mã mốc phục hồi hiện hành)
  |-- Git Working Tree & Logs     (Thống kê commit / file sửa đổi)
  |-- Runtime Health Probe        (Next.js: 3000, API: 8000/8001, 9Router: 20128)
       |
       v
[Bộ Thu Thập & Biên Soạn Tiến Độ: bao_cao_tien_do_cuoi_buoi.py]
  - Chuẩn hóa nội dung 100% tiếng Việt
  - Tuân thủ Rule 9: Tuyệt đối không dùng emoji, dùng thẻ văn bản [PRJ_069], [TIEN DO], [DIEM NGHEN]
       |
       +---> Kênh 1: Đồng bộ trực tiếp vào CSDL tập trung PRJ_021 (baha_baocao.db)
       |             -> Tạo daily_reports, daily_report_items, notifications_outbox
       |             -> Hiển thị trên Dashboard điều hành https://bc.bahagroup.vn
       |
       +---> Kênh 2: Gửi trực tiếp tin nhắn điều hành tới Telegram của Sếp
       |             -> Recipient: 7775586213 (@dieubaha)
       |             -> Sender: @BAHA_DieuHanh_bot (8684276925) / PRJ_011 n8n Gateway
       |
       +---> Kênh 3: Chế độ Xem trước an toàn (Dry-Run Preview)
                     -> Cho phép kỹ sư kiểm tra nội dung trước khi phát lệnh
```

---

## IV. BẢNG MẪU BÁO CÁO TIẾN ĐỘ CHUẨN (KHÔNG DÙNG EMOJI)

Định dạng tin nhắn báo cáo gửi Sếp Nguyễn Cảnh Diệu tuân thủ nghiêm ngặt quy định không dùng icon/emoji:

```text
[PRJ_069 - BAO CAO TIEN DO CUOI BUOI]
========================================
Du an: PRJ_069 - He Thong Xay Dung & Phat Trien Kenh TikTok Sin
Nhan su phu trach: Trinh Cong Son (Sin / usr-emp-5553)
Nguoi nhan: Sep Nguyen Canh Dieu (@dieubaha)
Thoi gian bao cao: 2026-10-28 17:30 (Asia/Ho_Chi_Minh)
Moc Checkpoint: CP22_OWNER_LLM_9ROUTER

[HANG MUC DA HOAN TAT TRONG CA]
- 1. Nghien cuu va tich hop thanh cong co che bao cao tu PRJ_021 vao PRJ_069.
- 2. Thiet lap cong cu tu dong tong hop tien do bao_cao_tien_do_cuoi_buoi.py.
- 3. Khoi tao loi tat 1-cham 00_GUI_BAO_CAO_TIEN_DO_CHO_SEP.cmd tai thu muc goc.

[TINH TRANG HA TANG & RUNTIME]
- Frontend Studio: Port 3000 [HOAT DONG]
- Backend Content API: Port 8000/8001 [HOAT DONG]
- AI Gateway 9Router: Port 20128 [HOAT DONG]
- Google Flow Bridge: Ket noi profile Chromium san sang tren NAS

[DIEM NGHEN & CAN HO TRO]
- Khong co diem nghan ky thuat gay dung tien do.

[KE HOACH BUOI TIEP THEO]
- Tiep tuc trien khai hoan thien pipeline render video tu dong va dong bo NAS.
========================================
He thong dieu hanh tu dong PRJ_069 & PRJ_021
```

---

## V. CÁC ĐIỂM CHỐT CHẶN AN TOÀN (GUARDRAILS)

1. **Chặn lộ lọt bí mật (No Secrets in Repo):**
   Token bot Telegram tuyệt đối không hardcode trong mã nguồn. Script hỗ trợ nạp từ biến môi trường `TELEGRAM_BOT_TOKEN`, file `.env`, hoặc tham số truyền vào phiên làm việc.
2. **Chặn sai lệch đối tượng (Strict Recipient Guard):**
   Hệ thống kiểm tra xác thực ID người nhận phải là `7775586213` (Nguyễn Cảnh Diệu). Từ chối mọi yêu cầu phát vào ID nhóm hoặc người dùng lạ.
3. **Tính lặp an toàn (Idempotency):**
   Báo cáo sinh ra có gắn khóa `idempotency_key` theo mã ngày và phiên bản `v{n}`, đảm bảo chạy lại nhiều lần không sinh bản ghi rác.
4. **Chuẩn hiển thị (SVG & Pure Text Only):**
   100% văn bản gửi qua Telegram và giao diện không chứa emoji, không chứa ký tự null byte gây lỗi encode.
