# BÁO CÁO NGHIỆM THU PHA P09: SOẠN THẢO KỊCH BẢN & KIỂM ĐỊNH TUYÊN BỐ SẢN PHẨM (SCRIPT DRAFTING & FACT-CHECKING)

- **Dự án:** SIN Content Intelligence (PRJ_069)
- **Pha thực hiện:** P09 — Script Drafting, Timing Control & Product Claim Fact-Checking
- **Ngày hoàn thành:** 21/10/2026
- **Trạng thái:** **HOÀN THÀNH TOÀN DIỆN (PASS 100%)**
- **Nguyên tắc cốt lõi:** **Ground Truth > Self-report**. Mọi kết quả nghiệm thu đều dựa trên bằng chứng lệnh thực thi thực tế (Exit Code 0), không có dữ liệu giả định.

---

## 1. TỔNG QUAN VÀ MỤC TIÊU PHA P09

Pha P09 chịu trách nhiệm chuyển hóa các thẻ ý tưởng đã được phê duyệt (`IdeaCard` APPROVED) thành bản thảo kịch bản video TikTok chi tiết theo từng phân cảnh, đồng thời áp đặt hai rào chắn bảo vệ thương hiệu tối cao:
1. **Kiểm định tuyên bố độc lập (Fact-Checking Engine - ClaimChecker):** Quét toàn bộ lời thoại (`narration`), mô tả khung hình (`visual_cue`) và các biến thể mở đầu (`hook_variants`) để phát hiện các tuyên bố định lượng (tính năng, tỷ lệ %, thời lượng giữ nhiệt, chất liệu kỹ thuật, cam kết tuyệt đối). Bắt buộc đối soát 1:1 với danh mục sự thật được phép (`AllowedFact`) của nhãn hàng. Cấm tuyệt đối phê duyệt kịch bản chứa tuyên bố chưa được kiểm chứng.
2. **Tính bất biến của kịch bản đã duyệt (Immutable Versioning):** Khi một kịch bản đã được phê duyệt (`APPROVED`), người dùng không được phép sửa đè trực tiếp. Mọi thao tác chỉnh sửa bắt buộc chuyển phiên bản cũ sang trạng thái thay thế (`SUPERSEDED`) và sinh bản nháp mới độc lập (`version = version + 1`, `DRAFT`), bảo toàn 100% lịch sử phê duyệt phục vụ kiểm toán.
3. **Kiểm soát dung sai thời lượng và cấu trúc phân cảnh (Timing & Hook Variants):** Tự động tính toán mốc thời gian bắt đầu và kết thúc tuần tự, không chồng chéo giữa các phân cảnh (`HOOK`, `SETUP`, `VALUE`, `PROOF`, `CTA`), kiểm tra độ lệch tổng thời lượng so với mục tiêu trong dung sai cho phép (±3 giây) và bảo đảm có tối thiểu ≥ 2 biến thể Hook để thử nghiệm A/B.

---

## 2. BẰNG CHỨNG THỰC THI KIỂM THỬ (GROUND TRUTH EVIDENCE)

Bộ kiểm thử `tests/test_scripts.py` được thực thi trực tiếp trên môi trường backend với SQLAlchemy và FastAPI TestClient.

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\tools\python-embed\python.exe
cachedir: .pytest_cache
rootdir: \\192.168.1.175\09.ai_workspace\01_du_an\PRJ_069_Sin_Xay_kenh\03_ban_lam_viec\sin_content_api
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 4 items

tests/test_scripts.py::test_t090_unverified_claim_blocks_approval PASSED [ 25%]
tests/test_scripts.py::test_t091_verified_claims_permit_approval PASSED  [ 50%]
tests/test_scripts.py::test_t092_immutable_versioning_on_edit PASSED     [ 75%]
tests/test_scripts.py::test_t093_timing_tolerance_and_hook_variants PASSED [100%]

======================= 4 passed, 3 warnings in 15.98s ========================
```

---

## 3. CHI TIẾT KẾT QUẢ NGHIỆM THU TỪNG TIÊU CHÍ (T090 - T093)

### 3.1. Bài kiểm thử T090: Chặn phê duyệt khi kịch bản chứa tuyên bố chưa kiểm định (BLOCKING Claims)
- **Đầu vào thử nghiệm:** Kịch bản tạo mới chứa tuyên bố phóng đại: *"Thử thách 24 tiếng giữ nóng hộp cơm văn phòng"* và *"cam kết 100% không bao giờ trào dù chạy 50km đường ổ gà"*, trong khi `AllowedFact` đã duyệt của hãng chỉ cho phép *"giữ nóng 6 tiếng liên tục"*.
- **Phản hồi của hệ thống khi tạo bản thảo (`POST /v1/scripts`):**
  - Trạng thái kịch bản: `NEEDS_FACT_CHECK`
  - `blocking_claims_count`: `2`
  - Các tuyên bố vi phạm tự động gắn nhãn: `verification_status = "BLOCKING"`, ghi rõ lý do thiếu nguồn chứng minh kỹ thuật từ hãng.
- **Rào chắn bảo vệ khi cố tình duyệt (`POST /v1/scripts/{id}/approve`):**
  - Mã trạng thái HTTP: `422 Unprocessable Entity`
  - Mã lỗi hệ thống: `error_code = "CANNOT_APPROVE_UNVERIFIED_CLAIMS"`
  - Thông báo an toàn: `message_safe = "Không thể duyệt kịch bản vì còn 2 tuyên bố chưa được kiểm định từ tài liệu hãng (AllowedFact)..."`
  - Trạng thái kịch bản trong DB vẫn giữ nguyên `NEEDS_FACT_CHECK`.
- **Kết luận T090:** **ĐẠT (PASS)**. Tuyệt đối không cho phép kịch bản vi phạm lọt lưới kiểm duyệt.

### 3.2. Bài kiểm thử T091: Kiểm định tuyên bố hợp lệ và phê duyệt thành công
- **Đầu vào thử nghiệm:** Kịch bản chỉ chứa các tuyên bố kỹ thuật chuẩn xác theo tài liệu hãng:
  - *"Hộp cơm giữ nóng 6 tiếng từ sáng đến trưa"* -> Khớp với AllowedFact Quatest 3.
  - *"Chất liệu inox 304 nắp gioăng silicon chống tràn canh tuyệt đối"* -> Khớp với chứng nhận TCVN và thử nghiệm rung lắc 50km/h.
- **Phản hồi của hệ thống (`POST /v1/scripts`):**
  - `blocking_claims_count`: `0`
  - Trạng thái kịch bản: `READY_FOR_REVIEW`
  - Toàn bộ claims đều có `verification_status = "VERIFIED"` kèm `allowed_fact_id` và `source_citation`.
- **Phê duyệt kịch bản (`POST /v1/scripts/{id}/approve`):**
  - Mã trạng thái HTTP: `200 OK`
  - Trạng thái kịch bản: `APPROVED`
  - Ghi nhận định danh người duyệt (`approved_by_user_id`) và dấu thời gian chuẩn ISO UTC (`approved_at`).
- **Kết luận T091:** **ĐẠT (PASS)**. Quy trình xác thực và cấp phép vận hành mượt mà, minh bạch nguồn gốc.

### 3.3. Bài kiểm thử T092: Tính bất biến của phiên bản kịch bản (Immutable Versioning on Edit)
- **Tình huống:** Kịch bản phiên bản 1 (`version = 1`) đã ở trạng thái `APPROVED`. Người dùng gửi yêu cầu chỉnh sửa lời kêu gọi hành động (`CTA`) qua `POST /v1/scripts/{v1_id}/edit`.
- **Hành vi hệ thống:**
  - Bản ghi `version = 1` được tự động chuyển trạng thái thành `SUPERSEDED`, hoàn toàn đóng băng không bị ghi đè.
  - Một bản ghi `ScriptDraftVersion` mới được khởi tạo với `version = 2`, mang ID mới, trạng thái ban đầu là `DRAFT`, chứa nội dung cập nhật mới nhất.
  - Khi kiểm tra lại qua `GET /v1/scripts/{v1_id}`, bản cũ vẫn tồn tại đầy đủ thông tin với trạng thái `SUPERSEDED`.
- **Kết luận T092:** **ĐẠT (PASS)**. Bảo toàn 100% dữ liệu lịch sử phiên bản, không bị xóa hay ghi đè trái phép.

### 3.4. Bài kiểm thử T093: Kiểm soát thời lượng phân cảnh và biến thể Hook (TimingCalculator)
- **Dung sai thời lượng (Tolerance Check):**
  - Kịch bản target 30 giây, thực tế các phân cảnh cộng dồn 32 giây (lệch +2s ≤ ±3s): `duration_tolerance_passed = True`.
  - Kịch bản target 30 giây, thực tế cộng dồn 36 giây (lệch +6s > ±3s): `duration_tolerance_passed = False`.
- **Tính liên tục không chồng chéo (Non-overlapping Timeline):**
  - Phân cảnh 1: `start_seconds = 0`, `end_seconds = 5`
  - Phân cảnh 2: `start_seconds = 5`, `end_seconds = 15`
  - Phân cảnh 3: `start_seconds = 15`, `end_seconds = 27`
  - Phân cảnh 4: `start_seconds = 27`, `end_seconds = 32`
  - `has_overlap = False`.
- **Số lượng biến thể Hook:**
  - Có 2 biến thể hook: `hook_variants_valid = True`.
  - Chỉ có 1 biến thể hook: `hook_variants_valid = False`.
- **Kết luận T093:** **ĐẠT (PASS)**. Đảm bảo chất lượng sản xuất kịch bản video ngắn đạt chuẩn truyền thông TikTok.

---

## 4. KIỂM TOÁN AN TOÀN BẢO MẬT T012 (CREDENTIALS & SECRETS AUDIT)

Lệnh kiểm toán toàn bộ thư mục làm việc `03_ban_lam_viec` được thực thi qua `scan_secrets.py`:

```text
=== T012: SECRETS & CREDENTIALS AUDIT ===
Scanning target directory: 03_ban_lam_viec
Scanned files count: 1129

[PASS] Zero committed credentials, tokens or passwords found!
T012 Result: PASS
```

- **Tổng số tệp quét:** 1.129 tệp mã nguồn (.py, .ts, .json, .md, .ps1, .yaml).
- **Số lượng secret vi phạm:** **0**.
- **Mã thoát lệnh (Exit code):** **0**.

---

## 5. TƯƠNG THÍCH BẢO MẬT & PHÂN QUYỀN RBAC CANONICAL

Toàn bộ các route của Pha P09 đã được tích hợp với hệ thống phân quyền chuẩn (`baha_auth`), khai báo tường minh các action keys được quản lý trong `PERMISSION_REGISTRY.json`:
- `POST /v1/scripts` -> `require_actions("script.create", "ideas.read")`
- `GET /v1/scripts` -> `require_action("script.read")`
- `GET /v1/scripts/{id}` -> `require_action("script.read")`
- `POST /v1/scripts/{id}/approve` -> `require_action("script.approve_final")`
- `POST /v1/scripts/{id}/edit` -> `require_action("script.edit")`
- `POST /v1/scripts/{id}/reject` -> `require_action("script.edit")`

Bài kiểm thử `tests/test_tich_hop_phan_quyen.py::test_moi_route_nghiep_vu_deu_khai_bao_action_rbac` xác nhận: **0 route nào của scripts bị bỏ sót hoặc thiếu guard**.

---

## 6. DANH MỤC TỆP ĐÃ PHÁT HÀNH TRONG PHA P09

| STT | Đường dẫn tệp | Mô tả trách nhiệm |
|---|---|---|
| 1 | `03_ban_lam_viec/sin_content_api/src/schemas/contracts.py` | Bổ sung Pydantic DTOs: `ScriptBlock`, `ClaimCheck`, `ScriptDraftCreate`, `ScriptDraftEditRequest`, `ScriptDraftOut`, `ScriptReviewRequest` |
| 2 | `03_ban_lam_viec/sin_content_api/src/models/entities.py` | Cập nhật ORM `ScriptDraftVersion` với các trường JSON, trạng thái duyệt và getters an toàn |
| 3 | `03_ban_lam_viec/sin_content_api/src/modules/scripts/claim_checker.py` | Bộ kiểm định tuyên bố sản phẩm độc lập (ClaimChecker) đối soát 1:1 với AllowedFact |
| 4 | `03_ban_lam_viec/sin_content_api/src/modules/scripts/timing_calculator.py` | Bộ tính toán timeline phân cảnh, kiểm soát dung sai ±3s và kiểm tra hook variants |
| 5 | `03_ban_lam_viec/sin_content_api/src/modules/scripts/script_service.py` | Service điều phối soạn thảo, kiểm định claims, duyệt và phiên bản hóa bất biến |
| 6 | `03_ban_lam_viec/sin_content_api/src/modules/scripts/router.py` | REST API Router `/v1/scripts` bảo vệ bằng RBAC actions |
| 7 | `03_ban_lam_viec/sin_content_api/src/modules/scripts/__init__.py` | Export module scripts |
| 8 | `03_ban_lam_viec/sin_content_api/src/main.py` | Mount `scripts_router` vào ứng dụng chính FastAPI |
| 9 | `03_ban_lam_viec/sin_content_api/tests/test_scripts.py` | Bộ kiểm thử tự động 4 bài test T090 - T093 tích hợp Baha Auth RBAC |
| 10 | `03_ban_lam_viec/sin_creator_os/src/contracts/index.ts` | Bổ sung TypeScript Interfaces đồng bộ 1:1 với backend contracts |
| 11 | `03_ban_lam_viec/sin_creator_os/bao_cao_p09.md` | Báo cáo nghiệm thu chính thức của Pha P09 |

---

## 7. QUYẾT ĐỊNH NGHIỆM THU & BƯỚC TIẾP THEO

- **Quyết định nghiệm thu:** **CHẤP THUẬN NGHIỆM THU PHA P09 (PASS)**.
- **Trạng thái cổng kiểm soát (Phase Gate):** Cổng Pha P09 đóng thành công; mở cổng sẵn sàng triển khai **Pha P10: Tạo storyboard, phỏng dựng hình ảnh & chỉ dẫn kỹ thuật sản xuất (Storyboard & Visual Prompts)**.
