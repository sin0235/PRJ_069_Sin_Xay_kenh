# Khung mẫu video V3: Dòng chảy (Follow the Flow)

- **Mã mẫu:** `V3`
- **Ý tưởng chủ đạo:** Máy quay di chuyển "đi theo" một vật thể origami biểu tượng xuyên suốt các cảnh (đồng xu, kiện hàng, hồ sơ); vật thể này đóng vai trò là "sợi chỉ đỏ" kết nối toàn bộ diễn biến câu chuyện từ đầu đến cuối.
- **Bài áp dụng tiêu biểu:** Bài 08, Bài 09, Bài 12.
- **Bảng màu:** Ngọc lam (`#5cc8c0`) chủ đạo trên nền Navy (`#0a1c2b`); San hô (`#e8695a`) xuất hiện tại các điểm vật thể bị tắc nghẽn hoặc rò rỉ; Vàng kim (`#ffd54a`) điểm nhấn.
- **Tâm trạng âm nhạc:** Trôi chảy, nhịp nhàng, cảm giác chuyển động liên tục không ngừng nghỉ.
- **Phong cách phụ đề (Sub style):** `da_sac_phan_tang` (phụ đề đa sắc tách lớp thanh thoát).
- **Chữ ký chuyển động:** "Vật dẫn đường" (guide object match cut): Cùng một vật xuất hiện ở cuối cảnh trước và tiếp nối ở đầu cảnh sau theo hướng chuyển động đồng quy (cảnh 3 sang 4, cảnh 4 sang 6, cảnh 6 sang 8).
- **Ngân sách Flow:** Đúng 1 clip Flow duy nhất (cảnh 1, 10 giây = 10% thời lượng). Có bản thay thế bằng cảnh mã `CASH_RIVER`.

---

## 1. Bảng phân cảnh 100 giây chi tiết (13 shot)

| Shot | Giây | Thời lượng | Vai trò | Layout | Chuyển động chính | Cú máy | Chuyển cảnh vào | Thay thế khi không Flow |
|---|---|---|---|---|---|---|---|---|
| s01 | 0 - 10 | 10s | Hook | `FLOW_ORIGAMI` | Giới thiệu vật dẫn đường (đồng xu / kiện hàng) bắt đầu hành trình | pull back | - | `CASH_RIVER` (A) bản mở |
| s02 | 10 - 16 | 6s | Câu chốt | `KINETIC_TITLE` | Tiêu đề hiện ra, vật dẫn đường lướt ngang qua màn hình | push in | push | - |
| s03 | 16 - 26 | 10s | Dòng chảy vào | `CASH_RIVER` (A) | Vật trôi dọc theo dòng sông giấy, chia làm các nhánh nhỏ | lia ngang | cover | - |
| s04 | 26 - 36 | 10s | Qua quy trình | `PIPELINE_RAIL` (B) | Cùng vật đó chuyển lên băng chuyền quy trình, đi qua các trạm | dolly dọc | scale | - |
| s05 | 36 - 42 | 6s | Quy mô | `STAT_RING` | Vòng tròn quét chỉ số chi phí vận hành tăng vọt | push in | dissolve | - |
| s06 | 42 - 52 | 10s | Dồn lại | `STACK_WAREHOUSE` (C) | Vật dồn về kho, các chồng hàng cao vút quá vạch an toàn, rung nhẹ | crane lên | push | - |
| s07 | 52 - 58 | 6s | Cách gọi | `WORD_SWAP` | Từ hoán đổi bản chất: "Tồn đọng" -> "Chậm luân chuyển" -> "Chôn vốn" | static | grid | - |
| s08 | 58 - 68 | 10s | Rò rỉ | `FUNNEL` | Vật rơi qua phễu phân loại, rò rỉ mất mát ở tầng vận hành | crane xuống | radial | - |
| s09 | 68 - 74 | 6s | Điểm nhấn | `MARK_PHRASE` | Câu insight cốt lõi, bút vẽ khoanh tròn từ khóa giải pháp | rack focus | split | - |
| s10 | 74 - 84 | 10s | Số liệu | `LIVE_DASHBOARD` (E) | Cột mọc thẳng tắp, kim đo chuyển về vùng xanh an toàn | lướt thị sai | push | - |
| s11 | 84 - 90 | 6s | Việc cần làm | `CHECKLIST` | 3 bước khơi thông dòng chảy được đánh dấu hoàn thành | push in | cover | - |
| s12 | 90 - 95 | 5s | Chốt ý | `KINETIC_TITLE` | Chữ kết luận đanh thép, vật dẫn đường bay vào vị trí trung tâm | pull back | scale | - |
| s13 | 95 - 100 | 5s | Kêu gọi | `CTA_CLOSE` | Thẻ kêu gọi hành động BAHA, nút đăng ký khám doanh nghiệp | static | blur | - |

---

## 2. Ngân sách lời đọc và âm tiết

- Tốc độ chuẩn: 3.8 âm tiết/giây (ngưỡng 3.0 - 4.2).
- Phân bổ âm tiết:
  - s01 (10s): 30 - 42 âm tiết
  - s02 (6s): 18 - 25 âm tiết
  - s03 (10s): 30 - 42 âm tiết
  - s04 (10s): 30 - 42 âm tiết
  - s05 (6s): 18 - 25 âm tiết
  - s06 (10s): 30 - 42 âm tiết
  - s07 (6s): 18 - 25 âm tiết
  - s08 (10s): 30 - 42 âm tiết
  - s09 (6s): 18 - 25 âm tiết
  - s10 (10s): 30 - 42 âm tiết
  - s11 (6s): 18 - 25 âm tiết
  - s12 (5s): 15 - 21 âm tiết
  - s13 (5s): 15 - 21 âm tiết
- Tổng toàn bộ: 360 - 390 âm tiết.
