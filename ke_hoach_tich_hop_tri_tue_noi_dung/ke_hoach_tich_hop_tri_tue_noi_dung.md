# KẾ HOẠCH TÍCH HỢP & ĐIỀU CHỈNH HỆ THỐNG TRÍ TUỆ NỘI DUNG (SIN-CONTENT-INTELLIGENCE-001)

- **Mã kế hoạch:** SIN-CONTENT-INTELLIGENCE-001
- **Phiên bản điều chỉnh:** 2.0.0
- **Ngày cơ sở gốc:** 21/10/2026 | **Ngày cập nhật điều chỉnh:** 22/10/2026
- **Trạng thái:** HOÀN TẤT ĐIỀU CHỈNH KẾ HOẠCH — ĐÃ XUẤT BẢN ĐẶC TẢ THI CÔNG CHI TIẾT (SPEC-EXEC-CI-2026-10-22) — **SẴN SÀNG TRIỂN KHAI (CHỜ LỆNH THI CÔNG)**.
- **Gói nguồn gốc tham chiếu:** `SIN_Anti_Content_Intelligence_Plan_v1.zip` tại thư mục gốc và `01_nguon_goc_bat_bien/` (Mã băm SHA256: `D58AF29EC4DA58A6E3D501A9451D489FD2F3AD4BAE5E90B42FF1F6D961817303`).
- **Phân vùng giải nén nguyên bản để đối soát diff:** `02_nguyen_ban_giai_nen/anti_content_intelligence_plan/`.
- **Kết quả kiểm định tính toàn vẹn gói nguồn (verify_pack.py):** ĐẠT 100% (8 tài liệu hướng dẫn bắt buộc, 15 pha tuần tự, 4 JSON Schemas hợp lệ, 5 synthetic fixtures, kiểm tra xuất xứ và công thức chấm điểm hợp lệ).
- **Phạm vi tài liệu:** Tích hợp toàn diện kiến trúc Trí tuệ Nội dung vào hệ sinh thái BAHA Creator Studio và Hệ thống Phân quyền Doanh nghiệp BAHA-AUTHZ-001; điều chỉnh lộ trình 15 pha (P00 - P14) dựa trên kết quả kiểm định độc lập thực tế; ban hành lộ trình khắc phục 27 phát hiện kỹ thuật (P10, P11, P12) trước khi mở cổng Canary P13. **Tuyệt đối chưa can thiệp sửa mã nguồn runtime (chưa code).**

---

## 1. Mục Tiêu Tích Hợp & Nguyên Tắc Tối Thượng

### 1.1 Mục Tiêu Cốt Lõi
Xây dựng phân hệ Trí tuệ Nội dung & Đề xuất Ý tưởng có Căn cứ (Content Intelligence & Evidence-Based Idea Generation) phục vụ vận hành kênh TikTok đa khách thuê (Multi-tenant SaaS). Hệ thống hỗ trợ khép kín chu trình sáng tạo:
1. **Nghiên cứu có căn cứ:** Thu thập dữ liệu từ các nguồn được cấp phép hoặc xuất dữ liệu chính thức do khách hàng cung cấp.
2. **Bóc tách nhu cầu khán giả:** Phân tích bình luận, phụ đề, phân loại nỗi đau, câu hỏi và sự phản đối mua hàng.
3. **Đề xuất ý tưởng gắn chứng cứ:** Tạo các thẻ ý tưởng (IdeaCard) có liên kết 100% với trích dẫn thực tế; phân định rõ giữa dữ liệu quan sát và giả thuyết sáng tạo.
4. **Soạn thảo kịch bản & Kiểm định sự thật:** Tự động đối soát lời thoại/phân cảnh với danh mục sự thật thương hiệu được duyệt (AllowedFact); ngăn chặn tuyên bố định lượng sai lệch.
5. **Vòng lặp học tập từ kênh sở hữu:** Tiếp nhận dữ liệu phân tích chỉ đọc từ các bài đăng thực tế trên kênh của khách hàng để tối ưu hóa thuật toán đề xuất cho các chu kỳ tiếp theo.

### 1.2 Bảy Nguyên Tắc Bất Biến (Immutable Invariants)
1. **Ground Truth > Self-Report (Bằng chứng thực tế trên hết):** Kết quả kiểm thử trên fixture ngoại tuyến (Offline fixture PASS) chỉ chứng minh logic mã nguồn, **tuyệt đối không chứng minh năng lực kết nối dữ liệu TikTok thật**. Năng lực dữ liệu thật chỉ được công nhận khi có nguồn truy cập hợp lệ, được cấp phép và có bằng chứng đối soát tái lập được.
2. **Zero Fabricated Data (Không bịa đặt dữ liệu):** Cấm tuyệt đối việc tạo số liệu giả định, tạo trích dẫn URL không tồn tại, hoặc suy diễn nhân khẩu học (độ tuổi, nghề nghiệp, giới tính) của người dùng khi thiếu báo cáo phân tích chính thức từ nền tảng.
3. **No Commercial Integration of Unapproved Code:** Cấm tích hợp các thư viện phi thương mại hoặc công cụ cào lậu vi phạm điều khoản dịch vụ (chặn đứng `MediaCrawler` và các công cụ bypass anti-bot).
4. **Idempotency & Safe Provenance:** Mọi tác vụ tiếp nhận dữ liệu, tính toán chỉ số, hoặc sinh ý tưởng phải đảm bảo tính lũy đẳng (Idempotent); 100% bản ghi dữ liệu phải truy nguyên được nhà cung cấp, thời điểm quan sát, phương thức lấy mẫu và bản ghi quyền sở hữu.
5. **Single Snapshot Integrity:** Đơn ảnh chụp số liệu chỉ phản ánh quy mô tại thời điểm quan sát; cấm tuyệt đối suy diễn vận tốc tăng trưởng xu hướng (Trend Velocity) từ một ảnh chụp đơn lẻ. Mọi kết luận về vận tốc bắt buộc yêu cầu tối thiểu >= 2 ảnh chụp cách nhau theo thời gian thực tế.
6. **Separation of Organic & Paid Cohorts:** Tách bạch triệt để giữa dữ liệu tự nhiên (Organic) và dữ liệu trả phí/quảng cáo (Paid); nghiêm cấm gộp số liệu để thổi phồng hiệu quả tiếp cận tự nhiên.
7. **Strict Human Review (Quy tắc Bốn Mắt & Phê duyệt Con người):** Mọi ý tưởng và kịch bản bắt buộc qua kiểm duyệt con người trước khi chuyển trạng thái sản xuất; cấm người tạo tự phê duyệt nội dung của mình.

---

## 2. Ánh Xạ Kiến Trúc Ba Trụ Cột Trong PRJ_069

Kế hoạch Trí tuệ Nội dung được tích hợp hài hòa vào cấu trúc hiện tại của dự án:

```
+-----------------------------------------------------------------------------------+
| TRỤ CỘT 1: FRONTEND SAAS - BAHA CREATOR STUDIO (03_ban_lam_viec/sin_creator_os/)  |
| Next.js 16+, Tailwind v4, shadcn/ui, BAHA Design Tokens (Primary #2B6FB8)        |
| 16 Core Screens: /discover, /ideas, /scripts, /video-studio (Safe Zone 9:16)...  |
+----------------------------------------+------------------------------------------+
                                         | REST API / Auth Headers
                                         v
+-----------------------------------------------------------------------------------+
| TRỤ CỘT 2: PHÂN QUYỀN DOANH NGHIỆP BAHA-AUTHZ-001 (03_ban_lam_viec/baha_auth/)   |
| 58 Action Keys, 15 Tổ Chức Vai Trò, Centralized Authorizer, AuditEvent            |
| RLS, Multi-tenant Isolation, Four-Eyes Principle, Quản trị Ngân sách Tác tử AI   |
+----------------------------------------+------------------------------------------+
                                         | Scoped Requests / RBAC Context
                                         v
+-----------------------------------------------------------------------------------+
| TRỤ CỘT 3: HỆ THỐNG TRÍ TUỆ NỘI DUNG (sin_content_api/ & sin_content_workers/)     |
| FastAPI Backend, SQLAlchemy ORM, SQLite Offline DB / PostgreSQL, Celery/Redis     |
| 15 Pha Tuần Tự (P00 - P14): Ingestion, NLP, Ranking, Idea, Script, Feedback Loop   |
+-----------------------------------------------------------------------------------+
```

### 2.1 Ánh Xạ Giao Diện BAHA Creator Studio (`sin_creator_os`)
- `/discover` & `/discover/[contentId]`: Khám phá nội dung viral có căn cứ; hiển thị xuất xứ dữ liệu, thời điểm quan sát, và 10 thông số phân tích bóc tách.
- `/ideas` & `/ideas/generate`: Phòng lab ý tưởng; tiếp nhận thẻ IdeaCard có điểm số 5 chiều, liên kết chứng cứ, và cờ phân biệt giữa `EVIDENCE_BACKED` và `HYPOTHESIS`.
- `/scripts/[id]`: Script Studio 3 cột; kiểm định lời thoại và phân cảnh đối soát trực tiếp với danh mục `AllowedFact`.
- `/video-studio/[projectId]`: Dựng video dọc 9:16 có Safe Zone TikTok (Top 150px, Bottom 320px, Right 120px).
- `/analytics` & `/competitors`: Radar phân tích chỉ số kênh; chỉ hiển thị dữ liệu có snapshot thực tế, phân biệt rõ ràng giữa Organic và Paid.

### 2.2 Ánh Xạ Phân Quyền Doanh Nghiệp BAHA-AUTHZ-001 (`baha_auth`)
- **Quyền Nghiên cứu & Dữ liệu:** `research.read`, `research.run`, `sources.read`, `sources.manage`.
- **Quyền Ý tưởng & Kịch bản:** `idea.create`, `idea.read`, `idea.review`, `script.create`, `script.read`, `script.edit`, `script.approve_final`.
- **Quyền Kênh & Chỉ số:** `channel.read`, `channel.connect`, `analytics.read`, `analytics.export`.
- **Quyền Ngân sách & Vận hành:** `ai_budget.update`, `billing.manage`, `system.audit_read`.
- **Nguyên tắc phân định:** Áp dụng nghiêm ngặt quy tắc Bốn Mắt (Separation of Duties): Chuyên viên sáng tạo (`content_creator`, `scriptwriter`) chỉ được tạo bản nháp (DRAFT); quyền phê duyệt chuyển sang trạng thái APPROVED bắt buộc thuộc về `content_lead`, `marketing_director` hoặc `client_reviewer`.

---

## 3. Bảng Tổng Hợp Hiện Trạng & Điều Chỉnh Lộ Trình 15 Pha (P00 - P14)

Dưới đây là bảng đánh giá hiện trạng thực tế dựa trên Ground Truth và đối soát kiểm định kỹ thuật:

| Pha | Tên Pha Chuyên Môn | Hiện Trạng Thực Tế | Đánh Giá Kiểm Định | Quyết Định Điều Chỉnh Kế Hoạch |
|---|---|---|---|---|
| **P00** | Khảo sát kho mã, quyền dữ liệu & tính khả thi | Đã hoàn tất báo cáo kỹ thuật tại `bao_cao_p00.md` | PASS | Duy trì kết quả nghiệm thu; khóa chặt nguyên tắc cấm cào lậu TikTok. |
| **P01** | Khung kiến trúc, DTO, Đa khách thuê & CI | Đã hoàn tất backend FastAPI, DTOs, migrations | PASS | Duy trì kết quả; kiểm tra hồi quy sau khi sửa phân quyền lõi. |
| **P02** | Bản tóm tắt thương hiệu & Mô hình khán giả | Đã hoàn tất BrandBrief, AudienceSegment, AllowedFact | PASS | Duy trì kết quả; phiên bản bất biến và cách ly tenant đạt chuẩn. |
| **P03** | Bộ chuyển đổi nguồn & Minh chứng năng lực | Đã hoàn tất Offline Fixtures, TikTok Official, Import | PASS OFFLINE | Nguồn TikTok chỉ hoạt động ở chế độ Offline/Fixtures; gắn nhãn UNVERIFIED cho đến khi có API thật. |
| **P04** | Tiếp nhận dữ liệu, chuẩn hóa & snapshot chỉ số | Đã hoàn tất Ingestion lũy đẳng, MetricSnapshot null | PASS | Duy trì; cần đồng bộ việc bảo toàn cờ `is_paid` từ P11. |
| **P05** | Lập kế hoạch truy vấn & Tập dữ liệu vàng | Đã hoàn tất Taxonomy 6 nhóm, Gold sets 90 mẫu | PASS | Duy trì bộ đánh giá 2 chuyên gia độc lập kèm quy tắc phủ quyết Veto. |
| **P06** | Hiểu nội dung NLP & Bóc tách tín hiệu | Đã hoàn tất NeedSignal, PromptInjectionGuard | PASS | Bảo toàn liên kết trích dẫn gốc; ASR giữ nhãn UNVERIFIED khi thiếu audio cấp phép. |
| **P07** | Truy xuất lai & Xếp hạng tất định | Đã hoàn tất TransparentScorer, Precision@10 >= 80% | PASS | Duy trì ma trận 5 chiều (Audience Fit 30%, Evidence 25%, Brand 20%, Uniqueness 15%, Feasibility 10%). |
| **P08** | Đề xuất ý tưởng có căn cứ trích dẫn | Đã hoàn tất IdeaCard, IdeaVerifier, DuplicateDetector | PASS | Mặc định trả `INSUFFICIENT_EVIDENCE` khi thiếu dữ liệu; cờ HYPOTHESIS có nhãn rõ ràng. |
| **P09** | Soạn thảo kịch bản & Kiểm định tuyên bố | Đã hoàn tất ClaimChecker, chặn tuyên bố chưa duyệt | PASS | Bất biến phiên bản (SUPERSEDED khi sửa bản APPROVED); dung sai thời lượng target ±3s. |
| **P10** | Giao diện nghiên cứu & Luồng phê duyệt | Báo cáo `bao_cao_p10.md` ghi nhận PASS, nhưng rà soát độc lập phát hiện **8 lỗi (6 P1, 2 P2)** | **BLOCKED - ĐIỀU CHỈNH CẦN SỬA** | **Tạm dừng nghiệm thu P10**. Lập backlog khắc phục 8 phát hiện (P10-01 đến P10-08): kết nối UI thật, bắt buộc expected_version, chống xung đột phiên bản. |
| **P11** | Vòng lặp phản hồi hiệu suất kênh & Tốc độ xu hướng | Báo cáo `bao_cao_p11.md` ghi nhận PASS, nhưng rà soát độc lập phát hiện **9 lỗi (7 P1, 2 P2)** | **BLOCKED - ĐIỀU CHỈNH CẦN SỬA** | **Tạm dừng nghiệm thu P11**. Lập backlog khắc phục 9 phát hiện (P11-01 đến P11-09): xóa số liệu mock, xác thực OAuth grant, bổ sung PublishedContentLink. |
| **P12** | An ninh, Độ tin cậy, Ngân sách & Đánh giá Staging | Báo cáo `bao_cao_p12.md` ghi nhận PASS, nhưng rà soát độc lập phát hiện **10 lỗi P1** | **BLOCKED - ĐIỀU CHỈNH CẦN SỬA** | **Tạm dừng nghiệm thu P12**. Lập backlog khắc phục 10 phát hiện (P12-01 đến P12-10): cách ly cache theo tenant, chống trừ phí kép, tẩy sạch secrets trong backup JSON. |
| **P13** | Phát hành Canary có kiểm soát & Rollback | Chưa triển khai | **NOT_STARTED (KHÓA CỔNG)** | **Khóa chặt Gate P13**. Chỉ mở khi 100% các phát hiện P10, P11, P12 được sửa triệt để và Founder ký duyệt. |
| **P14** | Mở rộng Đa phương thức & Nghiên cứu nâng cao | Hạng mục tùy chọn mở rộng tương lai | **NOT_STARTED** | Giữ nguyên ranh giới nghiên cứu độc lập; yêu cầu ngân sách và thẩm định bản quyền riêng. |

---

## 4. Trọng Tâm Điều Chỉnh: Danh Mục Khắc Phục Kỹ Thuật (Remediation Backlog)

Chi tiết kế hoạch hành động và bản thiết kế kỹ thuật mức code được quy định tại hai tài liệu đi kèm:
- `ke_hoach_khac_phuc_va_dieu_chinh_p10_p11_p12.md`: Lộ trình và phương án giải quyết 27 phát hiện kỹ thuật theo 5 bước tối ưu.
- `ban_dac_ta_thi_cong_chi_tiet.md`: Bản đặc tả thi công chi tiết mức mã nguồn (chữ ký hàm, schema DTO, câu lệnh atomic update SQL, test commands và RACI matrix). Dưới đây là tóm lược các nhóm giải pháp bắt buộc:

### 4.1 Khắc Phục Pha P10 (Giao diện Nghiên cứu & Luồng Kiểm duyệt - 8 Phát hiện)
1. **P10-01 (P1):** Thay thế toàn bộ mock data trong UI (`ideas/page.tsx`, `idea-service.ts`, `discover-service.ts`) bằng API endpoints thật kết nối cơ chế xác thực và workspace hiện hành.
2. **P10-02 (P1):** Bắt buộc trường `expected_version` và `expected_status` trong hợp đồng API review; từ chối dứt khoát với HTTP 422 nếu thiếu một trong hai trường.
3. **P10-03 (P1):** Thực thi câu lệnh `UPDATE ... WHERE id = :id AND workspace_id = :ws AND version = :exp_ver` ở cấp cơ sở dữ liệu để chống xung đột ghi đè giữa hai phiên đồng thời.
4. **P10-04 (P1):** Loại bỏ logic gắn nhãn `is_trending = true` chỉ dựa vào tổng lượt xem của một snapshot đơn lẻ; tách biệt rõ ràng giữa chỉ số tích lũy và tín hiệu xu hướng thực tế.
5. **P10-05 (P1):** Thêm ràng buộc kiểm tra thời gian quan sát `observed_at <= now()`, từ chối snapshot có mốc thời gian trong tương lai.
6. **P10-06 đến P10-08:** Khắc phục các vấn đề hiển thị trạng thái thiếu dữ liệu (`MISSING`), đồng bộ nhật ký kiểm toán trong cùng transaction, và bổ sung Playwright E2E test cho 8 màn hình.

### 4.2 Khắc Phục Pha P11 (Vòng Phản Hồi Kênh Sở Hữu & Vận Tốc Tăng Trưởng - 9 Phát hiện)
1. **P11-01 (P1):** Xóa bỏ hoàn toàn các giá trị số liệu cố định (`follower_count=45000`, `video_count=86`); khi chưa có quan sát thực tế từ API chính thức hoặc bản nhập khách hàng, bắt buộc trả về `metrics = null` kèm thông điệp minh bạch `METRICS_NOT_YET_OBSERVED`.
2. **P11-02 (P1):** Ngăn chặn người gọi tự khai `oauth_scopes`; chỉ cập nhật trạng thái kết nối từ OAuth grant đã được máy chủ xác thực; kiểm tra cờ hết hạn (`EXPIRED`) và thu hồi quyền (`REVOKED`).
3. **P11-03 (P1):** Giữ nguyên giá trị `null` xuyên suốt các bước tính toán; khi thiếu snapshot đầu vào, vận tốc và tỷ lệ phần trăm phải trả về `NOT_AVAILABLE`; cấm biến `null` thành số 0.
4. **P11-04 (P1):** Áp dụng cơ chế định danh duy nhất (Idempotency Key) cho từng cặp quan sát; ngăn chặn việc tính lại cùng một cặp snapshot làm sai lệch giá trị trung bình của toàn cohort.
5. **P11-05 (P1):** Bảo toàn cờ `is_paid` và `channel_id` khi tiếp nhận dữ liệu qua `IngestionService`; tách bạch tuyệt đối dữ liệu quảng cáo khỏi nhóm tự nhiên.
6. **P11-06 (P1):** Lọc bỏ toàn bộ nguồn có `synthetic = true` hoặc `is_purged = true` trước khi đưa vào động cơ tính toán hiệu suất thực tế.
7. **P11-07 (P1):** Xây dựng đầy đủ các thực thể và API còn thiếu theo đúng hợp đồng: `PublishedContentLink`, `PerformanceSnapshot`, `LearningSignal`, `ExperimentSuggestion`, liên kết chặt chẽ bài đăng thực tế với phiên bản kịch bản `APPROVED`.
8. **P11-08 (P2):** Tính toán vận tốc dựa trên thời gian thực tế; loại bỏ việc áp đặt ngầm `max(delta_days, 0.0001)` gây phóng đại số liệu vận tốc.
9. **P11-09 (P2):** Thực thi bộ lọc cohort thực sự trên tập kết quả trả về, không chỉ gắn nhãn hình thức trên response.

### 4.3 Khắc Phục Pha P12 (An Ninh, Độ Tin Cậy, Ngân Sách & Đánh Giá Staging - 10 Phát Hiện)
1. **P12-01 (P1):** Khóa cache tác vụ theo tổ hợp `workspace_id + idempotency_key`; ngăn chặn tuyệt đối tình trạng trả artifact của khách thuê này cho khách thuê khác.
2. **P12-02 (P1):** Lưu trữ kết quả và trạng thái tác vụ vào cơ sở dữ liệu bền vững; đảm bảo khi tiến trình khởi động lại hoặc mất cache RAM, hệ thống replay an toàn mà không trừ phí hai lần.
3. **P12-03 (P1):** Ràng buộc bản ghi `CostLedger` với chữ ký (fingerprint) bất biến của request; cấm việc tái sử dụng key của tác vụ bị từ chối (`REFUSED_OVER_BUDGET`) để vượt trần ngân sách.
4. **P12-04 (P1):** Triển khai cơ chế giữ chỗ ngân sách nguyên tử (Atomic reservation) với điều kiện số dư; chống xung đột cập nhật (lost update) khi nhiều phiên đồng thời cùng yêu cầu tài nguyên.
5. **P12-05 (P1):** Kiểm thử kịch bản timeout và bounded retry trên tác vụ giả lập có side effect thực tế bền vững; vô hiệu hóa các route giả lập trước khi chuyển sang staging/production.
6. **P12-06 (P1):** Nâng cấp script sao lưu database staging (`backup_staging_db.py`): quét và tẩy sạch triệt để toàn bộ chuỗi token, API key, và thông tin nhạy cảm trong các cột JSON payload, không chỉ thay đổi mật khẩu ở bảng users.
7. **P12-07 (P1):** Sửa đổi script khôi phục database (`restore_staging_db.py`): bắt buộc xác thực manifest được phê duyệt, kiểm tra mã băm SHA256 và chạy kiểm tra tính toàn vẹn (PRAGMA integrity_check) trên bản sao tạm trước khi ghi đè database đích.
8. **P12-08 (P1):** Chạy quy trình đánh giá prompt và mô hình trên held-out dataset thực tế với >= 30 ứng viên mỗi brief; lưu trữ đánh giá độc lập của 2 chuyên gia và xác thực các quy tắc phủ quyết Veto; loại bỏ bảng nhãn hardcoded.
9. **P12-09 (P1):** Nâng cấp công cụ kiểm toán phụ thuộc (`audit_licenses_and_deps.py`): chuẩn hóa danh sách package, quét lockfiles và cơ sở dữ liệu lỗ hổng bảo mật thực tế; đánh dấu `NOT_CHECKED` cho các mục chưa thu thập đủ dữ liệu.
10. **P12-10 (P1):** Khóa chặt Gate P13 trong tài liệu `RELEASE_READINESS.md`; cập nhật trạng thái trung thực là P12 CHƯA ĐẠT cho đến khi toàn bộ 10 phát hiện trên được kiểm định lại.

---

## 5. Quy Trình Phối Hợp & Cam Kết Kỷ Luật "Chưa Code"

### 5.1 Phân Định Trách Nhiệm Giữa Antigravity & Codex
- **Antigravity (Kiến trúc sư & Kiểm định chất lượng):**
  - Chịu trách nhiệm quy hoạch kiến trúc tổng thể, duy trì tài liệu chuẩn mực, cập nhật trạng thái tại `00_bat_dau/CURRENT_STATE.md` và `hanh_trinh_phat_trien_069.html`.
  - Thiết lập tiêu chí nghiệm thu (acceptance criteria) và giám sát việc tuân thủ các quy tắc bất biến.
  - Tổ chức đối soát độc lập, đánh giá chất lượng và khóa checkpoint sau khi các pha vượt qua cổng kiểm tra thực tế.
- **Codex (Chuyên viên thực thi mã nguồn):**
  - Triển khai sửa mã nguồn theo đúng backlog đã được phân rã chi tiết trong `ke_hoach_khac_phuc_va_dieu_chinh_p10_p11_p12.md`.
  - Tuân thủ nguyên tắc Ponytail Minimalist: viết mã ngắn gọn, không kéo thư viện thừa, chú thích bằng Tiếng Việt rõ ràng.
  - Chạy unit test và integration test thực tế tại môi trường local, lưu log và bằng chứng vào `08_kiem_thu/bang_chung/`.

### 5.2 Cam Kết "Chưa Code" (Zero Runtime Modifications)
- Trong phạm vi thực thi lệnh điều phối này, toàn bộ các hoạt động chỉ tập trung vào việc **tiếp nhận, tích hợp, đối soát và điều chỉnh kế hoạch**.
- Tuyệt đối không chỉnh sửa mã nguồn backend (`sin_content_api/src/`), giao diện frontend (`sin_creator_os/src/`), lõi phân quyền (`baha_auth/`), hay cơ sở dữ liệu runtime.
- Mọi hoạt động viết mã khắc phục chỉ được phép bắt đầu sau khi Founder phê duyệt kế hoạch điều chỉnh này và ban hành thẻ điều phối công việc chính thức.
