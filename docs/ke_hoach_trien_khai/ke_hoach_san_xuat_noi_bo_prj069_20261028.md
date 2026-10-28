# Kế hoạch vận hành production nội bộ PRJ_069

## Mục tiêu

Chạy SIN Creator OS trên NAS ở `APP_ENV=production`, chỉ bind cổng loopback, đăng nhập bằng mật khẩu riêng cho Founder và giữ dữ liệu qua các lần khởi động.

## Phạm vi

- API chỉ nhận mật khẩu Founder đã cấu hình và phiên JWT có chữ ký; không bật `DEV_AUTH_BYPASS`, `TESTING` hoặc tự đăng ký.
- Phiên trình duyệt dùng cookie HttpOnly, SameSite Strict, thời hạn 8 giờ; đăng nhập kiểm tra Origin và giới hạn thử sai.
- FE có biểu mẫu đăng nhập thật và đăng xuất thu hồi cookie.
- Compose production riêng, không dùng project/volume E2E; API/FE bind `127.0.0.1`.
- Khởi tạo dữ liệu idempotent trong thư mục bền vững riêng từ DB nguồn; thêm workspace `prj069_sin_xay_kenh`, GlobalUser Founder, membership, role `WORKSPACE_OWNER` và policy duyệt workspace. DB nguồn không bị sửa.
- Khóa LLM lấy từ `9rt.env`, model `cx/gpt-6-luna`; không in khóa hoặc đưa khóa vào Git.

## Ngoài phạm vi

- Tạo `PLATFORM_OWNER`, thêm người dùng khác, public Internet/Cloudflare, hoặc thay đổi các workspace đang có.
- Xóa, sửa hoặc di chuyển dữ liệu nguồn.

## Thứ tự thực hiện

1. Viết kiểm thử cho bộ băm mật khẩu, JWT phiên và endpoint đăng nhập/đăng xuất; xác nhận kiểm thử mới thất bại đúng nguyên nhân.
2. Triển khai API auth chỉ dùng trong production và cập nhật biểu mẫu FE; giữ nguyên Cloudflare Access khi cấu hình Access được dùng.
3. Tạo bootstrap dữ liệu bản sao có kiểm tra nguồn, marker, quyền tệp và khả năng chạy lại an toàn.
4. Tạo Compose production riêng, cấu hình secret bị bỏ qua bởi Git, health check và cổng loopback.
5. Chạy kiểm thử mục tiêu, build FE/API, kiểm tra Compose và cấu hình LLM; sao lưu/khởi tạo trên NAS, khởi chạy rồi kiểm tra đăng nhập và health.

## Tiêu chí hoàn tất

- Sai email/mật khẩu bị từ chối; tài khoản hợp lệ nhận cookie HttpOnly; cookie sai, hết hạn hoặc khi auth tắt bị từ chối.
- Founder chỉ thấy workspace PRJ_069 và có role `WORKSPACE_OWNER`; thao tác duyệt được ghi audit theo policy hiện hành.
- API và FE báo production, test/bypass tắt, dữ liệu nằm trên bind mount bền vững, cổng host chỉ là loopback.
- DB nguồn và volume E2E không đổi.

## Rủi ro đã biết

DB content nguồn có bốn vi phạm khóa ngoại và nhiều workspace không thuộc PRJ_069. Bootstrap giữ nguyên các hàng nguồn, không gán Founder vào chúng. Những dữ liệu đó vẫn cần đối soát riêng trước khi nhập vào workspace PRJ_069.
