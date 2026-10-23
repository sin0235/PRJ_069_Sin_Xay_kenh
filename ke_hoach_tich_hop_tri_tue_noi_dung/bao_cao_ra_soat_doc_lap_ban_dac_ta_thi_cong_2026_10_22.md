# BÁO CÁO RÀ SOÁT ĐỘC LẬP BẢN ĐẶC TẢ THI CÔNG CHI TIẾT TRÍ TUỆ NỘI DUNG (PHẦN HOÀN THIỆN MỚI)
**DỰ ÁN PRJ_069 - SIN XÂY KÊNH (BAHA GROUP)**

- **Mã báo cáo:** AUDIT-SPEC-CI-20261022-002
- **Thời điểm rà soát:** 2026-10-22T10:00:00+07:00
- **Đối tượng rà soát (Các phần vừa hoàn thiện):**
  1. Bản đặc tả thi công chi tiết: `03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md` (SPEC-EXEC-CI-2026-10-22 v1.0.0)
  2. Kế hoạch Master Plan hoàn thiện: `03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ke_hoach_tich_hop_tri_tue_noi_dung.md` (v2.0.0)
  3. Thẻ điều phối nhiệm vụ: `00_bat_dau/COMMAND_CONTROL_CARD.md`
- **Nguyên tắc thẩm định:** Rà soát độc lập trên tư duy phản biện kỹ thuật (Red Team Audit), đối chiếu trực tiếp chữ ký hàm, câu lệnh SQL, luồng xác thực middleware `baha_auth`, cơ chế đa tenant và an toàn giao dịch; **tuyệt đối không dựa vào các cam kết trên giấy nhằm loại trừ triệt để ảo giác kỹ thuật**.
- **Kết luận thẩm định:** **CẦN ĐIỀU CHỈNH 8 ĐIỂM KỸ THUẬT TRƯỚC KHI BẮT ĐẦU VIẾT MÃ (CONDITIONAL APPROVAL / AMENDMENT REQUIRED)**.

---

## I. TÓM TẮT ĐÁNH GIÁ ĐỘC LẬP (EXECUTIVE SUMMARY)

Bản đặc tả thi công kỹ thuật chi tiết (`ban_dac_ta_thi_cong_chi_tiet.md`) vừa được bổ sung là một bước tiến vượt bậc so với các tài liệu kế hoạch định tính trước đây: Nó đã chuyển hóa thành công các yêu cầu nghiệp vụ thành kiến trúc mã nguồn rõ ràng (chữ ký hàm, DTO schemas, SQL update, và RACI matrix).

Tuy nhiên, qua rà soát độc lập đối chiếu từng dòng mã đặc tả với tầng middleware bảo mật `baha_auth` và hạ tầng runtime thực tế, chúng tôi phát hiện **8 lỗ hổng kỹ thuật (4 Must Fix, 4 Should Fix)**. Nếu Codex bắt tay thi công ngay mà không sửa các điểm này, hệ thống sẽ gặp các sự cố nghiêm trọng sau:
1. **Kiểm thử Baseline P00-RE chuyển từ lỗi 401 sang 403 Forbidden**: Hàm `create_test_bearer_token` trong đặc tả chỉ sinh chuỗi JWT mà không khởi tạo bản ghi trong CSDL `auth_db` và `content_db`, khiến middleware chặn 100% request.
2. **Lọt lưới nguyên tắc Bốn Mắt (Four-Eyes Principle)**: Câu lệnh SQL Atomic Review Update quên điều kiện kiểm tra `IdeaCard.created_by != reviewer_id`, cho phép tác giả tự phê duyệt ý tưởng của chính mình.
3. **Sập tác vụ khách thuê mới (Missing Row Exception)**: Câu lệnh `UPDATE WorkspaceBudget` đơn lẻ sẽ trả về `rowcount == 0` đối với tenant mới chưa có dòng budget, khiến tenant mới bị từ chối với HTTP 402 ngay từ request đầu tiên.
4. **Lỗi tính toán vận tốc âm**: Không xử lý trường hợp TikTok quét bot view khiến số lượt xem giảm (`to_views < from_views`).
5. **Rủi ro hồi quy chéo với Media Studio**: Cả hai phân hệ cùng chỉnh sửa chung các file cốt lõi (`entities.py`, `contracts.py`, `budget_guard.py`, `tenancy.py`) trong khi Media Studio đang có 22 lỗi mở, nguy cơ làm hỏng chéo hệ thống.

---

## II. BẢNG TỔNG HỢP 8 PHÁT HIỆN KỸ THUẬT (SPEC-01 ĐẾN SPEC-08)

| Mã | Mức Độ | Hạng Mục & Dòng Đặc Tả | Tóm Tắt Bản Chất Kỹ Thuật |
|---|---|---|---|
| **SPEC-01** | **MUST FIX** | Giai đoạn 0: `tests/conftest.py` (L77-100) | Token sinh ra chỉ có payload JWT thô; thiếu fixture khởi tạo user/workspace/role ở cả 2 DB (`auth_db` + `content_db`), gây lỗi HTTP 403 Forbidden. |
| **SPEC-02** | **MUST FIX** | Giai đoạn 2: `ideation_service.py` (L218-237) | Câu lệnh SQL Atomic Update bỏ quên điều kiện `IdeaCard.created_by != reviewer_id`, phá vỡ nguyên tắc Bốn Mắt (No Self-Approval). |
| **SPEC-03** | **MUST FIX** | Giai đoạn 2: `budget_guard.py` (L262-273) | Câu lệnh `UPDATE WorkspaceBudget` đơn lẻ bị lỗi `rowcount == 0` với tenant mới tạo (chưa có row), gây lỗi HTTP 402 vô lý. |
| **SPEC-04** | **MUST FIX** | Ranh giới hạ tầng: Shared Core Files | Nguy cơ hồi quy chéo: Cả Trí tuệ Nội dung và Media Studio cùng sửa chung `entities.py`, `contracts.py`, `budget_guard.py` mà thiếu ranh giới khóa tệp. |
| **SPEC-05** | **SHOULD FIX** | Giai đoạn 2: `velocity_engine.py` (L244-249) | Không xử lý trường hợp `to_views < from_views` khi TikTok quét bot làm sụt giảm view, dẫn đến vận tốc âm làm hỏng phép tính logarit. |
| **SPEC-06** | **SHOULD FIX** | Giai đoạn 1: `entities.py` (L131-166) | Thiếu composite foreign key ràng buộc `workspace_id` trên `LearningSignal` và `ExperimentSuggestion`; `evidence_data_json` thiếu Pydantic validation. |
| **SPEC-07** | **SHOULD FIX** | Giai đoạn 3: `IdeaReviewModal` (L301-314) | Thiếu logic ẩn/vô hiệu hóa nút APPROVE khi Creator xem thẻ của chính mình; thiếu cơ chế Optimistic UI Rollback khi gặp lỗi 409 Conflict. |
| **SPEC-08** | **SHOULD FIX** | Giai đoạn 4: Human Quality Protocol (L336-348) | Thiếu schema JSON cấu trúc cho tệp lưu kết quả và thiếu thuật toán giải quyết bất đồng thuận (Cohen's Kappa / Veto boundaries) giữa 2 chuyên gia. |

---

## III. CHI TIẾT TỪNG PHÁT HIỆN & PHƯƠNG ÁN ĐIỀU CHỈNH BẮT BUỘC

### SPEC-01 (MUST FIX): Hàm `create_test_bearer_token` Thiếu Fixture Khởi Tạo CSDL Kép Gây Lỗi HTTP 403 Forbidden
- **Vị trí trong đặc tả:** [`ban_dac_ta_thi_cong_chi_tiet.md#L77-L100`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md#L77-L100)
- **Phân tích đối soát với mã nguồn thật:**
  Trong `sin_content_api/src/auth/tenancy.py` (L141-157), hàm phụ thuộc `get_current_tenant_context` thực hiện chuỗi kiểm tra nghiêm ngặt:
  1. Gọi `verify_bearer_token` giải mã JWT lấy `identity.user_id`.
  2. Mở kết nối `auth_db` và gọi `load_actor_for_user(auth_db, workspace_id, user_id)`. Nếu user chưa có bản ghi `GlobalUser`, `Membership`, `RoleAssignment` trong `auth_db`, hệ thống ném **HTTP 403 FORBIDDEN: "Không có quyền truy cập workspace đã chọn."**
  3. Mở kết nối `content_db` và kiểm tra `content_db.query(Workspace.id).filter(Workspace.id == x_workspace_id)`. Nếu workspace chưa tồn tại trong `content_db`, hệ thống tiếp tục ném **HTTP 403 FORBIDDEN**.
- **Lỗ hổng của bản đặc tả:** Bản đặc tả chỉ hướng dẫn sinh token JWT qua `jwt.encode()` mà hoàn toàn không hướng dẫn chèn các bản ghi tương ứng vào cả 2 CSDL RAM (`auth_db` và `content_db`). Nếu Codex làm theo, test suite sẽ chuyển từ lỗi `401 Unauthorized` sang lỗi `403 Forbidden`, toàn bộ bài test vẫn thất bại 100%.
- **Phương án điều chỉnh bắt buộc trong Giai đoạn 0:**
  Bổ sung vào `tests/conftest.py` fixture thiết lập môi trường CSDL kép chuẩn hóa (tham chiếu mô hình thành công từ `test_media_studio_budget_gf05.py#L97-L150`):
  ```python
  @pytest.fixture
  def auth_tenant_fixture():
      ws_id = f"ws-test-{uuid.uuid4().hex[:8]}"
      user_id = f"user-test-{uuid.uuid4().hex[:8]}"
      
      # 1. Khởi tạo trong content_db
      with SessionLocal() as db:
          db.add(Workspace(id=ws_id, name="Test Studio", slug=ws_id))
          db.add(User(id=user_id, email=f"{user_id}@baha.vn", hashed_password="mock"))
          db.commit()
          
      # 2. Khởi tạo trong auth_db
      with AuthSessionLocal() as auth_db:
          auth_db.add(AuthWorkspace(id=ws_id, name="Test Studio", slug=ws_id, status="ACTIVE"))
          auth_db.add(GlobalUser(id=user_id, email=f"{user_id}@baha.vn", status="ACTIVE"))
          auth_db.commit()
          
          m = AuthMembership(id=str(uuid.uuid4()), user_id=user_id, workspace_id=ws_id, status="ACTIVE")
          auth_db.add(m)
          auth_db.commit()
          
          role_owner = auth_db.query(AuthRole).filter(AuthRole.code == "WORKSPACE_OWNER").first()
          ra = RoleAssignment(
              id=str(uuid.uuid4()), membership_id=m.id, role_id=role_owner.id,
              workspace_id=ws_id, status="ACTIVE", granted_by=m.id, scope_type="WORKSPACE"
          )
          auth_db.add(ra)
          auth_db.commit()
          
      return {
          "workspace_id": ws_id,
          "user_id": user_id,
          "headers": {
              "Authorization": f"Bearer {create_test_bearer_token(user_id, ws_id)}",
              "X-Workspace-Id": ws_id
          }
      }
  ```

---

### SPEC-02 (MUST FIX): Câu Lệnh SQL Atomic Review Update Bỏ Quên Điều Kiện Kiểm Tra Nguyên Tắc Bốn Mắt
- **Vị trí trong đặc tả:** [`ban_dac_ta_thi_cong_chi_tiet.md#L218-L237`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md#L218-L237)
- **Hiện trạng mã đặc tả:**
  ```python
  stmt = (
      update(IdeaCard)
      .where(
          IdeaCard.id == card_id,
          IdeaCard.workspace_id == workspace_id,
          IdeaCard.version == request.expected_version,
          IdeaCard.status == request.expected_status
      )
      .values(
          status=target_status,
          version=IdeaCard.version + 1,
          reviewed_by=reviewer_id,
          reviewed_at=datetime.now(timezone.utc),
          review_reason=request.review_reason
      )
  )
  ```
- **Vấn đề:** Câu lệnh SQL chỉ kiểm tra `version` và `status` hiện tại mà **hoàn toàn không có điều kiện `IdeaCard.created_by != reviewer_id` khi action là `APPROVE`**.
- **Hậu quả:** Nguyên tắc Bốn Mắt (Separation of Duties / No Self-Approval) là rào chắn nghiệp vụ cốt lõi của BAHA Group (được khẳng định tại Mục 1.2, Nguyên tắc 7). Nếu chỉ dựa vào câu lệnh này, một Creator khi có quyền review có thể tự gửi request duyệt chính bài viết/ý tưởng của mình và câu lệnh SQL vẫn chạy trót lọt, gán `status = "APPROVED"`.
- **Phương án điều chỉnh bắt buộc trong Giai đoạn 2:**
  Bổ sung chốt chặn Bốn Mắt ở cả tầng Python Guard lẫn tầng Atomic SQL:
  ```python
  # 1. Chặn sớm ở tầng Logic Service
  idea = db.query(IdeaCard).filter(IdeaCard.id == card_id, IdeaCard.workspace_id == workspace_id).first()
  if not idea:
      raise HTTPException(status_code=404, detail="IDEA_NOT_FOUND")
      
  if target_status == "APPROVED" and idea.created_by == reviewer_id:
      raise HTTPException(
          status_code=status.HTTP_403_FORBIDDEN,
          detail="SELF_APPROVAL_VIOLATION: Người tạo không được phép tự phê duyệt ý tưởng của chính mình."
      )

  # 2. Khóa kép ở tầng Atomic SQL Update
  where_conditions = [
      IdeaCard.id == card_id,
      IdeaCard.workspace_id == workspace_id,
      IdeaCard.version == request.expected_version,
      IdeaCard.status == request.expected_status
  ]
  if target_status == "APPROVED":
      where_conditions.append(IdeaCard.created_by != reviewer_id)

  stmt = update(IdeaCard).where(*where_conditions).values(...)
  ```

---

### SPEC-03 (MUST FIX): Lỗi Missing Row Exception Trong Câu Lệnh Atomic Budget Update Đối Với Khách Thuê Mới
- **Vị trí trong đặc tả:** [`ban_dac_ta_thi_cong_chi_tiet.md#L262-L273`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md#L262-L273)
- **Hiện trạng mã đặc tả:**
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
- **Vấn đề:** Câu lệnh `UPDATE` chỉ có tác dụng khi bản ghi `WorkspaceBudget` của `workspace_id` đã tồn tại trong CSDL. Khi một khách thuê mới vừa tạo workspace và thực hiện tác vụ AI đầu tiên, bảng `WorkspaceBudget` chưa có dòng của khách thuê này. Lệnh `UPDATE` sẽ trả về `result.rowcount == 0`.
- **Hậu quả:** Hệ thống hiểu lầm rằng tenant này bị hết tiền (`REFUSED_OVER_BUDGET`), ném ngay lỗi `HTTP 402 PAYMENT_REQUIRED` và từ chối tác vụ của khách thuê mới, mặc dù tenant này đáng lẽ phải được hưởng hạn mức dùng thử mặc định (ví dụ 100.0 units).
- **Phương án điều chỉnh bắt buộc trong Giai đoạn 2:**
  Đặc tả bắt buộc gọi hàm `get_or_create_budget()` trước khi chạy lệnh atomic update, hoặc sử dụng câu lệnh có fallback khởi tạo:
  ```python
  # Bắt buộc đảm bảo dòng budget tồn tại trước khi atomic update
  budget_guard.get_or_create_budget(db, workspace_id=workspace_id, default_allocated=100.0)
  db.commit()

  # Sau đó mới thực thi câu lệnh atomic reservation có điều kiện số dư
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

---

### SPEC-04 (MUST FIX): Rủi Ro Hồi Quy Chéo Trên Các Tệp Chia Sẻ Chung (Shared Core Files)
- **Bối cảnh rủi ro:**
  Phân hệ Trí tuệ Nội dung (P10-P12) và Phân hệ Media Studio (P01-P14) sử dụng chung 4 tệp lõi:
  1. `03_ban_lam_viec/sin_content_api/src/models/entities.py` (Chung ORM Base)
  2. `03_ban_lam_viec/sin_content_api/src/schemas/contracts.py` (Chung DTO Schemas)
  3. `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/budget_guard.py` (Chung Budget)
  4. `03_ban_lam_viec/sin_content_api/src/auth/tenancy.py` (Chung Middleware)
- **Nguy cơ thực tế:** Hiện tại Phân hệ Media Studio đang có **22 lỗi kỹ thuật mở (15 Must Fix)** và Checkpoint CP02 đã bị bác bỏ. Nếu Codex thi công sửa các tệp chia sẻ này cho Trí tuệ Nội dung mà không phân định ranh giới rõ ràng, rất dễ làm hỏng chéo (regression) các module đang được rà soát của Media Studio.
- **Phương án điều chỉnh bắt buộc:**
  - Thiết lập ranh giới khóa tệp (Namespace Guard): Khi mở rộng `entities.py`, Codex chỉ được phép **append (thêm mới)** các thực thể của Trí tuệ Nội dung (`PublishedContentLink`, `LearningSignal`, `ExperimentSuggestion`) và không được chỉnh sửa cấu trúc các bảng của Media Studio (`ProductionProject`, `MediaAsset`, `AIGenerationJob`).
  - Toàn bộ thay đổi phải được kiểm tra hồi quy độc lập bằng cách chạy riêng biệt suite Content Intelligence:
    `python -m pytest sin_content_api/tests/test_workbench.py sin_content_api/tests/test_feedback_loop.py sin_content_api/tests/test_staging_evaluation.py`.

---

### SPEC-05 (SHOULD FIX): Tính Toán Trend Velocity Thiếu Xử Lý Khi View Bị Sụt Giảm Do Quét Bot
- **Vị trí trong đặc tả:** [`ban_dac_ta_thi_cong_chi_tiet.md#L244-L249`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md#L244-L249)
- **Vấn đề:** Trong thực tế TikTok Analytics, số lượt xem `to_views` có thể nhỏ hơn `from_views` khi nền tảng quét và trừ view ảo, hoặc người dùng chuyển bài viết sang chế độ riêng tư. Khi đó, `delta_views = to_views - from_views < 0`.
- **Hậu quả:** Công thức tính vận tốc sẽ trả về giá trị âm (ví dụ `-1500 views/day`). Nếu giá trị âm này được đưa trực tiếp vào ma trận xếp hạng `TransparentScorer` (trong `P07`), hàm tính logarit hoặc chuẩn hóa điểm số có thể bị ném ngoại lệ toán học `ValueError: math domain error`.
- **Phương án điều chỉnh:**
  Nếu `to_views < from_views`, quy định rõ:
  - Gán nhãn `velocity_status = "AUDIT_PURGED_ANOMALY"`.
  - Đặt `velocity_views_per_day = 0.0` (không tính số âm vào thuật toán đề xuất ý tưởng).
  - Ghi cảnh báo kiểm toán vào trường ghi chú của bản ghi quan sát.

---

### SPEC-06 (SHOULD FIX): Thiếu Composite Key Ràng Buộc Đa Khách Thuê & Pydantic Validation Trên Thực Thể Mới
- **Vị trí trong đặc tả:** [`ban_dac_ta_thi_cong_chi_tiet.md#L143-L166`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md#L143-L166)
- **Vấn đề:** `LearningSignal` và `ExperimentSuggestion` chỉ khai báo khóa ngoại đơn `ForeignKey("published_content_links.id")`. Ngoài ra, trường `evidence_data_json` lưu chuỗi JSON tự do không có schema kiểm soát.
- **Phương án điều chỉnh:**
  - Thêm chỉ mục tổ hợp `(workspace_id, signal_type)` trên `LearningSignal` để tối ưu hóa truy vấn phân tích.
  - Định nghĩa Pydantic schema `LearningSignalEvidenceSchema` để xác thực cấu trúc `evidence_data_json` trước khi lưu vào CSDL, chống rác dữ liệu.

---

### SPEC-07 (SHOULD FIX): Modal Kiểm Duyệt Trên UI Thiếu Logic Tự Vô Hiệu Hóa Đối Với Tác Giả & Optimistic Rollback
- **Vị trí trong đặc tả:** [`ban_dac_ta_thi_cong_chi_tiet.md#L301-L314`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md#L301-L314)
- **Vấn đề:** Bản đặc tả giao diện chưa hướng dẫn ẩn hoặc disable nút `Duyệt (APPROVE)` khi `idea.created_by == currentUser.id`. Ngoài ra, khi gặp lỗi `HTTP 409 Conflict`, giao diện chưa có cơ chế hoàn tác dữ liệu lạc quan (Optimistic Rollback).
- **Phương án điều chỉnh:**
  - Trong `IdeaReviewModal`: Nếu người dùng hiện tại là tác giả tạo thẻ, nút `APPROVE` phải bị mờ (disabled) kèm chú thích (tooltip): *"Bạn không thể tự duyệt ý tưởng của chính mình (Quy tắc Bốn Mắt)"*.
  - Bổ sung cơ chế tự động gọi `loadIdeas()` tải lại dữ liệu mới nhất từ server khi gặp lỗi 409 để đồng bộ trạng thái thẻ tức thì.

---

### SPEC-08 (SHOULD FIX): Thiếu Schema JSON Đầu Ra & Công Thức Bất Đồng Thuận Trong Human Quality Study
- **Vị trí trong đặc tả:** [`ban_dac_ta_thi_cong_chi_tiet.md#L336-L348`](file:///192.168.1.175/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md#L336-L348)
- **Vấn đề:** Giai đoạn 4 yêu cầu 2 chuyên gia đánh giá độc lập >= 30 mẫu, nhưng không định nghĩa cấu trúc file lưu trữ kết quả đánh giá và công thức xử lý khi 2 chuyên gia chấm lệch nhau.
- **Phương án điều chỉnh:**
  - Ban hành định dạng JSON Schema chuẩn cho tệp đánh giá: `{"brief_id": "...", "rater_1_score": 1, "rater_2_score": 0, "final_decision": "RESOLVED_VETO", ...}`.
  - Quy định rõ: Tiêu chí an toàn thương hiệu và từ khóa cấm áp dụng **Quy tắc Phủ Quyết Tuyệt Đối (Strict Veto)**: Chỉ cần 1 trong 2 chuyên gia chấm vi phạm thì kết quả coi như KHÔNG ĐẠT. Đối với độ tương quan Relevancy, nếu lệch nhau thì tính trung bình trọng số.

---

## IV. KẾT LUẬN & KIẾN NGHỊ HÀNH ĐỘNG

Bản đặc tả thi công chi tiết (`ban_dac_ta_thi_cong_chi_tiet.md`) **RẤT CHẤT LƯỢNG VỀ MẶT CẤU TRÚC VÀ ĐỦ ĐIỀU KIỆN ĐỂ TRIỂN KHAI SAU KHI CẬP NHẬT 4 ĐIỂM MUST FIX (SPEC-01 ĐẾN SPEC-04)**.

### Các Bước Cần Thực Hiện Ngay:
1. **Cập nhật Bản đặc tả thi công**: Bổ sung trực tiếp 8 điểm điều chỉnh trên vào `03_ban_lam_viec/ke_hoach_tich_hop_tri_tue_noi_dung/ban_dac_ta_thi_cong_chi_tiet.md`.
2. **Cập nhật Thẻ điều phối**: Ghi chú các điều kiện tiên quyết này vào `00_bat_dau/COMMAND_CONTROL_CARD.md`.
3. **Phân công Codex thi công**: Sau khi đặc tả được cập nhật hoàn chỉnh, Founder có thể an tâm phát lệnh cho Codex bắt tay thi công tuần tự từ **Giai đoạn 0 (P00-RE)** đến **Giai đoạn 1 (Data Layer)**.
4. **Cam kết kỷ luật**: Tiếp tục giữ nguyên trạng thái chưa chỉnh sửa mã nguồn runtime cho đến khi lệnh thi công chính thức được ban hành.
