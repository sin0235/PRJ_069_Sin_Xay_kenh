# Báo cáo rà soát đường gọi Google Flow trong G0

Ngày rà soát: 23/10/2026
Phạm vi: đọc source working tree tại `03_ban_lam_viec/sin_content_api` và `03_ban_lam_viec/cong_cu_tu_dong/flow_bridge`; không chạy API, Flow, pytest, không đọc DB/WAL/secret và không sửa source.

## Kết luận

Có một đường API công khai đang tạo video Flow trực tiếp từ prompt người dùng: `POST /v1/media/video/generate`. Nó được bảo vệ bằng bearer token, workspace header và quyền `media.upload`; nếu có `project_id`, route kiểm tra dự án thuộc workspace, và nếu có ảnh đầu vào thì kiểm tra asset thuộc workspace, đúng loại ảnh, đúng project khi asset đã gắn project. Các kiểm tra này bảo vệ tenant/project ở mức hiện có, nhưng route không yêu cầu project bắt buộc.

Sau các kiểm tra đó, route gọi thẳng `VideoOrchestrator`, provider biên dịch prompt bằng compiler cục bộ rồi gọi `GoogleFlowClient.create_video()`. Không thấy Harness, LLM, style binding đã duyệt, approval theo revision hay receipt server-side làm gate trước side effect Flow. Đây là bypass trực tiếp so với hợp đồng G0/G1 mới.

Có một nhánh job engine nội bộ cũng gọi `video_orchestrator.flow_provider.generate()` trực tiếp, nhưng provider `GOOGLE_FLOW` hiện không nằm trong Literal của schema request `AIGenerationJobCreate`, nên nhánh video này chưa gọi được qua router công khai với schema hiện tại. Cần tính đây là đường bypass tiềm tàng nếu enum được mở rộng hoặc service được gọi nội bộ.

## Bản đồ đường chạy thực tế

1. **AI Studio -> API video trực tiếp -> Flow**
   - Frontend gọi `mediaStudioApi.generateVideo()` và gửi nguyên `prompt`, `project_id` tùy chọn, cùng `start_image_asset_id` nếu có: `sin_creator_os/src/lib/api/media-studio-api.ts:391-407`.
   - Trang AI Studio gọi hàm này từ nút tạo video: `sin_creator_os/src/app/(main)/ai-studio/page.tsx:290-303`.
   - Router được đăng ký trực tiếp trong ứng dụng: `sin_content_api/src/main.py:142-146`; prefix route là `/v1/media`: `sin_content_api/src/modules/media_studio/router.py:57`.
   - Entry point nhận prompt là `POST /v1/media/video/generate`: `sin_content_api/src/modules/media_studio/router.py:868-922`.
   - Route gọi `video_orchestrator.generate_video_scene(...)`: `router.py:902-916`.
   - Nếu không có ảnh, `VideoOrchestrator` gọi Flow provider; nhánh `use_official_omni=True` cũng chỉ ủy quyền lại cho Flow provider: `sin_content_api/src/modules/media_studio/video_provider.py:182-200, 212-234`.
   - Provider dựng prompt bằng `video_prompt_compiler.compile(...)`, sau đó tạo `GoogleFlowClient` mới và gọi `create_video(...)`: `video_provider.py:47-118`.
   - Với ảnh đầu vào, `generate_from_image()` cũng biên dịch prompt rồi tạo client mới và gọi cùng `create_video(..., start_image_path=...)`: `video_provider.py:127-180`.
   - Client mở giao diện Google Flow, điền prompt, bấm tạo, có thể tự chọn xác nhận credit, rồi đợi và tải video: `cong_cu_tu_dong/flow_bridge/google_flow_client.py:49-66, 169-240, 245-291`. Nhánh ảnh chọn chế độ Video và tải ảnh vào frame đầu: `google_flow_client.py:337-413`.

2. **AI Jobs -> nhánh Flow video trong service (hiện chưa mở qua schema công khai)**
   - Router `POST /v1/ai-jobs` nhận request có auth `ai_job.create`, rồi truyền payload trực tiếp cho `job_engine.submit_job()`: `sin_content_api/src/modules/media_studio/router.py:57-58, 217-235`.
   - Request schema cho phép `asset_type="VIDEO"` nhưng provider chỉ nhận `GOOGLE_OFFICIAL`, `FLOW_MUSIC_ASSISTED`, `FAKE_PROVIDER`; không có `GOOGLE_FLOW` hay `GOOGLE_FLOW_ASSISTED`: `sin_content_api/src/schemas/contracts.py:813-820`.
   - Dù vậy, engine vẫn có feature flag và session-revoked gates cho các provider Flow: `sin_content_api/src/modules/media_studio/job_engine.py:92-160`; trong `_process_flow_job()` có nhánh gọi thẳng `video_orchestrator.flow_provider.generate(...)`: `job_engine.py:283-304`.
   - `submit_job()` lấy `workspace_id` từ tenant nhưng không truy vấn xác nhận `payload.project_id` thuộc workspace trước khi ghi job/asset; hiện nhánh Flow video không thể được chọn qua schema HTTP, nhưng thiếu kiểm tra project sẽ thành rủi ro nếu mở provider hoặc gọi service từ nơi khác: `router.py:217-235`, `job_engine.py:92-160, 252-275, 283-318`.

3. **Điều phối sửa cảnh / Assisted UI**
   - API có router theo project `/v1/media/projects/{project_id}/dung`: `sin_content_api/src/modules/dieu_phoi_dung/bo_dinh_tuyen.py:29`.
   - `POST .../don-sua-canh` kiểm tra project trong workspace và `don.project_id` khớp đường dẫn, rồi tạo/lưu ticket: `bo_dinh_tuyen.py:230-255`; kiểm tra quyền dự án nằm ở `bo_dinh_tuyen.py:54-68`.
   - `QuanLySuaCanh` chọn trạng thái/tạo receipt dạng token cho `ASSISTED_UI`; nhánh `API_DIRECT` chỉ dò cấu hình khóa. Không có call `GoogleFlowClient` hay provider thực thi tại đây: `sin_content_api/src/modules/dieu_phoi_dung/sua_bang_flow.py:15-95`.
   - Callback `POST .../don-sua-canh/{request_id}/ket-qua` nhập asset đã có và kiểm workspace/project/thời lượng/hash nếu có DB session: `bo_dinh_tuyen.py:257-278`, `sua_bang_flow.py:100-178`. Vì vậy đây là quy trình giao người vận hành sửa trên UI Flow, không phải API tự tạo/sửa Flow.
   - Các route draft/command/commit thao tác timeline trong harness nhưng không gọi Flow trực tiếp: `bo_dinh_tuyen.py:150-228`. Capability hiện khai báo `supports_extend=False`: `sua_bang_flow.py:15-24`.

4. **Entry points liên quan nhưng không gọi Flow tạo video**
   - `POST /v1/media/video/prompt/compile` chỉ chạy compiler và yêu cầu `media.upload`; không gọi LLM/provider: `router.py:852-865`.
   - `/v1/media/video/expand`, `/video/remove-watermark`, `/video/assemble`, timeline save/render là xử lý hậu kỳ/local trên asset đã có, không gọi `GoogleFlowClient`: `router.py:676-848, 926-1008, 1070-1332`.
   - `/v1/media/flow/login` chỉ mở Edge đăng nhập; giới hạn workspace owner, không tạo video: `router.py:78-96`.

## Kiểm tra auth và ranh giới project/workspace

- `get_current_tenant_context` đòi `Authorization: Bearer ...` và `X-Workspace-Id`, xác minh token/actor thuộc workspace đó: `sin_content_api/src/auth/tenancy.py:97-162`.
- `require_action("media.upload")` dùng dependency tenant/RBAC trên `/video/generate` và route compile: `sin_content_api/src/modules/media_studio/router.py:852-880`; AI Jobs dùng `ai_job.create`: `router.py:217-224`.
- `/video/generate` xác minh `project_id` thuộc workspace nếu được truyền (`router.py:882-889`); ảnh đầu vào phải thuộc workspace, là ảnh và không gắn sang project khác (`router.py:891-900`). `project_id` vẫn tùy chọn, nên route cho phép tạo asset ngoài project.
- Auth/tenant kiểm soát ai có thể gọi API, nhưng không thay thế các gate nội dung/style/approval. `GoogleFlowClient.create_video()` cũng là client nội bộ thuần, không tự xác thực người dùng hoặc workspace; nó nhận prompt và workspace từ caller.

## Global Flow client và điểm bypass

- `flow_bridge/__init__.py` tạo và export một instance global `google_flow_client = GoogleFlowClient()` cùng class: `cong_cu_tu_dong/flow_bridge/__init__.py:9-18`.
- Đường gọi sản xuất từ `video_provider.py` không dùng global instance này; nó import class và tạo client mới mỗi lần ở cả text-to-video lẫn image-to-video: `video_provider.py:78-80, 140-142`. Do đó global hiện là entry point có thể dùng bởi importer khác, không phải wrapper gate trên đường router chính.
- `git status` tại repo `03_ban_lam_viec` cho thấy `cong_cu_tu_dong/flow_bridge/google_flow_client.py` đang modified. Báo cáo này dựa trên working tree hiện tại; không đọc diff và không sửa file đó theo yêu cầu.

## Gate đang có và gate còn thiếu

- **Đang có trên route chính:** bearer + workspace identity, RBAC `media.upload`, project/workspace lookup nếu có project, workspace/project/type check cho ảnh; compile prompt cục bộ; kiểm tra phiên đăng nhập Flow khi thao tác browser; asset trả về ở trạng thái `UNREVIEWED`.
- **Chỉ có ở nhánh AI Jobs nội bộ:** `FLOW_PILOT_ENABLED` (mặc định true), `FLOW_SESSION_REVOKED` (mặc định false), idempotency theo job; không được áp dụng cho route `/video/generate` trực tiếp.
- **Chưa có trước side effect ở route `/video/generate`:** bắt buộc project/run nguồn content, Harness session/revision, LLM plan và validation, channel style binding được duyệt + snapshot/hash, approval revision, receipt thực thi server-side, idempotency chống submit trùng, kiểm soát retry/reconciliation ở cấp Flow job. Route hiện dùng `video_prompt_compiler` là compiler tĩnh, không phải LLM gate.
- **Kế hoạch xác nhận đây là yêu cầu chưa triển khai:** hợp đồng nêu rõ đây là yêu cầu thi công chứ chưa phải cơ chế chạy (`hop_dong_harness_llm_truoc_flow.md:1-3`); luồng chuẩn là Harness -> LLM -> validation -> approval -> receipt -> worker/Flow (`hop_dong_harness_llm_truoc_flow.md:5-22`). Checklist G0 yêu cầu map cả AI Studio, clip API, I2V, extend, sửa cảnh và Assisted UI; hiện G0 tổng thể còn thiếu kiểm kê runtime/DB/backup và evidence (`ke_hoach_trien_khai_va_checklist.md:78-92`). G1 vẫn chờ prototype/style/storyboard và Founder duyệt (`ke_hoach_trien_khai_va_checklist.md:94-107`).

## Trạng thái và giới hạn của lần rà soát

Báo cáo này hoàn tất phần inventory source/API/provider/Flow bridge của G0 trong phạm vi được giao; không kết luận G0 toàn dự án đã pass. Không kiểm tra DB runtime, project/asset record thực tế, process đang chạy, backup/restore, không gọi Flow và không chạy test. Checkpoint vẫn CP22 theo `00_bat_dau/CHECKPOINT.json`; trạng thái hành trình ghi G0/G1 và hợp đồng code phải được xác minh/duyệt trước khi phát lease runtime.

