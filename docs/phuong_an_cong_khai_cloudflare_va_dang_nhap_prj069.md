# Phương án công khai qua Cloudflare và đăng nhập PRJ_069

**Trạng thái:** Founder đã duyệt thiết kế và hostname; chờ kiểm kê A00 trước khi cấp quyền production  
**Ngày:** 2026-10-28  
**Phạm vi:** ứng dụng SIN Creator OS chạy trên NAS, đăng nhập thật, vai trò Founder và kiểm thử trên dữ liệu hiện có.

## Mục tiêu

Đưa ứng dụng lên Internet qua Cloudflare để Founder và các tài khoản kiểm thử đăng nhập bằng danh tính đã xác minh. Giữ ứng dụng, API, cơ sở dữ liệu, media và worker trên NAS; không mở cổng NAS trực tiếp ra Internet. Dùng dữ liệu nghiệp vụ hiện có và cấu hình LLM Luna 6 qua 9rt.env.

## Những gì đã xác minh

- Zone bahagroup.vn đang hoạt động. Hostname nhap-xaykenh-proj069.bahagroup.vn chưa có bản ghi DNS hoặc ứng dụng Access.
- Tài khoản Cloudflare có Access One-time PIN. Có tunnel riêng PRJ039_XAYKENH_DRAFT với hostname nhap-xaykenh.bahagroup.vn; route đó không bật Access. Không dùng hoặc sửa tunnel/hostname này cho PRJ_069.
- Trên NAS, Compose nas_kiem_thu_that còn chạy cấu hình development với auth bypass. FE chỉ bind loopback và API bind 127.0.0.1:8002; chưa có route Cloudflare riêng cho PRJ_069.
- API đăng nhập hiện tại cấp token từ tài khoản mẫu viết cứng trong mã; không xác thực qua bảng GlobalUser. Kho Baha Auth chỉ xác minh bearer token và lưu danh tính, membership, role assignment; không có kho mật khẩu hay luồng đăng ký. Vì vậy hiện chưa có đăng nhập thật.
- FE đang giữ token trong localStorage, dùng thông tin mặc định khi chưa có hồ sơ người dùng và rewrite /v1/* từ Next.js sang FastAPI. Các yêu cầu đó phải chuyển sang danh tính Cloudflare đã xác minh; không thể chỉ bật tunnel.
- Compose NAS khởi tạo volume bằng các bản sin_content_e2e_test.db và baha_auth_e2e_test.db, cộng sin_dieu_phoi_dung.db. Volume bền vững tên prj069_nas_kiem_thu_that_data; script không chép đè nếu marker đã tồn tại. Các nguồn nghiệp vụ hiện có trong vùng làm việc là sin_content_offline.db và baha_auth_live.db. Chưa đối chiếu dữ liệu bên trong volume đang chạy với hai nguồn này; không đọc nội dung bản ghi người dùng.
- Tài liệu trạng thái ghi nhận 119 người dùng, 78 workspace, 58 ý tưởng và 27 bản nháp kịch bản trong cơ sở dữ liệu nghiệp vụ; các con số này là tham chiếu cũ, không xác nhận trạng thái volume hiện tại.
- Kế hoạch RBAC gốc đang để A00–A12 NOT_STARTED; cổng phát hành yêu cầu kiểm kê, kiểm thử bảo mật, dry-run migration và chứng minh rollback. Mục tiêu này cần đóng các cổng thuộc phạm vi đăng nhập và phát hành trước khi mở public.

## Phương án đề xuất

### Cloudflare và mạng

1. Tạo tunnel riêng PRJ069_SIN_CREATOR_PROD và hostname nhap-xaykenh-proj069.bahagroup.vn.
2. Đặt Cloudflare Access trước toàn bộ hostname, dùng One-time PIN và allowlist email tường minh. Không mở đăng ký công khai. Người dùng nhận mã qua email, không đặt mật khẩu ứng dụng mới.
3. Ưu tiên tunnel remotely managed riêng cho PRJ_069; đặt `cloudflared` trên cùng Docker network với FE/API và cấp tunnel token bằng tệp secret runtime. Tạo published application path route `/v1` tới API, route mặc định cùng hostname tới FE; Cloudflare giữ nguyên path tới origin. Theo Compose canonical, origin là `http://api_kiem_thu_that:8000` và `http://giao_dien_kiem_thu_that:3000` trên network `mang_kiem_thu`. Access bảo vệ toàn hostname. Cách này đưa header `Cf-Access-Jwt-Assertion` tới thẳng API, không phụ thuộc Next.js có chuyển tiếp assertion hay không. FE/API không publish cổng host. Nếu dùng local ingress YAML thay cho route dashboard thì path phải là Go regexp, ví dụ `^/v1(/.*)?$`; `/v1/*` không phải wildcard path trong cú pháp đó. Lưu token ngoài Git, Compose được render và log; hướng dẫn đối chiếu tại `03_ban_lam_viec/sin_content_api/08_kiem_thu/bang_chung/tra_cuu_huong_dan_public_nas_cloudflare_20261028.md`.
4. API xác minh chữ ký, issuer, audience, thời hạn và email của `Cf-Access-Jwt-Assertion` do Cloudflare ký; không tin header email tùy ý, bearer giả hoặc giá trị do trình duyệt gửi. Ghép danh tính với GlobalUser/membership trong DB rồi chạy RBAC hiện có. Theo tài liệu Cloudflare, assertion được gửi tới origin và nên được xác minh bằng khóa công khai; không chỉ đọc cookie `CF_Authorization`.
5. Nguồn tham khảo triển khai: [xác minh Access JWT](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/), [tunnel token](https://developers.cloudflare.com/tunnel/reference/tunnel-tokens/), [route dashboard](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/) và [quy tắc ingress local](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/). Tổng hợp repo công khai và đối chiếu NAS nằm tại `03_ban_lam_viec/sin_content_api/08_kiem_thu/bang_chung/tra_cuu_huong_dan_public_nas_cloudflare_20261028.md`.

### Tài khoản và quyền

- Một danh tính Founder được ánh xạ tới một GlobalUser, membership ACTIVE và role WORKSPACE_OWNER trong workspace PRJ_069. “Full quyền” ở phương án này có nghĩa là toàn quyền nghiệp vụ trong workspace PRJ_069, gồm tạo, sửa, xóa, gửi và duyệt nội dung; không tự mở rộng sang các workspace khác hoặc quyền PLATFORM_OWNER toàn hệ thống. Cấu hình LLM tiếp tục được nạp từ `9rt.env` trên NAS.
- Giai đoạn đầu chỉ cho phép email Founder qua Cloudflare Access; không tạo hoặc allowlist tài khoản test riêng. Kiểm thử chặn tự duyệt của vai trò thường bằng dữ liệu kiểm thử cô lập trước khi public.
- Không nhận mật khẩu qua chat và không tạo mật khẩu dùng chung. Cloudflare Access OTP là bước xác thực; Baha Auth tiếp tục quyết định quyền nghiệp vụ.
- Chỉ các email đã được Founder chỉ định mới được thêm vào Access allowlist. Tài khoản không có membership hợp lệ bị từ chối kể cả khi vượt qua OTP.

### Quyền Founder tự duyệt

Founder đã yêu cầu ngoại lệ tự duyệt. Thực hiện ngoại lệ có phạm vi hẹp, dựa trên danh tính Founder đã provision ở phía máy chủ; không dựa vào role, is_owner hay cờ do client gửi. Ngoại lệ cho phép Founder tự duyệt các nội dung nghiệp vụ do mình tạo trong workspace được gán. Tài khoản khác tiếp tục bị chặn tự duyệt.

Ngoại lệ chỉ bỏ điều kiện người duyệt khác người tạo. Vẫn bắt buộc xác minh workspace, quyền hành động, phiên bản/hash hiện hành, thứ tự trạng thái, kiểm định sự thật/nội dung, ghi audit bất biến và kiểm tra lại trước khi publish. Không cấp quyền vượt workspace, bỏ kiểm tra nội dung, bỏ điều kiện TikTok/provider, hay tự động đăng bài.

> Đây là thay đổi chính sách có chủ đích so với RBAC gốc vốn cấm tự duyệt. Cần ghi policy version và audit reason riêng; acceptance test AUTH-060 phải được cập nhật thành: người dùng thường bị từ chối, Founder được phép trong đúng workspace và mọi điều kiện còn lại vẫn được giữ.

### Cơ sở dữ liệu và LLM

- Giữ nguyên volume hiện có; trước khi đổi cấu hình hoặc schema, chụp SQLite nhất quán, kiểm tra integrity_check, đối chiếu số lượng bảng/bản ghi và lưu điểm khôi phục trong 90_sao_luu/.
- Không xóa, khởi tạo lại hoặc seed lại volume. Dùng `sin_content_offline.db` và `baha_auth_live.db` làm cặp nguồn nghiệp vụ dự kiến theo yêu cầu dùng dữ liệu thật; trước khi chạy phải đối chiếu read-only với volume đang chạy và giữ nguyên bản sao lưu. Nếu volume có dữ liệu mới hơn hoặc không tương thích, dừng chuyển đổi và báo chênh lệch; chỉ sau khi xác định nguồn chuẩn mới chạy dry-run/diff rồi migration có rollback.
- Tắt DEV_AUTH_BYPASS; chạy cấu hình production với dữ liệu đã xác định, SYNTHETIC_DATA_ALLOWED=false. Giữ LLM thật qua 9rt.env, model cx/gpt-6-luna; không in hoặc sao chép secret.

## Kiểm thử chấp nhận

1. Truy cập chưa xác thực bị Cloudflare Access chặn; email ngoài allowlist không vào được. Chỉ người vượt OTP mới tới ứng dụng.
2. Chữ ký JWT sai, issuer/audience sai, hết hạn hoặc thiếu danh tính bị API từ chối; giả mạo email/header và client gửi role/workspace khác không làm tăng quyền.
3. Founder đăng nhập, thấy workspace được cấp, tạo nội dung và tự duyệt được; audit ghi danh tính Founder, action, workspace, policy version, artifact version/hash và lý do ngoại lệ.
4. Trong kiểm thử cô lập, tài khoản STRATEGIST tạo/gửi kịch bản nhưng không thể tự duyệt; Founder có thể duyệt phiên bản được phép, gồm nội dung do chính Founder tạo. Người dùng ngoài workspace không đọc/sửa được tài nguyên.
5. Phiên bản/hash cũ, nội dung chưa đạt kiểm định hoặc sai trạng thái vẫn bị từ chối, kể cả với Founder.
6. API/FE không truy cập được từ Internet qua cổng NAS trực tiếp; chỉ đi qua tunnel và Access.
7. Kiểm tra integrity_check, đối chiếu dữ liệu trước/sau, thử rollback từ snapshot; LLM Luna probe đạt mà không lộ khóa.

Không gửi nội dung lên TikTok trong smoke test mặc định. Tạo nội dung bằng LLM thật chỉ sau khi xác nhận hạn mức và endpoint đang hoạt động; không giả lập kết quả thành thành công.

## Phạm vi tệp dự kiến

- sin_content_api/src/modules/auth/router.py: bỏ tài khoản mẫu; trả hồ sơ từ danh tính đã xác minh.
- sin_content_api/src/auth/tenancy.py và sin_content_api/src/auth/platform_auth.py: xác minh Access assertion và nạp membership/role hiện hành.
- baha_auth/src/xac_minh_danh_tinh.py, baha_auth/src/policy/evaluator.py và baha_auth/src/services/approval_service.py: xác thực danh tính và ngoại lệ tự duyệt Founder có audit.
- sin_creator_os/src/lib/api/auth-api.ts, sin_creator_os/src/app/api/auth/*, sin_creator_os/src/proxy.ts, sin_creator_os/next.config.mjs và các lớp gọi API: chuyển khỏi token mẫu/localStorage, dùng phiên Access và cùng hostname.
- ha_tang/nas_kiem_thu_that/docker-compose.yml, .gitignore/ignore tương ứng: thêm connector riêng, giữ secret ngoài Git và khóa bypass. Chỉ sửa bản Compose thuộc vùng 03_ban_lam_viec.
- Kiểm thử auth, RBAC, approval, API proxy và kiểm tra cấu hình Compose. Bằng chứng kiểm thử lưu ở 08_kiem_thu/bang_chung/ sau khi thực thi.

Không sửa các tunnel Cloudflare khác, không dùng lại hostname của PRJ039, không mở port router/NAS, không đổi DB hay cấp quyền live trước khi snapshot/dry-run và xác nhận phát hành cuối.

## Việc còn lại trước khi public

1. Email Founder đã được cung cấp; giai đoạn đầu chỉ allowlist tài khoản này, không tạo tài khoản test riêng.
2. Hoàn tất hồ sơ A00, xác định workspace và DB nguồn chuẩn, kiểm tra rollback trước khi đổi phân quyền sống.
3. Ngay trước khi tạo Access app/route/DNS công khai hoặc cấp quyền live, trình bày cấu hình cuối gồm hostname, allowlist, origin/port, dữ liệu và kết quả kiểm thử để Founder xác nhận hành động đó.

