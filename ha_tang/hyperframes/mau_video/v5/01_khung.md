# Khung mẫu video V5: Ba sai lầm (Three Mistakes)

- **Mã mẫu:** `V5`
- **Ý tưởng chủ đạo:** Cấu trúc 3 chương rành mạch, mỗi chương mổ xẻ một sai lầm phổ biến có gắn số thứ tự lớn (1, 2, 3), kèm một cảnh minh hoạ trực quan và một câu chốt hạ đanh thép; phần cuối đưa ra phương pháp khắc phục chuẩn xác.
- **Bài áp dụng tiêu biểu:** Bài 10, Bài 11.
- **Bảng màu:** San hô (`#e8695a`) đại diện cho sai lầm; Vàng kim (`#ffd54a`) cho số thứ tự chương; Ngọc lam (`#5cc8c0`) cho cách làm đúng; Navy (`#0a1c2b`) nền vững chãi.
- **Tâm trạng âm nhạc:** Tiết tấu dứt khoát, nhịp gõ rõ ràng; mỗi chương bắt đầu bằng một cú đánh nhạc (impact hit) mạnh mẽ.
- **Phong cách phụ đề (Sub style):** `inline_pop_trai` (phụ đề nảy từ trái sang sắc nét).
- **Chữ ký chuyển động:** "Thẻ số chương" (chapter badge): Số 1, 2, 3 xuất hiện bằng cú quét nhanh rồi dừng (whip pan settle), mỗi lần hạ xuống có âm đóng dấu SFX `dong_dau`.
- **Ngân sách Flow:** 1 clip Flow duy nhất (cảnh 1, 10 giây = 10% thời lượng). Có bản thay thế bằng cảnh mã `STACK_WAREHOUSE`.

---

## 1. Bảng phân cảnh 100 giây chi tiết (14 shot)

| Shot | Giây | Thời lượng | Vai trò | Layout | Chuyển động chính | Cú máy | Chuyển cảnh vào | Thay thế khi không Flow |
|---|---|---|---|---|---|---|---|---|
| s01 | 0 - 10 | 10s | Hook | `FLOW_ORIGAMI` | Cảnh nhà kho / văn phòng đối mặt với khủng hoảng quản lý | pull back | - | `STACK_WAREHOUSE` (C) bản mở |
| s02 | 10 - 15 | 5s | Giới thiệu 3 sai lầm | `KINETIC_TITLE` | Tiêu đề lớn: "3 SAI LẦM KHIẾN DOANH NGHIỆP TẮC NGHẼN" | whip pan rồi dừng | push | - |
| s03 | 15 - 25 | 10s | Sai lầm 1 | `STACK_WAREHOUSE` (C) | Thẻ số 1 dập xuống: Kho dồn đống quá tải, xe nâng không kịp bốc dỡ | crane lên | cover | - |
| s04 | 25 - 29 | 4s | Chốt 1 | `MARK_PHRASE` | Dòng câu chốt: "Ôm đồm việc không phân loại" khoanh đỏ | rack focus | dissolve | - |
| s05 | 29 - 39 | 10s | Sai lầm 2 | `PIPELINE_RAIL` (B) | Thẻ số 2 dập xuống: Quy trình duyệt đơn kẹt cứng ở khâu thủ công | dolly dọc | push | - |
| s06 | 39 - 43 | 4s | Chốt 2 | `WORD_SWAP` | Từ hoán đổi: "Chờ sếp" -> "Mất khách" -> "Lỡ cơ hội" | static | grid | - |
| s07 | 43 - 53 | 10s | Sai lầm 3 | `CASH_RIVER` (A) | Thẻ số 3 dập xuống: Chi phí vận hành rò rỉ ngầm dưới lòng sông | lia ngang rồi đẩy vào | split | - |
| s08 | 53 - 57 | 4s | Chốt 3 | `STAT_RING` | Vòng tròn đỏ quét 45% dòng tiền hao tổn vô hình | push in | scale | - |
| s09 | 57 - 67 | 10s | Tổng kết số liệu | `LIVE_DASHBOARD` (E) | Biểu đồ tổng kết thiệt hại, kim chỉ báo mức rủi ro cao | lướt thị sai | push | - |
| s10 | 67 - 73 | 6s | Chuyển sang cách đúng | `KINETIC_TITLE` | Chữ chuyển từ màu San hô sang Ngọc lam: "GIẢI PHÁP TỪ GỐC" | push in | radial | - |
| s11 | 73 - 83 | 10s | Ba việc đúng | `CHECKLIST` | 3 hành động tháo gỡ triệt để được tích xanh vững chắc | push in | cover | - |
| s12 | 83 - 89 | 6s | Chỉ số theo dõi | `KPI_CARDS` | Bộ thẻ KPI mục tiêu trượt vào khẳng định tương lai tăng trưởng | push in | scale | - |
| s13 | 89 - 95 | 6s | Chuyển trọng tâm | `CARD_SHIFT` | Chuyển đổi tư duy: từ "Quản lý sự vụ" sang "Vận hành hệ thống" | rack focus | push | - |
| s14 | 95 - 100 | 5s | Kêu gọi | `CTA_CLOSE` | Thẻ kêu gọi hành động khám sức khỏe doanh nghiệp cùng BAHA | static | blur | - |

---

## 2. Ngân sách lời đọc và âm tiết

- Tốc độ chuẩn: 3.8 âm tiết/giây (ngưỡng 3.0 - 4.2).
- Phân bổ âm tiết:
  - s01 (10s): 30 - 42 âm tiết
  - s02 (5s): 15 - 21 âm tiết
  - s03 (10s): 30 - 42 âm tiết
  - s04 (4s): 12 - 17 âm tiết
  - s05 (10s): 30 - 42 âm tiết
  - s06 (4s): 12 - 17 âm tiết
  - s07 (10s): 30 - 42 âm tiết
  - s08 (4s): 12 - 17 âm tiết
  - s09 (10s): 30 - 42 âm tiết
  - s10 (6s): 18 - 25 âm tiết
  - s11 (10s): 30 - 42 âm tiết
  - s12 (6s): 18 - 25 âm tiết
  - s13 (6s): 18 - 25 âm tiết
  - s14 (5s): 15 - 21 âm tiết
- Tổng toàn bộ: 360 - 390 âm tiết.
