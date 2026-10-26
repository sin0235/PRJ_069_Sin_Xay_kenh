# Nghiệm thu Voice Clone & TTS riêng

## Kết quả

- `/voice-studio` có đúng hai tab: `TTS` và `Clone giọng`.
- Tab Clone giọng lưu voice profile trong workspace, gồm provider và tham chiếu đến audio mẫu. Tab TTS chọn preset hoặc voice đã lưu; không sinh audio khi lưu profile.
- Tab TTS có điều khiển nâng cao theo provider và bảng phiên âm theo dạng `từ gốc = cách đọc`. Bảng được lưu theo workspace trên trình duyệt và áp dụng bằng thay thế từ trọn vẹn trước inference.
- Gwen-TTS hỗ trợ temperature, top-k, top-p, repetition penalty, max tokens và x-vector-only. VieNeu hỗ trợ temperature, top-k, top-p, repetition penalty, denoise/reference codes, max frames và max chars theo API model [VieNeu v3 Turbo](https://github.com/pnnbao97/VieNeu-TTS/blob/main/src/vieneu/v3turbo.py) và [Qwen3-TTS](https://huggingface.co/spaces/Qwen/Qwen3-TTS/blob/main/qwen_tts/inference/qwen3_tts_model.py).
- Profile và job được giới hạn theo workspace. Phản hồi danh sách profile không trả transcript; trạng thái job không trả nội dung đọc.
- Audio đầu ra lưu thành MediaAsset ở workspace, không gắn với project video. Worker dùng chung lease với pipeline video.

## Kiểm tra thực tế

- `python -m pytest tests/test_voice_studio.py tests/test_content_video_pipeline.py -q --tb=short`: **63 passed**.
- `python -m compileall -q src/modules/voice_studio src/modules/tao_video_noi_dung/tts_provider.py src/models/entities.py src/models/__init__.py src/migrations/runner.py`: thành công.
- `npm run build`: thành công; Next.js tạo route `/voice-studio` trong tổng số 43 route.
- `GET http://127.0.0.1:3000/voice-studio`: HTTP 200.
- OpenAPI từ mã nguồn ở chế độ test có `/v1/voice-studio/jobs`, `/v1/voice-studio/jobs/{job_id}` và `/v1/voice-studio/voices`.
- `git diff --check`: thành công.

## Giới hạn đã biết

- API dev trên cổng 8000 vẫn là tiến trình khởi động trước thay đổi nên chưa có các route mới. Cần restart API trước khi gửi job từ giao diện; tiến trình không được restart vì cấu hình môi trường riêng không có trong shell.
- Chưa tải model hoặc chạy inference thật; test worker và tham số dùng model giả lập. Chất lượng giọng và hiệu năng CPU trên máy triển khai chưa được nghiệm thu.
- Chưa có ảnh chụp màn hình nghiệm thu: Playwright thiếu Chromium headless và Edge automation không gắn được debugger.

## Bổ sung: bộ phiên âm lưu theo workspace

- Bộ phiên âm được lưu trong bảng `voice_studio_settings`, khóa theo `workspace_id`; giao diện không còn dùng `localStorage`.
- Có `GET/PUT /v1/voice-studio/settings`. API xác thực tối đa 100 dòng, từ gốc không quá 80 ký tự, cách đọc không quá 120 ký tự và từ trùng nhau không phân biệt hoa thường.
- Khi tạo TTS, backend tự dùng bộ phiên âm của workspace nếu yêu cầu không gửi `pronunciation_dictionary`. Giá trị gửi tường minh (kể cả chuỗi rỗng) được xem là ghi đè cho một lần chạy.
- `python -m pytest tests/test_voice_studio.py tests/test_content_video_pipeline.py -q --tb=short`: **64 passed**.
- `python -m compileall -q src/modules/voice_studio src/models/entities.py src/models/__init__.py src/migrations/runner.py`: thành công.
- `npm run build`: thành công; route `/voice-studio` có trong bản build.
- Sinh OpenAPI từ `src.main` ở chế độ test xác nhận `/v1/voice-studio/settings`; giao diện đang chạy trả HTTP 200. API dev cổng 8000 không phản hồi kịp khi kiểm tra OpenAPI runtime; cần khởi động lại tiến trình API để nạp route mới.
- `git diff --check`: thành công.