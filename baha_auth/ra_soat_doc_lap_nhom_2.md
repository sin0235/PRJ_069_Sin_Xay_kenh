# Rà soát độc lập nhóm 2 — phê duyệt và worker

Ngày: 21/10/2026  
Phạm vi: `baha_auth` — dịch vụ/router phê duyệt và worker, schema, cùng caller tại `sin_content_workers/worker.py`.

## Thay đổi đã làm

Nhóm 2 chuyển luồng duyệt và grant worker sang dùng actor, policy, tài nguyên, phiên bản và hash do máy chủ đọc; runtime recheck cũng kiểm tra lại membership, quyền, policy, hạn dùng và binding trước khi caller chạy handler. Tôi đối chiếu các luồng này với báo cáo gốc mục 9–11, kế hoạch sửa, báo cáo nhóm 2, evidence và các caller liên quan.

SHA256 của năm file nhóm 2 trong gói rà soát khớp với file hiện tại. Evidence hiện có ghi nhận 29 bài kiểm thử service, 8 bài API, 4 bài AUTH-060/061/070/071 và compile đều đạt trên SQLite trong RAM; tôi không chạy lại các bài đó. Tôi kiểm tra riêng hai giả thuyết bằng ca cô lập trong RAM, không dùng database dự án hoặc mạng.

## Cần sửa trước nghiệm thu

### 1. [P1] Worker recheck không thiết lập tenant trước khi đọc grant

- **Ca cụ thể:** Sau khi áp dụng migration có `FORCE ROW LEVEL SECURITY`, worker có bearer hợp lệ gọi `/authz/v1/workers/recheck` với job đang có grant. Route gọi service mà không gắn workspace vào session (`src/api/worker_router.py:123–139`); câu đầu trong service tra grant bằng `job_id` trước khi có tenant (`src/services/worker_service.py:257–270`). Chính sách buộc `workspace_id` khớp `baha.current_workspace_id` (`di_chuyen_du_lieu/001_rang_buoc_tenant_va_nhat_ky.sql:214–240`), còn hook chỉ đặt GUC khi session đã có workspace tin cậy (`src/database.py:62–69`). Vì vậy PostgreSQL ẩn grant; nhánh từ chối tiếp tục ghi audit với `workspace_id=None`, cũng bị chính sách RLS từ chối, làm route trả lỗi 500 thay vì kết quả từ chối an toàn.
- **Bản chất:** Đây là lỗi nối luồng giữa worker của nhóm 2 và RLS; bộ kiểm thử SQLite hiện tại không thực thi chính sách PostgreSQL.
- **Sửa nhỏ nhất:** Dùng một truy vấn/hàm phía máy chủ được giới hạn cho worker đã xác minh để phân giải workspace từ job và subject; đặt GUC transaction-local trước các truy vấn ORM và audit tiếp theo. Không lấy tenant từ request worker.
- **Nếu bỏ qua:** Khi bật migration RLS, worker không thể xác thực grant hợp lệ và các lần recheck trả 500.

### 2. [P1] Owner có thể tự duyệt tài nguyên do người khác tạo

- **Ca cụ thể:** Tài nguyên có `creator_id=user-author`, `owner_id=user-reviewer`; người khác mở run, trưởng nhóm duyệt chặng đầu, rồi owner có role đúng duyệt chặng cuối. Điều kiện `actor.user_id == (resource.creator_id or resource.owner_id)` tại `src/services/approval_service.py:399–400` chỉ so sánh creator vì giá trị này có trước, nên owner được chấp thuận. Tôi tái hiện ca này trên SQLite chỉ trong RAM; quyết định của owner được ghi `APPROVED`.
- **Bản chất:** SoD hiện ngăn người tạo run và creator, nhưng bỏ sót owner khi creator khác owner.
- **Sửa nhỏ nhất:** Từ chối khi `actor.user_id` bằng bất kỳ giá trị không rỗng nào trong `{resource.creator_id, resource.owner_id}`.
- **Nếu bỏ qua:** Chủ sở hữu tài nguyên có thể tự ký duyệt tài nguyên mình sở hữu.

## Đã đối chiếu, chưa thấy lỗi trong phạm vi

Service nạp lại actor hiện hành, kiểm tra đúng tenant/tài nguyên/phiên bản/hash, yêu cầu đúng chặng đang chờ và xử lý phát lại cùng payload; grant worker giới hạn TTL tối đa 15 phút và action theo quyền actor hiện tại. Caller trong `sin_content_workers/worker.py:117–128` so khớp `job_id`, `action_key` và toàn bộ binding canonical trước khi handler chạy.

## Kết luận

Chưa nên nghiệm thu nhóm 2 trước khi sửa hai lỗi trên. Mô phỏng hook trong RAM xác nhận session không có workspace thì không đặt GUC; ca SoD riêng xác nhận owner khác creator vẫn duyệt được.

**Chưa kiểm chứng:** Chưa chạy PostgreSQL/RLS thật, kiểm thử đồng thời trên PostgreSQL, staging, production hoặc migration trên database dự án. Evidence hiện có dùng SQLite trong RAM nên chưa chứng minh được kết quả khi bật RLS.
