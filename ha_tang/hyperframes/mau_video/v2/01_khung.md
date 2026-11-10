# Khung mẫu video V2: Con số tố cáo (Numbers Reveal)

- **Mã mẫu:** `V2`
- **Ý tưởng chủ đạo:** Mỗi cảnh một con số hoặc biểu đồ làm lộ ra vấn đề cốt lõi; nhịp nhanh, dữ dội, nhiều thông số trực quan, tạo áp lực nhận thức rõ rệt.
- **Bài áp dụng tiêu biểu:** Bài 04, Bài 07, Bài 17.
- **Bảng màu:** Vàng kim (`#ffd54a`) trên nền Navy (`#0a1c2b`) đậm; San hô (`#e8695a`) cho con số cảnh báo/xấu; Ngà (`#f6efe0`) chữ.
- **Tâm trạng âm nhạc:** Nhịp đều, hơi điện tử (electronic beat), gọn gàng, tăng tiến dứt khoát.
- **Phong cách phụ đề (Sub style):** `bento_ba_tang` (hộp 3 tầng hiện đại, nổi bật thông số).
- **Chữ ký chuyển động:** "Con số rơi" (dropping digit): Mỗi con số then chốt rơi thẳng từ đỉnh khung hình xuống mặt sàn, nảy 1 nhịp (`back.out`), kèm âm đóng dấu SFX `dong_dau` ở cảnh 1, 4, 10, 12.
- **Ngân sách Flow:** 1 clip duy nhất (cảnh 4, 10 giây = 10% thời lượng). Có bản thay thế bằng cảnh mã `CASH_RIVER`.

---

## 1. Bảng phân cảnh 100 giây chi tiết (13 shot)

| Shot | Giây | Thời lượng | Vai trò | Layout | Chuyển động chính | Cú máy | Chuyển cảnh vào | Thay thế khi không Flow |
|---|---|---|---|---|---|---|---|---|
| s01 | 0 - 5 | 5s | Hook số | `OPEN_NUMBER` | Con số lớn rơi từ trên cao, chạm đất nảy nhẹ kèm tiếng đóng dấu | push in | - | - |
| s02 | 5 - 15 | 10s | Bức tranh dữ liệu | `LIVE_DASHBOARD` (E) | Cột mọc liên tiếp, đường xu hướng vẽ dần, kim quét vùng đỏ | lướt thị sai | push | - |
| s03 | 15 - 21 | 6s | Tỉ lệ | `STAT_RING` | Vòng tròn quét đầy 78%, hiển thị chi phí ẩn | push in | scale | - |
| s04 | 21 - 31 | 10s | Đời thực | `FLOW_ORIGAMI` | Cảnh nhân sự bận rộn xử lý thủ công, đối lập với con số năng suất | pull back | cover | `CASH_RIVER` (A) |
| s05 | 31 - 37 | 6s | Điểm nhấn | `MARK_PHRASE` | Câu chốt nguyên nhân, nét gạch chân phát sáng cụm từ khóa | rack focus | dissolve | - |
| s06 | 37 - 47 | 10s | Diễn biến | `CHART_STORY` | Biểu đồ cột tự kể diễn biến 4 quý, cột gần nhất tụt dốc | lia ngang | push | - |
| s07 | 47 - 53 | 6s | Câu hỏi | `KINETIC_TITLE` | Câu hỏi thức tỉnh: "VẤN ĐỀ NẰM Ở ĐÂU?" phóng to | push in | radial | - |
| s08 | 53 - 63 | 10s | Dòng tiền thật | `CASH_RIVER` (A) | Đồng xu trôi theo dòng sông giấy, rò rỉ rơi xuống miệng cống | lia ngang rồi đẩy vào | split | - |
| s09 | 63 - 69 | 6s | Cách gọi | `WORD_SWAP` | Đổi tên bản chất: "Thiếu người" -> "Thiếu thời gian" -> "Thiếu hệ thống" | static | grid | - |
| s10 | 69 - 79 | 10s | Hai đường giao nhau | `LIVE_DASHBOARD` (E) | Chuỗi dữ liệu 2 xuất hiện, đường chi phí cắt đường doanh thu | lướt thị sai | push | - |
| s11 | 79 - 85 | 6s | Chỉ số chính | `KPI_CARDS` | 3 thẻ KPI mục tiêu trượt vào từ cạnh phải, phát sáng chỉ số tốt | push in | cover | - |
| s12 | 85 - 95 | 10s | Việc cần làm | `CHECKLIST` | 4 bước kiểm toán số liệu và tối ưu vận hành lần lượt tích xanh | push in | scale | - |
| s13 | 95 - 100 | 5s | Kêu gọi | `CTA_CLOSE` | Thẻ kêu gọi khám doanh nghiệp miễn phí cùng BAHA, thông tin website | static | blur | - |

---

## 2. Ngân sách lời đọc và âm tiết

- Tốc độ chuẩn: 3.8 âm tiết/giây (khoảng cho phép: 3.0 - 4.2).
- Phân bổ âm tiết:
  - s01 (5s): 15 - 21 âm tiết
  - s02 (10s): 30 - 42 âm tiết
  - s03 (6s): 18 - 25 âm tiết
  - s04 (10s): 30 - 42 âm tiết
  - s05 (6s): 18 - 25 âm tiết
  - s06 (10s): 30 - 42 âm tiết
  - s07 (6s): 18 - 25 âm tiết
  - s08 (10s): 30 - 42 âm tiết
  - s09 (6s): 18 - 25 âm tiết
  - s10 (10s): 30 - 42 âm tiết
  - s11 (6s): 18 - 25 âm tiết
  - s12 (10s): 30 - 42 âm tiết
  - s13 (5s): 15 - 21 âm tiết
- Tổng toàn bộ: 360 - 390 âm tiết.
