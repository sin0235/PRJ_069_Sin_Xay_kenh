# Bật xóa watermark Flow một lần, ngày 03/11/2026

- Checkout đang chạy: C:/Users/Baha Group/Documents/PRJ_069_Sin_Xay_kenh_git_push_wt_auto_edit_ui.
- Auto Edit giữ cờ remove_watermark=True tại provider. Không thêm xử lý vào bước ghép cuối.
- Video Studio lưu clip gốc, chuyển CLEANING rồi gọi remove_veo_watermark. Decorator chuyển tác vụ sang PREPARE_FLOW_ASSET trên GitHub Actions khi REMOTE_COMPUTE_MODE=github.
- Giữ remove_watermark=False ở dispatch Video Studio để tránh xóa hai lần. Bước CLEANING là nơi duy nhất xóa cho luồng này, bao gồm clip tạo từ ảnh.
- Kết quả sạch có khóa theo workspace, dự án và SHA-256 nguồn; kiểm tra SHA-256 trước khi dùng lại. Lưu MediaAsset sạch trước khi hoàn tất bước; retry không tạo lại Flow, không dùng clip chưa xóa thành công. Không xử lý lại video đã xuất trước thay đổi.
- Kiểm thử trước sửa: 3 lỗi đúng kỳ vọng. Sau sửa: 17 kiểm thử harness/retry/resume/watermark đạt; log xoa_watermark_flow_mot_lan_20261103.log cùng thư mục. Bao phủ gọi lại cùng clip, bản ghi khác cùng nội dung và kết quả xóa không thành công.
- Kiểm thử mở rộng Flow: 13 đạt, 1 lỗi ở test_google_flow_enters_video_mode_before_attaching_image do Locator giả thiếu last. Không sửa phần không liên quan.
- Khi kiểm tra trước nạp mã: không còn job mới QUEUED/RUNNING/SUBMITTING; một job SUBMITTING cũ ngày 02/11, lease đã hết. Worker không giữ lease. Đã khởi động lại riêng worker: PID 15512, cổng 8090. /healthz worker trả ok; /readyz trên domain BAHA trả ready, DB/worker READY, TTS REMOTE_GITHUB.
- Không khởi động lại API, không dừng Tunnel, không gửi job Flow/render thật, không đẩy Git. API hiện còn mã retry cũ trong bộ nhớ, nhưng worker mới vẫn chuyển các shot Flow SUCCEEDED chưa sạch về CLEANING trước ghép; mã service mới có hiệu lực ở lần khởi động API tiếp theo.
- Giới hạn: chưa xác minh chất lượng hình ảnh sau xóa bằng clip Flow thật. Mất tiến trình trước khi kết quả sạch được ghi DB có thể cần thực hiện lại tác vụ chưa được xác nhận.
