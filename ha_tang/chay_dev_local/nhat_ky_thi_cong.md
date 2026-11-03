# Nhật ký thi công: chuyển dev local và kiểm thử từ xa

Kế hoạch: ke_hoach_chuyen_dev_local_va_kiem_thu_tu_xa_20261103.md.
Nhánh: dev/local-remote-video-tests. Nền ban đầu: b316d02.

- Xác nhận worktree local đã cách ly; không tạo checkout thứ hai.
- Máy có 8 GB RAM, khoảng 2,3 GB trống; Docker daemon chưa chạy. Không bật Docker vì có thể làm cạn RAM; triển khai native trước, cấu hình Compose vẫn được chuẩn bị cho môi trường đủ tài nguyên.
- Cloudflared service đang chạy; dùng token quản lý từ xa. Chưa đổi route.
- Checkout Git thiếu 28 file/thay đổi hiện có trong nguồn SSOT, bao gồm nhánh worker Auto Edit. Đã nhập nguyên trạng các thay đổi mã video và Remotion từ SSOT, giữ nguyên Whisper incremental hiện tại; commit baseline riêng trước khi sửa pipeline từ xa. Không đổi mã RBAC của các agent khác.
- Đã thêm store task bền vững, token theo task, lease/fencing, retry chunk có đối chiếu nội dung và kiểm tra hash kết quả. Bốn test tập trung đạt, gồm ký OIDC RSA thật và thử sai repo/ref/audience/signature.
- Quyết định: queue remote dùng SQLite riêng trong MEDIA_ROOT_DIR/.remote do BE quản lý, tránh can thiệp schema nghiệp vụ khi đang chuyển môi trường. Không chia sẻ DB này cho runner.
- Đang thi công tiếp client/runner và cấu hình native. Chưa có kết quả triển khai đầu-cuối; chưa render 8 GB.

## Tiến độ triển khai đã kiểm chứng

- Nhánh dev đã push tới `aeafb41` trước đợt sửa bổ sung hiện tại; GitHub main chỉ nhận hai tệp đăng ký workflow qua commit `f9b636aef658771f6570d00fdd781fed18623508`.
- Đã lấy snapshot nhất quán của ba DB từ container NAS đang dừng, nhập local và sao chép đúng khóa mã hóa/cấu hình hiện hữu. NAS chỉ được đọc, không build/restart.
- API native local đã chạy; cùng domain đi qua Tunnel tới Caddy `127.0.0.1:13069`. Không đổi DNS/ingress. Phiên owner hiện hữu gọi `/v1/auth/me` trả 200, anonymous trả 401.
- Build FE Windows trên Actions run `41569110732` đạt; FE native phục vụ `/auto-edit` qua domain HTTP 200. Hai lần build trước phát hiện sai công cụ lockfile và frontend Git cũ có lỗi cú pháp; đã chuyển về npm ci và đồng bộ frontend SSOT. Không sửa các component UI được bảo vệ.
- Kiểm thử worker run `41569431676` đạt: QC đoạn 12 giây từ DJI gốc (105.488.867 byte), giải mã thật; peak RSS 252.674.048 byte, 20,18 giây engine.
- Cũng run trên, dựng HyperFrames thật từ yêu cầu diễn họa LLM hiện hữu: alpha ProRes, 1080x1920, 30 fps, 5 giây; output 63.575.376 byte, hash đối soát; peak RSS 1.875.054.592 byte, 109,15 giây engine. Đã xem khung PNG sau render; không dùng video đã edit làm nguồn kiểm thử.
- Kết quả JSONL: `sin_content_api/08_kiem_thu/bang_chung/chuyen_dev_local_20261103/ket_qua_worker.jsonl`.
- Các tiến trình local đo sau khi ổn định: FE khoảng 85 MB, API 83 MB, gateway 32 MB, Tunnel 44 MB. Không chạy model/render nặng local.
- 21 test upload/remote từng đạt; sau thêm startup fencing/streaming đã có 12 test remote/child worker đạt. Cần chạy lại nhóm tập trung trước commit tiếp.
- Browser access host hiện không khả dụng; chưa nghiệm thu giao diện bằng browser, chỉ HTTP/API và artifact.
- Đã thêm launcher idempotent và runbook; chưa bật orchestrator local cho đến khi xác nhận không nhận lại command Flow cũ.

## Việc tiếp theo

- Tối ưu nguồn 8,43 GB: tránh tải toàn tệp cho từng stage/clip; giữ chất lượng bằng demux/stream copy có giới hạn tài nguyên, còn ASR/encode/render/QC ở Actions. Cần kiểm định timestamp trước khi sử dụng window nguồn.
- Kiểm thử upload HTTP toàn kích thước và Range, rồi thử các stage trên nguồn lớn; chưa coi bản 105 MB là chứng minh 8 GB đạt.
- Kiểm tra phiên Flow trên Windows; profile NAS không được đưa lên Actions hoặc sao chép vào profile Windows.
- Nhập video đầu ra hiện hữu từ NAS vào local để các liên kết đã có hoạt động; chỉ đọc NAS và xác minh hash.
- Hoàn thiện dọn dữ liệu tạm theo tham chiếu, kiểm thử mất mạng và hủy job, rà soát cuối nhánh.
- Quyết định: dùng native thay vì tạo thêm stack Compose chưa dùng; máy 8 GB và Docker daemon đang tắt. Đây là điều chỉnh triển khai từ plan, không thay mục tiêu chuyển môi trường.
