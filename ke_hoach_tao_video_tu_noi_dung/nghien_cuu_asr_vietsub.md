# Nghiên cứu ASR và căn lời cho Vietsub

**Ngày rà soát:** 26/10/2026  
**Trạng thái:** Nghiên cứu tài liệu; chưa chạy model, chưa benchmark, chưa chọn model production.  
**Phạm vi:** Vietsub tiếng Việt cho narration trong `CONTENT_VIDEO_RENDER`. MVP giả định lời đọc đích đã là tiếng Việt; dịch lời nói từ ngôn ngữ khác chưa thuộc phạm vi.

## Kết luận điều hành

Không nên chọn một ASR duy nhất cho mọi đầu vào. Pipeline hiện có kịch bản narration đã duyệt và track giọng đọc có thể do người dùng tải lên. Với audio được tạo từ kịch bản đã duyệt, phương án căn lời (forced alignment) có thể giữ đúng chính tả script và sinh mốc thời gian, nhưng chỉ khi lời đọc thực tế khớp nội dung. Với audio không có transcript đáng tin, cần ASR rồi đưa transcript cho người duyệt. Căn lời không chứng minh transcript đúng; ASR cũng không thay thế kiểm tra nội dung.

Đề xuất cho vòng benchmark sau khi có quyền dữ liệu:

1. **Audio từ narration có script:** đưa Montreal Forced Aligner với acoustic model tiếng Việt vào benchmark căn lời. Đối soát ASR hoặc con người để phát hiện từ bị lược/thêm; cue không đạt độ tin cậy chuyển `REVIEW_REQUIRED`.
2. **Audio tải lên không có script:** dùng OpenAI Whisper multilingual `medium` làm baseline ASR; thêm VibeVoice-ASR làm đối chứng nếu môi trường GPU/RAM và dependency cho phép.
3. **Không có voice asset:** không tạo cue tự động, trả `NO_AUDIO_FOR_VIETSUB`.

Đây là thứ tự benchmark đề xuất, không phải quyết định dùng trong production. Trạng thái ASR của hệ thống vẫn `UNVERIFIED`.

## So sánh ứng viên

| Ứng viên | Phù hợp với | Căn cứ từ nguồn chính thức | Ràng buộc và điểm chưa rõ | Vai trò đề xuất |
|---|---|---|---|---|
| OpenAI Whisper multilingual | Audio có lời nhưng chưa có transcript; nhận dạng tiếng Việt | Mã nguồn chính thức có mã ngôn ngữ `vi`; README nêu mô hình multilingual xử lý lời nói không phải tiếng Anh và giấy phép MIT cho mã cùng trọng số. | Cần đo WER tiếng Việt, thuật ngữ BAHA và timing trên corpus dự án. Có PyTorch, tiktoken và phụ thuộc FFmpeg; không tự giả định tích hợp nhẹ. Không dùng kết quả ASR làm chữ đã duyệt khi mismatch. | Baseline ASR cho audio tải lên hoặc transcript không chắc chắn. |
| Microsoft VibeVoice-ASR-HF | Audio dài, nhiều người nói, diarization và timestamp theo đoạn | Model card hiện ghi 51 ngôn ngữ, giấy phép MIT, 8B tham số BF16, timestamped transcription; Transformers từ phiên bản 5.3.0. Technical report mô tả xử lý dài tối đa 60 phút. | Model card hiện không nêu tên tiếng Việt trong nội dung văn bản được rà soát; kiểm tra phân phối ngôn ngữ và benchmark tiếng Việt trước khi kết luận. Kích thước model tải xuống khoảng 16.7 GB; footprint thực tế cao hơn và cần đo. Bản tham khảo cục bộ yêu cầu `transformers>=5.3.0`, xung đột profile TTS `transformers==4.57.3`; code tham khảo bật `trust_remote_code=True`. Cần pin revision, rà soát mã và cách ly tiến trình. | Đối chứng ASR nếu tài nguyên cho phép; chưa chọn làm mặc định. |
| Montreal Forced Aligner với `vietnamese_mfa` | Audio có transcript tiếng Việt đáng tin, đặc biệt narration đã sinh từ script | Model card của Montreal Corpus Tools ghi rõ mục đích là căn lời tiếng Việt, license CC BY 4.0; tài liệu MFA mô tả forced alignment dùng transcript và mô hình ngữ âm để tạo mốc thời gian. | Đây không phải ASR và không kiểm chứng từ có thực sự được nói. Model học trên lời đọc ít nhiễu; tài liệu ghi không có metric đánh giá độc lập cho model này. Dictionary có giới hạn từ vựng; tên riêng/thuật ngữ cần kiểm tra. | Benchmark cho track TTS/script-backed; chỉ chấp nhận khi đối soát lời đọc và timing. |

Nguồn: [Whisper README](https://github.com/openai/whisper/blob/main/README.md), [Whisper tokenizer](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py), [VibeVoice-ASR model card](https://huggingface.co/microsoft/VibeVoice-ASR-HF), [VibeVoice-ASR technical report](https://arxiv.org/abs/2601.18184), [Vietnamese MFA model card](https://huggingface.co/MontrealCorpusTools/vietnamese_mfa), [MFA Vietnamese model documentation](https://mfa-models.readthedocs.io/en/latest/acoustic/Vietnamese/Vietnamese%20MFA%20acoustic%20model%20v3_0_0.html).

## Luồng đề xuất theo loại audio

| Đầu vào | Xử lý | Điều kiện hiển thị Vietsub |
|---|---|---|
| Có audio giọng đọc và script đã duyệt | Chạy forced alignment bằng script; so transcript ASR hoặc đối soát con người ở mức cần thiết để phát hiện khác biệt. | Chỉ xác nhận script làm chữ hiển thị sau khi mismatch đã được loại trừ; alignment một mình không đủ để chứng minh nội dung. |
| Có audio nhưng không có script đáng tin | Chạy ASR; lưu nguyên transcript nhận dạng; cho phép sửa cue; không tự viết lại bằng LLM. | Người duyệt xác nhận transcript trước khi đánh dấu Vietsub hoàn tất. |
| Không có `voice_asset_id` | Không căn thời gian từ narration text và không chia cue theo độ dài câu. | Trả `NO_AUDIO_FOR_VIETSUB`; giữ luồng caption thủ công riêng. |
| Có lời nói không phải tiếng Việt | Không dịch trong MVP. | Chặn hoặc yêu cầu quy trình dịch riêng được duyệt. |

Hợp đồng provenance nên phân biệt rõ `ASR`, `FORCED_ALIGNMENT`, `ASR_SCRIPT_CONFIRMED` và `MANUAL`. Chỉ dùng `ASR_SCRIPT_CONFIRMED` khi transcript nhận dạng thực sự khớp script sau kiểm tra; không gán trạng thái này chỉ vì forced aligner tạo được timestamp.

## Thiết kế benchmark đề xuất, chưa thực hiện

- Ít nhất 20 đoạn audio, tổng ít nhất 20 phút, tối thiểu 3 chất giọng và gồm audio sạch, nhiễu nhẹ, tên riêng/thuật ngữ BAHA.
- Chỉ dùng audio có văn bản xác nhận quyền sử dụng; transcript chuẩn và ranh giới câu do người rà soát xác nhận.
- So sánh cùng một tập cho ASR transcript, forced alignment script-backed, mốc thời gian đầu/cuối, tỷ lệ mismatch cần người duyệt, tốc độ xử lý, RAM/VRAM, lỗi và khả năng chạy trong môi trường cách ly.
- Chuẩn hóa Unicode, chữ hoa/thường, dấu câu và cách viết thuật ngữ bằng cùng một quy tắc cho transcript tham chiếu và kết quả; không biến đổi dấu tiếng Việt để làm đẹp WER.
- Mục tiêu ban đầu để Founder duyệt: WER không quá 10% trên narration sạch, thuật ngữ ít nhất 95%, median sai lệch biên cue không quá 300 ms, P95 không quá 800 ms. Chưa có dữ liệu chứng minh các ngưỡng này phù hợp với nội dung BAHA.
- Benchmark thật, tải model, cấp GPU và lưu audio chỉ bắt đầu sau khi Founder duyệt nhà cung cấp/model, quyền corpus, ngân sách, vùng lưu trữ và lease tài nguyên concurrency 1.

## Kết luận và quyết định cần Founder

Ứng viên ưu tiên không phải một model duy nhất: benchmark MFA cho narration có transcript; Whisper multilingual làm baseline khi không có transcript; VibeVoice-ASR làm đối chứng có điều kiện tài nguyên. Sau benchmark mới chọn một cấu hình production hoặc giữ `UNVERIFIED`.

Founder cần quyết định quyền dùng corpus, loại audio được phép xử lý, ngân sách/tài nguyên, rubric benchmark và việc có cho phép tải model mã nguồn mở vào môi trường cách ly hay không. Chưa có quyết định nào trong tài liệu này cấp quyền chạy model hoặc sửa runtime.
