# Kế hoạch thi công: Làm lại shot và quay lại bước tạo video

> Agent triển khai: Codex trong phiên hiện tại theo lệnh trực tiếp của Founder.

**Mục tiêu:** Retry từ shot được chọn, cho phép làm mới một hoặc toàn bộ shot và làm mất hiệu lực kết quả phía sau khi lưu revision nội dung/storyboard mới.

**Kiến trúc:** Backend tạo run mới từ receipt của plan đã duyệt, sao chép asset của các shot không được chọn và chỉ đặt shot cần làm mới về `READY`. Sửa storyboard đã duyệt tạo revision nháp mới; lịch sử hiện hành chỉ trả run thuộc revision mới nhất. Giao diện giữ project Flow cũ mặc định và cho phép chuyển sang project mới từ shot đó sau khi thao tác với project cũ bị chặn.

**Tech stack:** FastAPI, Pydantic, SQLAlchemy, Next.js, React, TypeScript; không thêm dependency hoặc migration.

**Spec:** `00_bat_dau/COMMAND_CONTROL_CARD.md`, thẻ `lam_lai_shot_va_quay_lui_video_20261026`.

## Ràng buộc toàn cục

- Chỉ sửa mã và kịch bản trong `03_ban_lam_viec/`; dữ liệu nguồn và bản nguyên mẫu giải nén giữ nguyên.
- Tên file/thư mục tiếng Việt không dấu, chữ thường, snake_case; nội dung và UI tiếng Việt có dấu; không dùng emoji hoặc unicode icon.
- Không gọi Flow, không chạy migration trên DB dự án, không đổi checkpoint hoặc production.
- Giữ media cũ trong thư viện; revision mới không coi run cũ là kết quả hiện hành.

## Điểm rà soát

- Retry một shot hoàn tất phải giữ clip của shot còn lại; retry run đang lỗi phải bắt đầu ở shot chưa hoàn tất đầu tiên.
- Shot ở `SUBMITTING`/`NEEDS_RECONCILIATION` không được gửi lại nếu người dùng chưa xác nhận Flow không tạo clip.
- Project Flow mới phải bỏ URL cũ, nhưng vẫn giữ clip thành công trước shot được retry.
- Sửa storyboard không được sửa receipt/plan đã duyệt tại chỗ; phải tạo revision nháp cần duyệt lại.
- Lịch sử dự án không được ghép run của revision cũ vào plan mới nhất.

---

### Task 1: Hợp đồng retry, revision storyboard và kiểm thử backend

**Files:**
- Modify: `03_ban_lam_viec/sin_content_api/src/modules/tao_video_noi_dung/contracts.py`
- Modify: `03_ban_lam_viec/sin_content_api/src/modules/tao_video_noi_dung/service.py`
- Modify: `03_ban_lam_viec/sin_content_api/src/modules/tao_video_noi_dung/router.py`
- Modify: `03_ban_lam_viec/sin_content_api/src/modules/tao_video_noi_dung/runner.py`
- Test: `03_ban_lam_viec/sin_content_api/tests/test_content_video_pipeline.py`

**Interfaces:**
- Tạo `RetryRunRequest(shot_ids, new_flow_project, confirm_no_flow_clip, idempotency_key)` và `retry_run(db, project_id, run_id, workspace_id, user_id, request)`.
- Retry trả run mới với receipt được dựng lại cho run mới; asset của shot được giữ nguyên được tái sử dụng.
- `update_plan` trên plan đã duyệt trả revision mới ở trạng thái `DRAFT`; `get_latest_history` chỉ ghép run với plan mới nhất.

- [ ] Viết test cho retry shot chọn lọc, retry tất cả, project mới, xác nhận shot bất định, sửa plan đã duyệt thành revision mới và lịch sử không trả run cũ.
- [ ] Chạy test mục tiêu để xác nhận lỗi do hợp đồng/hành vi chưa tồn tại.
- [ ] Triển khai endpoint retry, sao chép clip đúng phạm vi và lưu URL project mới vào shot đang được gửi.
- [ ] Chạy `python -m pytest tests/test_content_video_pipeline.py -q` trong `03_ban_lam_viec/sin_content_api`; kết quả dự kiến: toàn bộ test pipeline đạt.

### Task 2: Điều khiển quay lại và làm mới shot trên giao diện

**Files:**
- Modify: `03_ban_lam_viec/sin_creator_os/src/lib/api/content-video-api.ts`
- Modify: `03_ban_lam_viec/sin_creator_os/src/app/(main)/video-studio/[projectId]/production/_components/content_video_production.tsx`

**Interfaces:**
- API client gọi endpoint retry với danh sách shot, lựa chọn project Flow và xác nhận không có clip khi cần.
- Giao diện cho phép quay lại sửa nội dung/storyboard; lưu nội dung tạo plan mới, lưu storyboard đã duyệt tạo revision mới và bỏ run cũ khỏi luồng hiện hành.
- Run hoàn tất có thao tác làm mới từng shot và tất cả shot; project Flow mới chỉ là lựa chọn phục hồi sau khi project cũ không dùng được.

- [ ] Nối API retry và thêm các thao tác sửa/quay lại cùng trạng thái xác nhận an toàn.
- [ ] Chạy `npm run build` trong `03_ban_lam_viec/sin_creator_os` và mechanical detector của Impeccable; kết quả dự kiến: build đạt, detector không báo lỗi chặn.
- [ ] Chạy lại test backend của Task 1 sau tích hợp và lưu bằng chứng nghiệm thu.
