# Kiểm tra tích hợp cuối phân quyền API

Ngày: 2026-10-21

## Kết quả

Đã thêm một regression test cho `POST /v1/scripts/{script_id}/approve`. Test tạo owner có JWT hợp lệ cùng script và ý tưởng trong SQLite RAM, rồi xác nhận request bị từ chối `403`, handler service không được gọi, trạng thái script và thông tin phê duyệt không đổi, đồng thời không phát sinh audit `SCRIPT_APPROVE`. Test dùng evaluator và danh tính thật; chỉ theo dõi lời gọi service để xác nhận authorization chặn trước nghiệp vụ.

## Rà soát route P09

Route coverage hiện có xác nhận mỗi route `/v1/` khai báo action và action thuộc registry hoặc thuộc danh sách ngoại lệ. Phần kiểm tra resource chỉ áp dụng khi dependency tự khai báo `requires_resource_authorization`; vì vậy test coverage không tự phát hiện các route `require_action` chưa có `ResourceContext`.

Các route P09 dưới đây chưa có kiểm tra phạm vi theo row/creator trong router:

- `GET /v1/scripts/{script_id}` dùng `script.read` tổng hợp.
- `POST /v1/scripts/{script_id}/edit` và `POST /v1/scripts/{script_id}/reject` dùng `script.edit` tổng hợp.
- `POST /v1/scripts` nhận `idea_id`, sau đó service tải ý tưởng theo workspace; route yêu cầu `script.create` và `ideas.read` tổng hợp.

Các route trên hiện chỉ được chứng minh theo grant `WORKSPACE`; chưa có kiểm thử tích cực cho resource thuộc phạm vi `OWN`, `TEAM` hoặc `PROJECT`. Báo cáo này ghi nhận thiếu coverage theo phạm vi, không kết luận có IDOR khi chưa có ca tái hiện. Model `IdeaCard` và `ScriptDraftVersion` hiện không có metadata creator đáng tin cậy để router chuyển vào resource context.

## Kiểm thử và bằng chứng

| Lệnh | Kết quả | Bằng chứng |
|---|---|---|
| `python -m pytest -q tests/test_tich_hop_phan_quyen.py::test_workspace_owner_khong_duyet_script_khi_thieu_tai_nguyen_tin_cay_va_nguoi_tao` | 1 passed, 3 cảnh báo | `08_kiem_thu/bang_chung/kiem_tra_tich_hop_cuoi_p09_don_le_20261021.txt` |
| `python -m pytest -q tests/test_tich_hop_phan_quyen.py` | 10 passed, 3 cảnh báo; giữ xanh cả 9 test cũ | `08_kiem_thu/bang_chung/kiem_tra_tich_hop_cuoi_suite_20261021.txt` |

Hai URL SQLite được cấu hình ở đầu test module trước các import ứng dụng. `tests/conftest.py` chỉ thêm thư mục API vào `sys.path`; test không gọi provider, database thật hay production. Ba cảnh báo là deprecation từ Starlette/httpx và SQLAlchemy SQLite in-memory.

Evaluator được cập nhật trước lượt chạy test này, nên không có kết quả RED trước sửa trong bằng chứng của lượt tích hợp. Lượt test đầu tiên và suite đều chạy sau cập nhật và đạt GREEN.

## Giới hạn

Chưa kiểm thử PostgreSQL/RLS, grant resource `OWN`/`TEAM`/`PROJECT` cho các route P09 còn lại, hoặc môi trường staging/production. Chưa sửa router/service P09 theo giới hạn phân công.
