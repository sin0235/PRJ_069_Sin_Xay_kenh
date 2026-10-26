# Kế hoạch sửa pipeline khử logo theo từng shot

> Kế hoạch này được thực thi trực tiếp trong phiên hiện tại theo yêu cầu của người dùng.

**Mục tiêu:** Phát hiện đầu ra bị cắt thời lượng và khử logo từng shot ngay khi tải về, chồng lấp CPU với lần tải Flow kế tiếp trước khi ghép toàn cục.

**Thiết kế:** Lớp remover xác minh thời lượng đầu ra so với đầu vào trước khi báo thành công. Worker lưu clip Flow gốc, chạy một tác vụ remover nền CPU đơn luồng sau mỗi lần tải; các shot khác có thể tiếp tục gửi/tải trong lúc tác vụ chạy. Chỉ ghép các asset đã xử lý và xác minh.

**Phạm vi kỹ thuật:** Python, SQLAlchemy, SQLite, ffprobe, ThreadPoolExecutor.

**Ràng buộc:** Giữ nguyên clip nguồn; không đưa clip lỗi vào timeline; chỉ một tác vụ remover CPU tại một thời điểm; shot liên tục vẫn dùng khung cuối shot trước; không gọi lại Flow chỉ để khử logo.

**Điểm rà soát:**
- Đầu ra ngắn hơn nguồn hoặc mất luồng video phải làm shot thất bại, không báo thành công.
- Worker khởi động lại khi shot ở trạng thái đang khử logo phải tiếp tục từ asset Flow đã tải, không gửi lại Flow.
- Lỗi khử logo phải ngăn ghép final và giữ nguyên asset Flow gốc.
- Luồng không yêu cầu khử logo tiếp tục giữ nguyên hành vi.

---

## Task 1: Xác minh và chặn đầu ra bị cắt

**Tệp:** `cong_cu_tu_dong/veo_watermark_remover/remover_service.py`, `sin_content_api/tests/test_media_studio_video.py`.

- [x] Viết test: remover trả mã thành công nhưng output ngắn hơn input thì API báo lỗi duration mismatch.
- [x] Chạy test và xác nhận thất bại do hiện tại trả `SUCCEEDED`.
- [x] Thêm probe duration đầu vào/đầu ra, chia clip đoạn 7 giây do binary giới hạn 8 giây, nối và từ chối output lệch quá 0,5 giây.
- [ ] Chạy test mục tiêu và test liên quan.

## Task 2: Khử logo nền theo từng shot

**Tệp:** `sin_content_api/src/modules/tao_video_noi_dung/runner.py`, `sin_content_api/src/modules/tao_video_noi_dung/cong_harness.py`, test pipeline liên quan.

- [x] Viết test: remover chạy nền trong lúc tiến trình shot kế tiếp tiếp tục; timeline chỉ nhận asset đã xử lý.
- [x] Chạy test để xác nhận trước sửa không gọi remover trong harness.
- [x] Dùng một ThreadPoolExecutor đơn luồng; sau download xếp xử lý ngay; giữ raw asset; chờ trước ghép, tạo asset sạch và cập nhật receipt.
- [x] Khôi phục `CLEANING` từ asset Flow đã lưu, không gửi lại Flow.
- [x] Chạy test pipeline, xác minh clip Flow thật đủ 10 giây cả hình/âm thanh, và rà soát diff.
