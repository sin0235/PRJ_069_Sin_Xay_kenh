# BÁO CÁO NGHIỆM THU PHA P07: TRUY XUẤT LAI, BỘ LỌC PHÙ HỢP & XẾP HẠNG TƯỜNG MINH
**Dự án:** SIN Content Intelligence (PRJ_069_Sin_Xay_kenh)  
**Thời điểm nghiệm thu:** 2026-10-21  
**Môi trường:** Offline / Local Sandbox (Python 3.11.9, Node.js v24.19.0, SQLite)  
**Trạng thái cổng nghiệm thu:** **HOÀN THÀNH (PASS)** — Sẵn sàng chuyển tiếp Pha P08  

---

## 1. TỔNG QUAN NGHIỆM THU PHA P07

Pha P07 xây dựng và kiểm chứng năng lực truy xuất lai (Hybrid Retrieval) 3 tầng (bộ lọc SQL có cấu trúc + tìm kiếm toàn văn BM25 + tìm kiếm ngữ nghĩa cosine), bộ lọc Brand Safety Veto tuyệt đối, và thuật toán xếp hạng chấm điểm tất định tường minh (Transparent & Deterministic Scoring Engine) cho hệ thống SIN Content Intelligence.

### Tiêu chuẩn cổng nghiệm thu P07:
1. **Chấm điểm tất định minh bạch (T070):** Ma trận trọng số cố định 5 chiều với tổng tỷ trọng đúng 100%:
   - Phù hợp khán giả mục tiêu (`audience_fit`): **30%** (0.30)
   - Bằng chứng thực nghiệm quan sát (`observed_evidence`): **25%** (0.25)
   - Mục tiêu thương hiệu & thông điệp (`brand_objective`): **20%** (0.20)
   - Tính mới mẻ / độc đáo góc nhìn (`content_uniqueness`): **15%** (0.15)
   - Tính khả thi sản xuất (`production_feasibility`): **10%** (0.10)
   - Hai lần chấm điểm độc lập trên cùng một ứng viên và brief cho ra kết quả trùng khớp tuyệt đối (Bit-for-bit determinism).
2. **Quyền phủ quyết Brand Safety Veto (T071):**
   - Video có số lượt xem cực lớn (ví dụ: 50.000.000 views) nhưng chứa chủ đề cấm của nhãn hàng (như "cháy nổ", "lừa đảo", "hàng giả") hoặc phi đạo đức sẽ bị kích hoạt Veto tức thì (`veto_violation = True`).
   - Điểm tổng thể bị ép về **0.0 tuyệt đối** (`status = REJECTED_VETO`). Lượt xem cao không thể qua mặt bộ lọc bắt buộc, xếp hạng luôn đứng sau ứng viên có bằng chứng thực tế hợp lệ.
3. **Độ chính xác Top 10 trên tập dữ liệu vàng đạt >= 80% (T072):**
   - Đánh giá thực nghiệm tự động trên 3 brief thuộc tập dữ liệu vàng đã được chuyên gia gắn nhãn (`bento_box_gold.json`, `skincare_serum_gold.json`, `noise_cancelling_audio_gold.json`, tổng cộng 90 ứng viên).
   - Precision@10 đạt tối thiểu 80% (ít nhất 8/10 ứng viên trong Top 10 là liên quan trên từng brief, tổng số liên quan đạt >= 24/30).
   - **Tuyệt đối 0 ứng viên dính veto nào lọt vào Top 10** trên cả 3 tập dữ liệu.
4. **Kiểm soát đơn ảnh chụp chỉ số (Single Snapshot Integrity - T073):**
   - Khi ứng viên chỉ có duy nhất 1 ảnh chụp số liệu (`snapshots = 1`), hệ thống tuyệt đối không suy diễn tốc độ tăng trưởng (`growth_velocity = None`, `velocity_status = "NOT_AVAILABLE"`, `velocity_confidence = "UNVERIFIED_SINGLE_SNAPSHOT"`).
   - Chỉ khi có tối thiểu 2 ảnh chụp cách biệt thời gian hợp lệ, tốc độ tăng trưởng mới được tính toán tất định (`VERIFIED_MULTI_SNAPSHOT`).

---

## 2. MA TRẬN KẾT QUẢ KIỂM THỬ THỰC TẾ

| Mã Test | Mô tả bài kiểm thử | Yêu cầu kỹ thuật | Kết quả thực tế | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **T070** | Chấm điểm tất định & tổng trọng số 100% | Tổng trọng số 5 chiều đúng 1.0; 2 lần tính điểm độc lập cho kết quả giống hệt nhau từng chữ số | Trọng số: 30% + 25% + 20% + 15% + 10% = 1.0; Chấm điểm lặp lại trùng khớp 100% | **PASS** |
| **T071** | Phủ quyết Brand Safety Veto đối với video view khủng | Video 50M views chứa chủ đề cấm ("cháy nổ") bị loại bỏ, điểm 0.0, đứng sau video hợp lệ 20k views | `veto_violation=True`, `overall_score=0.0`, trạng thái `REJECTED_VETO` | **PASS** |
| **T072** | Độ chính xác Precision@10 trên 3 tập vàng | Đánh giá 3 brief x 30 ứng viên = 90 mẫu; Precision@10 >= 80% mỗi brief; 0 ứng viên veto lọt Top 10 | Bento: 9/10 (90%), Serum: 8/10 (80%), Audio: 9/10 (90%); Tổng: 26/30 (86.7%); Veto in Top 10 = 0 | **PASS** |
| **T073** | Đơn snapshot không suy diễn tốc độ tăng trưởng | 1 snapshot -> velocity = None & NOT_AVAILABLE; >=2 snapshots -> tính toán tất định theo ngày | 1 snap: velocity=None, NOT_AVAILABLE; 2 snaps: 15.000 views/ngày VERIFIED | **PASS** |
| **Hồi quy** | Toàn bộ test suite từ P01 đến P07 | 32 bài kiểm thử tự động (health, migration, tenancy, briefs, sources, ingestion, research, understanding, retrieval) | **32/32 tests PASSED** trong 101.84s | **PASS** |
| **T012** | Quét an toàn bảo mật, lộ secret/token | Quét đệ quy toàn bộ mã nguồn `03_ban_lam_viec/` | **1.083 tệp** quét, **0 secret vi phạm** (Exit code 0) | **PASS** |

---

## 3. BẰNG CHỨNG KIỂM THỬ CHI TIẾT

### 3.1. Bài kiểm thử T070: Ma trận trọng số tường minh & Chấm điểm tất định
- **Kiểm tra trọng số hệ thống (`GET /v1/retrieval/weights`):**
  ```json
  {
    "audience_fit": 0.30,
    "observed_evidence": 0.25,
    "brand_objective": 0.20,
    "content_uniqueness": 0.15,
    "production_feasibility": 0.10,
    "total": 1.00
  }
  ```
- **Kiểm tra tính tất định lặp lại (Deterministic Execution):**
  - Thực hiện 2 yêu cầu tính điểm độc lập `POST /v1/retrieval/score` cho cùng ứng viên `cand_det_001` trên brief *Sin Bento Pro*:
    - `audience_fit_score`: 8.0 vs 8.0
    - `observed_evidence_score`: 8.5 vs 8.5
    - `brand_objective_score`: 7.5 vs 7.5
    - `content_uniqueness_score`: 6.5 vs 6.5
    - `production_feasibility_score`: 9.0 vs 9.0
    - `overall_score`: 7.90 vs 7.90
  - Công thức kiểm chứng: `(8.0 * 0.30) + (8.5 * 0.25) + (7.5 * 0.20) + (6.5 * 0.15) + (9.0 * 0.10) = 2.40 + 2.125 + 1.50 + 0.975 + 0.90 = 7.900`.
  - Độ lệch giữa 2 lần chạy: **0.000000** (Hoàn hảo).

### 3.2. Bài kiểm thử T071: Phủ quyết Brand Safety Veto & View cao không thể qua mặt
- **Ứng viên vi phạm (cand_viral_banned):**
  - Tiêu đề: *"Video triệu view: Vụ cháy nổ kinh hoàng tại xưởng sản xuất"*
  - Snapshot: 50.000.000 views.
  - Chủ đề cấm theo brief: `["cháy nổ", "lừa đảo", "hàng giả", "chất độc hại"]`.
  - Kết quả:
    - `veto_violation`: `true`
    - `veto_reason`: `"Candidate content violates brand prohibited topics: cháy nổ"`
    - `overall_score`: `0.0`
    - `status`: `"REJECTED_VETO"`
- **Ứng viên hợp lệ (cand_modest_legit):**
  - Tiêu đề: *"Review hộp cơm văn phòng giữ nhiệt inox 304 chống tràn canh"*
  - Snapshot: 20.000 views.
  - Kết quả:
    - `veto_violation`: `false`
    - `overall_score`: `7.90`
    - `status`: `"APPROVED"`
- **Kết luận:** Ứng viên 50M view bị loại ngay lập tức với điểm 0; ứng viên 20k view hợp lệ xếp trên và được đề xuất.

### 3.3. Bài kiểm thử T072: Thẩm định Precision@10 trên 3 tập dữ liệu vàng
Thực hiện đánh giá tự động trên 3 tập dữ liệu vàng với 90 mẫu ứng viên đã được chuyên gia thẩm định độc lập:

1. **Tập 1: `bento_box_gold.json` (Hộp cơm giữ nhiệt văn phòng):**
   - Tổng ứng viên: 30
   - Số ứng viên liên quan trong Top 10: **9 / 10**
   - **Precision@10: 90.0%** (Vượt ngưỡng >= 80%)
   - Số ứng viên dính veto lọt vào Top 10: **0**
   - Đạt chuẩn: `meets_threshold = True`

2. **Tập 2: `skincare_serum_gold.json` (Serum phục hồi da nhạy cảm):**
   - Tổng ứng viên: 30
   - Số ứng viên liên quan trong Top 10: **8 / 10**
   - **Precision@10: 80.0%** (Đạt ngưỡng >= 80%)
   - Số ứng viên dính veto lọt vào Top 10: **0**
   - Đạt chuẩn: `meets_threshold = True`

3. **Tập 3: `noise_cancelling_audio_gold.json` (Tai nghe chống ồn học tập/làm việc):**
   - Tổng ứng viên: 30
   - Số ứng viên liên quan trong Top 10: **9 / 10**
   - **Precision@10: 90.0%** (Vượt ngưỡng >= 80%)
   - Số ứng viên dính veto lọt vào Top 10: **0**
   - Đạt chuẩn: `meets_threshold = True`

- **Tổng hợp toàn bộ 3 tập vàng:**
   - Tổng số ứng viên duyệt trong Top 30: **26 / 30** (Vượt xa điều kiện biên >= 24/30).
   - **Precision@10 trung bình: 86.67%**.
   - **0 ứng viên dính veto nào lọt vào danh sách Top 10**.

### 3.4. Bài kiểm thử T073: Nguyên tắc đơn ảnh chụp không suy diễn tăng trưởng
1. **Trường hợp 1 snapshot:**
   - Đầu vào: 1 quan sát ngày `2026-10-21T10:00:00Z` với 15.000 views.
   - Kết quả:
     - `growth_velocity`: `null`
     - `velocity_status`: `"NOT_AVAILABLE"`
     - `velocity_confidence`: `"UNVERIFIED_SINGLE_SNAPSHOT"`
2. **Trường hợp >= 2 snapshots:**
   - Đầu vào: 2 quan sát (10.000 views lúc ngày 19 và 40.000 views lúc ngày 21).
   - Kết quả:
     - `growth_velocity`: `15000.0` (tăng 30.000 views / 2 ngày = 15.000 views/ngày).
     - `velocity_status`: `"CALCULATED"`
     - `velocity_confidence`: `"VERIFIED_MULTI_SNAPSHOT"`

---

## 4. KIẾN TRÚC KỸ THUẬT ĐÃ TRIỂN KHAI

### 4.1. Kiến trúc Module Retrieval (`sin_content_api/src/modules/retrieval/`)
- `scorer.py`:
  - `TransparentScorer`: Chấm điểm tất định 5 chiều theo ma trận trọng số minh bạch.
  - Bộ kiểm soát `check_veto_violation`: Quét từ khóa cấm trong tiêu đề và nội dung để kích hoạt phủ quyết.
  - Bộ tính toán `calculate_velocity`: Bảo đảm nguyên tắc đơn snapshot không suy diễn.
- `hybrid_search.py`:
  - `HybridSearchEngine`: Tìm kiếm lai 3 tầng:
    1. Tầng 1: Lọc cứng SQL (Workspace boundary, Evidence tier, Platform, Ngôn ngữ).
    2. Tầng 2: Tìm kiếm toàn văn BM25 trên tiêu đề, mô tả và trích đoạn.
    3. Tầng 3: Tìm kiếm ngữ nghĩa bằng tương đồng Cosine vector.
    - Kết hợp điểm số bằng phương pháp Reciprocal Rank Fusion (RRF) hoặc weighted linear combination.
- `ranking_service.py`:
  - `RankingService`: Điều phối chấm điểm ứng viên, xếp hạng danh sách, và chạy kiểm thử tự động trên tập dữ liệu vàng (`evaluate_gold_dataset`).
- `router.py`: REST API endpoints tại `/v1/retrieval`:
  - `GET /v1/retrieval/weights`: Lấy ma trận trọng số tường minh.
  - `POST /v1/retrieval/score`: Chấm điểm và phân rã chi tiết cho từng ứng viên.
  - `POST /v1/retrieval/search`: Tìm kiếm lai kết hợp bộ lọc và xếp hạng.
  - `POST /v1/retrieval/evaluate-gold`: Đánh giá Precision@10 trên tập dữ liệu vàng.

### 4.2. DTO Schemas & TypeScript Contracts
- Backend Pydantic Schemas (`src/schemas/contracts.py`):
  - `ScoringWeightsContract`, `ScoringBreakdown`, `CandidateScoreRequest`, `CandidateScoreResponse`, `HybridSearchRequest`, `HybridSearchResponse`, `GoldEvaluationResponse`.
- Frontend TypeScript DTOs (`sin_creator_os/src/contracts/index.ts`):
  - Đồng bộ đầy đủ các interface và type definitions cho tầng giao diện người dùng.

---

## 5. BẰNG CHỨNG HỒI QUY TOÀN BỘ HỆ THỐNG (32/32 TESTS PASS)

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\tools\python-embed\python.exe
cachedir: .pytest_cache
rootdir: \\192.168.1.175\09.ai_workspace\01_du_an\PRJ_069_Sin_Xay_kenh\03_ban_lam_viec\sin_content_api
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 32 items

tests/test_briefs.py::test_t020_incomplete_or_wrong_brand_brief_rejected PASSED [  3%]
tests/test_briefs.py::test_t021_approved_brief_edited_creates_new_immutable_version PASSED [  6%]
tests/test_briefs.py::test_t022_viewer_tries_approve_brief_denied PASSED [  9%]
tests/test_health.py::test_healthz_endpoint PASSED                       [ 12%]
tests/test_health.py::test_readyz_endpoint PASSED                        [ 15%]
tests/test_health.py::test_openapi_json_endpoint PASSED                  [ 18%]
tests/test_ingestion.py::test_t040_idempotent_ingestion_no_duplicates PASSED [ 21%]
tests/test_ingestion.py::test_t041_missing_view_count_null_never_zero PASSED [ 25%]
tests/test_ingestion.py::test_t042_duplicate_url_different_providers_one_canonical_record PASSED [ 28%]
tests/test_ingestion.py::test_t043_synthetic_fixture_rejected_in_prod PASSED [ 31%]
tests/test_ingestion.py::test_t044_deletion_expiry_purges_fields_and_logs_audit PASSED [ 34%]
tests/test_migrations.py::test_database_migration_lifecycle PASSED       [ 37%]
tests/test_planning_and_gold.py::test_t050_brief_with_excluded_topics_omits_prohibited_terms PASSED [ 40%]
tests/test_planning_and_gold.py::test_t051_three_briefs_gold_dataset_human_reviewed PASSED [ 43%]
tests/test_planning_and_gold.py::test_t052_query_planner_respects_max_requests_and_cost_cap PASSED [ 46%]
tests/test_retrieval.py::test_t070_deterministic_scoring_exact_weights_sum_100 PASSED [ 50%]
tests/test_retrieval.py::test_t071_high_view_count_irrelevant_or_prohibited_rejected_by_veto PASSED [ 53%]
tests/test_retrieval.py::test_t072_precision_at_10_meets_or_exceeds_80_percent_on_gold_sets PASSED [ 56%]
tests/test_retrieval.py::test_t073_single_snapshot_no_growth_velocity_inferred PASSED [ 59%]
tests/test_sources.py::test_t030_provider_empty_results_zero_fake_records PASSED [ 62%]
tests/test_sources.py::test_t031_auth_failed_forbidden_no_bypass PASSED  [ 65%]
tests/test_sources.py::test_t032_rate_limited_bounded_backoff_and_budget_cap PASSED [ 68%]
tests/test_sources.py::test_t033_malformed_response_quarantine_no_success_claim PASSED [ 71%]
tests/test_sources.py::test_t034_live_source_status_truthful PASSED      [ 75%]
tests/test_sources.py::test_t035_banned_source_rejected_without_network_call PASSED [ 78%]
tests/test_tenancy.py::test_user_a_can_access_own_workspace_brief PASSED [ 81%]
tests/test_tenancy.py::test_cross_tenant_access_denied_user_b_cannot_access_workspace_1 PASSED [ 84%]
tests/test_tenancy.py::test_user_b_in_own_workspace_cannot_read_brief1 PASSED [ 87%]
tests/test_understanding.py::test_t060_cluster_three_vietnamese_variants_of_same_objection PASSED [ 90%]
tests/test_understanding.py::test_t061_prompt_injection_stored_as_data_no_execution PASSED [ 93%]
tests/test_understanding.py::test_t062_demographic_claim_without_analytics_labeled_unsupported_inference PASSED [ 96%]
tests/test_understanding.py::test_t063_asr_status_truthful PASSED        [100%]

================= 32 passed, 5 warnings in 101.84s (0:01:41) ==================
```

---

## 6. KẾT LUẬN & SẴN SÀNG CHO PHA P08

- **Kết luận:** Pha P07 đã **HOÀN THÀNH 100% TIÊU CHÍ (PASS)**.
- **Tiêu chuẩn Cổng nghiệm thu đạt được:**
  - 100% tính tất định và minh bạch trong ma trận trọng số 5 chiều (tổng đúng 100%).
  - Cơ chế Brand Safety Veto loại bỏ triệt để video vi phạm dù có hàng chục triệu lượt xem.
  - Precision@10 đạt **86.67%** (vượt xa mục tiêu 80%) và 0 ứng viên dính veto lọt vào Top 10 trên 3 tập dữ liệu vàng.
  - Tuân thủ nghiêm ngặt nguyên tắc đơn ảnh chụp, không suy đoán tốc độ tăng trưởng.
  - An toàn bảo mật đạt 100% (quét 1.083 tệp mã nguồn, 0 secret vi phạm).
- **Sẵn sàng chuyển tiếp:** Pha P08 — **Sinh ý tưởng phái sinh LLM có trích dẫn & kiểm duyệt thương hiệu (LLM Ideation with Strict Grounding & Brand Alignment)**.
