# Nghiên cứu cải tổ bộ tạo video từ nội dung

Ngày khảo sát: 23/10/2026. Phạm vi phiên này: nghiên cứu, đặc tả, kế hoạch và điều kiện nghiệm thu; chưa thay mã nguồn sản phẩm.

## 1. Yêu cầu được ưu tiên

Người dùng nhập nội dung, chẳng hạn yêu cầu video 2 phút. Hệ thống phải hiểu mục tiêu, xây kịch bản, chia phân cảnh, tạo prompt riêng, điều phối tạo tư liệu và lắp ráp thành video hoàn chỉnh để đội xây kênh sử dụng. Đây là hệ thống nội bộ BAHA, không phải sản phẩm bán cho khách hàng.

Tài liệu định hướng: `C:/Users/Baha Group/Downloads/BAHA_CREATOR_STUDIO_MASTER_TRANSFORMATION_SPEC.md`, phiên bản 1.0. Bản sao nguyên văn đi cùng hồ sơ: `dinh_huong_goc_cua_founder.md`; hash nguồn trong `bang_chung/khao_sat_thuc_te.json`. Đề nghị trực tiếp về video 120 giây bổ sung ca nghiệm thu bắt buộc; không thay thế demo 45–60 giây của tài liệu gốc.

Các lựa chọn do Codex đề xuất, chưa coi là Founder đã duyệt: hỗ trợ đầu tiên 30–180 giây, xuất dọc 1080 × 1920 ở 30 fps, dung sai thành phẩm tối đa 0,5 giây; có chế độ giữ nguyên lời và chế độ biên soạn từ ý tưởng. Các định dạng dài hơn và ngang được mở theo giai đoạn, không âm thầm cắt yêu cầu về 60 giây.

## 2. Bằng chứng hiện trạng

Các đường dẫn dưới đây tương đối với `03_ban_lam_viec/`. Số dòng là vị trí khảo sát, hash cho phép phát hiện thay đổi sau khảo sát.

| Thành phần | Bằng chứng trực tiếp | Kết luận và phương án |
|---|---|---|
| Nút tự động | `sin_creator_os/src/app/(main)/video-studio/[projectId]/page.tsx:394`: nhạc cố định 30 giây, gọi một `generateVideo`, `durationMs` lấy từ clip, `voice_track: null` | REFACTOR: chuyển quyền điều phối về backend, nhập thời lượng rõ ràng; không dùng chức năng này làm bộ tạo phim dài |
| Biên dịch prompt | `sin_content_api/src/modules/media_studio/prompt_compiler.py:31`: chỉ dẫn một cảnh liền mạch, trả một `CompiledVideoPrompt` | KEEP ở cấp shot; EXTEND bộ lập kế hoạch nhiều cảnh bên trên. Không sửa compiler thành hàm vừa viết truyện vừa gọi provider |
| API tạo clip | `sin_content_api/src/modules/media_studio/router.py:869`: nhận prompt, tỷ lệ, project, ảnh đầu; chưa có thời lượng đích toàn phim hoặc storyboard trong hợp đồng này | KEEP endpoint clip cũ; thêm API tạo kế hoạch/run toàn phim riêng |
| Bộ điều phối clip | `sin_content_api/src/modules/media_studio/video_provider.py:140`: I2V biên dịch 10 giây, tạo 16:9 rồi chuẩn hóa dọc; `GoogleOfficialOmniProvider` cũng gọi `flow_provider` | REFACTOR capability và tên provider theo đường gọi thật; chưa có bằng chứng đây là API chính thức riêng |
| Dựng timeline | `sin_content_api/src/modules/media_studio/video_processor.py:243`: chuẩn hóa clip, concat, phụ đề, voice/music, loudnorm | KEEP và EXTEND; renderer hữu ích nhưng không tự lập kịch bản, không tự tạo voice hoặc xác minh câu chuyện |
| Đạo diễn dựng | `sin_content_api/src/modules/dieu_phoi_dung/dao_dien.py:78`: tạo insert_clip từ evidence speech, sửa theo clip/timecode | KEEP cho hậu kỳ; không nhầm với đạo diễn tạo video từ nội dung trống tư liệu |
| Kịch bản | `sin_content_api/src/modules/scripts/script_service.py:97`: tạo draft gắn IdeaCard, kiểm claim và timing, lưu phiên bản | EXTEND cho đầu vào trực tiếp; tái sử dụng version/approval, không tạo lịch sử kịch bản thứ hai |
| Tính thời gian | `sin_content_api/src/modules/scripts/timing_calculator.py`: cộng thời lượng block nguyên giây, dung sai mặc định 3 giây | KEEP cho gợi ý nháp; thêm thời gian theo frame và audio đo thật cho render |
| Kiểm claim | `sin_content_api/src/modules/scripts/claim_checker.py`: đối chiếu AllowedFact, nhiều quy tắc về tuyên bố sản phẩm | EXTEND claim ledger công nghệ; bộ regex không phải bằng chứng xác minh mọi khái niệm |
| LLM | `sin_content_api/src/modules/llm/client.py:88`: có `LLMClient.from_db`, giới hạn input/output, không tự retry | KEEP; chia lời gọi có cấu trúc để tránh storyboard 120 giây vượt trần output |
| Lưu phiên dựng | `sin_content_api/src/modules/dieu_phoi_dung/kho_luu_tru.py`: SQLite WAL và lease | KEEP semantics CAS/lease; không mặc định SQLite trên NAS là hàng đợi đa máy an toàn |
| Worker | `sin_content_workers/worker.py:126`: `OfflineTaskQueue.jobs` trong RAM | REFACTOR hạ tầng run bền vững; hiện trạng này không đủ bằng chứng resume pipeline tạo video dài |
| Dữ liệu | `sin_content_api/src/models/entities.py:682`: ProductionProject, ProductionTask, MediaAsset, AIGenerationJob, TimelineVersion | EXTEND tối thiểu; giữ ID, nguồn asset, revision và liên kết script |

Không tìm thấy repository Git tại thư mục dự án gốc khi chạy `git status --short`. Không tạo nhánh/commit giả; phải xác định repository quản lý trước thi công. Chưa kết luận các thư mục con là repository độc lập.

`bang_chung/khao_sat_thuc_te.json` ghi HTTP 200 của `/healthz`, `/readyz`, environment offline, `offline_mode=true`; trang `/video-studio` có HTML phản hồi. Đây là kiểm tra khả dụng HTTP, không phải E2E đăng nhập hoặc bằng chứng provider hoạt động. Hai DB tại gốc `03_ban_lam_viec/` được mở read-only không có các bảng production cần kiểm tra; không suy ra ứng dụng không có dữ liệu. Phải đối chiếu DB runtime với cấu hình hiệu lực trong G0.

## 3. Nguyên nhân lệch sản phẩm

Đường đi hiện tại là prompt → một clip → ghép nhạc → MP4. Đơn vị thực thi là clip, còn nhu cầu người dùng là một câu chuyện đủ thời lượng và đủ nội dung. Việc thêm câu “120 giây” vào prompt không giải quyết được giới hạn provider, thiếu lời đọc, thiếu đồng bộ hoặc thiếu tư liệu cho từng luận điểm.

Ba lớp đang cần bổ sung là kế hoạch nội dung có cấu trúc, sản xuất từng thành phần có trạng thái bền vững, và kiểm định thành phẩm theo yêu cầu ban đầu. Timeline/editor và FFmpeg tiếp tục là công cụ của dây chuyền này.

## 4. Nghiên cứu nguồn chính thức

Tra cứu ngày 23/10/2026. Các thông số dưới đây là năng lực được tài liệu mô tả, chưa chứng minh tài khoản công ty có quyền sử dụng.

| Nguồn | Điều xác nhận | Hệ quả thiết kế |
|---|---|---|
| [Veo trong Gemini API](https://ai.google.dev/gemini-api/docs/veo?hl=en) | Có ràng buộc duration/model/resolution/reference; tài liệu mô tả các lựa chọn 4/6/8 giây và điều kiện riêng cho extension | Registry lưu tổ hợp hợp lệ theo provider/model; chia shot theo capability. Không suy giới hạn Flow UI từ Gemini API |
| [Dựng cảnh trong Flow](https://support.google.com/flow/answer/16935718?hl=en) | Có thao tác dựng/extend; extension giới hạn theo loại video | Flow UI là adapter riêng. Không coi thao tác trên trình duyệt là một API cloud chính thức |
| [Danh sách giọng Google Cloud](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types?hl=en) | Có giọng vi-VN | TTS cloud là ứng viên; cần thử entitlement, tiếng Việt có thuật ngữ, latency và giá trước khi bật |
| [API liệt kê giọng](https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/voices/list) | Có endpoint liệt kê giọng | Kiểm tra giọng được tài khoản truy cập thay vì hardcode một giọng dự đoán |
| [Bộ lọc FFmpeg](https://www.ffmpeg.org/ffmpeg-filters.html) | Có loudnorm, sidechaincompress, subtitles và transition filters | Tái sử dụng FFmpeg CPU; kiểm tra bản cài thực có filter/font cần dùng. Có lệnh filter không đồng nghĩa module hiện tại đã hỗ trợ hiệu ứng |

Không cam kết “0 đồng” hoặc thời gian tạo cố định. Subscription, credit, phí cloud, dung lượng và thời gian nhân sự cần ghi tách; chi phí chưa biết phải là chưa xác định, không ghi 0. Không tự động xử lý xóa watermark; giữ provenance và ràng buộc provider trong phương án mới.

## 5. So sánh phương án

| Phương án | Khả năng đáp ứng | Quyết định |
|---|---|---|
| Một prompt dài, một video dài | Phụ thuộc giới hạn model, khó sửa cục bộ, khó đảm bảo nội dung và thời lượng | Không chọn làm kiến trúc chính |
| Mọi cảnh đều gọi AI video | Có thể tạo nhiều clip nhưng tốn lượt, khó chính xác sơ đồ/UI, không tự giải quyết voice/sync | Chỉ dùng cho cảnh phù hợp |
| Kịch bản → storyboard → shot/asset theo loại → voice timing → tự lắp ráp | Đảm bảo bao phủ nội dung, kiểm soát thời lượng, dùng Flow khi cần, sửa được từng cảnh | Chọn làm phương án đề xuất |

Các loại cảnh bắt buộc trong kiến trúc: DIAGRAM, SCREEN_RECORDING, REAL_FOOTAGE, STOCK_BROLL, AI_IMAGE, AI_VIDEO, TEXT_MOTION, BRAND_OUTRO. Cảnh thiếu tư liệu thật phải dừng chờ cung cấp; không dựng UI giả rồi gọi đó là demo thật. Sơ đồ và chữ nên dựng có kiểm soát để tiếng Việt và nội dung chính xác.

## 6. Phạm vi nội bộ và đối chiếu master spec

Giữ phân quyền, truy vết nguồn, version, duyệt và ngân sách vì đây là yêu cầu vận hành nội bộ. Không đưa subscription khách hàng, paywall, quản trị tenant thương mại hoặc thanh toán SaaS vào kế hoạch này. Các workspace hiện có vẫn được giữ để bảo toàn dữ liệu và cách ly nhóm.

Master spec P0–P8 vẫn là định hướng chung. Đợt ưu tiên này xử lý dây chuyền từ nội dung tới gói video; topic radar, lead attribution và analytics toàn công ty là nhánh tiếp theo có phụ thuộc riêng, không được báo đã hoàn thành khi bộ tạo video hoàn tất. Bảng ánh xạ chi tiết nằm trong `ke_hoach_trien_khai_va_checklist.md`.

## 7. Giới hạn khảo sát và bước tiếp quản

Chưa chạy provider tính phí, chưa tạo phim 120 giây, chưa có benchmark giọng/ASR, chưa duyệt storyboard với Founder, chưa kiểm thử GUI có phiên đăng nhập, chưa audit đầy đủ publishing/lead/RBAC và chưa chạy migration. Kết quả kiểm thử cơ sở được ghi riêng, không nâng trạng thái provider nhờ mock test.

Vùng ghi phiên này là `03_ban_lam_viec/` và trạng thái quy định tại `00_bat_dau/`. Bằng chứng được giữ tại thư mục `bang_chung/` của bộ kế hoạch để không vượt vùng ghi; việc đưa bằng chứng nghiệm thu chính thức vào `08_kiem_thu/bang_chung/` và cập nhật trang hành trình gốc do người có vùng ghi phù hợp thực hiện ở gate sau. Không đổi checkpoint nghiệm thu sản phẩm trong phiên nghiên cứu.


## 8. C?p nh?t l?a ch?n TTS ti?ng Vi?t ? 2026-10-26

B? sung VieNeu-TTS v3 Turbo l?m ?ng vi?n th? hai b?n c?nh Gwen-TTS. Ch? m?t provider/model ???c n?p v? ch?y t?i m?t th?i ?i?m; job ghi provider/version ?? ch?n, kh?ng ch?y song song v? kh?ng fallback t? ??ng. VieNeu c? backend CPU ONNX/GPU PyTorch, audio 48 kHz v? voice cloning; c?c s? ?o t?c ?? v? s? preset c?n ph? thu?c phi?n b?n upstream, c?n pin b?n v? benchmark n?i b?. Chi ti?t ??i chi?u, gi?y ph?p, ?? xu?t ?i?u ph?i v? A/B ? `nghien_cuu_tich_hop_tts_vietnamese.md`, m?c 8.
