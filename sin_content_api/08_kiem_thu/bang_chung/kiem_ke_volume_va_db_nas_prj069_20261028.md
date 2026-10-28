# Kiểm kê volume và DB NAS PRJ_069

**Ngày:** 2026-10-28  
**Phạm vi:** đọc cấu hình qua SMB, metadata SQLite ở chế độ chỉ đọc và trạng thái project qua DSM. Không khởi chạy container, sửa Compose, thay đổi DB/volume hoặc cấu hình Cloudflare.

## Bằng chứng DSM

- Project `prj069_nas_kiem_thu_that` nằm tại `03_ban_lam_viec/ha_tang/nas_kiem_thu_that`; ba container API, FE và initializer đều dừng.
- Chi tiết initializer cho thấy nó gắn read-only `sin_content_e2e_test.db`, `baha_auth_e2e_test.db`, `sin_dieu_phoi_dung.db`, thư mục media và script khởi tạo vào container.
- Log lúc 2026-10-27 18:07 ghi đã chép ba DB và 118 tệp media; 27 tệp media được tham chiếu không có trong nguồn. Năm lần chạy tiếp theo trong log, gần nhất 2026-10-28 09:08, đều ghi volume đã khởi tạo trước đó và được giữ nguyên.
- Vì vậy có thể xác nhận volume bắt nguồn từ E2E. Chưa đọc trực tiếp DB/media hiện đang ở volume; không thể xác nhận có hoặc không có thay đổi nghiệp vụ phát sinh sau lúc seed.

## Cấu hình và nguồn DB

- Compose canonical đang có `APP_ENV=development`, `DEV_AUTH_BYPASS=1`, `TESTING=0`, `SYNTHETIC_DATA_ALLOWED=false`, `LLM_ENABLED=true`; API dùng hai file DB E2E. FE/API chưa được public.
- Hai DB nguồn hiện có là `sin_content_offline.db` và `baha_auth_live.db`. Chúng chỉ khớp một workspace và một cặp membership là `default_ws`; không có tài khoản Founder đã cung cấp trong Auth DB; `default_ws` không có approval policy ACTIVE. Content DB có bốn vi phạm khóa ngoại.
- Content DB có 78 workspace; tên workspace bao gồm nhiều không gian kiểm thử như `P09 Script Workspace`, `Sin Source Test WS` và `Sin Planning Test WS`.
- Cấu hình LLM singleton trong content DB đang lưu `gpt-4o-mini` và base URL `http://127.0.0.1:20128/v1`. Chưa chứng minh cấu hình này sẽ được ghi đè từ `9rt.env`; hiện chưa đạt yêu cầu Luna 6.
- `sin_content.db` là tệp rỗng. Không dùng nó làm nguồn.

## Cloudflare và kết quả

- Cloudflare Dashboard mở tới màn hình đăng nhập. DNS lookup cho `nhap-xaykenh-proj069.bahagroup.vn` hiện không trả bản ghi.
- SSH batch bằng khóa hiện có bị từ chối; không yêu cầu hoặc ghi mật khẩu vào chat.
- Chưa khởi động service, thay DB/volume, sửa DNS/tunnel/Access, provision Founder hay gọi LLM.

## Quyết định

Không dùng Compose hiện tại để chạy thật: nó bật auth bypass và gắn DB E2E. Chưa thể chuyển sang public thật vì chưa có cặp DB/workspace đã đối soát, tài khoản/policy Founder trong DB, xác minh Luna 6 hoặc Cloudflare session. A00 giữ BLOCKED. Bản sao lưu volume chưa tạo vì không đọc/ghi được Docker named volume an toàn từ phiên này.