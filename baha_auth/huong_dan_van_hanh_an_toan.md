# Hướng dẫn vận hành an toàn cho bản khắc phục phân quyền

Tài liệu này áp dụng cho đợt sửa theo `ke_hoach_sua_phan_quyen_2026_10_21.md`. Trạng thái nghiệm thu phải lấy từ báo cáo kiểm thử mới nhất, không dựa vào nhãn PASS trong tài liệu cũ.

## Xác thực và cấu hình

Chỉ nhận danh tính từ bearer token đã được xác minh theo issuer/audience và khóa cấu hình riêng của môi trường. Header workspace chỉ chọn phạm vi sau khi máy chủ xác thực và kiểm tra thành viên. Không dùng header định danh người dùng làm bằng chứng đăng nhập. Bộ xác minh không phát hành token và không thay thế nhà cung cấp đăng nhập.

Thiếu cấu hình, không xác minh được danh tính, thiếu chính sách hoặc không tìm thấy tài nguyên phải từ chối. Không khôi phục khả năng truy cập bằng cách tắt kiểm tra quyền. Không đặt khóa/token thật vào tệp mã, báo cáo hoặc dữ liệu mẫu.

Token dịch vụ worker phải có `workspace_id` được nhà cung cấp ký, cùng subject và audience dành riêng cho worker đã cấu hình. Tenant được gắn vào phiên DB trước truy vấn grant; token thiếu hoặc sai workspace không được dùng để chạy job. Mỗi tiến trình worker hiện dùng một token cấu hình cho tenant tương ứng; chưa có bộ quản lý token cho nhiều tenant trong cùng tiến trình. Không thêm workspace từ payload để thay claim đã ký.

Luồng duyệt từ chối khi thiếu ngữ cảnh tài nguyên hoặc thông tin người tạo/chủ sở hữu đáng tin cậy. Người tạo run, người tạo tài nguyên và chủ sở hữu tài nguyên đều không tự duyệt; một quản lý được ghi làm owner cũng cần người duyệt độc lập. Quy tắc này cần được đối chiếu với định nghĩa ownership của doanh nghiệp trước khi phát hành.

## Di trú và phát hành

Chỉ kiểm tra migration với cơ sở dữ liệu thử nghiệm riêng. Trước khi thay đổi môi trường đang có người dùng, phải có kiểm kê quyền trước/sau, xác nhận ánh xạ định danh, ma trận vai trò được phê duyệt, bản sao lưu đã thử khôi phục và văn bản phát hành từ Founder. Việc sửa mã theo yêu cầu không phải phê duyệt thay quyền sống.

Tạo bảng bằng ORM không thay thế migration cho bảng đang có. Không chạy tự động di trú dữ liệu hiện hữu khi khởi động ứng dụng. Các mục RLS, tranh chấp đồng thời, trình duyệt, staging và nhà cung cấp chưa kiểm tra thực tế phải ghi đúng là chưa kiểm tra.

## Khi cần hoàn nguyên

1. Đưa dịch vụ vào chế độ bảo trì hoặc ngừng nhận tác vụ ghi; giữ nguyên kiểm tra cách ly tenant và quyền.
2. Ghi nhận mốc phiên bản và bằng chứng sự cố, bảo toàn nhật ký kiểm toán.
3. Dùng migration hoàn nguyên đã được diễn tập hoặc khôi phục bản sao lưu đã xác minh vào môi trường riêng để đối soát trước.
4. Xác minh quyền đã thu hồi không sống lại, worker cũ bị chặn, các bản duyệt và phiên bản nội dung vẫn khớp.
5. Chỉ mở lại lưu lượng sau kiểm thử và phê duyệt theo quy trình phát hành.

Không dùng `drop_all()` trên cơ sở dữ liệu dự án làm phương án rollback. Không đặt `enforce_strict_tenant_isolation=False` để khắc phục sự cố. Runbook cũ tại `docs/implementation/rbac/RUNBOOK.md` có hướng dẫn trái các điều kiện này; chuyển Antigravity đối soát trong vùng tài liệu do họ quản lý.
