# Kiểm thử upload và Auto Edit trên máy local

Ngày kiểm thử: 2026-11-02

## Tư liệu đầu vào

- Video nguồn: `C:\Users\Baha Group\Downloads\DJI_20261027202121_0203_D.MP4`.
- Kích thước: 8.428.283.732 byte; thời lượng: 926,859 giây.
- Định dạng: HEVC 1728 × 3072, 30000/1001 fps; âm thanh AAC.
- SHA-256 xác nhận trong lượt upload: `8b520dc243dfa602d09fee1f24c3d1f9ff89f56833b234eb6d317fc272a542df`.
- `mau1.mp4` và `mau2.mp4` chỉ được probe metadata và giải mã hai giây ở độ phân giải 360 × 640. Không dùng hai video mẫu làm đầu vào Auto Edit.

## Kết quả

- Phát hiện giới hạn stream mặc định là 500 MiB, trong khi phiên upload tiếp tục đã có giới hạn 12 GiB. Sửa mặc định `UPLOAD_LIMIT_VIDEO_MB` thành 12.288 MiB để hai đường upload dùng cùng ngưỡng.
- Chạy upload stream thật qua `MediaStudioService.upload_asset_stream` với file DJI 8,43 GB: đạt, nhận đủ byte, SHA-256 trùng, hoàn tất trong 91,7 giây. Bản sao trong thư mục tạm đã được xóa; video nguồn vẫn giữ nguyên kích thước và thời gian sửa.
- Auto Edit gọi upload tiếp tục theo khối 64 MiB; backend đọc và ghi theo khối 1 MiB. Kiểm thử API upload tiếp tục và kiểm tra khối sai đạt.
- Kiểm thử dựng Auto Edit trên video tổng hợp 12 giây đạt; kiểm thử cờ gỡ watermark Flow đạt.
- Hai video tham khảo đều giải mã được đoạn hai giây bằng một luồng FFmpeg.
- Bộ kiểm thử chọn lọc: `14 passed`, `2 warnings` về API tương thích của Starlette.
- RAM khả dụng ghi nhận trong lượt upload khoảng 2,18–2,32 GiB. Quá trình hoàn tất; không thấy tiến trình bị kết thúc do thiếu bộ nhớ.

## Giới hạn của lượt kiểm thử

- Chưa chạy ASR, gọi LLM thật hoặc render toàn bộ video DJI 15 phút trên máy này. Cấu hình LLM local đang tắt và cơ sở dữ liệu local không có bảng cấu hình LLM; máy chỉ có 8 GiB RAM tổng, nên chưa khởi tạo tác vụ nặng.
- Upload 8,43 GB được chạy thật qua service stream; đường HTTP resumable được kiểm thử bằng các ca API nhỏ, chưa truyền đủ 8,43 GB qua trình duyệt hoặc gateway.
- Không build hoặc khởi động lại NAS trong lượt này.
