# Kế hoạch triển khai dọn dữ liệu test và mock

> **Dành cho người thực thi:** làm tuần tự trong phiên hiện tại; kiểm tra từng bước trước khi chuyển bước.

**Mục tiêu:** Gỡ các bản ghi giả đang hiển thị trong SIN Creator OS và làm sạch hai cơ sở dữ liệu E2E mà vẫn giữ fixture phục vụ kiểm thử.

**Cách làm:** Sao lưu nhất quán hai SQLite E2E, chuyển các tệp media chỉ được E2E tham chiếu sang thư mục khôi phục, rồi xóa dữ liệu hàng trong DB E2E. Loại bỏ nguồn dữ liệu tĩnh và fallback giả khỏi giao diện; trạng thái rỗng hiển thị rõ ràng. Sửa test double Flow đang thiếu phương thức mà mã thật gọi.

**Công nghệ:** Next.js/TypeScript, FastAPI/Python, SQLite, pytest.

## Ràng buộc

- Chỉ ghi trong `03_ban_lam_viec/` và file trạng thái được phép trong `00_bat_dau/`.
- Không thay đổi DB live, DB offline, media nguồn, checkpoint hoặc dịch vụ production.
- Giữ test fixtures, adapter tổng hợp chỉ dùng cho test và provider giả dành riêng cho test.
- Không khởi chạy LLM, worker tạo video, Google Flow hoặc TTS trong kiểm thử.

## Điểm cần rà soát

- Chỉ dọn media E2E nếu đường dẫn nằm trong `03_ban_lam_viec/media_assets/` và không được DB offline tham chiếu; sao lưu có thể khôi phục trước khi chuyển.
- Trang dùng API phải phân biệt danh sách rỗng với lỗi kết nối, không thay bằng nội dung giả.
- Test Flow phải mô phỏng `get_attribute` đúng với interface của Playwright.

## Nhiệm vụ 1: Sao lưu và làm sạch dữ liệu E2E

**Tệp:** `sin_content_api/sin_content_e2e_test.db`, `sin_content_api/baha_auth_e2e_test.db`; các tệp media E2E riêng trong `media_assets/`; bản sao lưu trong `sin_content_api/scratch/`.

- [ ] Ghi nhận số dòng, SQLite integrity và các media key đang được DB E2E/offline tham chiếu.
- [ ] Dùng SQLite backup API tạo bản sao lưu nhất quán; kiểm tra `integrity_check` và SHA-256.
- [ ] Chuyển riêng media E2E không được DB khác tham chiếu vào bản sao lưu trong `scratch/`.
- [ ] Xóa dữ liệu hàng trong hai DB E2E, giữ schema; kiểm tra integrity và số dòng sau dọn.

## Nhiệm vụ 2: Gỡ dữ liệu giả khỏi giao diện

**Tệp:** `sin_creator_os/src/data/mock-creator-data.ts` và các caller; `ai-job-indicator.tsx`, `job-service.ts`, `script-service.ts`, các trang `scripts/[id]`, `trends`, `competitors`, `discover/[contentId]`, `ideas/generate`, `ai-studio`, `media`, `content`, `dashboard`; `tiktok-service.ts`.

- [ ] Chạy kiểm tra hồi quy nguồn để xác nhận các trang đang tham chiếu dữ liệu tĩnh.
- [ ] Thay danh sách giả bằng API thật nếu đã có; nếu chưa có nguồn dữ liệu, hiển thị trạng thái rỗng.
- [ ] Gỡ fallback trả dữ liệu giả khi API lỗi; không xóa fixture hoặc mẫu nội dung thuộc luồng nghiệp vụ.
- [ ] Chạy kiểm tra TypeScript/build và quét lại để bảo đảm không còn caller tới bộ dữ liệu mock đã gỡ.

## Nhiệm vụ 3: Sửa test Flow và xác minh

**Tệp:** `sin_content_api/tests/test_bat_buoc_dang_nhap_flow.py`.

- [ ] Cập nhật test double `Locator` để trả thuộc tính `aria-pressed` như Playwright.
- [ ] Chạy lại test Flow bị lỗi, sau đó chạy toàn bộ suite backend với SQLite RAM.
- [ ] Chạy `pnpm run build`.
- [ ] Khởi động API/UI bằng DB SQLite RAM, worker và LLM tắt; kiểm tra health/readiness và các route liên quan.
- [ ] Lưu log kiểm chứng trong `sin_content_api/08_kiem_thu/bang_chung/`.
