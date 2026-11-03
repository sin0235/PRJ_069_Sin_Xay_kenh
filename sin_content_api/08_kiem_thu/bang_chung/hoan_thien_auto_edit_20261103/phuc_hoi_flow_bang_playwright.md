# Phục hồi cảnh Flow bằng Playwright CLI

Ngày 03/11/2026, Founder yêu cầu dùng skill Playwright. Đã đọc skill và kiểm tra npx, dùng playwright-cli đã cài, session doi_soat_flow.

- Trước mở: phiên API cũ INTERRUPTED/FLOW_SESSION_WORKER_RESTARTED; không có tiến trình Edge dùng profile Flow. Mở lại đúng thư mục profile cố định qua --persistent --profile, không tạo/copy profile hoặc cookie. Trang provider hiện tài khoản đã đăng nhập và gói PRO.
- Từ snapshot danh sách dự án, mở dự án 16:51: https://flow.google.com/project/9641e15e-70e6-4e67-9df3-d80830433472 . Prompt trên giao diện mô tả 20 đơn giấy đã quyết toán cạnh bảng tính trống, đúng nội dung cảnh e8696e28-7c0b-45db-8453-2e8f831731bb bị gián đoạn.
- Video đã tồn tại tại /edit/07b07d05-d765-41ab-8246-107927644564. Nhấn tải bản gốc 720p, không nhấn tạo mới, upscale hoặc gửi prompt.
- Đã tải MP4 về runtime/flow_canh_don_hang_v4.mp4, 720x1280, có audio, 10,026667 giây. SHA-256: 4297ac14453a8df7bb068bb6794c8ac6faa1f7c987593dc4f3a62246e4ed0d29.
- Đây là cảnh nguồn Flow đã phục hồi, chưa gỡ watermark, chưa đăng ký/đối soát kết quả vào hàng đợi sản phẩm, chưa ghép thành MP4 hoàn chỉnh. Không dùng cảnh này thay video quay gốc hoặc báo đạt nghiệm thu.
- Session CLI đang mở đúng dự án để tiếp tục đối soát. Snapshot CLI có thể chứa thông tin tài khoản nên giữ local, không commit toàn thư mục .playwright-cli.
