# Chẩn đoán đăng nhập và kết nối cơ sở dữ liệu NAS

**Thời điểm:** 28/10/2026, 13:55 GMT+7  
**Phạm vi:** Kiểm tra chỉ đọc API, giao diện, cấu hình Compose và bản CSDL mẫu E2E. Không gửi thông tin đăng nhập, không ghi vào CSDL NAS, không khởi động lại container.

## Kết quả đã xác minh

- API `http://192.168.1.175:8069/healthz` trả HTTP 200 và báo `development`.
- API `http://192.168.1.175:8069/readyz` trả HTTP 200, `status=ready`, `database_connected=true`. Vì vậy CSDL nội dung mà API đang dùng có kết nối tại thời điểm kiểm tra.
- Giao diện trả HTTP 200 cho `/auth/v1/login`, `/v1/auth/me` và `/v1/workspaces`.
- Compose kiểm thử cấu hình `APP_ENV=development`, `DEV_AUTH_BYPASS=1`, `DATABASE_URL=...sin_content_e2e_test.db`, `BAHA_AUTH_DATABASE_URL=...baha_auth_e2e_test.db`; đây là môi trường E2E, không phải cấu hình production.
- Mã `/readyz` chỉ gọi `check_db_ready()` của CSDL nội dung trong `src/database.py`; không kiểm tra kết nối `BAHA_AUTH_DATABASE_URL`. Do đó kết quả `ready` chưa chứng minh CSDL phân quyền đang kết nối.
- Bản mẫu `baha_auth_e2e_test.db` trên workspace đọc được ở chế độ chỉ đọc. Tài khoản kiểm thử do luồng đăng nhập cục bộ tham chiếu, workspace cấu hình và membership tương ứng đều có trạng thái `ACTIVE` trong bản mẫu. Chưa đọc trực tiếp volume đang được container dùng nên chưa thể xác nhận trạng thái bản đang chạy.
- Ảnh log Container Manager do Founder cung cấp ghi cảnh báo Next.js về `allowedDevOrigins` khi truy cập từ `192.168.1.175`. `next.config.mjs` hiện chưa khai báo mục này. Khi thử nhập ở trang TTS, giá trị textarea đổi trong DOM nhưng bộ đếm React vẫn ở `0/5000` và nút gửi vẫn khóa; giao diện chưa xử lý được trạng thái nhập.

## Kết luận

- Chưa có bằng chứng CSDL nội dung bị mất kết nối; phép kiểm tra readiness trả kết nối thành công.
- Cảnh báo Next.js và trạng thái giao diện cho thấy frontend development qua IP NAS chưa được cho phép đầy đủ; đây là nguyên nhân có bằng chứng nhất cho việc form/luồng đăng nhập trên trình duyệt không hoạt động ổn định.
- Tình trạng CSDL Auth trên volume đang chạy chưa được kiểm chứng. `GET /v1/auth/me` trả 200 trong cấu hình bypass nên không chứng minh nó đã truy cập CSDL Auth.
- Chưa có lỗi POST đăng nhập trong log được cung cấp; ảnh chỉ chứng minh trang đăng nhập được phục vụ. Chưa thể kết luận sai mật khẩu hay lỗi truy vấn membership.

## Hướng xử lý đề xuất

Cho phép host `192.168.1.175` trong `allowedDevOrigins` của Next.js rồi khởi động lại riêng frontend để nạp cấu hình. Sau đó kiểm tra đăng nhập bằng giao diện và xác minh riêng kết nối Auth DB trong container; không đổi CSDL hoặc cấp quyền production từ kết quả này.

Tham khảo tài liệu Next.js: https://nextjs.org/docs/app/api-reference/config/next-config-js/allowedDevOrigins
