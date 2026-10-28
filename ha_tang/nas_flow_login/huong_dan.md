# Đăng nhập Google Flow trên NAS

## Mục đích

Container này mở Chromium có giao diện trong màn hình ảo trên NAS. Người dùng xem và điều khiển màn hình bằng noVNC qua SSH tunnel, đăng nhập Google một lần rồi đóng Chromium. Hồ sơ lưu trong Docker volume prj069_flow_profile, tách khỏi mã nguồn và thư mục đồng bộ.

Google có thể yêu cầu xác minh thiết bị hoặc chặn đăng nhập do môi trường tự động hóa. Trình duyệt đăng nhập được khởi chạy trực tiếp, không gắn Playwright điều khiển vào phiên đăng nhập. Sau khi đóng trình duyệt, các worker Playwright có thể mở cùng hồ sơ ở chế độ ẩn.

## Tạo project trong Container Manager

1. Mở Container Manager > Project > Create.
2. Đặt tên project là prj069_flow_login.
3. Chọn thư mục dự án trên NAS: /volume1/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ha_tang/nas_flow_login.
4. Chọn tệp docker-compose.yml trong thư mục đó và hoàn tất tạo project.
5. Bật project. Lần đầu Container Manager sẽ tải image Playwright và build container.

Port 6080 chỉ bind vào loopback của NAS, không mở trên LAN hoặc Internet. Để truy cập, mở PowerShell trên máy làm việc và chạy:

ssh -N -L 127.0.0.1:6080:127.0.0.1:6080 -p 22 <tai_khoan_dsm>@bahahomes.synology.me

Giữ cửa sổ PowerShell đó mở. Trong trình duyệt trên máy làm việc, mở:

http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale

Đăng nhập vào Google Flow và Flow Music. Đóng cửa sổ Chromium để kết thúc container; Docker volume giữ phiên đăng nhập qua các lần khởi động lại. Nếu Google yêu cầu đăng nhập lại, khởi động lại container từ Container Manager rồi mở lại tunnel.

Không bật Web Station cho project này, không đổi cổng bind thành 0.0.0.0, không tạo reverse proxy hay chuyển tiếp port 6080 từ router. Quyền truy cập màn hình được bảo vệ bởi tài khoản SSH của NAS.

## Dùng hồ sơ trong API

API chạy trên NAS cần dùng cùng phiên bản Playwright/Chromium và gắn volume này vào cả hai đường dẫn. Khai báo volume ngoài project với tên prj069_flow_profile, rồi đặt BROWSER_PROFILE_DIR và LOCAL_BROWSER_PROFILE_DIR cùng trỏ tới điểm mount đó, đồng thời đặt BROWSER_CHANNEL=chromium. Không sao chép volume ra thư mục mã nguồn hoặc chia sẻ tệp hồ sơ; cookie trong đó cho phép sử dụng phiên Google.

Stack ứng dụng hiện tại chưa được bật bằng cấu hình Compose sẵn có: cấu hình đó dùng thông tin staging mẫu và port cố định, chưa có dịch vụ giao diện web. Container đăng nhập này chỉ tạo phiên trình duyệt an toàn để gắn vào runtime sau khi cấu hình ứng dụng được hoàn thiện.

## Cấu hình hồ sơ theo tài khoản (đang chuẩn bị, chưa nghiệm thu trên NAS)

Hai project phải cùng chọn `FLOW_PROFILE_ID`, ví dụ `tai_khoan_1`. Chỉ dùng chữ không dấu, số, gạch dưới và gạch ngang. Cấu hình biến này cho cả project API và project đăng nhập, sau đó dựng lại các container tương ứng. Mỗi hồ sơ nằm riêng trong volume Docker `prj069_flow_profiles`; volume này không nằm trong image. Hồ sơ cũ tại `prj069_flow_profile` không tự chuyển sang volume mới.

Trước khi mở project đăng nhập, chờ các tác vụ Flow kết thúc. Container đăng nhập và worker dùng chung khóa hồ sơ: nếu đang bận, trình duyệt thứ hai không được mở. Người dùng tự nhập thông tin Google và đóng trình duyệt sau khi đăng nhập. Màn hình noVNC chỉ mở qua tunnel SSH như hướng dẫn bên trên. Không sao chép cookie hoặc mật khẩu vào mã nguồn.

Các bước dựng runtime, kiểm tra trạng thái phiên và thử chuyển hai tài khoản thực tế chưa được nghiệm thu. Không coi hướng dẫn này là xác nhận đăng nhập thành công.
