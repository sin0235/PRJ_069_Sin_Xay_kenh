# Kế hoạch khôi phục flow video AI tự động

Ngày: 2026-10-23

## Mục tiêu

Cho phép tạo project thật trong Video Studio và tự động đưa một brief qua Flow tạo video, Flow Music tạo nhạc, timeline và bộ render TikTok để nhận MP4 9:16. Dùng các API, provider và FFmpeg hiện có; không thêm thư viện, không dùng provider trả phí, không ghi cookie/khóa vào repo, không sửa tư liệu gốc.

Founder đã yêu cầu triển khai pipeline AI tự động, thay cho giới hạn Pro-Assisted ở kế hoạch M-P6. Quyền dùng Flow phụ thuộc phiên Flow đã đăng nhập; nếu provider không sẵn sàng, flow phải báo lỗi, không sinh media giả.

## Thực trạng đã kiểm tra

- API `http://127.0.0.1:8000/readyz`: `ready`, `offline_mode=true`.
- UI `http://127.0.0.1:3000`: HTTP 200.
- DB offline có bảng `production_projects` nhưng không có project nào.
- DB offline chưa có bảng `platform_llm_configurations`; 9Router `127.0.0.1:20128` không lắng nghe; LLM không khả dụng.
- FFmpeg/FFprobe sẵn có. Asset Flow 9:16 1080x1920, H.264/AAC, 30 fps, 10.005 giây đã giải mã đầy đủ.
- Workspace không có Git metadata nên không thể tạo worktree hoặc ghi commit baseline.

## Phạm vi thi công

1. Viết test API đỏ cho tạo/liệt kê project và kiểm tra project/workspace.
2. Thêm route tạo/liệt kê project, dùng service hiện có và quyền `media.read`/`media.upload`.
3. Truyền `project_id` qua sinh video, mở rộng, upload và lọc asset theo project; bảo vệ tệp đầu vào extension bằng validator hiện có và tên tạm do server tạo.
4. Thêm hành động tự động trong project: Flow sinh video 9:16, Flow Music tạo nhạc khi được bật, timeline gồm video/nhạc/chú thích do người dùng cung cấp, lưu version rồi kết xuất bằng API hiện có.
5. Thay các liên kết `proj_01` bằng project thật; hiển thị lỗi provider/xác thực/lưu/render rõ ràng.
6. Chạy test an toàn có mock provider, typecheck/build; không chạy test nào gọi Flow thật mặc định.

## Tiêu chí hoàn thành

- Tạo và mở project mới được trong workspace, tải lại vẫn giữ project/timeline/assets.
- Project A không thấy asset riêng của project B; project của workspace khác trả 404.
- Video tạo/mở rộng và nhạc sinh ra được liên kết với đúng project.
- Một thao tác tạo video tự động chạy tuần tự; giới hạn concurrency bằng 1; render chỉ chạy sau khi timeline lưu thành công.
- Provider thất bại thì không tạo asset/timeline thành công giả; tệp gốc được giữ nguyên.
- MP4 cuối có thể giải mã đầy đủ và đạt 1080x1920, 30 fps, audio mục tiêu -14 LUFS ±1 LUFS.

## Giới hạn hiện thời

Không thể tự sinh ý tưởng/kịch bản bằng LLM cho tới khi Platform LLM được cấu hình và gateway chạy. Flow Music/Video thật cần phiên đăng nhập Flow khả dụng trên máy chạy API. Chưa gọi provider thật trong bước kiểm kê.

## Kết quả triển khai ngày 2026-10-23

- Hoàn tất route tạo/liệt kê project, kết nối project với video/music/extension và lọc asset theo project; bổ sung kiểm tra workspace, xác thực upload và tên tệp tạm an toàn cho extension.
- Giao diện Video Studio có nút tự động chạy Flow Music → Flow Video 9:16 → lưu timeline/phụ đề → render MP4; bỏ route `proj_01` cố định.
- Sửa nhãn nguồn Omni giả thành nguồn Flow và phản ánh đúng kết quả xóa watermark.
- Kiểm tra: 4 kiểm thử liên quan đạt; `pnpm exec tsc --noEmit` đạt. Có một cảnh báo deprecation Starlette/httpx.
- Runtime được kiểm tra ở chế độ offline; project list workspace mặc định rỗng; Flow Music capability bật, chi phí khai báo 0 USD, cờ yêu cầu phê duyệt bật. Chưa gọi provider thật và chưa xác nhận đăng nhập Flow; chưa có LLM/9Router để tự sinh kịch bản hoặc giọng đọc. Vì thế chưa có MP4 AI thành phẩm để nghiệm thu.
- Kiểm tra Playwright headless vào UI trả HTTP 200 và tải được script nhưng vẫn đứng tại màn xác minh quyền truy cập, nên chưa xác nhận thao tác trên giao diện.
- Bằng chứng đầu ra thực tế và cập nhật trang hành trình chưa ghi vì các vị trí đó nằm ngoài vùng ghi được phép trong phiên này.

## Ki?m th? 9Router v? video m?u ? 2026-10-23

- C?u h?nh LLM ??c kh?a t? `9router.env` ? runtime, ch?n `cx/gpt-6-luna`; 35 model ???c li?t k?, model ?? ch?n g?i th?nh c?ng.
- ?? ch?y ph?n t?ch h?nh m?u, sinh ba ph? ??, m? r?ng 16:9 sang 9:16, render timeline v?i ?m thanh g?c v? x?c minh MP4 1080 x 1920, 30 fps, 6 gi?y, -13.93 LUFS.
- S?a renderer ?? xu?ng d?ng ph? ?? v? s?a bi?n ?nh khung ??u ch?a khai b?o trong route m? r?ng.
- Ki?m th? c?u h?nh/client 34 ??t; API/video 5 ??t. Bi?n b?n v? video n?m trong `sin_content_api/data/media_storage/video_thu_nghiem_9router/`.
- API ?ang ch?y tr?n c?ng 8000 ch?a n?p c?u h?nh m?i; instance ki?m tra m?i tr?n c?ng 8001 tr? tr?ng th?i `ready`. Google Flow ch?a ???c g?i trong l??t n?y.
- To?n b? backend sau s?a ??t 317/317; API ki?m th? c?ng 8001 tr? `ready` r?i ?? d?ng. API c?ng 8000 ch?a ???c kh?i ??ng l?i.
