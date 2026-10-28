# Bằng chứng E2E tạo video AI và email

Ngày kiểm tra: 2026-10-24

## Kết quả

- Run `86e4f5e1-6eef-4b01-89e4-190c157145c9` hoàn tất với trạng thái `COMPLETED`, QC `PASS`; cả 7 cảnh đều `SUCCEEDED`.
- Video MP4: `03_ban_lam_viec/media_assets/workspaces/default_ws/media/content_video_86e4f5e1-6eef-4b01-89e4-190c157145c9_v3.mp4`.
- Gói xuất: `03_ban_lam_viec/media_assets/workspaces/default_ws/media/content_video_86e4f5e1-6eef-4b01-89e4-190c157145c9_v3_export.zip`; kiểm tra ZIP không có lỗi.
- SHA-256 MP4: `8b211e7a05003c2799f003f3bfaf695458caa2bb3fc642c81c0f852570e4b5f7`; khớp bản ghi asset `asset-c82035966e82` trong DB test.
- Ảnh xem trước ba cảnh: `anh_xem_truoc_e2e_ai_email_20261024.png`.

## Luồng ảnh liên tục

- Provider giữ nguồn Flow 16:9 riêng với tên `flow_source_16_9_<mã>.mp4`; runner trích khung hình nối cảnh từ nguồn này, không từ bản đã mở rộng 9:16.
- Đã xác nhận có nguồn Flow cho cả 7 asset cảnh.
- Flow hiện có thể tải ảnh tham chiếu chậm. Bridge chờ nút upload theo selector DOM `button.sidebar-upload-btn`, chờ chip composer trước khi thử nút thêm dự phòng, và chờ chip tối đa 15 giây.
- Run cũ `e25cd6ba-01b0-43d1-89fb-d6884285cb0b` được giữ nguyên trạng thái chặn trước khi gửi cảnh 5; run mới bắt đầu từ cảnh 1 để áp dụng luồng ảnh đúng cho toàn video.

## QC thành phẩm

- Kích thước 1080 × 1920, tỷ lệ 9:16, 30 fps, thời lượng 60 giây.
- Video H.264, âm thanh AAC stereo 44,1 kHz.
- Âm lượng tích hợp: -14,13 LUFS; true peak: -1,49 dBTP; QC âm thanh đạt.
- Giải mã, kích thước, codec, tốc độ khung hình và thời lượng đều đạt; không có lỗi QC.
- API `/readyz` và giao diện `/auth/v1/login` trả HTTP 200 sau khi hoàn tất.

## Kiểm thử hồi quy

- 7 kiểm thử liên quan đến giữ nguồn Flow gốc, trích khung hình liên tục, upload ảnh và gắn chip composer đạt.
- `py_compile` và rà soát diff không có lỗi định dạng.

## Phạm vi lưu bằng chứng

Báo cáo và ảnh xem trước nằm trong vùng ghi `03_ban_lam_viec`. Không ghi vào `08_kiem_thu/bang_chung` hoặc sửa trang hành trình vì nằm ngoài vùng ghi Codex theo quy tắc dự án. Checkpoint CP22 giữ nguyên. Hai cơ sở dữ liệu dùng cho E2E là bản test riêng; DB nghiệp vụ chính không được chạy migration trong lần kiểm tra này.
