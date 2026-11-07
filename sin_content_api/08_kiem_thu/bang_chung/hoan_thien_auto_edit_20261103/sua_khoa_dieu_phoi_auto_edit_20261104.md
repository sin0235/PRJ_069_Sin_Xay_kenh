# Sửa khóa điều phối Auto Edit

## Nguyên nhân và bản sửa

Runner GitHub đã tách nhưng media worker local còn phụ thuộc khóa `content-video-flow` đang được AI Video giữ. Lô đã duyệt bị kẹt trước khi gửi tác vụ từ xa.

Commit `43a2b95` thêm bộ điều phối Auto Edit riêng với khóa `auto-edit-media`, chỉ nhận dự án AUTO_EDIT. Kiểm tra quyền, khóa từng job, heartbeat và khóa chống gửi trùng vẫn đi qua worker hiện hữu. Khôi phục job hết hạn và đánh thức parent cũng giới hạn đúng luồng. Flow vẫn phải lấy khóa `content-video-flow` trước khi được nhận; khi khóa bận, worker tiếp tục tìm cảnh HyperFrames để gửi GitHub. Heartbeat giữ cả hai khóa khi xử lý Flow.

Chạy tại local bằng `python ha_tang/chay_dev_local/chay_worker_auto_edit.py`, PID ban đầu 18068. Không khởi động lại hoặc hủy worker AI Video.

## Bằng chứng

- Test mới thất bại trước sửa vì thiếu bộ nhận lease riêng.
- `pytest tests/test_media_queue.py tests/test_runner_tach_luong.py`: 74 đạt, 1 cảnh báo.
- Sau tối ưu truy vấn mặc định, chạy lại test mới: 1 đạt.
- Đã push commit `43a2b95` lên `dev/local-remote-video-tests`.
- Runner Auto Edit mới: https://github.com/sin0235/PRJ_069_Sin_Xay_kenh/actions/runs/41787347833 — in_progress, đang chuẩn bị môi trường tại thời điểm ghi nhận.
- Runner AI Video `41782996268` vẫn in_progress.
- Tác vụ từ xa `7a8bae4b-c3fd-4eb0-9e0a-92b4fc685506`: RENDER_VISUAL, AUTO_EDIT, QUEUED chờ runner mới.
- Lô media: 1 SUBMITTING, 73 QUEUED; chưa có MP4 cuối. Không gọi trạng thái này là đã render thành công.

## Tiếp tục

Biên nhận lô: `ha_tang/chay_dev_local/runtime/tien_trinh_lo_8_video_da_duyet.json`.
Log worker: `ha_tang/chay_dev_local/runtime/worker_auto_edit.err.log`.
Tiến trình lô PID ban đầu 21092 tiếp tục đợi cảnh rồi xuất tám MP4 độc lập. Không tạo lại lô hoặc đổi khóa idempotency khi kiểm tra tiến độ.
