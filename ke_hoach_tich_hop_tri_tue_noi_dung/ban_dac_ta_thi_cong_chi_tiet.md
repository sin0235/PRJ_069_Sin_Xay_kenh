# BẢN ĐẶC TẢ THI CÔNG KỸ THUẬT CHI TIẾT (IMPLEMENTATION BLUEPRINT)
## Phân Hệ Trí Tuệ Nội Dung SIN Content Intelligence (PRJ_069)

- **Mã tài liệu:** SPEC-EXEC-CI-2026-10-22
- **Phiên bản:** 1.0.0
- **Ngày ban hành:** 22/10/2026
- **Trạng thái:** BẢN ĐẶC TẢ SẴN SÀNG THI CÔNG (IMPLEMENTATION-READY SPECIFICATION) — **CHỜ LỆNH THI CÔNG**
- **Căn cứ kế hoạch:**
  - Kế hoạch Master Plan: `ke_hoach_tich_hop_tri_tue_noi_dung.md` (v2.0)
  - Kế hoạch khắc phục P10-P12: `ke_hoach_khac_phuc_va_dieu_chinh_p10_p11_p12.md`
  - Báo cáo rà soát độc lập: `bao_cao_ra_soat_doc_lap_ke_hoach.md` (AUDIT-PLAN-CI-2026-10-22)
  - Ma trận phân quyền: `ma_tran_tich_hop_rbac_va_frontend.md`
- **Mục tiêu tài liệu:** Cung cấp bản thiết kế kỹ thuật chi tiết mức mã nguồn (code-level blueprint), định rõ từng file cần tạo/sửa, chữ ký hàm, mô hình dữ liệu, câu lệnh SQL nguyên tử, lệnh kiểm thử tương ứng và tiêu chí nghiệm thu cho từng giai đoạn, sẵn sàng để Codex hoặc kỹ sư bắt tay thi công chuẩn xác 100%.

---

## I. TỔNG QUAN LỘ TRÌNH 5 GIAI ĐOẠN THI CÔNG

```
+-----------------------------------------------------------------------------------------+
| GIAI ĐOẠN 0: CHUẨN HÓA TEST HARNESS & AUTH FIXTURE (P00-RE)                             |
| File: tests/conftest.py, tests/test_tenancy.py, test_briefs.py, test_sources.py, test_scripts|
| Mục tiêu: Giải quyết AUD-01; tạo fixture Bearer JWT token; đưa Baseline P01-P09 về 100% PASS|
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
| GIAI ĐOẠN 1: ĐỒNG BỘ CSDL, ORM & HỢP ĐỒNG BACKEND/FRONTEND (DATA LAYER)                  |
| File: src/models/entities.py, src/schemas/contracts.py, sin_creator_os/src/contracts/   |
| Mục tiêu: Thêm PublishedContentLink, is_paid, channel_id, WorkspaceBudget, CostLedger;   |
|           bắt buộc expected_version; đồng bộ TypeScript contracts 1:1.                  |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
| GIAI ĐOẠN 2: TRIỂN KHAI TOÀN BỘ LOGIC BACKEND & BẢO MẬT GUARDS (SERVICE LAYER)           |
| File: modules/ideation/, modules/sources/, modules/feedback/, modules/staging_reliability|
|       scripts/backup_staging_db.py, scripts/restore_staging_db.py                        |
| Mục tiêu: Atomic review update; xóa mock 45k/86; chuẩn hóa OAuth; giữ null; atomic budget|
|           cache key {ws_id}:{key}; đệ quy secrets scrubbing; khôi phục nguyên tử an toàn.|
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
| GIAI ĐOẠN 3: TÍCH HỢP GIAO DIỆN NGƯỜI DÙNG WORKBENCH (UI LAYER - P10)                   |
| File: sin_creator_os/src/app/(main)/ideas/, src/services/idea-service.ts, discover-service|
| Mục tiêu: Thay mock data bằng API thật; modal review 4 thao tác; hiển thị MISSING/EXPIRED|
|           Chạy Playwright E2E cho 8 màn hình chính & lưu ảnh nghiệm thu.                 |
+--------------------------------------------+--------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
| GIAI ĐOẠN 4: ĐÁNH GIÁ STAGING, QUÉT BẢO MẬT & ĐÓNG GÓI GATE P13 (AUDIT & HANDOFF)       |
| File: prompt_regression.py, audit_licenses_and_deps.py, RELEASE_READINESS.md           |
| Mục tiêu: Đánh giá prompt trên gold sets >= 30 mẫu x 3 briefs; quét T012 100% tệp;       |
|           kiểm toán giấy phép; lập biên bản nghiệm thu trình Founder mở Canary P13.      |
+-----------------------------------------------------------------------------------------+
```

---

## II. ĐẶC TẢ CHI TIẾT TỪNG GIAI ĐOẠN THI CÔNG

### GIAI ĐOẠN 0: CHUẨN HÓA TEST HARNESS & AUTH FIXTURE (P00-RE)
**Mục tiêu:** Khắc phục triệt để lỗi 401 Unauthorized do middleware `baha_auth` chặn header legacy `X-User-Id`; bảo đảm toàn bộ test suite cơ sở (Baseline P01 - P09) xanh 100%.

#### 1. Tệp Cần Chỉnh Sửa
- `03_ban_lam_viec/sin_content_api/tests/conftest.py`
- `03_ban_lam_viec/sin_content_api/tests/test_tenancy.py`
- `03_ban_lam_viec/sin_content_api/tests/test_briefs.py`
- `03_ban_lam_viec/sin_content_api/tests/test_sources.py`
- `03_ban_lam_viec/sin_content_api/tests/test_scripts.py`

#### 2. Đặc Tả Kỹ Thuật Mã Nguồn
- **Trong `tests/conftest.py`:** Cung cấp helper tạo Bearer token chuẩn hóa và fixture CSDL kép (bắt buộc khởi tạo ở cả `content_db` và `auth_db` để vượt qua `get_current_tenant_context` mà không bị chặn 403 Forbidden):
  ```python
  import jwt
  import uuid
  import pytest
  from datetime import datetime, timezone, timedelta
  from sqlalchemy.orm import Session

  JWT_SECRET = "kiem-thu-bang-khoa-gia-lap-p11"
  JWT_ALGORITHM = "HS256"

  def create_test_bearer_token(user_id: str, workspace_id: str, role: str = "workspace_owner") -> str:
      payload = {
          "sub": user_id,
          "workspace_id": workspace_id,
          "role": role,
          "iss": "baha-auth-local-issuer",
          "aud": "sin-content-api",
          "exp": datetime.now(timezone.utc) + timedelta(hours=2)
      }
      return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

  def auth_headers(user_id: str, workspace_id: str, role: str = "workspace_owner") -> dict:
      token = create_test_bearer_token(user_id, workspace_id, role)
      return {
          "Authorization": f"Bearer {token}",
          "X-Workspace-Id": workspace_id
      }

  @pytest.fixture
  def auth_tenant_fixture(db_session, auth_db_session):
      """Khởi tạo đồng bộ bản ghi tenant ở cả content_db và auth_db chống lỗi 403."""
      ws_id = f"ws-test-{uuid.uuid4().hex[:8]}"
      user_id = f"user-test-{uuid.uuid4().hex[:8]}"
      
      # 1. Khởi tạo Workspace & User trong content_db
      from src.models.entities import Workspace, User
      ws = Workspace(id=ws_id, name="Test Studio", slug=ws_id)
      u = User(id=user_id, email=f"{user_id}@baha.vn", hashed_password="mock")
      db_session.add_all([ws, u])
      db_session.commit()
      
      # 2. Khởi tạo Membership & RoleAssignment trong auth_db
      from baha_auth.src.models.entities import (
          Workspace as AuthWorkspace, GlobalUser, Membership, Role, RoleAssignment
      )
      auth_ws = AuthWorkspace(id=ws_id, name="Test Studio", slug=ws_id, status="ACTIVE")
      auth_u = GlobalUser(id=user_id, email=f"{user_id}@baha.vn", status="ACTIVE")
      auth_db_session.add_all([auth_ws, auth_u])
      auth_db_session.commit()
      
      m = Membership(id=str(uuid.uuid4()), user_id=user_id, workspace_id=ws_id, status="ACTIVE")
      auth_db_session.add(m)
      auth_db_session.commit()
      
      r = auth_db_session.query(Role).filter(Role.code == "WORKSPACE_OWNER").first()
      if not r:
          r = Role(code="WORKSPACE_OWNER", name="Owner", is_template=True, status="ACTIVE")
          auth_db_session.add(r)
          auth_db_session.commit()
          
      ra = RoleAssignment(
          id=str(uuid.uuid4()), membership_id=m.id, role_id=r.id,
          workspace_id=ws_id, status="ACTIVE", granted_by=m.id, scope_type="WORKSPACE"
      )
      auth_db_session.add(ra)
      auth_db_session.commit()
      
      return {
          "workspace_id": ws_id,
          "user_id": user_id,
          "headers": auth_headers(user_id, ws_id, "WORKSPACE_OWNER")
      }
  ```
- **Trong các file test cũ (`test_tenancy.py`, `test_briefs.py`, `test_sources.py`):**
  - Thay thế toàn bộ lời gọi `headers={"X-Workspace-Id": ..., "X-User-Id": ...}` thành `headers=auth_headers(user_id, workspace_id, role)`.
- **Trong `test_scripts.py`:**
  - Sửa fixture `setup_p09_env` bảo đảm khởi tạo đầy đủ các bảng ORM `ScriptDraft`, `ClaimCheck`, `AllowedFact` trong database RAM trước khi insert dữ liệu mẫu.

#### 3. Lệnh Kiểm Thử Nghiệm Thu Giai Đoạn 0
```bash
python -m pytest 03_ban_lam_viec/sin_content_api/tests/test_health.py 03_ban_lam_viec/sin_content_api/tests/test_tenancy.py 03_ban_lam_viec/sin_content_api/tests/test_briefs.py 03_ban_lam_viec/sin_content_api/tests/test_sources.py 03_ban_lam_viec/sin_content_api/tests/test_scripts.py -v
```
**Tiêu chí hoàn thành:** 100% tests PASSED (Exit code 0), 0 lỗi 401 Unauthorized, 0 lỗi setup CSDL.

---

### GIAI ĐOẠN 1: ĐỒNG BỘ CSDL, ORM & HỢP ĐỒNG BACKEND/FRONTEND (DATA LAYER)
**Mục tiêu:** Xây dựng đầy đủ các thực thể và trường dữ liệu còn thiếu cho P10, P11, P12 ở cả backend ORM, Pydantic schemas và frontend TypeScript contracts.

#### 1. Tệp Cần Chỉnh Sửa
- `03_ban_lam_viec/sin_content_api/src/models/entities.py`
- `03_ban_lam_viec/sin_content_api/src/schemas/contracts.py`
- `03_ban_lam_viec/sin_creator_os/src/contracts/index.ts`

#### 2. Đặc Tả Kỹ Thuật Mã Nguồn
- **Trong `src/models/entities.py`:**
  1. *Mở rộng `SourceRecord`:*
     ```python
     is_paid = Column(Boolean, default=False, nullable=False)
     channel_id = Column(String(100), nullable=True, index=True)
     ```
  2. *Thêm thực thể `PublishedContentLink`:*
     ```python
     class PublishedContentLink(Base):
         __tablename__ = "published_content_links"
         id = Column(String(36), primary_key=True)
         workspace_id = Column(String(36), nullable=False, index=True)
         script_draft_id = Column(String(36), nullable=False, index=True)
         script_version = Column(Integer, nullable=False)
         published_url = Column(String(500), nullable=False)
         platform_post_id = Column(String(100), nullable=True)
         published_at = Column(DateTime(timezone=True), nullable=True)
         status = Column(String(30), default="ACTIVE", nullable=False) # ACTIVE, DETACHED, PURGED
         created_at = Column(DateTime(timezone=True), nullable=False)
     ```
  3. *Thêm thực thể `LearningSignal`:*
     ```python
     class LearningSignal(Base):
         __tablename__ = "learning_signals"
         id = Column(String(36), primary_key=True)
         workspace_id = Column(String(36), nullable=False, index=True)
         published_link_id = Column(String(36), ForeignKey("published_content_links.id"), nullable=False)
         signal_type = Column(String(50), nullable=False) # RETENTION_HOOK, AUDIENCE_OBJECTION, VELOCITY_PEAK
         insight_text = Column(Text, nullable=False)
         evidence_data_json = Column(Text, nullable=True)
         created_at = Column(DateTime(timezone=True), nullable=False)
     ```
  4. *Thêm thực thể `ExperimentSuggestion`:*
     ```python
     class ExperimentSuggestion(Base):
         __tablename__ = "experiment_suggestions"
         id = Column(String(36), primary_key=True)
         workspace_id = Column(String(36), nullable=False, index=True)
         based_on_signal_id = Column(String(36), ForeignKey("learning_signals.id"), nullable=False)
         hypothesis = Column(Text, nullable=False)
         suggested_action = Column(Text, nullable=False)
         status = Column(String(30), default="PROPOSED", nullable=False)
         created_at = Column(DateTime(timezone=True), nullable=False)
     ```
  5. *Ràng buộc duy nhất trên `TrendVelocityObservation`:*
     ```python
     __table_args__ = (
         UniqueConstraint("workspace_id", "from_observation_id", "to_observation_id", "metric_name", name="uq_velocity_obs_pair"),
     )
     ```

- **Trong `src/schemas/contracts.py`:**
  1. *Khóa cứng `IdeaReviewRequest`:*
     ```python
     class IdeaReviewRequest(BaseModel):
         action: Literal["APPROVE", "REJECT", "REQUEST_EVIDENCE", "REOPEN"]
         expected_version: int = Field(..., ge=1, description="Bắt buộc phiên bản mà reviewer đã xem xét")
         expected_status: str = Field(..., description="Bắt buộc trạng thái hiện tại trước khi chuyển trạng thái")
         review_reason: str = Field(..., min_length=3, description="Lý do đánh giá bắt buộc phục vụ audit")
     ```
  2. *Thêm DTOs phản hồi liên kết bài đăng & học tập:*
     - `PublishedLinkCreateRequest`, `PublishedLinkResponse`
     - `LearningSignalResponse`, `ExperimentSuggestionResponse`

- **Trong `sin_creator_os/src/contracts/index.ts`:**
  - Định nghĩa 1:1 các interface TypeScript tương ứng (`IdeaReviewRequestContract`, `PublishedContentLinkContract`, `LearningSignalContract`, `ExperimentSuggestionContract`).

#### 3. Lệnh Kiểm Thử Nghiệm Thu Giai Đoạn 1
```bash
python -m pytest 03_ban_lam_viec/sin_content_api/tests/test_migrations.py -v
```
**Tiêu chí hoàn thành:** Toàn bộ bảng ORM mới được khởi tạo hoàn hảo; migration up/down chạy thông suốt; hợp đồng Pydantic và TypeScript khớp 100%.

---

### GIAI ĐOẠN 2: TRIỂN KHAI TOÀN BỘ LOGIC BACKEND & BẢO MẬT GUARDS (SERVICE LAYER)
**Mục tiêu:** Khắc phục toàn bộ 27 phát hiện kỹ thuật trong tầng logic service và bảo vệ an toàn ranh giới dữ liệu.

#### 1. Tệp Cần Chỉnh Sửa
- `03_ban_lam_viec/sin_content_api/src/modules/ideation/ideation_service.py` (P10-02, P10-03)
- `03_ban_lam_viec/sin_content_api/src/modules/sources/router.py` (P10-04, P10-05)
- `03_ban_lam_viec/sin_content_api/src/modules/ingestion/service.py` (P11-05)
- `03_ban_lam_viec/sin_content_api/src/modules/feedback/channel_service.py` (P11-01, P11-02)
- `03_ban_lam_viec/sin_content_api/src/modules/feedback/velocity_engine.py` (P11-03, P11-04, P11-08)
- `03_ban_lam_viec/sin_content_api/src/modules/feedback/cohort_service.py` (P11-06, P11-09)
- `03_ban_lam_viec/sin_content_api/src/modules/feedback/router.py` (P11-07)
- `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/downstream_executor.py` (P12-01, P12-02, P12-05)
- `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/budget_guard.py` (P12-03, P12-04)
- `03_ban_lam_viec/sin_content_api/scripts/backup_staging_db.py` (P12-06)
- `03_ban_lam_viec/sin_content_api/scripts/restore_staging_db.py` (P12-07)

#### 2. Đặc Tả Kỹ Thuật Các Giải Pháp Then Chốt

1. **Khóa Lạc Quan & Atomic Review Update Tuân Thủ Bốn Mắt (`ideation_service.py`):**
   - Rào chắn nguyên tắc Bốn Mắt (Separation of Duties): Tác giả tạo thẻ ý tưởng tuyệt đối **KHÔNG ĐƯỢC PHÉP TỰ PHÊ DUYỆT (NO SELF-APPROVAL)**.
   ```python
   # Chặn sớm ở tầng Logic Service
   idea = db.query(IdeaCard).filter(IdeaCard.id == card_id, IdeaCard.workspace_id == workspace_id).first()
   if not idea:
       raise HTTPException(status_code=404, detail="IDEA_NOT_FOUND")
       
   if target_status == "APPROVED" and idea.created_by == reviewer_id:
       raise HTTPException(
           status_code=status.HTTP_403_FORBIDDEN,
           detail="SELF_APPROVAL_VIOLATION: Người tạo không được phép tự phê duyệt ý tưởng của chính mình (Quy tắc Bốn Mắt)."
       )

   # Khóa kép ở tầng Atomic SQL Update
   where_conds = [
       IdeaCard.id == card_id,
       IdeaCard.workspace_id == workspace_id,
       IdeaCard.version == request.expected_version,
       IdeaCard.status == request.expected_status
   ]
   if target_status == "APPROVED":
       where_conds.append(IdeaCard.created_by != reviewer_id)

   stmt = (
       update(IdeaCard)
       .where(*where_conds)
       .values(
           status=target_status,
           version=IdeaCard.version + 1,
           reviewed_by=reviewer_id,
           reviewed_at=datetime.now(timezone.utc),
           review_reason=request.review_reason
       )
   )
   result = db.execute(stmt)
   if result.rowcount == 0:
       raise HTTPException(status_code=409, detail="STALE_VERSION_CONFLICT")
   ```

2. **Xóa Mock Data & Xác Thực Scope Kênh Kỷ Luật (`channel_service.py`):**
   - Loại bỏ dictionary 45.000 follower / 86 video.
   - Khi chưa có quan sát chỉ số thật: Trả về `metrics = None`, `metrics_status = "METRICS_NOT_YET_OBSERVED"`.
   - Kiểm tra `token_expires_at < now()` hoặc `status == "EXPIRED"` &rarr; trả về `FEATURE_UNAVAILABLE` và `metrics = None`.

3. **Toán Học Vận Tốc An Toàn & Chuẩn Hóa Thời Gian (`velocity_engine.py`):**
   - Nếu `from_views is None` hoặc `to_views is None` &rarr; `rate_status = "NOT_AVAILABLE"`, `velocity_views_per_day = None`.
   - Tính toán theo giây thực tế: `delta_days = delta_seconds / 86400.0`.
   - Nếu `delta_seconds < 3600` (dưới 1 giờ): Từ chối với HTTP 422 `WINDOW_TOO_SHORT_FOR_VELOCITY`, cấm ép ngầm `0.0001`.
   - **Xử lý sụt giảm view do TikTok lọc bot (`to_views < from_views`):** Gán `velocity_status = "AUDIT_PURGED_ANOMALY"`, `velocity_views_per_day = 0.0` (chống số âm gây crash hàm logarit khi tính xếp hạng).
   - Upsert lũy đẳng: Nếu cặp `(from_obs_id, to_obs_id)` đã tồn tại trong `trend_velocity_observations` thì trả về bản ghi cũ, không tạo bản ghi mới.

4. **Bảo Toàn Cờ Quảng Cáo & Lọc Dữ Liệu Bẩn (`ingestion/service.py` & `cohort_service.py`):**
   - Ingestion map đúng `is_paid = raw.get("is_paid", False)` và `channel_id = raw.get("channel_id")`.
   - Cohort queries bắt buộc có: `WHERE SourceRecord.is_synthetic == False AND SourceRecord.is_purged == False`.
   - Thực thi bộ lọc `?cohort=ORGANIC`: Lọc triệt để các bài viết trả phí khỏi mảng dữ liệu trả về.

5. **Cách Ly Cache Đa Khách Thuê & Atomic Budget Update (`downstream_executor.py` & `budget_guard.py`):**
   - Khóa cache: `cache_key = f"{workspace_id}:{idempotency_key}"`.
   - Xác minh quyền sở hữu: `assert artifact.workspace_id == current_user.workspace_id`.
   - Tránh trừ phí lặp khi mất cache RAM: Kiểm tra `CostLedger` trong DB trước; nếu trạng thái `COMMITTED`, trả về artifact đã lưu với `charged_units = 0.0`.
   - Chặn vượt cap qua ledger cũ: Nếu ledger cũ có trạng thái `REFUSED_OVER_BUDGET`, bắt buộc thẩm tra lại ngân sách, không cho phép bypass.
   - **Atomic Budget Update tương thích đa CSDL (Bắt buộc khởi tạo nếu thiếu):**
     ```python
     # Đảm bảo dòng budget tồn tại cho tenant mới, tránh bị ném 402 vô lý
     budget_guard.get_or_create_budget(db, workspace_id=workspace_id, default_allocated=100.0)
     db.commit()

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

6. **Sao Lưu Tẩy Sạch Bí Mật & Khôi Phục Nguyên Tử An Toàn (`backup_staging_db.py` & `restore_staging_db.py`):**
   - Backup: Quét đệ quy toàn bộ chuỗi JSON, thay thế các pattern nhạy cảm (`access_token`, `refresh_token`, `api_key`, `secret`, `password`) thành `[SCRUBBED_IN_BACKUP]`. Chạy T012 scanner xác thực file backup sạch 100%.
   - Restore: Kiểm tra mã băm SHA256 và chạy `PRAGMA integrity_check` trên file backup trước khi chạm vào CSDL đích. Tạo bản sao lưu tạm `.target.bak` trước khi thực hiện atomic file replacement.

7. **Ranh Giới Khóa Tệp Ngăn Ngừa Hồi Quy Chéo Với Media Studio (Namespace Guard):**
   - Khi chỉnh sửa `entities.py`, `contracts.py`: Chỉ **thêm mới (append)** các thực thể Trí tuệ Nội dung, tuyệt đối không chỉnh sửa schema các bảng Media Studio (`MediaAsset`, `AIGenerationJob`, `ProductionProject`).
   - Mọi thay đổi phải chạy kiểm tra độc lập qua bộ test Trí tuệ Nội dung (`test_workbench.py`, `test_feedback_loop.py`, `test_staging_evaluation.py`) mà không gây ảnh hưởng lẫn nhau.

#### 3. Lệnh Kiểm Thử Nghiệm Thu Giai Đoạn 2
```bash
python -m pytest 03_ban_lam_viec/sin_content_api/tests/test_workbench.py 03_ban_lam_viec/sin_content_api/tests/test_feedback_loop.py 03_ban_lam_viec/sin_content_api/tests/test_staging_evaluation.py -v
```
**Tiêu chí hoàn thành:** 100% tests của P10, P11, P12 đều PASSED trong môi trường in-memory độc lập; 0 rò rỉ chéo tenant; 0 lỗi toán học.

---

### GIAI ĐOẠN 3: TÍCH HỢP GIAO DIỆN NGƯỜI DÙNG WORKBENCH (UI LAYER - P10)
**Mục tiêu:** Thay thế 100% dữ liệu mẫu trên giao diện BAHA Creator Studio bằng dữ liệu sống kết nối từ backend API; xây dựng hoàn chỉnh luồng kiểm duyệt 4 thao tác.

#### 1. Tệp Cần Chỉnh Sửa
- `03_ban_lam_viec/sin_creator_os/src/app/(main)/ideas/page.tsx`
- `03_ban_lam_viec/sin_creator_os/src/services/idea-service.ts`
- `03_ban_lam_viec/sin_creator_os/src/services/discover-service.ts`
- `03_ban_lam_viec/sin_creator_os/src/components/ideas/idea-review-modal.tsx` (Tạo mới)
- `03_ban_lam_viec/sin_creator_os/src/components/common/metric-coverage-badge.tsx` (Tạo mới)

#### 2. Đặc Tả Kỹ Thuật Giao Diện
1. **Kết Nối Client API Service:**
   - Trong `idea-service.ts`: Gọi `GET /v1/ideation/cards` kèm `Bearer token` và `X-Workspace-Id`.
   - Trong `discover-service.ts`: Gọi `GET /v1/sources/evidence/{id}` nạp dữ liệu trích dẫn thật.
2. **Hộp Thoại Kiểm Duyệt Thẻ Ý Tưởng (`IdeaReviewModal`):**
   - Hiển thị thông tin phiên bản hiện tại (`version`) và trạng thái (`status`).
   - Cung cấp 4 nút bấm tương ứng:
     - Duyệt (`APPROVE` - Màu xanh `#246849`)
     - Từ chối (`REJECT` - Màu đỏ cảnh báo)
     - Yêu cầu bổ sung chứng cứ (`REQUEST_EVIDENCE` - Màu vàng hổ phách)
     - Mở lại xem xét (`REOPEN` - Màu xanh thương hiệu `#2B6FB8`)
   - Ô nhập văn bản bắt buộc: `Lý do đánh giá (Review Reason)` tối thiểu 3 ký tự.
   - Truyền đầy đủ `expected_version` và `expected_status`. Khi gặp lỗi HTTP 409 Conflict, hiển thị thông báo: *"Thẻ ý tưởng đã được chỉnh sửa bởi người khác, vui lòng tải lại trang để xem phiên bản mới nhất."*
3. **Thẻ Hiển Thị Trạng Thái Chỉ Số (`MetricCoverageBadge`):**
   - Khi `metrics == null`: Hiển thị nhãn trung thực `CHƯA CÓ QUAN SÁT THỰC TẾ`.
   - Khi `observed_at > 30 ngày`: Hiển thị nhãn `SỐ LIỆU ĐÃ HẾT HẠN`.
   - Tuyệt đối cấm hiển thị `0 lượt xem` hoặc `Đang thịnh hành` khi thiếu dữ liệu.
4. **Quy Chuẩn Rule 9:** 100% biểu tượng sử dụng vector SVG Lucide, 0 unicode emoji.

#### 3. Lệnh Kiểm Thử Nghiệm Thu Giai Đoạn 3
- Chạy kiểm thử tự động Playwright E2E cho 8 màn hình chính:
  ```bash
  cd 03_ban_lam_viec/sin_creator_os && npx playwright test tests/e2e/workbench.spec.ts
  ```
- Lưu ảnh chụp màn hình nghiệm thu vào `08_kiem_thu/bang_chung/p10_ui_workbench/`.

---

### GIAI ĐOẠN 4: ĐÁNH GIÁ STAGING, QUÉT BẢO MẬT & ĐÓNG GÓI GATE P13 (AUDIT & HANDOFF)
**Mục tiêu:** Thực thi toàn bộ các bài đánh giá độc lập về chất lượng prompt, an ninh mã nguồn, kiểm toán giấy phép và chuẩn bị hồ sơ nghiệm thu chính thức trình Founder.

#### 1. Tệp Cần Chỉnh Sửa & Thực Thi
- `03_ban_lam_viec/sin_content_api/src/modules/staging_reliability/prompt_regression.py` (P12-08)
- `03_ban_lam_viec/sin_content_api/scripts/audit_licenses_and_deps.py` (P12-09)
- `03_ban_lam_viec/sin_content_api/scripts/scan_secrets.py` (T012)
- `03_ban_lam_viec/sin_content_api/docs/RELEASE_READINESS.md` (P12-10)
- `03_ban_lam_viec/sin_creator_os/bao_cao_nghiem_thu_tong_the_p10_p12.md` (Tạo mới)

#### 2. Đặc Tả Quy Trình Đánh Giá
1. **Đánh Giá Prompt Theo Quy Chuẩn Con Người (Human Quality Study Protocol):**
   - Chạy pipeline truy xuất và xếp hạng trên 3 customer briefs độc lập (Bento Box, Dưỡng da Serum, Trang phục thể thao).
   - Mỗi brief đánh giá tối thiểu >= 30 ứng viên với 2 chuyên gia đánh giá độc lập.
   - Tiêu chí qua cổng: Top 10 của cả 3 briefs đạt độ tương quan >= 80% (tổng thể >= 24/30 RELEVANT); 0 vi phạm từ khóa/chủ đề cấm; 0 số liệu bịa đặt.
2. **Kiểm Toán Giấy Phép & Phụ Thuộc Phần Mềm (T125):**
   - Quét chuẩn hóa toàn bộ dependencies; loại bỏ hoàn toàn extras.
   - Xác nhận: 0 thư viện cấm (loại trừ tuyệt đối `MediaCrawler`), 0 giấy phép copyleft thương mại trái phép, các mục chưa có offline advisory phải ghi rõ `NOT_CHECKED`.
3. **Quét Khóa Bí Mật Toàn Diện (T012):**
   - Quét 100% tệp trong `03_ban_lam_viec/`: Xác nhận 0 commit credentials, 0 rò rỉ token API.
4. **Cập Nhật Hồ Sơ Sẵn Sàng Phát Hành (`RELEASE_READINESS.md`):**
   - Khi 100% các tiêu chí trên đạt chuẩn, cập nhật trạng thái hệ thống: `STAGING_VERIFIED_PASS (READY FOR CANARY P13)`.
   - Lập biên bản bàn giao hoàn tất trình Founder ký duyệt phát hành.

---

## III. MA TRẬN PHÂN CÔNG & QUẢN TRỊ TRÁCH NHIỆM (RACI MATRIX)

| Hạng Mục Công Việc | Người Chủ Trì (Accountable / Responsible) | Người Hỗ Trợ (Consulted / Informed) | Bằng Chứng Nghiệm Thu |
|---|---|---|---|
| **Giai đoạn 0: Test Harness P00-RE** | **Codex** (Triển khai code tests) | **Antigravity** (Kiểm tra token spec) | Log Pytest P01-P09 xanh 100% |
| **Giai đoạn 1: Đồng bộ CSDL & Contracts** | **Codex** (Viết ORM & Pydantic) | **Antigravity** (Đối soát Schemas) | Pytest migrations & TypeScript check |
| **Giai đoạn 2: Sửa Backend Logic P10-P12** | **Codex** (Triển khai services & scripts) | **Antigravity** (Thẩm tra Atomic SQL) | Log Pytest P10, P11, P12 PASSED |
| **Giai đoạn 3: Tích hợp Frontend UI P10** | **Codex** (Nối UI & viết modal) | **Antigravity** (Duyệt UX & Safe Zone) | Ảnh chụp E2E Playwright 8 màn hình |
| **Giai đoạn 4: Đánh giá Staging & Quét QC** | **Antigravity** (Chủ trì QC & Audit) | **Codex** (Sửa lỗi phát sinh) | Báo cáo Gold Sets & Log T012 Exit 0 |
| **Ký Duyệt Mở Cổng Canary P13** | **Founder / Project Owner** | **Antigravity & Codex** | Quyết định phát hành chính thức |

---

## IV. CAM KẾT HIỆN TẠI: BẢN ĐẶC TẢ HOÀN TẤT — CHƯA CODE

Bản đặc tả này đóng gói toàn bộ giải pháp kỹ thuật, cấu trúc mã nguồn và lộ trình thi công chuẩn mực. Toàn bộ mã nguồn hệ thống hiện tại được giữ nguyên vẹn 100%. Đội ngũ sẵn sàng bắt tay thi công ngay khi nhận được lệnh khởi động chính thức từ Founder.
