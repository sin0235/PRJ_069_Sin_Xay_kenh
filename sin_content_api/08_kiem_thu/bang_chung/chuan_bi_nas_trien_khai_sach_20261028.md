# Chuẩn bị dự án triển khai NAS mới (prj069_v2)

Ngày 28-10-2026. Trạng thái: đã chuẩn bị và kiểm thử trên máy làm việc, chưa triển khai lên NAS.

## Chẩn đoán lúc 16:5x (NAS đang chạy bản cũ)

- Ping NAS 3 ms. Giao diện cổng 3069 trả 200 (5,8 giây) và 307 (0,4 giây). API cổng 8069: cổng TCP mở nhưng `/healthz` không trả lời sau 10 giây và 45 giây.
- `kiem_tra_trang_thai_nas.py` bản cũ báo "đang chạy" chỉ vì cổng mở. Đã sửa: chỉ báo thành công khi `/healthz` trả 200. Chạy lại sau sửa: cổng FE/API không mở (NAS đã thay đổi trạng thái).

## Nguyên nhân tìm thấy trong mã và cấu hình

1. `sin_content_api/src/modules/auth/router.py` có mật khẩu dự phòng cố định, hash và khóa JWT mặc định trong mã, và ID người dùng cố định khi tạo phiên. Vi phạm nguyên tắc không để bí mật trong repo.
2. Compose cũ: `--reload`, mount mã nguồn, FE chạy `npm run dev`, bypass xác thực, DB E2E (122 workspace, 245 người dùng thử trong DB seed), image thiếu Chromium.
3. Hash mật khẩu có ký tự `$` bị Compose nội suy (đã ghi trong biên bản xác minh đăng nhập trước đó).

## Thay đổi

- `sin_content_api/src/modules/auth/router.py`: bỏ mật khẩu dự phòng và mọi giá trị mặc định nhạy cảm; thiếu `FOUNDER_EMAIL`, `FOUNDER_PASSWORD_HASH`, `SIN_WORKSPACE_ID` trả 503; ID phiên lấy từ Baha Auth DB (không có hoặc không ACTIVE trả 403; lỗi DB trả 503).
- `sin_content_api/src/auth/tenancy.py`: production trả 503 nếu thiếu `BAHA_AUTH_JWT_SECRET/ISSUER/AUDIENCE/DATABASE_URL`, không rơi về giá trị mặc định.
- `sin_content_api/scripts/khoi_tao_production_noi_bo.py`: thêm `PRJ069_BOOTSTRAP_MODE=sach` (DB trống; Auth DB tạo từ mô hình hiện hành cùng 4 vai trò mẫu); chế độ mặc định `ke_thua` giữ nguyên hành vi cũ; tạo thư mục cache model và chuyển quyền hồ sơ Flow.
- `sin_content_api/Dockerfile`: build-arg `CAI_TRINH_DUYET` (mặc định 0) cài Playwright 1.63.0 và Chromium.
- `ha_tang/nas_flow_login/khoi_dong.sh`: hỗ trợ `VNC_PASSWORD`.
- Dự án mới `ha_tang/nas_trien_khai_sach/`: `docker-compose.yml`, `docker-compose.dang_nhap_flow.yml`, `tao_cau_hinh.py`, `kiem_tra_sau_trien_khai.py`, `huong_dan_trien_khai.md`, `.gitignore`.

## Kiểm thử đã chạy

- `tests/test_dang_nhap_noi_bo.py` (mới): 6/6 đạt (ID phiên lấy từ DB, mật khẩu dự phòng cũ bị từ chối, sai mật khẩu, Founder chưa có trong DB, Founder không ACTIVE, thiếu cấu hình).
- Chạy cùng `test_dev_auth_bypass.py`, `test_tenancy.py`, `test_tich_hop_phan_quyen.py`: 28 đạt, 3 lỗi. Ba lỗi nằm ở mã không đụng tới: dev bypass trả UUID thay vì `default_ws`; test thiếu `BAHA_AUTH_DATABASE_URL` nhận 403 thay vì 503 (guard mới chỉ áp dụng ở production); kiểm kê route RBAC báo thiếu khai báo cho 3 route `/v1/auth/*`. Chưa đối chiếu với bản trước khi sửa vì không có git ở thư mục này.
- `tao_cau_hinh.py` (trong thư mục tạm): tạo `.env` và `secrets/9rt.env`, lần hai từ chối ghi đè. Sau khi `docker compose config` giải mã `$$`, hash trong Compose khớp `.env` ở cả hai dịch vụ.
- `docker compose config`: hợp lệ.
- Initializer chế độ `sach` trong thư mục tạm, chạy hai lần: lần 1 `initialized`, lần 2 `already_initialized`. Auth DB: 1 người dùng (Founder, ACTIVE), 1 workspace, 1 membership, 1 role assignment, 4 role, 1 policy; content DB: 1 workspace, 1 user, 1 membership; `integrity_check` ok cả hai.
- API production (APP_ENV=production, bypass tắt) trên DB sạch, `kiem_tra_sau_trien_khai.py`: 11/11 bước đạt (health, ready, môi trường production, 401 khi chưa đăng nhập, sai mật khẩu 401, mật khẩu cũ 401, đăng nhập 200, `/v1/auth/me` đúng workspace và vai trò WORKSPACE_OWNER, ba API TTS 200).

## Chưa kiểm chứng

- Docker daemon máy làm việc tắt: chưa build image API, FE hay image đăng nhập Flow; chưa chạy trên NAS.
- Chưa kiểm tra: Next.js build trong image, hồ sơ Chromium dùng chung giữa image đăng nhập và image API, tải model VieNeu, âm thanh TTS thật, phiên Google Flow thật, kiến trúc CPU của NAS.
- Mật khẩu và khóa trong thư mục thử là giá trị giả lập, đã bỏ; `.env` thật chưa được tạo (cần Founder nhập mật khẩu).
