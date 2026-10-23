# Báo cáo rà soát nguyên mẫu G1

Ngày rà soát: 23/10/2026  
Đối tượng: `nguyen_mau_tao_video_noi_dung.html`  
Phạm vi: đọc HTML/CSS/JavaScript và đối chiếu checklist G1, quy chuẩn phong cách kênh, quy tắc NO EMOJI/SVG. Đây là rà soát tĩnh; không sửa prototype/source, không gọi backend/provider/Flow, không đọc DB/WAL. Không chạy kiểm thử trình duyệt hoặc đo trên thiết bị.

## Kết luận

Prototype phù hợp để Founder xem luồng khung ban đầu: có nhãn “NGUYÊN MẪU · CHỜ DUYỆT”, nhập nội dung, chọn 60/120 giây, hiển thị phân cảnh, các bước sản xuất, QC mẫu và các blocker style/Harness. Tổng thời lượng cảnh khớp: 60 giây gồm 5 cảnh; 120 giây gồm 8 cảnh.

Chưa đạt điều kiện đóng G1. Đây là một màn hình mô phỏng luồng, chưa phải bộ prototype đầy đủ theo checklist: còn thiếu style board/profile và binding có thể duyệt, storyboard ba chủ đề, voice/preset được Founder chọn, thao tác sửa cảnh và gói tải; nhiều trạng thái bắt buộc chưa được trình bày. Chưa có bằng chứng thao tác desktop/mobile, bàn phím, screenshot hoặc biên bản Founder duyệt. Chưa chuyển G2 hoặc cấp quyền triển khai backend dựa trên prototype này.

## Đối chiếu G1

| Tiêu chí | Kết quả | Ghi nhận |
|---|---|---|
| Prototype trong thư mục kế hoạch, gắn nhãn mô phỏng | Đạt | Đúng vị trí; nhãn chờ duyệt và footer nói rõ trạng thái không kết nối API/Flow.
| Nhập nội dung và thời lượng 60/120 giây | Đạt một phần | Có textarea, chọn kênh/thời lượng. Chưa có chế độ lời đọc, upload/reference asset hoặc kiểm tra nội dung quá dài.
| Kịch bản, scene cards, prompt và thời gian | Đạt một phần | Có 5/8 cảnh, nhãn mục tiêu/lời đọc/prompt và thời lượng; prompt là mẫu tổng quát, chưa có voice/cost/source/claim và chưa duyệt nội dung.
| Tổng thời lượng đúng mục tiêu | Đạt | Mã dữ liệu tĩnh cộng đúng 60 giây và 120 giây; giao diện cập nhật tổng khi đổi lựa chọn.
| Chi phí, quota và blocker | Thiếu | Có thông báo chặn style/Harness, nhưng không có dự toán chi phí/credit hoặc trạng thái quota.
| Luồng sản xuất, preview, QC | Đạt một phần | Có 5 bước, khung minh họa, số liệu QC mẫu và nút “Xem luồng mẫu”. Không có player thật, timecode, waveform hoặc kết quả QC thực; giao diện có ghi rõ mô phỏng.
| Sửa một cảnh | Thiếu | Không có nút chỉnh, thay asset, sửa prompt, lưu revision hoặc xem diff theo scene.
| Gói tải | Thiếu | Có danh sách đầu ra dự kiến, chưa có nút tải hay biểu diễn manifest/hash/trạng thái file.
| Đường đi cho người không kỹ thuật | Đạt một phần | Không bắt người dùng nhập prompt từng shot và có summary lời đọc/prompt. Chưa có thao tác duyệt kịch bản hoặc tiếp tục/hủy một run.
| Style family, token/reference/voice và binding kênh | Thiếu, blocker Founder | Thẻ trạng thái nói chưa có binding đã duyệt; chưa có style board/profile, token thật, reference frame, sample voice hoặc biến thể series. Bảng màu prototype tái dùng một số màu web nhưng chưa có approval video.
| Storyboard ba chủ đề và rubric | Thiếu, blocker Founder | Chỉ có một chủ đề minh họa. Chưa có các storyboard AI Agent/Chatbot 60 giây, RAG/Fine-tuning 120 giây, workflow doanh nghiệp 120 giây để so độ nhất quán.
| Chốt preset, voice, tốc độ, caption, outro O1/O2/O3 | Thiếu, blocker Founder | Không có lựa chọn/biên bản duyệt. Hiển thị dọc 9:16, 1080 x 1920, 30 fps và -14 LUFS ±1 như thông tin mẫu, không phải quyết định G1.
| Trạng thái empty/loading/error/cancel/resume/revision conflict | Thiếu | Không có màn hình hoặc trạng thái tương ứng. Dòng thông báo LLM lỗi/thiếu style chỉ mô tả quy tắc, không phải trạng thái lỗi, phục hồi hay hủy có thể xem.
| Tình huống Flow mất phiên, thiếu TTS/recording | Thiếu | Không có lỗi, hướng dẫn khôi phục hoặc lựa chọn chờ cung cấp tư liệu.
| Founder duyệt và bằng chứng | Chưa có | Không có screenshot/bản lưu duyệt/biên bản trong artifact được rà soát. Không suy ra approval từ nhãn hoặc sự tồn tại của file.

## NO EMOJI và quy tắc biểu tượng

Quét tĩnh nội dung HTML không phát hiện ký tự trong các dải emoji/pictograph phổ biến. Không thấy biểu tượng Unicode hoặc emoji trong giao diện. Prototype hiện dùng ảnh logo raster (`logo.webp`) và không dùng biểu tượng giao diện; nếu bổ sung icon thì phải dùng SVG theo quy tắc dự án. Không có logo/wordmark nào được AI vẽ lại trong mã.

## Accessibility và tương tác

| Điểm kiểm | Nhận xét |
|---|---|
| Ngôn ngữ và cấu trúc | Có `lang="vi"`, viewport, một `main`, một `h1`, các tiêu đề `h2`, label gắn với `select`/`textarea`; logo có alt text. `details`/`summary` dùng phần tử native nên có hỗ trợ bàn phím mặc định.
| Điều hướng | Các mục sidebar là `div`, không phải `nav`/link/button, không có `aria-current`; ở màn hình nhỏ sidebar bị ẩn hoàn toàn và không có menu thay thế. Vì vậy không thể điều hướng chức năng bằng bàn phím hoặc công nghệ hỗ trợ.
| Focus/keyboard | Không có quy tắc focus tùy chỉnh hoặc bằng chứng kiểm tra keyboard. Các nút và trường form native có thể nhận focus; nút “Tạo video” disabled không thể nhận focus và lý do chặn chỉ nằm trong `title` cùng nội dung thẻ khác.
| Cập nhật nội dung | Scene list, bộ đếm ký tự, tổng thời gian và notice preview thay đổi bằng JavaScript nhưng không có live region/`aria-live`; người dùng screen reader có thể không được thông báo cập nhật.
| Tương phản | Tính tĩnh theo màu CSS cho các cặp được dùng trong chữ nhỏ: `#8292a4` trên trắng khoảng 3,18:1 và `#7b8a99` trên `#f8fafd` khoảng 3,38:1, thấp hơn ngưỡng 4,5:1 của chữ thường WCAG AA. Các cặp kiểm tra khác: `#526477`/trắng khoảng 6,09:1; `#2b6fb8`/trắng khoảng 5,16:1; trạng thái cảnh báo `#9c5c10`/`#fffaf0` khoảng 5,11:1. Đây là tính toán từ token CSS, chưa thay cho đo trên render thực tế.
| Responsive/tiếng Việt | Có media query chuyển layout một cột và HTML tiếng Việt; chưa có screenshot/kiểm tra trên thiết bị nhỏ. Font khai báo `Inter, Segoe UI, sans-serif` không được khóa thành font asset có license, glyph tiếng Việt hoặc hash.
| Chuyển động | Không thấy animation/transition đáng kể; không cần giảm chuyển động cho bản hiện tại. Nếu thêm motion ở prototype sau, cần tôn trọng `prefers-reduced-motion`.

## Blocker Founder và việc cần hoàn tất

1. Duyệt profile/family, binding mẫu, token/reference, logo và quyền dùng, font tiếng Việt có license, giọng/quyền dùng, nhạc và outro/CTA; ghi phiên bản, owner/reviewer, ngày, quyết định và hash asset.
2. Duyệt storyboard ba chủ đề bắt buộc và rubric đối chiếu style; xác nhận sample frame/voice hoặc ghi rõ hạng mục không áp dụng.
3. Chốt preset 9:16/1080 x 1920/30 fps, safe zone, caption, tốc độ lời, sai số tổng thời lượng và lựa chọn outro. Các con số trong prototype hiện chỉ là mẫu.
4. Bổ sung trạng thái giao diện G1 còn thiếu: empty, loading, lỗi LLM/Flow, thiếu TTS/recording, quá dài, quota, hủy, tiếp tục, xung đột revision; thể hiện thao tác duyệt, sửa một cảnh và tải gói.
5. Làm điều hướng bằng phần tử semantic và keyboard; thêm thông báo thay đổi cho screen reader; tăng tương phản chữ nhỏ navlabel/footer ít nhất đạt ngưỡng phù hợp; duyệt lại focus và layout mobile.
6. Lưu screenshot/render của prototype desktop và mobile, ghi nhận keyboard/tiếng Việt và biên bản Founder duyệt đúng phiên bản. Chỉ coi G1 hoàn tất khi có bằng chứng review thật theo checklist.

Nguồn đối chiếu: `ke_hoach_trien_khai_va_checklist.md` (G1), `quy_chuan_phong_cach_kenh.md` (profile và review pack), `dac_ta_bo_tao_video_hoan_chinh.md` (điều kiện prototype), `ma_tran_nghiem_thu.md`, `nguyen_mau_tao_video_noi_dung.html`.
