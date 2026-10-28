# Nghiên cứu và phương án tích hợp TTS tiếng Việt

- **Ngày khảo sát:** 2026-10-26
- **Mã nhiệm vụ:** `nghien_cuu_tich_hop_tts_vietnamese_2026_10_26`
- **Phạm vi:** Clone mã nguồn tham chiếu, khảo sát tĩnh và đề xuất vị trí tích hợp. Không cài dependency, không chạy model, không gọi dịch vụ ngoài và không sửa mã runtime.
- **Trạng thái:** Đã clone và khảo sát; TTS trong dự án vẫn chưa được triển khai.

## 1. Tóm tắt quyết định

Đã clone [Vietnamese TTS Studio](https://github.com/sin0235/vietnamese-tts-studio) vào `03_ban_lam_viec/tham_chieu_vietnamese_tts_studio/` tại commit `20fe46fa5e66f074ea2f83f63e9edb820d4a9e13` (`2026-10-25T21:25:19+07:00`). Đây là bản tham khảo riêng, giữ lịch sử Git của upstream để tiện đối chiếu.

Đề xuất dùng repository này làm **tham khảo kỹ thuật cho tầng xử lý tiếng Việt và hàng đợi suy luận**, chưa đưa nguyên ứng dụng Flask vào SIN Creator Studio và chưa coi Gwen-TTS là provider production đã được duyệt. Hướng tích hợp phù hợp với kiến trúc hiện có là một TTS provider adapter riêng, chạy job bất đồng bộ, nhận lời narration đã duyệt và trả audio thành media asset trong đúng workspace/project. Việc triển khai cần bắt đầu sau khi khóa quyền sử dụng model/giọng, kiểm tra GPU và duyệt tiêu chí chất lượng thực tế.

## 2. Kết quả khảo sát repository tham chiếu

### Năng lực có thể học hỏi

- Dùng Gwen-TTS 0.6B qua `qwen-tts`, với audio tham chiếu và transcript khớp chính xác để điều kiện hóa giọng; có lựa chọn preset.
- Tách tiền xử lý prompt, quy tắc phát âm và chuẩn hóa từ vựng tiếng Việt; có nhánh `sea-g2p` và fallback giới hạn.
- Chia văn bản dài theo câu/dấu câu, sinh tuần tự từng đoạn, tái sử dụng prompt giọng, rồi chỉ crossfade tại biên có độ im lặng thấp.
- Có API đồng bộ/bất đồng bộ, SQLite queue, polling, giới hạn hàng đợi, lease, heartbeat và retry hữu hạn.
- Trả metadata cho audio như sample rate, thời lượng, thời gian inference, số chunk và ghi chú fallback.
- Tách ASR tùy chọn khỏi TTS. README cảnh báo xung đột phiên bản giữa stack Gwen và VibeVoice-ASR; ASR mặc định tắt.

### Giới hạn đáng lưu ý

- Gwen trong repository yêu cầu CUDA và được gắn vào `cuda:0`; không hỗ trợ TTS CPU theo triển khai hiện tại. README chưa đưa benchmark VRAM, độ trễ hay real-time factor có thể tái lập.
- Ứng dụng tham chiếu là Flask chạy cục bộ; README ghi rõ hiện không có authentication, tenant isolation, mã hóa dữ liệu, access control hoặc chính sách tự dọn audio tham chiếu và audio sinh.
- Studio web chủ yếu dùng preset; luồng tham chiếu tải lên tùy chỉnh được hỗ trợ qua API, chưa nối trọn vào UI Studio.
- Queue SQLite và lưu file cục bộ phù hợp làm mẫu đơn máy; không thể mặc định dùng trực tiếp như hạ tầng job/asset đa tenant của dự án.
- Chưa có lock file chung cho mọi môi trường; profile notebook dùng nhiều phiên bản dependency cụ thể, còn ASR có thể xung đột với môi trường TTS.
- README upstream ghi repository chưa có tệp giấy phép. Tệp WAV preset và các logo trong repo không có bằng chứng cấp quyền riêng kèm theo.

## 3. Đối chiếu với PRJ_069

Khảo sát tĩnh source hiện có cho thấy nền tảng media đã có các điểm nối cần thiết, nhưng chưa có engine TTS thật trong luồng tạo video:

- Planner tạo `narration` theo từng cảnh và ghi rõ narration là nội dung để người duyệt hoặc giọng đọc tùy chọn dùng; luồng planner không tự tạo audio.
- Content video run có `voice_asset_id`; runner hiện truy xuất audio asset theo đúng `workspace_id` và `project_id`, xác thực file/codec và yêu cầu thời lượng audio lệch không quá 0,5 giây so với thời lượng mục tiêu.
- Gói xuất ghi hash voice asset nhưng hiện đánh dấu nguồn `UPLOAD`; trường `speech_alignment` đang là `NOT_MEASURED` trong luồng đã khảo sát.
- Media Studio đã có chức năng dùng voice asset để trộn với nhạc nền và auto-ducking, đồng thời lưu audio dưới dạng media asset.
- Định hướng gốc của Founder đã yêu cầu adapter/capability registry cho `TTS`, `VOICE_CLONE`, `ASR`, `CAPTION_ALIGNMENT`, có bằng chứng thực trước khi đánh dấu provider supported; P4 yêu cầu narration, subtitle, media QC và job lifecycle thật.

Do đó, giá trị tích hợp của repo tham chiếu nằm ở provider/worker và xử lý ngôn ngữ, còn quyền sở hữu dữ liệu, tenant, job lifecycle, media asset, approval và QC phải tiếp tục nằm trong các lớp hiện hữu của PRJ_069.

## 4. Kiến trúc tích hợp đề xuất

1. **Đầu vào:** chỉ nhận narration của phiên bản kịch bản đã được duyệt, voice profile đã được cấp quyền và từ điển phát âm gắn với hồ sơ phong cách kênh.
2. **Điều phối:** tạo job TTS trong pipeline media hiện hữu; giữ concurrency suy luận nặng bằng `1` theo quy tắc dự án. Queue mẫu của upstream dùng làm tài liệu thiết kế, không thay queue/harness đang có.
3. **Provider:** triển khai một adapter tách biệt cho Gwen hoặc provider được Founder chọn. Adapter khai báo capability, health/readiness, model/version, phương thức tham chiếu, giới hạn đầu vào và tình trạng quyền sử dụng.
4. **Sinh audio:** tạo audio theo cảnh hoặc đoạn narration có ranh giới ổn định; giữ metadata từng đoạn để có thể sinh lại một phần khi nội dung đổi. Không tự giả định tổng thời lượng cuối sẽ khớp target.
5. **Đưa vào thư viện:** sau khi xác thực định dạng, duration, sample rate, peak và decode, nhập audio qua cơ chế MediaAsset hiện hữu trong đúng workspace/project. Lưu provider/model/version, voice profile, hash input/output, tham số, transcript/normalization version và quyền sử dụng cần thiết.
6. **Hậu kỳ và QC:** dùng audio asset hiện hữu cho timeline/mix; chạy loudness normalization/QC theo chuẩn TikTok của dự án (-14 LUFS ±1 LUFS), kiểm tra clipping, khoảng lặng, phát âm tên riêng/thuật ngữ, độ khớp lời với shot và căn phụ đề có đo lường.
7. **Phê duyệt:** mọi thay đổi narration, voice profile, quy tắc phát âm hoặc model phải làm mất hiệu lực asset/QC/approval phụ thuộc theo version graph; không thay giọng âm thầm khi provider lỗi.

Hợp đồng provider tối thiểu cần có: `submit`, `status`, `cancel`, `readiness`, mã job ổn định, trạng thái terminal rõ ràng, `audio artifact`, `duration`, `sample_rate`, `provider/model/version`, `voice reference ID`, `input hash`, lỗi có thể phân loại và usage/inference receipt. Tệp audio chỉ được lấy qua đường asset đã xác thực của hệ thống, không dùng URL công khai từ service tham chiếu.

## 5. Rào chắn trước khi chọn Gwen cho production

- **Giấy phép mã nguồn:** bản clone upstream hiện không có file LICENSE; không sao chép hoặc phân phối lại mã/asset của repo như thể đã được cấp quyền. Cần xin xác nhận chủ sở hữu hoặc chọn cách tích hợp đã được duyệt.
- **Giấy phép model:** model card Gwen trên Hugging Face khai báo MIT, nhưng điều đó không tự xác nhận quyền của dữ liệu huấn luyện, preset audio, mẫu giọng, mọi dependency hoặc mục đích thương mại cụ thể.
- **Nguồn dữ liệu:** model card tự mô tả Gwen được fine-tune từ Qwen3-TTS bằng khoảng 1.000 giờ audio tiếng Việt thu thập từ TikTok. Cần rà soát nguồn/quyền và yêu cầu pháp lý của tổ chức trước khi dùng cho nội dung thương mại.
- **Giọng tham chiếu:** chỉ dùng voice sample có chấp thuận và phạm vi quyền rõ ràng; không đưa preset WAV upstream vào voice library production khi chưa kiểm tra quyền đối với bản ghi và danh tính người nói.
- **Bảo mật đa tenant:** không expose Flask/Cloudflare tunnel của repo tham chiếu cho người dùng; không gửi audio tham chiếu hoặc narration qua service chưa có xác thực, authorization theo workspace và retention policy.
- **Hạ tầng:** xác minh GPU khả dụng và mức VRAM thực tế trước khi chọn self-host. Nếu không đáp ứng, so sánh provider/API khác theo capability, chi phí và quyền truy cập; không bật tự động fallback sang dịch vụ tính phí.

## 6. Tiêu chí nghiên cứu/đánh giá trước khi cấp task triển khai

- Bộ câu thử tiếng Việt có câu ngắn/dài, số/ngày/đơn vị, tên riêng, acronym và từ điển phát âm theo style BAHA.
- So sánh đầu ra mù giữa ít nhất hai lựa chọn giọng/provider được cấp quyền; chấm phát âm, tự nhiên, ổn định, cảm xúc, tính nhất quán qua nhiều cảnh và mức sửa tay.
- Đo trên phần cứng dự kiến: thời lượng sinh, real-time factor, VRAM peak, tỷ lệ lỗi, kích cỡ file và khả năng xử lý hàng đợi/retry/cancel.
- Kiểm tra WAV đầu ra bằng full decode, sample rate, duration, clipping/true peak và loudness; đo alignment lời đọc/phụ đề thay vì chỉ dùng thời lượng ước lượng từ số từ.
- Xác minh quyền model, code, voice reference và quy trình lưu/xóa audio; lập capability status `REAL_VERIFIED`, `REAL_UNVERIFIED` hoặc `BLOCKED` cùng bằng chứng.

## 7. Kết luận và bước tiếp theo

Kết quả hiện tại là **tích hợp nghiên cứu và tài liệu tham chiếu**, không phải tích hợp runtime. Upstream cung cấp mẫu tốt cho text normalization tiếng Việt, voice conditioning, chunking và tuần tự hóa GPU. Không nên đưa nguyên Flask app, SQLite queue hay preset voices vào production của PRJ_069. Trước khi giao task code, cần có quyết định provider/model, quyền sử dụng, môi trường GPU hoặc API được phép, tiêu chí nghiệm thu giọng và xác nhận mẫu voice profile. Sau đó có thể khóa hợp đồng adapter và giao triển khai riêng mà không sửa luồng video ngoài lease được cấp.

## Nguồn

- Repository đã clone: <https://github.com/sin0235/vietnamese-tts-studio>
- Snapshot cục bộ: `03_ban_lam_viec/tham_chieu_vietnamese_tts_studio/` — commit `20fe46fa5e66f074ea2f83f63e9edb820d4a9e13`.
- Model card Gwen-TTS: <https://huggingface.co/g-group-ai-lab/gwen-tts-0.6B>.
- Các giới hạn, endpoint và cấu hình ở trên được đối chiếu trực tiếp với `README.md`, `webapp/app.py`, `webapp/tts_service.py`, `webapp/job_queue.py`, `webapp/tts_worker.py` trong snapshot đã clone. Phần đối chiếu PRJ_069 dựa trên source trong `sin_content_api/src/modules/tao_video_noi_dung/`, `sin_content_api/src/modules/media_studio/` và tài liệu định hướng hiện có; chưa chạy runtime.


## 8. B? sung nghi?n c?u: VieNeu-TTS v3 Turbo l? l?a ch?n th? hai

### Ngu?n upstream ?? kh?o s?t

- [Repository ch?nh th?c VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS), README v? README ti?ng Vi?t: SDK, backend, voice cloning, streaming, benchmark, t?nh tr?ng v3/v4.
- [Model card VieNeu-TTS v3 Turbo](https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo): checkpoint, phi?n b?n SDK ???c m? t?, preset voices, quy?n s? d?ng v? gi?i h?n d? li?u.
- [Factory/API c?u h?nh mode](https://github.com/pnnbao97/VieNeu-TTS/blob/main/src/vieneu/factory.py): x?c nh?n `v3turbo` l? mode ri?ng, CPU ONNX/GPU PyTorch.

### K?t qu? kh?o s?t k? thu?t

- v3 Turbo tr? audio 48 kHz; h? tr? 23 preset theo model card v3.7.1, clone gi?ng b?ng clip 3?8 gi?y, streaming v? API HTTP t??ng th?ch OpenAI. README repository m?i h?n m? t? 25 preset. V? v?y c?n pin ??ng b?n SDK/checkpoint v? l?y roster t? SDK ?? c?i, kh?ng hard-code con s? ho?c t?n voice.
- CPU ch?y ONNX, kh?ng c?n PyTorch; GPU ch?y PyTorch. Upstream c?ng b? benchmark ri?ng: kho?ng RTF 0,55?0,62 cho CPU fp32 tr?n Core i5 th? h? 12 v? RTF 0,011?0,02 cho batch GPU tr?n RTX 3060. ??y l? s? ?o c?a upstream, kh?ng ph?i k?t qu? tr?n m?y PRJ_069; v?i nguy?n t?c concurrency TTS b?ng 1, l?i ?ch batch/stream nhi?u request c? th? kh?ng ??t nh? con s? ?a lu?ng.
- B?n v3 Turbo l? b?n m? m?i nh?t trong repo hi?n kh?o s?t; v4 ???c gi?i thi?u tr?n d?ch v? VieNeu v? kh?ng ph?i model m? ?? t? host. Ph?m vi l?a ch?n c?a PRJ_069 ? ??y ch? l? v3 Turbo.
- C?c tag c?m x?c ???c t?i li?u ghi l? th? nghi?m. Thu?c t?nh `style` b? b? qua ? v3 Turbo; phong c?ch ??c c?n ch?n qua voice/reference, v? v?y kh?ng ?nh x? tr??ng style hi?n c? sang tham s? gi?.
- API streaming kh?ng l?m m?t y?u c?u job lifecycle c?a PRJ_069: service adapter v?n c?n chuy?n output ho?n ch?nh v?o MediaAsset, ki?m tra decode/th?i l??ng/loudness v? gi? log/provenance.

### ??i chi?u gi?y ph?p v? d? li?u

- Model card/repository c?ng b? Apache-2.0 v? tuy?n b? gi?y ph?p bao ph? checkpoint c?ng preset assets; y?u c?u gi? th?ng b?o/license/attribution khi ph?n ph?i l?i.
- C?ng model card cho bi?t dataset 10k ti?ng Anh?Vi?t b? gated v? quy tr?nh thu th?p/ti?n x? l? n?i b? kh?ng c?ng khai. ??y l? th?ng tin publisher c?ng b?, ch?a audit ??c l?p.
- Quy?n preset voice kh?ng t? c?p quy?n cho m?u voice do ng??i d?ng t?i l?n; ph?i l?u h? s? ??ng ? v? ph?m vi s? d?ng cho custom reference voice.
- VieNeu c?n ph? thu?c th?nh ph?n tokenizer/phonemizer; gi? c?c th?ng b?o gi?y ph?p c?a t?ng th?nh ph?n theo manifest phi?n b?n tr??c khi ??ng g?i.

### Quy?t ??nh t?ch h?p t?i li?u

VieNeu v3 Turbo ???c th?m v?o danh s?ch ?ng vi?n ngang h?ng v?i Gwen-TTS, ch?a ch?n model m?c ??nh v? ch?a tuy?n b? provider n?o ?? ch?y th?t trong d? ?n. Cho m?i run ng??i d?ng/workflow ch?n m?t provider; job ch?p `provider_id`, model/checkpoint, SDK version v? voice id. Quy t?c hard gate: t?i ?a m?t model TTS ???c n?p v? t?i ?a m?t job TTS ch?y to?n h? th?ng (`concurrency=1`). Kh?ng ch?y Gwen v? VieNeu ??ng th?i, kh?ng hedge request, kh?ng t? fallback, kh?ng t?o job th? hai khi provider l?i. ??i provider ch? di?n ra sau khi job tr??c k?t th?c/h?y an to?n v? model ?? ???c gi?i ph?ng; l?n ch?y l?i ph?i th? hi?n r? l?a ch?n m?i.

T?ch worker/runtime theo provider n?n ???c ??nh gi? v? hai dependency stack kh?c nhau; tuy nhi?n v?n ph?i d?ng m?t lease/scheduler d?ng chung ?? b?o ??m kh?ng c? hai process TTS ho?t ??ng ??ng th?i. N?u kh?ng th? ch?ng minh ki?m so?t t?i model v? lease tr?n ??ng m?i tr??ng, provider th? hai v?n ? tr?ng th?i `REAL_UNVERIFIED`.

### Ti?u ch? A/B tr??c khi ch?n m?c ??nh

1. C?ng b? script TikTok BAHA: c?u ng?n/d?i, s?/ng?y/??n v?, acronym, t?n ri?ng v? t? Anh?Vi?t; d?ng c?ng normalization/t? ?i?n khi kh? thi.
2. C?ng voice reference ???c c?p quy?n; ri?ng preset th? ch?n gi?ng t??ng ???ng nh?t v? ghi r? kh?ng ho?n to?n ??ng nh?t.
3. Ch?m m? ?? ch?nh x?c ph?t ?m, t? nhi?n, ?n ??nh qua nhi?u shot, c?m x?c ph? h?p, m?c ch?nh tay; kh?ng ch?n ch? theo sample rate ho?c benchmark publisher.
4. ?o th?i gian n?p model, RTF, RAM/VRAM, ?? tr? ??u ti?n, k?ch c? WAV, full decode, duration, clipping/true peak v? loudness tr?n ph?n c?ng th?c t?.
5. Th? ??i provider khi queue r?ng, khi ?ang c? job, khi job l?i v? khi h?y; ch?ng minh kh?ng n?p/ch?y ??ng th?i, kh?ng t? fallback, kh?ng nh?n ??i usage.
6. Ch?t quy?n model, code, preset/custom voice, dependency, ?i?u kho?n audio ??u ra v? retention tr??c khi ??nh d?u capability `REAL_VERIFIED`.

### Cập nhật tích hợp CPU theo SDK gốc (2026-10-26)

- Repo chính thức hiện phát hành VieNeu SDK 3.8.3. v3 Turbo chạy CPU bằng ONNX Runtime, không cần PyTorch; checkpoint fp32 là cấu hình mặc định để giữ chất lượng. Int8 nhanh và tải nhẹ hơn nhưng upstream cảnh báo CPU cần VNNI để tránh méo tiếng. v3 Nano dành cho CPU yếu, chỉ 24 kHz và không hỗ trợ clone nên không chọn cho yêu cầu này.
- API clone chính thức là `infer(text, ref_audio=..., denoise=True, use_ref_codes=True)`. SDK tự cắt audio tham chiếu tối đa 8 giây và giới hạn mỗi chunk tối đa 256 ký tự; đầu ra v3 Turbo là waveform 48 kHz. Mã tích hợp lấy sample rate từ `model.sample_rate`.
- Giữ sampling mặc định của SDK (temperature 0.8, top-k 25, top-p 0.95, repetition penalty 1.2) và babble guard mặc định để giảm lặp từ/nói dôi cuối câu. Tag cảm xúc vẫn là thử nghiệm, chưa bật mặc định.
- Lỗi ONNX trong notebook phù hợp với cấu trúc cache từ `huggingface_hub` 1.32: các tệp trong snapshot có thể là symlink trỏ tới blob riêng, trong đó graph `.onnx` và file `.data` nằm ở các đường dẫn khác nhau. ONNX Runtime chặn external tensor khi file trọng số nằm ngoài thư mục model. Runtime dùng cache riêng, tắt shared blobs và symlink trước khi tải model để graph cùng `.data` nằm thật trong snapshot.
- Module hệ thống đặt `HF_HOME`/`HF_HUB_CACHE` theo `PRJ069_VIENU_HF_HOME`, bật `HF_HUB_DISABLE_SHARED_BLOBS=1` cùng `HF_HUB_DISABLE_SYMLINKS=1`, và buộc `device=cpu`, `backend=onnx`, `precision=fp32`. Docker cài SDK CPU và giữ cache trong named volume; cache cũ của người dùng không bị xóa.
- Các tham số trên là cấu hình upstream; chưa benchmark hoặc nghe A/B trên CPU PRJ_069. Cần kiểm tra latency, RAM, phát âm kịch bản BAHA, loudness và chất lượng clone trước khi gắn capability `REAL_VERIFIED`.

Nguồn: [VieNeu README PyPI](https://github.com/pnnbao97/VieNeu-TTS/blob/main/README_PYPI.md), [VieNeu CPU engine](https://github.com/pnnbao97/VieNeu-TTS/blob/main/src/vieneu/_v3_turbo_engine/onnx_runtime_lite.py), [PyPI vieneu 3.8.3](https://pypi.org/project/vieneu/3.8.3/), [Hugging Face tắt shared blobs](https://huggingface.co/docs/huggingface_hub/main/package_reference/environment_variables#hf-hub-disable-shared-blobs) và [tắt symlink](https://huggingface.co/docs/huggingface_hub/main/package_reference/environment_variables#hf-hub-disable-symlinks).
