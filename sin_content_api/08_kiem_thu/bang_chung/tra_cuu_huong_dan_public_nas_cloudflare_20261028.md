# Rà cứu hướng dẫn public ứng dụng PRJ_069 trên NAS

**Ngày:** 2026-10-28  
**Phạm vi:** Đọc tài liệu Cloudflare/Synology và repo GitHub công khai; đối chiếu với Compose PRJ_069 hiện có. Không sửa DNS, tunnel, Access, dữ liệu hoặc container.

## Kết luận triển khai

- Dùng một Cloudflare Tunnel riêng cho PRJ_069, quản lý từ Cloudflare Dashboard. Cloudflare Tunnel khởi tạo kết nối outbound từ NAS, không cần mở cổng router/NAS vào Internet. Dùng hostname riêng `nhap-xaykenh-proj069.bahagroup.vn`; không sửa tunnel hoặc hostname dự án khác.
- Đặt Cloudflare Access trước toàn hostname, bật One-time PIN và allowlist email cụ thể. Connector không cần mở trình duyệt đăng nhập trên NAS: lấy tunnel token từ dashboard và cấp cho `cloudflared` bằng tệp secret runtime. Token đủ quyền khởi chạy tunnel nên phải giữ ngoài Git, Compose được render và log.
- Gắn `cloudflared` vào Docker network nội bộ của project. Theo Compose canonical hiện có, API là `api_kiem_thu_that:8000`, FE là `giao_dien_kiem_thu_that:3000`, network là `mang_kiem_thu`. Route `/v1` và các đường dẫn con tới API; route hostname mặc định tới FE. Path được giữ nguyên tới origin để FastAPI tiếp tục nhận `/v1/...`. Không publish cổng host cho connector/API/FE.
- Hai kiểu cấu hình route có cú pháp khác nhau. Với tunnel quản lý từ dashboard, tạo published application path route `/v1` rồi route mặc định cùng hostname tới FE. Nếu chuyển sang `cloudflared` local ingress YAML, `path` là biểu thức chính quy Go: dùng `^/v1(/.*)?$`, đặt trước route FE và kết thúc cấu hình bằng catch-all `http_status:404`. Không dùng `/v1/*` như wildcard regex: trong Go regexp, `*` lặp dấu `/` ngay trước nó.
- API phải xác minh chữ ký JWT Access, issuer, audience và thời hạn trên `Cf-Access-Jwt-Assertion`; sau đó mới ánh xạ email sang GlobalUser/membership. Access OTP chỉ xác thực người; Baha Auth vẫn áp dụng quyền workspace và approval.

## Bài học từ repo công khai

1. Repo chính thức [Vercel Next.js `examples/with-docker`](https://github.com/vercel/next.js/tree/canary/examples/with-docker) dùng multi-stage, standalone output và user không phải root cho image production. README nhắc `.env` trong build context có thể đi vào standalone output; secret server phải cấp lúc chạy, không dùng build arg. PRJ_069 FE hiện build nguyên cây, chạy root, không bật standalone; Compose NAS còn ép `npm run dev`. Trước khi public cần image/runtime production.
2. Repo cộng đồng [lowestprime/KenMatch — Synology NAS deployment](https://github.com/lowestprime/KenMatch/blob/main/docs/synology-nas-deploy.md) tách mã runtime với dữ liệu bind-mounted để rebuild không chạm dữ liệu; hướng dẫn backup mã hóa ra đích ngoài NAS và giữ cấu hình đã khử secret trong Git. Có thể dùng làm mẫu vận hành/backup, nhưng cần áp dụng theo quyền UID/GID và mô hình SQLite của PRJ_069.
3. Repo cộng đồng [kareemf/photo-stack-playbook](https://github.com/kareemf/photo-stack-playbook) minh họa Compose/cloudflared trên NAS, nhưng hướng dẫn local `tunnel login` cần browser và có ví dụ `chmod 777`; không dùng hai cách đó cho PRJ_069. Ưu tiên tunnel remotely managed, token file runtime và quyền tệp hẹp.
4. Đường dẫn GitHub đã ghi cho repo PRJ_069 không trả nội dung công khai khi kiểm tra không đăng nhập. Kết quả này chỉ cho biết repo không đọc được công khai tại URL đó; chưa thể phân biệt repo private, đã xóa hay đổi tên.

## Đối chiếu trạng thái NAS hiện tại

- Compose canonical đang gắn `sin_content_e2e_test.db` và `baha_auth_e2e_test.db`, bật `APP_ENV=development`, `DEV_AUTH_BYPASS=1`, và FE chạy chế độ development. Chưa có `cloudflared` service. Không public hoặc khởi động cấu hình này.
- Volume hiện bắt nguồn từ seed E2E; chưa đọc trực tiếp nội dung volume. Cặp DB offline/auth live hiện không đồng bộ đủ điều kiện, Founder chưa có trong Auth DB, workspace `default_ws` thiếu approval policy ACTIVE, DB content có vi phạm khóa ngoại và model lưu không phải Luna 6.
- Vì vậy kết quả nghiên cứu mới chốt được kiến trúc mạng. Chưa đạt điều kiện dữ liệu, định danh/quyền và cấu hình LLM để dùng thật. A00 vẫn BLOCKED; chưa bật public.

## Nguồn chính thức dùng để kiểm tra

- [Cloudflare Tunnel fundamentals](https://developers.cloudflare.com/tunnel/concepts/): kết nối do `cloudflared` mở từ trong mạng; Quick Tunnel chỉ dành cho tạm thời.
- [Cloudflare private web application](https://developers.cloudflare.com/cloudflare-one/setup/secure-private-apps/private-web-app/): Access OTP, allowlist và published hostname.
- [Cloudflare remotely-managed tunnel routes](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/): route theo path giữ nguyên path tới service.
- [Cloudflare tunnel token](https://developers.cloudflare.com/tunnel/reference/tunnel-tokens/): tunnel token đủ để khởi chạy connector; phải coi là bí mật.
- [Cloudflare local ingress configuration](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/): path regex theo Go regexp, thứ tự ingress và catch-all.
- [Cloudflare Access JWT validation](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/): xác minh chữ ký bằng JWKS, issuer và audience.
- [Synology Container Manager Project](https://kb.synology.com/en-global/DSM/help/ContainerManager/docker_project): phân biệt Stop với Clean/Delete; Clean xóa cả volume do project tạo, không dùng cho volume dữ liệu PRJ_069.

## Việc tiếp theo

1. Hoàn tất A00 read-only, xác định và đối chiếu cặp DB/workspace chuẩn; kiểm tra volume và tạo bản sao lưu SQLite nhất quán trước khi đổi cấu hình.
2. Hoàn tất ma trận quyền, hồ sơ phát hành và provision Founder trong đúng workspace theo quy định dự án; không cấp quyền production trước các cổng này.
3. Chốt cấu hình Luna 6 từ `9rt.env` mà không in secret; kiểm tra cấu hình runtime ghi đè singleton DB hay không.
4. Chuyển Compose/image sang production: bỏ bypass, bỏ DB E2E, FE chạy production, giữ dữ liệu volume đã xác định; chỉ sau đó mới thêm connector, tạo Access app/route/DNS mới và chạy nghiệm thu.

**Chưa thực hiện:** không chạy test, build, container, LLM hoặc thay đổi Cloudflare/NAS trong lượt rà cứu này.
