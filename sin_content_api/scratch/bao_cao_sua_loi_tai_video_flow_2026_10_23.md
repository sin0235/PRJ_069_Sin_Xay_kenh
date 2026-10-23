# Báo cáo sửa lỗi nhận video Google Flow — 2026-10-23

## Nguyên nhân đã xác định
- Fallback tải media gọi `media.getMediaUrlRedirect` bằng tham số `?name=...`; endpoint tRPC cần query `input` chứa JSON và tên media phải được URL-encode.
- Lỗi phân tích response và lỗi tải bị bỏ qua, sau đó hệ thống báo nhầm Flow đang quá tải.
- Khi remover timeout hoặc báo `FALLBACK_ORIGINAL`, renderer cũ vẫn dùng video nguồn để dựng và lưu MP4, nên logo vẫn còn. Thời gian remover thực tế là 300 giây, dài hơn thời gian chờ được nêu trên giao diện.
- Nội dung lỗi cũ còn đề nghị dùng nút tải video 16:9 đã bị gỡ khỏi AI Studio.

## Thay đổi
- URL redirect Flow dùng query tRPC đã mã hóa; lỗi response/tải được ghi log rõ ràng.
- Timeout không còn khẳng định nguyên nhân là hàng đợi cao; hướng dẫn UI không còn chỉ tới nút tải video đã bị gỡ.
- Renderer dừng xuất video nếu remover không sẵn sàng, timeout, lỗi, không tạo tệp, hoặc không xác nhận `watermark_removed`.
- Thêm test hồi quy cho URL, thông báo lỗi, remover thiếu và trường hợp remover trả video gốc.

## Kiểm chứng
- RED: 3 test hồi quy thất bại trước khi sửa ở các hành vi cần thiết.
- GREEN ban đầu: 7/7 test đạt. Sau khi thêm fail-closed, 8/8 test mục tiêu đạt; có 1 cảnh báo deprecation Starlette/httpx.
- `python -m py_compile` cho client, provider, renderer và test đạt.
- Live ngày 23-10: Flow trả video 10 giây, 2.364.094 byte; API tải xuống, lưu asset `asset-18ff9250b881` và trả HTTP 200.
- Log live xác nhận công cụ khử logo chạy hết timeout 300 giây. Bản cũ vẫn dựng/lưu video bằng nguồn gốc. Đây là nguyên nhân trực tiếp khiến video cuối còn watermark và phản hồi tới giao diện bị trễ.
- Đã khởi động lại API cổng 8000 với bản renderer fail-closed.

## Giới hạn còn lại
- Asset live đã lưu trước khi sửa có thể còn watermark.
- Chưa xác nhận remover có thể hoàn tất trên video Flow thật; trên video live này remover vượt 300 giây. Với bản mới, pipeline sẽ báo lỗi và không xuất video 9:16 nếu không gỡ logo được.
- Đã xác định remover bị ép CPU; Vulkan không khởi tạo được trên Intel HD Graphics 4600. Timeout 300 giây thấp hơn thời gian đo thực tế.

## Bổ sung sửa luồng tạo video từ ảnh — 23-10-2026
- Khi request có ảnh đầu vào, bridge hiện đợi editor hiển thị, mở menu chế độ bằng nút crop và chọn tab Video trước khi mở ô khung hình đầu.
- Bản tham chiếu gflow-cli xác nhận ô frame nằm trong editor chính và yêu cầu chế độ Video; bridge cũ mở project nhưng không chọn chế độ này trước khi tìm ô ảnh.
- Test hồi quy mới kiểm tra thứ tự chờ editor → chọn Video: `tests/test_bat_buoc_dang_nhap_flow.py`, tổng 8/8 đạt; biên dịch cú pháp đạt.
- Tăng timeout remover mặc định lên 900 giây; khi quá hạn, lỗi trả kèm tiến độ cuối. Vẫn giữ fail-closed.
- Chạy remover trên clip Flow 10 giây 1280x720/240 khung hình: hoàn tất trong 336,9 giây, đầu ra MP4 H.264/AAC 1.643.880 byte; đã đối chiếu khung hình trước/sau, watermark được loại bỏ.
- Test timeout và thông báo tiến độ: 2/2 đạt; `py_compile` đạt; API khởi động lại, `/healthz` trả trạng thái OK.
- Bản kết quả và bằng chứng: `verified_clean_flow.mp4`, `verified_clean_flow_stdout.log`, `verified_clean_flow_stderr.log`, `frame_source.png`, `frame_clean.png` trong thư mục `scratch`.
