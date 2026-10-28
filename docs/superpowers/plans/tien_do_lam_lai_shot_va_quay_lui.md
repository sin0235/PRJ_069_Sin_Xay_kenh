# Tiến độ thi công — kế hoạch `2026-10-26_lam_lai_shot_va_quay_lui.md`

- Ruling: Không có metadata Git/worktree trong cây dự án hiện tại; tiếp tục sửa SSOT tại `03_ban_lam_viec` theo lệnh Founder, không tạo nhánh hoặc commit giả.
- Ruling: Khi sửa nội dung/storyboard, run cũ và clip cũ được giữ làm lịch sử/tài sản; revision mới không hiển thị chúng như kết quả hiện hành. Xóa file media vật lý có thể gây mất dữ liệu ngoài ý muốn.
- Pre-flight: Task 1 tạo hợp đồng `RetryRunRequest` và `retry_run`; Task 2 tiêu thụ hợp đồng qua API client. Chưa thấy xung đột giao diện/API khác.
- Task 1: complete — test RED đúng vì `RetryRunRequest` chưa có; backend kiểm thử `python -m pytest tests/test_content_video_pipeline.py -q` đạt 49/49.
- Ruling: Cập nhật mock VieNeu trong test pipeline để khớp hợp đồng hiện tại (`infer()` trả audio, `sample_rate` nằm trên model); runtime TTS không đổi. Chi phí nếu sai: có thể che một lỗi của mock cũ, nhưng kiểm tra này chỉ định hình test double theo chính API `_infer` đang dùng.
- Task 2: hoàn tất — API client và production UI có retry một/toàn bộ shot, tiếp tục từ shot lỗi, xác nhận fallback project Flow mới, sửa/quay lại bước trước và vô hiệu hóa kết quả downstream bằng revision mới.

- Nghiệm thu cuối: `python -m pytest tests/test_content_video_pipeline.py -q` đạt 53/53; build giao diện ở lượt cập nhật UI trước đạt 42 route; lần xác minh build cách ly hiện tại dừng do giới hạn RAM; detector Impeccable trả `[]`.
- Giới hạn nghiệm thu: Edge tại cổng 3000 vẫn hiển thị bundle cũ; cầu trình duyệt hết thời gian khi tải lại/chụp trang. Chưa xác nhận trực quan giao diện mới; không gọi Flow hoặc thay đổi dữ liệu đang chạy.
- Bằng chứng: `08_kiem_thu/bang_chung/nghiem_thu_lam_lai_shot_va_quay_lui_20261026.md` và `08_kiem_thu/bang_chung/kiem_thu_backend_lam_lai_shot_20261026.txt`.
- Rà soát trust boundary phát hiện cờ `new_flow_project` mới chỉ bị khóa ở UI. RED xác nhận backend nhận yêu cầu sau lỗi hết hạn mức và cho chọn toàn bộ shot trong project mới. Service nay yêu cầu đúng `FLOW_REQUEST_NOT_SUBMITTED` và đúng một shot chưa hoàn tất đầu tiên; hai ca hồi quy đạt sau sửa.
- Fresh verification: pipeline đạt 53/53. Build cách ly được dừng ở bước tạo route khi RAM trống còn 293 MB; build UI đã thành công 42 route sau cập nhật UI ở lượt triển khai trước. Edge chưa xác nhận được bundle mới. Bản sao tạm còn lại vì chính sách chặn lệnh dọn thư mục dù đường dẫn đã được kiểm tra trong vùng làm việc.
