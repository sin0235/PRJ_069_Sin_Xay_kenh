# Nghiên cứu harness dựng và sửa video chuyên nghiệp cho BAHA

Ngày khảo sát: 23/10/2026. Phạm vi: đọc mã nguồn BAHA, báo cáo audit được cung cấp và nguồn chính thức trên web. Chưa clone, cài đặt, chạy repo bên ngoài, gọi AI, thao tác tài khoản Flow hoặc thử phần mềm dựng. Đây là kết quả nghiên cứu tài liệu và thiết kế, không phải biên bản nghiệm thu tính năng.

Tài liệu đi cùng: [đặc tả](dac_ta_harness_dung_video_baha.md), [kế hoạch kế tiếp](ke_hoach_harness_dung_video_baha_2026_10_23.md), [ma trận nghiệm thu](ma_tran_nghiem_thu_harness_dung_video_baha.md).

## 1. Yêu cầu đã nhận và quyết định thiết kế đề xuất

- Founder yêu cầu thêm một plan thực hiện sau plan Video Studio media-first; nghiên cứu sâu, chưa triển khai.
- Founder xác nhận ưu tiên: “tối ưu toàn diện khả năng edit video chuyên nghiệp”. Vì vậy phạm vi gồm dựng nhiều lớp, hậu kỳ âm thanh/màu/đồ họa, chỉnh theo phản hồi, biến thể đầu ra, bàn giao project và sửa cảnh bằng Flow.
- Lựa chọn của người soạn: BAHA giữ quyền điều phối, dữ liệu và timeline chuẩn; dùng engine/phần mềm dựng đã kiểm chứng cho năng lực chuyên sâu. Không xây lại toàn bộ phần mềm dựng chuyên nghiệp trong trình duyệt.
- Bộ công cụ cho agent phải thực thi thật, có phiên bản, kiểm tra kết quả và phục hồi. Prompt, danh sách skill hoặc MCP đơn lẻ chưa đáp ứng mục tiêu này.

## 2. Sổ đối soát mã nguồn cục bộ

Các đường dẫn dưới đây tính từ `03_ban_lam_viec/`, trừ khi ghi khác. Trạng thái `CODE_READ` chỉ xác nhận đã đọc phần mã liên quan; không đồng nghĩa kiểm thử chạy đạt.

| Mã | Quan sát tại thời điểm khảo sát | Bằng chứng | Hệ quả cho plan mới |
|---|---|---|---|
| L01 | Plan trước có M-P0..M-P7; chưa bao gồm editor nhiều lớp chuyên nghiệp và tự động hóa Flow UI | `ke_hoach_tich_hop_media_studio/ke_hoach_mo_rong_video_studio_media_first_2026_10_23.md`, mục phạm vi | Kế hoạch kế tiếp mở rộng có version; không gán tính năng tương lai cho nền tảng hiện tại |
| L02 | Download hiện có `require_action("media.read")` và lọc workspace | `sin_content_api/src/modules/media_studio/router.py::download_asset`, dòng 119 trở đi | Nhận định download không có tenant guard trong bản plan cũ đã lệch hiện trạng; kiểm tra chạy ở H00, không sửa lại một lỗi bằng suy đoán |
| L03 | Validator hiện đã có giới hạn dung lượng và allowlist category ảnh/video; vẫn có fallback MIME theo đuôi tệp | `sin_content_api/src/modules/media_studio/security.py::detect_real_mime`, `UPLOAD_SIZE_LIMITS`, `CATEGORY_MIME_ALLOWLIST` | Không mặc định validation đã hoàn chỉnh; thử nội dung hỏng/giả MIME và decoder giới hạn tài nguyên |
| L04 | `TimelineVersion` có unique `(project_id, version)` | `sin_content_api/src/models/entities.py::TimelineVersion`, dòng 764 trở đi | Tái sử dụng version hiện có; không tạo bảng timeline cạnh tranh |
| L05 | `OfflineTaskQueue` lưu jobs/snapshots trong dictionary và dùng Lock của tiến trình | `sin_content_workers/worker.py::OfflineTaskQueue`, dòng 131 trở đi | Đây chưa là bằng chứng hàng đợi bền vững qua restart hoặc khóa liên tiến trình |
| L06 | `GoogleOfficialOmniProvider.generate` gọi lại `GoogleFlowZeroCostProvider.generate`; provider đó dùng `GoogleFlowClient` và ép nguồn 16:9/10 giây | `sin_content_api/src/modules/media_studio/video_provider.py`, dòng 44..173 | Tên Official hiện chưa chứng minh gọi API chính thức; không tái sử dụng nó làm adapter API đã được xác minh |
| L07 | Một nhánh orchestrator tự đặt `approval_state="APPROVED"`; nhánh job khác tạo `UNREVIEWED` | `video_provider.py::VideoOrchestrator.generate_video_scene`; `job_engine.py::_process_flow_job` | H00 phải đối soát kết quả plan trước; harness tuyệt đối không thừa hưởng tự duyệt |
| L08 | Có metadata asset, asset cha, QC result, budget và cost ledger | `sin_content_api/src/models/entities.py::MediaAsset`, `MediaQCResult`, `WorkspaceBudget`, `CostLedger` | Tái sử dụng; chỉ bổ sung dữ liệu phiên chạy/giao dịch nếu có khoảng trống đã chứng minh |
| L09 | `LLMClient.complete` dùng HTTP OpenAI-compatible cho chuỗi thông điệp, giới hạn input và lỗi; không phải bộ xử lý video đa phương thức | `sin_content_api/src/modules/llm/client.py::LLMClient`, dòng 49 trở đi | Dùng lại chính sách log/lỗi; không giả định client đã gửi được ảnh/video/JSON schema |
| L10 | Có bộ quét injection dựa trên pattern; `assert_safe_passive_data` trả True | `sin_content_api/src/modules/understanding/prompt_injection_guard.py` | Không xem regex là ranh giới an toàn; tool broker phải tự chặn quyền, dữ liệu và side effect |
| L11 | Có hàm đo âm lượng, audio QC, chuẩn hóa và ducking | `sin_content_api/src/modules/media_studio/audio_processor.py` | Đối soát và dùng lại; kiểm tra file render cuối, không suy ra từ tên hàm |
| L12 | State/hành trình chứa các tuyên bố thành công lịch sử, trong khi checkpoint từng ghi audit bác bỏ | `00_bat_dau/CURRENT_STATE.md`, `00_bat_dau/CHECKPOINT.json`, `hanh_trinh_phat_trien_069.html` | Không dùng self-report hoặc trạng thái checkpoint đơn lẻ để mở gate kế tiếp |
| L13 | Khi kiểm tra cuối lượt, hash router/video provider đã thay đổi so với mốc đọc đầu; router hiện có GET/PUT timeline và POST render-timeline, còn nhánh Official vẫn gọi Flow provider | `router.py::get_project_timeline`, `save_project_timeline`, `render_project_timeline`; `video_provider.py::GoogleOfficialOmniProvider.generate` | Workspace đang có thay đổi đồng thời; chỉ xác nhận sự hiện diện source, chưa test route. H00 phải kiểm kê lại phiên bản thực nhận, không tạo API timeline trùng lặp hoặc xem source mới là M-P7 đã PASS |

### Dấu vân tay khảo sát

SHA256 được lấy bằng `Get-FileHash` trong phiên nghiên cứu. Đây là mốc đọc đầu để đối chiếu tài liệu, không phải snapshot triển khai. Kiểm tra cuối lượt đã phát hiện router/video provider thay đổi như L13; không xem các hash này là bản mới nhất hoặc tiếp tục đúng số dòng cũ. Trước H00 phải kiểm kê lại.

| Tệp | SHA256 |
|---|---|
| Plan media-first | `F26FC98BA7DC350F8DDB0998761EA2C1E766EBD4F8E368E50BC4746244FE1351` |
| Audit tại thư mục gốc | `2F12BD5DE27D0FAFCCE871D2BA26F9024CF1BB459E359ED4A6D8AF39D81607AA` |
| `media_studio/router.py` | `479DA441BD40B396A5970526676A0BE05BB95CACEA497D998C0F7C703D10AAB6` |
| `media_studio/security.py` | `B9B119891367EC4AEB4C96823950D342EDF1DCC083E5B214620407DDAABE4BFC` |
| `media_studio/video_provider.py` | `AE604234820B700B8F893FCFEB106A93E6EB128DC5FB30934192478FC3D76F41` |
| `sin_content_workers/worker.py` | `183163ABCA72E0F995D1A6E61A6B660FF3117EFD5D4016F4678B1890F699AB86` |
| `modules/llm/client.py` | `A28477B1FE15A460258973F26A672C3E64ECD07EC12E2881D2E3D3AEB7D07FEA` |

## 3. Flow và API: năng lực đã có tài liệu, chưa thử tài khoản BAHA

### R01. Sửa footage tải lên trong Flow

Tài liệu hiện hành cho phép sửa clip tải lên bằng Omni Flash: upload tối đa 60 giây/1 GB, clip trên 30 giây phải trim, chọn đoạn sửa tối đa 10 giây; có thể tiếp tục đến 3 lượt hội thoại. Lịch sử giữ phiên bản trước. Scenebuilder cho sắp xếp/trim/xem trước/tải chuỗi clip. Đây là căn cứ thiết kế sửa theo cảnh; chưa chứng minh khả năng sửa nguyên video dài hoặc xuất timeline BAHA. [Google Flow: sửa video](https://support.google.com/flow/answer/16935718?hl=en).

### R02. Không gom mọi model vào một năng lực “Flow”

Bảng model của Flow phân biệt first/last frame, references, video editing và extend. Omni hỗ trợ edit video đến 10 giây; extension trong bảng Omni vẫn được ghi là sắp có. Vì vậy capability phải gắn sản phẩm, model và thời điểm. [Google Flow: model và tính năng](https://support.google.com/flow/answer/16352836?hl=en).

### R03. Ảnh là một đường hậu kỳ độc lập

Flow có chỉnh ảnh, crop, thêm reference và lịch sử ảnh. Đề xuất luồng BAHA: sửa ảnh sản phẩm, duyệt ảnh, dùng ảnh đã duyệt để dựng hoặc tạo chuyển động, rồi nhập kết quả về cùng nguồn gốc. [Google Flow: tạo và sửa ảnh](https://support.google.com/flow/answer/16729550?hl=en).

### R04. Flow Agent và Tools có thể giúp chuẩn hóa thao tác của editor

Flow Agent có storyboard, sửa media, tạo biến thể, tổ chức asset, session và hướng dẫn dự án. Đây là agent nằm trong sản phẩm Google; chưa có bằng chứng là API điều khiển dành cho BAHA. [Google Flow Agent](https://support.google.com/flow/answer/17093911?hl=en).

Flow Tools cho tạo công cụ tái sử dụng bằng mô tả; chia sẻ link có thể lộ code/tên/thumbnail. Chỉ nghiên cứu recipe/tool nội bộ không chứa dữ liệu khách hàng; không xem Tools là đầu nối MCP mặc định. [Google Flow Tools](https://support.google.com/flow/answer/17104535?hl=en).

### R05. Có đường API chính thức để agent sửa video

Gemini Omni có sửa video tải lên và sửa hội thoại qua Interactions API với `previous_interaction_id`. Tài liệu giới hạn nguồn upload edit/extend đến 10 giây; không hỗ trợ sửa giọng nói, tham chiếu audio upload và một số khu vực. `store=false` không giữ được chuỗi sửa theo interaction trước. Extension API là nối cuối, không phải insert đoạn giữa. Capability API phải độc lập với capability Flow UI. [Gemini Omni](https://ai.google.dev/gemini-api/docs/omni).

### R06. Tài liệu cũ có thể dẫn agent đến model ngừng hoạt động

Trang tổng quan Google cập nhật 22/10/2026 ghi Veo 3.1 Preview trong Gemini API đã ngừng ngày 22/10/2026. Không suy ra Veo trong Flow UI cũng bị ngừng. Các tutorial Veo cũ không đủ để chốt model API. [Google: video API](https://ai.google.dev/gemini-api/docs/video).

### R07. Hiểu video không tương đương cắt chính xác từng frame

Google mô tả xử lý video và tham chiếu timestamp; sampling tĩnh mặc định 1 FPS có thể bỏ lỡ chuyển động nhanh. Đề xuất BAHA: lượt xem tổng quan, sau đó lấy đoạn/frame dày hơn quanh vùng cần edit; timecode quyết định cuối do bộ xử lý xác minh. [Gemini: hiểu video](https://ai.google.dev/gemini-api/docs/video-understanding).

### R08. ASR cần bằng chứng mức từ, không tự chế căn thời gian

Cloud STT trả word offset khi bật tính năng tương ứng; API V2 lưu ý độ chính xác offset có thể thay đổi, confidence có thể thiếu. Kiểm tra tổ hợp tiếng Việt/model/region và benchmark trước khi chọn; không coi timestamp ASR chính xác đến frame. [Cloud STT: WordInfo](https://docs.cloud.google.com/speech-to-text/docs/reference/rest/v2/projects.locations.recognizers/recognize), [ngôn ngữ/model](https://docs.cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages).

### R09. JSON hợp schema vẫn có thể sai nội dung

Google phân biệt structured output và function calling; JSON hợp lệ chưa bảo đảm giá trị đúng. Edit decision phải qua kiểm tra nguồn, quyền và giới hạn thời gian ở phía BAHA. [Google: structured output](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).

### R10. Quyền riêng tư, vùng và chi phí là đầu vào của router

Flow có giới hạn vùng cho sửa video upload; chưa đăng nhập tài khoản BAHA để xác nhận khả dụng. [Vùng hỗ trợ](https://support.google.com/flow/answer/16353544?hl=en).

Tài liệu Flow mô tả dùng dữ liệu để cải thiện khi bật thiết lập tương ứng và hướng dẫn tránh đưa thông tin bí mật. Preset khách hàng phải xác định nhà cung cấp nào được phép nhận media; không mặc định tài khoản thuê bao tương đương hợp đồng dữ liệu doanh nghiệp. [Dữ liệu Flow](https://support.google.com/flow/answer/17025472?hl=en).

Credits phụ thuộc model và tính theo từng generation, một request có thể sinh nhiều kết quả. Không dùng tên `ZeroCostProvider` làm bằng chứng không phát sinh chi phí; sổ cái phải ghi credit và API billing riêng. [Credits Flow](https://support.google.com/flow/answer/16526234?hl=en).

## 4. Chọn engine và phần mềm dựng

### R11. FableCut: ứng viên PoC lõi thao tác

Giấy phép gốc là MIT. [Giấy phép](https://github.com/ronak-create/FableCut/blob/main/LICENSE).

Mã MCP hiện được web hiển thị có `baseRevision` tùy chọn và `force` có thể vượt khóa. BAHA cần bắt buộc revision và loại quyền force khỏi agent. Phân tích reference mặc định có thể trích nhạc; BAHA phải mặc định không nhập âm thanh từ reference nếu chưa có quyền. [Mã MCP](https://github.com/ronak-create/FableCut/blob/main/mcp-server.js).

Release v1.12.0 công bố patch từ chối revision cũ. [Release](https://github.com/ronak-create/FableCut/releases). Chưa chạy build/render/tenant test. Bản raw mà web trả về có độ dài và nội dung khác bản blob cùng nhánh; không kết hợp chúng thành một commit đã xác minh.

### R12. OpenChatCut: ứng viên tham khảo vòng làm việc agent

README mô tả draft edit session, review, áp dụng nguyên tử và undo; công cụ generation/export không nằm trong draft có thể từ chối. Đây là ý tưởng phù hợp cho BAHA, nhưng chưa kiểm chứng chạy. [README](https://github.com/0xsline/OpenChatCut).

`package.json` công bố AGPL-3.0-or-later, Node 24 và script sync MediaPipe/whisper-cli. Chưa chọn tái sử dụng mã; phải đối soát giấy phép của phần định dùng và chặn đường AI local. [Package](https://github.com/0xsline/OpenChatCut/blob/main/package.json). Hai đường source `external-edit-session-core.ts` và `approval-policy.ts` không tải được trong nghiên cứu này; không báo đã đọc chúng. Dùng source link trong audit tại commit ghim làm danh sách cần PoC.

### R13. Phát hiện mới: ưu tiên khảo sát kết nối chính thức của Resolve

Blackmagic công bố Resolve 21.1 có tích hợp AI assistant, hỗ trợ các việc như quản lý media và batch render. Không suy ra mọi thao tác Color/Fusion đều được assistant thực thi. [Thông cáo Blackmagic](https://www.blackmagicdesign.com/media/partial/release/20260908-03).

Support Center nêu tích hợp AI assistant trong Studio 21.1 và điều kiện license. H02 phải kiểm kê phần mềm BAHA đang dùng, edition, máy và công cụ thật; chưa mua/cài/đổi NLE theo nghiên cứu này. [Blackmagic Support](https://www.blackmagicdesign.com/support).

Audit trước khảo sát `samuelgursky/davinci-resolve-mcp`; nguồn cộng đồng khác được đọc bổ sung là `superhaynes/davinci-mcp`. Không trộn hai repo thành một kết quả. Repo cộng đồng chỉ làm phương án dự phòng sau kết nối chính thức, còn phụ thuộc Resolve đang chạy và bridge tương thích. [Tài liệu cài repo bổ sung](https://github.com/superhaynes/davinci-mcp/blob/main/docs/install.md).

### R14. OTIO dùng để trao đổi dựng, không thay renderer

OTIO lưu thông tin cắt và tham chiếu media, không đóng gói media mặc định. Các adapter định dạng nằm ở package/repo riêng; mức hỗ trợ khác nhau. Chỉ thêm OTIO nếu PoC bàn giao chứng minh cần thiết, không hứa giữ nguyên mọi effect/grade khi đổi NLE. [OTIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/main/README.md), [adapters](https://github.com/AcademySoftwareFoundation/OpenTimelineIO/blob/main/docs/tutorials/adapters.md).

### R15. QA có phần đo tất định và phần đánh giá nghề dựng

FFmpeg có loudnorm, sidechaincompress, blackdetect và silencedetect. Các phép đo này không chứng minh ý nghĩa câu chuyện hoặc chất lượng thẩm mỹ; black/silence phải đối chiếu chủ ý của timeline. [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html).

### R16. Harness cần tiếp quản được và chấm kết quả thật

Nghiên cứu harness dài hạn của Anthropic nhấn mạnh artifact trạng thái và tiến độ theo từng bước. BAHA áp dụng cho phiên dựng có thể tiếp tục, không áp dụng thành cam kết năng lực video. [Harness dài hạn](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).

Tài liệu eval phân biệt lời agent nói với trạng thái môi trường sau thực thi. Đề xuất BAHA dùng timeline đã lưu, file render và đánh giá editor độc lập làm kết quả. [Eval cho agent](https://www.anthropic.com/research/demystifying-evals-for-ai-agents).

### R17. API sửa ảnh phải chọn riêng với API sửa video

Hướng dẫn ảnh của Google mô tả text + image để chỉnh ảnh và sửa nhiều lượt; không phải mọi model ảnh đều tối ưu cho nhiều reference hoặc hội thoại. H02 chọn model ảnh và kiểm chứng output image riêng, model video riêng; không gửi request chỉnh ảnh vào adapter chỉ trả video. Không ghim model từ tên marketing hoặc tutorial cũ. [Google: image generation và editing](https://ai.google.dev/gemini-api/docs/image-generation).

### R18. Hỗ trợ tiếng Việt không bảo đảm mọi tính năng ASR

Tài liệu Chirp 3 liệt kê tiếng Việt cho transcription, nhưng danh sách diarization riêng không liệt kê tiếng Việt tại bản được đọc. H05 không suy ra speaker labels/word offsets từ nhãn multilingual. Nếu speaker labels cần cho multicam, dùng đường hosted được benchmark hoặc nhãn editor đã duyệt, tách khỏi kết luận nhận dạng câu chữ. [Cloud STT: Chirp 3 và phạm vi tính năng](https://docs.cloud.google.com/speech-to-text/v2/docs/chirp-model).

## 5. Quyết định với các repo trong audit

| Ứng viên | Việc làm ở H02 | Điều kiện trước khi đưa vào sản phẩm |
|---|---|---|
| FableCut | So với renderer BAHA sau M-P7 trên cùng fixture; đo thao tác, preview/export parity, revision và tài nguyên | Commit/lockfile/license ghim; CPU render đạt; qua BAHA tool broker; không public server local |
| OpenChatCut | Học draft/review/QA; thử engine nếu giấy phép và tài nguyên phù hợp | Quyết định license bằng văn bản, hosted AI, kiểm tra isolation, không kéo local model |
| Resolve chính thức | Khảo sát kết nối AI assistant/scripting của phiên bản BAHA thực có; thử edit/readback/render | License/máy/quyền được xác nhận; tool allowlist và native project mở lại được |
| Resolve MCP cộng đồng trong audit | Chỉ thử nếu kết nối chính thức không đáp ứng | Ghim đúng repo và commit, không giả định 100% API coverage |
| Concat | Giữ làm tham khảo; chưa dùng renderer chính | Cần CPU compositor có chứng cứ và license phù hợp |
| MakeMyClip/editor | Tham khảo cách thao tác nhỏ | Không xem compiler hạn chế track là lõi dựng chuyên nghiệp |
| Gutsken/Autoclip, chadbar/autoclip, vidcut, OpenMontage | Đọc ý tưởng có chọn lọc | Chưa nhận nguyên repo vì audit ghi phụ thuộc inference local |
| chikeyy/auto-clipper | Dùng lỗi false-success trong audit làm ca kiểm tra thiết kế | Không chọn làm NLE hoặc nền tảng QA |

Các nhận định ở nhóm cuối kế thừa báo cáo audit, chưa được khảo sát độc lập toàn bộ source trong lượt này. Audit ghi smoke FFmpeg riêng, repo clone/test/API/NLE chưa chạy. Các script/manifest mà audit nói đính kèm không xuất hiện trong kết quả `rg --files -g 'BAHA_*'` tại workspace này; H02 phải tìm/xác thực trước khi sử dụng, không ghi đã có script sẵn.

## 6. Kiến trúc được đề xuất và phương án đã cân nhắc

| Phương án | Khả năng tối ưu công việc | Hạn chế | Kết luận thiết kế |
|---|---|---|---|
| Mở rộng BAHA thành toàn bộ NLE riêng | Chủ động giao diện | Chi phí phát triển màu/VFX/conform lớn, kéo dài trước khi editor dùng được | Không chọn làm hướng mặc định |
| Nhập nguyên một repo editor/agent | Nhanh để demo | Hai timeline, tenant/license/runtime khác, dễ chỉ có demo chạy đơn máy | Chỉ PoC, chưa chọn tích hợp |
| BAHA điều phối + timeline chuẩn + engine đã đo + NLE chuyên sâu + Flow/API sửa cảnh | Tận dụng nền tảng và công cụ editor, agent thao tác có kiểm soát | Phải có hợp đồng chuyển đổi và nghiệm thu roundtrip | Phương án đề xuất |

Không cần swarm nhiều agent để có harness mạnh. Khởi đầu một agent điều phối, một tool broker, phiên bản bất biến và bộ kiểm định độc lập. Vai trò lập dựng/kiểm định có thể chạy tuần tự; chỉ tăng số agent khi benchmark chứng minh lợi ích và vẫn chỉ một bên ghi timeline tại một thời điểm.

## 7. Điều chưa biết và phase phải giải quyết

| Chưa biết | Quyết định tại |
|---|---|
| NLE chính, edition/license, cấu hình máy editor và loại job BAHA | H00, H02 |
| Định mức chi phí mỗi project, quyền đưa footage khách hàng ra cloud | H00, H01 |
| API/model thực sự truy cập được, Flow UI của tài khoản thực | H02 và H08 live |
| Engine đạt parity khi mask/keyframe/color/retime và mở lại | H02, H06, H09 |
| Chất lượng ASR tiếng Việt, sampling cho cảnh nhanh | H05 |
| Mức giảm thời gian editor và chi phí sau nhiều lượt sửa | H12 |

Kết luận nghiên cứu: đủ căn cứ để viết plan harness kế tiếp có điều kiện; chưa có căn cứ chọn engine thắng cuộc hoặc tuyên bố BAHA đã có agent dựng chuyên nghiệp.
