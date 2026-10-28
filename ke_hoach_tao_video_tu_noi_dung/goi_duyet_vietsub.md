# Gói quyết định Founder: Vietsub tự động

**Trạng thái:** Tài liệu tổng hợp để Founder ra quyết định một lần; đây chưa phải phê duyệt kỹ thuật, lease runtime hoặc duyệt style cuối.  
**Mục tiêu MVP:** Vietsub tiếng Việt theo lời đọc thực tế trong `CONTENT_VIDEO_RENDER`, có thể xem/sửa, gắn vào timeline, render MP4 và xuất SRT/provenance.

## Phạm vi đề xuất

- Lời đọc đích đã là tiếng Việt; MVP không tự dịch audio ngoại ngữ.
- Caption theo câu/cụm có timestamp; chưa làm karaoke từng từ.
- Lấy `voice_track` gắn với `run.voice_asset_id` làm audio chuẩn. Không có voice asset thì báo `NO_AUDIO_FOR_VIETSUB`, không ước lượng thời gian theo số ký tự.
- Giữ nguyên luồng caption thủ công của Media Studio.
- Sai khác giữa audio và script phải hiện `REVIEW_REQUIRED`; không để LLM tự sửa lời đọc.

## Các quyết định đề nghị Founder ghi nhận

| Mã | Quyết định | Đề xuất điều phối | Nếu chưa quyết định |
|---|---|---|---|
| D1 | Phạm vi Vietsub | Chấp thuận phụ đề tiếng Việt theo lời đọc đã có; dịch ngoại ngữ nằm ngoài MVP. | Không xử lý audio khác ngôn ngữ như thể đã có Vietsub. |
| D2 | Hành vi khi không có audio | Chặn tự động với `NO_AUDIO_FOR_VIETSUB`; caption thủ công vẫn dùng được. | Không thể căn timing; không dùng narration text làm proxy cho lời nói. |
| D3 | Quy trình căn lời | Benchmark forced alignment MFA cho audio gắn script; ASR cho audio không có transcript. | Không chạy benchmark hoặc tự chọn model production. |
| D4 | Ứng viên ASR | Whisper multilingual `medium` làm baseline; VibeVoice-ASR-HF làm đối chứng nếu tài nguyên và dependency phù hợp. | Giữ ASR `UNVERIFIED`; không gọi API trả phí hoặc tải model. |
| D5 | Font | Be Vietnam Pro SemiBold 600 làm candidate trình xem, chưa khóa. | Không nhúng font vào production hoặc fallback âm thầm. |
| D6 | Style | So sánh A: chữ sáng, viền tối mảnh; B: chữ sáng trên hộp tối bán trong suốt. Điều phối đề nghị B cho pilot nếu không che chủ thể. | Chưa phát hành style default cho workspace. |
| D7 | Corpus và ngân sách | Cấp audio có quyền sử dụng, transcript chuẩn, nơi lưu, thời hạn lưu, ngân sách/GPU cho benchmark. | Không thu thập, tải lên hoặc chạy benchmark. |
| D8 | Rubric | Duyệt/điều chỉnh mục tiêu WER ≤10%, thuật ngữ ≥95%, median timing error ≤300 ms, P95 ≤800 ms cùng ngưỡng tài nguyên. | Không tuyên bố ASR đã xác minh. |
| D9 | G1 và lease | Duyệt prototype/style board G1 trước; lease runtime là quyết định riêng sau khi contract, owner file, hash và rollback hoàn tất. | Không mở task ghi runtime. |

## Phương án nghiên cứu và rủi ro

- **Whisper multilingual:** mã/tokenizer chính thức có tiếng Việt; MIT; cần benchmark thực tế. Không suy ra chất lượng từ danh sách ngôn ngữ.
- **VibeVoice-ASR-HF:** model card hiện nêu 51 ngôn ngữ, MIT, 8B BF16, timestamp theo người nói; yêu cầu Transformers từ 5.3.0. Nội dung văn bản model card được rà soát chưa liệt kê cụ thể tiếng Việt. Model khoảng 16.7 GB tải xuống và có xung đột với profile TTS tham khảo 4.57.3.
- **Vietnamese MFA:** model căn lời tiếng Việt, không phải ASR; chỉ đáng thử khi transcript đúng. Tài liệu cảnh báo model học trên lời đọc ít nhiễu và chưa có kết quả đánh giá độc lập đủ dùng cho BAHA.
- **Renderer:** hiện cố định Arial/màu vàng/hộp đen; binary FFmpeg chưa xác minh. Khóa render `threading.Lock()` không đảm bảo concurrency = 1 giữa nhiều process.
- **Hợp đồng:** năm model Timeline bị khai báo trùng tên; khối sau đang được consumer hiện hữu dùng. `StyleSnapshot` có hash trong approval receipt, không mở rộng trực tiếp.
- **Working tree:** các tệp tracked `migrations/runner.py`, `models/entities.py`, `tao_video_noi_dung/contracts.py`, `tao_video_noi_dung/service.py`, `tests/test_content_video_pipeline.py` và tài liệu nghiên cứu đang có thay đổi; `tao_video_noi_dung/tts_provider.py` đang untracked. Chưa xác minh owner; không giao task chạm các tệp này đến khi AGY đối chiếu lại.

## Cổng tiếp theo

Sau quyết định D1–D9, AGY hoàn tất hợp đồng Vietsub phiên bản hóa, bản đồ consumer, owner/hash từng file, môi trường thử, lease resource concurrency 1 và phương án rollback. Việc đó mới cho phép AGY phát task card runtime. Chỉ Codex sửa file được giao trong lease; file shared và tích hợp do Integrator xử lý qua proposal.

## Nguồn chính

- [Whisper README](https://github.com/openai/whisper/blob/main/README.md) và [danh sách ngôn ngữ chính thức](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py).
- [VibeVoice-ASR model card](https://huggingface.co/microsoft/VibeVoice-ASR-HF) và [technical report](https://arxiv.org/abs/2601.18184).
- [Vietnamese MFA model card](https://huggingface.co/MontrealCorpusTools/vietnamese_mfa) và [tài liệu model tiếng Việt](https://mfa-models.readthedocs.io/en/latest/acoustic/Vietnamese/Vietnamese%20MFA%20acoustic%20model%20v3_0_0.html).
- [Be Vietnam Pro](https://fonts.google.com/specimen/Be+Vietnam+Pro) và [metadata/license](https://github.com/google/fonts/tree/main/ofl/bevietnampro).
