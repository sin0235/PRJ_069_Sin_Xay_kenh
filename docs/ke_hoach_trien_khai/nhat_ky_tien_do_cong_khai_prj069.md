# Nhật ký tiến độ — công khai Cloudflare PRJ_069

Kế hoạch: `03_ban_lam_viec/docs/ke_hoach_trien_khai/2026-10-28_cong_khai_cloudflare_dang_nhap_prj069.md`

## Quyết định thực hiện

- Người dùng đã duyệt thiết kế và yêu cầu triển khai hostname `nhap-xaykenh-proj069.bahagroup.vn`.
- Ruling: làm trực tiếp trên bản SSOT trong `03_ban_lam_viec` vì thư mục workspace hiện không phải Git repository, không có remote/branch để tạo worktree, và bản nguồn canonical nằm trên NAS. Tạo worktree giả sẽ tạo một bản code lệch canonical và nằm ngoài ranh giới ghi được phép. Rủi ro nếu sai: không có Git rollback cho phần sửa mã; giữ nguyên mọi bản gốc ngoài vùng ghi và ghi rõ từng tệp thay đổi.
- Ruling: thực hiện mã và kiểm thử cục bộ trước; không tạo public hostname/Access app/route hoặc cấp role live khi chưa hoàn thành kiểm thử, xác nhận cuối tại thời điểm mở public, và hồ sơ A00 theo quy định dự án. Rủi ro nếu sai: trì hoãn public; nếu bỏ gate có thể mở ứng dụng với bypass hoặc cấp quyền sai workspace.

## Trạng thái bước

- A00: kiểm kê read-only một phần, BLOCKED. Compose đang bật `DEV_AUTH_BYPASS=1` và trỏ tới DB E2E; cặp DB nguồn chỉ khớp một workspace và một membership; chưa xác minh nội dung volume, chưa có Founder trong DB Auth live, và workspace `default_ws` chưa có approval policy ACTIVE. Chưa được phê duyệt.
- Bước 2–4: mã xác thực Access, ánh xạ danh tính API và ngoại lệ tự duyệt Founder đã triển khai cục bộ. Kiểm thử Baha Auth đạt 70/70; kiểm thử API đạt 27/27.
- Bước 5: FE đã chuyển sang phiên Access, cùng origin và đăng xuất Access. TypeScript và build Next.js đạt 43 route; Biome chưa chạy. Đã sửa nhãn trang đăng nhập để hướng dẫn OTP Access.
- Bước 6: mã, tài liệu và bằng chứng đã đồng bộ vào SSOT NAS; SHA-256 khớp 46/46 mục tiêu. Bản khôi phục: `03_ban_lam_viec/bao_luu_phuc_hoi_xac_thuc_cloudflare_20261028_100520/`. Chưa sửa Compose, DB, volume, Cloudflare, DNS, tunnel hoặc cấp tài khoản/quyền live.
- Bước 7: chưa chạy trên NAS; chưa xác minh OTP live, dữ liệu volume, LLM Luna 6 hoặc hành vi public.
- Kiểm tra trạng thái public: hostname hiện trả `ERR_NAME_NOT_RESOLVED` trong Edge. DSM vẫn liệt kê project `prj069_nas_kiem_thu_that` với ba container API, FE và khởi tạo dữ liệu; không khởi động container nào.
- So sánh SHA-256 cho tệp code cục bộ đã sửa cho thấy các tệp xác thực/FE khác với bản NAS hoặc chưa có trên NAS; chưa ghi đè bản SSOT.

## Bằng chứng lượt này

- `03_ban_lam_viec/docs/ke_hoach_trien_khai/bao_cao_kiem_ke_A00_prj069.md`
- `03_ban_lam_viec/sin_content_api/08_kiem_thu/bang_chung/kiem_thu_dang_nhap_cloudflare_20261028.md`
- `03_ban_lam_viec/sin_content_api/08_kiem_thu/bang_chung/kiem_ke_ma_nguon_api_giao_dien_20261028.md`
- `03_ban_lam_viec/sin_content_api/08_kiem_thu/bang_chung/dong_bo_xac_thuc_cloudflare_len_nas_20261028.md`
- Log pytest và build nằm cùng thư mục bằng chứng; không chứa giá trị secret.

## Cổng tiếp theo

Không mở hostname hoặc chạy ứng dụng thật cho tới khi đối chiếu volume/dataset, chốt workspace chuẩn, giải quyết các tham chiếu khóa ngoại, có approval policy và hồ sơ phát hành A00 được phê duyệt.
