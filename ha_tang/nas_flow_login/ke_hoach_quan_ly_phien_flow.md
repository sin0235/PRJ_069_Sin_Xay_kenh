# Kế hoạch triển khai phiên Google Flow trên NAS

Mục tiêu: chọn hồ sơ riêng khi triển khai, đăng nhập do người dùng thực hiện và bảo vệ hồ sơ khi nhiều tiến trình cùng truy cập. Tài liệu thiết kế: de_xuat_quan_ly_phien_flow_nas.md; mẫu: mau_quan_ly_phien_flow.html.

1. Kiểm thử trước khóa liên tiến trình: cùng hồ sơ chỉ một chủ sở hữu; hồ sơ khác độc lập; khi tiến trình chết khóa được giải phóng. Không xóa khóa Chromium hoặc dừng tiến trình khác.
2. Áp dụng khóa bao toàn bộ vòng đời Chromium cho đăng nhập, tạo video, tạo nhạc và kiểm tra phiên; giữ tương thích Windows. Không đồng bộ cookie trong lúc hồ sơ được sử dụng.
3. Cấu hình tên hồ sơ hợp lệ, volume dùng chung bền vững, Chromium và Playwright cùng phiên bản cho login và API; không đưa bí mật vào cấu hình.
4. Tích hợp giao diện chọn hồ sơ và trạng thái, xác minh quyền truy cập, đảm bảo đổi phiên chỉ tác động tác vụ mới; người dùng tự đăng nhập qua tunnel.
5. Kiểm thử đơn vị và cấu hình; kiểm tra thực tế đăng nhập, đổi hai hồ sơ, rebuild và tạo video trên NAS. Ghi rõ các bước chưa thể xác minh nếu dịch vụ NAS chưa sẵn sàng.

Các trường hợp phải kiểm tra: tên hồ sơ không hợp lệ; hồ sơ bận; tiến trình bị dừng đột ngột; phiên hết hạn; job đang chạy khi đổi; dịch vụ đăng nhập không truy cập được; khác phiên bản Chromium.
