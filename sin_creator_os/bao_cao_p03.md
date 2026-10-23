# BÁO CÁO NGHIỆM THU PHA P03: BỘ CHUYỂN ĐỔI NGUỒN DỮ LIỆU & MINH CHỨNG NĂNG LỰC
*(Data-Source Adapters, Compliance Registry & Capability Proof)*

**Dự án:** PRJ_069_Sin_Xay_kenh - SIN Content Intelligence  
**Phiên bản hệ thống:** 1.0.0  
**Ngày thực hiện:** 2026-10-21  
**Người thực hiện:** Anti (Agent triển khai)

---

## 1. KHỐI TRẠNG THÁI CHUẨN HÓA (EXACT STATUS BLOCK)

```yaml
PHASE: P03
STATUS: PASS
FILES_CREATED_OR_MODIFIED:
  - 03_ban_lam_viec/sin_content_api/src/modules/sources/__init__.py (Khoi tao module nguon)
  - 03_ban_lam_viec/sin_content_api/src/modules/sources/provider_protocol.py (Giao thuc SourceProvider & DTOs)
  - 03_ban_lam_viec/sin_content_api/src/modules/sources/offline_fixture_adapter.py (Adapter fixture synthetic test)
  - 03_ban_lam_viec/sin_content_api/src/modules/sources/customer_import_adapter.py (Adapter import du lieu khach hang)
  - 03_ban_lam_viec/sin_content_api/src/modules/sources/tiktok_official_adapter.py (Adapter TikTok API gated by OAuth)
  - 03_ban_lam_viec/sin_content_api/src/modules/sources/provider_registry.py (Registry, Circuit Breaker, chan MediaCrawler)
  - 03_ban_lam_viec/sin_content_api/src/modules/sources/router.py (REST API cho providers, search, import, quarantine)
  - 03_ban_lam_viec/sin_content_api/src/models/entities.py (Bo sung entity QuarantineRecord cho du lieu loi)
  - 03_ban_lam_viec/sin_content_api/src/main.py (Tich hop sources_router va format exception)
  - 03_ban_lam_viec/sin_creator_os/src/contracts/index.ts (Dong bo TypeScript DTOs cho SourceProvider)
  - 03_ban_lam_viec/sin_content_api/tests/test_sources.py (Suite kiem thu T030, T031, T032, T033, T034, T035)
  - 03_ban_lam_viec/sin_creator_os/bao_cao_p03.md (Bao cao nghiem thu P03)
  - Cap nhat trang thai tai: 00_bat_dau/CURRENT_STATE.md
CHANGES: Xay dung giao thuc SourceProvider, bo 3 adapter nguon, registry ngat mach Circuit Breaker, co che chan MediaCrawler, va cach ly ban ghi loi vao quarantine
TESTS_RUN:
  - T030 (Provider tra ve rong hop le -> EMPTY, 0 ban ghi gia): PASSED [50%]
  - T031 (Loi 401/403/captcha -> AUTH_FAILED/FORBIDDEN, khong bypass): PASSED [56%]
  - T032 (429 Rate limit backoff & chan vuot ngan sach BUDGET_EXCEEDED): PASSED [62%]
  - T033 (Du lieu loi sai cau truc -> INVALID_DATA/PARTIAL, cach ly quarantine): PASSED [68%]
  - T034 (Kiem tra trang thai live trung thuc -> UNVERIFIED / AUTHORIZED_IMPORT): PASSED [75%]
  - T035 (Goi crawler bi cam MediaCrawler -> RIGHTS_NOT_GRANTED, 0 network call, ghi audit): PASSED [81%]
  - Toan bo test suite hoi quy (T010, T011, Migrations, T020, T021, T022, T030-T035): 16/16 tests PASSED in 15.97s
  - T012 (Secrets scanner tren 1.007 tap tin): 0 vi pham, EXIT CODE 0 in 23s
LIVE_VERIFICATION: UNVERIFIED (Bao cao trung thuc: chua co OAuth credentials duoc duyet cho TikTok live; he thong su dung duong import khach hang customer_import hop phap lam nòng cot offline)
EVIDENCE: Log terminal thuc te cua Pytest (16/16 passed), log scan_secrets.py (1.007 files passed)
COST/RIGHTS: Chi phi 0 USD; cam tuyet doi MediaCrawler va cac crawler trai phep vi pham ToS; bao toan quyen du lieu khach hang
RISKS/BLOCKERS: Khong con blocker ky thuat. Live TikTok API can bo credential chinh thuc khi deploy production
NEXT_ALLOWED_PHASES: P04 - Tiep nhan du lieu, chuan hoa, xuat xu & snapshot chi so (Ingestion, Provenance & Snapshots)
```

---

## 2. NỘI DUNG CÁC THÀNH PHẦN ĐÃ XÂY DỰNG TRONG PHA P03

### 2.1. Giao thức Chuẩn Hóa `SourceProvider` Protocol (`src/modules/sources/provider_protocol.py`)
- Thiết lập định dạng hợp đồng kiểu dữ liệu nghiêm ngặt cho toàn bộ các nhà cung cấp dữ liệu:
  - `capabilities() -> ProviderCapabilities`
  - `search_content(query: SearchQuery, auth: AuthContext, budget: Budget) -> Page[ProviderPost] | ProviderError`
  - `get_content(external_ref: str, auth: AuthContext, budget: Budget) -> ProviderPost | ProviderError`
  - `get_comments(external_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget) -> Page[ProviderComment] | ProviderError`
  - `list_profile_posts(profile_ref: str, cursor: Optional[str], auth: AuthContext, budget: Budget) -> Page[ProviderPost] | ProviderError`
  - `refresh_metrics(external_refs: List[str], auth: AuthContext, budget: Budget) -> List[dict] | ProviderError`
- Định nghĩa đầy đủ các Enums trạng thái:
  - Trạng thái năng lực (`ProviderCapabilityStatus`): `SUPPORTED`, `UNSUPPORTED`, `REQUIRES_AUTH`, `UNVERIFIED`, `DISABLED_BY_POLICY`.
  - Trạng thái kết quả (`ProviderStatus`): `OK`, `EMPTY`, `PARTIAL`, `RATE_LIMITED`, `AUTH_FAILED`, `FORBIDDEN`, `UNAVAILABLE`, `INVALID_DATA`, `BUDGET_EXCEEDED`, `CANCELED`, `RIGHTS_NOT_GRANTED`, `NO_APPROVED_SOURCE`.
  - Phân loại nguồn (`Platform`): `TIKTOK`, `WEB`, `CUSTOMER_DATA`, `OTHER`.
  - Phương pháp thu thập (`RetrievalMethod`): `API`, `LICENSED_PROVIDER`, `APPROVED_CRAWLER`, `CUSTOMER_IMPORT`, `FIXTURE`.

### 2.2. Hệ Thống 3 Bộ Chuyển Đổi Nguồn Dữ Liệu (Adapters)
1. **`OfflineFixtureAdapter` (`offline_fixture_adapter.py`)**:
   - Sử dụng cho kiểm thử ngoại tuyến và phát triển.
   - **Quy tắc bất biến:** `synthetic` luôn luôn là `True`, `provider_id` là `"test_fixture"`, `retrieval_method` là `"FIXTURE"`, `live_status` là `"UNVERIFIED"`.
   - Đáp ứng 100% ràng buộc schema của `source_record.schema.json`.
   - Hỗ trợ tiêm lỗi mô phỏng (fault injection) để kiểm tra các tình huống biên (401, 403, 429, 500, malformed).
2. **`CustomerImportAdapter` (`customer_import_adapter.py`)**:
   - Nòng cốt cho môi trường Offline MVP theo khuyến nghị tại P00.
   - Tiếp nhận tệp dữ liệu khách hàng cung cấp (JSON/CSV exports).
   - `synthetic` là `False` (dữ liệu thật của khách hàng).
   - Kiểm tra cấu trúc từng bản ghi: nếu thiếu trường bắt buộc (như `external_id` hoặc tiêu đề), hệ thống tự động cách ly vào danh sách `quarantine`, trả về trạng thái `PARTIAL` hoặc `INVALID_DATA`, không sập chương trình và không tuyên bố thành công giả mạo.
3. **`TikTokOfficialAdapter` (`tiktok_official_adapter.py`)**:
   - Adapter kết nối TikTok Display API / Commercial Content API.
   - Toàn bộ năng lực được khóa bằng trạng thái `REQUIRES_AUTH`.
   - Trạng thái trực tiếp: `UNVERIFIED` (chưa có credentials trực tiếp được phê duyệt).
   - Nếu gọi mà thiếu Access Token hợp lệ (`act.*`): lập tức trả về `AUTH_FAILED` (HTTP 401). Tuyệt đối **không** tự động chuyển sang cào trộm (scraping fallback) hay vượt captcha.

### 2.3. Quản Trị Tuân Thủ, Ngắt Mạch & Ngân Sách (`provider_registry.py`)
- **Khóa cứng công cụ cấm (T035):** Danh mục `BANNED_SOURCES` (`mediacrawler`, `tiktok_scraper`, `unapproved_crawler`, `douyin_scraper`) bị chặn ngay lập tức ở tầng Registry với mã lỗi `RIGHTS_NOT_GRANTED`, không thực hiện bất kỳ lệnh gọi mạng nào, đồng thời ghi log cảnh báo vào `AuditEvent`.
- **Cơ chế Ngắt Mạch (Circuit Breaker - T032):** Theo dõi số lần lỗi liên tiếp (ngưỡng 5 lần lỗi). Khi quá ngưỡng, ngắt mạch chuyển sang trạng thái `OPEN`, lập tức từ chối nhanh các request tiếp theo với mã `UNAVAILABLE` kèm thời gian chờ (`retry_after_seconds`).
- **Kiểm soát trần ngân sách (Budget Guard - T032):** Kiểm tra `current_requests >= max_requests` hoặc `current_cost_usd >= max_cost_usd`. Nếu vượt trần, từ chối với lỗi `BUDGET_EXCEEDED` mà không kích hoạt xử lý tốn tài nguyên.

### 2.4. Mở Rộng Cơ Sở Dữ Liệu & Endpoint API (`src/models/entities.py`, `src/modules/sources/router.py`)
- Bổ sung bảng ORM `quarantine_records` lưu trữ chi tiết bản ghi lỗi, nguyên nhân vi phạm và payload thô phục vụ kiểm toán xuất xứ dữ liệu (Provenance).
- Cung cấp các endpoint RESTful:
  - `GET /v1/sources/providers`: Liệt kê nhà cung cấp và năng lực.
  - `GET /v1/sources/providers/{id}/capabilities`: Chi tiết năng lực (trả 403 nếu nhà cung cấp bị cấm).
  - `POST /v1/sources/search`: Tìm kiếm có kiểm tra bản quyền, budget, circuit breaker.
  - `POST /v1/sources/customer-import`: Tiếp nhận batch dữ liệu khách hàng, tự động cách ly bản ghi hỏng vào bảng quarantine.
  - `GET /v1/sources/quarantine`: Tra cứu danh sách bản ghi bị cách ly theo workspace.
  - `GET /v1/sources/records`: Tra cứu danh sách bản ghi nguồn hợp lệ theo workspace.

---

## 3. BẰNG CHỨNG THỰC NGHIỆM CÁC BÀI KIỂM THỬ BẮT BUỘC P03

Toàn bộ 16/16 bài kiểm thử tự động (gồm 6 bài kiểm thử P03 và 10 bài kiểm thử hồi quy P01-P02) đã chạy thành công trên máy chủ:

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\tools\python-embed\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Baha Group
plugins: anyio-4.15.1, asyncio-1.4.0
collected 16 items

test_briefs.py::test_t020_incomplete_or_wrong_brand_brief_rejected PASSED [  6%]
test_briefs.py::test_t021_approved_brief_edited_creates_new_immutable_version PASSED [ 12%]
test_briefs.py::test_t022_viewer_tries_approve_brief_denied PASSED       [ 18%]
test_health.py::test_healthz_endpoint PASSED                             [ 25%]
test_health.py::test_readyz_endpoint PASSED                              [ 31%]
test_health.py::test_openapi_json_endpoint PASSED                        [ 37%]
test_migrations.py::test_database_migration_lifecycle PASSED             [ 43%]
test_sources.py::test_t030_provider_empty_results_zero_fake_records PASSED [ 50%]
test_sources.py::test_t031_auth_failed_forbidden_no_bypass PASSED        [ 56%]
test_sources.py::test_t032_rate_limited_bounded_backoff_and_budget_cap PASSED [ 62%]
test_sources.py::test_t033_malformed_response_quarantine_no_success_claim PASSED [ 68%]
test_sources.py::test_t034_live_source_status_truthful PASSED            [ 75%]
test_sources.py::test_t035_banned_source_rejected_without_network_call PASSED [ 81%]
test_tenancy.py::test_user_a_can_access_own_workspace_brief PASSED       [ 87%]
test_tenancy.py::test_cross_tenant_access_denied_user_b_cannot_access_workspace_1 PASSED [ 93%]
test_tenancy.py::test_user_b_in_own_workspace_cannot_read_brief1 PASSED  [100%]

======================= 16 passed, 4 warnings in 15.97s =======================
```

Kiểm tra an toàn bí mật mã nguồn (T012):
```text
=== T012: SECRETS & CREDENTIALS AUDIT ===
Scanning target directory: \\192.168.1.175\09.ai_workspace\01_du_an\PRJ_069_Sin_Xay_kenh\03_ban_lam_viec
Scanned files count: 1007

[PASS] Zero committed credentials, tokens or passwords found!
T012 Result: PASS
```

---

## 4. ĐỐI SOÁT TIÊU CHUẨN CỔNG THOÁT P03 (EXIT GATE CRITERIA)

| Tiêu Chuẩn Cổng P03 | Kết Quả Thực Nghiệm | Đánh Giá |
|---|---|:---:|
| **T030: Nguồn trả rỗng hợp lệ (Empty Handling)** | `test_t030` xác nhận trả về `EMPTY`, `items=[]`, 0 bản ghi giả | **ĐẠT (PASS)** |
| **T031: Xử lý 401/403/WAF không bypass (No Scraping Fallback)** | `test_t031` xác nhận 401 `AUTH_FAILED` và 403 `FORBIDDEN`, 0 bypass | **ĐẠT (PASS)** |
| **T032: Rate limiting backoff & Budget cap** | `test_t032` xác nhận phản hồi 429 và chặn trước khi gọi với `BUDGET_EXCEEDED` | **ĐẠT (PASS)** |
| **T033: Cách ly dữ liệu hỏng (Quarantine Isolation)** | `test_t033` xác nhận bản ghi lỗi bị cách ly vào bảng `QuarantineRecord`, trả về `PARTIAL`, không tuyên bố thành công giả | **ĐẠT (PASS)** |
| **T034: Báo cáo trung thực trạng thái Live (Truthful Live Status)** | `test_t034` xác nhận `tiktok_official` là `UNVERIFIED`, `customer_import` là `AUTHORIZED_IMPORT` | **ĐẠT (PASS)** |
| **T035: Chặn nguồn bị cấm không gọi mạng (Banned Source Guard)** | `test_t035` xác nhận `mediacrawler` bị từ chối 403 `RIGHTS_NOT_GRANTED` và ghi `AuditEvent` | **ĐẠT (PASS)** |
| **An toàn bảo mật (T012 Secrets Audit)** | Quét 1.007 tệp mã nguồn, 0 mật khẩu/token bị lộ | **ĐẠT (PASS)** |

---

## 5. KẾT LUẬN & ĐIỀU KIỆN TIẾP THEO

- **Pha P03 đã hoàn tất 100% các tiêu chí nghiệm thu.**
- Hệ thống đã sở hữu tầng trừu tượng nguồn dữ liệu hoàn chỉnh, tuân thủ nghiêm ngặt tính pháp lý, cơ chế cách ly lỗi và bảo vệ ngân sách.
- **Pha tiếp theo được phép triển khai:** **Pha P04 — Tiếp nhận dữ liệu, chuẩn hóa, xuất xứ & snapshot chỉ số (Ingestion, Provenance & Snapshots)**.
