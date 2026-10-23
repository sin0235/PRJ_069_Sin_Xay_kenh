# Báo cáo kiểm thử AI Studio ảnh sang video — 2026-10-23

## Kết quả
- Giao diện Edge tại `/ai-studio` sau khi khởi động lại Next.js hiển thị ô “Ảnh tham chiếu (không bắt buộc)” và nút “Tải ảnh tham chiếu lên”; nút tải video 16:9 không còn.
- API cục bộ khởi động và `/healthz` trả `status=ok`, `environment=offline`.
- Tạo ảnh PNG thử trong thư mục scratch. Thao tác chọn ảnh bị tiện ích ChatGPT trên Edge chặn khi gọi file chooser: cần bật “Allow access to file URLs” tại `edge://extensions`.
- Vì ảnh chưa được gắn vào form, không phát sinh upload asset và không gửi lệnh tạo video tới Google Flow. Luồng ảnh → video thật chưa được nghiệm thu.

## Phạm vi kiểm tra
- Đã xác nhận bằng accessibility tree của Edge rằng giao diện mới được phục vụ sau khi khởi động lại Next.js.
- Đã xác nhận liveness API.
- Chưa kiểm tra backend upload asset, ghép ảnh vào khung hình đầu của Flow, hay render MP4 dọc 9:16.

## Trạng thái môi trường
- API kiểm thử đã được dừng sau khi kiểm tra.
- Next.js trên cổng 3000 đã được khởi động lại và vẫn chạy để Edge tiếp tục hiển thị giao diện mới.
- Không upload ảnh lên dịch vụ ngoài và không tạo video/tiêu hao lượt Flow.
