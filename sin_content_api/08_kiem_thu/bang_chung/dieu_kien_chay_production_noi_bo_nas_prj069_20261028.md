# Điều kiện chạy production nội bộ PRJ_069 trên NAS

**Ngày:** 2026-10-28  
**Phạm vi:** Đọc Compose, luồng xác thực, mô hình role và báo cáo A00; không sửa hoặc khởi động container, không ghi DB hay Cloudflare.

## Không có cấu hình production sẵn sàng

- `ha_tang/compose.yaml` khai báo `APP_ENV=staging`, chứa thông tin xác thực mẫu trong YAML và publish cổng PostgreSQL, Redis, API ra mọi địa chỉ host. Không dùng cho production.
- `ha_tang/docker_compose_kiem_thu.yaml` và các Compose `nas_api_kiem_thu`/`nas_fe_kiem_thu` chạy `APP_ENV=test`, `/tmp`, synthetic data hoặc image kiểm thử.
- Compose đang dùng trong DSM là `ha_tang/nas_kiem_thu_that/docker-compose.yml`: `APP_ENV=development`, `DEV_AUTH_BYPASS=1`, hai DB E2E, FE chạy `npm run dev`. Không dùng cho production.
- Không tìm thấy Compose production khác trong `03_ban_lam_viec/ha_tang`.

## Localhost hiện không có luồng xác thực production

- FE lấy phiên bằng `GET /v1/auth/me`; API xác minh `Cf-Access-Jwt-Assertion` rồi tra GlobalUser, membership và workspace trong Baha Auth.
- Khi chạy production, API từ chối nếu thiếu assertion Cloudflare Access. Bypass chỉ hoạt động trong môi trường development/test trên kết nối loopback.
- Baha Auth không có handler đăng nhập mật khẩu hoặc OTP cục bộ đang dùng. Tắt bypass rồi mở `localhost` sẽ không tạo được phiên Founder. Dùng Access đòi hỏi một ứng dụng qua Cloudflare; đó là hostname có thể truy cập từ Internet nhưng bị Access chặn theo policy, không phải localhost-only.
- Không tự thêm nhà cung cấp đăng nhập mới: bộ RBAC gốc yêu cầu ADR, đánh giá an toàn và phê duyệt khi thêm auth provider.

## Tài khoản và dữ liệu thật chưa đủ điều kiện

- DB nguồn `sin_content_offline.db` và `baha_auth_live.db` chỉ khớp một workspace/membership; Founder không có trong Auth DB; workspace khớp chưa có approval policy ACTIVE. Content DB có bốn vi phạm khóa ngoại. Chi tiết đã được ghi trong `docs/ke_hoach_trien_khai/bao_cao_kiem_ke_A00_prj069.md`.
- Đường dẫn API production cần `SIN_WORKSPACE_ID`; chưa có workspace chuẩn được phê duyệt để cấu hình. Không chọn `default_ws` chỉ vì đó là ID giao nhau duy nhất.
- RBAC gốc yêu cầu A00 inventory/signed role catalog trước live grant; A11 yêu cầu migration diff, rollback proof và phát hành live có ký duyệt. Master Plan còn đặt hard gate không tự duyệt nội dung cuối. Ngoại lệ Founder đã yêu cầu trước đó chưa được ghi thành policy A00 đã duyệt; không thể áp dụng quyền đó cho DB live hiện tại.
- Phạm vi account đã được yêu cầu trước đây là Founder/`WORKSPACE_OWNER` trong đúng workspace PRJ_069, không phải `PLATFORM_OWNER` toàn hệ thống. Tài khoản này chưa thể đăng nhập hoặc nhận role khi danh tính/workspace/policy chưa có trong cặp DB chuẩn.

## Quyết định

Không bật hoặc chỉnh Compose hiện tại thành production bằng cách chỉ đổi `APP_ENV`: cách đó sẽ giữ DB E2E, bypass và sai luồng đăng nhập. Không tạo account/role trong DB nguồn hoặc volume trước khi chọn nguồn thật, kiểm tra volume, phê duyệt A00/ma trận/policy, sao lưu và chuẩn bị rollback.

Để có localhost-only production, trước hết cần một thiết kế xác thực nội bộ được phê duyệt và ADR; hoặc chọn Cloudflare Access qua tunnel riêng, chấp nhận hostname Internet có Access bảo vệ. Cả hai hướng đều cần DB/workspace chuẩn và xử lý cổng A00 trước khi cấp account Founder.

## Cập nhật kiểm tra trực tiếp DSM và workspace, 2026-10-28

- Đã đọc Package Center trên DSM đang đăng nhập. Synology SSO Server chưa cài; Package Center liệt kê gói chính thức này là có thể cài. OAuth Service đã cài là gói khác, không thay thế SSO Server. Tài liệu Synology mô tả SSO Server hỗ trợ OIDC cho ứng dụng và yêu cầu cấu hình URL dịch vụ HTTPS hợp lệ: [mô tả SSO Server](https://kb.synology.com/index.php/en-us/DSM/help/SSOServer/sso_server_desc?version=7), [thêm ứng dụng OIDC](https://kb.synology.com/en-uk/DSM/help/SSOServer/sso_server_application_list?version=7), [cấu hình URL máy chủ](https://kb.synology.com/index.php/en-ph/PAS/help/SSOServer/sso_server_general_setting?version=1_0).
- Truy vấn chỉ đọc DB nội dung nguồn xác nhận `default_ws` có tên `BAHA Group Workspace`, không phải workspace PRJ_069. Không đặt `SIN_WORKSPACE_ID=default_ws` cho hệ thống này.
- Tệp `9rt.env` có ở máy phát triển nhưng không có tại thư mục SSOT tương ứng trên NAS. Chưa chép thông tin xác thực lên NAS.
- Vì vậy chưa có cấu hình local-production nào vừa đăng nhập được, vừa trỏ đúng workspace/dữ liệu. Cấu hình production hiện tại chỉ xác minh Cloudflare Access; cấu hình NAS còn lại là development/E2E. Chưa tạo Compose mới, chưa cài gói, chưa ghi DB, chưa khởi động container.
- Mức CPU DSM tại thời điểm mở Package Center dao động khoảng 52–60%; đây là ảnh chụp tức thời, không phải benchmark.