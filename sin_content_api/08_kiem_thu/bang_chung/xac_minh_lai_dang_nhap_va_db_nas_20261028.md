# Xác minh đăng nhập và cơ sở dữ liệu trên NAS

Ngày kiểm tra: 28-10-2026, múi giờ Việt Nam.

## Kết quả thực tế

- API NAS tại cổng 8069 trả `GET /healthz` HTTP 200 và `GET /readyz` HTTP 200 với `database_connected=true`.
- `GET /v1/auth/me` không gửi cookie hoặc bearer token trả HTTP 200. Đây không xác nhận Auth DB vì cấu hình đang bật `DEV_AUTH_BYPASS=1`; mã nguồn trả danh tính kiểm thử trước khi truy vấn Auth DB.
- Readiness hiện chỉ kiểm tra content DB. Vì vậy `readyz` xanh chưa chứng minh kết nối `BAHA_AUTH_DATABASE_URL`.
- Container Manager cho thấy API và FE đang chạy, initializer đã dừng. API đã chạy từ 13:48. Project dùng `APP_ENV=development`, `DEV_AUTH_BYPASS=1` và hai SQLite E2E trong volume `du_lieu_that`; đây chưa phải cấu hình production.
- Tệp seed `baha_auth_e2e_test.db` trong SSOT vượt `PRAGMA integrity_check` với kết quả `ok`; có 245 người dùng, 122 workspace và 245 membership. Tài khoản owner tổng hợp có membership ACTIVE trong workspace kiểm thử. Đây là kiểm tra tệp seed, không phải volume đang được container sử dụng.

## Nguyên nhân tìm thấy

- Trước khi sửa, `docker compose config --quiet` cảnh báo hai biến không được khai báo. Nguyên nhân là các dấu `$` trong `FOUNDER_PASSWORD_HASH` bị Compose hiểu là nội suy biến, làm thay đổi chuỗi băm khi nạp cấu hình.
- Đã escape ba dấu phân cách thành `$$` trong file Compose thuộc SSOT. Kiểm tra lại: Compose hợp lệ, mô hình giữ nguyên chuỗi đã escape, không còn cảnh báo biến nội suy.
- Theo tài liệu Docker, `$$` dùng để biểu diễn dấu `$` theo nghĩa đen và ngăn Compose nội suy giá trị: [Tài liệu Docker về nội suy Compose](https://docs.docker.com/reference/compose-file/interpolation/).

## Giới hạn và bước cần làm tiếp

- Chưa xác minh kết nối Auth DB trong volume runtime: bypass đang che nhánh đó và terminal DSM báo không thể gắn phiên terminal. Không gửi thử mật khẩu, không thay đổi dữ liệu DB và chưa restart/recreate container.
- Compose source cũng đã khai báo mount `next.config.mjs` cho FE. YAML đang lưu trong DSM chưa phản ánh mount này; cấu hình cần được áp dụng để lỗi origin FE hết hẳn.
- Cần áp dụng lại Compose để nhận hash đã sửa và mount FE. Thao tác có thể recreate API và FE, gây gián đoạn ngắn; volume dữ liệu giữ nguyên. Chưa thực hiện vì phạm vi trước đó chỉ cho phép restart FE, không gồm API hoặc toàn project.
- Sau khi áp dụng, kiểm tra Auth DB bằng nhánh đăng nhập thật và `/v1/auth/me`; không coi kết quả `readyz` hay dev bypass là bằng chứng cho Auth DB.
- Giá trị biến môi trường nhạy cảm trong màn hình Container Manager đã được lược khỏi biên bản. Nếu khóa đang hiển thị là khóa thật, cần chuyển sang kho bí mật và xoay khóa.
## Sự cố initializer ngày 28-10-2026

- Start project DSM đã chạy initializer cũ, thoát mã 0. Mã cũ ghi đè ba DB volume bằng seed; chưa xác định mức dữ liệu bị ảnh hưởng hoặc có bản sao trước thao tác.
- Đã sửa initializer SSOT giữ DB và media hiện hữu; kiểm thử dữ liệu tạm 2/2 đạt. Chưa recreate API/FE và chưa xác minh đăng nhập hay Auth DB runtime.

## Khởi động lại và thử TTS ngày 28-10-2026

- Theo yêu cầu dùng lại môi trường kiểm thử, DSM Build đã recreate API và FE; initializer đã sửa chạy xong, mã thoát 0. Không xóa volume.
- API `/healthz`, `/readyz`, `/v1/auth/me` và OpenAPI trả HTTP 200; `/readyz` báo kết nối content DB. Đăng nhập với thông tin sai trả HTTP 401. Trang đăng nhập và Voice Studio trả HTTP 200. Chưa xác minh đăng nhập bằng tài khoản thật và Auth DB do bypass đang bật.
- Giao diện TTS trên HTTP LAN gặp lỗi `crypto.randomUUID is not a function`; đã chuyển sang `crypto.getRandomValues`. Thử lại tạo tác vụ `de39bcc3-96af-4616-a195-3ae13a332aaa`; API nhận, worker chuyển sang RUNNING và chưa hoàn tất tại lúc ghi. Chưa có audio để nghe hoặc đánh giá chất lượng.
- Kiểm thử initializer trên dữ liệu tạm đạt 2/2; `docker compose config --quiet` và Python compile đạt.
