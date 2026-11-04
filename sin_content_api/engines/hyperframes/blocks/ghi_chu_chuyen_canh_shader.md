# Khảo sát chuyển cảnh Shader HyperFrames (@hyperframes/shader-transitions)

## 1. Bối cảnh và mục tiêu khảo sát
Khảo sát khả năng ứng dụng gói chuyển cảnh shader chính thức `@hyperframes/shader-transitions@0.8.222` trên môi trường HyperFrames CLI 0.8.222, Node 24, Chrome headless (SwiftShader software GL) trên Windows (RAM 8 GB, không GPU phần cứng rời).

Tiêu chí thành công:
- Khung hình tại điểm giữa chuyển cảnh (mid-transition) hiển thị rõ hiệu ứng biến dạng/hòa trộn shader (không phải là chồng lấn đè phẳng thông thường).
- Quá trình dựng (render) hoàn tất trên môi trường SwiftShader mà không cần GPU rời.

---

## 2. Kết quả đo lường thực nghiệm 3 giả thuyết

Mỗi giả thuyết được kiểm thử bằng một lượt render thực tế độ dài 2,5 giây (`--start 4 --end 6.5 -q draft -w 1 -o out.mp4`), ghi nhận thời gian thực (wall-clock seconds) và trích xuất khung hình trước (4,2s), giữa (5,3s) và sau (6,2s) chuyển cảnh để so sánh sai khác pixel bằng Pillow (PIL).

### Giả thuyết (a): Đặt trực tiếp markup HTML cảnh nội tuyến (inline) trong index.html
- **Cấu hình**: Ba cảnh `<div id="s01..s03" class="scene">` được nhúng trực tiếp nội dung trong `index.html` (không dùng `data-composition-src`), sau đó gọi `HyperShader.init()`.
- **Thời gian render (2,5s video)**: 20,91 giây.
- **Tốc độ**: 8,36 giây thực / 1 giây video render.
- **Kết quả hình ảnh**: Khung hình giữa (5,3s) hoàn toàn giống hệt khung hình sau (6,2s) (`diff_s2 = False`). Cảnh sau (`#s02`) đã che phủ hoàn toàn cảnh trước (`#s01`) ngay từ mốc bắt đầu chuyển cảnh (4,8s). Không có bất kỳ hiệu ứng shader nào xuất hiện.
- **Đánh giá**: THẤT BẠI (chỉ là cắt đè phẳng - plain cut/overlap).

### Giả thuyết (b): Giữ sub-compositions, gọi init khi cảnh con được mount
- **Cấu hình**: Giữ cấu trúc `data-composition-src="compositions/s01..03.html"`, gán class `scene` cho các host element, gọi `HyperShader.init()` khi sẵn sàng trong vòng đời timeline.
- **Thời gian render (2,5s video)**: 21,24 giây.
- **Tốc độ**: 8,50 giây thực / 1 giây video render.
- **Kết quả hình ảnh**: Khung hình giữa (5,3s) hoàn toàn giống hệt khung hình sau (6,2s) (`diff_s2 = False`).
- **Đánh giá**: THẤT BẠI (chỉ là cắt đè phẳng - plain cut/overlap).

### Giả thuyết (c): Pre-render từng cảnh thành MP4 ngắn và dùng thẻ `<video class="scene">`
- **Cấu hình**: Tạo trước các clip MP4 bằng FFmpeg, dùng `<video id="s01..03" class="scene" src="...">` làm các cảnh cho `HyperShader.init()`.
- **Thời gian render (2,5s video)**: 40,87 giây.
- **Tốc độ**: 16,35 giây thực / 1 giây video render.
- **Ghi chú bộ nhớ**: Xuất hiện cảnh báo bộ nhớ Node.js: `MaxListenersExceededWarning: Possible EventEmitter memory leak detected. 11 error/close listeners added to [WriteStream]`. Tiến trình render video ngốn nhiều RAM hơn đáng kể.
- **Kết quả hình ảnh**: Khung hình giữa (5,3s) vẫn giống hệt khung hình sau (6,2s) (`diff_s2 = False`), không có biến dạng shader.
- **Đánh giá**: THẤT BẠI (chỉ là cắt đè phẳng - plain cut/overlap).

---

## 3. Nguyên nhân kỹ thuật gốc rễ (Root Cause Analysis)

Qua giải mã mã nguồn gói `@hyperframes/shader-transitions` (`dist/index.js`) và lõi render của HyperFrames CLI (`dist/chunk-SKCS4SUZ.js`):

1. **Cơ chế fallback trong Virtual Time (`function yf`)**:
   Khi chạy render dưới môi trường thời gian ảo (`window.__HF_VIRTUAL_TIME__ = true`), `HyperShader.init` không tạo canvas WebGL trong trang mà rơi vào hàm `yf`:
   ```javascript
   tl.set('#' + toScene, { opacity: 1 }, time);
   tl.set('#' + fromScene, { opacity: 0 }, time + duration);
   ```
   Do `toScene` có `z-index` cao hơn, lệnh `opacity: 1` ngay tại `time` khiến cảnh sau che khuất hoàn toàn cảnh trước trong toàn bộ cửa sổ chuyển cảnh.

2. **Cơ chế Page-side Compositing không khả dụng trên Headless Chrome**:
   Lựa chọn `--page-side-compositing` yêu cầu API thử nghiệm Blink `CanvasDrawElement` (`HTML-in-canvas`, kiểm tra qua hàm `nr()`: `layoutSubtree` và `drawElementImage()`). Chrome headless tiêu chuẩn (kể cả với SwiftShader) không kích hoạt tính năng này, khiến gói tự động ghi log cảnh báo và hạ cấp về chế độ lật opacity (`opacity-flip mode`):
   ```
   [HyperShader] page-side compositing requested but drawElementImage/WebGL is not available; falling back to opacity-flip mode
   ```

3. **Cơ chế Layered Compositing phía Node-side bị bỏ qua**:
   HyperFrames CLI trong môi trường headless không có phần cứng GPU tự động hạ cấp xuống chụp ảnh màn hình phẳng toàn chunk (`Browser capability probe selected screenshot capture for the entire chunk`), bỏ qua hoàn toàn luồng trộn shader đa lớp Node-side (`runSequentialLayeredFrameLoop`). Do đó ảnh chụp thực tế chỉ ghi lại trạng thái DOM đã bị đè phẳng bởi GSAP timeline.

---

## 4. Kết luận và kiến nghị

- Không có giả thuyết nào trong cả 3 giả thuyết đem lại hiệu ứng shader thực sự trong video render trên môi trường thử nghiệm.
- **Quyết định**: Giữ nguyên hằng số `SHADER_TRANSITIONS_SUPPORTED = False` trong `sin_content_api/src/modules/tao_video_noi_dung/hf_transitions.py`.
- Không đấu nối (wire) gói `@hyperframes/shader-transitions` vào `hf_project.py`.
- Toàn bộ nhu cầu chuyển cảnh giữa các cảnh host tiếp tục sử dụng các chuyển cảnh thuần GSAP trong `hf_transitions.py` (push, cover, scale, dissolve, radial, grid, blur, split) đã được chứng minh hoạt động ổn định, xác định và hiển thị rõ nét trên 100% các khung hình snapshot thực tế.
