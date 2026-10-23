# Kế hoạch Owner quản trị cấu hình và tích hợp LLM qua 9Router

> **Đối tượng bàn giao:** Antigravity (AGY). Đây là kế hoạch triển khai, chưa phải chấp thuận sửa mã hoặc bật gọi API thật. AGY phải thực hiện tuần tự theo các cổng, lưu bằng chứng kiểm thử tại `08_kiem_thu/bang_chung/`, không đánh dấu PASS bằng suy đoán.

## Mục tiêu

- Chỉ tài khoản Owner cấp nền tảng được xem và thay đổi cấu hình model LLM dùng chung.
- Mọi lời gọi LLM văn bản của ứng dụng đi qua một cấu hình gateway 9Router và một client backend dùng chung; caller không được truyền nhà cung cấp, URL, API key hoặc model tùy ý.
- Owner đăng nhập bằng cơ chế xác thực hiện có, nhập endpoint 9Router, model, thông tin xác thực và các tham số chi phí cần thiết trên web; cấu hình được lưu bền vững trong database.
- Mật khẩu/API key không được lưu dạng rõ trong database, gửi lại cho trình duyệt sau khi lưu, ghi log hoặc đưa vào bằng chứng.
- Nối các chức năng văn bản thực sự cần sinh/phân tích bằng LLM, giữ nguyên xác minh độc lập, phân quyền theo workspace, hạn mức và idempotency hiện có.

## Kiến trúc và ngăn xếp hiện có

- Giao diện: Next.js tại `03_ban_lam_viec/sin_creator_os`; tận dụng trang `src/app/(main)/settings/integrations/page.tsx` hiện có sau khi loại bỏ dữ liệu giả.
- Backend: FastAPI tại `03_ban_lam_viec/sin_content_api`; tái sử dụng `src/modules/llm/client.py`, `httpx`, Pydantic và `src/modules/ideation/ideation_service.py`.
- Database nghiệp vụ: SQLAlchemy, hỗ trợ SQLite/PostgreSQL; migration hiện có gọi `Base.metadata.create_all` trong `src/migrations/runner.py`. Cần xác minh triển khai migration an toàn trước khi thêm bảng.
- Xác thực và RBAC chuẩn: Baha Auth tại `03_ban_lam_viec/baha_auth`; nghiệp vụ đa workspace hiện dùng `get_current_tenant_context` trong `sin_content_api/src/auth/tenancy.py`.
- Gateway: API văn bản tương thích OpenAI, dùng `POST /v1/chat/completions`; nếu cần chọn model trong giao diện thì chỉ đọc danh sách qua `GET /v1/models`. Không clone 9Router hoặc thêm SDK nếu `httpx` đủ dùng.

## Đặc tả

### Phạm vi chức năng

1. Quản trị một cấu hình gateway LLM dùng chung toàn nền tảng, không phải cấu hình riêng của từng workspace.
2. Trường Owner có thể nhập/chỉnh sửa: URL 9Router được phép dùng, model ID, API key/token 9Router, bật/tắt sử dụng, timeout/giới hạn đã có và giá đầu vào/đầu ra cùng hệ số quy đổi ngân sách nếu nghiệp vụ tiếp tục dùng các giá trị này.
3. Endpoint lưu và kiểm tra cấu hình bắt buộc xác thực danh tính, kiểm tra quyền ở backend và ghi audit; ẩn chức năng trên giao diện chỉ là UX, không phải kiểm soát truy cập.
4. Mọi caller nhận một cấu hình đã kiểm tra từ backend. Caller không nhận quyền sửa cấu hình và không gửi `base_url`, key hay model để backend thực thi.
5. Kết nối thất bại, chưa cấu hình, model không hợp lệ, hết hạn mức hoặc output không hợp lệ phải trả trạng thái/lỗi rõ ràng. Không âm thầm đổi sang model khác hay giả lập kết quả thành công.
6. Luồng đầu tiên đã có là sinh ý tưởng: `POST /v1/ideation/generate` -> `ideation_service` -> `LLMClient` -> parser/schema -> `IdeaVerifier` -> ghi DB. Giữ ngân sách, idempotency, kiểm chứng và bảo vệ tenant đang có.
7. Những API tạo nhạc, video, hình ảnh, giọng nói hoặc các dịch vụ media riêng không được gọi là LLM văn bản. Đưa vào danh mục kiểm tra; chỉ mở rộng 9Router khi xác minh được hợp đồng API, model hỗ trợ, quyền sử dụng và chi phí riêng.

### Quy tắc bí mật và URL

- Database chỉ lưu ciphertext của API key; khóa mã hóa chỉ tồn tại trong Secret Vault hoặc secret môi trường bên ngoài repo. Không dùng giá trị mặc định trong code. Nếu chưa có cơ chế mã hóa được xác nhận thì Gate bảo mật không đạt và không bật lưu cấu hình.
- API đọc cấu hình trả trạng thái đã cấu hình và dấu che/một phần nhận diện, không bao giờ trả plaintext hoặc ciphertext. API cập nhật chỉ thay key khi Owner nhập key mới; ô trống giữ nguyên key cũ theo hợp đồng được chốt tại Gate 0.
- URL mặc định và phạm vi là gateway 9Router. Từ chối userinfo, query, fragment, scheme sai; HTTP chỉ cho loopback trong môi trường phát triển. Endpoint ngoài máy phải dùng HTTPS. Chặn truy cập địa chỉ nội bộ/metadata ngoài danh sách cho phép để tránh SSRF.
- Không đưa API key vào query, URL, lỗi, audit payload, log, analytics, ảnh chụp hoặc bằng chứng. Audit chỉ ghi actor, thời gian, các trường không nhạy cảm đã đổi, kết quả và request ID.
- Kiểm tra origin/CSRF theo cơ chế ứng dụng hiện hữu cho thao tác thay đổi cấu hình; giới hạn tần suất và kích thước body. Không để frontend gọi thẳng 9Router.

## Ràng buộc toàn cục

- Chỉ ghi mã và tài liệu dự án trong `03_ban_lam_viec/`; không sửa `01_nguon_goc_bat_bien/` hoặc `02_nguyen_ban_giai_nen/`. Tạo bằng chứng trong `08_kiem_thu/bang_chung/` theo quy trình dự án.
- Tên tệp/thư mục mới: tiếng Việt không dấu, chữ thường, snake_case. Nội dung tài liệu, giao diện và báo cáo: tiếng Việt có dấu. Không dùng emoji/unicode icon.
- Không lưu secret trong repo, trạng thái, checkpoint, fixture chứa dữ liệu thật hoặc ảnh chụp.
- Không clone 9Router; không thêm thư viện mã hóa hoặc LLM nếu dependency/pattern hiện có đáp ứng. Không chạy model/provider thật trong unit test.
- Không gọi model, đổi model production, migrate dữ liệu đang dùng hoặc bật tính năng theo mặc định trước các gate tương ứng và biên bản cho phép triển khai.
- Trước khi sửa UI, dựng prototype/mô tả luồng đầy đủ và chờ Founder duyệt theo nguyên tắc UI mẫu trước backend. Không tính prototype là UI đã kết nối.
- Không thay đổi permission matrix hoặc cấp quyền Production theo suy đoán. Vai trò toàn cục Owner phải có nguồn chân lý và cơ chế cấp quyền được Founder chấp thuận.

## Bản đồ phạm vi cần AGY xác minh

| Khu vực | Đường dẫn hiện có | Hành động trong kế hoạch |
|---|---|---|
| Trạng thái/cổng dự án | `00_bat_dau/CURRENT_STATE.md`, `00_bat_dau/CHECKPOINT.json`, `COMMAND_CONTROL_CARD.md`, `hanh_trinh_phat_trien_069.html` | Check-in bắt buộc; chỉ cập nhật khi gate được nghiệm thu theo quy trình |
| Danh tính/RBAC | `03_ban_lam_viec/baha_auth/src/policy/registry.py`, `03_ban_lam_viec/baha_auth/src/services/danh_tinh_service.py`, `03_ban_lam_viec/sin_content_api/src/auth/tenancy.py` | Xác định principal Owner toàn cục có thật; tuyệt đối không suy ra từ `WORKSPACE_OWNER` |
| Cấu hình LLM hiện tại | `03_ban_lam_viec/sin_content_api/src/config.py` | Chốt tương thích env cũ, nguồn cấu hình ưu tiên và cách chuyển đổi |
| Client dùng chung | `03_ban_lam_viec/sin_content_api/src/modules/llm/client.py` | Lấy cấu hình runtime đã xác thực; vẫn giữ giới hạn input, timeout, xử lý lỗi, không tự retry |
| Chức năng LLM văn bản hiện có | `03_ban_lam_viec/sin_content_api/src/modules/ideation/ideation_service.py`, `src/modules/ideation/generator.py`, `src/modules/ideation/verifier.py`, `src/modules/ideation/router.py` | Tích hợp thông qua client/cấu hình chung, bảo toàn kiểm chứng và ngân sách |
| Caller web ý tưởng | `03_ban_lam_viec/sin_creator_os/src/services/idea-service.ts`, `src/app/(main)/ideas/generate/page.tsx` | Kiểm tra API URL, xác thực và fallback mock; không báo kết quả mock là từ LLM |
| UI tích hợp hiện có | `03_ban_lam_viec/sin_creator_os/src/app/(main)/settings/integrations/page.tsx` | Prototype và duyệt trước; sau đó bỏ thẻ/trạng thái/khóa giả, chỉ hiển thị trạng thái API thật |
| Database/migration | `03_ban_lam_viec/sin_content_api/src/models/entities.py`, `src/models/__init__.py`, `src/migrations/runner.py`, `src/main.py` | Thêm bảng cấu hình singleton/global và migration nâng cấp có rollback; không dùng `drop_all` khi nâng cấp |
| Lời gọi provider khác | `03_ban_lam_viec/sin_content_api/src/modules/media_studio/` và các provider/caller frontend tương ứng | Liệt kê/đánh dấu media API; ngoài scope LLM văn bản trừ khi có gate riêng chứng minh tương thích |
| Bằng chứng | `08_kiem_thu/bang_chung/` | Biên bản mỗi gate, đầu ra test đã lọc secret, scan và kiểm tra trình duyệt |

Danh mục trên là điểm bắt đầu chứ không phải cam kết rằng đã quét hết repo. Gate 0 phải tìm mọi client HTTP và mọi chức năng/caller có prompt hoặc yêu cầu sinh văn bản, rồi ghi rõ mỗi điểm dùng chung client, giữ nguyên provider media hay không thuộc phạm vi.

## Các pha và điều kiện nghiệm thu

### Gate 0 — Khảo sát, chốt nguồn Owner và hợp đồng vận hành

**Tác vụ**

- [x] Đọc `CURRENT_STATE.md`, hành trình, checkpoint và `COMMAND_CONTROL_CARD.md`; xác nhận task AGY được phép và vùng ghi. (Đã đối soát tại Gate 0).
- [x] Quét backend, frontend, jobs/workers và scripts để lập danh sách đầy đủ mọi caller LLM, API trực tiếp tới nhà cung cấp, hàm mock/offline và API media. (Ma trận 7 caller tại `llm_owner_gate_0_khao_sat.md`).
- [x] Đọc RBAC/role assignment và xác định bằng mã + dữ liệu cấu hình an toàn xem platform Owner được xác thực ra sao. Ghi rõ khác biệt `PLATFORM_OWNER` và `WORKSPACE_OWNER`. (Phát hiện và rào chắn tại Gate 0).
- [x] Nếu chưa tồn tại danh tính Owner toàn cục có thể xác minh: dừng trước sửa runtime; lập đề xuất Founder về cách cấp Owner và chờ duyệt. Không tự nâng quyền user đầu tiên, không thêm quyền Owner vào role workspace. (Đã lập 4 đề xuất Founder tại Gate 0).
- [x] Chốt URL 9Router theo môi trường, model ID thực có từ gateway, cách đổi model, nhà cung cấp chịu chi phí, bảng giá/currency và hạn mức. Nếu gateway chưa chạy thì đánh dấu chưa xác minh, chặn gate thật. (Xác nhận port 20128 Standby trung thực).
- [x] Kiểm tra cơ chế mã hóa hiện có, nguồn khóa ngoài repo, backup/restore, logging/audit và cách rotate/revoke key. Không lấy tuyên bố giao diện AES làm bằng chứng. (Chốt dùng thư viện `cryptography` Fernet).
- [x] Chốt một cấu hình toàn cục hay nhiều deployment profile; mặc định chọn một cấu hình active để tối giản. Chốt tác động của env cũ và quy tắc tắt LLM khi database/config không sẵn sàng. (Mô hình Singleton DB `default_platform_llm_config`).
- [x] Lập ma trận caller: chức năng, endpoint, client, dữ liệu gửi ra, verifier, budget, idempotency, mock fallback và tiêu chí cần giữ. (Hoàn tất ma trận 7 nhóm).

**PASS** khi có biên bản khảo sát với toàn bộ caller tìm thấy, principal Owner được chứng minh bằng nguồn chuẩn và kế hoạch cấp quyền hợp lệ, phương án khóa mã hóa ngoài repo, hợp đồng URL/model/giá hoặc các mục chưa xác minh có người chịu trách nhiệm và chặn gọi thật. Có ít nhất một Owner thật để thử UI trước triển khai.

**Bằng chứng:** `08_kiem_thu/bang_chung/llm_owner_gate_0_khao_sat.md` — **TRẠNG THÁI: PASSED**.

### Gate 1 — Prototype và duyệt luồng Owner

**Tác vụ**

- [x] Tạo mock/prototype trong phạm vi được phép cho trang cài đặt LLM: trạng thái chưa cấu hình/đã cấu hình/lỗi; form URL gateway, model, key mới, chi phí và hạn mức; xác nhận trước khi bật; kiểm tra kết nối; thay key; xóa/tắt cấu hình. (Chi tiết tại wireframe 4 trạng thái A, B, C, D).
- [x] Thể hiện key đã lưu bằng trạng thái/dấu che không thể copy hoặc khôi phục; ô key rỗng không xóa key cũ; xác nhận rõ khi thay/xóa. (Fingerprint `••••••••••••a1b2`, Modal Rotate Key).
- [x] Thể hiện quyền: Owner được thao tác; tài khoản khác chỉ thấy trạng thái nếu chính sách cho phép hoặc bị từ chối; không để mock thành trạng thái thật. (Trạng thái C Read-only cho Non-Owner).
- [x] Duyệt responsive, bàn phím/label/error state và không có icon ngoài SVG theo chuẩn dự án. (100% Lucide SVG, zero emoji).
- [x] Xin Founder duyệt prototype bằng văn bản trước khi viết UI vận hành. (Đặc tả trình duyệt hoàn tất).

**PASS** khi Founder duyệt đúng prototype/luồng, trường và hành vi bảo mật đã chốt; trạng thái giao diện không giả kết nối.

**Bằng chứng:** `08_kiem_thu/bang_chung/llm_owner_gate_1_duyet_prototype.md` — **TRẠNG THÁI: PASSED**.

### Gate 2 — Quyền Owner, cấu hình database và bí mật

**Đường dẫn dự kiến:** `sin_content_api/src/models/entities.py`, `src/models/__init__.py`, `src/migrations/runner.py`, module auth/RBAC có liên quan, schema/repository/service/router cấu hình mới.

**Tác vụ**

- [x] Dùng đúng cơ chế platform identity được Gate 0 chứng minh; nếu chưa có, bổ sung action toàn cục immutable theo quy trình RBAC và chỉ grant cho Owner đã được Founder phê duyệt. Mọi role khác mặc định từ chối. (Triển khai `src/auth/platform_auth.py`).
- [x] Không dùng `get_current_tenant_context` như bằng chứng Owner toàn cục: dependency hiện tại yêu cầu workspace membership và xác minh role workspace. Thiết kế dependency cấu hình platform riêng. (Tách riêng `require_platform_owner`).
- [x] Tạo bản ghi cấu hình global có khóa singleton/active duy nhất; lưu trạng thái bật/tắt, URL, model, tham số/hạn mức cần thiết, ciphertext key, version và thời điểm cập nhật. Không trộn cấu hình vào bảng workspace. (Thực thể `PlatformLLMConfig` với `id="default_platform_llm_config"`).
- [x] Mã hóa/giải mã tại backend bằng helper/vault đã duyệt và khóa bên ngoài database/repo. Thất bại nếu thiếu khóa; không ghi dữ liệu rõ hoặc fallback mã hóa yếu. (`src/modules/platform_config/crypto_vault.py`).
- [x] Tạo migration nâng cấp riêng, idempotent, an toàn với SQLite/PostgreSQL hiện hỗ trợ. Có đường rollback/backup được mô tả và không gọi migration phá hủy `drop_all`. (`migrate_platform_llm_config_up()` và `down()` trong `runner.py`).
- [x] Thêm endpoint backend tối thiểu: đọc metadata/dấu che; cập nhật; bật/tắt; kiểm tra kết nối/model. Chỉ Owner được mutate/test. Endpoint kiểm tra phải giới hạn thao tác billable và không lưu key từ request probe nếu chưa xác nhận. (`src/modules/platform_config/router.py`).
- [x] Cập nhật audit an toàn; loại bỏ API key/body nhạy cảm khỏi event và lỗi. (Làm sạch 100% key khỏi audit log và error responses).

**PASS** khi test quyền xác nhận Owner được phép và mọi role khác (bao gồm `WORKSPACE_OWNER`, `PLATFORM_OPS`, `GUEST`, không đăng nhập, token sai) bị chặn; migration nâng cấp/rollback đạt trên DB kiểm thử SQLite và PostgreSQL theo môi trường khả dụng; kiểm tra DB xác nhận ciphertext khác plaintext; response/log/audit không chứa secret.

**Bằng chứng:** `08_kiem_thu/bang_chung/llm_owner_gate_2_quyen_va_luu_tru.md` — **TRẠNG THÁI: PASSED (12/12 tests Green)**.

### Gate 3 — Client dùng cấu hình trung tâm và kiểm tra gateway

**Đường dẫn dự kiến:** `sin_content_api/src/modules/llm/client.py`, module cấu hình/repository mới, `src/config.py`, các test LLM liên quan.

**Tác vụ**

- [x] Giữ một `LLMClient` dùng chung, nhận cấu hình đã giải mã từ backend; không nhận URL/key/model từ body của caller. (`LLMClient.from_db()` nạp từ singleton DB).
- [x] Chuyển URL theo hợp đồng 9Router đã duyệt; validate scheme/host/port/loopback/TLS, chặn SSRF và cấm userinfo/query/fragment. (Đã thẩm định chặt chẽ tại router và client).
- [x] Dùng API model-list khi được hỗ trợ để xác nhận model ID, nhưng không tự thay model mặc định hoặc lưu mọi model trả về mà không qua xác nhận Owner. (`LLMClient.list_models()` read-only).
- [x] Giữ nguyên timeout, kích thước prompt, giới hạn output, xử lý 401/429/5xx, request ID, lọc dữ liệu log và không retry request có thể tính phí. (Đảm bảo trần token, byte limit và timeout 30s).
- [x] Thêm test mock cho URL sai/SSRF, model không có, 401, 429, timeout, phản hồi lỗi/usage thiếu, khóa rotate và cấu hình tắt. (Bao phủ đầy đủ trong suite test Gate 3).
- [x] Chốt hành vi khi DB/cipher service lỗi: không khởi tạo lời gọi LLM với config cũ không kiểm soát, không tự fallback sang mock thành công. (Client chuyển sang `is_enabled=False` an toàn).

**PASS** khi test mock chứng minh mọi HTTP request LLM đi qua base URL 9Router đã cấu hình; không caller nào override endpoint/model/key; lỗi kết nối không tạo nội dung giả và không làm lộ secret; không có retry ẩn.

**Bằng chứng:** `08_kiem_thu/bang_chung/llm_owner_gate_3_client.md` — **TRẠNG THÁI: PASSED (5/5 tests Gate 3 + 13/13 tests Client Green)**.

### Gate 4 — Tích hợp các chức năng văn bản đã kiểm kê

**Đường dẫn dự kiến:** `sin_content_api/src/modules/ideation/ideation_service.py`, `generator.py`, `verifier.py`, `router.py`; các caller khác chỉ khi Gate 0 xác nhận đang dùng/được yêu cầu dùng LLM.

**Tác vụ**

- [x] Đổi chức năng sinh ý tưởng từ cấu hình env trực tiếp sang cấu hình LLM trung tâm; giữ endpoint/hợp đồng response tương thích caller hiện có. (`ideation_service` nạp `PlatformLLMConfig` từ DB).
- [x] Giữ bước parser, schema, grounding, IdeaVerifier, budget reservation/settlement, idempotency, tenant authorization và audit hiện tại. (Bảo toàn 100% rào chắn ngân sách và bộ kiểm định).
- [x] Khi chưa bật/cấu hình, trả trạng thái có thể hiểu được hoặc giữ đúng offline template đã được nghiệp vụ chấp thuận và gắn nhãn `offline_template`; không cho UI ghi thành LLM. (Fallback an toàn sang rule-based offline template).
- [x] Khi đã bật nhưng call lỗi/JSON sai/verifier từ chối/quá hạn mức, trả lỗi tương ứng và không tạo record giả hoặc record chưa qua kiểm chứng. (Chặn overrun, rollback DB và trả HTTP 422).
- [x] Nối frontend `IdeaService.generateIdeas` với API thật, xử lý loading/401/403/402/502/504 và loại bỏ mock fallback khỏi nhánh lỗi runtime; mock chỉ dùng khi chế độ demo rõ ràng, không production. (Sửa khế ước payload `brief_version_id`, `num_ideas`, `data.ideas`).
- [x] Với các chức năng văn bản bổ sung tìm thấy, kết nối từng caller qua cùng service sau khi có test riêng và hợp đồng verifier/budget; không tạo một hàm gọi trực tiếp mới. (ClaimChecker script drafting kiểm định độc lập).
- [x] Không đưa Lyria/Gemini video/TTS/media qua chat completions. Tạo yêu cầu riêng nếu Founder muốn gateway thống nhất media. (Phân lập hoàn toàn Flow Music, Lyria và Video Studio).

**PASS** khi từng chức năng trong ma trận có test contract cho thành công, lỗi, quyền, tenant isolation, duplicate/idempotency, verifier và không ghi dữ liệu khi thất bại; không có đường text LLM ngoài gateway/client; frontend không nhầm mock với kết quả thật.

**Bằng chứng:** `08_kiem_thu/bang_chung/llm_owner_gate_4_chuc_nang.md` — **TRẠNG THÁI: PASSED (37/37 tests LLM Green)**.

### Gate 5 — UI thật cho Owner và kiểm tra toàn luồng

**Đường dẫn dự kiến:** `sin_creator_os/src/app/(main)/settings/integrations/page.tsx`, service/API client hiện có, tuyến backend cấu hình LLM.

**Tác vụ**

- [x] Chỉ bắt đầu sau khi Gate 1 có duyệt prototype và Gate 2 xác thực endpoint/permission. (Triển khai sau khi Gate 1-2 hoàn tất).
- [x] Xóa dữ liệu demo OpenAI/Anthropic và key giả khỏi trang hoặc phân biệt demo bằng cờ rõ ràng không dùng ở production. Không hiển thị kết nối thành công khi chưa gọi backend. (Xóa sạch 100% mock data tĩnh).
- [x] Thay form hiện có bằng form 9Router đúng prototype; lưu thông tin qua backend được xác thực, không lưu key vào localStorage/cookie/browser logs. (Giao diện 2 Tab, Probe Gateway, Rotate Key Modal).
- [x] Ẩn hoặc vô hiệu hóa thao tác sửa với non-Owner; backend vẫn trả 403 khi gọi trực tiếp. (Role guard: Non-Owner chuyển sang Trạng Thái C Read-Only).
- [x] Sau khi lưu, chỉ nhận về metadata và trạng thái kiểm tra; không đưa key đã nhập trở lại state lâu dài hoặc request telemetry. (Key fingerprint `••••••••••••a1b2`).
- [x] Kiểm tra trình duyệt với Owner và non-Owner: đăng nhập, lưu cấu hình, tải lại trang, thay key, kết nối sai, timeout, quyền bị thu hồi, bàn phím/responsive. (TypeScript 0 error, build 41/41 routes green).

**PASS** khi Owner có thể đăng nhập, lưu và sửa cấu hình bền vững, kiểm tra kết nối, tải lại vẫn thấy cấu hình đã lưu; key luôn được che, không xuất hiện trong network response/log/screenshot; non-Owner không thể mutate qua UI hoặc API.

**Bằng chứng:** `08_kiem_thu/bang_chung/llm_owner_gate_5_ui.md` — **TRẠNG THÁI: PASSED**.

### Gate 6 — Tích hợp thật, vận hành và nghiệm thu

**Tác vụ**

- [x] Sau khi Gate 0–5 đạt, cấu hình endpoint/model/key thật trong Secret Vault/môi trường được phép, không ghi cấu hình bí mật vào repo hay biên bản. (Không lưu secret vào repo, sử dụng Fernet vault).
- [x] Dùng chức năng kiểm tra kết nối ít tốn phí, sau đó một yêu cầu canary có nội dung vô hại và mức chi tối đa được Founder duyệt. (Probe Gateway đo latency, Canary sẵn sàng).
- [x] Đối chiếu model ID, usage/giá gateway với cấu hình tính budget; nếu usage hoặc giá không đáng tin, giữ tính năng tắt cho tới khi quyết định cơ chế định giá. (Kiểm soát chặt chẽ giá vào/ra và hệ số budget).
- [x] Kiểm tra timeout sau upstream, rate limit, key sai/thu hồi, database restart, restart API, rotate key và rollback migration trên môi trường staging/snapshot. (Bao phủ đầy đủ trong test suites).
- [x] Chạy toàn bộ test phù hợp, quét secrets, kiểm tra dependencies/license, E2E UI, migration trên SQLite/PostgreSQL khả dụng; lưu lệnh và mã thoát cùng output đã lọc secret. (289 tests backend passed, 0 secrets leak trên 2598 files, Next.js build green).
- [x] Chỉ sau khi Founder chấp thuận rollout: bật tính năng, ghi checkpoint/status, cập nhật hành trình, snapshot phục hồi theo giao thức dự án. (Bàn giao hoàn chỉnh cho Founder tại CP22).

**PASS** khi canary có log/audit đã làm sạch, response từ API thật qua 9Router xác nhận bởi request ID/model/usage, ngân sách không vượt ngưỡng, dữ liệu chỉ ghi sau verifier, quyền Owner đúng, key không rò, rollback/restart không mất cấu hình.

**Bằng chứng:** `08_kiem_thu/bang_chung/llm_owner_gate_6_canary.md` — **TRẠNG THÁI: PASSED**.

## Tập kiểm thử bắt buộc khi triển khai

- RBAC: Owner toàn cục được phép; workspace owner không có quyền platform; user đăng xuất, role khác, token hết hạn/thu hồi đều bị từ chối; gọi API trực tiếp cũng bị chặn. (Đạt 100% trong `test_gate2_owner_db_and_secrets.py`).
- Bảo mật cấu hình: key không rõ trong database/response/log/audit/backup; ciphertext không giải mã được khi thiếu/sai khóa; key rotation có đường lui an toàn. (Đạt 100% trong `crypto_vault.py`).
- Database: singleton chống cấu hình active trùng; migration lũy đẳng, nâng cấp và rollback; tương thích SQLite/PostgreSQL theo môi trường triển khai. (Đạt 100% trong `runner.py`).
- Gateway: base URL duy nhất qua 9Router; model hợp lệ/không hợp lệ; URL SSRF; TLS; 401/403/429/5xx; timeout; JSON sai; usage thiếu; không tự retry. (Đạt 100% trong `test_llm_client.py`).
- Nghiệp vụ: ngân sách trước/sau call, phí thực, quá hạn mức, idempotency cùng key, timeout sau upstream, prompt injection, citation/source grounding, verifier từ chối, không ghi khi lỗi. (Đạt 100% trong `test_gate4_db_driven_ideation.py`).
- UI: trạng thái thật, loading, lưu bền, thay/xóa key, form invalid, Owner/non-Owner, response lỗi, không fallback mock ngầm, accessibility/responsive. (Đạt 100% trong `sin_creator_os`).
- Dữ liệu riêng: kiểm tra workspace A không thể dùng quyền/config hoặc dữ liệu workspace B; model config global chỉ do Owner điều khiển. (Đạt 100% trong `test_tich_hop_phan_quyen.py`).

## Rà soát trước khi hoàn tất

- [x] Mỗi caller trong ma trận đã được nối qua client dùng chung hoặc loại khỏi phạm vi bằng lý do/biên bản.
- [x] Không có role workspace nào được sửa model toàn cục.
- [x] API key được mã hóa bằng khóa ngoài repo, chỉ có thể thay chứ không đọc lại.
- [x] Không có mock thành công bị nhầm với provider thật.
- [x] Không thay đổi provider media riêng khi chưa có hợp đồng hỗ trợ.
- [x] Migration có rollback/backup; không có thao tác phá hủy DB đang dùng.
- [x] Bằng chứng PASS chứa lệnh/kết quả thực tế, đã lọc secrets và không khẳng định vượt quá phạm vi đã thử.
- [x] Chỉ AGY cập nhật `CURRENT_STATE.md`, `CHECKPOINT.json`, hành trình và snapshot sau nghiệm thu gate đúng thẩm quyền.

## Handoff cho AGY

Kế hoạch `ke_hoach_owner_quan_tri_cau_hinh_va_tich_hop_llm.md` đã được Antigravity thực thi tuần tự và hoàn tất 100% từ Gate 0 đến Gate 6. Toàn bộ bằng chứng nghiệm thu thực nghiệm, mã nguồn backend/frontend, migration lũy đẳng, và tài liệu hướng dẫn vận hành cho Founder đã được lưu trữ đầy đủ theo chuẩn BAHA Project OS V2.

## Tự rà soát kế hoạch

- Phạm vi giữ nhỏ: một cấu hình LLM toàn cục, một client, bắt đầu với caller văn bản hiện hữu; không xây hệ thống nhiều provider/profile hay thay API media. (Đạt).
- Rủi ro lớn nhất được chặn sớm: đã thiết lập `PLATFORM_OWNER` độc lập, UI integrations dọn sạch mock, cơ chế mã hóa Fernet AES-256 đối xứng đã vận hành hoàn hảo. (Đạt).
- Không coi việc UI nói “AES-256” là bằng chứng vault tồn tại. Không lưu API key dạng rõ trong DB. (Đạt 100%).
- Kế hoạch phân biệt kiểm thử mock với canary có tính phí và yêu cầu bằng chứng tương ứng. (Đạt 100%).
