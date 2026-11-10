# Khung mẫu video V6: Một ngày thật (A Real Day)

- **Mã mẫu:** `V6`
- **Ý tưởng chủ đạo:** Kể lại câu chuyện một ngày làm việc thực tế với nhân vật origami quen thuộc; đi từ nhịp điệu bình thường, dần rơi vào hỗn loạn và quá tải, để người xem thấy chính mình trong đó, rồi mở ra lối thoát bằng công nghệ thông minh.
- **Bài áp dụng tiêu biểu:** Bài 03, Bài 14.
- **Bảng màu:** Vàng ấm (`#ffd54a`) và Ngà (`#f6efe0`) lúc bình thường; San hô (`#e8695a`) bùng lên khi quá tải; Ngọc lam (`#5cc8c0`) bình ổn khi giải pháp xuất hiện trên nền Navy (`#0a1c2b`).
- **Tâm trạng âm nhạc:** Mang tính tự sự, ấm áp, có khoảng lặng kịch tính ở giữa, bừng sáng ở đoạn kết.
- **Phong cách phụ đề (Sub style):** `tu_dong` (phụ đề chuyển động tự nhiên theo ngữ điệu).
- **Chữ ký chuyển động:** "Đổi nét theo người" (rack focus character focus): Máy quay chuyển tiêu điểm giữa các nhân vật origami tại cảnh 3, 7 và 10; nhân vật đang hành động thì nét căng, các nhân vật khác mờ nhẹ tạo chiều sâu điện ảnh.
- **Ngân sách Flow:** 2 clip Flow (cảnh 1 và 5, tổng 20 giây = 20% thời lượng) để đặc tả diễn xuất nhân vật và cảm xúc bối rối. Có bản thay thế 100% bằng mã cho chế độ không Flow.

---

## 1. Bảng phân cảnh 100 giây chi tiết (13 shot)

| Shot | Giây | Thời lượng | Vai trò | Layout | Chuyển động chính | Cú máy | Chuyển cảnh vào | Thay thế khi không Flow |
|---|---|---|---|---|---|---|---|---|
| s01 | 0 - 10 | 10s | Hook | `FLOW_ORIGAMI` | Nhân vật origami bước vào văn phòng, khởi đầu ngày mới đầy năng lượng | pull back | - | `TEAM_BOARD` (F) bản mở |
| s02 | 10 - 16 | 6s | Tên tình huống | `KINETIC_TITLE` | Tiêu đề: "8 TIẾNG BẬN RỘN NHƯNG KHÔNG HIỆU QUẢ" | push in | push | - |
| s03 | 16 - 26 | 10s | Mọi thứ trôi chảy | `TEAM_BOARD` (F) | Các nhân vật chuyền tay thẻ việc trôi chảy, máy quay đổi nét giữa 2 người | rack focus | cover | - |
| s04 | 26 - 32 | 6s | Tin đến dồn dập | `CHAT_THREAD` | Hội thoại khách hỏi dồn dập, nhân viên luống cuống phản hồi không kịp | push in | scale | - |
| s05 | 32 - 42 | 10s | Khoảnh khắc rối | `FLOW_ORIGAMI` | Nhân vật quản lý ôm đầu giữa vòng vây điện thoại và yêu cầu phát sinh | push in | dissolve | `NOTIFY_STACK` rồi `PILE_UP` |
| s06 | 42 - 48 | 6s | Việc dồn | `PILE_UP` | Các thẻ công việc chưa xong chất đống cao ngất quanh bàn làm việc | push in | push | - |
| s07 | 48 - 58 | 10s | Quy trình kẹt | `PIPELINE_RAIL` (B) | Băng chuyền dừng đột ngột, hồ sơ khách hàng rơi rụng vì thiếu người duyệt | dolly dọc | split | - |
| s08 | 58 - 64 | 6s | Thông báo dồn | `NOTIFY_STACK` | Loạt thông báo đỏ nhắc việc khẩn cấp xếp chồng lên nhau che khuất màn hình | static | grid | - |
| s09 | 64 - 72 | 8s | Điểm nhấn | `MARK_PHRASE` | Dòng nhận diện sự thật: "Vấn đề không phải do thiếu nỗ lực" khoanh tròn | rack focus | radial | - |
| s10 | 72 - 81 | 9s | Cách làm khác | `BOOK_FLIP` (D) | Cuốn sổ lật trang 3D: từ hỗn loạn thủ công sang phân loại tự động ngăn nắp | orbit nhẹ | push | - |
| s11 | 81 - 87 | 6s | Kết quả | `STAT_RING` | Vòng tròn xanh quét 95% công việc được tự động hóa trơn tru | push in | scale | - |
| s12 | 87 - 95 | 8s | Việc cần làm | `CHECKLIST` | 3 bước thiết lập ngày làm việc thông minh được tích xanh trọn vẹn | push in | cover | - |
| s13 | 95 - 100 | 5s | Kêu gọi | `CTA_CLOSE` | Thẻ kết BAHA, kêu gọi đăng ký chương trình khám sức khỏe doanh nghiệp | static | blur | - |

---

## 2. Ngân sách lời đọc và âm tiết

- Tốc độ chuẩn: 3.8 âm tiết/giây (ngưỡng 3.0 - 4.2).
- Phân bổ âm tiết:
  - s01 (10s): 30 - 42 âm tiết
  - s02 (6s): 18 - 25 âm tiết
  - s03 (10s): 30 - 42 âm tiết
  - s04 (6s): 18 - 25 âm tiết
  - s05 (10s): 30 - 42 âm tiết
  - s06 (6s): 18 - 25 âm tiết
  - s07 (10s): 30 - 42 âm tiết
  - s08 (6s): 18 - 25 âm tiết
  - s09 (8s): 24 - 33 âm tiết
  - s10 (9s): 27 - 38 âm tiết
  - s11 (6s): 18 - 25 âm tiết
  - s12 (8s): 24 - 33 âm tiết
  - s13 (5s): 15 - 21 âm tiết
- Tổng toàn bộ: 360 - 390 âm tiết.
