# Báo cáo sửa phân quyền — nhóm 1

Ngày thực hiện: 21/10/2026. Phạm vi nhóm 1 xử lý các phát hiện 1, 3, 4, 5, 6, 7, 8, 12, 13 và 14. Mã nguồn, cấu hình và kiểm thử chỉ thuộc `03_ban_lam_viec/baha_auth/`; không sửa `sin_content_api/`, worker nghiệp vụ hay giao diện.

## Kết quả

- Xác thực bearer token bên ngoài theo HS256, kiểm tra `iss`, `aud`, `sub`, `exp`, `nbf`; từ chối token sai định dạng, thời gian không hữu hạn, sai thuật toán hoặc thiếu cấu hình. Không có endpoint đăng nhập hay phát hành token. Workspace từ header chỉ chọn tenant; membership, trạng thái người dùng và các role assignment hiện hành được nạp từ DB.
- Bộ đánh giá quyền giữ các hợp đồng `ActorContext`, `ResourceContext`, `evaluate_permission` và `get_current_actor`. Chỉ role assignment đang hiệu lực, thuộc tenant, có role đang hoạt động và khớp cùng một phạm vi mới cấp quyền. Mã action lạ, actor thiếu định danh tin cậy và resource thuộc tenant khác đều bị từ chối.
- Cấp role/invite kiểm tra đúng assignment và tài nguyên trước khi ghi dữ liệu. Invite bị từ chối không tạo user, membership hay assignment; chỉ ghi sự kiện từ chối. Thu hồi owner bảo vệ owner hiệu lực cuối cùng, đồng thời cho phép thu hồi assignment đã hết hạn.
- `TenantService` kiểm tra quyền theo tài nguyên đã nạp từ DB cho đọc, tìm kiếm, sửa và tải media. Quyền tải media dùng `media.read`; URL trả về `None` khi chưa có dịch vụ ký URL.
- Helper danh tính chung là `baha_auth.src.services.danh_tinh_service.load_actor(db, workspace_id, membership_id)`. Helper kiểm toán `baha_auth.src.services.nhat_ky_kiem_toan.write_audit_event(db, *, workspace_id, actor_id, actor_type, action_key, decision, reason, policy_version, ...)` chỉ flush vào giao dịch của bên gọi, làm sạch metadata và băm resource ID. SQLite có trigger chặn sửa/xóa; migration PostgreSQL thêm trigger append-only.
- SQLite bật kiểm tra khóa ngoại trong test. Model và migration bổ sung khóa ngoại ghép theo workspace cho membership, tổ chức, resource, role assignment, approval run và worker grant; approval run có khóa duy nhất theo resource/version/policy và mỗi step chỉ có một quyết định. Ứng dụng không tự `create_all`; schema được quản lý bằng migration ngoại tuyến.

Các tệp chính trong phạm vi gồm `src/config.py`, `src/database.py`, `src/main.py`, `src/xac_minh_danh_tinh.py`, `src/api/deps.py`, các router role/org/evaluate/audit, `src/models/entities.py`, `src/policy/evaluator.py`, `src/policy/registry.py`, các service role/tenant/org cùng hai helper danh tính/kiểm toán, `tests/conftest.py`, `tests/test_a01_tenant_isolation.py`, `tests/test_kiem_tra_phan_quyen_nhom_1.py` và `di_chuyen_du_lieu/001_rang_buoc_tenant_va_nhat_ky.sql`.

## Phạm vi chưa hỗ trợ

Phạm vi PROJECT hiện chỉ được bộ đánh giá xử lý khi đã có role assignment và metadata project đáng tin cậy. API cấp vai trò và mời thành viên chưa có mô hình project chuẩn để xác minh scope nên vẫn từ chối cấp mới theo PROJECT; không xem đây là quy trình project đã hoàn tất. Cần mô hình và dữ liệu project được phê duyệt, di trú cùng kiểm thử trước khi mở thao tác này; không nhận project ID tùy ý từ client để cấp quyền.

Evaluator hiện hỗ trợ phạm vi `W` (WORKSPACE), `D` (DEPARTMENT), `T` (TEAM), `P` (PROJECT) và `S` (OWN). Các mã `B` (BRAND), `H` (CHANNEL), `R` (CLIENT_REVIEWED), `A` (OBJECT) và `O` (PLATFORM) chưa có ngữ cảnh thành viên/tài nguyên đáng tin cậy tương ứng nên bị từ chối. Trong `ROLE_PERMISSION_MATRIX.csv`, 43 action key có ít nhất một cặp role/action dùng các mã phạm vi chưa hỗ trợ: `ai_budget.read`, `ai_budget.update`, `analytics.export`, `analytics.read`, `brand.read`, `brand.update`, `brief.approve`, `brief.edit`, `brief.read`, `channel.connect`, `channel.manage_connection`, `channel.read`, `client.review`, `comment.read`, `comment.reply`, `evidence.export`, `evidence.read`, `ideas.approve_final`, `ideas.approve_team`, `ideas.create`, `ideas.edit`, `ideas.read`, `ideas.submit`, `media.approve`, `media.edit`, `media.read`, `platform.ops.manage`, `project.assign`, `project.create`, `project.read`, `publishing.cancel`, `publishing.execute`, `publishing.schedule`, `research.read`, `research.run`, `script.approve_final`, `script.approve_team`, `script.create`, `script.edit`, `script.read`, `script.submit`, `security.support_access`, `workspace.read`. Từ chối áp dụng cho các cặp role/action có scope tương ứng; không khẳng định đã hỗ trợ đủ 15 role/58 action. Action không có trong registry cũng bị từ chối mặc định.

## Kiểm thử và bằng chứng

| Lệnh | Kết quả | Mã thoát |
|---|---:|---:|
| `python -m pytest -q tests/test_kiem_tra_phan_quyen_nhom_1.py tests/test_a01_tenant_isolation.py` | 32 passed; 1 cảnh báo Starlette/httpx | 0 |
| `python -m pytest -q tests/test_a02_a07_comprehensive.py -k "auth_020 or auth_021 or auth_030 or auth_040 or auth_044"` | 5 passed, 4 deselected | 0 |
| `python -m compileall -q src tests` | Thành công, không có đầu ra | 0 |

Các kiểm thử chạy ngoại tuyến với `DATABASE_URL=sqlite:///:memory:` và `BAHA_AUTH_DATABASE_URL=sqlite:///:memory:`. Hash SHA-256 và đầu ra lệnh được lưu tại [bằng chứng nhóm 1](../../08_kiem_thu/bang_chung/bang_chung_phan_quyen_nhom_1_2026_10_21.txt).

## Giới hạn xác minh

Migration `di_chuyen_du_lieu/001_rang_buoc_tenant_va_nhat_ky.sql` chỉ được tạo và rà soát tĩnh, chưa chạy. Không có PostgreSQL/`psql` sẵn sàng; RLS, khóa ngoại và trigger trên PostgreSQL được ghi nhận **NOT TESTED**, không suy ra PASS từ SQLite. Không kết nối DB dự án hoặc gọi dịch vụ thật. Nhà cung cấp danh tính thật chưa được cấu hình/tích hợp; URL media chưa có dịch vụ ký. Bộ test tích hợp cùng nhóm 2/3 và toàn bộ 15 role/58 action chưa được nghiệm thu trong báo cáo nhóm này.
