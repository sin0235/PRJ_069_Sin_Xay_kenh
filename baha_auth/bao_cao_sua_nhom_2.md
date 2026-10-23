# Báo cáo sửa nhóm 2: phê duyệt và worker

Ngày cập nhật: 21/10/2026  
Phạm vi: `baha_auth` — dịch vụ/router phê duyệt và worker, helper xác minh danh tính, evaluator SoD, schema và kiểm thử liên quan.

## Kết quả vòng rà soát 1

Đã khắc phục hai P1 được nêu trong rà soát độc lập. Worker recheck chỉ dùng `workspace_id` trong bearer JWT đã ký: helper xác minh claim tùy chọn và kiểm tra kiểu, độ dài, khoảng trắng; route worker bắt buộc claim này, gắn tenant context trước truy vấn đầu tiên, xác nhận workspace đang hoạt động và truyền tenant đã xác minh vào service. Service lọc grant và resource theo cả job lẫn workspace. Khi không tìm được grant, audit DENY vẫn gắn workspace từ token; response DENY không trả binding resource.

Evaluator và approval service coi cả `owner_id` lẫn `creator_id` là bên có lợi ích; cả hai đều không thể tự duyệt, ngoài kiểm tra người tạo approval run. Các action approve/review/override bị từ chối nếu thiếu ResourceContext hoặc resource thiếu cả owner lẫn creator. Approval service từ chối attribution thiếu trước khi tạo decision.

Worker token cần được nhà cung cấp bên ngoài ký riêng cho một workspace. Workspace không lấy từ body, header, queue hay job ID. Worker pool hiện dùng token theo tenant được ký; chưa xác minh cơ chế cấp/luân chuyển token nhiều tenant tại runtime.

## Tệp đã sửa hoặc cập nhật

- `src/api/worker_router.py`: bắt buộc signed workspace claim, gọi `set_tenant_context` trước truy vấn, kiểm tra workspace ACTIVE, truyền workspace đã xác minh vào service.
- `src/services/worker_service.py`: yêu cầu `expected_workspace_id`; lọc grant và resource theo tenant, ghi audit DENY theo tenant đã xác minh kể cả khi không có grant.
- `src/xac_minh_danh_tinh.py`: thêm `VerifiedIdentity.workspace_id` tùy chọn; claim nếu có phải là chuỗi không rỗng, không khoảng trắng thừa và tối đa 36 ký tự. JWT người dùng vẫn không cần claim này.
- `src/policy/evaluator.py`: từ chối approve/review/override khi thiếu resource hoặc thiếu attribution; chặn cả owner và creator tự duyệt.
- `src/services/approval_service.py`: chặn owner/creator và run creator; từ chối resource thiếu owner lẫn creator trước khi ghi quyết định.
- `src/api/approval_router.py`, `src/schemas/contracts.py`: thuộc bộ thay đổi nhóm 2 ban đầu; không thay đổi trong vòng sửa P1 này.
- `tests/test_kiem_thu_duyet_tac_vu_nen.py`: thêm hồi quy tenant JWT, audit/context sau commit, SoD owner/creator, resource context/attribution và xác minh claim.
- `tests/test_kiem_thu_duyet_tac_vu.py`: bộ kiểm thử hiện có được bao gồm trong suite đầy đủ.
- `tests/test_api_endpoints.py`: worker bearer fixture ký kèm workspace claim.
- `tests/test_a02_a07_comprehensive.py`: truyền tenant tường minh cho service recheck trong các ca worker.

## Kiểm thử và bằng chứng

Các ca riêng dùng SQLite RAM; không kết nối cơ sở dữ liệu dự án. Bằng chứng đầy đủ nằm tại [`kiem_thu_nhom_2_approval_worker_2026_10_21.txt`](../../08_kiem_thu/bang_chung/kiem_thu_nhom_2_approval_worker_2026_10_21.txt).

- TDD RED vòng 1 trước khi sửa nguồn: 4 test thất bại đúng kỳ vọng, gồm owner được evaluator cho qua, worker token không workspace vẫn nhận 200, token workspace khác có thể tìm grant, và truy vấn đầu chưa có tenant context (19 test khác được lọc; exit 1).
- TDD RED cho kiểm tra tổng quát approve/review: 3 test thất bại với lý do kỳ vọng (thiếu ResourceContext, thiếu attribution, approval service trả lỗi stale thay vì attribution); test xác minh claim độc lập đã qua. 3 failed, 1 passed, 23 deselected; exit 1.
- `python -m pytest --noconftest -q --tb=short tests/test_kiem_thu_duyet_tac_vu_nen.py`: **27 passed**, exit 0.
- `python -m pytest -q --tb=short tests/test_api_endpoints.py`: **8 passed**, exit 0.
- `python -m pytest -q --tb=short tests/test_a02_a07_comprehensive.py -k 'worker or approval'`: **3 passed, 6 deselected**, exit 0.
- `python -m pytest -q --tb=short tests`: **86 passed**, exit 0.
- `python -m compileall -q src/services/approval_service.py src/services/worker_service.py src/api/approval_router.py src/api/worker_router.py src/schemas/contracts.py src/xac_minh_danh_tinh.py src/policy/evaluator.py tests/test_api_endpoints.py tests/test_a02_a07_comprehensive.py tests/test_kiem_thu_duyet_tac_vu_nen.py`: exit 0.
- Một lệnh chọn test cũ dùng nhầm tên `tests/test_kiem_thu_phan_quyen_nhom_1.py` trả exit 1 do file không tồn tại; suite đầy đủ sau đó chạy thành công và bao gồm file thật `tests/test_kiem_tra_phan_quyen_nhom_1.py`.
- Tích hợp P09: agent kiểm tra báo POST approve của owner khi thiếu resource context trả 403, không gọi service và không đổi row/audit. Test được tạo sau khi evaluator đã sửa nên không có RED riêng cho route; bộ tích hợp P09 đầy đủ có bằng chứng riêng.

Một cảnh báo tương thích Starlette/httpx xuất hiện trong TestClient; không làm fail test.

## Hash nguồn

SHA-256 tổng hợp của các tệp nhóm 2 được liệt kê trong bằng chứng: `14c7f4d405ea80921441892bb22cd6b5b31bd7918d6f04dd4abbe5659021da79`. Bằng chứng cũng ghi hash riêng từng tệp.

## Drift quan sát được

`sin_content_api/src/modules/briefs/router.py` hiện dùng `require_resolved_resource_action("brief.approve")`. Tệp này nằm ngoài phạm vi nhóm 2 và không được sửa trong lượt này.

## Giới hạn

**PostgreSQL/RLS và concurrency thực tế: NOT TESTED.** SQLite RAM chỉ xác nhận service lọc tenant, audit DENY có workspace, và test mô phỏng hook `set_config` với connection giả; không xác nhận PostgreSQL thật áp dụng RLS hay hành vi transaction khi commit/rollback dưới tải. Chưa gọi provider, staging, production hoặc migration thật. Không dùng SECURITY DEFINER, truy vấn all-tenant hay bypass bằng service account.


