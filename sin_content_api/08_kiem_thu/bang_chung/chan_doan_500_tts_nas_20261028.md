# Chẩn đoán lỗi 500 Voice Studio trên NAS

Thời điểm kiểm tra: 2026-10-28 15:53:17 +07:00

- Giao diện http://192.168.1.175:3069/voice-studio vẫn trả HTTP 200 và hiển thị Lỗi API 500..
- API NAS http://192.168.1.175:8002/healthz và /readyz không kết nối được (connection refused); cổng frontend 3069 vẫn hoạt động.
- Container Manager liệt kê prj069-nas-api-kiem-thu-that đã dừng, image đang chạy trước đó là prj069-sin-api:kiem-thu-nas11; FE còn Up.
- Log API cho thấy Uvicorn khởi động lại bằng --reload, và các GET /healthz, /v1/voice-studio/jobs, /voices, /settings đều từng trả 200 sau lần khởi động gần nhất. Không thấy traceback hoặc request TTS POST mới trong phần log cuối; vì vậy chưa có bằng chứng cho thấy chính handler TTS ném lỗi 500.
- DSM trước đó báo health check vượt timeout 5 giây và CPU tổng NAS từng lên 95%. Compose giới hạn API 2 GiB và bật --reload; đây là điều kiện đáng kiểm tra tiếp, chưa đủ để kết luận nguyên nhân container dừng hay OOM.

Kết luận đã xác nhận: lỗi 500 người dùng thấy hiện tại là do giao diện còn phục vụ trong khi API container đã dừng/không nghe cổng. Nguyên nhân khiến API dừng chưa xác định từ log còn lại. Chưa restart container vì DSM đang báo hệ thống bận và cần lấy exit state/OOM evidence trước để tránh lặp vòng restart mù.

## Theo dõi tác vụ VieNeu v3 Turbo 15:57 ngày 28-10-2026

- API trả HTTP 200 /healthz và /readyz lúc 15:55; danh sách tác vụ có duy nhất job c3b29455-cefb-4294-9bdc-59dcb5659767 ở RUNNING, không có asset/audio, tạo lúc 15:20. Chưa thấy trạng thái hoàn tất.
- Log sau lần khởi động API lúc 15:54 lặp lại cảnh báo truy cập Hugging Face Hub không xác thực; log không có dòng TTS hoàn tất hoặc lỗi job. Điều này gợi ý model/runtime đang phụ thuộc tải từ Hugging Face, nhưng chưa xác nhận được tiến độ tải hay lỗi mạng cụ thể.
- Container Manager đã ghi nhận mức đỉnh 1,64 GB trên giới hạn 2 GB và CPU 71,41%; ảnh chụp sau đó, sau lần API khởi động lại lúc 15:54, tiến trình API chỉ 27 MB/1,4% CPU. Hai ảnh chụp khác thời điểm, không dùng mức đỉnh làm số đo hiện tại.
- Lúc 15:57, truy vấn từ máy làm việc tới /healthz và trạng thái job qua cổng 8069 đều timeout 10 giây, trong khi DSM vẫn báo container Healthy. Hiện tượng không nhất quán cần kiểm tra đường gọi FE/API và tình trạng tải model tiếp; không kết luận DB hay model đã hỏng.
- Chưa gửi thêm job để tránh trùng tác vụ đang RUNNING; chưa có audio để nghe. Bằng chứng giao diện hiện tại là job history sau reload hiển thị rỗng, dù API trước đó trả job này; có khả năng lệch trạng thái tải danh sách ở FE.
