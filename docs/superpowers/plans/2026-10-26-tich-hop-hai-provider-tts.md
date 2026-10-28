# Tích hợp Gwen-TTS và VieNeu v3 Turbo — Kế hoạch triển khai

> Triển khai theo từng bước TDD trong phiên này. Mỗi bước xác minh trong SQLite RAM/test harness; không chạy migration lên dữ liệu dự án.

**Mục tiêu:** Bổ sung lựa chọn sinh voiceover bằng Gwen-TTS hoặc VieNeu v3 Turbo vào luồng sản xuất video, bảo đảm một provider được dùng cho mỗi run và tối đa một model TTS được nạp/chạy toàn hệ thống.

**Kiến trúc:** API nhận lựa chọn provider/voice/reference có kiểm tra và lưu bất biến trong run. Worker video hiện hữu sinh voiceover qua adapter lazy-load, giữ một model active và giải phóng trước khi chuyển model; không fallback. Audio được kiểm tra và lưu thành MediaAsset qua đường lưu trữ hiện có.

**Ngăn xếp:** FastAPI, SQLAlchemy, Pydantic, worker Python hiện hữu, Next.js/TypeScript, SDK tùy chọn `qwen-tts` và `vieneu`.

**Đặc tả:** `03_ban_lam_viec/ke_hoach_tao_video_tu_noi_dung/nghien_cuu_tich_hop_tts_vietnamese.md` mục 8; lệnh Founder `tiến hành code đi` ngày 2026-10-26.

## Ràng buộc toàn cục

- Tên mới: tiếng Việt không dấu, chữ thường, snake_case; nội dung tài liệu/UI tiếng Việt có dấu.
- Không dùng emoji hoặc unicode icon trong UI/tài liệu/log mới.
- Tối đa một model TTS được nạp và tối đa một job TTS hoạt động; provider đã chọn lỗi thì dừng run, không fallback.
- TTS chỉ chạy trong worker có lease hiện hữu; giữ idempotency, tenant/project scope và bằng chứng provenance.
- Gwen/VieNeu SDK là dependency tùy chọn; không tải checkpoint lúc khởi động ứng dụng.
- Không gọi provider hoặc tải model khi chạy unit test.

## Điểm cần rà soát

- Lặp lại cùng `idempotency_key` với provider/reference/voice khác phải trả conflict, không trả lại run cũ.
- Hai process worker cùng lúc không được nạp engine đồng thời; dựa vào lease DB duy nhất hiện hữu và test bằng harness.
- Reference audio phải cùng workspace/project, có loại âm thanh hợp lệ và chấp thuận clone; không trả transcript tham chiếu trong response.
- Audio sai codec, lỗi decode hoặc lệch quá 0,5 giây với thời lượng mục tiêu phải chặn hoàn tất, không trim lời đọc âm thầm.
- SDK thiếu/model không sẵn sàng phải trả lỗi có mã rõ; không tự đổi provider.

---

### Task 1: Hợp đồng run và lưu lựa chọn TTS

**Tệp:**
- Sửa `sin_content_api/src/modules/tao_video_noi_dung/contracts.py`.
- Sửa `sin_content_api/src/models/entities.py`.
- Sửa `sin_content_api/src/migrations/runner.py`.
- Sửa `sin_content_api/src/modules/tao_video_noi_dung/service.py`.
- Sửa `sin_content_api/tests/test_content_video_pipeline.py`.

**Các bước:**
1. Viết test đỏ cho provider hợp lệ/không hợp lệ, điều kiện Gwen cần reference + transcript + consent, và không cho vừa chọn upload voiceover vừa chọn sinh TTS.
2. Viết test đỏ cho idempotency mismatch khi provider/voice/reference khác, và response không chứa reference transcript.
3. Thêm hợp đồng `voice_source`, `tts_provider`, `tts_voice_id`, `tts_reference_asset_id`, `tts_reference_text`, `voice_clone_consent`; provider/voice config được lưu riêng trong `ContentVideoRun.tts_config_json` qua migration idempotent.
4. Bảo đảm kiểm tra reference asset thuộc cùng workspace/project; so toàn bộ trường TTS khi tái sử dụng idempotency key.
5. Chạy test target và migration harness trên DB RAM.

### Task 2: Adapter và độc quyền model

**Tệp:**
- Tạo `sin_content_api/src/modules/tao_video_noi_dung/tts_provider.py`.
- Tạo `sin_content_api/tests/test_tts_provider.py`.
- Tạo `sin_content_api/tts_requirements_gwen.txt` và `sin_content_api/tts_requirements_vieneu.txt` nếu repo chưa có quy ước extras riêng.

**Các bước:**
1. Viết test đỏ cho adapter contract với provider factory giả lập, chọn đúng provider, không fallback, và chuyển Gwen → VieNeu chỉ sau khi giải phóng model cũ.
2. Viết test đỏ xác nhận chỉ một model instance tồn tại, lock tuần tự hóa lệnh tổng hợp và SDK thiếu trả lỗi có mã.
3. Cài đặt manager một-model-active với lock; import SDK và nạp checkpoint lazy chỉ khi bắt đầu tổng hợp.
4. Dùng API công khai: Gwen `generate_voice_clone(text, ref_audio, ref_text, ...)`; VieNeu `Vieneu(mode="v3turbo").infer(text, voice=...)` hoặc `ref_audio` khi được chọn. Không sao chép source/asset từ repo Flask tham chiếu.
5. Giải phóng reference tới model cũ và CUDA cache trước khi nạp model khác; không thêm retry sang provider kia.
6. Chạy test target bằng factory giả; không tải model hoặc gọi mạng.

### Task 3: Worker sinh và ghi nhận audio

**Tệp:**
- Sửa `sin_content_api/src/modules/tao_video_noi_dung/runner.py`.
- Sửa `sin_content_api/src/modules/media_studio/service.py` nếu cần tái dùng helper lưu media.
- Sửa `sin_content_api/tests/test_content_video_pipeline.py` và `sin_content_api/tests/test_media_studio_video.py` nếu có consumer bị ảnh hưởng.

**Các bước:**
1. Viết test đỏ cho TTS sinh narration đã duyệt, lưu audio đúng project/workspace, metadata source/provider/model/version/hash và thêm audio vào `output_asset_ids_json`.
2. Viết test đỏ cho QC codec/decode/duration và lỗi provider: run không được COMPLETED và không sinh asset giả.
3. Gọi provider đã khóa trong `tts_config_json` bên trong worker/run lease; chỉ sinh một voice track cho kịch bản, dùng narration tiếng Việt theo thứ tự cảnh.
4. Lưu đầu ra WAV qua media asset path hiện hữu; chạy probe, kiểm tra codec/duration và ghi provenance. Không trim lời đọc nếu sai thời lượng.
5. Chạy test pipeline và regression target.

### Task 4: Chọn provider trong UI

**Tệp:**
- Sửa `sin_creator_os/src/lib/api/content-video-api.ts`.
- Sửa `sin_creator_os/src/app/(main)/video-studio/[projectId]/production/_components/content_video_production.tsx`.

**Các bước:**
1. Thêm UI test đỏ cho lựa chọn `Tải voiceover` / `Sinh bằng TTS`, dropdown Gwen/VieNeu, trường voice/reference đúng điều kiện và consent khi clone.
2. Thêm lựa chọn provider trong trạng thái duyệt storyboard; giữ lựa chọn qua submit idempotent run và hiển thị provider trên trạng thái run.
3. Khi provider Gwen được chọn, buộc audio tham chiếu + transcript chính xác + xác nhận quyền clone; khi VieNeu chọn preset mặc định, không yêu cầu reference.
4. Giữ nhánh tải voiceover hoàn chỉnh tương thích hiện có; không gửi cả upload và TTS trong cùng request.
5. Chạy component/UI checks, TypeScript và backend test liên quan theo lệnh dự án.

### Task 5: Rà soát tích hợp và bàn giao

**Tệp:** chỉ các file nêu trên và trạng thái/task card được cấp quyền.

**Các bước:**
1. Chạy bộ kiểm thử backend liên quan, migration trên DB RAM, TypeScript và `git diff --check`.
2. Quét dependency/secret và xác nhận không phát sinh model weight, WAV reference hoặc file runtime trong Git.
3. Rà luồng cũ upload voiceover, idempotency, tenant scope, resume/retry và TTS exclusive lock.
4. Ghi bằng chứng lệnh/output, hash, giới hạn kiểm thử; capability model thật vẫn `REAL_UNVERIFIED` nếu chưa chạy model trên phần cứng được duyệt.
5. Không chạy live inference hoặc tải checkpoint trong lượt code này nếu chưa có môi trường/voice reference được cấp quyền.
