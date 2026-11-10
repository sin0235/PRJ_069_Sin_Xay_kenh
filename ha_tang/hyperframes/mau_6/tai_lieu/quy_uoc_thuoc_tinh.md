# Quy ước thuộc tính cho các thành phần chuyển động HyperFrames (T02)

Ngày ban hành: 09/11/2026
Tài liệu quy định bắt buộc cho tất cả các cảnh thành phần (A đến F) và các khối hoạt hoạ trong dự án 6 mẫu video HyperFrames nhằm phục vụ kiểm định tự động qua Cổng G3 (Chuyển động).

---

## 1. Mục đích và nguyên lý

Quy ước này biến nguyên tắc vật lý "vật thể có nguồn vào, có đích ra, có khối lượng, không dịch chuyển tức thời và không tự xuất hiện/biến mất kỳ dị" thành dữ liệu có thể đo đạc, ghi vết (trace) và kiểm thử tự động 100% tại từng khung hình (30 fps).

---

## 2. Bốn thuộc tính bắt buộc trên mọi phần tử chuyển động

Mọi phần tử tham gia hoạt hoạ trong sub-composition hoặc cảnh mã nguồn bắt buộc phải có 4 thuộc tính HTML data attributes sau:

### 2.1 `data-obj` (Định danh duy nhất)
- Chuỗi định danh duy nhất của vật trong cảnh.
- Cú pháp: `<loai>-<so>` (ví dụ: `coin-01`, `coin-02`, `card-lead`, `box-03`, `forklift-01`).

### 2.2 `data-kind` (Phân loại thực thể)
Gồm một trong 4 loại:
1. `prop`: Vật thể vật lý thật (đồng xu, thẻ giấy, hộp, xe nâng, nhân vật, kim đồng hồ, cột biểu đồ). Đây là đối tượng chịu kiểm tra khắt khe nhất của Cổng G3.
2. `text`: Nhãn chữ, số, tiêu đề, chip kết luận. Được phép hiện/tan bằng độ mờ (opacity).
3. `light`: Đèn tín hiệu, chớp sáng, ánh sáng nền. Được phép bật tắt/mờ.
4. `fx`: Hiệu ứng hạt bụi, vệt sáng, xoáy nước, bóng đổ. Không tính vào hạn ngạch số lượng vật thể chính.

### 2.3 `data-src` (Nguồn gốc xuất hiện)
Quy định cách thức và vị trí vật xuất hiện trong cảnh:
- `static`: Đã có sẵn trên sân khấu từ khung hình 0 (ví dụ: mặt bàn, nền xưởng, bệ đứng).
- `offscreen-left`: Di chuyển vào khung hình từ mép trái ngoài màn hình (x < 0%).
- `offscreen-right`: Di chuyển vào khung hình từ mép phải ngoài màn hình (x > 100%).
- `offscreen-top`: Rơi/đi vào từ phía trên mép khung hình (y < 0%).
- `offscreen-bottom`: Trồi lên từ phía dưới ngoài khung hình (y > 100%).
- `spawn-from:<data-obj>`: Sinh ra từ một vật thể nguồn cụ thể (ví dụ thẻ việc sinh ra từ bàn tay nhân vật: `spawn-from:char-01`, hay hộp bung ra từ pallet).
- `unfold-from:<data-obj>`: Mở nếp gấp ra từ một vật thể origami mẹ.

### 2.4 `data-dst` (Đích đến khi rời đi)
Quy định điểm kết thúc của vật thể:
- `stay`: Ở lại trên sân khấu cho đến hết thời lượng cảnh.
- `offscreen-left` / `offscreen-right` / `offscreen-top` / `offscreen-bottom`: Di chuyển ra ngoài mép khung hình tương ứng.
- `sink-into:<data-obj>`: Chui/chìm vào một vật khác (ví dụ: đồng xu xoáy lọt vào miệng cống: `sink-into:drain-hole`).
- `fold-into:<data-obj>`: Gấp lại và thu vào bên trong vật khác.
- `occluded-by:<data-obj>`: Bị che khuất hoàn toàn bởi một vật ở lớp trước.

---

## 3. Quy tắc kiểm duyệt tự động Cổng G3

1. **Vật thể `prop` không được hiện ra hoặc biến mất giữa khung hình:** Nếu một vật `prop` xuất hiện sau thời điểm 0 giây, `data-src` bắt buộc phải là một trong các giá trị ngoài màn hình hoặc `spawn-from` / `unfold-from`. Nghiêm cấm dùng `opacity: 0 -> 1` tại chỗ cho `prop`.
2. **Không dịch chuyển tức thời:** Khoảng cách di chuyển của tâm vật giữa 2 khung hình liên tiếp không vượt quá 12% kích thước khung hình (trừ cú whip-pan có chủ đích tối đa 24%).
3. **Gia tốc giảm dần:** Khi dừng lại, vật phải có ít nhất 0.15 giây giảm tốc độ (easing như `power2.out`, `back.out`), không được dừng đột ngột.
4. **Nhịp 2.5 giây:** Trong mọi cửa sổ 2.5 giây trượt (75 khung hình), phải có ít nhất một sự kiện chuyển động mới (vật mới vào, đổi camera, hoặc đổi tiêu điểm).
