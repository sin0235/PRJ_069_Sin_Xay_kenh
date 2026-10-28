# Kế hoạch tích hợp Vietsub tự động vào luồng dựng video

> Dành cho Antigravity: điều phối nghiên cứu, khóa quyết định thiết kế và nghiệm thu. Codex chỉ nhận lease triển khai sau khi các cổng duyệt trong tài liệu này hoàn tất.

**Mục tiêu:** Tạo Vietsub tiếng Việt theo lời đọc thực tế, căn thời gian với audio cuối, dùng font và style đã duyệt theo kênh, có thể xem lại, sửa và xuất cùng video.

**Kiến trúc:** Sinh transcript và mốc thời gian từ track giọng đọc trước khi trộn nhạc; kiểm nội dung so với narration đã duyệt; chuyển các đoạn hợp lệ thành cue trên timeline; khắc chữ bằng renderer hiện có; lưu transcript, style snapshot và dấu vết provider trong gói xuất. Vietsub được tạo ở lớp dựng sau khi sinh video, không giao việc hiển thị chữ cho model tạo hình.

**Công nghệ:** FastAPI/Pydantic, timeline và renderer FFmpeg hiện có, một adapter ASR hoặc căn lời được xác minh, font TTF/OTF có quyền nhúng và hỗ trợ tiếng Việt. Ưu tiên giữ mô hình suy luận ASR trong tiến trình/môi trường riêng nếu dependency xung đột với ứng dụng chính.

**Tài liệu chuẩn:** `quy_chuan_phong_cach_kenh.md`, `hop_dong_harness_llm_truoc_flow.md`, `quy_uoc_thi_cong_song_song.md`, `nghien_cuu_tich_hop_tts_vietnamese.md`.

## Cổng phê duyệt

Hiện trạng dự án vẫn chờ Founder duyệt prototype và hồ sơ phong cách G1; chưa cấp lease runtime theo `COMMAND_CONTROL_CARD.md`. Tài liệu này chỉ giao Antigravity làm phần khảo sát, đề xuất, mẫu duyệt và chuẩn bị hợp đồng. Không sửa runtime, không chạy model, không tải thêm font, không gọi Flow/TTS/ASR thật và không phát hành production trước khi Founder duyệt style Vietsub, phương án ASR, tiêu chí nghiệm thu và cấp lease cụ thể.

## Kết quả phản biện độc lập cho kế hoạch AGY

Lượt rà soát chỉ đọc ngày 26/10/2026 được điều phối qua Antigravity CLI 1.4.7, model `gemini-3.8-flash-high`, effort `high`. Gemini xác nhận kế hoạch đủ để AGY tiếp tục khảo sát và hoàn thiện hồ sơ, nhưng chưa đủ điều kiện giao Codex sửa runtime. Các điểm dưới đây đã được đối chiếu với repo và quy ước dự án:

- Lượt phản biện kế hoạch đầu tiên ghi nhận repo `03_ban_lam_viec` ở commit `dd85841`, chưa có file tracked sửa đổi và có các mục untracked. Pha 0 sau khi Founder duyệt kế hoạch kiểm tra lại cùng HEAD nhưng thấy `M ke_hoach_tao_video_tu_noi_dung/nghien_cuu_hien_trang_va_phuong_an.md`, là phần bổ sung nghiên cứu VieNeu-TTS; các mục untracked vẫn cần giữ nguyên. Đây chỉ là ảnh chụp ngày 26/10/2026, không thay cho kiểm tra trước mỗi lease.
- `video_processor.py` là cầu nối cũ dùng chung; hợp đồng trong `src/schemas/contracts.py` cũng thuộc vùng shared. Theo `quy_uoc_thi_cong_song_song.md`, chỉ Integrator được ghi các tệp shared này; worker chỉ gửi đề xuất patch.
- `src/schemas/contracts.py` có năm cặp khai báo trùng tên: `TimelineClip`, `TimelineAudioTrack`, `TimelineCaption`, `TimelineDocument` và `TimelineVersionOut`. Khối khai báo thứ hai đang được các caller Python hiện tại, renderer và API TypeScript dùng. Trước khi chuẩn hóa, AGY phải rà caller và dữ liệu cũ; lấy `start_ms` cùng `duration_ms` làm dạng thời gian nền phù hợp với consumer hiện tại, không lưu thêm `end_ms` suy ra nếu không có lý do tương thích đã kiểm chứng.
- `StyleSnapshot` trong `tao_video_noi_dung/contracts.py` dùng `extra="forbid"`; hash của snapshot được gắn vào biên nhận shot và xác minh khi chạy. Không sửa cấu trúc snapshot cấp cao trong phạm vi Vietsub. Nếu cần, thiết kế `CaptionStyleSnapshot` lồng riêng, có version/hash riêng và chỉ gắn vào hợp đồng run mới sau khi được duyệt.
- `voice_asset_id` là tùy chọn. Khi không có audio giọng đọc, Vietsub tự động không được căn theo `storyboard.narration` bằng thời lượng ước tính; đề xuất trạng thái `NO_AUDIO_FOR_VIETSUB` và giữ đường phụ đề thủ công hiện hữu.
- Khóa `threading.Lock()` hiện tại của renderer chỉ tuần tự hóa trong cùng tiến trình. Trước khi cho phép ASR/render, AGY phải xác minh cơ chế lease toàn máy hiện có; nếu không bao phủ mọi worker/process thì thiết kế khóa tài nguyên liên tiến trình, không coi khóa cục bộ là đủ.
- Chưa có bằng chứng ASR tiếng Việt đạt chuẩn trên tập audio có quyền sử dụng; capability giữ `UNVERIFIED`. G1 vẫn chờ Founder duyệt prototype/storyboard/style board. Font, model, ngưỡng benchmark và mọi thay đổi runtime đều chưa được phê duyệt.

### Trạng thái điều phối sau khi Founder duyệt kế hoạch

Pha 0 chỉ đọc đã hoàn tất; báo cáo nằm tại `ke_hoach_tao_video_tu_noi_dung/bang_chung/bao_cao_khao_sat_vietsub_20261026.md`. Các đầu ra nghiên cứu tài liệu ASR, đặc tả phong cách và gói quyết định Founder đã hoàn tất tại `nghien_cuu_asr_vietsub.md`, `bang_phong_cach_vietsub.md` và `goi_duyet_vietsub.md`. Đây là gói nghiên cứu/kế hoạch, chưa phải prototype G1 đã được duyệt. Founder vẫn cần quyết định model và corpus benchmark, font/style cuối, rubric, prototype trực quan và lease runtime trước khi mở Pha 3.

Lần kiểm tra working tree cuối trong lượt hoàn thiện kế hoạch phát hiện các tệp tracked đang sửa: `ke_hoach_tao_video_tu_noi_dung/nghien_cuu_hien_trang_va_phuong_an.md`, `sin_content_api/src/migrations/runner.py`, `sin_content_api/src/models/entities.py`, `sin_content_api/src/modules/tao_video_noi_dung/contracts.py`, `sin_content_api/src/modules/tao_video_noi_dung/service.py` và `sin_content_api/tests/test_content_video_pipeline.py`. Có mục untracked `sin_content_api/src/modules/tao_video_noi_dung/tts_provider.py`, `docs/superpowers/` cùng các mục đã ghi trong báo cáo Pha 0. Chưa xác minh owner hoặc nội dung diff của các thay đổi mới; bảo toàn nguyên trạng và không giao lease chạm các tệp này cho tới khi AGY xác nhận owner/base hash.

Bước AGY tiếp theo là trình một lần gói quyết định tại `goi_duyet_vietsub.md`. Các đầu ra nghiên cứu tài liệu ASR, đặc tả phong cách và khuyến nghị đã hoàn tất liên tiếp; không cần dừng giữa chúng để hỏi lại. Sau quyết định Founder, AGY mới chuẩn bị prototype trực quan G1, khóa hợp đồng và quyền dữ liệu, rồi mới cân nhắc lease runtime. Không tải font/model, không sửa code, không gọi provider và không chạy benchmark trước khi có phê duyệt phù hợp.

## Thẻ giao việc AGY: hoàn tất gói nghiên cứu và duyệt Vietsub

**Task ID:** `vietsub_20261026_ke_hoach_va_goi_duyet`  
**Chủ trì và chịu trách nhiệm đầu ra:** Antigravity (kiến trúc, tích hợp, kiểm định).  
**Rà soát độc lập:** Gemini 3.8 Flash High qua Antigravity CLI; AGY phải xác minh nhận định theo repo/tài liệu gốc.  
**Trạng thái:** Pha 0 và gói tài liệu nghiên cứu/đề xuất 1–2b hoàn tất; prototype trực quan G1, quyết định Founder và benchmark còn chờ.  
**Vùng ghi:** Chỉ tài liệu/mẫu trong `03_ban_lam_viec/ke_hoach_tao_video_tu_noi_dung/`. Không sửa `00_bat_dau/COMMAND_CONTROL_CARD.md` trong lượt Codex này; AGY cập nhật thẻ chính thức khi tiếp nhận task theo quyền của mình.

| Task | Việc AGY làm | Đầu ra bắt buộc | Điều kiện hoàn tất | Trạng thái |
|---|---|---|---|---|
| `vietsub_00_khao_sat` | Đối chiếu Git, call chain, schema, runner, renderer, API/UI và blocker. | `bang_chung/bao_cao_khao_sat_vietsub_20261026.md` | Giữ nguyên các thay đổi tracked/untracked khác. | Hoàn tất; ảnh chụp trạng thái tại ngày 26/10/2026. |
| `vietsub_01_nghien_cuu_asr` | Rà soát tài liệu chính thức của VibeVoice-ASR, Whisper và forced alignment; đối chiếu hỗ trợ tiếng Việt, timestamp, license/model card, mã thực thi từ xa, dependency, tài nguyên và ranh giới dữ liệu. | `nghien_cuu_asr_vietsub.md` | Có bảng so sánh, nguồn gốc và khuyến nghị; chưa chạy model; capability vẫn `UNVERIFIED`. | Hoàn tất nghiên cứu tài liệu; benchmark chờ phê duyệt. |
| `vietsub_02_phong_cach` | Đề xuất hai style bằng cùng câu mẫu; ghi font candidate, cỡ chữ, tương phản, nền, vị trí, safe zone và giới hạn đọc. | `bang_phong_cach_vietsub.md` | Đặc tả bằng văn bản. Prototype trực quan trên video thật thuộc G1 sau khi Founder chọn hướng và xác nhận quyền dùng tư liệu; chưa có font asset được duyệt. | Hoàn tất đặc tả; prototype G1 chờ. |
| `vietsub_02b_goi_duyet` | Gom ASR, style, phạm vi MVP, rubric, quyền dữ liệu, chi phí/tài nguyên và blocker thành một lần Founder xem xét. | `goi_duyet_vietsub.md` | Nêu lựa chọn, hệ quả, khuyến nghị, phần chưa xác minh và quyết định Founder cần ghi nhận. | Hoàn tất; chờ quyết định Founder. |
| `vietsub_03_khoa_hop_dong` | Sau quyết định Founder, Integrator rà dữ liệu timeline cũ, khóa hợp đồng caption/style, owner file, hash, dependency, lease và rollback. | `dieu_phoi_song_song/hop_dong_khoa_vietsub_v1.md` và task card chính thức do AGY cập nhật | Chỉ mở sau khi G1/style, ASR/data, rubric và quyền cần thiết được ghi nhận. | Chưa mở. |
| `vietsub_04_thi_cong_runtime` | Cấp từng lease file rõ ràng cho Codex; Integrator giữ file shared và tích hợp proposal. | Mã, test và evidence theo task card được duyệt | Chỉ chạy sau khi contract hash, owner/base hash, môi trường và concurrency 1 được xác minh. | Chưa mở; nằm ngoài lượt nghiên cứu này. |
| `vietsub_05_nghiem_thu` | Kiểm tra tích hợp, ASR thực, render, SRT, safe zone, idempotency, quyền và rollback. | Báo cáo nghiệm thu trong vùng bằng chứng được cấp | Không nâng checkpoint hoặc công bố ASR đạt nếu chưa có dữ liệu hợp lệ và bằng chứng thực tế. | Chưa mở. |

### Chỉ thị thực thi cho AGY

> Đã hoàn tất các task nghiên cứu tài liệu `vietsub_01_nghien_cuu_asr`, đặc tả `vietsub_02_phong_cach` và gói quyết định `vietsub_02b_goi_duyet`; đầu ra lần lượt là ba tài liệu cùng tên trong thư mục này. Không dừng giữa các đầu việc tài liệu độc lập để hỏi lại. Chỉ dùng nguồn/tài liệu được phép, phân biệt dữ kiện, đề xuất và suy luận. Lượt này không sửa mã nguồn hoặc trạng thái, không chạy test, ASR, benchmark, FFmpeg, DB, Flow, TTS, không tải font/model và không gọi API tính phí. Bàn giao Founder một lần qua `goi_duyet_vietsub.md`; quyết định Founder và cổng G1 vẫn cần có trước Pha 3.

### Gói quyết định Founder nhận một lần

1. Xác nhận phạm vi Vietsub theo audio thực tế; không tạo cue tự động nếu thiếu `voice_asset_id`.
2. Chọn style A/B hoặc yêu cầu điều chỉnh; duyệt font cụ thể, license/quyền nhúng, fallback và palette.
3. Chọn ứng viên ASR/forced alignment để benchmark; duyệt quyền sử dụng bộ audio, lưu trữ/xử lý dữ liệu và ngân sách.
4. Duyệt rubric benchmark đề xuất, gồm WER, độ chính xác thuật ngữ, timestamp, thời gian xử lý và giới hạn tài nguyên.
5. Xác nhận G1/prototype và cho phép AGY mở Pha 3 chuẩn bị hợp đồng. Đây chưa phải lease runtime; lease ghi code là quyết định riêng sau khi contract và phạm vi file được khóa.

Sau khi trình đủ gói này, AGY chờ một quyết định tổng hợp của Founder; không phát sinh yêu cầu duyệt lẻ giữa nghiên cứu ASR, style board và bản tổng hợp. Nếu Founder chưa duyệt một hạng mục, AGY chỉ giữ đúng hạng mục phụ thuộc đó ở trạng thái chờ, không làm lại phần độc lập đã hoàn tất.

## Phạm vi phiên bản đầu

- Sinh phụ đề theo từng câu hoặc cụm lời nói có mốc thời gian. Chưa làm karaoke tô sáng từng từ vì chưa xác minh được timestamp cấp từ.
- Hỗ trợ narration có sẵn và audio đầu vào. Transcript nhận dạng phải đối chiếu với script khi có; khác biệt cần hiện rõ cho người duyệt.
- Tạo Vietsub cho luồng `CONTENT_VIDEO_RENDER`, lưu cue trong phiên bản timeline và render thành MP4. Gói xuất kèm SRT và provenance.
- Cho phép sửa nội dung/thời điểm cue rồi render lại từ timeline hiện có. Sửa Vietsub không gửi lại lệnh tạo cảnh Flow.
- Giữ luồng phụ đề thủ công của Media Studio tương thích. Không tự bật một style mặc định chưa được duyệt cho mọi workspace.

## Hiện trạng và kết quả nghiên cứu

- `tao_video_noi_dung/runner.py` hiện tạo timeline clip và voice track nhưng chưa thêm cue phụ đề; QC ghi `speech_alignment: NOT_MEASURED`.
- `media_studio/video_processor.py` đã có FFmpeg `drawtext`, nhưng đang cố định Arial, cỡ chữ mặc định, màu vàng, nền đen bán trong suốt và vị trí theo công thức cố định.
- `src/schemas/contracts.py` có hai khai báo `TimelineCaption`; phải hợp nhất thành một hợp đồng chuẩn trước khi mở rộng.
- `understanding/asr_evaluator.py` chỉ tính WER trên cặp transcript đã có; trạng thái ASR thật mặc định là `UNVERIFIED`.
- Tài liệu `nghien_cuu_tich_hop_tts_vietnamese.md` đã rà soát Vietnamese TTS Studio và khuyến nghị không đưa nguyên ứng dụng Flask, queue SQLite hoặc giọng mẫu vào sản phẩm.
- Thư mục tham khảo `tham_chieu_vietnamese_tts_studio/` có nhánh VibeVoice-ASR tùy chọn. README ghi ASR mặc định tắt và cần môi trường riêng do xung đột dependency. API có thể trả đoạn người nói với `start`, `end`, `text`; đây là timestamp theo đoạn, chưa bảo đảm timestamp từng từ. Mã dùng `trust_remote_code=True`; cần pin revision và rà soát bảo mật trước khi chạy.
- Model card Microsoft VibeVoice-ASR-HF hiện nêu 51 ngôn ngữ, timestamp theo đoạn, license MIT, 8B tham số BF16 và khoảng 16,7 GB tệp model; trang được rà soát không liệt kê cụ thể tiếng Việt trong phần văn bản. Không coi tổng số ngôn ngữ là bằng chứng hỗ trợ hoặc chất lượng tiếng Việt. Chất lượng tiếng Việt vẫn cần đo trên dữ liệu có quyền sử dụng. [Model card Microsoft](https://huggingface.co/microsoft/VibeVoice-ASR-HF).
- Whisper multilingual có mã ngôn ngữ `vi` trong tokenizer chính thức; README mô tả nhận dạng lời nói không phải tiếng Anh. Đây là căn cứ để đưa Whisper vào benchmark, không phải bằng chứng đạt ngưỡng chất lượng trên tiếng Việt của dự án. [Whisper README](https://github.com/openai/whisper/blob/main/README.md), [danh sách ngôn ngữ trong tokenizer](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py).
- Montreal Forced Aligner có acoustic model tiếng Việt dành cho căn lời theo transcript; đây không phải ASR. Tài liệu model cảnh báo về miền lời đọc ít nhiễu và không cung cấp metric độc lập đủ để suy ra chất lượng trên corpus BAHA. Xem chi tiết cùng giới hạn tại `nghien_cuu_asr_vietsub.md`.
- Ứng viên font để làm mẫu là Be Vietnam Pro SemiBold, trọng lượng 600. Google Fonts khai báo có bộ ký tự tiếng Việt và giấy phép SIL Open Font License 1.1. Đây là ứng viên cần Founder duyệt, không phải lựa chọn thương hiệu đã khóa. [Google Fonts](https://fonts.google.com/specimen/Be+Vietnam+Pro), [metadata và giấy phép](https://github.com/google/fonts/tree/main/ofl/bevietnampro).
- Renderer `drawtext` phụ thuộc các tùy chọn biên dịch FFmpeg, gồm libfreetype và libharfbuzz. Antigravity cần xác minh binary của môi trường dựng trước khi chốt kỹ thuật. [Tài liệu FFmpeg](https://ffmpeg.org/ffmpeg-filters.html#drawtext).

## Ràng buộc chung

- Mã nguồn, kế hoạch và tài sản thử nghiệm thuộc SSOT `03_ban_lam_viec/`; tên tệp mới dùng tiếng Việt không dấu, chữ thường, snake_case.
- Nội dung giao diện, tài liệu và báo cáo dùng tiếng Việt đầy đủ dấu. Không dùng emoji hoặc ký hiệu hình ảnh Unicode.
- Khung TikTok mặc định 1080 x 1920, 30 fps; vùng an toàn trên 150 px, dưới 320 px, phải 120 px, lề trái đề xuất 60 px.
- Caption tối đa 2 dòng, 38 ký tự mỗi dòng, tối đa 20 ký tự/giây, cue từ 0,7 đến 6 giây; tính theo font thực đã khóa.
- Font phải có ID/hash, trọng lượng, kiểm tra đủ glyph tiếng Việt, quyền nhúng, giấy phép và fallback được duyệt. Không âm thầm rơi về Arial hoặc font hệ điều hành.
- Tác vụ ASR/render nặng dùng concurrency bằng 1. Resume và render lại phải idempotent; không tạo lại clip hoặc gọi ASR lặp khi hash đầu vào không đổi.
- Không ghi audio, transcript nhạy cảm, cookie hoặc khóa vào log. Không gửi dữ liệu ra provider khi chưa xác minh quyền, endpoint và ngân sách.
- Tài liệu `quy_chuan_phong_cach_kenh.md` yêu cầu Founder duyệt style board và binding trước runtime. Tài liệu này không tự cấp lease hoặc vượt G1.

## Trọng tâm rà soát

1. Audio không có lời, quá ngắn hoặc có nhạc lấn giọng: không tạo cue giả; trả blocker hoặc chờ nhập/sửa transcript. Kiểm bằng fixture im lặng và nhạc nền.
2. Lời đọc khác script đã duyệt: giữ transcript nhận dạng để đối chiếu, gắn trạng thái cần xem lại, không tự sửa câu chữ. Kiểm bằng fixture có bỏ từ, thêm từ và đổi tên riêng.
3. Dấu tiếng Việt, chữ hoa, số và thuật ngữ: glyph phải liền dấu, không rơi font; kiểm bằng câu thử gồm `ă â ê ô ơ ư đ` và thuật ngữ công nghệ.
4. Đoạn dài, tốc độ đọc cao hoặc vượt safe zone: chỉ ngắt ở ranh giới hợp lệ; nếu không có timestamp đủ tin cậy thì chuyển xem lại, không chia thời gian đều theo số ký tự.
5. ASR, font hoặc FFmpeg không sẵn sàng: không âm thầm xuất video như đã có Vietsub; báo trạng thái và giữ bản dựng có thể tiếp tục.

## Bản đồ tệp dự kiến sau khi có lease

| Tệp | Trách nhiệm dự kiến |
|---|---|
| `sin_content_api/src/modules/tao_video_noi_dung/vietsub.py` | Điều phối adapter, xác thực đoạn nhận dạng, đối chiếu script, tạo cue và khóa idempotency. |
| `sin_content_api/src/modules/tao_video_noi_dung/runner.py` | Điểm nối pipeline dự kiến. AGY xác định caller và owner ở Pha 0; nếu đây là file shared hoặc có nhiều consumer, Integrator giữ quyền ghi và worker chỉ gửi đề xuất patch. |
| `sin_content_api/src/schemas/contracts.py` | Hợp đồng shared, chỉ Integrator ghi. Rà soát đủ năm cặp khai báo trùng tên và consumer/dữ liệu cũ; phạm vi Vietsub dùng hợp đồng đang hoạt động nếu kiểm tra tương thích xác nhận. |
| `sin_content_api/src/modules/media_studio/video_processor.py` | Cầu nối cũ shared, chỉ Integrator ghi. Worker gửi đề xuất patch; renderer dùng font asset/hash và style snapshot đã duyệt. |
| `sin_content_api/src/modules/tao_video_noi_dung/contracts.py` | Không sửa `StyleSnapshot` cấp cao đã được hash trong biên nhận. Nếu cần, Integrator định nghĩa `CaptionStyleSnapshot` riêng, có version/hash riêng, sau khi kiểm tra tương thích run đang xử lý. |
| `sin_content_api/tests/test_vietsub_pipeline.py` | Kiểm tra adapter, cue, đối chiếu script, lỗi, idempotency và giới hạn đọc; owner riêng sau khi xác nhận file mới và lease. |
| `sin_content_api/tests/test_media_studio_video.py` | Kiểm tra render font, glyph tiếng Việt, safe zone và lỗi font; owner riêng, không ghi fixture chung khi chưa có lease. |
| `sin_content_api/tests/test_content_video_pipeline.py` | Kiểm tra run tự động lưu cue/snapshot/provenance và resume; owner riêng, phối hợp Integrator nếu cần sửa fixture hoặc hợp đồng shared. |
| `sin_creator_os/src/app/(main)/video-studio/[projectId]/production/_components/content_video_production.tsx` | Xem trước và sửa caption, báo khác biệt ASR/script, lưu revision; owner được chốt theo phạm vi file chính xác và dependency UI. |
| `sin_creator_os/src/lib/api/content-video-api.ts` | Hợp đồng frontend/API cho track và trạng thái Vietsub; xác định có phải client/type registry shared không trước khi cấp owner ghi. |
| `sin_creator_os/src/lib/api/media-studio-api.ts` | Hợp đồng TypeScript timeline/caption đang dùng; chỉ Integrator nối nếu cần đổi schema shared. |
| `sin_creator_os/src/app/(main)/video-studio/[projectId]/page.tsx` | Caller Media Studio hiện hữu có chỉnh/xem caption thủ công; rà soát để giữ tương thích, chỉ giao một owner nếu có thay đổi cần thiết. |

Antigravity phải đối chiếu `git status`, diff và hash từng tệp ngay trước khi giao task. Danh sách trên là bản đồ dự kiến, không thay cho owner theo file, hợp đồng đã khóa hoặc lease. Không reset, checkout, clean, restore hoặc chép đè thay đổi hiện hữu. Tích hợp viên chỉ giao Codex sau khi mỗi file có owner, điểm bàn giao, dependency và hash nền rõ ràng.

## Các pha công việc

### Pha 0: Khóa phạm vi và điểm xuất phát

**Chủ trì:** Antigravity. **Loại công việc:** chỉ đọc.

- [x] Đọc trạng thái hiện tại, thẻ điều phối, checkpoint và các tài liệu chuẩn nêu trên.
- [x] Ghi nhận HEAD `dd85841`, nhánh `main`, một file tracked đang sửa và các mục untracked tại thời điểm Pha 0. Lượt phản biện đầu tiên cùng ngày chưa thấy tracked change; kiểm tra lại status/hash ngay trước mỗi lease và giữ nguyên mọi mục hiện hữu.
- [x] Lập bản đồ consumer cho năm cặp model Timeline, `StyleSnapshot`, runner, renderer, API và UI; xác định file shared theo quy ước và ghi owner dự kiến trong báo cáo.
- [x] Ghi nhận `voice_asset_id` có thể vắng mặt và khóa render hiện chỉ có phạm vi một tiến trình; chưa có bằng chứng về khóa tài nguyên toàn máy.
- [x] Founder duyệt phạm vi kế hoạch: Vietsub theo câu/cụm lời trong `CONTENT_VIDEO_RENDER`; không bao gồm dịch ngôn ngữ khác, karaoke từng từ, tiêu đề đồ họa hay gọi provider Flow. Các quyết định riêng về G1, font, ASR, dữ liệu, benchmark và lease vẫn đang chờ.
- [x] Kết quả: `ke_hoach_tao_video_tu_noi_dung/bang_chung/bao_cao_khao_sat_vietsub_20261026.md` ghi nhận khảo sát và blocker.

### Pha 1: Benchmark ASR và căn thời gian sau phê duyệt

**Chủ trì:** Antigravity. **Worker thực thi mã benchmark:** chưa phân công trước khi có lease và bộ audio được duyệt quyền.

Nghiên cứu tài liệu/model card đã hoàn tất trong `nghien_cuu_asr_vietsub.md`. Các mục dưới đây mô tả kiểm tra bổ sung và benchmark; không chạy trước khi Founder duyệt quyền corpus, ngân sách và lease.

- [x] Đọc API, `tts_service.py`, cấu hình và README của `tham_chieu_vietnamese_tts_studio/`; ghi nhận schema đoạn, dependency, trạng thái mặc định và hành vi timestamp trong báo cáo khảo sát ASR.
- [x] Rà soát model card, giấy phép model, `trust_remote_code`, yêu cầu pin revision và cách ly tiến trình. Chưa tải trọng số hoặc khởi chạy model.
- [x] Đề xuất MFA cho audio có script đã duyệt; Whisper multilingual làm baseline ASR cho audio thiếu transcript; VibeVoice-ASR làm đối chứng có điều kiện tài nguyên. Đây là phương án benchmark, chưa chọn model production.
- [x] Đề xuất benchmark tối thiểu 20 đoạn audio, tổng ít nhất 20 phút, tối thiểu 3 giọng đọc, điều kiện sạch/nhiễu và từ điển thuật ngữ BAHA. Thu thập audio, gán nhãn và chạy benchmark chỉ sau khi chủ sở hữu xác nhận quyền dữ liệu và Founder duyệt phạm vi.
- [ ] Đo WER tiếng Việt, độ chính xác thuật ngữ, tỷ lệ segment có timestamp hợp lệ, độ lệch mốc đầu/cuối so với người rà soát, thời gian xử lý, RAM/VRAM và tỷ lệ lỗi. Mục tiêu đề xuất để Founder duyệt trước benchmark: WER tổng không quá 10% trên narration sạch, độ chính xác thuật ngữ ít nhất 95%, trung vị sai lệch biên cue không quá 300 ms và phân vị 95 không quá 800 ms.
- [ ] Kết quả: bảng so sánh, raw log đã loại đường dẫn/dữ liệu nhạy cảm, capability status `REAL_VERIFIED`, `REAL_UNVERIFIED` hoặc `BLOCKED`, và quyết định dùng hay loại ứng viên.

### Pha 2: Prototype trực quan, chốt style Vietsub và duyệt G1

**Chủ trì:** Antigravity. **Người duyệt:** Founder.

Đặc tả hai hướng A/B đã có trong `bang_phong_cach_vietsub.md`. Các mục dưới đây là prototype trực quan và quyết định G1; không được coi đặc tả văn bản là style đã duyệt.

- [x] Đặc tả bằng văn bản hai hướng trên cùng câu mẫu và ba điều kiện nền: nền tối, nền sáng và cảnh nhiều chi tiết.
- [x] Đề xuất A: Be Vietnam Pro SemiBold, chữ sáng, viền/bóng tối mảnh; B: cùng font với hộp caption tối bán trong suốt. Chưa khóa màu thương hiệu hoặc font production.
- [ ] Ghi chính xác font file, hash, weight, license, kiểm tra dấu, cỡ chữ, line-height, giới hạn dòng, độ đục nền, viền/bóng, căn lề, bounding box và vùng an toàn. Chỉ chọn fallback nếu Founder duyệt.
- [ ] Trình Founder chọn một biến thể hoặc yêu cầu sửa. Lưu quyết định và hash của style board; cập nhật trạng thái G1 theo quyền điều phối. Không bắt đầu runtime nếu chưa được duyệt.
- [ ] Dừng tại cổng này để chờ Founder duyệt bằng văn bản style board Vietsub, font/quyền nhúng, storyboard/prototype G1 và rubric nghiệm thu. Không chuyển sang đóng băng hợp đồng runtime hoặc cấp lease khi chưa ghi nhận đủ quyết định.

### Pha 3: Đóng băng hợp đồng và cấp lease

**Chủ trì:** Antigravity, với vai trò integrator duy nhất.

- [ ] Kiểm consumer của năm cặp model Timeline. Consumer hiện tại dùng khối khai báo thứ hai, trong đó caption dùng `caption_id`, `text`, `start_ms`, `duration_ms`, `font_size`, `safe_zone`; xác nhận dữ liệu lưu cũ trước khi chuẩn hóa. `CaptionCue` dùng `start_ms` và `duration_ms` làm ứng viên chuẩn, không lưu đồng thời `end_ms` suy ra nếu không có nhu cầu tương thích đã chứng minh.
- [ ] Đóng băng `CaptionTrack`: `transcript_source` là `ASR`, `ASR_SCRIPT_CONFIRMED` hoặc `MANUAL`; kèm audio SHA-256, transcript SHA-256, provider/model/revision nếu có, ngôn ngữ, trạng thái xem lại và danh sách cue. `ASR_SCRIPT_CONFIRMED` chỉ được dùng sau khi transcript nhận dạng khớp script đã duyệt. Nếu provider không có word timestamp, không khai báo độ chính xác cấp từ.
- [ ] Đóng băng `CaptionStyleSnapshot` riêng: font asset ID/hash, family, weight, size, line height, màu chữ, nền/độ đục, viền/bóng, anchor, lề và version/hash. Không sửa `StyleSnapshot` cấp cao đang tham gia `style_snapshot_sha256`/biên nhận shot; lưu cấu hình Vietsub theo cách không làm mất hiệu lực approval receipt cũ.
- [ ] Chốt hành vi mismatch: khi transcript và script không khớp, đánh dấu `REVIEW_REQUIRED`; chỉ áp script làm chữ hiển thị sau khi người duyệt xác nhận audio đọc đúng. Không để LLM tự viết lại transcript.
- [ ] Chốt trạng thái lỗi: provider/font/FFmpeg không sẵn sàng thì `CAPTION_BLOCKED` hoặc chờ sửa thủ công; không xuất bản như bản đã đạt Vietsub. Rerender dùng cue đã lưu, không gửi lại Flow hoặc ASR nếu hash đầu vào không đổi.
- [ ] Nếu thiếu `voice_asset_id`, chặn tạo Vietsub tự động bằng trạng thái `NO_AUDIO_FOR_VIETSUB`; không ước lượng timestamp từ lời kịch bản. Đường nhập/sửa caption thủ công của Media Studio giữ nguyên.
- [ ] Xác minh lease/hàng đợi hiện có có tuần tự hóa render xuyên mọi process hay không. `threading.Lock()` trong `VideoProcessor` không đủ; nếu không có khóa toàn máy, thiết kế/cấp một lease liên tiến trình trước khi gọi ASR hoặc render, giữ tổng concurrency nặng bằng 1.
- [ ] Tạo task card runtime gồm Task ID, lane, owner từng tệp, hash nền, dependency, môi trường DB/tmp/profile/port, lease/heartbeat và tiêu chí rollback theo `quy_uoc_thi_cong_song_song.md`.
- [ ] Chỉ Integrator cập nhật schema shared, renderer shared, route/registry và các điểm nối chung. Worker chỉ nhận lease trên file mới hoặc file riêng đã được gán đích danh; mọi thay đổi shared đi qua proposal/hàng đợi tích hợp.

### Pha 4: Triển khai sau phê duyệt

**Chủ trì kỹ thuật:** Codex theo lease Antigravity cấp. **Antigravity không sửa các tệp đã giao cho Codex trong thời gian lease.**

- [ ] Viết test thất bại với các tên cố định: `test_vietsub_rejects_invalid_segment_times`, `test_vietsub_without_voice_asset_is_blocked`, `test_vietsub_silence_returns_no_cues`, `test_vietsub_script_mismatch_requires_review`, `test_vietsub_long_segment_requires_review`, `test_vietsub_reuses_result_for_same_input_hash`, `test_caption_renderer_fails_when_pinned_font_missing`, `test_caption_renderer_keeps_vietnamese_diacritics`, `test_content_video_run_persists_caption_track_and_srt`. Bổ sung kiểm tra concurrency liên tiến trình nếu lease render hiện hữu chưa bao phủ trường hợp này.
- [ ] Codex chỉ xây module mới và các file riêng đã ghi trong task card, gồm `vietsub.py` và test mới nếu được cấp. Integrator nối caller, schema shared, renderer, router/client registry và fixture shared qua proposal theo hàng đợi. Dùng một hàng đợi/lease duy nhất cho inference nặng; không import toàn bộ ứng dụng Flask tham khảo vào FastAPI chính.
- [ ] Hợp nhất model `TimelineCaption`; lưu track/provenance/style snapshot vào timeline và manifest. Không đổi transcript đã duyệt khi resume.
- [ ] Sinh cue từ segment được ASR trả về. Chỉ gộp/ngắt khi mốc thời gian có dữ liệu đủ; đoạn vi phạm 0,7–6 giây hoặc vượt giới hạn dòng/tốc độ phải chuyển người duyệt.
- [ ] Dùng font đã duyệt bằng đường dẫn asset được quản lý; cập nhật drawtext theo snapshot và xác minh binary FFmpeg có filter cần thiết. Lỗi glyph/render phải dừng rõ ràng.
- [ ] Bổ sung màn xem trước, sửa văn bản/thời điểm, xác nhận mismatch và lưu revision. Xuất MP4 burn-in, tệp SRT và provenance trong gói xuất.
- [ ] Chạy backend từ `03_ban_lam_viec/sin_content_api`: `python -m pytest tests/test_vietsub_pipeline.py tests/test_media_studio_video.py tests/test_content_video_pipeline.py -q`; kết quả mong đợi là toàn bộ test mục tiêu đạt.
- [ ] Chạy frontend từ `03_ban_lam_viec/sin_creator_os`: `pnpm exec tsc --noEmit`; kết quả mong đợi là mã thoát 0. Chạy `git diff --check` và Python compile cho tệp backend đã cấp lease.
- [ ] Xác minh binary FFmpeg bằng `ffmpeg -hide_banner -filters` và `ffmpeg -hide_banner -h filter=drawtext`; kết quả phải có `drawtext` và các tùy chọn được renderer dùng. Không cài dependency ngoài lease.
- [ ] Không commit thay đổi ngoài owner hoặc ngoài lease.

### Pha 5: Nghiệm thu và bàn giao

**Chủ trì:** Antigravity.

- [ ] Chạy một video thử 20–60 giây từ asset/audio có quyền, không gọi Flow thật. Kiểm transcript, mốc cue, render MP4, SRT, full decode và metadata.
- [ ] Kiểm thủ công ít nhất 12 frame gồm đầu/giữa/cuối và cảnh sáng/tối/nhiều chi tiết; xác nhận dấu tiếng Việt, không cắt chữ, không che UI TikTok, bounding box nằm trong safe zone.
- [ ] Đối chiếu WER, thuật ngữ, timing, chi phí/tài nguyên, idempotency và trạng thái lỗi với rubric đã được duyệt. Lỗi chưa qua thì giữ `UNVERIFIED` và không nâng checkpoint.
- [ ] Lưu log, ảnh frame, hash artifact, test output và biên bản trong vùng bằng chứng được project governance cho phép. Cập nhật `CURRENT_STATE.md`; chỉ tạo checkpoint/restore point khi Antigravity xác nhận một gate đã hoàn tất.

## Tiêu chí nghiệm thu cuối

- Vietsub được tạo từ audio cuối hoặc script đã căn với audio; mọi cue có thời điểm hợp lệ, nằm trong thời lượng và truy được nguồn.
- Tiếng Việt có đầy đủ dấu; tối đa 2 dòng, 38 ký tự mỗi dòng, 20 ký tự/giây; cue 0,7–6 giây; nội dung không vượt safe zone 1080 x 1920.
- Style snapshot và font hash của timeline khớp bản MP4 đã render; không có fallback ngầm.
- Người dùng xem/sửa cue và render lại không tạo lệnh tạo video hoặc ASR trùng khi dữ liệu không đổi.
- Mismatch, provider lỗi, thiếu font hoặc lỗi FFmpeg hiện thành trạng thái chờ/blocker; bản xuất không bị đánh dấu đạt Vietsub.
- Backend tests, compile, frontend typecheck và một lượt render thử đều có output lưu được; không tuyên bố ASR đã xác minh chỉ từ mock.

## Nguồn nghiên cứu

- `03_ban_lam_viec/ke_hoach_tao_video_tu_noi_dung/nghien_cuu_tich_hop_tts_vietnamese.md`.
- `03_ban_lam_viec/tham_chieu_vietnamese_tts_studio/README.md`, `webapp/tts_service.py`, `webapp/app.py`.
- [Microsoft VibeVoice-ASR-HF](https://huggingface.co/microsoft/VibeVoice-ASR-HF).
- [Be Vietnam Pro trên Google Fonts](https://fonts.google.com/specimen/Be+Vietnam+Pro) và [giấy phép OFL trong kho Google Fonts](https://github.com/google/fonts/tree/main/ofl/bevietnampro).
- [Tài liệu bộ lọc drawtext của FFmpeg](https://ffmpeg.org/ffmpeg-filters.html#drawtext).
