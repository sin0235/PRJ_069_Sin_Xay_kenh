# Rà soát độc lập tổng hợp phân quyền

Ngày: 21/10/2026  
Phạm vi: đọc source hiện có của `baha_auth`, migration PostgreSQL, điểm gọi từ API/worker và trạng thái giao diện; đối chiếu với RBAC contracts, guardrails và ma trận vai trò. Không sửa source, không chạy lại các bộ test đã có bằng chứng và không kết nối database/dịch vụ thật.

Gói `goi_ra_soat_tong_hop.md` là snapshot source kèm SHA-256, không phải diff. Kho chưa có HEAD/baseline để kết luận thay đổi nào thuộc patch. Một số file nhóm 2 đã cập nhật sau snapshot; phần nhóm 2 trong báo cáo này đọc trực tiếp source hiện tại.

## Phát hiện và trạng thái xử lý

### [P2 — ĐÃ ĐÓNG BẰNG LÀM RÕ PHẠM VI] PROJECT

`RoleAssignmentRequest.scope_type` nhận `PROJECT` tại `baha_auth/src/schemas/contracts.py:98` và evaluator có nhánh so khớp project tại `baha_auth/src/policy/evaluator.py:81,104-107`, nhưng `_scope_resource()` từ chối cấp role/invite PROJECT tại `baha_auth/src/services/role_service.py:45-46` vì Baha Auth chưa có model/resolver project chuẩn. Báo cáo nhóm 1 hiện nói rõ P chỉ được đánh giá khi đã có assignment và metadata project tin cậy; API chưa cấp P và không xem đây là workflow hoàn chỉnh. Giới hạn này fail-closed, không phải cấp quyền rộng; chưa cần mở project model trong đợt sửa hiện tại.

### [P2 — ĐÃ SỬA VÀ ĐỐI CHIẾU] Dò sự tồn tại của brief khác tenant

Source trước sửa tại `sin_content_api/src/modules/briefs/router.py:143-154` phân biệt ID tenant khác bằng 403 với ID không tồn tại bằng 404. Source hiện tại chỉ truy vấn đồng thời `brief_id` và `ctx.workspace_id`, rồi trả 404 nếu không có hàng; không còn truy vấn toàn cục. Bằng chứng regression ghi nhận RED `403` so với `404`, targeted GREEN `1 passed`, suite tích hợp `11 passed`, dùng SQLite named-memory; xem `sin_content_api/kiem_tra_lo_lo_ton_tai_brief.md` và `08_kiem_thu/bang_chung/kiem_tra_fix_brief_chi_tiet_*.txt`.

Không còn phát hiện P0/P1/P2 đang mở trong phạm vi source đã rà soát.

## Các kiểm tra source khác

- Xác thực API nghiệp vụ lấy user từ bearer đã xác minh, kiểm tra membership hiện hành trong Baha Auth và workspace nội dung riêng; thiếu cấu hình/kết nối từ chối. `X-Workspace-Id` chỉ chọn workspace, không tạo membership. Các router đã include có action metadata; truy vấn danh sách lọc theo tenant, truy vấn object dùng hàng đã nạp từ tenant trước khi gọi guard. Không thấy `X-User-Id` được dùng làm danh tính.
- Evaluator kiểm tra trạng thái membership/user/workspace, role và assignment, khoảng hiệu lực, tenant của resource và giao giữa policy scope với scope assignment. Các scope B/H/R/A/O không được cho phép khi chưa có resolver tin cậy. Các action chưa đăng ký `workspace.create`, `evidence.import`, `evidence.purge` tiếp tục bị từ chối.
- Trong source nhóm 2 hiện tại, evaluator từ chối action phê duyệt/duyệt khi thiếu resource hoặc thiếu attribution owner/creator và ngăn actor trùng một trong hai. Approval service nạp resource/policy phía server, kiểm tra phiên bản/hash, người tạo run, SoD, thứ tự step, trạng thái và ghi audit trong giao dịch. Worker recheck yêu cầu workspace claim từ bearer đã ký, gắn tenant context trước truy vấn, lọc grant/resource theo workspace, rồi kiểm tra lại membership, quyền hiện tại, TTL, policy version, resource version/hash và approval bắt buộc. Không thấy lỗi quyền P1 mới ở các nhánh này qua đọc source.
- Migration PostgreSQL có preflight chéo tenant/trùng dữ liệu, khóa ngoại ghép workspace cho các quan hệ chính, RLS/FORCE RLS, chính sách đọc catalog role/permission và trigger cấm UPDATE/DELETE audit. Auth API gắn tenant context sau xác minh trước khi đọc; worker hiện gắn context từ workspace claim đã xác minh. Đọc tĩnh không phát hiện thiếu ràng buộc SQL cụ thể trong phần này.
- Trang `/team` hiển thị rõ “Chưa kết nối”, bỏ dữ liệu mẫu và vô hiệu hóa thao tác mời/tạo đơn vị. Đây là giao diện chưa tích hợp, không phải bằng chứng chức năng quản trị đã vận hành.

## Giới hạn bằng chứng

Migration/RLS chưa chạy trên PostgreSQL với runtime role; chưa xác minh quyền sở hữu bảng, `BYPASSRLS`, hành vi pool/transaction hay rollback. Các bằng chứng hiện có ghi nhận Baha Auth 86 passed, API tích hợp 11 passed và worker 14 passed; tôi đã đối chiếu SHA-256 source nhóm 2 trọng tâm với manifest trong log (`14c7f4d4…`) và đọc log regression brief. Không chạy lại test trong lượt review. Các kết quả SQLite không chứng minh PostgreSQL/browser/staging. Không có thử nghiệm nhà cung cấp danh tính thật hoặc production.

Scope tích hợp hiện còn phụ thuộc metadata nghiệp vụ: B/H/R/A/O chưa hỗ trợ; dữ liệu thiếu organization/project/owner/creator bị từ chối. Các action tạo workspace/nhập/xóa evidence nêu trên là DENY có chủ đích. Phê duyệt tài nguyên thiếu creator/owner bị đóng. Giao diện tổ chức chưa kết nối API. Vì vậy bằng chứng hiện tại chưa chứng minh hệ thống sẵn sàng production.
