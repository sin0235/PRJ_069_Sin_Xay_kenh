# Khung mẫu video V1: Điểm đau, nguyên nhân, cách gỡ (Pain, Cause, Fix)

- **Mã mẫu:** `V1`
- **Ý tưởng chủ đạo:** Kể một nỗi đau vận hành quen thuộc của doanh nghiệp, bóc tách điểm rò rỉ cốt lõi, và đưa ra 3 bước tháo gỡ cụ thể.
- **Bài áp dụng tiêu biểu:** Bài 01 (Doanh nghiệp bận rộn), Bài 02, Bài 13.
- **Bảng màu:** Navy (`#0a1c2b`) nền, San hô (`#e8695a`) cho điểm đau, chuyển dần sang Ngọc lam (`#5cc8c0`) cho giải pháp, Vàng kim (`#ffd54a`) điểm xuyết.
- **Tâm trạng âm nhạc:** Trầm, căng nhẹ ở nửa đầu; chuyển biến tươi sáng, nhịp nhàng và rõ ràng ở nửa sau.
- **Phong cách phụ đề (Sub style):** `tu_dong` (phụ đề động bo góc thanh thoát).
- **Chữ ký chuyển động:** Điểm đỏ (red dot) nhấp nháy đánh dấu chỗ rò rỉ xuất hiện ở cảnh 3, 7 và 9; sau cảnh 11 điểm này chuyển thành xanh ngọc báo hiệu luồng vận hành đã thông suốt.
- **Ngân sách Flow:** 2 clip (cảnh 1 và 12, tổng 20 giây = 20% thời lượng). Có bản thay thế 100% bằng mã cho chế độ không Flow.

---

## 1. Bảng phân cảnh 100 giây chi tiết (13 shot)

| Shot | Giây | Thời lượng | Vai trò | Layout | Chuyển động chính | Cú máy | Chuyển cảnh vào | Thay thế khi không Flow |
|---|---|---|---|---|---|---|---|---|
| s01 | 0 - 10 | 10s | Hook | `FLOW_ORIGAMI` | Cảnh văn phòng giấy, chủ doanh nghiệp bận rộn giữa đống giấy tờ | pull back | - | `PIPELINE_RAIL` (bản mở) |
| s02 | 10 - 15 | 5s | Câu chốt | `KINETIC_TITLE` | Chữ lớn "BẬN RỘN HAY PHÁT TRIỂN?" hiện từng từ | push in | push | - |
| s03 | 15 - 25 | 10s | Nỗi đau xảy ra | `PIPELINE_RAIL` (B) | Băng chuyền 3 trạm, thẻ hồ sơ dồn ứ tại trạm duyệt, rơi khỏi ray | dolly dọc băng chuyền | cover | - |
| s04 | 25 - 31 | 6s | Quy mô | `STAT_RING` | Vòng tròn quét tới 65%, con số thất thoát tăng vọt | push in | scale | - |
| s05 | 31 - 39 | 8s | Nguyên nhân gốc | `MARK_PHRASE` | Dòng câu nhận diện vấn đề, bút vẽ khoanh cụm then chốt | rack focus | dissolve | - |
| s06 | 39 - 47 | 8s | Nhánh nguyên nhân | `HUB_SPOKE` | Tâm điểm hệ thống toả ra 3 nhánh: Khách hàng, Nhân sự, Chi phí | orbit nhẹ | push | - |
| s07 | 47 - 55 | 8s | Chỗ rò rỉ | `FUNNEL` | Phễu tiếp nhận khách hàng, hạt trôi rơi rò rỉ tại tầng chăm sóc | crane xuống | radial | - |
| s08 | 55 - 61 | 6s | Cách gọi | `WORD_SWAP` | Từ hoán đổi liên tục "Mất đơn" -> "Chậm trễ" -> "Nghẽn quy trình" | static | grid | - |
| s09 | 61 - 71 | 10s | Số liệu thật | `LIVE_DASHBOARD` (E) | Cột biểu đồ 3D mọc, đường xu hướng đỏ dâng cao, kim đồng hồ cảnh báo | lướt thị sai | push | - |
| s10 | 71 - 77 | 6s | Chuyển ý | `KINETIC_TITLE` | Tiêu đề chuyển tiếp: "LỘ TRÌNH GỠ NGHẼN BẰNG AI" | whip pan rồi dừng | split | - |
| s11 | 77 - 85 | 8s | Ba bước gỡ | `CHECKLIST` | 3 việc tích dấu xanh lần lượt: Khám vận hành, Định vị rò rỉ, AI hoá | push in | cover | - |
| s12 | 85 - 95 | 10s | Kết quả | `FLOW_ORIGAMI` | Văn phòng thông suốt, khách hàng được phản hồi tức thì, chủ DN thảnh thơi | pull back | blur | `BEFORE_AFTER` |
| s13 | 95 - 100 | 5s | Kêu gọi | `CTA_CLOSE` | Thẻ nhận diện thương hiệu BAHA, nút đăng ký khám doanh nghiệp miễn phí | static | scale | - |

---

## 2. Ngân sách lời đọc và âm tiết

- Tốc độ đọc: 3.8 âm tiết/giây (ngưỡng an toàn 3.0 đến 4.2).
- Phân bổ chi tiết:
  - s01 (10s): 30 - 42 âm tiết
  - s02 (5s): 15 - 21 âm tiết
  - s03 (10s): 30 - 42 âm tiết
  - s04 (6s): 18 - 25 âm tiết
  - s05 (8s): 24 - 33 âm tiết
  - s06 (8s): 24 - 33 âm tiết
  - s07 (8s): 24 - 33 âm tiết
  - s08 (6s): 18 - 25 âm tiết
  - s09 (10s): 30 - 42 âm tiết
  - s10 (6s): 18 - 25 âm tiết
  - s11 (8s): 24 - 33 âm tiết
  - s12 (10s): 30 - 42 âm tiết
  - s13 (5s): 15 - 21 âm tiết
- Tổng ngân sách toàn bài: 360 - 390 âm tiết (khớp mục tiêu 380 âm tiết).
