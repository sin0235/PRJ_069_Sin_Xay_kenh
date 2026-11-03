# Phục hồi cảnh Flow bằng Playwright CLI

Ngày 03/11/2026, Founder yêu cầu dùng skill Playwright. Đã đọc skill và kiểm tra npx, dùng playwright-cli đã cài, session doi_soat_flow.

- Trước mở: phiên API cũ INTERRUPTED/FLOW_SESSION_WORKER_RESTARTED; không có tiến trình Edge dùng profile Flow. Mở lại đúng thư mục profile cố định qua --persistent --profile, không tạo/copy profile hoặc cookie. Trang provider hiện tài khoản đã đăng nhập và gói PRO.
- Từ snapshot danh sách dự án, mở dự án 16:51: https://flow.google.com/project/9641e15e-70e6-4e67-9df3-d80830433472 . Prompt trên giao diện mô tả 20 đơn giấy đã quyết toán cạnh bảng tính trống, đúng nội dung cảnh e8696e28-7c0b-45db-8453-2e8f831731bb bị gián đoạn.
- Video đã tồn tại tại /edit/07b07d05-d765-41ab-8246-107927644564. Nhấn tải bản gốc 720p, không nhấn tạo mới, upscale hoặc gửi prompt.
- Đã tải MP4 về runtime/flow_canh_don_hang_v4.mp4, 720x1280, có audio, 10,026667 giây. SHA-256: 4297ac14453a8df7bb068bb6794c8ac6faa1f7c987593dc4f3a62246e4ed0d29.
- Đây là cảnh nguồn Flow đã phục hồi, chưa gỡ watermark, chưa đăng ký/đối soát kết quả vào hàng đợi sản phẩm, chưa ghép thành MP4 hoàn chỉnh. Không dùng cảnh này thay video quay gốc hoặc báo đạt nghiệm thu.
- Session CLI đang mở đúng dự án để tiếp tục đối soát. Snapshot CLI có thể chứa thông tin tài khoản nên giữ local, không commit toàn thư mục .playwright-cli.

- PREPARE_FLOW_ASSET task 1e23db46-3cba-464e-ac65-a1d3658b76ce QUEUED; xử lý bằng offload remove_watermark và normalize_flow hiện hữu. Script điều phối runtime/lam_sach_flow_phuc_hoi.py kiểm hash nguồn, kết quả watermark_removed và thời lượng 10 giây trước ghi bằng chứng. Handle exec30729 còn sống, chưa có kết quả; render khác 5bae1e35-f8b9-4fee-92f7-a6690f1e5d0d RUNNING với heartbeat tăng.
- Founder nghi ngờ sai hồ sơ: dừng trước tạo mới và hỏi xác nhận tài khoản. DB chỉ có profile main d08e7af1-41c9-4869-aa99-b368a7675b98; provider hiện tài khoản tranthaomy235@gmail.com. Chưa coi hồ sơ đã được Founder xác nhận. Lệnh điền prompt cảnh hai timeout vì tên locator bị mã hóa thành dấu hỏi; không điền thành công, nút tạo vẫn disabled, không gửi prompt.
- Bổ sung API resume hiện hữu: cho phép đúng cặp FAILED/FLOW_SUBMISSION_NOT_SENT, bên cạnh các trạng thái chặn đăng nhập/quota trước gửi. UPDATE so sánh chính xác trạng thái và mã lỗi vừa đọc, vẫn yêu cầu lease_token rỗng; không cho NEEDS_RECONCILIATION hoặc lỗi FAILED chung chạy lại. Test trước sửa có 3 ca thất bại đúng lý do JOB_NOT_RESUMABLE; sau sửa toàn tests/test_media_queue.py đạt 56/56 trong 12,83 giây. Chưa gọi API resume thật, chưa nạp lại API vì đang chờ xác nhận tài khoản. Giữ cùng job ID/idempotency khi tiếp tục; không tạo child trùng.
