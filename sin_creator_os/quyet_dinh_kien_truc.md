# QUYẾT ĐỊNH KIẾN TRÚC HỆ THỐNG (ARCHITECTURE DECISION RECORDS - ADR)
## DỰ ÁN: SIN CONTENT INTELLIGENCE (PRJ_069)
**Tài liệu tham chiếu chuẩn:** `docs/DECISIONS.md`  
**Phiên bản:** 1.0.0 | **Ngày ban hành:** 2026-10-21 | **Agent phụ trách:** Anti  
**Vị trí lưu trữ SSOT:** `03_ban_lam_viec/sin_creator_os/quyet_dinh_kien_truc.md`

---

## TỔNG QUAN BỐI CẢNH DỰ ÁN
Dự án PRJ_069_Sin_Xay_kenh hiện đã hoàn thành Gate 01 (`CP01_FRONTEND_FOUNDATION_CORE`) với việc xây dựng thành công bộ khung giao diện SaaS chuyên sâu cho sáng tạo nội dung TikTok tại `03_ban_lam_viec/sin_creator_os/` (Next.js 16, React 19, TypeScript, Tailwind CSS v4, shadcn/ui).

Giai đoạn tiếp theo đòi hỏi xây dựng hệ thống Content Intelligence: nghiên cứu nội dung có căn cứ, trích xuất nhu cầu khán giả, đề xuất ý tưởng, soạn kịch bản, quy trình duyệt bài và tiếp nhận phản hồi hiệu suất. Để đảm bảo tính bền vững, tuân thủ pháp lý và quy chuẩn kỹ thuật của BaHa Group, các quyết định kiến trúc sau đây được xác lập làm chuẩn mực bắt buộc cho toàn bộ các pha triển khai từ P00 đến P13.

---

## ADR-001: LỰA CHỌN MÔ HÌNH KIẾN TRÚC TỔNG THỂ (MODULAR MONOLITH)

- **Trạng thái:** ĐÃ PHÊ DUYỆT (APPROVED).
- **Bối cảnh:** Kế hoạch đề xuất mô hình phân tán giữa Next.js Frontend, FastAPI Backend, Celery/Redis Worker, Postgres/pgvector và LangGraph. Kho mã nguồn hiện có là `sin_creator_os` (Next.js 16 Fullstack App Router).
- **Quyết định:**
  1. Giữ nguyên `03_ban_lam_viec/sin_creator_os/` làm Frontend Client & Workspace Shell chính của người dùng.
  2. Bổ sung Backend Service chuyên biệt sử dụng **Python 3.11+ / FastAPI** đặt tại `03_ban_lam_viec/sin_content_api/` (hoặc module hóa trong cùng phân vùng làm việc `03_ban_lam_viec/`) nhằm tận dụng hệ sinh thái xử lý ngôn ngữ tự nhiên (NLP), embedding, trích xuất dữ liệu và LangGraph.
  3. Sử dụng mô hình **Modular Monolith** có ranh giới module rõ ràng thay vì chia nhỏ thành Microservices, giảm thiểu độ trễ mạng NAS và độ phức tạp vận hành.
- **Hệ quả & Đánh đổi:**
  - *Tích cực:* Phân định rạch ròi trách nhiệm (Separation of Concerns). Giao diện web chạy mượt mà, độc lập; các tác vụ nặng (LangGraph, embedding, trích xuất bình luận) chạy ngầm qua hàng đợi Celery/Redis không gây đơ ứng dụng.
  - *Đánh đổi:* Cần quản lý cấu hình kết nối mạng nội bộ giữa Next.js và FastAPI thông qua biến môi trường bảo mật (`INTERNAL_API_URL`).

---

## ADR-002: ÁNH XẠ CẤU TRÚC KHO MÃ NGUỒN VÀ TIÊU CHUẨN ĐẶT TÊN

- **Trạng thái:** ĐÃ PHÊ DUYỆT (APPROVED).
- **Bối cảnh:** Quy tắc bất biến của dự án PRJ_069 quy định:
  - Chỉ được chỉnh sửa trong `03_ban_lam_viec/` và các file trạng thái được phép ở `00_bat_dau/`.
  - Tên tệp và thư mục mới phải 100% tiếng Việt không dấu, chữ thường, `snake_case`.
  - Gói kế hoạch tham chiếu `SIN_Anti_Content_Intelligence_Plan_v1.zip` sử dụng cấu trúc thư mục tiếng Anh (`docs/`, `apps/api`, `apps/web`).
- **Quyết định:** Thiết lập bảng ánh xạ chuẩn từ gói kế hoạch sang cấu trúc thực tế của dự án:

| Tài Liệu / Module Theo Kế Hoạch | Vị Trí Triển Khai Thực Tế Trong PRJ_069 | Mô Tả Chức Năng |
|---|---|---|
| `docs/DECISIONS.md` | `03_ban_lam_viec/sin_creator_os/quyet_dinh_kien_truc.md` | Quyết định kiến trúc hệ thống |
| `docs/OPEN_BLOCKERS.md` | `03_ban_lam_viec/sin_creator_os/danh_sach_blocker_rui_ro.md` | Quản trị rủi ro và các điểm nghẽn |
| `docs/provider-audit/CAPABILITY_MATRIX.csv` | `03_ban_lam_viec/sin_creator_os/ma_tran_nang_luc_nguon_du_lieu.csv` | Ma trận 6 năng lực nguồn dữ liệu |
| `docs/provider-audit/RIGHTS_REVIEW.md` | `03_ban_lam_viec/sin_creator_os/danh_gia_quyen_va_giay_phep.md` | Đánh giá pháp lý, giấy phép và chi phí |
| `docs/phase-reports/P00.md` | `03_ban_lam_viec/sin_creator_os/bao_cao_p00.md` | Báo cáo nghiệm thu kết quả pha P00 |
| `PHASES.yaml` & `ACCEPTANCE_TESTS.md` | `03_ban_lam_viec/sin_creator_os/danh_muc_nghiem_thu_cac_pha.md` | Checklist nghiệm thu các pha P01 - P13 |
| `apps/web` | `03_ban_lam_viec/sin_creator_os/` | Ứng dụng Next.js SaaS Creator OS |
| `apps/api` | `03_ban_lam_viec/sin_content_api/` | Backend API FastAPI (triển khai ở P01) |
| `workers` | `03_ban_lam_viec/sin_content_workers/` | Celery / Redis async worker (P01) |
| `packages/contracts` | `03_ban_lam_viec/sin_creator_os/src/contracts/` | JSON Schema & Typed DTOs đồng bộ |
| `fixtures/` | `03_ban_lam_viec/sin_creator_os/fixtures/` | Dữ liệu kiểm thử ngoại tuyến tổng hợp |

---

## ADR-003: CƠ CHẾ CÁCH LY ĐA KHÁCH THUÊ (MULTI-TENANCY & WORKSPACE ISOLATION)

- **Trạng thái:** ĐÃ PHÊ DUYỆT (APPROVED).
- **Bối cảnh:** Hệ thống phục vụ nhiều kênh/khách hàng khác nhau. Rò rỉ dữ liệu giữa các workspace là vi phạm nghiêm trọng mức độ CRITICAL.
- **Quyết định:**
  1. Mọi truy vấn đọc/ghi dữ liệu ở tầng Backend **BẮT BUỘC** phải gắn kèm và kiểm tra `workspace_id` được xác thực từ Session/JWT phía server.
  2. **Tuyệt đối không tin tưởng `workspace_id` do client tự gửi lên** trong URL hoặc body payload nếu không khớp với quyền sở hữu trong token phiên đăng nhập.
  3. Mọi dữ liệu nghiên cứu, ý tưởng, kịch bản, và chỉ số đều được phân vùng cứng theo `workspace_id`.
  4. Thực hiện kiểm tra phủ định (Negative Test) trong CI: Yêu cầu từ Workspace A truy cập tài nguyên của Workspace B phải nhận mã lỗi `403 Forbidden` hoặc `404 Not Found` mà không để lộ metadata.

---

## ADR-004: NGUYÊN TẮC BẰNG CHỨNG THỰC TẾ & BẢO TOÀN DỮ LIỆU NGUỒN (DATA PROVENANCE)

- **Trạng thái:** ĐÃ PHÊ DUYỆT (APPROVED).
- **Bối cảnh:** Hiện tại giao diện `sin_creator_os` đang sử dụng dữ liệu giả lập (mock data). Trong hệ thống sản xuất, AI không được phép bịa đặt số liệu (hallucination) hoặc biến phỏng đoán thành sự thật.
- **Quyết định:**
  1. Phân loại nghiêm ngặt 4 trạng thái dữ liệu trong toàn bộ schema:
     - `OBSERVED`: Dữ liệu quan sát thực tế từ nguồn hợp pháp (kèm URL, ID gốc, thời điểm `observed_at`, phương thức thu thập).
     - `DERIVED`: Chỉ số phái sinh tính toán theo công thức toán học tường minh (phải ghi rõ công thức và ID của các snapshot gốc).
     - `INFERRED`: Suy luận từ mô hình AI (phải có nhãn confidence và chỉ số độ tin cậy).
     - `HYPOTHESIS`: Giả thuyết sáng tạo chưa kiểm chứng (phải gắn nhãn rõ ràng trên UI, người dùng phải chủ động bật cờ `allow_hypotheses=true`).
  2. Mọi dữ liệu fixture kiểm thử ngoại tuyến **BẮT BUỘC** gắn cờ `synthetic=true`. Cổng Backend sẽ chặn dữ liệu `synthetic=true` đi vào luồng sản xuất thực tế.
  3. Nếu không có đủ dữ liệu quan sát thực tế, hệ thống trả về mã lỗi có cấu trúc `INSUFFICIENT_EVIDENCE`, tuyệt đối không tự động chuyển sang bịa đặt ý tưởng không có căn cứ.

---

## ADR-005: CHIẾN LƯỢC NGUỒN DỮ LIỆU CHO OFFLINE MVP VÀ PRODUCTION GO-LIVE

- **Trạng thái:** ĐÃ PHÊ DUYỆT (APPROVED).
- **Bối cảnh:**
  - TikTok không cung cấp API tìm kiếm công khai toàn cầu cho tài khoản thông thường.
  - MediaCrawler bị cấm triệt để do giấy phép phi thương mại.
  - Các công cụ cào lậu (unofficial scraper) tiềm ẩn rủi ro bị khóa IP và vi phạm điều khoản TikTok.
- **Quyết định:**
  1. **Nền tảng cho Offline MVP (P01 - P10):** Sử dụng `customer_import` (Dữ liệu khách hàng tự cung cấp từ kênh của họ dưới dạng file CSV/JSON hợp pháp) kết hợp với các bộ kiểm thử `fixtures/offline` có nhãn `synthetic=true`.
  2. **Tích hợp Kênh chính chủ (P11):** Sử dụng `tiktok_official_api` thông qua TikTok Login Kit & Display API để lấy chỉ số video chính chủ của khách hàng sau khi hoàn thành quy trình cấp quyền OAuth.
  3. **Khảo sát thị trường rộng:** Đặt ở trạng thái `UNVERIFIED` / `BLOCKED`. Chỉ xem xét tích hợp Apify Actor trả phí hoặc nhà cung cấp được cấp phép thương mại khi có phê duyệt ngân sách và văn bản pháp lý từ cấp quản lý.
  4. **Triệt để loại bỏ:** Cấm đưa `MediaCrawler` hoặc bất kỳ mã nguồn nào có giấy phép không tương thích vào repository.

---

## ADR-006: KIỂM SOÁT NGÂN SÁCH VÀ NGẮT MẠCH BẢO VỆ (BUDGET CIRCUIT BREAKER)

- **Trạng thái:** ĐÃ PHÊ DUYỆT (APPROVED).
- **Bối cảnh:** Việc gọi các mô hình LLM và dịch vụ ngoài tiềm ẩn rủi ro phát sinh chi phí đột biến ngoài tầm kiểm soát.
- **Quyết định:**
  1. Mọi tác vụ nghiên cứu (`ResearchRun`) và sinh ý tưởng (`IdeaGeneration`) đều phải khai báo mức trần ngân sách (`max_cost_usd`).
  2. Hệ thống kiểm tra hạn mức còn lại trước khi phát lệnh gọi API tính phí. Nếu chi phí ước tính vượt quá hạn mức, hệ thống từ chối thực thi với mã lỗi `BUDGET_EXCEEDED`.
  3. Thiết lập bảng ghi nhật ký chi phí (`cost_ledger_events`) chi tiết theo từng workspace, từng tác vụ để đối soát minh bạch.

---

## KẾT LUẬN & HƯỚNG DẪN THỰC THI
Toàn bộ các quyết định trên có hiệu lực tức thì kể từ Pha P00. Bất kỳ sự thay đổi nào đối với các kiến trúc nền tảng này đều phải thông qua quy trình lập đề xuất sửa đổi ADR và được Founder / Project Owner phê duyệt bằng văn bản.
