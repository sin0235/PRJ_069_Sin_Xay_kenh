# Ghi Chú Các Khối Lớp Phủ (HyperFrames Overlay Layers)

Tài liệu ghi nhận quá trình kiểm thử, chọn lọc và bản địa hóa các khối bảng tên (lower third) và lớp phủ môi trường (ambient overlay) từ HyperFrames 0.8.222 registry cho hệ thống dựng video tự động.

---

## 1. Danh sách các khối được giữ lại (Kept Blocks)

Tất cả các khối dưới đây đã được làm sạch bằng `hf_vendor.localize`, loại bỏ toàn bộ CDN bên ngoài (GSAP, Google Fonts) và kiểm định hiển thị dấu tiếng Việt đầy đủ.

### A. Bảng tên người nói (Lower Thirds)
1. **`lt-clean-bar.html`**:
   - Thẻ bảng tên phẳng hiện đại với dải màu nhấn cam (`.lt-tab`), nền thẻ trắng, tên và chức danh rõ ràng.
   - Hiển thị dấu tiếng Việt rất nét, không bị tràn viền hay lệch vị trí.
   - Chuỗi mẫu ban đầu: Tên `"Dr. Maya Chen"`, Chức danh `"Host · Neuroscientist"`.

2. **`lt-accent-underline.html`**:
   - Bảng tên dạng chữ nổi bật kèm đường gạch dưới hoạt hóa màu ngọc lam (`.lt-rule`).
   - Phông chữ Oswald hỗ trợ bộ ký tự tiếng Việt đầy đủ, các chữ hoa có dấu (Đ, Ắ, Ễ, Ộ, Ứ) hiển thị chuẩn xác.
   - Chuỗi mẫu ban đầu: Tên `"Dr. Maya Chen"`, Chức danh `"Host · Neuroscientist"`.

3. **`lt-side-rule.html`**:
   - Bảng tên với thanh dọc màu ngọc lam bên trái (`.lt-bar`), tên và chức vụ căn lề trái.
   - Bố cục thông thoáng, hiển thị tốt tiếng Việt trong vùng an toàn góc dưới.
   - Chuỗi mẫu ban đầu: Tên `"Dr. Maya Chen"`, Chức danh `"Host · Neuroscientist"`.

4. **`lt-soft-pill.html`**:
   - Bảng tên dạng viên con nhộng bo tròn (`.lt-pill`) với chấm trạng thái màu cam (`.lt-dot`).
   - Phông chữ Montserrat hỗ trợ đầy đủ tiếng Việt, hiệu ứng trượt vào êm ái.
   - Chuỗi mẫu ban đầu: Tên `"Dr. Maya Chen"`, Chức danh `"Host · Neuroscientist"`.

### B. Lớp phủ môi trường & ánh sáng (Ambient & Light Leaks)
1. **`starfield.html`**:
   - Lớp phủ hạt sao đêm nhấp nháy đa tầng và trôi nhẹ nhàng theo trục ngang.
   - Nền trong suốt (`background: transparent`), có mặt nạ xuyên tâm (radial mask) giữ cho vùng trung tâm màn hình luôn thông thoáng cho nhân vật và phụ đề.
   - Độ mờ đục điều chỉnh ở mức nhẹ (0.22), giữ nguyên độ rõ nét của cảnh bên dưới.

2. **`grain-field.html`**:
   - Lớp tạo hạt phim (grain/dots) chuyển động vi mô tinh tế, tạo chất liệu điện ảnh (designed surface).
   - Được cài đặt dưới dạng component với `data-composition-id="grain-field"`, điều khiển qua các biến CSS.
   - Sử dụng ở độ mờ thấp (0.15) để tăng chiều sâu mà không làm đổi màu cảnh chính.

3. **`organic-light-leak-overlay.html`**:
   - Hiệu ứng rò rỉ ánh sáng máy quay phim hữu cơ (light leaks) với chế độ hòa trộn `mix-blend-mode: screen`.
   - Các quầng sáng hổ phách, đỏ và vàng ấm chỉ quét qua các góc cạnh, không che vùng trung tâm.
   - Sử dụng ở độ mờ nhẹ (0.18) làm lớp điểm xuyết chuyển động.

---

## 2. Danh sách các khối bị loại bỏ (Skipped Blocks) và lý do

1. **`halftone-field.html`**:
   - **Lý do**: Sử dụng shader WebGL với nền đen đặc (`#hlf-backdrop { background: #000000; }`) và các điểm chấm bán sắc (halftone dots) độ tương phản rất cao (độ lệch giá trị kênh màu lên tới 249 trên nền navy). Khối này quá nổi bật, che khuất gần như toàn bộ chi tiết cảnh chính và không đạt tiêu chí "tinh tế, nhẹ nhàng trên bảng màu dark navy".

2. **`lt-kicker-name.html`**:
   - **Lý do**:
     - Phông chữ `Archivo Black` không có bộ ký tự dấu tiếng Việt trong bảng mã Google Fonts (chỉ có latin/latin-ext), dẫn đến việc các ký tự tiếng Việt có dấu bị rơi về phông chữ dự phòng cọc cạch.
     - Cấu trúc khối được thiết kế riêng cho số tập phát sóng (`<span id="lt-kicker">Episode 47</span>`) thay vì hiển thị chức vụ/vai trò của diễn giả (`role`), không phù hợp với hợp đồng dữ liệu chuẩn của shot video.

3. **Các thành phần snippet (Registry snippets)**:
   - Các mục trong HyperFrames registry không có thuộc tính `data-composition-id` (như `number-wheel` hoặc các đoạn trích CSS) chỉ là đoạn mã nhúng trong một khối lớn hơn, không thể gắn độc lập làm sub-composition trong timeline. Chúng bị bỏ qua tự động theo hợp đồng thiết kế.

---

## 3. Cách tìm kiếm và thay thế chuỗi mẫu cố định (Literals)

Trong các khối lower third chính thức, tác giả định nghĩa trực tiếp nội dung mẫu trong cây DOM HTML (không qua biến `data-composition-variables`):
- `lt-clean-bar`: `<div id="lt-name" class="lt-name">Dr. Maya Chen</div>` và `<div id="lt-role" class="lt-role">Host · Neuroscientist</div>`
- `lt-accent-underline`: `<div id="lt-name" class="lt-name">Dr. Maya Chen</div>` và `<div id="lt-role" class="lt-role">Host · Neuroscientist</div>`
- `lt-side-rule`: `<div id="lt-name" class="lt-name">Dr. Maya Chen</div>` và `<div id="lt-role" class="lt-role">Host · Neuroscientist</div>`
- `lt-soft-pill`: `<div id="lt-name" class="lt-name">Dr. Maya Chen</div>` và `<div id="lt-role" class="lt-role">Host · Neuroscientist</div>`

Lưu ý: Dấu chấm giữa trong chuỗi chức danh là ký tự Unicode middle dot `·` (`\u00b7`).
Hàm `lower_third_for_shot` xây dựng từ điển `literals` để ánh xạ:
- `"Dr. Maya Chen"` -> `html.escape(name)`
- `"Host · Neuroscientist"` -> `html.escape(role)` nếu có `role`, hoặc `""` (chuỗi rỗng) nếu `role` vắng mặt.
Qua đó, hàm `hf_blocks.prepare_block` thay thế toàn bộ chuỗi mẫu tiếng Anh mà không để sót bất kỳ dấu vết nào trong composition đầu ra.
