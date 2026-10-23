# KẾ HOẠCH HÀNH ĐỘNG KHẮC PHỤC KỸ THUẬT PHA P10, P11, P12
## Phân Hệ Trí Tuệ Nội Dung SIN (SIN-CONTENT-INTELLIGENCE-001)

- **Mã kế hoạch:** RE-P10-P11-P12-001
- **Phiên bản:** 1.0.0
- **Ngày lập:** 22/10/2026
- **Trạng thái:** KẾ HOẠCH HÀNH ĐỘNG CHI TIẾT — **CHƯA CODE (NOT_STARTED / PLAN ONLY)**
- **Mục tiêu:** Quy định chính xác vị trí tệp, nguyên nhân gốc rễ, phương án xử lý và tiêu chí kiểm thử cho toàn bộ 27 phát hiện kỹ thuật (P10: 8 phát hiện, P11: 9 phát hiện, P12: 10 phát hiện) được phát hiện trong đợt rà soát độc lập ngày 21/10/2026.
- **Nguyên tắc:** Ground Truth > Self-report. Không nghiệm thu dựa trên test mô phỏng; mọi ca sửa phải có kiểm thử thực tế và log Exit Code 0.

---

## I. DANH MỤC KHẮC PHỤC PHA P10: GIAO DIỆN NGHIÊN CỨU & LUỒNG KIỂM DUYỆT (8 PHÁT HIỆN)

### 1. P10-01 (Mức độ: P1) — Workbench dùng dữ liệu mẫu, thiếu luồng duyệt thực tế qua giao diện
- **Vị trí ảnh hưởng:** 
  - `03_ban_lam_viec/sin_creator_os/src/app/(main)/ideas/page.tsx`
  - `03_ban_lam_viec/sin_creator_os/src/services/idea-service.ts`
  - `03_ban_lam_viec/sin_creator_os/src/services/discover-service.ts`
  - `03_ban_lam_viec/sin_creator_os/src/services/job-service.ts`
- **Nguyên nhân gốc rễ:** Frontend vẫn đọc mảng cứng `mockIdeas` và `mockContentAnalysis`; service lưu trạng thái trong bộ nhớ RAM; kiểu `IdeaStatus` thiếu các trạng thái review của API (`IN_REVIEW`, `CHANGES_REQUESTED`, `APPROVED`, `REJECTED`, `REOPENED`).
- **Phương án khắc phục:**
  1. Kết nối toàn bộ service frontend với REST API backend `/v1/ideation/cards` và `/v1/sources/evidence/{id}` thông qua Axios client có gắn `Bearer Token` và header `X-Workspace-Id`.
  2. Cập nhật `IdeaCardContract` trên frontend phản ánh đầy đủ: `version`, `status`, `review_reason`, `reviewed_by`, `reviewed_at`.
  3. Xây dựng giao diện Modal/Drawer duyệt bài trực quan hỗ trợ 4 thao tác: Duyệt (`APPROVE`), Từ chối (`REJECT`), Yêu cầu chứng cứ (`REQUEST_EVIDENCE`), Mở lại (`REOPEN`).
  4. Hiển thị rõ ràng trạng thái thiếu dữ liệu (`MISSING`), hết hạn (`EXPIRED`) thay vì hiển thị dữ liệu giả định.
- **Tiêu chí nghiệm thu (Exit Criteria):**
  - Người dùng thao tác duyệt trên giao diện tạo đúng bản ghi `AuditEvent` trên backend.
  - Chạy kiểm thử tự động Playwright E2E cho 8 màn hình chính, chụp ảnh bằng chứng lưu tại `08_kiem_thu/bang_chung/`.

### 2. P10-02 (Mức độ: P1) — Bỏ trường expected_version vẫn phê duyệt thành công
- **Vị trí ảnh hưởng:**
  - `03_ban_lam_viec/sin_content_api/src/schemas/contracts.py` (Class `IdeaReviewRequest`)
  - `03_ban_lam_viec/sin_content_api/src/modules/ideation/ideation_service.py`
- **Nguyên nhân gốc rễ:** `expected_version` và `expected_status` được khai báo là `Optional[int] = None`; service chỉ kiểm tra khi client truyền lên, nếu client bỏ qua thì backend tự động bỏ qua kiểm tra phiên bản cũ.
- **Phương án khắc phục:**
  1. Đổi kiểu dữ liệu trong Pydantic schema: `expected_version: int = Field(..., ge=1)` và `expected_status: str = Field(...)` (bắt buộc, không cho phép null/None).
  2. Bổ sung validation decorator ném mã lỗi HTTP 422 `UNPROCESSABLE_ENTITY` ngay tại tầng request parsing nếu thiếu một trong hai trường.
- **Tiêu chí nghiệm thu:**
  - Gửi request thiếu `expected_version` bị từ chối ngay với HTTP 422.
  - Gửi request sai `expected_version` bị từ chối với HTTP 409 `STALE_VERSION_CONFLICT`.

### 3. P10-03 (Mức độ: P1) — Tranh chấp phiên bản giữa hai phiên đồng thời (Race Condition)
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/ideation/ideation_service.py`
- **Nguyên nhân gốc rễ:** Kiểm tra phiên bản bằng câu lệnh `SELECT` Python, sau đó thực thi `UPDATE` ở câu lệnh rời rạc; không khóa bản ghi hoặc không kiểm tra số dòng bị ảnh hưởng tại thời điểm ghi.
- **Phương án khắc phục:**
  1. Triển khai câu lệnh atomic update nguyên tử:
     ```python
     stmt = (
         update(IdeaCard)
         .where(IdeaCard.id == card_id, IdeaCard.workspace_id == workspace_id, IdeaCard.version == expected_version)
         .values(status=new_status, version=expected_version + 1, ...)
     )
     result = db.execute(stmt)
     if result.rowcount == 0:
         raise HTTPException(status_code=409, detail="STALE_VERSION_CONFLICT")
     ```
  2. Thực thi ghi `AuditEvent` trong cùng database transaction với thao tác cập nhật trạng thái thẻ.
- **Tiêu chí nghiệm thu:**
  - Chạy mô phỏng 2 session đồng thời cùng submit review trên version 1: đúng 1 session thành công trả HTTP 200 (version 2), session còn lại lập tức nhận HTTP 409.

### 4. P10-04 (Mức độ: P1) — Gắn nhãn đang thịnh hành chỉ dựa vào tổng lượt xem của 1 snapshot
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/sources/router.py`
- **Nguyên nhân gốc rễ:** Logic gán `is_trending = True` nếu `view_count >= 200_000` từ một quan sát duy nhất, vi phạm nghiêm trọng Nguyên tắc Đơn Ảnh Chụp (Single Snapshot Integrity).
- **Phương án khắc phục:**
  1. Tách bạch hoàn toàn giữa `view_magnitude` (Quy mô lượt xem) và `is_trending` (Tín hiệu xu hướng).
  2. Khi chỉ có 1 snapshot: Bắt buộc trả về `is_trending = None` và `trend_status = "UNVERIFIED_SINGLE_SNAPSHOT"`.
  3. Chỉ tính toán `is_trending = True` khi có tối thiểu 2 snapshots cách nhau và vận tốc tăng trưởng vượt ngưỡng quy định.
- **Tiêu chí nghiệm thu:**
  - 1 snapshot dù có 100 triệu views vẫn trả về `is_trending = null`.
  - Có 2 snapshots chứng minh gia tốc tăng trưởng mới trả về `is_trending = true`.

### 5. P10-05 đến P10-08 (Mức độ: P1 & P2) — Kiểm soát thời gian, nhật ký kiểm toán và hiển thị
- **P10-05 (P1):** Chặn snapshot có `observed_at > now()` với mã lỗi HTTP 422 `OBSERVATION_TIME_IN_FUTURE`.
- **P10-06 (P1):** Đảm bảo ghi nhật ký kiểm toán `AuditEvent` đồng bộ trong cùng transaction, rollback toàn bộ nếu ghi log thất bại.
- **P10-07 (P2):** Giao diện hiển thị nhãn `CHƯA CÓ DỮ LIỆU` rõ ràng, cấm hiển thị số 0 khi thiếu chỉ số.
- **P10-08 (P2):** Hỗ trợ hủy tác vụ nghiên cứu (`CANCEL_RESEARCH_RUN`) an toàn và giải phóng hạn mức ngân sách đã giữ chỗ.

---

## II. DANH MỤC KHẮC PHỤC PHA P11: VÒNG LẶP PHẢN HỒI KÊNH SỞ HỮU (9 PHÁT HIỆN)

### 1. P11-01 (Mức độ: P1) — Trả số liệu cố định dưới nhãn hiệu suất chính thức đã xác thực
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/feedback/channel_service.py`
- **Nguyên nhân gốc rễ:** Hardcode số liệu giả định (`follower_count=45000`, `video_count=86`, `profile_views_7d=12800`) khi kết nối kênh thành công; lấy thời điểm kết nối làm `verified_at`.
- **Phương án khắc phục:**
  1. Xóa bỏ hoàn toàn dictionary số liệu hardcode trong `channel_service.py`.
  2. Khi kết nối kênh mới hoặc chưa có lần quét chỉ số nào từ API chính thức: Trả về `metrics = None`, `metrics_status = "METRICS_NOT_YET_OBSERVED"`, `verified_at = None`.
  3. Chỉ trả về số liệu khi có bản ghi `SourceObservation` thực tế được thu thập qua API chính thức hoặc bản nhập CSV/JSON do khách hàng tải lên.
- **Tiêu chí nghiệm thu:**
  - Kết nối kênh mới -> API trả `metrics = null`.
  - Không còn bất kỳ hằng số 45000 hay 86 nào trong mã nguồn.

### 2. P11-02 (Mức độ: P1) — Người gọi tự khai OAuth scopes & kết nối hết hạn vẫn dùng được
- **Vị trí ảnh hưởng:**
  - `03_ban_lam_viec/sin_content_api/src/schemas/contracts.py` (Class `ChannelConnectRequest`)
  - `03_ban_lam_viec/sin_content_api/src/modules/feedback/channel_service.py`
- **Nguyên nhân gốc rễ:** Client tự gửi mảng `oauth_scopes=["channel:metrics"]` trong body; backend lưu thẳng vào database mà không xác thực với máy chủ OAuth; không kiểm tra trạng thái token hết hạn (`EXPIRED`) hoặc bị thu hồi (`REVOKED`).
- **Phương án khắc phục:**
  1. Loại bỏ trường `oauth_scopes` khỏi `ChannelConnectRequest`. Scope phải được trích xuất từ phản hồi của máy chủ ủy quyền OAuth (TikTok Login Kit) hoặc file chứng chỉ cấu hình nội bộ tin cậy.
  2. Bổ sung trường `token_expires_at` và hàm kiểm tra tính hợp lệ: Nếu `status in ["EXPIRED", "REVOKED"]` hoặc `token_expires_at < now()`, endpoint GET performance lập tức trả về `status = "FEATURE_UNAVAILABLE"`, `metrics = None`.
- **Tiêu chí nghiệm thu:**
  - Kênh có trạng thái `EXPIRED` trong database -> GET performance trả về `FEATURE_UNAVAILABLE` và `metrics = null`.

### 3. P11-03 (Mức độ: P1) — Chỉ số chưa biết bị đổi thành số 0 và tạo vận tốc giả
- **Vị trí ảnh hưởng:**
  - `03_ban_lam_viec/sin_content_api/src/modules/feedback/velocity_engine.py`
  - `03_ban_lam_viec/sin_content_api/src/modules/feedback/cohort_service.py`
- **Nguyên nhân gốc rễ:** Mã nguồn dùng hàm `from_views or 0`, vô tình chuyển đổi `None` thành `0`, dẫn đến việc tính toán ra mức tăng trưởng giả tạo.
- **Phương án khắc phục:**
  1. Kiểm tra đầu vào nghiêm ngặt: Nếu `from_views is None` hoặc `to_views is None`:
     - Trả về `delta_views = None`, `velocity_views_per_day = None`, `growth_rate = None`.
     - Đặt `rate_status = "NOT_AVAILABLE"`, `missing_reason = "INSUFFICIENT_METRIC_SNAPSHOTS"`.
  2. Trong `cohort_service.py`: Tính `coverage_rate = observed_posts / total_posts`. Chỉ tính trung bình trên các bài có dữ liệu hợp lệ; nếu toàn bộ bài đều thiếu lượt xem thì trả về `average_velocity = None`.
- **Tiêu chí nghiệm thu:**
  - Tính vận tốc với snapshot có lượt xem null -> trả về `velocity = null`, không sinh số liệu giả.

### 4. P11-04 (Mức độ: P1) — Tính lại cùng cặp snapshot làm lệch trung bình hiệu suất
- **Vị trí ảnh hưởng:**
  - `03_ban_lam_viec/sin_content_api/src/modules/feedback/velocity_engine.py`
  - `03_ban_lam_viec/sin_content_api/src/models/entities.py` (`TrendVelocityObservation`)
- **Nguyên nhân gốc rễ:** Mỗi lần gọi API tính toán, backend luôn `INSERT` một bản ghi mới vào bảng `trend_velocity_observations`. Khi tính trung bình cohort, query lấy trung bình trên toàn bộ bảng, khiến số lần gọi API trở thành trọng số thống kê sai lệch.
- **Phương án khắc phục:**
  1. Thêm chỉ mục độc nhất (Unique Constraint) trên bảng `trend_velocity_observations`:
     `UniqueConstraint('workspace_id', 'from_observation_id', 'to_observation_id', 'metric_name', name='uq_velocity_pair')`.
  2. Áp dụng cơ chế Upsert lũy đẳng: Nếu cặp quan sát đã tồn tại thì trả về kết quả cũ, không tạo bản ghi trùng lặp.
  3. Cohort query chỉ chọn quan sát mới nhất trong cùng một cửa sổ phân tích cho mỗi bài viết.
- **Tiêu chí nghiệm thu:**
  - Gọi lặp lại 10 lần cùng một phép tính -> số lượng bản ghi trong database không đổi, giá trị trung bình cohort không bị lệch.

### 5. P11-05 (Mức độ: P1) — Mất thông tin quảng cáo (is_paid) khi tiếp nhận dữ liệu
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/ingestion/service.py`
- **Nguyên nhân gốc rễ:** Hàm tiếp nhận dữ liệu `IngestionService.normalize_and_save` không trích xuất và lưu trữ trường `is_paid` và `channel_id` từ payload vào thực thể `SourceRecord`.
- **Phương án khắc phục:**
  1. Bổ sung trích xuất trường `is_paid = raw_item.get("is_paid", False)` và `channel_id = raw_item.get("channel_id")` trong mapper của IngestionService.
  2. Ràng buộc kiểm tra tính toàn vẹn: Bài viết có `is_paid = True` bắt buộc phải có thông tin chiến dịch hoặc chứng từ phân loại trả phí.
- **Tiêu chí nghiệm thu:**
  - Tiếp nhận bài viết có `is_paid=True` -> `SourceRecord.is_paid` trong database lưu đúng `True` và được tính vào `PAID_COHORT`.

### 6. P11-06 (Mức độ: P1) — Nguồn dữ liệu synthetic hoặc đã purge lọt vào phản hồi hiệu suất
- **Vị trí ảnh hưởng:**
  - `03_ban_lam_viec/sin_content_api/src/modules/feedback/velocity_engine.py`
  - `03_ban_lam_viec/sin_content_api/src/modules/feedback/cohort_service.py`
- **Nguyên nhân gốc rễ:** Các câu lệnh truy vấn SQL không có mệnh đề lọc `WHERE is_purged == False AND is_synthetic == False`.
- **Phương án khắc phục:**
  1. Thêm bộ lọc an toàn bắt buộc vào tất cả truy vấn:
     `query = query.join(SourceRecord).filter(SourceRecord.is_purged == False, SourceRecord.is_synthetic == False)`.
  2. Thêm cờ kiểm tra môi trường: Cấm tuyệt đối chạy phân tích trên dữ liệu mẫu khi môi trường không phải `TESTING`.
- **Tiêu chí nghiệm thu:**
  - Nguồn có `is_purged=True` hoặc `synthetic=True` bị loại bỏ 100% khỏi các báo cáo phản hồi hiệu suất.

### 7. P11-07 (Mức độ: P1) — Thiếu luồng và thực thể nối bài đã đăng với bản kịch bản đã duyệt
- **Vị trí ảnh hưởng:**
  - `03_ban_lam_viec/sin_content_api/src/models/entities.py`
  - `03_ban_lam_viec/sin_content_api/src/modules/feedback/`
- **Nguyên nhân gốc rễ:** Chưa khai báo thực thể ORM và router cho các đối tượng theo chuẩn hợp đồng: `PublishedContentLink`, `PerformanceSnapshot`, `LearningSignal`, `ExperimentSuggestion`.
- **Phương án khắc phục:**
  1. Bổ sung các bảng ORM và Pydantic DTOs chuẩn mực:
     - `PublishedContentLink`: `id`, `workspace_id`, `script_draft_id`, `script_version`, `published_url`, `platform_post_id`, `published_at`, `status`.
     - `LearningSignal`: `id`, `workspace_id`, `published_link_id`, `signal_type`, `insight_text`, `evidence_data_json`.
     - `ExperimentSuggestion`: `id`, `workspace_id`, `based_on_signal_id`, `hypothesis`, `suggested_action`.
  2. Cung cấp các endpoints chuẩn REST:
     - `POST /v1/feedback/published-links` (Nối bài đăng với kịch bản APPROVED)
     - `GET /v1/feedback/learning-signals` (Trích xuất bài học tối ưu hóa)
     - `DELETE /v1/feedback/published-links/{id}` (Tháo gỡ liên kết theo chính sách bảo mật).
- **Tiêu chí nghiệm thu:**
  - Nối thành công 1 URL video TikTok với kịch bản version 2 APPROVED, lưu trữ đầy đủ trong database và truy xuất được lịch sử.

### 8. P11-08 & P11-09 (Mức độ: P2) — Chuẩn hóa khoảng thời gian và thực thi bộ lọc Cohort
- **P11-08 (P2):** Tính toán vận tốc dựa trên số giây thực tế `delta_seconds / 86400.0`. Nếu `delta_seconds < 3600` (dưới 1 giờ): Từ chối tính toán với mã lỗi `WINDOW_TOO_SHORT_FOR_VELOCITY` thay vì ép ngầm `0.0001`.
- **P11-09 (P2):** Thực thi lọc kết quả theo tham số `?cohort=ORGANIC`: Khi có tham số, response chỉ trả về mảng dữ liệu của nhóm được yêu cầu; loại bỏ hoàn toàn nhóm bị lọc khỏi kết quả.

---

## III. DANH MỤC KHẮC PHỤC PHA P12: AN NINH, ĐỘ TIN CẬY & ĐÁNH GIÁ STAGING (10 PHÁT HIỆN P1)

### 1. P12-01 (Mức độ: P1) — Cache tác vụ trả artifact của workspace khác (Rò rỉ đa khách thuê)
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/downstream_executor.py`
- **Nguyên nhân gốc rễ:** Cache chỉ định danh theo `idempotency_key`, không kiểm tra `workspace_id`.
- **Phương án khắc phục:**
  1. Cấu trúc lại khóa cache: `cache_key = f"{workspace_id}:{idempotency_key}"`.
  2. Trước khi trả kết quả từ cache: Kiểm tra xác minh quyền sở hữu `artifact.workspace_id == current_user.workspace_id`. Nếu không khớp, lập tức ném HTTP 403 `FORBIDDEN_CROSS_TENANT_ACCESS`.
- **Tiêu chí nghiệm thu:**
  - Tenant B gửi cùng khóa idempotency của Tenant A -> Tenant B bị từ chối hoặc nhận cache độc lập, không thấy artifact của Tenant A.

### 2. P12-02 (Mức độ: P1) — Mất cache RAM khiến tác vụ đã hoàn thành bị trừ phí và tạo lại
- **Vị trí ảnh hưởng:**
  - `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/downstream_executor.py`
  - `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/budget_guard.py`
- **Nguyên nhân gốc rễ:** Khi khởi động lại tiến trình, cache RAM bị xóa, trong khi bảng `CostLedger` vẫn lưu trạng thái `COMMITTED`. Executor không đọc lại DB để tái dựng kết quả mà thực thi lại tác vụ và gọi hàm cộng trừ ngân sách lần hai.
- **Phương án khắc phục:**
  1. Đưa `CostLedger` và `ArtifactStore` vào database làm nguồn chân lý duy nhất (SSOT). Cache RAM chỉ đóng vai trò thứ cấp.
  2. Khi nhận request: Kiểm tra `CostLedger` trong DB trước; nếu trạng thái là `COMMITTED`, trả về ngay kết quả đã lưu kèm `charged_units = 0.0`, không thực thi lại downstream job.
- **Tiêu chí nghiệm thu:**
  - Khởi động lại ứng dụng, gửi lại request cũ -> không phát sinh chi phí lần 2, không sinh artifact mới.

### 3. P12-03 (Mức độ: P1) — Tái sử dụng key của tác vụ bị từ chối (REFUSED) để vượt trần ngân sách
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/budget_guard.py`
- **Nguyên nhân gốc rễ:** Logic kiểm tra chỉ phát hiện bản ghi cũ là `IDEMPOTENT_HIT` mà không phân biệt trạng thái `REFUSED_OVER_BUDGET`.
- **Phương án khắc phục:**
  1. Nếu bản ghi cũ có trạng thái `REFUSED_OVER_BUDGET`: Không cho phép bypass; bắt buộc thực hiện kiểm tra ngân sách mới tại thời điểm hiện tại.
  2. Băm chữ ký payload (`payload_fingerprint = sha256(payload)`): Nếu cùng key nhưng đổi payload (ví dụ tăng từ 0.1 lên 10 units), từ chối ngay với HTTP 400 `PAYLOAD_MISMATCH_FOR_IDEMPOTENT_KEY`.
- **Tiêu chí nghiệm thu:**
  - Gọi lại key bị từ chối -> tiếp tục bị từ chối nếu ngân sách chưa được nạp thêm.

### 4. P12-04 (Mức độ: P1) — Giữ chỗ ngân sách đồng thời làm mất dữ liệu (Lost Update)
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/budget_guard.py`
- **Nguyên nhân gốc rễ:** Thực hiện `budget.reserved_units += amount` trên object ORM trong Python memory, dẫn đến ghi đè khi nhiều luồng cùng commit.
- **Phương án khắc phục:**
  1. Sử dụng câu lệnh cập nhật nguyên tử có điều kiện ở tầng database:
     ```python
     stmt = (
         update(WorkspaceBudget)
         .where(
             WorkspaceBudget.workspace_id == workspace_id,
             (WorkspaceBudget.allocated_units - WorkspaceBudget.reserved_units - WorkspaceBudget.spent_units) >= amount
         )
         .values(reserved_units=WorkspaceBudget.reserved_units + amount)
     )
     ```
  2. Nếu không có dòng nào được cập nhật (`rowcount == 0`), ném ngay HTTP 402 `REFUSED_OVER_BUDGET`.
- **Tiêu chí nghiệm thu:**
  - 2 phiên đồng thời cùng giữ chỗ vượt hạn mức -> chỉ duy nhất 1 phiên thành công, 1 phiên nhận 402.

### 5. P12-05 (Mức độ: P1) — Bài thử timeout chưa thực thi công việc thực tế
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/downstream_executor.py`
- **Nguyên nhân gốc rễ:** Vòng lặp tự giả lập `raise TimeoutError` trong RAM rồi trả UUID ngẫu nhiên mà không có downstream pipeline thật.
- **Phương án khắc phục:**
  1. Kết nối executor với worker queue abstraction (`sin_content_workers`).
  2. Xây dựng mock downstream service có tác động ghi cơ sở dữ liệu bền vững (ghi nhận task pending -> timeout -> retry -> hoàn tất).
  3. Đảm bảo vô hiệu hóa router thử nghiệm staging trên môi trường Production bằng biến môi trường `ENVIRONMENT != "production"`.
- **Tiêu chí nghiệm thu:**
  - Test case mô phỏng timeout sau khi tác vụ đã tạo side-effect bền vững, chứng minh retry không tạo duplicate artifact.

### 6. P12-06 (Mức độ: P1) — Backup chỉ đổi mật khẩu 1 cột, để lọt secret trong JSON payload
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/scripts/backup_staging_db.py`
- **Nguyên nhân gốc rễ:** Script chỉ chạy câu lệnh `UPDATE users SET hashed_password = ...`, bỏ quên các trường token trong `source_observations.raw_payload_json` và `owned_channels.oauth_tokens`.
- **Phương án khắc phục:**
  1. Viết bộ lọc đệ quy quét toàn bộ các trường JSON trong database: Tìm và thay thế các chuỗi regex khớp với pattern `access_token`, `refresh_token`, `api_key`, `secret`, `password` bằng giá trị `[SCRUBBED_IN_BACKUP]`.
  2. Chạy bài kiểm tra tự động quét secret (T012 scanner) trên chính file SQLite backup vừa sinh ra; nếu còn sót token, lập tức hủy bản backup và trả exit code 1.
- **Tiêu chí nghiệm thu:**
  - File backup sau khi sinh ra vượt qua 100% bài kiểm tra T012 secrets scanner.

### 7. P12-07 (Mức độ: P1) — Restore xóa database đích trước khi kiểm tra tính hợp lệ của bản backup
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/scripts/restore_staging_db.py`
- **Nguyên nhân gốc rễ:** Script xóa file database đích trước khi chạy lệnh `PRAGMA integrity_check` trên file backup.
- **Phương án khắc phục:**
  1. Quy trình khôi phục 4 bước an toàn:
     - Bước 1: Xác thực chữ ký SHA256 của file backup đối chiếu với `backup_manifest.json`.
     - Bước 2: Mở file backup ở chế độ Read-Only và chạy `PRAGMA integrity_check;`. Nếu lỗi, dừng ngay lập tức.
     - Bước 3: Sao lưu tạm database đích hiện tại sang file dự phòng `.target.bak`.
     - Bước 4: Thực hiện hoán đổi file nguyên tử (Atomic file replace). Nếu gặp sự cố, tự động rollback từ `.target.bak`.
- **Tiêu chí nghiệm thu:**
  - Cung cấp file backup hỏng -> script từ chối và bảo toàn 100% database đích nguyên vẹn.

### 8. P12-08 (Mức độ: P1) — Đánh giá prompt tự đếm nhãn hardcode, không đo đạc thực tế
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/prompt_regression.py`
- **Nguyên nhân gốc rễ:** Bảng nhãn `RELEVANT`, `has_evidence` được viết cứng trong code Python thay vì chạy qua mô hình và tập dữ liệu vàng.
- **Phương án khắc phục:**
  1. Xóa bỏ cấu trúc nhãn tĩnh trong `prompt_regression.py`.
  2. Tích hợp chạy trực tiếp qua bộ dữ liệu vàng `evals/gold_sets/` (gồm 3 briefs độc lập, mỗi brief >= 30 mẫu ứng viên đã qua 2 chuyên gia đánh giá và biên bản phán quyết bất đồng).
  3. Chạy pipeline truy xuất và chấm điểm thực tế, tính toán Precision@10 động dựa trên kết quả đầu ra thực của thuật toán.
- **Tiêu chí nghiệm thu:**
  - Thay đổi prompt hoặc tiêu chí tìm kiếm -> điểm số Precision@10 thay đổi tương ứng theo chất lượng thực tế.

### 9. P12-09 (Mức độ: P1) — Kiểm toán phụ thuộc trả 0 vi phạm ảo
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/scripts/audit_licenses_and_deps.py`
- **Nguyên nhân gốc rễ:** Script chỉ so khớp chuỗi thô với 3 cái tên, không phân tích extras, không đọc lockfiles, và tự đặt các biến đếm lỗi bằng 0.
- **Phương án khắc phục:**
  1. Sử dụng thư viện chuẩn như `pip-licenses` hoặc quét qua `pip freeze` và `package-lock.json`.
  2. Chuẩn hóa tên gói phần mềm (loại bỏ extras như `[extra]`, chữ hoa/thường).
  3. Đối với các mục chưa có cơ sở dữ liệu quét lỗ hổng offline: Bắt buộc ghi nhận trạng thái `NOT_CHECKED`, tuyệt đối không ghi nhận `PASS` hoặc `0 vi phạm`.
- **Tiêu chí nghiệm thu:**
  - Khai báo gói cấm `MediaCrawler` kèm extra -> script phát hiện và trả kết quả FAIL kèm mã lỗi vi phạm.

### 10. P12-10 (Mức độ: P1) — Hồ sơ phát hành mở Gate P13 khi chưa đạt Gate P12
- **Vị trí ảnh hưởng:** `03_ban_lam_viec/sin_content_api/docs/RELEASE_READINESS.md`
- **Nguyên nhân gốc rễ:** Báo cáo ghi nhận sẵn sàng chuyển sang Canary P13 trong khi còn 10 phát hiện P1 mở.
- **Phương án khắc phục:**
  1. Cập nhật `RELEASE_READINESS.md`: Đặt trạng thái toàn hệ thống là `STAGING_VERIFICATION_IN_PROGRESS (BLOCKED FOR PRODUCTION)`.
  2. Ghi rõ điều kiện tiên quyết: Chỉ mở Gate P13 khi toàn bộ 27 phát hiện của P10, P11, P12 được sửa chữa và vượt qua kiểm định độc lập.
- **Tiêu chí nghiệm thu:**
  - `RELEASE_READINESS.md` thể hiện trung thực trạng thái dự án, khóa chặt việc triển khai Production.

---

## IV. LỘ TRÌNH 5 BƯỚC TRIỂN KHAI VÀ THỨ TỰ ƯU TIÊN (ĐÃ QUA RÀ SOÁT ĐỘC LẬP)

Sau khi rà soát độc lập (Báo cáo AUDIT-PLAN-CI-2026-10-22), thứ tự triển khai được điều chỉnh chuẩn xác theo nguyên tắc "Từ Trong Ra Ngoài" (Inside-Out) và bổ sung Bước 0 hiện đại hóa test harness:

```
[BƯỚC 0: CHUẨN HÓA TEST HARNESS & AUTH FIXTURES (P00-RE)]
  --> Cập nhật conftest.py: Cung cấp fixture Bearer JWT token hợp lệ do baha_auth ký
  --> Khắc phục test_tenancy (P01), test_briefs (P02), test_sources (P03) bị chặn 401
  --> Sửa lỗi setup fixture test_scripts (P09); bảo đảm toàn bộ Baseline P01-P09 xanh 100%
       |
       v
[BƯỚC 1: ĐỒNG BỘ CSDL, ORM & HỢP ĐỒNG BACKEND (DATA LAYER)]
  --> entities.py: Bổ sung PublishedContentLink, LearningSignal, ExperimentSuggestion
  --> entities.py: Bổ sung trường is_paid, channel_id vào SourceRecord; bảo toàn khi Ingestion
  --> entities.py: Bổ sung WorkspaceBudget, CostLedger, UniqueConstraint chống duplicate
  --> contracts.py: Bắt buộc expected_version/expected_status trong IdeaReviewRequest (P10)
  --> contracts/index.ts: Đồng bộ 100% sang hợp đồng TypeScript Frontend BAHA Creator Studio
       |
       v
[BƯỚC 2: SỬA TOÀN BỘ LOGIC BACKEND & GUARDS (SERVICE LAYER)]
  --> P10 Backend: Atomic review update chống race condition; tách trending khỏi single snapshot
  --> P11 Backend: Xóa mock 45k/86; chuẩn hóa OAuth status; giữ null khi thiếu data; lọc synthetic/purged
  --> P12 Backend: Cache key {workspace_id}:{key}; atomic budget reservation; backup scrubbing đệ quy
  --> Chạy test suites Pytest cho P10, P11, P12 -> Đạt 100% PASS
       |
       v
[BƯỚC 3: TÍCH HỢP GIAO DIỆN FRONTEND WORKBENCH (UI LAYER - P10)]
  --> Nối 8 màn hình chính với API backend thực tế (loại bỏ mockIdeas, mockContentAnalysis)
  --> Xây dựng UI Modal Review duyệt bài 4 thao tác (Approve / Reject / Request Evidence / Reopen)
  --> Hiển thị trung thực trạng thái thiếu dữ liệu (MISSING / EXPIRED)
  --> Chạy Playwright E2E tự động cho 8 màn hình và chụp ảnh bằng chứng nghiệm thu
       |
       v
[BƯỚC 4: ĐÁNH GIÁ TỔNG THỂ STAGING & NGHIỆM THU GATE P13 (AUDIT & HANDOFF)]
  --> Đánh giá Prompt trên Gold Sets >= 30 mẫu x 3 briefs với 2 chuyên gia độc lập
  --> Quét T012 Secrets Scanner trên 100% tệp trong 03_ban_lam_viec
  --> Kiểm toán giấy phép dependencies (T125)
  --> Lập biên bản nghiệm thu tổng thể trình Founder ký duyệt trước khi mở Canary P13
```

---

## V. CAM KẾT HIỆN TẠI: CHƯA CODE

Tài liệu này hoàn toàn mang tính chất kế hoạch hành động và đặc tả kỹ thuật. Toàn bộ mã nguồn hệ thống hiện tại được giữ nguyên vẹn 100% để bảo toàn trạng thái ổn định cho đến khi có lệnh thi công chính thức.
