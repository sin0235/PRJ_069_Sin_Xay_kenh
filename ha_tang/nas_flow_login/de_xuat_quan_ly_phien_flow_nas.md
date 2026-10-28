# Đề xuất quản lý phiên Google Flow trên NAS

Ngày: 28-10-2026. Trạng thái: đề xuất, chưa triển khai và chưa xác minh phiên Google thực tế.

## Mục tiêu

Cho phép người vận hành đăng nhập lại hoặc chọn tài khoản Flow khi triển khai, giữ phiên theo từng môi trường hoặc tài khoản và tránh đưa mật khẩu, cookie vào mã nguồn. Mỗi lần chạy video sử dụng một phiên đã chọn; việc đổi phiên không làm mất hay gửi lại job đang chạy.

## Hiện trạng

- Container đăng nhập `prj069_flow_login` chạy Chromium qua noVNC và SSH tunnel, lưu trong volume `prj069_flow_profile`. API hiện dùng đường dẫn profile khác trong volume dữ liệu và mặc định gọi `msedge`; Dockerfile API chưa cài browser tương ứng.
- Hai đường dẫn đăng nhập và worker chưa được nối với nhau. Chưa xác minh volume đăng nhập có phiên hợp lệ.
- `profile_guard.py` xóa khóa browser và trên Windows có thể dừng tiến trình Edge theo mẫu tên. Không dùng cơ chế đó để chia sẻ profile; cần sửa theo hướng từ chối khi profile đang bận.
- Playwright khuyến nghị một user data directory riêng và không chạy hai browser cùng thư mục; dữ liệu xác thực có thể dùng để mạo danh, nên không đưa vào repo ([BrowserType](https://playwright.dev/python/docs/api/class-browsertype), [Authentication](https://playwright.dev/python/docs/auth)).

## Phương án đề xuất

1. Tạo một volume riêng chỉ cho profile Flow; mỗi profile nằm trong thư mục con với mã định danh không nhạy cảm. Tên profile đang chọn khai báo bằng biến môi trường hoặc tệp cấu hình không chứa bí mật khi deploy. Cấu hình mặc định chỉ chọn một profile cho mỗi instance API.
2. Container đăng nhập và worker dùng cùng phiên bản Playwright và Chromium, cùng volume profile, cùng mã profile. Trình duyệt đăng nhập vẫn do người dùng điều khiển qua noVNC và SSH tunnel; người dùng tự nhập mật khẩu, OTP và giải quyết xác minh Google.
3. Có khóa liên tiến trình cho từng profile. Khi đăng nhập, tạm dừng gửi job Flow và chờ worker nhả profile; khi worker đang dùng, không mở trình duyệt đăng nhập. Không xóa `SingletonLock` hay dừng tiến trình của người khác. Khôi phục sau crash phải kiểm tra chủ khóa còn sống, không tự xóa khi chưa xác định được.
4. Sau khi người dùng đóng Chromium, kiểm tra trạng thái bằng mở Flow và quan sát UI, chỉ ghi kết quả `CONNECTED`, `LOGIN_REQUIRED`, `BUSY` hoặc `ERROR`; không xuất cookie, token hoặc nội dung profile. Dừng trước CAPTCHA hoặc xác minh danh tính.
5. Đổi tài khoản bằng tạo/chọn profile khác, chạy lại đăng nhập và xác minh; đổi cấu hình active chỉ sau khi job hiện tại kết thúc. Mỗi run ghi mã profile đã chọn trong receipt để đối soát, không ghi email hoặc bí mật.
6. Mỗi lần deploy có thể chọn profile hiện có hoặc tạo profile mới; volume nằm ngoài image và Compose project. Tắt hoặc xóa profile là thao tác riêng có xác nhận, không gắn với rebuild.

## Tiêu chí kiểm thử

- Rebuild API không mất profile; profile A và B tách biệt, đổi A sang B không làm thay đổi A.
- Khi profile đang bận, thao tác khác trả BUSY và không xóa lock hay thay cookie.
- Phiên hết hạn được báo LOGIN_REQUIRED; không tự gửi lại job Flow đang ở trạng thái chưa rõ.
- Chạy test thật bằng tài khoản do người dùng tự đăng nhập: chọn profile, tạo một shot, đối soát video tải về và receipt, rồi thử đổi profile và kiểm tra lại. Không in thông tin xác thực vào log.
- Chưa thể kết luận tái sử dụng cookie hoạt động trên Google Flow cho đến khi kiểm thử thật; Google có thể yêu cầu xác minh thêm.

## Việc cần chốt khi triển khai

Cần prototype giao diện đăng nhập/chọn profile để Founder duyệt theo quy tắc dự án; sau đó kiểm tra quyền điều khiển, build runtime có Chromium và áp dụng trên môi trường kiểm thử. Giao diện dự kiến hiển thị tên profile không nhạy cảm, trạng thái phiên, nút đăng nhập lại và chọn profile cho deployment; không hiển thị cookie hay thông tin bí mật.
