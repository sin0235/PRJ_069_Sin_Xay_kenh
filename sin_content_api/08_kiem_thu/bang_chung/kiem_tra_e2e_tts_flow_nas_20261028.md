# Kiểm tra E2E TTS và Flow trên NAS

Ngày 28-10-2026. Công việc đang thực hiện, chưa nghiệm thu E2E.

- Tác vụ TTS `de39bcc3-96af-4616-a195-3ae13a332aaa` trạng thái FAILED. Log DSM lúc 14:38 xác nhận `FileNotFoundError: ffprobe` tại `audio_processor.probe_audio`; model đã đến bước kiểm tra WAV.
- Image API cũ `kiem-thu-nas10` thiếu ffprobe. Dockerfile SSOT cài FFmpeg; đã đổi tag API thành `kiem-thu-nas11` và bắt đầu build trên DSM. Chưa kết luận build thành công.
- Kiểm thử cục bộ Voice Studio, provider, harness và Flow: 23 đạt. Pipeline video: 68 đạt. Nhóm media/video/Flow: 66 đạt, 3 lỗi; một fixture storyboard thiếu phân loại cảnh, hai test selector Flow không khớp. Chưa đối chiếu UI Flow thật.
- Đã tải bản phát hành Linux x64 v0.6.5-demo của Veo Watermark Remover; SHA-256 archive khớp `958a8f429208848af55d461754a841d5c5703301a61ac66d045831c5a9622654`, kiểm tra CRC đạt. Chưa chạy binary Linux. Nguồn: https://github.com/allenk/VeoWatermarkRemover/releases/tag/v0.6.5-demo .
- Wrapper báo sai `watermark_removed=True` khi không phát hiện logo. Đã sửa trạng thái này trong SSOT; ba kiểm thử mục tiêu đạt. Chưa triển khai wrapper vào image API; pipeline video hiện bỏ qua bước xóa logo.
- API dùng profile Flow khác volume đăng nhập và mặc định dùng msedge; Dockerfile chưa cài browser. `profile_guard.py` xóa khóa nên không nối profile đăng nhập trước khi giải quyết khóa và xác minh container đăng nhập đã dừng.
- Đề xuất đổi phiên/tài khoản: `03_ban_lam_viec/ha_tang/nas_flow_login/de_xuat_quan_ly_phien_flow_nas.md`.

## Cập nhật kiểm tra ngày 28-10-2026

- Build API trước đó lỗi vì thiếu hai tệp của `09_kiem_thu_quyen` trong build context `03_ban_lam_viec`. Đã sao chép hai tệp vào context và so sánh SHA-256 với bản gốc: cả hai trùng khớp.
- Container Manager build image `prj069-sin-api:kiem-thu-nas11` thành công, ghi Exit Code 0 và khởi động API, FE. Kiểm tra HTTP: `/healthz` 200 và `/voice-studio` 200.
- Job TTS `7a825eab-2d00-4212-9969-d3148c60a66c` đang RUNNING, chưa có tệp audio khi kiểm tra; chưa chứng minh TTS thành công. Một tệp mã API có thay đổi trong lúc job đang chạy và chế độ reload có thể ảnh hưởng tiến trình, cần đối soát job trước khi thử lại.
- Bản chuẩn bị phiên Flow gồm khóa liên tiến trình, kiểm tra tên hồ sơ và cấu hình thử nghiệm riêng. `pytest tests/test_khoa_phien_flow.py`: 17 passed trên Windows; bộ hồi quy liên quan trước đó 29 passed. Chưa kiểm thử khóa Linux giữa container, chưa dựng image Flow, chưa đăng nhập Google, chưa triển khai giao diện chọn phiên và chưa có E2E hai tài khoản.
- Cấu hình thử nghiệm: `03_ban_lam_viec/ha_tang/nas_kiem_thu_that/docker-compose.phien_flow.yml`; cấu hình stack đang chạy vẫn dùng nas11. Không kích hoạt cấu hình Flow thử nghiệm khi chưa kiểm tra runtime và giao diện.

## Đối soát job TTS 15:19 ngày 28-10-2026

- Nhật ký API: 15:11 StatReload phát hiện thay đổi `src/modules/media_studio/router.py`, dừng server process 9; 15:12 khởi chạy server process 189. Thay đổi do Codex thực hiện khi job đang xử lý.
- Worker dùng lease chung 480 giây; khi lấy lại lease có cơ chế đưa job VOICE_STUDIO đang RUNNING về QUEUED để chạy lại. Job `7a825eab-2d00-4212-9969-d3148c60a66c` sau đó trả SUCCEEDED, asset `asset-3192882daa0d`.
- Đã tải audio từ endpoint asset: WAV PCM, 1 kênh, 48.000 Hz, 3,04 giây, 145.920 mẫu, dữ liệu âm thanh có giá trị khác 0. Bằng chứng: `tts_kiem_tra_7a825eab.wav`. Chưa kiểm tra bằng nghe nội dung.

## Chuẩn bị phiên Flow trên NAS lúc 15:44 ngày 28-10-2026

- Container `prj069_flow_login` đã build image `prj069-flow-login:1.63.0-nas3`; log ghi Chromium đã khởi động. Người dùng xác nhận đã đăng nhập và đóng Chromium. Phiên lưu trong volume `prj069_flow_profiles`, không nằm trong image.
- Project build riêng đã tạo image `prj069-sin-api:kiem-thu-nas12`, Playwright 1.63.0 và Chromium Linux; Container Manager ghi build thành công, Exit Code 0. Image chưa thay thế API chính.
- Lần kiểm tra profile đầu tiên thất bại vì tệp script bind vào container không có quyền đọc; đã chỉnh cấu hình thử lại bằng cách đọc với root rồi hạ quyền sang appuser. Chưa có kết quả kiểm tra hoặc screenshot. Container Manager hiển thị container cũ không còn tồn tại, chưa xác minh được kết quả container mới.
- API chính nhiều lần không trả `/healthz`; Container Manager báo health check timeout, NAS báo CPU 84–99%. Đã restart riêng API theo yêu cầu xử lý lỗi 500: `/healthz` từng trả 200, sau đó lại timeout; job clone `c3b29455-cefb-4294-9bdc-59dcb5659767` từng vẫn báo RUNNING. Chưa xác định nguyên nhân nghẽn, không khẳng định do TTS hay build.
- Chưa nối giao diện chọn phiên, chưa kiểm thử khóa liên container Linux hoặc tạo video Flow, chưa áp dụng cấu hình thử nghiệm lên API chính.
