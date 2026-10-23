# Kế hoạch mở rộng Video Studio theo hướng dựng từ tư liệu — Implementation Plan

> **Dành cho agent thực thi:** AGY thực hiện tuần tự theo phase và cổng nghiệm thu trong tài liệu này. Chưa có phase nào được phép coi là hoàn tất nếu chưa có bằng chứng thực tế.

**Mục tiêu:** Mở rộng Video Studio để người dùng nhập ảnh và video của mình, sắp xếp và chỉnh sửa chúng thành video TikTok hoàn chỉnh; Flow là một lựa chọn tạo tư liệu, không phải đường đi bắt buộc.

**Kiến trúc:** Tái sử dụng MediaAsset, TimelineVersion, API tải tư liệu, thư viện UI và FFmpeg hiện có. Timeline được lưu theo phiên bản; render chỉ đọc asset gốc, tạo thành phẩm mới và giữ tenant boundary. Flow Pro-Assisted dùng thao tác chính thức do người dùng thực hiện; không tự động hóa trình duyệt hoặc dùng cookie phiên người dùng.

**Công nghệ:** Next.js/React và TypeScript hiện có; FastAPI, SQLAlchemy và SQLite kiểm thử hiện có; FFmpeg/FFprobe. Không thêm thư viện nếu các thành phần sẵn có đáp ứng yêu cầu.

**Đặc tả nguồn:** Yêu cầu Founder ngày 2026-10-23; phát hiện rà soát trong phiên; `03_ban_lam_viec/ke_hoach_tich_hop_media_studio/ke_hoach_tich_hop_media_studio.md`; quy tắc dự án trong `AGENTS.md`.

## Giao thức chống suy đoán khi thi công

AGY phải dùng bảng dưới đây như sổ chân lý của task. Mỗi nhận định mới phải được gắn một trong ba trạng thái: `ĐÃ ĐỐI SOÁT` (có đường dẫn/dòng hoặc lệnh và output), `GIẢ ĐỊNH` (cần Owner quyết định), `CHƯA KIỂM CHỨNG` (cần kiểm tra). Không đổi `CHƯA KIỂM CHỨNG` thành PASS chỉ dựa trên tài liệu cũ, lời kể hoặc code có vẻ liên quan.

| Nhận định | Trạng thái hiện tại | Bằng chứng trong repo / việc cần làm |
|---|---|---|
| Có endpoint upload, list, metadata và download media. | ĐÃ ĐỐI SOÁT | `sin_content_api/src/modules/media_studio/router.py`: `POST /upload`, `GET /assets`, `GET /assets/{asset_id}`, `GET /assets/{asset_id}/download`. Download route không khai báo `TenantContext`/`require_action`; `ttl` và `token` không được xác minh trong handler đã đọc. Handler truy vấn asset chỉ theo ID và mở file, nên hiện tại chưa tenant-safe. Đây là MUST FIX trước khi cho thư viện chứa tư liệu riêng tư. |
| Asset có `workspace_id`, `project_id`, MIME, SHA256 và asset cha; bảng `TimelineVersion` có `tracks_json`, `version`, `is_locked`. | ĐÃ ĐỐI SOÁT | `sin_content_api/src/models/entities.py`, các lớp `MediaAsset` và `TimelineVersion`. Chưa có kết luận rằng đã có API timeline. |
| Upload gọi `validate_audio_or_media_file`; hàm hiện chỉ có nhánh kiểm tra category `audio`. | ĐÃ ĐỐI SOÁT | `sin_content_api/src/modules/media_studio/service.py` và `security.py`. Chưa có kiểm tra chặt category ảnh/video tương đương audio. |
| Video Studio đặt preview mặc định bằng video mẫu ngoài thư viện, asset list chọn video/audio và timeline có track minh họa cố định. | ĐÃ ĐỐI SOÁT | `sin_creator_os/src/app/(main)/video-studio/[projectId]/page.tsx`. Xác nhận lại trên UI ở M-P0; không coi preview mặc định là tư liệu dự án. |
| Frontend hiện có hàm tạo Flow video, mở rộng video, upload asset chưa có trong client API và assemble video/audio. Không thấy hàm timeline. | ĐÃ ĐỐI SOÁT | `sin_creator_os/src/lib/api/media-studio-api.ts`; đối chiếu OpenAPI và `router.py` ở M-P0 trước khi thêm route. |
| Hàm assemble hiện nhận danh sách video cùng một asset audio; bộ xử lý concat dùng concat demuxer và `-shortest`. | ĐÃ ĐỐI SOÁT | `router.py` và `video_processor.py::assemble_scenes_with_audio`. Đây không phải bằng chứng hỗ trợ ảnh, trim, caption, fit hoặc loudness chuẩn đầu ra. |
| Flow client hiện điều khiển website bằng Playwright. | ĐÃ ĐỐI SOÁT | `cong_cu_tu_dong/flow_bridge/google_flow_client.py`; kế hoạch Media Studio gốc lại quy định Flow Pro-Assisted là người dùng tự thao tác. M-P0 phải ghi nhận xung đột; M-P6 không được mở rộng bot hoặc sử dụng session/profile. |
| Flow hỗ trợ chính xác loại ảnh tham chiếu mà UX định dùng tại thời điểm thi công. | CHƯA KIỂM CHỨNG | Chỉ xác nhận bằng HUMAN_VERIFIED trên website chính thức; nếu không xác nhận được, ghi BLOCKED_PROVIDER_UI. |
| Render có worker bền vững, kiểm soát concurrency = 1 và theo dõi trạng thái. | CHƯA KIỂM CHỨNG | M-P0 tìm entrypoint, state store và lệnh chạy thật trong `sin_content_workers/` hoặc runtime hiện hữu. Không tự đặt tên worker/endpoint rồi coi là có sẵn. |

### Quy tắc báo cáo và bằng chứng

- Trước mỗi phase, ghi SHA256 hoặc danh sách hiện trạng của đúng các tệp dự kiến đụng tới; workspace có thể không có Git metadata, nên không được báo cáo dựa riêng vào `git status`.
- Mỗi test mới phải có tên cụ thể, fixture, assertion và lệnh chạy. Mỗi fix đi theo thứ tự: thêm test tái hiện -> chạy thấy FAIL đúng lỗi -> sửa tối thiểu -> chạy PASS -> chạy regression của module.
- Test dùng fixture tổng hợp được phép kiểm tra xử lý cục bộ; không được dùng chúng làm bằng chứng Flow/AI thật. Bằng chứng provider thật phải có asset tải được, SHA256 và xác nhận của người vận hành.
- Ba test hiện có gọi trực tiếp provider thật và KHÔNG được chạy trong baseline mặc định: `test_gf02_04_flow_video_zero_cost`, `test_gf01_01_official_omni_provider`, `test_gf03_02_api_video_generate` trong `tests/test_media_studio_video.py`. Hai test đầu gọi `video_orchestrator.generate_video_scene`; test API gọi `/v1/media/video/generate`, route này cũng gọi orchestrator. Trước regression cuối, thay chúng bằng test provider có mock tường minh cho LOCAL_TESTED; việc chạy Flow thật chỉ thực hiện thủ công tại M-P6.
- Không dùng test hiện có assertion `approval_state == "APPROVED"` để xác nhận sản phẩm được duyệt. Tài sản render mới phải theo workflow duyệt hiện hành; tests cần xác minh trạng thái thực tế, không lặp lại giả định trong test cũ.
- Kết quả lệnh lưu đủ stdout/stderr, exit code, phiên bản runtime và ngày giờ; tóm tắt phải trỏ tới log gốc. `PASS`, `BLOCKED` và `NOT RUN` là ba trạng thái riêng. Không chuyển BLOCKED/NOT RUN thành PASS.
- Không chạy suite baseline trước khi đọc test fixture/provider để chắc chắn test không gọi tài khoản, Flow, mạng ngoài hoặc chi tiêu thật. Nếu có, cách ly test đó bằng mock rõ ràng cho LOCAL_TESTED; chỉ chạy provider thật ở cổng HUMAN/LIVE đã duyệt.
- `AGENTS.md` vừa giới hạn vùng ghi vào `03_ban_lam_viec/` và một số state file trong `00_bat_dau/`, vừa yêu cầu bằng chứng tại `08_kiem_thu/bang_chung/`. Đây là xung đột quyền ghi. M-P0 phải xin Owner/AGY xác định bằng văn bản nơi được phép ghi evidence trước khi chạy lệnh tạo artifact; không tự ý ghi ra ngoài vùng được phép.
- Nếu code hiện tại khác bất kỳ mô tả/tên hợp đồng nào trong plan, dừng bước phụ thuộc, cập nhật plan hoặc biên bản sai khác, nêu file/dòng và đề xuất, rồi chờ duyệt khi thay đổi hành vi/scope. Không âm thầm “đoán cho khớp”.

## Ràng buộc toàn cục

- Mã nguồn và tài liệu thi công chỉ nằm trong `03_ban_lam_viec/`; không sửa `01_nguon_goc_bat_bien/` hoặc `02_nguyen_ban_giai_nen/`.
- Nội dung UI, tài liệu, log và tên mới tuân thủ quy tắc tiếng Việt; không emoji hoặc unicode icon; biểu tượng dùng SVG/Lucide SVG.
- Trước khi viết backend nặng hoặc tự động hóa, AGY dựng prototype giao diện và lấy Founder duyệt tại cổng M-P1.
- Giữ nguyên tệp gốc. Mọi thao tác dựng tạo asset mới, có SHA256, nguồn gốc và liên kết asset cha khi phù hợp.
- Không giả lập đầu ra Flow/AI thành thành công. Không lưu session cookie, token hoặc khóa API trong repo.
- Mọi truy vấn và thao tác phải cách ly `workspace_id`; không thay đổi quyền Production hoặc mở rộng action RBAC nếu không có phase và phê duyệt riêng.
- Đầu ra TikTok: 1080x1920, 30 fps; âm thanh mục tiêu -14 LUFS ±1 LUFS; chữ nằm trong Safe Zone: trên 150 px, dưới 320 px, phải 120 px.
- Tác vụ FFmpeg/AI nặng có concurrency tối đa 1 trên môi trường dự án; không render đồng bộ kéo dài trong HTTP request.
- Chạy và lưu bằng chứng theo phase tại `08_kiem_thu/bang_chung/`; cập nhật CURRENT_STATE, hành trình và checkpoint chỉ sau khi gate tương ứng được duyệt.

## Phạm vi sản phẩm

### Bao gồm

- Nạp ảnh và video vào thư viện từ Video Studio, gắn với project đang mở.
- Dựng video từ danh sách phân cảnh gồm ảnh tĩnh và video: đổi thứ tự, bỏ phân cảnh, đặt thời lượng ảnh, cắt điểm vào/ra video, chọn cách vừa khung/cắt phủ.
- Xem trước đúng chuỗi phân cảnh, chữ, khung dọc và âm thanh sẽ xuất.
- Thêm track nhạc/giọng đọc, cấu hình mức âm và phụ đề chữ; các thiết lập phải đi vào timeline và file render, không chỉ hiện trên màn hình.
- Lưu/khôi phục timeline theo phiên bản và xuất MP4 TikTok.
- Giữ chức năng tạo video bằng Flow như một đường tạo tư liệu tùy chọn. Bổ sung quy trình ảnh tham chiếu sang video qua Flow Pro-Assisted nếu giao diện Flow chính thức hiện hành hỗ trợ; người dùng tự thao tác, tải kết quả về và nhập lại vào project.

### Chưa bao gồm

- Editor đa lớp kiểu NLE chuyên nghiệp: keyframe, mask, chroma key, hiệu ứng chuyển cảnh tùy biến, chỉnh màu từng frame.
- Tạo ảnh/nhạc/giọng đọc mới bằng API trả phí, hoặc tự động đăng nhập và thao tác Flow bằng Playwright.
- Thay đổi hệ thống duyệt bản quyền, publishing hoặc quyền RBAC Production.

### Giá trị mặc định cần Founder xác nhận tại M-P1

- Ảnh tĩnh dài 3 giây khi thêm vào timeline; người dùng chỉnh được thời lượng.
- Khung xuất mặc định 9:16; ảnh/video mặc định `cover`, người dùng đổi sang `contain`.
- Ảnh tham chiếu cho Flow được gửi thủ công trên website Flow; BAHA giữ ảnh gốc và chỉ nhập lại video kết quả.
- Ngưỡng dung lượng upload tối đa cho ảnh/video, sau khi M-P0 kiểm tra giới hạn runtime và storage thực tế.

## Tệp dự kiến và trách nhiệm

| Tệp | Trách nhiệm dự kiến |
|---|---|
| `03_ban_lam_viec/sin_creator_os/src/app/(main)/video-studio/[projectId]/page.tsx` | Luồng nạp tư liệu, thư viện, preview, timeline và thao tác dựng trong màn hiện có. |
| `03_ban_lam_viec/sin_creator_os/src/lib/api/media-studio-api.ts` | Gọi API upload, đọc/lưu timeline và render; giữ kiểu hợp đồng đồng bộ frontend/backend. |
| `03_ban_lam_viec/sin_content_api/src/modules/media_studio/router.py` | Endpoint timeline/render; kiểm soát quyền và workspace qua dependency hiện hành. |
| `03_ban_lam_viec/sin_content_api/src/modules/media_studio/service.py` | Tái sử dụng upload, truy vấn asset và project; sửa validation nếu kiểm thử phase xác nhận thiếu hỗ trợ ảnh/video. |
| `03_ban_lam_viec/sin_content_api/src/modules/media_studio/video_processor.py` | Chuẩn hóa clip, tạo phân cảnh ảnh, trim, overlay chữ, trộn âm và kiểm tra đầu ra. |
| `03_ban_lam_viec/sin_content_api/src/schemas/contracts.py` | Schema timeline/render request nếu không thể dùng schema hiện có một cách an toàn. |
| `03_ban_lam_viec/sin_content_api/src/models/entities.py` | Chỉ sửa nếu kiểm kê chứng minh TimelineVersion hiện có không đáp ứng lưu version; ưu tiên tái sử dụng bảng. |
| `03_ban_lam_viec/sin_content_api/tests/test_media_studio_p1.py` | Kiểm thử upload, MIME, project/workspace và tải tệp. |
| `03_ban_lam_viec/sin_content_api/tests/test_media_studio_video.py` | Kiểm thử timeline, ảnh tĩnh, clip video, render, âm thanh và hợp đồng API. |
| `03_ban_lam_viec/sin_creator_os/tests/e2e/` | Mở rộng harness hiện có để kiểm tra thao tác UI xuyên suốt; không tạo framework E2E mới. |

Đường dẫn trên là phạm vi dự kiến; M-P0 phải đối chiếu thực tế trước khi AGY sửa. Không tạo file nếu có thể mở rộng nơi đang được codebase sử dụng.

## Điểm cần kiểm tra trong toàn bộ kế hoạch

- Ảnh JPEG/PNG hợp lệ, ảnh lớn, ảnh sai phần mở rộng và dữ liệu hỏng phải có kết quả kiểm tra rõ ràng; ảnh không bị coi là audio/video.
- Video không có audio, video có audio, nhiều codec/FPS/độ phân giải khác nhau phải ghép được hoặc báo lỗi có thể hành động; không cắt cụt ngoài ý muốn.
- Timeline rỗng, asset không tồn tại, asset thuộc workspace khác, asset bị thiếu trên đĩa và ID lặp không được tạo bản render sai hoặc rò dữ liệu.
- Người dùng tải lại trang hoặc lưu timeline liên tục không làm đảo thứ tự clip hoặc mất bản timeline đã lưu.
- Render timeout/lỗi FFmpeg không được tạo asset thành công giả; tệp tạm phải được dọn an toàn, asset gốc phải còn nguyên.
- Chữ tiếng Việt, dấu câu và Safe Zone phải hiển thị đúng cả preview lẫn file MP4; âm lượng thành phẩm phải được đo, không suy ra từ metadata khai báo.

## Phase và cổng nghiệm thu

### M-P0 — Kiểm kê, baseline và ranh giới

**Đầu ra:** Bảng đối chiếu phát hiện với code thật, baseline test, ma trận luồng hiện có và danh sách Must Fix trước khi mở rộng. Kiểm tra panel ảnh, an toàn endpoint download, hợp đồng `expected_category`, giới hạn upload, lưu trữ, worker/render concurrency và phạm vi dùng Playwright Flow trong runtime. Đối chiếu các phát hiện của báo cáo audit 2026-10-22 với trạng thái repo hiện tại; không mặc định chúng đã được xử lý. Kiểm tra OpenAPI thực tế và xác nhận route download không thể truy cập chéo tenant hoặc ẩn danh trước khi dùng asset thật.

**Các bước:**

- [ ] Chụp danh sách và SHA256 hiện trạng của các file sẽ có khả năng thay đổi; ghi rõ nếu Git metadata không khả dụng. Không sửa file trong M-P0.
- [ ] Đọc test fixtures và từng test trong ba module media; đánh dấu `LOCAL_SAFE`, `LIVE_PROVIDER`, `EXTERNAL_NETWORK` hoặc `UNKNOWN`. Dùng `UNKNOWN` là chưa được chạy.
- [ ] Đối soát router/schema/OpenAPI, upload validation, đường dẫn MediaAsset storage, download auth, TimelineVersion, video processor và worker; trích dẫn file/symbol cụ thể vào evidence ledger.
- [ ] Kiểm tra các phát hiện audit 22 mục có liên quan tới luồng media; phân loại `REPRODUCED`, `FIXED_WITH_EVIDENCE`, `NOT_REPRODUCED` hoặc `OUT_OF_SCOPE`. Với `NOT_REPRODUCED`, đính kèm lệnh kiểm chứng.
- [ ] Chạy backend safe subset nêu dưới đây và frontend typecheck/build. Nếu thư mục evidence chưa được Owner/AGY phân xử quyền ghi, dừng trước lệnh sinh artifact và xin quyết định; không tự ghi sang `08_kiem_thu/`.
- [ ] Ghi baseline lỗi nguyên trạng; không sửa lỗi trong phase audit, không xóa test, không tắt kiểm tra để tạo baseline xanh.

**Lệnh baseline đã đối soát với repo:**

- Backend safe subset, working directory `03_ban_lam_viec/sin_content_api`: `python -m pytest -q tests/test_media_studio_p1.py::test_b04_upload_security_rejects_malicious_files tests/test_media_studio_p1.py::test_b05_media_validation_probe_and_checksum tests/test_media_studio_video.py::test_gf02_01_probe_video_specs tests/test_media_studio_video.py::test_gf02_02_verify_tiktok_vertical_9_16 tests/test_media_studio_video.py::test_gf02_03_tiktok_safe_zone_compliance tests/test_media_studio_video.py::test_gf03_01_assemble_scenes_with_audio tests/test_media_studio_video.py::test_gf03_03_api_video_assemble`.
- Không chạy cả ba file test media theo module cho tới khi từng test được phân loại. Cụ thể loại ba test provider thật nêu trong giao thức; rà các test còn lại trong `test_media_studio_music.py` và `test_media_studio_p1.py` để chắc chắn không đụng Flow/API/mạng/tài khoản thật.
- Frontend, working directory `03_ban_lam_viec/sin_creator_os`: `pnpm exec tsc --noEmit`, sau đó `pnpm run build` (`package.json` không khai báo script `typecheck`; không thay thế bằng lệnh giả định).
- UI harness hiện có, chỉ khi dev server đã được AGY khởi chạy và kiểm tra URL: `python tests/e2e/run_ui_verification.py`. Harness đang chụp 8 route; bản thân nó chưa chứng minh thao tác upload/timeline/render.

Trước khi chạy backend suite, rà soát test provider và fixture. Suite không được phép dùng Flow thật, tài khoản thật hoặc API tính phí. Ghi baseline riêng từng lệnh; không sửa runtime trong M-P0.

**Gate M-P0 PASS khi:** Có sổ chân lý cập nhật với đường dẫn/dòng hoặc lệnh cho từng nhận định; safe subset có raw output; build/typecheck có raw output hoặc trạng thái BLOCKED lý do rõ; audit xác nhận download, upload validation, storage path và worker behavior; ba provider tests được loại khỏi lệnh mặc định và có kế hoạch thay bằng mock; từng phát hiện audit cũ được phân loại; xung đột thư mục evidence được Owner/AGY phân xử bằng văn bản; không còn lỗi bảo toàn file gốc, tenant boundary hoặc giả báo thành công chưa có người chịu trách nhiệm. Không có mạng/tài khoản ngoài trong baseline. Nếu một điều kiện thiếu, phase là BLOCKED, chưa bắt đầu M-P1/M-P2.

### M-P1 — Prototype UI và duyệt trải nghiệm

**Đầu ra:** Prototype tĩnh/click-through trên route Video Studio, không gọi render hoặc Flow. Hiển thị rõ hai lựa chọn: dựng từ tư liệu có sẵn và tạo tư liệu bằng AI/Flow. Luồng prototype: nạp ảnh/video, xem thư viện, thêm/sắp xếp phân cảnh, chỉnh thời lượng/crop, xem preview, thêm chữ/âm thanh và xuất.

**Các bước:**

- [ ] Tạo prototype chỉ trong `sin_creator_os/` theo layout route hiện có; dữ liệu là fixture hiển thị rõ là mẫu, không gọi API hay provider.
- [ ] Trình bày trọn luồng từ mở project, nạp ảnh/video, timeline, caption, hai track âm thanh riêng (voice và music), preview và export state.
- [ ] Prototype các trạng thái rỗng, đang tải, upload lỗi, timeline chưa lưu, conflict version và render lỗi; không thiết kế chỉ happy path.
- [ ] Dùng viewport 1440x900 và viewport hẹp đã được Founder chọn; kiểm tra keyboard/focus/labels và Safe Zone theo số pixel của canvas 1080x1920.
- [ ] Chụp prototype và walkthrough; ghi quyết định/điều chỉnh trong biên bản. Không code API/render trong phase này.

**Kiểm chứng:** Walkthrough trực tiếp trên màn hình với Founder; ghi phản hồi và quyết định về mặc định ảnh 3 giây, `cover/contain`, track âm thanh/phụ đề, xử lý project hiện có và điểm handoff Flow.

**Gate M-P1 PASS khi:** Founder duyệt prototype và phạm vi MVP bằng văn bản trong biên bản phase; các giá trị mặc định được chốt; không còn hành vi UI chưa rõ có ảnh hưởng đến kết quả xuất. Chưa có duyệt thì không bắt đầu phase API/render.

### M-P2 — Nhập ảnh/video và thư viện tư liệu

**Đầu ra:** Người dùng có thể tải một hoặc nhiều ảnh/video từ Studio vào project. Tận dụng endpoint `/v1/media/upload` và xác thực tệp hiện có; frontend gửi `expected_category` phù hợp MIME, nhận URL tải an toàn, cập nhật thư viện và preview ảnh/video bằng loại media đúng. Tư liệu gắn `project_id`; file nguồn giữ nguyên.

**Các bước thi công:**

- [ ] Thêm test API phân loại MIME/category: `test_b09_upload_image_video_category_validation` trong `tests/test_media_studio_p1.py`. Assertion: JPEG/PNG chỉ qua `image`; MP4 chỉ qua `video`; audio chỉ qua `audio`; category sai, file rỗng, hỏng hoặc MIME không khớp bị từ chối với 4xx; DB không có asset mới và không còn file tạm.
- [ ] Thêm `test_b11_upload_rejects_oversize_file` theo đúng ngưỡng Owner duyệt; assert HTTP 413/4xx và không có asset/tệp dở dang. Không tự chọn con số dung lượng trước M-P1.
- [ ] Thêm `test_b12_upload_safe_name_and_project_scope`; tên chứa path traversal phải được chuẩn hóa/từ chối, asset phải gắn đúng `project_id`, workspace khác không được gán project.
- [ ] Chạy riêng test mới và lưu output FAIL do hành vi thiếu trước khi sửa; đồng thời thêm negative test cho endpoint download chưa auth để chứng minh lỗi hiện tại trước khi fix.
- [ ] Sửa `security.py::validate_audio_or_media_file` để kiểm tra allowlist theo category, magic bytes/ffprobe cần thiết và giới hạn upload đã chốt ở M-P1; giữ ZIP chỉ ở category được thiết kế; không nới lỏng kiểm tra audio cũ.
- [ ] Thêm test tenant tải xuống: `test_b10_download_requires_workspace_authorization`. Assertion: thiếu auth bị 401/403; tenant sở hữu đọc được; tenant khác nhận 404; token/TTL sai hoặc hết hạn bị từ chối nếu signed URL được chọn; bytes trả về khớp SHA256.
- [ ] Sửa route download hiện có trong `router.py`; không tạo route download thứ hai. Ghi cách hỗ trợ video seek/Range và kiểm chứng bằng request Range; không chấp nhận URL công khai không hạn hoặc token không được xác minh.
- [ ] Thêm `mediaStudioApi.uploadAsset({file, project_id, expected_category})` trong `media-studio-api.ts`; category suy ra từ MIME đã kiểm tra client-side nhưng backend vẫn là ranh giới tin cậy.
- [ ] Thêm điều khiển upload trong tab Tư Liệu tại `page.tsx`; lọc ảnh/video/audio bằng MIME thực trả về; render thumbnail ảnh, player video/audio; hiển thị tiến trình, lỗi và kết quả tải lại.
- [ ] Chạy safe subset backend đã chốt ở M-P0 cộng tests mới; kiểm tra SHA256 nguồn trước/sau; chạy `pnpm exec tsc --noEmit`.

**Gate M-P2 PASS khi:** Tất cả test mới và regression đạt; API trả metadata chính xác; tệp sai loại bị chặn trước khi ghi; request tải xuống không thể đọc chéo tenant và hỗ trợ seek theo quyết định M-P0; E2E nạp ít nhất một ảnh PNG, một ảnh JPEG và một MP4 trong workspace kiểm thử; asset xuất hiện đúng project; không có sample ảnh/video thay vào kết quả thật.

**Lệnh kiểm tra:** Tại `03_ban_lam_viec/sin_content_api`, chạy `python -m pytest -q tests/test_media_studio_p1.py -k "b09 or b10 or b11 or b12"`, sau đó safe subset M-P0. Kết quả mong đợi: toàn bộ test được chọn PASS, exit code 0; số test thu thập và số PASS được ghi theo output thật.

### M-P3 — Hợp đồng và lưu timeline phiên bản

**Đầu ra:** Dùng `TimelineVersion.tracks_json` để lưu snapshot version nếu phù hợp. Hợp đồng timeline tối thiểu gồm canvas, danh sách clip theo thứ tự, `asset_id`, `media_type`, `start_ms`, `duration_ms`, `trim_in_ms`, `trim_out_ms`, `fit`; tối đa một track `voice` và một track `music`, mỗi track có `asset_id`, vị trí, thời lượng, gain; track music có cấu hình ducking đã được Founder duyệt; caption gồm text, thời gian, vị trí an toàn và cỡ chữ. Lưu/đọc qua API theo project và workspace. Validate quan hệ thời lượng/trim, loại asset, giá trị fit, quyền project và version; lưu bản mới bất biến, không sửa version đã khóa.

**API dự kiến:** `GET /v1/media/projects/{project_id}/timeline` trả version mới nhất; `PUT /v1/media/projects/{project_id}/timeline` nhận payload timeline và `expected_version`, trả version vừa lưu. Nếu kiểm kê phát hiện chuẩn route hoặc schema hiện có khác, AGY cập nhật hợp đồng trước khi triển khai và ghi lý do trong evidence.

**Các bước thi công:**

- [ ] Trước khi tạo endpoint, kiểm tra router/schema/service/model hiện tại và quyền project. Xác nhận đường dẫn `TimelineVersion` và `ProductionProject` qua code, không suy ra API từ ORM.
- [ ] Chốt Pydantic contract cụ thể trong `schemas/contracts.py`: `TimelineClip`, `TimelineAudioTrack`, `TimelineCaption`, `TimelineDocument`; mọi thời gian là số nguyên millisecond; `clip_id` ổn định; `asset_id` bắt buộc; `media_type` được suy ra từ MIME asset ở server; `fit` chỉ là `cover|contain`; không nhận storage path từ client; `expected_version` là số nguyên.
- [ ] Thêm tests đỏ trong `tests/test_media_studio_video.py`: `test_timeline_get_returns_latest_version`, `test_timeline_put_round_trips_document`, `test_timeline_put_rejects_stale_version`, `test_timeline_put_rejects_cross_workspace_assets`, `test_timeline_put_rejects_invalid_trim_and_unknown_fields`, `test_timeline_put_does_not_modify_locked_version`.
- [ ] Chỉ sau khi tests đỏ đúng nguyên nhân, thêm hai route `GET/PUT /v1/media/projects/{project_id}/timeline` ở `router.py`, dùng `require_action("media.read")` cho GET và quyền ghi đã được xác nhận trong RBAC ở PUT. Nếu chưa có action quyền phù hợp, dừng và yêu cầu phê duyệt thay đổi RBAC; không tái sử dụng `media.upload` như quyền chỉnh timeline nếu chưa chứng minh phù hợp.
- [ ] Dùng transaction để đọc version mới nhất, so `expected_version`, tạo version bất biến tiếp theo; không overwrite version cũ. Chỉ thêm migration nếu M-P0 chứng minh bảng chưa tồn tại hoặc thiếu cột bắt buộc; kèm migration forward/rollback test.
- [ ] Kiểm tra unique index cho `(project_id, version)`; nếu thiếu, xử lý race condition bằng migration/index hoặc locking có test concurrency. Không dựa riêng vào kiểm tra version ở frontend.
- [ ] Chạy từng test mới; sau đó chạy backend media suite. Lưu request/response test và version records.

**Lệnh kiểm tra:** Tại `03_ban_lam_viec/sin_content_api`, chạy `python -m pytest -q tests/test_media_studio_video.py -k timeline_`. Kết quả mong đợi: các test timeline mới PASS, exit code 0; ghi lại số test thực tế được chọn.

**Gate M-P3 PASS khi:** Contract được validate server-side; GET/PUT tenant-safe; GET trả version mới nhất; PUT round-trip chính xác clip/voice/music/caption; OCC conflict trả 409 kể cả hai ghi đồng thời; khóa không bị sửa; asset refs hợp lệ; migration không phát sinh nếu không cần; toàn bộ test assertions cụ thể nêu trên đạt.

### M-P4 — Dựng và xem trước thực từ timeline

**Đầu ra:** Thư viện cho phép thêm/bỏ clip; timeline thể hiện chính các asset đang chọn theo thứ tự; kéo đổi thứ tự hoặc thao tác điều khiển thứ tự có thể tiếp cận bằng bàn phím; thời lượng ảnh chỉnh được; clip video có điểm vào/ra; khung preview đổi giữa ảnh/video đúng theo playhead; caption và vùng an toàn lấy từ timeline, không dùng track minh họa hard-code. Tự lưu chỉ sau khi hợp đồng M-P3 được chốt; hiển thị lỗi lưu/thất bại.

**Các bước thi công:**

- [ ] Tạo prototype tĩnh/click-through theo duyệt M-P1 trước; so từng khu vực với biên bản duyệt và chốt selectors/labels ổn định cho E2E.
- [ ] Dùng component và dependency đã có trong repo; kiểm tra thư viện sortable hiện hữu trước khi thêm drag-and-drop code. Nếu đổi thứ tự bằng drag, cung cấp nút lên/xuống hoặc cách bàn phím tương đương.
- [ ] Thay preview URL mẫu và timeline hard-code; tạo preview từ asset thật, playhead và timeline đã tải qua API M-P3. Giải phóng object URL khi đổi/tắt component.
- [ ] Chỉ gọi render sau khi lưu timeline thành công. Khi save trả 409, giữ local edit và cho người dùng tải lại/giải quyết conflict; không âm thầm ghi đè.
- [ ] Mở rộng `tests/e2e/run_ui_verification.py` bằng kịch bản `video_studio_media_first`; assertion: upload, thêm asset, reorder, duration, trim, fit, caption, lưu, reload, khôi phục. Dùng API/test data trong workspace kiểm thử; không dựa trên tài khoản hoặc nội dung production.
- [ ] Chạy typecheck/build và E2E; lưu ảnh chụp các trạng thái empty, ảnh/video trong timeline, lỗi lưu và preview.

**Lệnh kiểm tra:** Tại `03_ban_lam_viec/sin_creator_os`, chạy `pnpm exec tsc --noEmit`, `pnpm run build`, rồi `python tests/e2e/run_ui_verification.py` khi API và frontend test server đã được xác nhận là môi trường kiểm thử. Kết quả mong đợi: ba lệnh exit code 0; E2E assertion cho scenario media-first đều PASS.

**Gate M-P4 PASS khi:** E2E chứng minh đúng dữ liệu sau reload; preview cập nhật theo playhead; không sample URL hoặc track demo; keyboard-accessible reorder và input có label; loading/empty/error state có mô tả tiếng Việt; lỗi 409/lỗi mạng không làm mất nội dung chưa lưu.

### M-P5 — Render MP4 từ ảnh, video, chữ và âm thanh

**Đầu ra:** Endpoint render nhận timeline version đã lưu; kiểm tra tenant và asset; chuẩn hóa mỗi phân cảnh bằng FFmpeg/FFprobe; ảnh tĩnh được tạo thành clip đúng duration; video trim đúng in/out; áp dụng `cover/contain`; burn-in caption tiếng Việt vào Safe Zone; trộn audio theo thời gian và gain; xuất MP4 H.264/AAC 1080x1920, 30 fps, audio -14 LUFS ±1. Render phải chạy qua worker bền vững, concurrency = 1; M-P0 phải xác định worker cụ thể trước khi thi công. Nếu hiện chưa có, M-P5 dừng để Founder duyệt kiến trúc worker trước khi code. Frontend theo dõi trạng thái và chỉ hiện download khi file được kiểm tra xong. Tạo asset mới có SHA256, project, provenance và trạng thái chưa duyệt phù hợp; không tự đặt APPROVED/PUBLISH_READY.

Track voice và music được trộn riêng theo thời gian. Ducking chỉ áp dụng lên music khi voice có tín hiệu; nếu không có voice thì music không bị sidechain. Không cắt âm thanh bằng `-shortest` trước khi xác định duration của timeline. Bằng chứng loudness phải đo file đã render.

**Các bước thi công:**

- [ ] M-P0 phải chỉ ra worker bền vững đang chạy thật. Nếu chưa có worker phù hợp, trước khi code đề xuất hợp đồng job, storage trạng thái, retry/timeout, concurrency lock và rollback; Founder duyệt thiết kế này. Không dùng FastAPI in-process BackgroundTasks để giả concurrency bền vững.
- [ ] Thêm test xử lý thuần trong `tests/test_media_studio_video.py`: `test_timeline_render_image_only`, `test_timeline_render_video_only`, `test_timeline_render_mixed_order_and_durations`, `test_timeline_render_burns_vietnamese_caption`, `test_timeline_render_respects_fit_mode`, `test_timeline_render_audio_shorter_and_longer_than_video`, `test_timeline_render_failure_never_creates_asset`.
- [ ] Sinh fixtures media test bằng FFmpeg lavfi trong `tmp_path`; ghi rõ đây là fixture tổng hợp. Assertion phải kiểm tra tệp đọc được, frame dimensions, codec, duration, thứ tự bằng màu/ảnh fixture, audio mapping, caption qua frame capture và SHA256; không assertion tautological kiểu so giá trị tự gán.
- [ ] Xác định và dùng `video_processor` hiện hữu; thay concat-only nếu cần. Tạo clip tạm chuẩn hóa codec, timebase, fps, resolution trước concat; xử lý still image bằng duration hữu hạn; tôn trọng trim, fit, audio và captions theo cùng timeline contract.
- [ ] Endpoint nhận `project_id` và `timeline_version_id`/version đã lưu, không nhận file paths. Kiểm tra mọi asset thuộc workspace/project. Job thất bại trả trạng thái FAILED, không tạo MediaAsset, dọn temporary files an toàn.
- [ ] Dùng FFprobe và loudness measurement trên tệp đầu ra. Tiêu chí: 1080x1920, 30 fps, H.264/AAC, caption trong safe rectangle tính đúng theo pixel 1080x1920, loudness -14 ±1 LUFS. Xác định duration tolerance bằng số frame, không dùng ước lượng byte-size.
- [ ] Chạy test mới và regression; kiểm thử hai lệnh render đồng thời, xác nhận chỉ một tiến trình FFmpeg chạy; thử cancel/timeout/restart worker và xác minh job không báo thành công sai.

**Lệnh kiểm tra:** Tại `03_ban_lam_viec/sin_content_api`, chạy `python -m pytest -q tests/test_media_studio_video.py -k timeline_render`. Kết quả mong đợi: toàn bộ test render mới PASS, exit code 0; sau đó chạy safe subset và kiểm chứng concurrency bằng log/process count.

**Gate M-P5 PASS khi:** Toàn bộ ma trận render đạt; output mở được bằng ffprobe và phát thực; duration lệch tối đa một frame ở mỗi điểm cắt; video 1080x1920/30fps; audio đo được -14 ±1 LUFS; caption không tràn Safe Zone; file gốc không đổi; concurrency quan sát được bằng log/process count = 1; mọi lỗi đều có trạng thái FAILED và không tạo asset đầu ra giả; download output qua quyền M-P2 thành công. Bằng chứng gồm log, probe JSON, loudness report, hash và ảnh chụp preview/thành phẩm.

### M-P6 — Flow Pro-Assisted và ảnh tham chiếu sang video

**Đầu ra:** Trong màn AI/Flow, người dùng chọn ảnh từ thư viện làm ảnh tham chiếu, nhập prompt video, nhận hướng dẫn mở Flow chính thức và sao chép prompt; người dùng tự nạp ảnh, tạo video, tải file xuống rồi nhập MP4 về project. Lưu provenance của video đầu ra và `parent_asset_id` trỏ ảnh tham chiếu khi phù hợp. Nếu Flow UI chính thức hiện tại không hỗ trợ chế độ/định dạng đó, hiển thị giới hạn và không báo thành công. Không điều khiển Flow tự động, không đọc cookie/profile, không tự bấm chấp thuận credits.

**Các bước:**

- [ ] Trước khi code, một người vận hành có quyền dùng tài khoản Flow xác nhận giao diện chính thức hiện hành hỗ trợ ảnh tham chiếu sang video; ghi ngày, model/mode, giới hạn file và bước thao tác, không lưu thông tin phiên.
- [ ] Nếu không xác nhận được, đánh dấu M-P6 `BLOCKED_PROVIDER_UI` và không triển khai nút hứa chức năng chưa tồn tại. Các phase editor từ asset người dùng vẫn có thể nghiệm thu riêng.
- [ ] Nếu được xác nhận, dựng UX handoff trong AI/Flow tab: chọn asset ảnh, nhập prompt, copy prompt, mở URL chính thức; nói rõ người dùng cần tự tải ảnh lên Flow và tải video kết quả về.
- [ ] Sau khi người dùng nạp MP4 vào project, liên kết ảnh cha bằng `parent_asset_id` hoặc trường provenance hiện có; nếu schema hiện tại không biểu đạt được provenance, dừng và xin duyệt contract thay vì bỏ liên kết.
- [ ] Chạy test UI với Flow giả lập không gọi web; xác minh giới hạn provider thật bằng HUMAN_VERIFIED một lần khi có tài khoản và quyền sử dụng. Lưu asset output/hash, biên bản xác nhận, không chụp nội dung tài khoản nhạy cảm.

**Kiểm thử bắt buộc:** Kiểm thử đơn vị cho tạo handoff/provenance; UI E2E kiểm tra chọn ảnh, copy prompt, mở link, nhập video tải về; kiểm tra người dùng hủy/không có phiên đăng nhập; HUMAN_VERIFIED với một lần chạy thật trên tài khoản Flow được chủ tài khoản cho phép, lưu asset và hash. Không lưu thông tin phiên.

**Gate M-P6 PASS khi:** Có một vòng đời ảnh tham chiếu -> người dùng tạo trên Flow -> video tải về -> asset nhập vào timeline và render được; provenance giữ đúng ảnh cha; flow thất bại/không hỗ trợ được báo BLOCKED/FAILED. Nếu thiếu tài khoản hoặc Flow thay đổi giao diện, ghi `BLOCKED_CREDENTIALS` hoặc `BLOCKED_PROVIDER_UI` cùng bằng chứng; không đánh dấu phase live là PASS.

### M-P7 — Regression, nghiệm thu và bàn giao AGY

**Đầu ra:** Chạy toàn bộ backend media tests, frontend typecheck/build, UI E2E, security/secret scan và kiểm tra contract. Cập nhật tài liệu hướng dẫn dùng từ ảnh/video; báo cáo các lỗi tồn đọng, giới hạn Flow/live, tương thích project cũ và đường rollback. Không thay đổi checkpoint Production nếu phase chưa qua phê duyệt tương ứng.

**Các bước:**

- [ ] Thay/đánh dấu tách biệt mọi test mặc định gọi Flow/API thật; xác nhận suite tự động không mở trình duyệt đăng nhập hoặc tạo chi phí.
- [ ] Chạy full backend test suite từ đúng thư mục và giữ exit code/log; chạy frontend `pnpm exec tsc --noEmit`, `pnpm run build`, sau đó E2E có server kiểm thử đã xác nhận.
- [ ] Chạy kiểm tra secrets, quyền workspace, đường dẫn file, MIME, file nguồn, trạng thái duyệt, log lỗi, tải output và asset hash; có checklist từng điều kiện MED-EDIT-01..06.
- [ ] Đối chiếu diff/hash của đúng các file đã khai báo phạm vi; liệt kê file ngoài kế hoạch và dừng để giải thích/duyệt trước khi đóng phase.
- [ ] Gói raw output và evidence theo nơi ghi được Owner/AGY cho phép tại M-P0; lập báo cáo PASS/BLOCKED/NOT RUN cho từng test và từng gate.
- [ ] Chỉ sau Founder/Owner duyệt mới cập nhật CURRENT_STATE/hành trình; chỉ checkpoint nếu thỏa điều kiện bảo lưu/sao lưu của project.

**Lệnh kiểm tra cuối:** Tại `03_ban_lam_viec/sin_content_api`, chạy `python -m pytest -q`; tại `03_ban_lam_viec/sin_creator_os`, chạy `pnpm exec tsc --noEmit`, `pnpm run build` và `python tests/e2e/run_ui_verification.py`. Chỉ dùng lệnh full backend suite sau khi ba test provider thật đã được cách ly khỏi collection mặc định. Mọi lệnh phải exit code 0; lệnh không chạy được báo BLOCKED kèm lý do, không quy đổi thành PASS.

**Gate M-P7 PASS khi:** Full backend/media suite đã an toàn không gọi provider thật mặc định đạt exit 0; build/typecheck và E2E đạt exit 0; review ranh giới file, tenant, secret và license không có Must Fix; evidence đầy đủ theo phase; Owner/Founder duyệt bản dựng đầu ra; AGY cập nhật `00_bat_dau/CURRENT_STATE.md` và `hanh_trinh_phat_trien_069.html` sau nghiệm thu. Chỉ tạo checkpoint/snapshot khi Founder xác nhận hoàn tất gate phát hành và quy trình sao lưu an toàn đã được kiểm tra.

## Bộ nghiệm thu tổng thể

| ID | Điều kiện nghiệm thu đầu cuối | Bằng chứng bắt buộc |
|---|---|---|
| MED-EDIT-01 | Tải ảnh và video hợp lệ vào đúng project/workspace, tải lại vẫn còn trong thư viện. | Log API, metadata, SHA256, ảnh chụp UI. |
| MED-EDIT-02 | Dựng clip gồm ảnh và video; thay đổi thứ tự, thời lượng ảnh, trim video, fit và caption được lưu/khôi phục. | Timeline version JSON trước/sau và video preview E2E. |
| MED-EDIT-03 | Render H.264/AAC 1080x1920, 30 fps; caption tiếng Việt nằm Safe Zone; LUFS -14 ±1. | FFprobe JSON, loudness report, frame capture, hash. |
| MED-EDIT-04 | Tệp nguồn không đổi; lỗi upload/render không thành công giả; tải và đọc asset tenant khác bị chặn. | Hash trước/sau, negative API tests, log FAILED. |
| MED-EDIT-05 | Asset đầu ra từ Flow ảnh tham chiếu có provenance; tạo thật qua thao tác người dùng hoặc được đánh dấu BLOCKED với nguyên nhân. | E2E handoff, asset cha/con, hash và biên bản human verification hoặc blocked evidence. |
| MED-EDIT-06 | Không có emoji, secret, dữ liệu giả hoặc trạng thái duyệt tự động trong UI, code, log và thành phẩm. | Quét repo/log, review mã và kiểm tra asset metadata. |

## Hướng dẫn bàn giao cho AGY

1. Đọc lại `00_bat_dau/CURRENT_STATE.md`, `00_bat_dau/CHECKPOINT.json`, hành trình dự án và kế hoạch Media Studio gốc; xác nhận trạng thái code hiện tại trước khi dùng plan.
2. Thực hiện M-P0, lưu bằng chứng và báo cáo sai khác với audit 2026-10-22; không bỏ qua lỗi cũ chỉ vì checkpoint mới hơn.
3. Xin Founder duyệt prototype và giá trị mặc định ở M-P1. Chỉ sau khi có duyệt mới thực hiện M-P2 trở đi.
4. Mỗi phase hoàn thành phải có review độc lập, lệnh kiểm chứng thực tế, evidence trong `08_kiem_thu/bang_chung/` và cập nhật trạng thái có căn cứ. Không gộp nhiều phase qua một báo cáo PASS.
5. Không mở rộng scope khi chưa được Founder duyệt; mọi thay đổi hợp đồng, migration, provider hoặc quyền Production cần ghi lý do, rủi ro và cổng nghiệm thu riêng.
6. Không dùng `git status` làm bằng chứng thay đổi nếu thư mục hiện hành không phải Git worktree; dùng manifest hash ở giao thức chống suy đoán.
