# Bằng chứng kiểm tra giới hạn RAM của Audio QC

Ngày kiểm tra: 2026-11-02

## Thay đổi

`verify_audio_qc` lấy kích thước từ metadata tệp và chỉ đọc tối đa 200 byte đầu để nhận diện phản hồi HTML. Trước đó hàm dùng `Path.read_bytes()` để nạp toàn bộ video hoặc âm thanh vào RAM.

## Kiểm tra

- Kiểm thử mới được chạy trước thay đổi và thất bại đúng tại `Path.read_bytes()`.
- Lệnh sau khi sửa: `python -m pytest --noconftest tests/test_audio_qc_gioi_han_bo_nho.py -q`
- Kết quả: `1 passed in 0.09s`.
- `python -m py_compile src/modules/media_studio/audio_processor.py tests/test_audio_qc_gioi_han_bo_nho.py`: thành công.
- `git diff --check`: không phát hiện lỗi khoảng trắng.
- Máy có 7.81 GiB RAM tổng; còn khoảng 2.51 GiB tại lần kiểm tra cuối. Không chạy FFmpeg, ffprobe hoặc render video dài trong lượt này.

## Giới hạn

Kiểm thử module Audio QC được chạy cô lập để tránh nạp package ứng dụng. Bộ kiểm thử chuẩn hiện không thu thập được vì `src/auth/tenancy.py` import `local_password_mode` nhưng `src/auth/mat_khau_noi_bo.py` không định nghĩa tên này. Đây là lỗi tồn tại độc lập; không thay đổi mã xác thực trong lần sửa này.
