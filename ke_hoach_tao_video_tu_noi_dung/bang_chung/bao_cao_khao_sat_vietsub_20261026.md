# Báo cáo khảo sát chỉ đọc Pha 0: Vietsub tự động

**Ngày:** 26/10/2026  
**Phạm vi:** Khảo sát luồng hiện có và blocker để chuẩn bị Vietsub tiếng Việt tự động trong `CONTENT_VIDEO_RENDER`.  
**Điều phối:** Codex. **Lượt phản biện:** Antigravity CLI 1.4.7, `gemini-3.8-flash-high`, effort `high`.

## Ranh giới và cách khảo sát

Đây là rà soát chỉ đọc. Không sửa mã nguồn, không đọc/ghi cơ sở dữ liệu, không chạy test hoặc compile, không gọi ASR/TTS/Flow/provider, không tải model/font và không render video. Kết luận về FFmpeg chỉ dựa trên mã renderer; binary cài trên máy chưa được xác minh.

## Git và điểm xuất phát

- Repo: `03_ban_lam_viec`; nhánh `main`; HEAD `dd8584173f8f6de15580ea6dcc217a8080531c70`.
- Có một tệp tracked đang sửa: `ke_hoach_tao_video_tu_noi_dung/nghien_cuu_hien_trang_va_phuong_an.md`. Diff thêm mục khảo sát VieNeu-TTS; giữ nguyên và xác định owner trước khi giao bất kỳ task nào chạm tệp.
- Các mục untracked gồm `bao_cao_khao_sat_sales_prj058/`, hai báo cáo/xem trước E2E, kế hoạch Vietsub này, nghiên cứu TTS, hai log Flow và `tham_chieu_vietnamese_tts_studio/`. Không xóa, clean, checkout hoặc ghi đè các mục này.
- Commit và status phải được kiểm tra lại ngay trước mỗi lease; ảnh chụp này không phải baseline bất biến.

## Luồng tạo video và căn cứ Vietsub

| Bước | Điểm nối hiện hữu |
|---|---|
| Tạo kế hoạch | `content_video_production.tsx:createPlan` → `content-video-api.ts:contentVideoApi.createPlan` → `tao_video_noi_dung/router.py:create_content_video_plan` → `service.py:create_plan` → `planner.py:generate_storyboard`. Kịch bản có `Storyboard.narration` và `shots[].narration`. |
| Nạp lời đọc | `content_video_production.tsx:uploadVoice` dùng `mediaStudioApi.uploadAsset`; `startRun` gửi `voiceAssetId` tới `create_content_video_run`. `voice_asset_id` là tùy chọn. |
| Chạy phân cảnh | `runner.py:ContentVideoWorker._loop` → `_claim_next_run` → `process_run`; `cong_harness.py:dispatch_shot` gọi `video_orchestrator.generate_video_scene` với `include_audio=False`. Flow chỉ tạo hình im lặng. |
| Render | `runner.py:_render_and_qc` gọi `_voice_input`, kiểm hash/thời lượng audio, tạo `TimelineDocument(width, height, fps, clips, voice_track)` rồi gọi `VideoProcessor.render_timeline_document`. Timeline hiện không truyền `captions`; `runner.py` ghi `speech_alignment: NOT_MEASURED`. |
| QC và xuất | `_render_and_qc` chạy đánh giá video/audio rồi `_write_export_package` tạo MP4 và ZIP. Không có bước nhận dạng hoặc căn lời trước render. |

Nguồn căn Vietsub tự động phải là audio thực tế trong `voice_track`, tương ứng với `run.voice_asset_id`. Không thể suy ra timing đáng tin từ `Storyboard.narration` khi không có audio. Đề xuất khi thiếu voice asset: trả `NO_AUDIO_FOR_VIETSUB`, không tạo phụ đề tự động; đường nhập caption thủ công của Media Studio vẫn hoạt động.

## Hợp đồng timeline và tương thích

`sin_content_api/src/schemas/contracts.py` có hai khối khai báo cùng tên cho năm model: `TimelineClip`, `TimelineAudioTrack`, `TimelineCaption`, `TimelineDocument`, `TimelineVersionOut` (khối đầu khoảng dòng 890-963, khối sau khoảng dòng 1062-1114). Khai báo Python phía sau che khuất tên khai báo trước khi module được import.

Khối sau đang được consumer hiện tại dùng:

- `runner.py:_render_and_qc` tạo `TimelineDocument` bằng `width` và `height`.
- `video_processor.py:render_timeline_document` đọc `timeline.width`, `timeline.height` và caption theo `start_ms`, `duration_ms`, `font_size`.
- `sin_creator_os/src/lib/api/media-studio-api.ts` định nghĩa cùng dạng `TimelineCaption` và `TimelineDocument`.
- `sin_creator_os/src/app/(main)/video-studio/[projectId]/page.tsx` có luồng caption thủ công; `media_studio/router.py` nhận/lưu tài liệu timeline.

Vì vậy `start_ms` + `duration_ms` là ứng viên tương thích cho cue Vietsub; không lưu thêm `end_ms` suy ra nếu chưa chứng minh cần thiết. Trước khi chuẩn hóa schema phải rà dữ liệu timeline cũ và tất cả consumer. Không dọn các model trùng ngoài phạm vi nếu chưa có lease riêng và kiểm tra tương thích.

`tao_video_noi_dung/contracts.py:StyleSnapshot` có `extra="forbid"`. `style_snapshot_sha256` tham gia biên nhận shot và được kiểm tra khi worker thực thi. Không mở rộng trực tiếp snapshot cấp cao trong phạm vi Vietsub. Nếu cần lưu style caption, dùng cấu trúc riêng có version/hash riêng, gắn với run mới mà không làm mất hiệu lực biên nhận đã duyệt.

## Renderer, font và giới hạn hiện tại

`media_studio/video_processor.py:VideoProcessor.render_timeline_document` hiện:

- Dùng Arial với đường dẫn hệ thống cố định; nếu không tìm thấy thì bỏ `fontfile` để FFmpeg tự chọn font.
- Ghi caption ra tệp tạm UTF-8, dùng `drawtext=textfile`; bật hiển thị theo `start_ms` và `duration_ms`.
- Cố định chữ vàng, hộp nền đen bán trong suốt và căn giữa. Video dọc neo caption tại `y=h-480`.
- Có `threading.Lock()` cục bộ; nó không khóa render giữa nhiều tiến trình.

Mã cho thấy renderer dự kiến hỗ trợ UTF-8, nhưng glyph dấu tiếng Việt, `drawtext`, `libfreetype`/`libharfbuzz`, BOM/CRLF và hành vi font fallback chưa được xác minh trên binary FFmpeg thực tế. Cần kiểm tra sau khi có lease runtime. Quy tắc concurrency toàn máy phải dựa trên lease/khóa liên tiến trình đã kiểm chứng, không dựa riêng vào `threading.Lock()`.

## ASR và quyền dữ liệu

`understanding/asr_evaluator.py:AsrEvaluator` tính WER/độ chính xác thuật ngữ từ các transcript đã có; đây không phải engine nhận dạng. Khi chưa có audio tiếng Việt được cấp phép và transcript đối chứng, trạng thái phải là `UNVERIFIED`. Không chạy benchmark nếu chưa xác nhận quyền dùng audio, phạm vi xử lý, chi phí/tài nguyên và tiêu chí nghiệm thu.

Thư mục `tham_chieu_vietnamese_tts_studio/` là bản tham khảo untracked; mã VibeVoice-ASR nằm trong ứng dụng Flask riêng và bật `trust_remote_code=True`. Cần rà soát riêng giấy phép repo/model, revision, dependency, bảo mật và mức hỗ trợ tiếng Việt. Chưa xác minh ASR nào đạt chất lượng tiếng Việt trong pipeline này; không tự chuyển sang provider trả phí.

## Blocker, owner và đầu ra kế tiếp

| Blocker | Owner | Đầu ra hoặc cổng cần qua |
|---|---|---|
| Trạng thái Git thay đổi; có file tracked và untracked cần bảo toàn | AGY | Chụp lại status/hash trước lease, xác định owner file; không dọn các mục có sẵn. |
| Năm model Timeline trùng tên và dữ liệu lịch sử chưa đối soát | AGY khảo sát; Integrator sở hữu thay đổi shared | Bản đồ consumer và đề xuất hợp đồng có tương thích; chưa sửa schema trong Pha 0. |
| Snapshot style gắn với approval receipt | AGY/Integrator | Thiết kế cấu trúc caption tách biệt và hash riêng; giữ nguyên snapshot/receipt cũ. |
| Voice asset có thể không tồn tại | AGY | Chốt trạng thái `NO_AUDIO_FOR_VIETSUB`; không căn timing theo script thuần. |
| ASR chưa xác minh và thiếu corpus có quyền | Founder/đầu mối dữ liệu, AGY điều phối | Duyệt quyền dữ liệu, phương án model, ngân sách và rubric trước benchmark. |
| Font/style chưa được chọn; binary FFmpeg chưa xác minh | Founder duyệt, AGY chuẩn bị mẫu; runtime kiểm sau lease | Duyệt style board/font; sau đó mới kiểm hash font và binary trong môi trường được cấp. |
| Khóa render chỉ trong một process | AGY khảo sát, Integrator thiết kế lease | Chứng minh lease hiện hữu bao phủ mọi worker/process hoặc đề xuất khóa toàn máy trước render. |
| G1 chưa được Founder duyệt | Founder | Ghi nhận duyệt prototype/storyboard/style; chưa chuyển sang lease runtime trước đó. |

## Quyết định chưa được ngầm coi là đã duyệt

Founder cần quyết định riêng về nghiệm thu G1; font và quyền nhúng; lựa chọn style Vietsub; phương án ASR/forced alignment, quyền sử dụng corpus và ngân sách; ngưỡng benchmark. Việc duyệt tài liệu kế hoạch không đồng nghĩa với các phê duyệt này hoặc với lease sửa runtime.

## Kết luận Pha 0

Pha 0 đã xác nhận điểm nối, trạng thái Git, hợp đồng đang hoạt động và các blocker trên cơ sở tài liệu/mã nguồn đọc được. Chưa chạy test, DB, model, benchmark, FFmpeg hoặc render; chưa cập nhật checkpoint. Bước tiếp theo theo kế hoạch là AGY hoàn tất nghiên cứu ASR chỉ đọc và chuẩn bị style board để Founder xem xét. Chỉ benchmark khi quyền dữ liệu được duyệt; chỉ triển khai runtime sau khi các cổng Founder và lease theo file hoàn tất.
