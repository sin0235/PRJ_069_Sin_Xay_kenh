# Kế hoạch sửa phân quyền — 21/10/2026

Mục tiêu: xử lý 16 phát hiện trong `ra_soat_phan_quyen_2026_10_21.md`, bảo đảm từ chối mặc định và kiểm tra quyền tại điểm thực thi.

Kiến trúc: giữ dịch vụ hiện hữu, dùng danh tính đã xác minh và quyền theo action/tài nguyên. Không triển khai production hoặc suy diễn phê duyệt Founder. Các agent Luna 6 mức max chia vùng ghi riêng; điều phối viên kiểm tra tích hợp và bằng chứng.

Ràng buộc: mã mới trong `03_ban_lam_viec/`; không sửa nguồn bất biến, không ghi dữ liệu thật, không dùng secrets cố định; kiểm thử bảo mật chạy DB riêng trong RAM. Mọi migration chỉ tạo và kiểm tra ngoại tuyến, không áp dụng DB dự án. Không đổi giao diện ngoài sửa dữ liệu/kết nối/trạng thái liên quan phân quyền.

- [ ] Nhóm 1: sửa danh tính, policy, cấp/thu hồi quyền, truy vấn tài nguyên, ràng buộc DB và audit. Sở hữu `baha_auth/src/api/deps.py`, `config.py`, `database.py`, `models/`, `policy/`, `services/role_service.py`, `services/tenant_service.py`, `services/org_service.py`, `api/role_router.py`, `api/org_router.py`, `api/evaluate_router.py`, `api/audit_router.py`. Thêm kiểm thử hồi quy riêng. Giao diện chung: `get_current_actor`, `ActorContext`, `ResourceContext`, `evaluate_permission` giữ tên; bổ sung trình xác minh bearer dùng được cho API nghiệp vụ.
- [ ] Nhóm 2: sửa approval và worker, strict schemas; sở hữu các service/router tương ứng và `baha_auth/src/schemas/contracts.py`. Kiểm tra policy/tài nguyên phía máy chủ, đúng người/chặng/phiên bản, idempotency, runtime recheck và audit. Không sửa DB/models chung; báo nhu cầu cho nhóm 1.
- [ ] Nhóm 3: tích hợp vào API nghiệp vụ/worker và sửa trang team tránh dữ liệu mẫu bị hiểu là trạng thái thật. Sở hữu `sin_content_api/`, `sin_content_workers/`, `sin_creator_os/` trong phạm vi phân quyền; không sửa nghiệp vụ ngoài quyền. Phối hợp nhóm 1 về cơ chế xác thực chung và định danh tenant; không tự tạo bản sao danh tính/quyền không đồng bộ.
- [ ] Điều phối: chạy kiểm thử tổng hợp độc lập, rà soát chéo qua agent, sửa lỗi tích hợp, ghi báo cáo khắc phục và cập nhật trạng thái trung thực; không tạo checkpoint nghiệm thu toàn bộ khi thiếu PostgreSQL/staging/phê duyệt.

Tiêu chí: mỗi ca khai thác phải có kiểm thử từ chối và ca cho phép tương ứng; thu hồi/hết hạn có hiệu lực tại lần gọi sau; job không nhận quyền lớn hơn người khởi tạo; duyệt không lặp/sai người/sai phiên bản; truy vấn không vượt phạm vi; không còn tự báo A00–A10 PASS từ kiểm thử đơn vị. Lưu lệnh, mã thoát và giới hạn tại `08_kiem_thu/bang_chung/`.

Các trường hợp phải kiểm tra chéo: membership nhiều nhóm, role hết hạn, tài nguyên không tồn tại, thay tenant trong yêu cầu/job, gửi lại quyết định, policy store thiếu/hỏng, môi trường không có dịch vụ xác thực.
