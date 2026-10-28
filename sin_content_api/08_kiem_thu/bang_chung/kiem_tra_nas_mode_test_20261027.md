# Kiểm tra đăng nhập và mode test trên NAS - 2026-10-27

## Trạng thái NAS và Flow

- Container `prj069_flow_login-flow_login-1`, image `prj069-flow-login:1.63.0-nas2`, hiển thị `Up for 31 mins` trong Container Manager.
- noVNC kết nối được tới Chromium chạy trên NAS. Google Flow mở với avatar chữ T và gói Pro.
- Màn giới thiệu đầu tiên `Your face, your voice, your story` còn nút `Get started`; không bấm nút này và không gửi yêu cầu tạo nội dung.

## Kiểm tra cấu hình test

- Compose kiểm thử nằm trong vùng làm việc và bản NAS khớp SHA-256 với local: `61102391FB39FECBB75987203FAA16A41F55C5C060D70557355915F4470A5657`.
- `docker compose -f 03_ban_lam_viec/ha_tang/docker_compose_kiem_thu.yaml config --quiet` kết thúc với mã 0.
- `python -m pytest --collect-only -q tests` thu thập 434 ca test. Không có ca test nào được thực thi.

## Kết quả triển khai

- DSM báo: `Sorry, this user account has not been assigned proper privileges to perform this action.` khi tạo thư mục triển khai trong `03_ban_lam_viec/ha_tang`.
- Không tạo project API test hoặc container `prj069-sin-api-kiem-thu`; stack test chưa chạy.
- SSH kiểm tra ở chế độ không tương tác trả `Permission denied (publickey,password)`. Không nhập mật khẩu.
- Thư mục rỗng tạo nhầm tại `/volume1/09.ai_workspace/03_ban_lam_viec/nas_api_kiem_thu` được xóa sau khi Founder xác nhận; kiểm tra lại cho kết quả không tồn tại.

## Việc cần làm tiếp

Cấp quyền ghi cho tài khoản DSM hiện tại trên `03_ban_lam_viec/ha_tang`, hoặc dùng tài khoản DSM đã có quyền phù hợp. Sau đó khởi chạy Compose test bằng file tường minh, xác nhận healthcheck, rồi chạy pytest trong container.