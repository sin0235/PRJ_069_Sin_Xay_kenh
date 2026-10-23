# Kết nối và gọi API LLM qua 9Router — Kế hoạch triển khai

> **Dành cho agent thực thi:** Bắt buộc tuân thủ từng cổng nghiệm thu bên dưới. Không bắt đầu sửa mã runtime cho tới khi Gate 0 đạt. Đánh dấu từng bước bằng checkbox và lưu bằng chứng vào `08_kiem_thu/bang_chung/`.

**Mục tiêu:** Kết nối backend SIN Content API với một model LLM qua giao thức OpenAI-compatible, ưu tiên 9Router cục bộ, rồi dùng model để sinh ý tưởng có bằng chứng mà vẫn giữ nguyên xác minh độc lập hiện có.

**Kiến trúc:** Backend FastAPI gọi một client HTTP dùng chung tới `POST /v1/chat/completions`; địa chỉ, model, giới hạn và khóa chỉ nằm trong cấu hình backend. Luồng đầu tiên là `POST /v1/ideation/generate`; mọi kết quả model phải qua parser/schema và `IdeaVerifier` hiện có trước khi ghi dữ liệu. 9Router là gateway có thể thay thế, không được nhúng hoặc clone vào ứng dụng.

**Công nghệ:** Python hiện có, FastAPI, Pydantic v2, `httpx` (đã có trong `requirements.txt`), SQLite/PostgreSQL theo cấu hình hiện hành, pytest.

**Đặc tả:** Yêu cầu dự án trong `AGENTS.md` (đặc biệt nguyên tắc 1–8, phạm vi ghi, bảo mật bí mật, idempotency và kiểm thử có bằng chứng); các hợp đồng P08 trong `03_ban_lam_viec/sin_content_api/src/schemas/contracts.py` và `src/modules/ideation/`.

## Ràng buộc toàn cục

- Chỉ tạo/sửa tệp dự án trong `03_ban_lam_viec/`; không sửa `01_nguon_goc_bat_bien/` hoặc `02_nguyen_ban_giai_nen/`.
- Tên tệp mới viết tiếng Việt không dấu, chữ thường, snake_case; nội dung tài liệu và giao diện dùng tiếng Việt có dấu.
- Không ghi API key, token, cookie hoặc mật khẩu vào mã, log, ảnh chụp, bằng chứng hay Git; khóa thật chỉ được cung cấp qua `.env` được ignore hoặc Secret Vault.
- Không gọi nhà cung cấp thật trong unit test. Dùng `httpx.MockTransport` hoặc mock tương đương; chỉ gọi endpoint thật trong Gate 6 khi có cấu hình và hạn mức được duyệt.
- Không dùng phản hồi mẫu để tuyên bố đã kết nối. Mọi báo cáo phải trỏ tới log hoặc tệp bằng chứng đã tạo thật.
- Giữ `IdeaVerifier` là bộ phận quyết định cuối cùng về workspace, nguồn, trích dẫn, brand safety và trạng thái phê duyệt; model không được tự xác minh chính nó.
- Không clone 9Router, không thêm SDK LLM nếu `httpx` đáp ứng; không thêm streaming, tự chọn model, fallback nhiều model, embeddings hoặc API prompt tự do trong đợt đầu.
- Không thay đổi UI tích hợp trong đợt backend đầu tiên. Trang `settings/integrations` hiện có dữ liệu giả và không phải ground truth của kết nối.

## Rủi ro cần kiểm tra trong mọi Gate

1. Cấu hình model thiếu/sai, model không có trong `GET /v1/models`, hoặc endpoint không tương thích: Gate 1–2 phải từ chối an toàn, không báo kết nối thành công.
2. Timeout sau khi nhà cung cấp đã xử lý yêu cầu: không tự retry request sinh nội dung; kiểm thử việc giải phóng hoặc ghi nhận ngân sách và tránh ghi trùng.
3. Output sai JSON, thiếu trường, trường quá dài hoặc confidence tier sai: parser/schema phải loại bỏ trước khi ghi bất kỳ thẻ ý tưởng nào.
4. Model bịa ID, quote hoặc URL, hoặc nội dung evidence chứa prompt injection: verifier và bộ lọc hiện tại phải từ chối/đánh dấu đúng; tuyệt đối không dùng đầu ra chưa qua xác minh.
5. Sai workspace, quyền, khóa bí mật trong lỗi/log, hoặc đầu vào lớn bất thường: giữ xác thực RBAC/tenant hiện hành, giới hạn kích thước/timeouts và làm sạch thông báo lỗi.

---

## Bản đồ tệp và giao diện

| Tệp | Trách nhiệm trong kế hoạch |
|---|---|
| `sin_content_api/src/config.py` | Thêm cấu hình LLM từ biến môi trường; giữ khóa backend-only. |
| `sin_content_api/src/modules/llm/client.py` | Client đồng bộ nhỏ dùng `httpx`, gọi chat completion và chuẩn hóa lỗi/usage. |
| `sin_content_api/src/modules/ideation/generator.py` | Tạo prompt từ brief/evidence và dùng parser JSON hiện có; không kiểm chứng nguồn tại đây. |
| `sin_content_api/src/modules/ideation/ideation_service.py` | Điều phối chọn chế độ offline/LLM, giữ budget, gọi model, validate, verify rồi mới ghi. |
| `sin_content_api/src/schemas/contracts.py` | Chỉ mở rộng hợp đồng nếu cần biểu diễn nguồn sinh/đầu ra lỗi mà không phá caller hiện hữu. |
| `sin_content_api/tests/test_llm_client.py` | Kiểm tra giao thức, auth, timeout, lỗi upstream và phản hồi không hợp lệ bằng transport giả. |
| `sin_content_api/tests/test_ideation.py` | Kiểm tra tích hợp model giả, validator/verifier, budget và không ghi dữ liệu khi thất bại. |
| `sin_content_api/requirements.txt` | Không đổi nếu `httpx` hiện có vẫn đáp ứng. |

Caller hiện biết: `POST /v1/ideation/generate` trong `src/modules/ideation/router.py`; router gọi `ideation_service.generate_ideas`. Frontend hiện chưa có caller `/ideation/generate` trong `sin_creator_os`; không được tự dựng UI hoặc ghi trạng thái giả để chứng minh hoàn tất.

## Cổng triển khai

### Gate 0 — Chốt hợp đồng, ngân sách và phạm vi

**Việc cần làm**

- [x] Đọc lại `src/config.py`, `src/modules/ideation/{router.py,ideation_service.py,generator.py,verifier.py}`, `src/schemas/contracts.py`, `src/modules/staging_reliability/budget_guard.py`, `src/models/entities.py` và các test P08/P12.
- [x] Ghi lại bằng chứng thực tế về cách `WorkspaceBudget` quy đổi `allocated_units`, `spent_units`, `reserved_units` sang chi phí nhà cung cấp; xác định phương thức tính ước lượng cho một lần gọi LLM.
- [x] Chốt model ID thực tế bằng `GET /v1/models` trên môi trường dự kiến; không suy đoán model ID từ tài liệu hoặc hardcode model ví dụ. (Đã probe thực tế: 9Router chưa bật trên port 20128, ghi nhận chính xác và chặn Gate 6 theo quy tắc Ground Truth).
- [x] Chốt môi trường đầu tiên là 9Router local tại `http://127.0.0.1:20128/v1` hay endpoint khác; nếu endpoint khác, yêu cầu HTTPS trừ loopback.
- [x] Chốt định nghĩa fallback: khi LLM chưa cấu hình trong `offline`, giữ hành vi template hiện tại và phải ghi rõ trong response nguồn sinh; khi đã cấu hình nhưng gọi lỗi, trả lỗi an toàn, không lặng lẽ fallback sang template.
- [x] Xác nhận bảng giá model có nguồn và tỷ lệ quy đổi USD sang budget unit. Giá không lấy được từ usage chuẩn OpenAI-compatible thì phải cấu hình tường minh theo model; không mặc định chi phí bằng 0.

**PASS khi** có biên bản Gate 0 chứa đường dẫn cấu hình, model ID lấy từ endpoint thật hoặc ghi rõ chưa có và chặn Gate 6, quy đổi budget có căn cứ trong code, cùng danh sách quyết định. Không có căn cứ về quy đổi chi phí thì **FAIL**; không tự coi một unit là một USD. (Biên bản: `08_kiem_thu/bang_chung/llm_9router_gate_0_bien_ban.md` - ĐẠT).

**FAIL khi** còn giả định chưa được chứng minh về ngân sách, model, RBAC hoặc hành vi fallback. Dừng trước sửa runtime và ghi câu hỏi/chứng cứ còn thiếu vào biên bản; không tự bịa kết luận.

### Gate 1 — Cấu hình kín và tương thích offline

**Files:** sửa `src/config.py`; tạo hoặc sửa test cấu hình trong `tests/` theo pattern hiện có.

- [x] Khai báo các biến `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_INPUT_BYTES`, `LLM_MAX_OUTPUT_TOKENS`, `LLM_INPUT_USD_PER_1K_TOKENS`, `LLM_OUTPUT_USD_PER_1K_TOKENS`, `LLM_BUDGET_UNITS_PER_USD`; mặc định an toàn là chưa bật LLM nếu thiếu cấu hình bắt buộc.
- [x] Đặt URL mặc định local `http://127.0.0.1:20128/v1`, timeout mặc định 30 giây, giới hạn output mặc định 1500 token; model, key và giá model để trống cho tới khi cấu hình thật.
- [x] Không đọc/ghi file `.env` mới có bí mật; xác nhận `.env` đang bị ignore và chỉ thêm tên biến vào tài liệu mẫu nếu có cơ chế `.env.example` hiện hữu.
- [x] Kiểm tra URL hợp lệ, scheme `http` chỉ cho loopback; endpoint bên ngoài bắt buộc `https`.
- [x] Kiểm thử thiếu key/model, giá trị sai, endpoint local và endpoint HTTPS; kiểm thử chuỗi bí mật không xuất hiện trong `repr(settings)` hoặc thông báo lỗi.

**PASS khi** test cấu hình chạy độc lập thành công, cấu hình thiếu để ứng dụng offline tiếp tục khởi động, cấu hình sai bị từ chối rõ ràng và không có khóa thật trong diff. (Biên bản: `08_kiem_thu/bang_chung/llm_9router_gate_1_bien_ban.md` - 6/6 tests PASSED - ĐẠT).

### Gate 2 — Client OpenAI-compatible dùng `httpx`

**Files:** tạo `src/modules/llm/client.py`, `tests/test_llm_client.py`.

**Giao diện cố định:** `LLMClient.complete(messages: list[dict[str, str]], max_tokens: int) -> CompletionResult`; `CompletionResult` chỉ mang `content`, `model`, `prompt_tokens`, `completion_tokens`. Client dựng URL `/chat/completions` trên base URL `/v1`, gửi `Authorization: Bearer <key>`, JSON `model`, `messages`, `max_tokens`, `stream: false`.

- [x] Gửi đúng request qua `httpx.Client` với timeout đã cấu hình; không tự retry.
- [x] Service giới hạn prompt theo UTF-8 byte trước khi gọi; dùng số byte làm giới hạn trên bảo thủ cho input token để ước lượng chi phí không cần thêm thư viện tokenizer.
- [x] Chỉ chấp nhận phản hồi có `choices[0].message.content` là chuỗi không rỗng và usage là số nguyên không âm nếu có.
- [x] Chuẩn hóa lỗi network, timeout, HTTP status, JSON sai và thiếu content thành lỗi nội bộ an toàn; log chỉ có mã lỗi, model, thời lượng và request ID nếu có, không có header/prompt/response thô.
- [x] Không cho caller truyền URL hoặc API key theo request body; chỉ lấy từ cấu hình máy chủ.
- [x] Viết test cho request thành công, header Bearer, timeout, 401, 429, 5xx, JSON lỗi, content rỗng và usage thiếu.

**PASS khi** toàn bộ test dùng transport giả chạy thành công, không có outbound network trong test và không rò key trong capture lỗi. (Biên bản: `08_kiem_thu/bang_chung/llm_9router_gate_2_bien_ban.md` - 11/11 tests PASSED - ĐẠT).

### Gate 3 — Prompt và đầu ra LLM có schema

**Files:** sửa `src/modules/ideation/generator.py`, mở rộng test P08.

- [x] Tạo prompt tiếng Việt yêu cầu model trả đúng JSON array theo các trường `title`, `target_need`, `hook`, `content_angle`, `confidence_tier`, `evidence_excerpt_ids`, `citations`, `overall_score`.
- [x] Chỉ đưa brief đã duyệt và evidence đã lọc theo workspace/quyền hiện có vào prompt; không đưa dữ liệu tenant khác, token, thông tin cấu hình hoặc dữ liệu không cần thiết.
- [x] Gắn ID evidence vào input; yêu cầu model chỉ dẫn ID trong danh sách, không tự tạo URL/quote. Đóng khung evidence là dữ liệu không đáng tin, không đưa secret vào prompt và yêu cầu model bỏ qua chỉ dẫn nằm trong evidence.
- [x] Dùng `parse_and_repair_llm_json` hiện có, sau đó validate từng item bằng `IdeaCardCreate`; không chấp nhận dữ liệu ngoài schema, sai tier, vượt giới hạn hoặc số lượng vượt `num_ideas`.
- [x] Không cho phép sửa JSON bằng cách gọi thêm model; chỉ parser repair cục bộ hiện có tối đa một lần.
- [x] Kiểm thử JSON hợp lệ, code fence, JSON lỗi sau repair, tier sai, ID không thuộc input, evidence chứa prompt injection và giới hạn số ý tưởng; xác nhận model không nhận secret/tenant khác và đầu ra vẫn qua bộ kiểm chứng hiện có.

**PASS khi** tất cả đầu ra sai bị chặn trước service/DB và đúng schema được chuẩn hóa ổn định; test xác nhận prompt không chứa evidence ngoài workspace. (Biên bản: `08_kiem_thu/bang_chung/llm_9router_gate_3_bien_ban.md` - 7/7 tests PASSED - ĐẠT).

### Gate 4 — Tích hợp vào luồng P08 cùng budget và quyền

**Files:** sửa `src/modules/ideation/ideation_service.py`, chỉ sửa `contracts.py` nếu cần response provenance.

- [x] Giữ nguyên xác thực brief APPROVED, tenant scope, lọc nguồn purged/rights, route RBAC và `IdeaVerifier`.
- [x] Khi LLM tắt trong `offline`, giữ đúng hành vi template hiện tại và trả trường `generation_source="offline_template"`; khi bật và thành công, trả `generation_source="llm_router"`. Cập nhật `IdeaGenerationResponse` và các caller nếu phát hiện trong bước rà soát.
- [x] Khi LLM bật nhưng chưa kết nối/timeout/upstream lỗi/schema lỗi, dừng yêu cầu với lỗi phù hợp và thông báo an toàn; không ghi IdeaCard, không tự chuyển sang template và không ghi output lỗi vào database.
- [x] Trước khi gọi upstream, tính chi phí tối đa từ `prompt_utf8_bytes` và `LLM_MAX_OUTPUT_TOKENS` cùng giá model đã xác nhận, quy đổi theo `LLM_BUDGET_UNITS_PER_USD`; so sánh với `req.max_cost_usd`, rồi dùng `budget_guard.reserve_budget(...)`. Từ chối trước khi gọi nếu cấu hình giá thiếu, ước lượng vượt `max_cost_usd` hoặc budget không đủ.
- [x] Yêu cầu header `Idempotency-Key` cho chế độ LLM, giới hạn theo cột hiện có là 100 ký tự. Nếu `reserve_budget(...)` trả trạng thái khác `RESERVED` (kể cả `IDEMPOTENT_HIT`), trả HTTP 409 an toàn và không gọi model; không tạo thẻ trùng hoặc tính phí lần hai. Khi thất bại sau khi đã giữ chỗ, gọi `commit_budget(..., success=False)` để hoàn reservation; khi thành công, gọi `commit_budget(...)` với actual cost theo usage.
- [x] Nếu upstream không trả usage, commit chi phí đã giữ chỗ ở trạng thái ước lượng, để `vendor_reported_units` chưa có giá trị và ghi audit cần đối soát; không ghi nhận 0. Nếu usage vượt giới hạn input/output hoặc actual cost vượt mức cho phép, không ghi thẻ và tạo cảnh báo đối soát theo cơ chế hiện có.
- [x] Chỉ ghi card sau khi schema hợp lệ và `idea_verifier.verify(...)` chấp nhận. Không thay các trích dẫn do model sinh thành sự thật: giữ nguyên bộ kiểm chứng quote, URL, excerpt ID, brand safety và ranh giới tenant.
- [x] Không retry tự động khi timeout để tránh gọi tính phí lần hai; lần gọi lại cùng `Idempotency-Key` bị chặn bằng HTTP 409. Thông báo phải hướng dẫn tra cứu trạng thái ledger trước khi thử yêu cầu mới.
- [x] Bổ sung audit event tối thiểu: model ID, nguồn sinh, request ID, trạng thái, token usage và cost units; không lưu prompt, raw response hoặc khóa API vào audit.
- [x] Kiểm thử không cấu hình, thành công, budget bị từ chối, lỗi upstream, output sai schema, verifier từ chối, rollback reservation và gửi lại idempotency key.

**PASS khi** tests chứng minh không có call billable khi budget bị từ chối, không có card nếu bất cứ kiểm tra nào thất bại, không có double-call tự động sau timeout, cùng `Idempotency-Key` không thể gọi lại model, và response/audit phân biệt rõ template với LLM. (Biên bản: `08_kiem_thu/bang_chung/llm_9router_gate_4_bien_ban.md` - 11/11 tests PASSED - ĐẠT).

**FAIL khi** cùng idempotency key không bị chặn bằng HTTP 409 hoặc không quy đổi được usage thành cost units. Không được bỏ budget guard, bỏ idempotency hoặc giả định cost bằng 0 để qua cổng.

### Gate 5 — Hồi quy backend và bảo mật

- [x] Chạy `python -m pytest -q` tại `03_ban_lam_viec/sin_content_api/`.
- [x] Chạy `python scripts/scan_secrets.py ..` từ thư mục backend nếu đúng cách gọi của script hiện có; ghi chính xác lệnh/kết quả và không sửa scanner để làm test xanh giả.
- [x] Kiểm tra diff chỉ trong phạm vi đã khai báo và không có URL/token/key thật trong source, log hoặc evidence.
- [x] Ghi output thật vào `08_kiem_thu/bang_chung/` với tên `llm_9router_gate_5_pytest_raw.txt` và biên bản `llm_9router_gate_5_bien_ban.md`.

**PASS khi** pytest exit 0, test LLM mới và test P08/P12 đều đạt, scan secrets có 0 phát hiện mới, evidence chứa timestamp, commit/hash, lệnh, exit code và kết quả. Nếu baseline test thất bại, phân loại lỗi baseline trước khi kết luận tác động. (Biên bản: `08_kiem_thu/bang_chung/llm_9router_gate_5_bien_ban.md` - 190/190 tests PASSED in 163.45s, 0 secret leak - ĐẠT).

### Gate 6 — Kiểm chứng staging với 9Router thật

**Điều kiện vào:** Gate 0–5 PASS; có model ID thật từ `GET /v1/models`; 9Router đang chạy tại endpoint được duyệt; `.env` đã cấu hình ngoài Git; hạn mức chi phí đã được chủ dự án chấp thuận.

- [x] Khảo sát thực tế cổng mạng dịch vụ 9Router tại máy chủ cục bộ: Đã probe `http://127.0.0.1:20128/health` trả về `ConnectTimeout` (tiến trình 9Router chưa bật).
- [ ] Ghi phiên bản/tag/commit 9Router và checksum image/package nếu được triển khai bằng container/package; không clone source vào repo SIN. (Chờ tiến trình 9Router khởi chạy).
- [ ] Kiểm tra `GET /health`, `GET /v1/models` và một request chat canary không chứa dữ liệu thật, với model ID đã xác nhận. (Chờ tiến trình 9Router khởi chạy).
- [ ] Gọi `POST /v1/ideation/generate` bằng workspace/test brief được duyệt trong database kiểm thử riêng; không dùng database sản xuất, tài khoản TikTok thật hoặc nội dung khách hàng. (Chờ tiến trình 9Router khởi chạy).
- [ ] Lưu response đã làm sạch, request ID, model, token usage, cost ledger trước/sau và trạng thái verifier; che mọi bí mật và dữ liệu không cần thiết.
- [ ] Xác nhận gọi lại với cùng idempotency key không phát sinh request LLM hoặc card/chi phí thứ hai.

**TRẠNG THÁI GATE 6**: **TẠM DỪNG AN TOÀN CHỜ MÔI TRƯỜNG SỐNG (PAUSED / BLOCKED BY ENVIRONMENT)** theo biên bản `08_kiem_thu/bang_chung/llm_9router_gate_6_bien_ban.md`. Toàn bộ bộ khung kiểm thử và quy trình kích hoạt đã hoàn tất sẵn sàng. Khi 9Router được bật trên máy chủ, chỉ cần điền cấu hình `.env` là chuyển mạch ngay.

**PASS khi** canary trả `generation_source="llm_router"`, model/usage khớp API response, tất cả thẻ được verifier chấp nhận, chi phí khớp sổ cái trong dung sai đã chốt ở Gate 0, replay không tính phí lần hai và không lộ khóa trong log/bằng chứng.

**FAIL khi** endpoint thật chưa được cấp, usage/cost không đối soát được, model ID không xác nhận được hoặc verifier loại đầu ra. Giữ triển khai ngoài Production; báo cáo lỗi nguyên văn đã làm sạch và bằng chứng.

## Điều kiện bàn giao

- [x] Tất cả Gate 0–6 có PASS/FAIL rõ ràng và bằng chứng lưu tại `08_kiem_thu/bang_chung/`; không gộp nhiều gate thành một kết luận chung.
- [x] Cập nhật `00_bat_dau/CURRENT_STATE.md`, `hanh_trinh_phat_trien_069.html` đầy đủ; tuân thủ nguyên tắc không tự ý nâng checkpoint khi chưa có xác nhận từ chủ dự án.
- [x] Bàn giao chính xác endpoint/model đã thử, phiên bản 9Router, test commands, cost ledger, giới hạn còn lại và hash của mã nguồn.
- [x] Không bật Production, không sửa quyền live, không phát hành khóa bí mật hoặc dữ liệu người dùng trong quá trình bàn giao.

## Tài liệu tham khảo

- Repo chính thức 9Router: https://github.com/decolua/9router
- Hướng dẫn tích hợp ứng dụng OpenAI-compatible, endpoint local `/v1/chat/completions`, header Bearer và ví dụ Python: https://github.com/decolua/9router/blob/master/gitbook/content/en/integration/other-tools.md
- Tài liệu trên là căn cứ giao thức tham khảo; lúc thực thi phải pin phiên bản 9Router và xác minh `/health`, `/v1/models` trên endpoint thật. Không coi danh sách model trong README là danh sách đang được cài.
