# Kết quả dọn dữ liệu kiểm thử và nghiệm thu

Ngày thực hiện: 2026-10-27

## Dữ liệu đã dọn

- Đã xóa dữ liệu phát sinh trong `sin_content_e2e_test.db` và `baha_auth_e2e_test.db`; giữ nguyên cấu trúc 42 và 19 bảng. Kiểm tra sau dọn: mỗi cơ sở dữ liệu có 0 bản ghi và SQLite `integrity_check` trả về `ok`.
- Trước khi xóa, đã sao lưu hai cơ sở dữ liệu và cách ly 99 tệp media chỉ được tham chiếu bởi dữ liệu kiểm thử, tổng cộng 430.113.946 byte. Bản sao, media cách ly và manifest SHA-256 nằm tại `03_ban_lam_viec/sin_content_api/scratch/data_test_backup_20261027/`.
- Đã chuyển bốn tệp nguồn TypeScript chứa dữ liệu/dịch vụ giả cũ khỏi mã ứng dụng, lưu tại `03_ban_lam_viec/docs/data_mock_da_cach_ly_20261027/`. Thư mục có README giải thích mục đích lưu giữ.
- Đã loại dữ liệu demo mặc định và các chỉ số giả khỏi giao diện/kết nối kênh. Khi chưa có số liệu đã xác minh, giao diện để trống; mã xác thực không còn token, email hay mật khẩu mẫu được nhúng sẵn.
- API không tự gán số người theo dõi, số video, lượt xem hồ sơ hoặc số 0 khi TikTok không trả số liệu. Phần đăng TikTok trực tiếp vẫn chưa tích hợp và nút thao tác được vô hiệu hóa.

## Kết quả kiểm tra

- Build giao diện: đạt; Next.js biên dịch thành công và sinh đủ 43 trang tĩnh.
- Kiểm thử hồi quy cho dữ liệu số liệu kênh thiếu: 3 đạt, 0 lỗi.
- Khởi chạy ở chế độ kiểm thử: API `/healthz`, `/readyz` và giao diện `/dashboard`, `/channels`, `/publishing` đều trả HTTP 200. Dịch vụ thử nghiệm đã được dừng sau kiểm tra.
- Toàn bộ kiểm thử backend: 427 đạt, 7 lỗi, 10 cảnh báo. Cùng 7 ca lỗi này đã xuất hiện trong lượt chạy trước khi hoàn tất việc dọn; không kết luận toàn bộ bộ kiểm thử đã đạt.

Các ca lỗi còn lại:

1. `tests/test_flow_login_launcher.py::test_linux_flow_login_starts_session_manager`
2. `tests/test_flow_login_launcher.py::test_linux_flow_login_reuses_existing_session`
3. `tests/test_google_flow_download_correlation.py::test_localized_flow_agent_editor_is_accepted_without_legacy_video_mode_menu`
4. `tests/test_google_flow_download_correlation.py::test_flow_video_mode_selects_requested_portrait_ratio`
5. `tests/test_khoi_tao_du_an_flow.py::test_flow_editor_initialization_reloads_same_project_once_before_failing`
6. `tests/test_media_studio_video.py::test_content_video_plan_calls_llm_and_persists_reviewable_storyboard`
7. `tests/test_tts_provider_vieneu.py::test_vieneu_clone_uses_reference_denoising_and_sdk_sample_rate`

## Bằng chứng

- Build giao diện: `ket_qua_build_giao_dien_20261027.txt`.
- Kiểm thử backend cuối: `ket_qua_kiem_thu_backend_sau_don_20261027.txt`.
- Kết quả build và smoke test: `kiem_thu_khoi_dong_che_do_kiem_thu_20261027.json`.
- Lượt kiểm thử trước đó: `ket_qua_kiem_thu_backend_luot_dau_20261027.txt`.
- Sao lưu cơ sở dữ liệu, media cách ly và manifest: `03_ban_lam_viec/sin_content_api/scratch/data_test_backup_20261027/`.
- Mã nguồn mock đã cách ly: `03_ban_lam_viec/docs/data_mock_da_cach_ly_20261027/`.

## Giới hạn còn lại

Build và kiểm tra khởi chạy đạt. Bộ kiểm thử backend vẫn còn 7 lỗi nêu trên; cần xử lý riêng trước khi dùng kết quả đó làm cổng phát hành. Đăng TikTok trực tiếp chưa được hỗ trợ.
