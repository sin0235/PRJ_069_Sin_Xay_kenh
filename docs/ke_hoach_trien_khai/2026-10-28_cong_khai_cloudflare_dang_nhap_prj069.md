# Kế hoạch triển khai công khai Cloudflare và đăng nhập PRJ_069

**Mục tiêu:** Đưa SIN Creator OS lên `nhap-xaykenh-proj069.bahagroup.vn`, yêu cầu Cloudflare Access OTP và xác thực quyền từ Baha Auth trên dữ liệu nghiệp vụ đã được đối chiếu.

**Kiến trúc:** Tunnel remotely managed riêng trên NAS định tuyến path `/v1` thẳng tới API và route mặc định tới FE; Cloudflare Access bảo vệ toàn hostname bằng allowlist email. API xác minh `Cf-Access-Jwt-Assertion`, ghép email đã xác minh với GlobalUser và membership đang hoạt động. Founder có `WORKSPACE_OWNER` trong đúng workspace PRJ_069 và ngoại lệ tự duyệt nội dung của mình có ghi audit. Path được giữ nguyên. Nếu dùng local ingress YAML thì `/v1` phải được biểu diễn bằng Go regexp `^/v1(/.*)?$`, không dùng `/v1/*`.

**Công nghệ:** FastAPI, SQLAlchemy, Next.js, `cryptography`, `httpx`, Docker Compose, Cloudflare Access One-time PIN và Cloudflare Tunnel.

**Tài liệu thiết kế:** `03_ban_lam_viec/docs/phuong_an_cong_khai_cloudflare_va_dang_nhap_prj069.md`.

## Ràng buộc chung

- Chỉ sửa mã, cấu hình và tài liệu trong `03_ban_lam_viec/`; dữ liệu nguồn gốc và bản giải nén chỉ đọc.
- Không đọc, ghi log, commit hoặc đưa giá trị bí mật trong `9rt.env`, `xac_thuc_api.env`, `xac_thuc_fe.env` hay tunnel token.
- Không sửa tunnel, DNS, Access app hoặc hostname của dự án khác; hostname mới là `nhap-xaykenh-proj069.bahagroup.vn`.
- Không mở cổng NAS/router ra Internet; chỉ connector tunnel kết nối outbound. API/FE không publish port public.
- Không bật `DEV_AUTH_BYPASS`, tài khoản giả, mật khẩu dùng chung hoặc tự đăng ký công khai trong cấu hình public.
- Không xóa, seed lại, đổi nguồn hay migrate volume đến khi đã xác định DB chuẩn, sao lưu nhất quán và chứng minh rollback.
- Chỉ cho email Founder được cung cấp vào Access allowlist giai đoạn đầu; chưa tạo tài khoản test riêng.
- Ngoại lệ tự duyệt chỉ dựa trên Founder đã xác minh và provision phía máy chủ; không bỏ kiểm tra tenant, phiên bản/hash, trạng thái, policy stage, nội dung hoặc audit.
- Cổng A00 và hồ sơ phát hành do `AGENTS.md` yêu cầu phải đạt trước khi sửa phân quyền sống hoặc cấp vai trò trên production.

## Tệp dự kiến

- `03_ban_lam_viec/baha_auth/src/xac_minh_danh_tinh.py`: thêm bộ xác minh Access RS256 riêng, giữ nguyên bộ xác minh HS256 đang dùng bởi các caller khác.
- `03_ban_lam_viec/sin_content_api/src/auth/tenancy.py`, `src/auth/platform_auth.py`, `src/modules/auth/router.py`: xác minh assertion, ánh xạ danh tính/membership và trả phiên hiện hành; bỏ đăng nhập mẫu cùng giải mã token không xác minh chữ ký.
- `03_ban_lam_viec/baha_auth/src/policy/evaluator.py`, `src/services/danh_tinh_service.py`, `src/services/approval_service.py`: xác định Founder từ email đã xác minh và cấu hình máy chủ; ghi quyết định tự duyệt Founder với lý do audit riêng.
- `03_ban_lam_viec/sin_creator_os/src/lib/api/auth-api.ts`, `src/components/auth/auth-guard.tsx`, trang/route đăng nhập và đăng xuất, cùng các dịch vụ API đang gọi `AuthApi` hoặc dùng `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_CONTENT_API_URL`: chuyển sang phiên cùng hostname, bỏ localStorage/token giả và endpoint API localhost trong trình duyệt.
- `03_ban_lam_viec/ha_tang/nas_kiem_thu_that/docker-compose.yml` trên NAS: gắn connector remotely managed vào `mang_kiem_thu`, định tuyến `/v1` tới `api_kiem_thu_that:8000` và route mặc định tới `giao_dien_kiem_thu_that:3000`; tắt bypass và khóa cấu hình public. Dùng token file runtime ngoài Git.
- Các kiểm thử hiện có `baha_auth/tests/test_kiem_tra_phan_quyen_nhom_1.py`, `test_a02_a07_comprehensive.py`, `sin_content_api/tests/test_tenancy.py`, `test_dev_auth_bypass.py` và kiểm thử FE phù hợp.

## Các bước

### Bước 1: Hoàn tất kiểm kê A00 và đối chiếu dữ liệu, chỉ đọc

- [ ] Đối chiếu cấu hình Compose, volume đang gắn, nguồn `sin_content_offline.db` và `baha_auth_live.db`; chỉ ghi nhận đường dẫn, schema, trạng thái integrity và số lượng bản ghi, không xuất nội dung người dùng.
- [ ] Xác định DB nghiệp vụ chuẩn và workspace PRJ_069; nếu volume chứa dữ liệu mới hơn hoặc chưa rõ nguồn chuẩn, dừng provision và yêu cầu Founder chốt nguồn.
- [ ] Lập hồ sơ A00, threat model, ma trận quyền và kế hoạch rollback để Founder duyệt trước mọi thay đổi quyền production.
- [ ] Kiểm tra: có báo cáo so sánh định danh DB, workspace và số lượng bảng/bản ghi; chưa ghi vào DB, volume, Cloudflare hay tunnel.

### Bước 2: Viết kiểm thử lỗi trước và xác minh Cloudflare JWT

**Tệp:** `baha_auth/src/xac_minh_danh_tinh.py`; thêm kiểm thử đơn vị cạnh các kiểm thử verifier hiện có.

- [x] Thêm kiểm thử assertion RS256 hợp lệ với issuer, audience, email, hạn dùng và khóa JWKS giả lập; thêm trường hợp sai chữ ký, sai audience/issuer, thiếu email, hết hạn và `kid` không có.
- [x] Chạy kiểm thử verifier mới: assertion hợp lệ được chấp nhận, trường hợp sai bị từ chối.
- [x] Thêm hàm verifier Access độc lập, lấy issuer và JWKS từ cấu hình máy chủ; xác minh chữ ký và các claim bắt buộc, cache JWKS có giới hạn và giữ nguyên `verify_bearer_token` HS256.
- [x] Chạy kiểm thử verifier mới cùng các kiểm thử RBAC và approval liên quan: 70 đạt.

### Bước 3: Ánh xạ danh tính ở API và bỏ đăng nhập giả

**Tệp:** `sin_content_api/src/auth/tenancy.py`, `src/auth/platform_auth.py`, `src/modules/auth/router.py`; kiểm thử `sin_content_api/tests/test_tenancy.py` và kiểm thử auth hiện có.

- [x] Viết kiểm thử API: chỉ ánh xạ Access assertion hợp lệ sang GlobalUser/membership đang hoạt động; kiểm thử email lạ, assertion giả/hết hạn, membership và workspace không hợp lệ.
- [x] Kiểm tra các luồng bearer/demo cũ bị từ chối trong cấu hình production; bearer nội bộ chỉ còn cho test/local.
- [x] Dùng assertion Cloudflare làm danh tính chính ở các dependency API; server lấy workspace/membership/role từ DB và cung cấp endpoint phiên người dùng hiện hành.
- [x] Bỏ luồng token demo và giải mã payload `/auth/me` không xác minh; giữ nguyên verifier HS256 ở caller nội bộ không thuộc đăng nhập web.
- [x] Chạy kiểm thử tenancy, bypass và auth liên quan trong môi trường fixture: 27 đạt.

### Bước 4: Thêm ngoại lệ tự duyệt Founder có kiểm soát

**Tệp:** `baha_auth/src/policy/evaluator.py`, `src/services/danh_tinh_service.py`, `src/services/approval_service.py`; kiểm thử `test_kiem_tra_phan_quyen_nhom_1.py`, `test_a02_a07_comprehensive.py` và `test_kiem_thu_duyet_tac_vu_nen.py`.

- [x] Cập nhật kiểm thử AUTH-060: tài khoản thường, kể cả workspace owner không phải Founder, vẫn bị từ chối tự duyệt; ngoại lệ chỉ áp dụng cho Founder đã xác minh và được cấp quyền workspace.
- [x] Kiểm thử Founder không vượt workspace, policy stage, thứ tự quyết định, version/hash hoặc attribution; thao tác được phép ghi audit lý do `FOUNDER_SELF_APPROVAL_EXCEPTION`.
- [x] Sửa evaluator và service: trạng thái Founder được xác lập từ danh tính đã xác minh, email cấu hình máy chủ và user trong DB; client không thể gửi cờ Founder. Không thay đổi policy matrix nguồn.
- [x] Chạy kiểm thử approval/RBAC liên quan. Không sửa tài liệu nguồn protected trong `02_nguyen_ban_giai_nen/`.

### Bước 5: Chuyển FE sang phiên Access và cùng hostname

**Tệp:** `sin_creator_os/src/lib/api/auth-api.ts`, auth guard, login/logout, external landing page và các dịch vụ đang gắn API URL localhost.

- [x] Chuyển trạng thái người dùng/workspace sang endpoint phiên; bỏ profile Founder giả, token đăng nhập trong localStorage/cookie thường và bearer token do FE giữ.
- [x] Chuyển yêu cầu API và media asset sang cùng origin; API kiểm tra membership phía máy chủ.
- [x] Đổi đăng xuất sang Cloudflare Access logout; giao diện đăng nhập chỉ hướng dẫn xác minh OTP, không có ô mật khẩu ứng dụng.
- [x] TypeScript và `npm run build` đạt với 43 route.
- [ ] Biome chưa chạy trong lượt này.

### Bước 6: Cấu hình public riêng, sau xác nhận tại thời điểm thay đổi

**Tệp NAS:** `03_ban_lam_viec/ha_tang/nas_kiem_thu_that/docker-compose.yml`, `.gitignore` và tệp secret ngoài Git nếu cần.

- [ ] Tạo tunnel remotely managed riêng `PRJ069_SIN_CREATOR_PROD`; cấu hình hostname `nhap-xaykenh-proj069.bahagroup.vn` với Access One-time PIN chỉ cho email Founder, route path `/v1` tới API và route mặc định tới FE. Connector đọc tunnel token từ tệp secret runtime; không cần `cloudflared tunnel login` trên NAS.
- [ ] Kiểm tra thay đổi chỉ tác động DNS record, tunnel và Access app mới của hostname này; không cập nhật tunnel khác. Xác nhận ngay trước thao tác tạo Access app/route/DNS vì đây là mở điểm truy cập Internet.
- [ ] Lưu tunnel token ngoài Git/Compose output; đặt issuer/AUD từ Access app mới trong cấu hình API mà không chép token hoặc API key vào log.
- [ ] Sau khi báo cáo so sánh DB và snapshot/rollback được duyệt, provision GlobalUser, membership và `WORKSPACE_OWNER` cho Founder đúng một workspace. Dừng nếu cổng A00 hoặc văn bản phát hành chưa được duyệt.
- [ ] Tắt bypass và synthetic data trong public profile. Giữ dữ liệu volume; không seed/migrate nếu chưa có dry-run diff và rollback đã xác nhận.

### Bước 7: Kiểm thử nghiệm thu trước và sau khi mở hostname

- [ ] Trên fixture cô lập: kiểm tra OTP/allowlist, JWT hợp lệ/giả/hết hạn, email không có user/membership, cô lập tenant, quyền Founder và chặn tự duyệt tài khoản thường.
- [ ] Trên NAS trước khi public: health/readiness, FE gọi API cùng origin, không truy cập API qua port ngoài tunnel, LLM Luna 6 probe bằng prompt tổng hợp và không ghi lộ khóa.
- [ ] Sau khi hostname được mở: kiểm tra người ngoài allowlist bị Access chặn, Founder đăng nhập được, audit tự duyệt đúng lý do, và truy cập API trực tiếp qua IP/port NAS từ Internet thất bại.
- [ ] Kiểm tra integrity DB, số lượng bản ghi trước/sau và thử hướng rollback; lưu log kiểm thử đã khử bí mật trong `08_kiem_thu/bang_chung/` chỉ khi có quyền ghi theo hồ sơ dự án.
- [ ] Cập nhật trạng thái dự án, trang hành trình và checkpoint theo đúng gate sau khi có bằng chứng; không đánh dấu gate chưa hoàn tất.

## Rà soát phạm vi và rủi ro

- Điểm gọi FE đã được tìm bằng `rg`: `AuthApi` được dùng bởi các dịch vụ nội dung, media, voice, TikTok, publishing, platform config, sidebar và auth guard; mọi base URL localhost phải được rà để tránh browser gọi thẳng API bỏ qua cùng hostname.
- Điểm xác minh bearer HS256 còn được gọi trong Baha Auth API/worker; phải giữ tương thích, không thay hàm dùng chung theo kiểu phá caller.
- Dữ liệu và trạng thái thật của volume NAS chưa đối chiếu; hiện ba container PRJ069 đang dừng. Không đưa cấu hình development với `DEV_AUTH_BYPASS=1` ra Internet.
- Hiện chưa có Access app/DNS/tunnel PRJ069; OTP provider có sẵn. Kết quả tunnel creation và audience tag chỉ có sau bước triển khai được xác nhận.
- `AGENTS.md` chặn thay đổi role sống trước hồ sơ A00, ma trận đã duyệt và phát hành Founder. Nếu cổng đó chưa hoàn thành, có thể hoàn thiện/test mã và cấu hình cô lập nhưng không cấp quyền Founder trên DB production hoặc mở ứng dụng để sử dụng thật.

Tham khảo hướng dẫn repo công khai và kết quả đối chiếu cấu hình NAS tại `03_ban_lam_viec/sin_content_api/08_kiem_thu/bang_chung/tra_cuu_huong_dan_public_nas_cloudflare_20261028.md`.

## Cách thực hiện

Thực hiện tuần tự trong phiên Codex hiện tại để tránh xung đột sửa file và tốn thời gian build song song. Không build NAS lại cho đến khi kiểm thử auth/approval/FE ở local đạt; không mở hostname trong cùng bước build đầu tiên.
