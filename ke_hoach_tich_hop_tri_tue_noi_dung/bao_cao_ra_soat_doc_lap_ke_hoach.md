# BÁO CÁO RÀ SOÁT ĐỘC LẬP KẾ HOẠCH TRIỂN KHAI TRÍ TUỆ NỘI DUNG (PRE-IMPLEMENTATION INDEPENDENT AUDIT)
## Phân Hệ SIN Content Intelligence (SIN-CONTENT-INTELLIGENCE-001 v2.0)

- **Mã báo cáo:** AUDIT-PLAN-CI-2026-10-22
- **Phiên bản:** 1.0.0
- **Thời điểm rà soát:** 2026-10-22T09:40:00+07:00
- **Đơn vị rà soát:** Antigravity (Kiến trúc sư Thẩm định Độc lập & Quản trị Rủi ro Hệ thống)
- **Đối tượng rà soát:**
  1. Kế hoạch Master Plan: `03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ke_hoach_tich_hop_tri_tue_noi_dung.md`
  2. Kế hoạch khắc phục P10-P12: `03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ke_hoach_khac_phuc_va_dieu_chinh_p10_p11_p12.md`
  3. Ma trận phân quyền & UI: `03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ma_tran_tich_hop_rbac_va_frontend.md`
  4. Thực trạng mã nguồn và test suites tại `03_ban_lam_viec/sin_content_api/` và `baha_auth/`.
- **Nguyên tắc tối thượng:** Ground Truth > Self-Report. Mọi kết luận thẩm định phải dựa trên việc thực chạy lệnh, kiểm tra log lỗi thực tế và phân tích rủi ro kỹ thuật khách quan.
- **Cam kết kỷ luật:** CHƯA CODE MÃ NGUỒN RUNTIME. Toàn bộ phát hiện được đóng gói thành khuyến nghị điều chỉnh kế hoạch trước khi thi công.

---

## I. TỔNG QUAN KẾT QUẢ RÀ SOÁT ĐỘC LẬP

Quá trình rà soát độc lập đã tiến hành đối soát chéo giữa các tài liệu kế hoạch, hợp đồng dữ liệu, và thực trạng chạy lệnh trên hệ thống. Kết quả phát hiện **6 vấn đề cốt lõi (1 P0, 3 P1, 2 P2)** cần phải được hiệu chỉnh trong kế hoạch trước khi giao việc cho Codex thi công mã nguồn:

| Mã Vấn Đề | Mức Độ | Tên Vấn Đề Rà Soát | Tác Động Nếu Không Sửa Kế Hoạch |
|---|---|---|---|
| **AUD-01** | **CRITICAL (P0)** | **Bẫy "P00-P09 Đã Đạt" & Nợ kỹ thuật Test Harness cũ:** Các test suite P01-P03 dùng header legacy `X-User-Id` bị 401 Unauthorized do `baha_auth` đã siết chặt Bearer token | Không thể chạy regression test; CI toàn hệ thống sẽ đỏ rực khi Codex bắt đầu commit code mới |
| **AUD-02** | **HIGH (P1)** | **Nghịch lý thứ tự triển khai (Inverted Dependency Order):** Kế hoạch xếp P10 (Frontend Workbench) trước P11 (Entities/Database) và P12 (Budget Guard) | Frontend sẽ phải đập đi viết lại lần 2 do schemas và endpoints backend chưa ổn định |
| **AUD-03** | **HIGH (P1)** | **Rủi ro khóa tệp SQLite trên ổ mạng NAS (Windows SMB Locking):** Chạy database file trực tiếp trên đường dẫn mạng UNC gây lỗi treo tiến trình | Gặp lỗi `database is locked` hoặc `PermissionError` ngẫu nhiên khi chạy test hoặc dev server |
| **AUD-04** | **HIGH (P1)** | **Thiếu cơ chế Atomic Budget Update tương thích đa cơ sở dữ liệu:** SQLite không hỗ trợ `SELECT FOR UPDATE` của PostgreSQL | Dễ phát sinh lỗi cú pháp khi chạy local hoặc không chặn được tranh chấp số dư đồng thời |
| **AUD-05** | **MEDIUM (P2)** | **Ranh giới dữ liệu TikTok Live vs Offline Fixtures:** Cần minh bạch tuyệt đối về việc chưa có TikTok Official API production credentials | Nguy cơ tạo mock data trá hình nếu không khóa chặt cờ `OFFLINE_FIXTURE_ONLY` |
| **AUD-06** | **MEDIUM (P2)** | **Đồng bộ triệt để nhận diện thương hiệu BAHA Creator Studio:** Còn sót chuỗi ký tự "SIN Creator OS" trong tài liệu và code mẫu | Ảnh hưởng tính đồng nhất thương hiệu và tài liệu bàn giao Founder |

---

## II. CHI TIẾT 6 PHÁT HIỆN RÀ SOÁT ĐỘC LẬP & GIẢI PHÁP ĐIỀU CHỈNH

### 1. AUD-01 (Mức độ: P0 - Critical): Test Harness Cũ Bị Chặn 401 Unauthorized Do Lõi Phân Quyền Đã Được Siết Chặt

#### Hiện Trạng & Bằng Chứng Thực Tế:
- Khi chạy thực tế kiểm thử P01-P03 trên môi trường hiện tại:
  ```bash
  python -m pytest 03_ban_lam_viec/sin_content_api/tests/test_tenancy.py 03_ban_lam_viec/sin_content_api/tests/test_briefs.py 03_ban_lam_viec/sin_content_api/tests/test_sources.py
  ```
  **Kết quả:** 12/15 bài kiểm thử bị **FAILED với mã lỗi HTTP 401 Unauthorized** (`Cần bearer token hợp lệ`).
- **Nguyên nhân gốc rễ:** Trong đợt khắc phục phân quyền ngày 21/10/2026, nhóm Luna đã siết chặt middleware bảo mật: Vô hiệu hóa hoàn toàn việc giả mạo danh tính qua header `X-User-Id` và bắt buộc 100% request phải có Bearer JWT token hợp lệ do `baha_auth` ký. Tuy nhiên, các file test cũ của P01, P02, P03 chưa được nâng cấp fixture sinh token Bearer (trong khi test P11 và P12 đã có fixture này).
- Ngoài ra, `test_scripts.py` (P09) gặp lỗi `ERROR at setup` do schema SQLite memory thiếu trường hoặc không tương thích fixture.

#### Điều Chỉnh Kế Hoạch Bắt Buộc:
- **Bổ sung Tầng 0 (P00-RE: Test Harness Modernization) vào đầu lộ trình:**
  - Nâng cấp `conftest.py` tại `sin_content_api/tests/` để cung cấp fixture `auth_headers(role, workspace_id)` chuẩn hóa, tự động tạo Bearer JWT token hợp lệ cho mọi bài test từ P01 đến P12.
  - Sửa lỗi setup bảng kịch bản trong `test_scripts.py`.
  - Bảo đảm toàn bộ test suite cơ sở (Baseline P01 - P09) xanh 100% trước khi can thiệp vào P10, P11, P12.

---

### 2. AUD-02 (Mức độ: P1 - High): Đảo Ngược Thứ Tự Phụ Thuộc Kỹ Thuật (Phải Làm Backend & Schemas Trước Khi Nối UI)

#### Hiện Trạng & Phân Tích Kỹ Thuật:
- Trong kế hoạch trước đây, lộ trình ghi: Bước 1 (Sửa P10 UI Workbench) &rarr; Bước 2 (Sửa P11 Feedback Loop) &rarr; Bước 3 (Sửa P12 Staging Security/Budget).
- **Lỗ hổng logic:** P10 Workbench là tầng giao diện người dùng (Frontend UI). Nếu Codex tiến hành nối UI với API ngay từ đầu, trong khi:
  - Các thực thể CSDL của P11 (`PublishedContentLink`, `LearningSignal`, `ExperimentSuggestion`) chưa có trong ORM.
  - Trường `is_paid` và `channel_id` của `SourceRecord` chưa được bảo toàn.
  - Cấu trúc `WorkspaceBudget` và `CostLedger` của P12 chưa được chốt chặn.
  &rarr; Frontend TypeScript Contracts (`sin_creator_os/src/contracts/`) sẽ bị lỗi thời và phải đập đi sửa lại nhiều lần, gây lãng phí công sức và dễ phát sinh lỗi hồi quy.

#### Điều Chỉnh Kế Hoạch Bắt Buộc:
- **Tái cấu trúc lộ trình theo nguyên tắc "Từ Trong Ra Ngoài" (Inside-Out):**
  1. **Bước 1 (Tầng Dữ Liệu & Hợp Đồng):** Bổ sung thực thể ORM (`entities.py`), migrations, Pydantic Schemas (`contracts.py`) và đồng bộ sang TypeScript Contracts (`contracts/index.ts`).
  2. **Bước 2 (Tầng Logic Nghiệp Vụ & API Guard):** Sửa toàn bộ backend endpoints của P10 (expected_version, atomic update), P11 (xóa mock, tính vận tốc), P12 (cache key tenant, atomic budget, backup scrubbing).
  3. **Bước 3 (Tầng Giao Diện Người Dùng):** Nối các màn hình Frontend P10 với API backend đã hoàn chỉnh và ổn định.
  4. **Bước 4 (Tầng Kiểm Thử & Nghiệm Thu):** Chạy E2E Playwright và đánh giá Staging.

---

### 3. AUD-03 (Mức độ: P1 - High): Rủi Ro Khóa Tệp SQLite Trên Ổ Mạng NAS (Windows SMB File Locking)

#### Hiện Trạng & Nguy Cơ:
- Mã nguồn và cơ sở dữ liệu `sin_content_offline.db` đang nằm trên thư mục chia sẻ mạng UNC: `\\192.168.1.175\09.ai_workspace\01_du_an\PRJ_069_Sin_Xay_kenh\`.
- Giao thức chia sẻ tệp SMB của Windows có cơ chế khóa tệp rất ngặt nghèo (Opportunistic Locks / File Locking). Khi có 2 tiến trình trở lên (ví dụ vừa chạy Next.js dev server, vừa chạy FastAPI backend, vừa chạy Pytest) cùng mở file `.db` trên NAS, SQLite sẽ lập tức ném ngoại lệ `sqlite3.OperationalError: database is locked` hoặc `PermissionError`.

#### Điều Chỉnh Kế Hoạch Bắt Buộc:
- **Quy chuẩn quản trị môi trường thực thi:**
  - Toàn bộ các bài kiểm thử tự động (Unit / Integration Tests) **bắt buộc chạy trên SQLite In-Memory (`sqlite:///:memory:`) hoặc URI memory chia sẻ (`sqlite:///file:memdb?mode=memory&cache=shared&uri=true`)**.
  - Khi chạy ứng dụng local để kiểm thử giao diện: File database tạm thời phải được đặt tại ổ đĩa SSD cục bộ của máy trạm (ví dụ `C:\temp\sin_dev.db`), sau đó mới đồng bộ snapshot kết quả nghiệm thu về NAS. Tuyệt đối cấm nhiều tiến trình cùng ghi đồng thời vào file `.db` trên đường dẫn mạng UNC.

---

### 4. AUD-04 (Mức độ: P1 - High): Thiếu Cơ Chế Giữ Chỗ Ngân Sách Nguyên Tử (Atomic Budget Reservation) Tương Thích Cả SQLite và PostgreSQL

#### Hiện Trạng & Nguy Cơ:
- Phát hiện P12-04 chỉ ra lỗi 2 session đồng thời cùng giữ chỗ ngân sách dẫn đến mất cập nhật (Lost Update) và vượt trần hạn ngạch.
- Nếu giải quyết bằng cách dùng `SELECT ... FOR UPDATE` (cú pháp của PostgreSQL), mã nguồn sẽ sập ngay lập tức trên môi trường SQLite local/test vì SQLite không hỗ trợ cú pháp này.
- Nếu chỉ dùng Python threading Lock, cơ chế sẽ vô hiệu khi ứng dụng chạy trên đa tiến trình worker (Multi-worker Uvicorn / Celery).

#### Điều Chỉnh Kế Hoạch Bắt Buộc:
- **Quy chuẩn công thức Atomic SQL độc lập với loại database:**
  Sử dụng duy nhất một câu lệnh `UPDATE` có điều kiện số dư ở tầng database:
  ```python
  stmt = (
      update(WorkspaceBudget)
      .where(
          WorkspaceBudget.workspace_id == workspace_id,
          (WorkspaceBudget.allocated_units - WorkspaceBudget.reserved_units - WorkspaceBudget.spent_units) >= amount
      )
      .values(reserved_units=WorkspaceBudget.reserved_units + amount)
  )
  result = db.execute(stmt)
  if result.rowcount == 0:
      raise HTTPException(status_code=402, detail="REFUSED_OVER_BUDGET")
  ```
  *Cơ chế này hoạt động chính xác 100% trên cả SQLite, MySQL và PostgreSQL mà không cần cú pháp khóa dòng đặc thù.*

---

### 5. AUD-05 (Mức độ: P2 - Medium): Khóa Chặt Trạng Thái Quyền Nguồn TikTok Thật (Real Source vs Mock Fixture)

#### Hiện Trạng:
- Trong mã nguồn và tài liệu có một số chỗ dùng từ ngữ dễ gây hiểu lầm như "Kết nối TikTok Official thành công" hay "Thu thập dữ liệu live".
- Trên thực tế, dự án hiện chưa có TikTok Developer Partner App Credentials chính thức.

#### Điều Chỉnh Kế Hoạch Bắt Buộc:
- Kế hoạch phải quy định rõ: Trạng thái của nguồn TikTok hiện tại bắt buộc phải là `UNVERIFIED / OFFLINE_FIXTURE_ONLY`.
- Mọi dữ liệu nghiên cứu phục vụ kiểm thử bắt buộc đi qua `CustomerImportAdapter` (nhập file CSV/JSON hợp lệ do khách hàng cung cấp) hoặc `OfflineFixtureAdapter`. Cấm tuyệt đối việc tạo code giả mạo cào dữ liệu lậu hoặc giả lập kết nối live khi chưa có văn bản cấp phép.

---

### 6. AUD-06 (Mức độ: P2 - Medium): Chuẩn Hóa Nhận Diện Thương Hiệu BAHA Creator Studio

#### Hiện Trạng:
- Trong một số file tài liệu cũ và schema frontend vẫn còn sót rải rác nhãn `SIN Creator OS`.
- Nhận diện thương hiệu chính thức đã được Founder chốt là **BAHA Creator Studio**.

#### Điều Chỉnh Kế Hoạch Bắt Buộc:
- Đưa vào checklist nghiệm thu: Quét sạch 100% các điểm hiển thị trên giao diện người dùng và thông điệp hệ thống để hiển thị đúng "BAHA Creator Studio".
- Giữ nguyên các mã định danh kỹ thuật nội bộ (như `sin_content_api`, `PRJ_069`) ở tầng hạ tầng để tránh gãy liên kết đường dẫn (Preserve Technical SSOT).

---

## III. LỘ TRÌNH 5 BƯỚC ĐIỀU CHỈNH HOÀN THIỆN (REFINED IMPLEMENTATION ROADMAP)

Dựa trên kết quả rà soát độc lập, lộ trình thi công chính thức được điều chỉnh lại như sau:

```
[BƯỚC 0: CHUẨN HÓA TEST HARNESS & AUTH FIXTURE (P00-RE)]
  - Nâng cấp conftest.py: Tạo fixture Bearer JWT token hợp lệ của baha_auth.
  - Chạy lại toàn bộ test suite P01 - P09 -> Đảm bảo Baseline xanh 100%.
       |
       v
[BƯỚC 1: ĐỒNG BỘ CƠ SỞ DỮ LIỆU, ORM & HỢP ĐỒNG BACKEND]
  - entities.py: Bổ sung PublishedContentLink, LearningSignal, ExperimentSuggestion.
  - entities.py: Thêm trường is_paid, channel_id vào SourceRecord; bảo toàn cờ khi Ingestion.
  - entities.py: Bổ sung WorkspaceBudget, CostLedger, UniqueConstraint chống duplicate.
  - contracts.py: Bắt buộc expected_version/expected_status trong IdeaReviewRequest.
  - contracts/index.ts: Đồng bộ 100% sang hợp đồng TypeScript Frontend.
       |
       v
[BƯỚC 2: SỬA TOÀN BỘ LOGIC BACKEND & GUARDS (P10, P11, P12 BACKEND)]
  - P10 Backend: Triển khai atomic review update chống race condition; tách trending khỏi single snapshot; chặn thời gian tương lai.
  - P11 Backend: Xóa bỏ hoàn toàn số liệu mock 45k/86; chuẩn hóa OAuth status; giữ null xuyên suốt khi thiếu data; lọc bỏ synthetic/purged.
  - P12 Backend: Khóa cache tác vụ theo {workspace_id}:{idempotency_key}; atomic budget update; backup scrubbing đệ quy; restore kiểm tra integrity trước khi thay thế đích.
  - Chạy test suites Pytest cho P10, P11, P12 -> Đạt 100% PASS.
       |
       v
[BƯỚC 3: TÍCH HỢP GIAO DIỆN FRONTEND WORKBENCH (P10 FRONTEND)]
  - Nối 8 màn hình chính với API backend thực tế (thay thế mockIdeas, mockContentAnalysis).
  - Triển khai UI Modal duyệt bài 4 thao tác (Approve / Reject / Request Evidence / Reopen).
  - Hiển thị trực quan trạng thái MISSING và EXPIRED.
  - Chạy Playwright E2E tự động cho 8 màn hình và chụp ảnh bằng chứng.
       |
       v
[BƯỚC 4: ĐÁNH GIÁ STAGING, QUÉT BẢO MẬT & NGHIỆM THU GATE P13]
  - Chạy đánh giá Prompt trên held-out gold sets >= 30 mẫu x 3 briefs với 2 chuyên gia đánh giá.
  - Quét T012 Secrets Scanner trên 100% tệp trong 03_ban_lam_viec.
  - Kiểm toán giấy phép dependencies (T125).
  - Lập Báo cáo nghiệm thu hoàn chỉnh trình Founder ký duyệt trước khi mở Canary P13.
```

---

## IV. KẾT LUẬN & KIẾN NGHỊ

1. **Kế hoạch Master Plan v2.0 có cơ sở kiến trúc vững chắc**, nhưng cần được bổ sung ngay **Bước 0 (P00-RE)** và đảo thứ tự triển khai (Backend/ORM trước, Frontend UI sau) để tránh rủi ro vỡ trận khi bắt tay vào code.
2. **Kế hoạch khắc phục kỹ thuật đã quy định chính xác giải pháp cho 27 phát hiện**, nay được bổ sung thêm giải pháp Atomic SQL độc lập cơ sở dữ liệu và quy chuẩn môi trường chạy SQLite in-memory.
3. **Toàn bộ hệ thống hiện tại được giữ nguyên vẹn (CHƯA CODE)**, sẵn sàng để Founder phê duyệt báo cáo rà soát này trước khi phân công Codex thi công Bước 0 và Bước 1.
