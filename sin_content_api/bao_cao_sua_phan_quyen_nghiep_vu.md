# Báo cáo tích hợp phân quyền nghiệp vụ

Ngày: 2026-10-21

## Kết quả

- API nghiệp vụ chỉ lấy danh tính từ bearer JWT do nhà cung cấp bên ngoài phát hành. `X-User-Id` không còn là nguồn danh tính, actor hoặc role mặc định; dependency legacy `require_role` từ chối. `X-Workspace-Id` chỉ chọn tenant; dịch vụ xác minh membership hiện hành trong kho Baha Auth chuẩn và workspace tương ứng trong kho nghiệp vụ. Hai cơ sở dữ liệu được cấu hình riêng; thiếu cấu hình hoặc membership thì từ chối. Secret offline mặc định đã bị xóa khỏi cấu hình API.
- Tất cả route `/v1/` có metadata action RBAC. Route danh sách/tìm kiếm không có bộ lọc tổ chức đáng tin cậy chỉ chấp nhận grant scope `WORKSPACE`. Route có tài nguyên cụ thể tải row từ tenant trước, sau đó kiểm tra action bằng `ResourceContext`; trường tổ chức, chủ sở hữu hoặc người tạo bị thiếu thì scope tương ứng bị từ chối. Quyết định được ghi vào nhật ký Baha Auth; tenant context được gắn lại trước mỗi transaction audit.
- Tạo brief nháp dùng action đã đăng ký `brief.edit` theo ràng buộc soạn thảo trong registry; kiểm thử xác nhận WORKSPACE_OWNER được tạo và GUEST bị từ chối. Không tạo alias `brief.create` hoặc thêm quyền mới.
- Worker ánh xạ tác vụ sang action nội bộ, gửi recheck ngay trước handler tới URL cấu hình tường minh, chỉ truyền `job_id` và action. Queue ghim snapshot JSON và binding gồm workspace, resource, loại resource, phiên bản, hash và phiên bản chính sách ngay khi enqueue; payload bị sửa sau đó, recheck trả binding khác, thiếu cấu hình, timeout, lỗi HTTP/JSON hoặc HTTP không mã hóa tới máy chủ ngoài loopback đều chặn handler. Handler chỉ nhận bản sao từ snapshot đã đối chiếu; redirect và phát lại job đều bị chặn.
- Trang nhóm giữ năm tab và bố cục prototype hiện có, bỏ dữ liệu mẫu về thành viên, sơ đồ, ma trận quyền, phê duyệt và audit. Trang thông báo rõ dữ liệu chưa kết nối; thao tác tạo phòng ban và mời thành viên đang tắt.

## Tệp thay đổi

- API: `src/auth/tenancy.py`, `src/config.py`; router `src/modules/briefs/router.py`, `ingestion/router.py`, `ideation/router.py`, `research/router.py`, `retrieval/router.py`, `sources/router.py`, `understanding/router.py`, `workspaces/router.py`; `src/modules/sources/provider_protocol.py`; kiểm thử `tests/test_tich_hop_phan_quyen.py`.
- Worker: `worker.py`; kiểm thử `tests/test_kiem_tra_quyen_worker.py`.
- Giao diện: `src/app/(main)/team/page.tsx` trong `sin_creator_os`.
- Báo cáo này nằm trong `sin_content_api` theo phạm vi được giao.

## Kiểm thử và bằng chứng

| Lệnh | Kết quả | Bằng chứng |
|---|---|---|
| `python -m pytest -q tests/test_tich_hop_phan_quyen.py` tại `sin_content_api` | Mã thoát 0; 9 passed, 3 cảnh báo | `08_kiem_thu/bang_chung/nhom3_tich_hop_phan_quyen_api_20261021.txt` |
| `python -m pytest -q tests/test_kiem_tra_quyen_worker.py` tại `sin_content_workers` | Mã thoát 0; 14 passed | `08_kiem_thu/bang_chung/nhom3_tich_hop_phan_quyen_worker_20261021.txt` |
| `python -m compileall -q src` tại `sin_content_api` | Mã thoát 0 | `08_kiem_thu/bang_chung/nhom3_tich_hop_phan_quyen_compile_20261021.txt` |
| `python -m py_compile worker.py` tại `sin_content_workers` | Mã thoát 0 | `08_kiem_thu/bang_chung/nhom3_tich_hop_phan_quyen_compile_20261021.txt` |

Kiểm thử API nạp API nghiệp vụ và kho Baha Auth chuẩn trong cùng tiến trình. Hai engine dùng hai SQLite named-memory riêng; biến môi trường được đặt trước import. Fixture tạo thành viên thuộc hai team nhưng chỉ có grant cho một team, xác nhận grant đó không mở team còn lại hay danh sách toàn tenant; kiểm thử cũng xác nhận thay ID sang tài nguyên đồng nghiệp cùng tenant bị từ chối. Bộ kiểm thử duyệt cả router FastAPI đã include lười, kiểm tra mọi route nghiệp vụ có action metadata và xác nhận route dùng guard theo resource gọi `authorize_resource`. Tập action chưa có trong registry được xác nhận chính xác là `workspace.create`, `evidence.import` và `evidence.purge`. `tests/conftest.py` chỉ thêm thư mục API vào `sys.path`, không khởi tạo engine hoặc truy cập cơ sở dữ liệu.

## Giới hạn và công việc cần trước khi triển khai

- Chưa chạy migration hay dry-run đối chiếu membership, workspace và ID nghiệp vụ hiện tại. Cần chạy dry-run trên bản sao dữ liệu được phê duyệt, đối chiếu ID giữa hai kho và xử lý các bản ghi không khớp trước rollout. Không truy vấn cơ sở dữ liệu ứng dụng hiện tại trong lượt này.
- Schema nghiệp vụ hiện thiếu metadata đáng tin cậy như `org_unit_id`, `project_id`, `owner_id` và `creator_id` trên nhiều tài nguyên. Vì vậy API chỉ cấp quyền danh sách theo scope workspace; grant team/project/own trên những hàng thiếu metadata sẽ bị từ chối. Cần migration và backfill có kiểm chứng trước khi mở các scope đó.
- Các route có action chưa đăng ký tiếp tục bị đóng: `POST /v1/workspaces` (`workspace.create`), `POST /v1/ingestion/batch` và `POST /v1/sources/customer-import` (`evidence.import`), `DELETE /v1/ingestion/purge/{source_record_id}` (`evidence.purge`). Chỉ mở sau khi registry/ma trận được phê duyệt và kiểm thử. Phê duyệt brief/idea tiếp tục đóng khi chưa có creator attribution để kiểm tra phân tách nhiệm vụ.
- Các suite legacy `tests/test_briefs.py`, `test_tenancy.py`, `test_ingestion.py`, `test_ideation.py`, `test_planning_and_gold.py`, `test_retrieval.py`, `test_scripts.py`, `test_sources.py` và `test_understanding.py` còn dùng `X-User-Id` hoặc giả định role cũ; không cập nhật hay chạy chúng trong lượt này. Chỉ chạy bộ security test cô lập đã nêu ở trên; không monkeypatch header thành token.
- Worker cần `BAHA_AUTHZ_BASE_URL` và token service principal được cấp ngoài tiến trình. Không gọi provider, dịch vụ phân quyền từ xa hay production trong kiểm thử.
- Chỉ dùng SQLite RAM; PostgreSQL RLS chưa được xác minh. Cần kiểm thử policy/transaction RLS trên môi trường kiểm thử riêng trước triển khai. Giao diện React chưa chạy build/lint theo quy tắc cục bộ yêu cầu lệnh explicit.

