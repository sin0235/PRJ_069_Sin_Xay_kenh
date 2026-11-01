# BÀN LÀM VIỆC VÀ ĐIỂM NGUỒN KỸ THUẬT DUY NHẤT (TECHNICAL SSOT)

Đây là không gian làm việc chính của dự án. Mọi thành phần mã nguồn, module tùy biến, API handler đều được phát triển tại đây.

## Quy Tắc Làm Việc:
1. **SSOT**: Mọi logic kỹ thuật cốt lõi phải được tập trung và có tài liệu đối soát rõ ràng.
2. **Không phân mảnh**: Không tạo nhiều phiên bản mã nguồn trôi nổi ngoài các thư mục phân quyền.
3. **Kiểm thử kèm theo**: Mọi tính năng phát triển mới tại đây phải có test case tương ứng trong 08_kiem_thu.
## Video Auto Edit: chạy thực tế trên video 8,43 GB

Job NAS `6e09044e-a25b-4062-b312-b217c7d8789c` đã hoàn tất qua LLM cấu hình thật, Flow, HyperFrames và FFmpeg. Kết quả gồm 8 video dọc H.264/AAC, 1080 × 1920, 30 fps; tổng 8 MP4 khoảng 127 MB. Các đầu ra vẫn ở trạng thái chờ nhân viên duyệt.

Mở từng video (cần đăng nhập hệ thống trước):

1. [01 — Doanh thu chưa phải tiền thực nhận](https://nhap-xaykenh-prj069.bahagroup.vn/v1/media/assets/b117968c-9d3d-4358-aeb2-f16cda8379ef/download?ttl=3600) — 63,7 giây
2. [02 — Tăng giá nhưng lợi nhuận vẫn giảm](https://nhap-xaykenh-prj069.bahagroup.vn/v1/media/assets/e141ef16-a77e-4cfb-ae77-59d1eb4eb879/download?ttl=3600) — 48,5 giây
3. [03 — Đừng tăng giá chỉ vì thấy có đơn](https://nhap-xaykenh-prj069.bahagroup.vn/v1/media/assets/82dd8e2c-fb3d-43cc-8323-d091b1cbab97/download?ttl=3600) — 44,9 giây
4. [04 — Món hàng rẻ vẫn có thể lỗ công](https://nhap-xaykenh-prj069.bahagroup.vn/v1/media/assets/3f13085c-9cfd-4a3e-871e-af643edee11b/download?ttl=3600) — 18,5 giây
5. [05 — Đơn nhiều chưa chắc có lãi](https://nhap-xaykenh-prj069.bahagroup.vn/v1/media/assets/1014100a-4052-4630-9b68-d4cc8753ffca/download?ttl=3600) — 60,6 giây
6. [06 — Theo dõi tiền vào, tiền phải trả mỗi ngày](https://nhap-xaykenh-prj069.bahagroup.vn/v1/media/assets/17ffe3e2-d85c-4a38-97c2-4b0957b13b16/download?ttl=3600) — 36,8 giây
7. [07 — Rời sàn không có nghĩa là hết phí](https://nhap-xaykenh-prj069.bahagroup.vn/v1/media/assets/ada9da7f-c34d-49ff-8ef6-54ceaf7c5a3a/download?ttl=3600) — 75,4 giây
8. [08 — Đừng mặc định giảm 10% giá](https://nhap-xaykenh-prj069.bahagroup.vn/v1/media/assets/515c6eba-f99c-4d48-85a0-69555cc45e03/download?ttl=3600) — 27,2 giây

Các đường dẫn phát trực tiếp yêu cầu phiên đăng nhập có quyền đọc media. Lần kiểm tra sau khi render, API tài sản trả HTTP 503 do kho membership/phân quyền; nếu link chưa phát được, mở [Auto Edit](https://nhap-xaykenh-prj069.bahagroup.vn/auto-edit) sau khi đăng nhập và thử lại. Không bật truy cập công khai cho tài sản.

Biên bản E2E và ảnh chụp nằm tại `08_kiem_thu/bang_chung/video_auto_edit_8gb_e2e_20261101/` trong workspace NAS.
