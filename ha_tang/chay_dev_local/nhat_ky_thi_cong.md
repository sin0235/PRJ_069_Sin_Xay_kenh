# Nhật ký thi công: chuyển dev local và kiểm thử từ xa

Kế hoạch: ke_hoach_chuyen_dev_local_va_kiem_thu_tu_xa_20261103.md.
Nhánh: dev/local-remote-video-tests. Nền ban đầu: b316d02.

- Xác nhận worktree local đã cách ly; không tạo checkout thứ hai.
- Máy có 8 GB RAM, khoảng 2,3 GB trống; Docker daemon chưa chạy. Không bật Docker vì có thể làm cạn RAM; triển khai native trước, cấu hình Compose vẫn được chuẩn bị cho môi trường đủ tài nguyên.
- Cloudflared service đang chạy; dùng token quản lý từ xa. Chưa đổi route.
- Checkout Git thiếu 28 file/thay đổi hiện có trong nguồn SSOT, bao gồm nhánh worker Auto Edit. Đã nhập nguyên trạng các thay đổi mã video và Remotion từ SSOT, giữ nguyên Whisper incremental hiện tại; commit baseline riêng trước khi sửa pipeline từ xa. Không đổi mã RBAC của các agent khác.
- Đã thêm store task bền vững, token theo task, lease/fencing, retry chunk có đối chiếu nội dung và kiểm tra hash kết quả. Bốn test tập trung đạt, gồm ký OIDC RSA thật và thử sai repo/ref/audience/signature.
- Quyết định: queue remote dùng SQLite riêng trong MEDIA_ROOT_DIR/.remote do BE quản lý, tránh can thiệp schema nghiệp vụ khi đang chuyển môi trường. Không chia sẻ DB này cho runner.
- Đang thi công tiếp client/runner và cấu hình native. Chưa có kết quả triển khai đầu-cuối; chưa render 8 GB.
