# Kiểm tra che giấu brief ngoài workspace

Ngày: 2026-10-21

## Kết quả

`GET /v1/briefs/{brief_id}` giờ trả cùng `404` khi ID không tồn tại hoặc brief thuộc workspace khác. Handler chỉ truy vấn theo đồng thời `brief_id` và `ctx.workspace_id`; đã bỏ truy vấn toàn cục dùng để phân biệt brief ngoại tenant.

Regression test dùng owner có bearer JWT hợp lệ trong workspace hiện tại, seed một brief ở workspace khác và gọi thêm ID ngẫu nhiên. Test xác nhận hai phản hồi có cùng mã lỗi sau khi bỏ `correlation_id` riêng theo request, không chứa ID/tên brief ngoại tenant, không tạo `AuditEvent`, và không thay đổi row được seed.

## Kiểm thử và bằng chứng

| Lệnh | Kết quả | Bằng chứng |
|---|---|---|
| `python -m pytest -q tests/test_tich_hop_phan_quyen.py::test_brief_o_workspace_khac_va_id_khong_ton_tai_cung_tra_404` trước sửa | RED: brief ngoại tenant trả `403`, ID ngẫu nhiên trả `404` | `08_kiem_thu/bang_chung/kiem_tra_fix_brief_chi_tiet_red_20261021.txt` |
| Cùng lệnh sau sửa | 1 passed, 3 cảnh báo | `08_kiem_thu/bang_chung/kiem_tra_fix_brief_chi_tiet_green_20261021.txt` |
| `python -m pytest -q tests/test_tich_hop_phan_quyen.py` | 11 passed, 3 cảnh báo | `08_kiem_thu/bang_chung/kiem_tra_fix_brief_chi_tiet_suite_20261021.txt` |

Hai cơ sở dữ liệu của suite dùng SQLite named-memory và được cấu hình trước import ứng dụng. `tests/conftest.py` chỉ thêm API root vào `sys.path`; không truy cập database thật, provider hay production. Các cảnh báo là deprecation từ Starlette/httpx và SQLAlchemy SQLite in-memory.

Chỉ thay đổi handler `get_brief` cùng regression test tích hợp này. Không sửa các route P09 hay route khác.
