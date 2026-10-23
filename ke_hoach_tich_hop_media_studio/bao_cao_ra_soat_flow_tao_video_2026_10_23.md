# Báo cáo rà soát flow tạo video

- Ngày: 2026-10-23
- Phạm vi: Video Studio, Media Studio API, tạo project, tư liệu, Flow, mở rộng video, timeline và render.
- Cách rà soát: đọc mã nguồn, hợp đồng API, kế hoạch Media Studio và trạng thái checkpoint; chưa chạy API, trình duyệt hoặc kiểm thử.
- Kết luận: flow hiện tại chưa thể bắt đầu ổn định từ một project mới. Một số chức năng xử lý đã có ở backend nhưng chưa được nối vào trải nghiệm Studio.

## Phát hiện

### Chặn luồng tạo video

1. **Không có API tạo project.** `MediaStudioService.create_project()` tồn tại trong `sin_content_api/src/modules/media_studio/service.py`, nhưng router không gọi nó và không có endpoint tạo project. Giao diện vẫn mở `/video-studio/proj_01`; `GET /projects/{project_id}/timeline` kiểm tra project tồn tại trong workspace trước khi trả timeline. Project mới vì vậy không có đường đi từ giao diện đến bản ghi mà timeline yêu cầu.

2. **Các lối vào khác cũng trỏ đến project giả định.** `/video-studio` chuyển hướng cứng đến `proj_01`; trang Nội dung và trang Kịch bản cũng điều hướng đến cùng ID. Việc mở Studio từ các màn hình này không tạo project và không chuyển ngữ cảnh project thật.

### Asset không đi cùng project

3. **Tạo video không nhận project ID.** Frontend `GenerateVideoParams` không có `project_id`; `POST /video/generate` cũng không nhận ID này; `VideoOrchestrator` lưu asset chỉ theo workspace. Video tạo ra không thuộc project đang mở.

4. **Mở rộng video chưa được gọi từ Studio và kết quả không gắn project.** Có helper `mediaStudioApi.expandVideo()` và endpoint `/video/expand`, nhưng không có caller trong giao diện. Endpoint không nhận `project_id` và bản ghi output không đặt `project_id`.

5. **Thư viện lấy asset toàn workspace.** Studio gọi `listAssets()` với workspace cố định `default_ws`, không truyền project ID. Người dùng có thể thấy asset của project khác; thao tác mở rộng/tạo mới cũng không nhất quán với project đang xem.

### Hành vi sai lệch và an toàn xử lý

6. **Tùy chọn xóa watermark bị bỏ qua khi sinh video.** UI truyền `remove_watermark`, nhưng `generateVideo()` không gửi trường này; backend cũng không nhận nó. Provider luôn gọi xử lý watermark với giá trị cố định `true`.

7. **Nhãn “Omni chính thức” có thể không đúng với provider thực tế.** `GoogleOfficialOmniProvider` gọi lại `GoogleFlowZeroCostProvider`, sau đó đổi `source_product` thành `GEMINI_OMNI_API`. Nếu bật `use_official_omni`, nguồn ghi nhận không phản ánh đường tạo video thật.

8. **Endpoint mở rộng đọc tệp không giới hạn và ghép tên tệp trực tiếp vào đường dẫn tạm.** `/video/expand` đọc toàn bộ nội dung vào RAM rồi tạo `input_path` từ tên tệp do người dùng gửi, không gọi validator upload hiện có. Cần đưa validation, giới hạn dung lượng và chuẩn hóa tên tệp vào cùng ranh giới trước khi chạy FFmpeg.

9. **Lỗi tải dữ liệu bị che thành thư viện rỗng.** `listAssets()` trả `[]` khi API lỗi; `loadTimeline()` chỉ ghi cảnh báo console. Người dùng có thể hiểu nhầm lỗi xác thực/mạng hoặc project không hợp lệ thành project mới chưa có tư liệu.

10. **Luồng “tự động” gọi Flow qua điều khiển trình duyệt.** Endpoint sinh video gọi provider dùng Playwright và chờ tối đa 240 giây. Kế hoạch Media Studio hiện hành mô tả Flow Pro-Assisted: người dùng tự thao tác rồi nhập video vào project. Mã runtime và kế hoạch đang mâu thuẫn; cần thống nhất cổng sử dụng trước khi giữ hoặc bỏ đường tự động.

11. **Client có bearer token phát triển được nhúng sẵn.** `AuthApi.getAuthToken()` rơi về `DEFAULT_DEV_TOKEN` khi không có phiên đăng nhập. Điều này làm các thao tác Studio gửi credential mặc định thay vì dừng với trạng thái yêu cầu đăng nhập; cần xử lý tại ranh giới xác thực trước khi dùng dữ liệu thật.

## Luồng đích tối thiểu

1. Người dùng mở Video Studio và thấy danh sách project của workspace hoặc tạo project mới.
2. Khi tạo project thành công, giao diện điều hướng bằng ID do API trả về; không dùng ID dựng sẵn.
3. Thư viện chỉ tải asset thuộc project hiện tại, đồng thời có lựa chọn xem asset dùng chung trong workspace nếu người dùng cần.
4. Người dùng nạp video Flow 16:9 hoặc chọn asset sẵn có, mở rộng sang 9:16, xem kết quả và nhận asset mới gắn đúng project.
5. Người dùng thêm asset vào timeline, lưu version, tải lại để khôi phục và chỉ render từ version đã lưu.
6. Mọi lỗi đăng nhập, tải project, mở rộng, lưu và render đều hiển thị tại giao diện; không đổi lỗi thành trạng thái rỗng hoặc thành công.

## Thứ tự xử lý đề xuất

1. Dựng prototype và chốt trải nghiệm mở/tạo project, chọn tư liệu, mở rộng Flow, timeline và trạng thái lỗi.
2. Bổ sung endpoint tạo/list project theo quyền workspace hiện có; nối route và mọi lối vào Studio vào project thật.
3. Truyền `project_id` xuyên suốt sinh/mở rộng/upload asset; lọc thư viện theo project.
4. Chuẩn hóa xác thực và upload mở rộng; bỏ token mặc định khỏi luồng sản phẩm; kiểm thử tenant, tên tệp và giới hạn dung lượng.
5. Chốt Flow Pro-Assisted hay tự động hóa được phép dùng; bảo đảm nhãn provider và provenance khớp đường chạy.
6. Hiển thị lỗi đúng trạng thái; chạy kiểm thử API, kiểm thử UI, typecheck và build sau khi có duyệt prototype.

## Cổng dự án

Kế hoạch hiện có `ke_hoach_mo_rong_video_studio_media_first_2026_10_23.md` đã quy định M-P1 phải có prototype và Founder duyệt trước khi code API/render. Báo cáo này không thay đổi runtime, không chạy test, không cập nhật checkpoint. Cần Founder duyệt prototype và phạm vi xử lý rồi mới triển khai các bước trên.
