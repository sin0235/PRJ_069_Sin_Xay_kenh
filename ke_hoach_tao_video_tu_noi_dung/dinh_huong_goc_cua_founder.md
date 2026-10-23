# BAHA GROUP CREATOR STUDIO
## MASTER TRANSFORMATION SPEC — Nền tảng sản xuất nội dung giải thích công nghệ và chuyển đổi khách hàng bằng AI

**Phiên bản:** 1.0 — 23/10/2026  
**Mục đích:** Tài liệu đặc tả sản phẩm kiêm chỉ thị thực thi cho AI coding agent/Antigravity chuyển đổi **toàn diện dự án BAHA Group Creator Studio đang tồn tại**.  
**Phạm vi:** Product strategy, UX/UI, dữ liệu, backend, video production, tích hợp AI qua API, quy trình nhân sự, xuất bản, đo lường và nghiệm thu.  
**Nguyên tắc căn bản:** Tài liệu này mô tả **trạng thái mong muốn (TO-BE)**. Mọi nhận định về những gì mã nguồn hiện tại (AS-IS) đã có/chưa có đều **phải do agent kiểm tra thực tế**. Không coi kế hoạch, README, mockup hoặc báo cáo cũ là bằng chứng chức năng đang chạy.

---

# 0. NHIỆM VỤ BẮT BUỘC DÀNH CHO AGENT

Bạn là **Lead Product Architect + Full-stack Engineer + AI Media Pipeline Engineer + QA Lead** được giao tái cấu trúc sản phẩm BAHA Group Creator Studio hiện có thành một **Technology Explainer & AI Solutions Media Operating System**. Đây **không phải** nhiệm vụ chỉ đổi tên ứng dụng, thêm vài trang, thay màu hoặc ghép một demo AI giả lập.

Bạn phải:

1. **Khảo sát source thực**: cấu trúc repo, routes, database, backend, workers, thiết kế, luồng đang chạy, hạ tầng deploy, tích hợp, key/config (không làm lộ bí mật), test, migration và tính năng đang được người dùng sử dụng.
2. **Lập bản đồ AS-IS → TO-BE** và ma trận KEEP / REFACTOR / EXTEND / DEPRECATE. Giữ các chức năng có ích, không làm mất dữ liệu, quyền truy cập, kết nối kênh hoặc lịch sử nội dung.
3. **Thiết kế lại hành trình end-to-end** từ phát hiện chủ đề → nghiên cứu → xác minh kiến thức → kịch bản → storyboard → dựng video tự động → hậu kỳ có thể chỉnh sửa → QC → phê duyệt → xuất bản → phân tích → tạo khách hàng tiềm năng.
4. **Triển khai vào hệ thống đang có**, ưu tiên tái sử dụng mã nguồn, thư viện hoặc dịch vụ hiện hữu khi thực sự phù hợp. Không viết lại toàn bộ chỉ vì dễ làm hơn.
5. **Kiểm định kỹ thuật và nghiệp vụ theo từng phase**. Tính năng chưa có kiểm định chạy thật phải ghi đúng trạng thái, không được báo DONE chỉ dựa vào UI, README, unit test mock hoặc một API giả định.
6. **Không sử dụng GPU cục bộ như điều kiện bắt buộc**. Ưu tiên cloud API cho AI generation, CPU/worker cho ghép dựng, encoder hoặc remote rendering tùy cấu hình thực tế.
7. **Không triển khai sản xuất lên production hoặc chạy đăng bài thật khi chưa có quyền phê duyệt**. Hoàn thiện trên nhánh/môi trường thử nghiệm; bàn giao bằng chứng trước khi phát hành.

## 0.1. Các nguyên tắc không thể thương lượng

- Không được khẳng định tích hợp khả dụng nếu chưa chứng minh API, quyền truy cập tài khoản, hạn mức, điều kiện sử dụng và thử nghiệm thành công.
- Google AI Pro/Flow/Flow Music, Gemini, Veo, Lyria, TikTok Studio/Suite **không mặc nhiên đồng nghĩa với API thương mại**. Phải kiểm tra từng surface sản phẩm, account entitlement và đường tích hợp cụ thể; thiết kế adapter có thể thay provider.
- Không gọi một demo có dữ liệu mock là tính năng production. Gắn nhãn rõ `REAL_VERIFIED`, `REAL_UNVERIFIED`, `MOCK`, `PLANNED`, `BLOCKED` trong báo cáo và bảng tích hợp nội bộ.
- Không dùng ảnh stock ngẫu nhiên, đoạn AI sinh không đúng khái niệm hoặc lời thuyết minh sai sự thật chỉ để video trông đã hoàn thiện.
- Mọi kết luận kỹ thuật quan trọng phải có bằng chứng kiểm tra mã nguồn, log, ảnh chụp, bài test hoặc file đầu ra thực tế.
- Bảo toàn những luồng sản xuất video, quản lý kênh, lịch nội dung, phân quyền, biên tập timeline và media asset đang hoạt động nếu kiểm toán xác nhận chúng tồn tại.

---

# 1. TẦM NHÌN SẢN PHẨM VÀ CHIẾN LƯỢC NỘI DUNG

## 1.1. Sứ mệnh

Biến BAHA Group Creator Studio từ nền tảng hỗ trợ quản lý/xây kênh và sản xuất nội dung nói chung thành **hệ điều hành truyền thông công nghệ có khả năng tự động hóa cao**, tập trung sản xuất video **giải thích kiến thức công nghệ dễ hiểu**, chuyển từ kiến thức sang **ứng dụng thực tiễn**, rồi kết nối nhu cầu của người xem với năng lực cung cấp giải pháp AI của BAHA Group.

**Thông điệp thương hiệu chuẩn trong video:**

> **BAHA Group — Cung cấp giải pháp AI toàn diện.**

Hướng truyền thông: **Knowledge First → Real Application → Trusted Expertise → Qualified Lead**.

Người xem không đến để xem quảng cáo BAHA; họ đến để hiểu công nghệ. Sự hiện diện của BAHA phải nhất quán, có chuyên môn, có giá trị và tinh tế.

## 1.2. Các mục tiêu kinh doanh

- Xây dựng nhận biết và độ tin cậy cho BAHA trong mảng công nghệ/AI.
- Tiếp cận doanh nghiệp có bài toán AI thực tế, đồng thời duy trì lượng người xem đại chúng qua kiến thức dễ hiểu.
- Sản xuất nội dung đều đặn mà chi phí biên trên mỗi video giảm dần nhờ tái sử dụng dữ liệu, template, asset và năng lực tự động hóa.
- Chuyển đổi nội dung thành tương tác có giá trị: truy cập landing page, yêu cầu tư vấn, tải tài liệu, đăng ký demo, liên hệ trực tiếp.
- Đo lường xuyên suốt từ **chủ đề → video → phân phối → tương tác → lead**; không lấy views làm KPI duy nhất.

## 1.3. Đối tượng người xem

1. **Đại chúng quan tâm công nghệ:** cần giải thích đơn giản, ví dụ trực quan; ưu tiên chia sẻ/lưu lại.
2. **Quản lý/Chủ doanh nghiệp:** quan tâm công nghệ giải quyết vấn đề gì, quy trình, thời gian và hiệu quả có thể chứng minh.
3. **Trưởng bộ phận/Người làm sản phẩm và vận hành:** cần quy trình triển khai, tích hợp, demo và giới hạn giải pháp.
4. **Nhân sự kỹ thuật:** quan tâm kiến trúc, API, so sánh phương pháp, các trường hợp sử dụng thực tế.

Nội dung phải được gắn mục tiêu đối tượng và giai đoạn nhận thức; không sử dụng cùng một lời kêu gọi hành động cho tất cả chủ đề.

## 1.4. Cấu trúc các trụ cột nội dung

Tỷ trọng ban đầu **có thể cấu hình**, giá trị mặc định cho giai đoạn thử nghiệm:

| Pillar | Tỷ trọng | Bản chất | Ví dụ |
|---|---:|---|---|
| Tech Explained | 40% | Giải thích công nghệ từ bản chất, dễ hiểu và chính xác | AI Agent là gì, RAG khác Fine-tuning, MCP hoạt động ra sao, API khác SDK |
| AI in Practice | 40% | Ứng dụng theo quy trình và bài toán thực tế | Tự động phân loại email, phân tích tài liệu, chăm sóc khách hàng, trích xuất hóa đơn |
| BAHA Lab / Proof | 20% | Demo xác minh được, case study có sự cho phép và năng lực thực thi | Demo workflow BAHA, bản thiết kế kiến trúc, before/after có dữ liệu |

**Series/Chương trình gợi ý:** `Công nghệ trong 60 giây`, `AI ứng dụng vào doanh nghiệp`, `BAHA Lab`, `Giải mã công nghệ mới`. Tên series phải chỉnh được trong UI; không hardcode tên đề xuất thành taxonomy cố định.

## 1.5. Giọng điệu và đạo đức nội dung

- Tự tin, hiểu biết, súc tích, dễ hiểu; không thổi phồng, không khoe thuật ngữ.
- Hook hấp dẫn nhưng không đánh lừa, không hứa kết quả không kiểm chứng.
- Phân biệt sự kiện thực tế, dự đoán, giả định, số liệu, ví dụ mô phỏng và demo trực tiếp.
- Không gán tên khách hàng hoặc thành tích cho BAHA khi chưa có dữ liệu chứng minh và quyền công bố.
- Phần giới thiệu BAHA đặt chủ yếu ở cuối; cho phép biến thể ngắn hơn hoặc kết hợp watermark tinh tế nếu kiểm thử cho thấy hiệu quả.

---

# 2. FORMAT NỘI DUNG VÀ NHẬN DIỆN VIDEO

## 2.1. Định dạng xuất mặc định

- **Short video:** ưu tiên 9:16, 1080×1920, thời lượng mục tiêu 45–60 giây (configurable, không hardcode).
- **Long form:** 16:9, thời lượng theo kịch bản, cho YouTube và kênh sở hữu.
- **Biến thể:** 1:1, 4:5 và các cấu hình riêng của kênh khi thực sự có nhu cầu.
- **Ngôn ngữ:** tiếng Việt mặc định, subtitle tiếng Việt đầy đủ dấu; hỗ trợ từ điển phát âm thuật ngữ AI tiếng Anh. Có thể thêm tiếng Anh về sau.

## 2.2. Storytelling template cho video giải thích 60 giây

| Mốc gợi ý | Mục đích | Yêu cầu sản xuất |
|---|---|---|
| 0–3 giây | Hook | Câu hỏi/vấn đề cụ thể, visual mở đầu mạnh, không logo dài |
| 3–15 giây | Đặt khái niệm | Giải thích bằng ngôn ngữ đơn giản, đối chiếu trước/sau |
| 15–43 giây | Giải thích + minh họa | Motion diagram, UI demo, screen recording, B-roll phù hợp |
| 43–55 giây | Kết luận có giá trị | Khẳng định đúng, nêu ứng dụng/giới hạn/cách hiểu |
| 55–60 giây | Brand outro | Logo, thông điệp BAHA, CTA phù hợp, âm thanh nhận diện |

Các mốc là template khởi tạo, không phải quy tắc cứng. Cho phép kịch bản không cần CTA bán hàng và thay đổi nhịp dựng tùy chủ đề.

## 2.3. Ba chế độ outro bắt buộc

- **O1 / Brand only:** Logo BAHA + “Cung cấp giải pháp AI toàn diện”, thời lượng ngắn, không ép hành động.
- **O2 / Follow for knowledge:** Brand + CTA theo dõi series hoặc lưu video.
- **O3 / Business solution:** Brand + lời mời khám phá demo/đăng ký tư vấn khi nội dung có quan hệ trực tiếp đến giải pháp.

Outro phải là một **Brand Template** có phiên bản, cho phép thay cảnh nền, âm nhạc, voice tag, motion, logo, CTA, URL và safe area. Sử dụng A/B test về giữ chân người xem và chất lượng lead; không để outro làm hỏng nội dung chính.

## 2.4. Hệ sinh thái asset video

Cảnh có thể dùng một hoặc nhiều loại nguồn: đồ họa dựng từ dữ liệu, sơ đồ động, UI/product demo, screen recording, video quay thật, footage có quyền sử dụng, hình AI, video AI, infographic và subtitle động. **Ưu tiên minh họa đúng khái niệm hơn là cảnh AI đẹp nhưng sai nội dung.**

---

# 3. PHẠM VI CHUYỂN ĐỔI TOÀN DIỆN (TO-BE MODULES)

Toàn bộ hệ thống phải vận hành như **một sản phẩm thống nhất**. Agent có quyền đề xuất hợp nhất menu/trang, mô hình dữ liệu, state machine và component nhằm bỏ sự trùng lặp; nhưng phải có kiểm tra hồi quy cho luồng cũ.

## 3.1. Executive Dashboard

Một dashboard trả lời: hôm nay cần làm gì, nội dung nào bị tắc, video nào được xuất bản, nội dung nào hiệu quả, lead nào cần theo dõi, pipeline nào tốn chi phí. Phân biệt KPI có dữ liệu thật và KPI chưa tích hợp; không đưa dashboard số mẫu giả vào production.

**Nhóm thông tin:** content throughput, time-to-publish, pending approval, render failure rate, chi phí theo video/provider, performance theo pillar/series, hiệu quả CTA, qualified leads, workload nhân sự.

## 3.2. Strategy & Series Planner

Tạo chương trình nội dung theo: audience, pillar, pain point, kênh, tần suất, độ khó, format, mục tiêu, CTA, brand kit, người phụ trách và KPI. Có calendar, backlog, chiến dịch và trạng thái từng tập. Cho phép thay đổi tỷ trọng 40/40/20, không hardcode.

## 3.3. Topic Radar & Research Desk

- Gợi ý chủ đề từ nguồn xác định (feed chính thức, RSS, dữ liệu tìm kiếm/trend được phép, đầu vào thủ công, kênh đã kết nối nếu API hỗ trợ).
- Gắn `source_url`, thời điểm truy cập, tên nguồn, tác giả/đơn vị phát hành, độ mới và tình trạng kiểm chứng.
- Bộ lọc `evergreen / trending / customer problem / product proof / news`.
- Điểm ưu tiên chủ đề có giải thích được theo audience-fit, business relevance, tính mới, bằng chứng và mức độ cạnh tranh; điểm AI chỉ là gợi ý.
- Không tự suy diễn rằng TikTok Studio cung cấp trend API hoặc endpoint xuất bản nếu chưa kiểm tra quyền và tài liệu thực tế.

## 3.4. Knowledge & Fact-Checking Engine

Mỗi video có **Research Pack** gồm:

- Câu hỏi chính và luận điểm cốt lõi.
- Các claim tách biệt, mỗi claim có tài liệu chứng minh và link/source snapshot nếu được phép.
- Mức xác thực: `VERIFIED`, `NEEDS_REVIEW`, `OPINION`, `ILLUSTRATIVE`, `UNSUPPORTED`.
- Điều kiện/ngoại lệ, thuật ngữ cần giải thích, các phát biểu phải tránh.
- Ngày cập nhật cuối cùng. Chủ đề công nghệ thay đổi nhanh cần kiểm tra lại trước khi xuất bản.

**Gate:** Không được tự động đưa claim `UNSUPPORTED` hoặc `NEEDS_REVIEW` thành thông tin khẳng định trong lời thoại final. Có thể chuyển thành câu hỏi hoặc loại bỏ.

## 3.5. Script Studio

Input: content brief + research pack + audience + duration + brand voice + CTA type.  
Output versioned: hook, narration, on-screen text, scene beats, visual hints, pronunciation dictionary, intended emotion/pacing, source citation map.

Yêu cầu: generate nhiều phương án hook; biên tập thủ công, so sánh bản sửa; khóa phiên bản được phê duyệt; chống thay đổi script ngầm khi đã dựng xong; mọi chỉnh sửa tạo revision có thể so sánh và rollback.

## 3.6. Visual Storyboard & Scene Planner

Mỗi kịch bản được tách thành scene theo ID ổn định, thứ tự, thời lượng, lời thoại, visual goal, source media, loại chuyển cảnh, overlay, subtitles, audio cue và trạng thái duyệt. Hệ thống cho phép scene `DIAGRAM`, `SCREEN_RECORDING`, `REAL_FOOTAGE`, `STOCK_BROLL`, `AI_IMAGE`, `AI_VIDEO`, `TEXT_MOTION`, `BRAND_OUTRO`.

**Tính năng cần có:** xem storyboard dạng cards/filmstrip, preview từng cảnh, kéo đổi thứ tự, thay nguồn cảnh, khóa asset, đánh dấu cần quay màn hình, xuất JSON storyboard; thay scene không bắt buộc render lại toàn bộ asset nguồn.

## 3.7. Production Studio — dựng video thực sự, không chỉ text-to-video

Đây là trọng tâm kỹ thuật:

- Timeline đa track cho video, image, voice, music, SFX, caption, text, logo/overlays và chuyển cảnh.
- Trim/split/cut, crop/reframe, speed, zoom/pan, pan-and-scan, transition, keyframe tối thiểu, hiệu ứng intro/outro, text animation, template scene.
- Auto assembly từ storyboard, auto scene timing theo speech, căn phụ đề theo timestamp, audio ducking, normalize loudness với preset kiểm thử được, xuất MP4 + subtitle + editable project.
- Waveform/preview (hoặc biểu diễn khả thi theo stack), chỉnh sửa từng cảnh, thay voice, sửa text, đổi template, cập nhật montage theo version.
- Kết hợp screen recording / video upload từ người dùng và tư liệu AI, không giới hạn vào AI sinh video từ text/ảnh.
- Render/export với FFmpeg hoặc engine thực tế tương thích stack đã kiểm toán; CPU worker hoặc dịch vụ render remote; không phụ thuộc GPU cục bộ.
- State rõ: `DRAFT → ASSEMBLING → PREVIEW_READY → QC_REQUIRED → APPROVED → RENDERING → READY_FOR_PUBLISH` và các trạng thái `FAILED / CANCELLED / REVISION_REQUESTED`.

**Hai chế độ vận hành:**
1. `AUTO`: tự nghiên cứu có nguồn, đề xuất script, dựng rough cut, chạy QC, đợi duyệt.
2. `HYBRID/EDITOR`: nhân sự chủ động quay, upload footage, chỉnh timeline, giao việc, duyệt và xuất bản.

## 3.8. AI Provider Hub (API-first, cloud-first)

Tạo adapter interface và **Capability Registry** cho `LLM`, `SEARCH`, `IMAGE`, `VIDEO`, `MUSIC`, `TTS`, `VOICE_CLONE`, `ASR`, `CAPTION_ALIGNMENT`, `STOCK_MEDIA`, `PUBLISHING`.

Mỗi provider cần dữ liệu: capability được chứng minh, auth, request/response sample đã scrub, quota, region, SLA (nếu có), chi phí, retry, cancellation, rate limit, artifact retention, policy/license, health check, trạng thái và fallback.

- Ưu tiên model API/cloud để tránh sử dụng GPU nội bộ.
- Có thể khảo sát Gemini/Veo/Google Flow/Flow Music/Lyria, OpenRouter và model/service khác phù hợp. **Không mặc định** cùng một subscription có quyền gọi mọi API.
- Nếu một dịch vụ chỉ có giao diện web, đánh giá một luồng điều khiển giao diện được phép và có xác nhận của người dùng **riêng với tích hợp API**; phải đo độ ổn định, khả năng retry và giới hạn. Nếu không đáng tin cậy, báo `BLOCKED` và đề xuất fallback.
- Model TTS tiếng Việt nhẹ (bao gồm VieNeu-TTS hoặc tương đương) chỉ được đánh dấu supported nếu có endpoint/hosting phù hợp, bằng chứng chạy và chất lượng đo được.
- Voice clone cần có quyền sử dụng mẫu giọng, bản ghi chấp thuận và watermark/metadata khi cần. Không giả định mọi nhà cung cấp hỗ trợ cloning.
- Không đặt key API trong client, logs, prompt history hoặc file public. Hỗ trợ budget cap và ngừng gọi khi hết quota.

## 3.9. Asset Library & Rights

Thư viện asset có taxonomy (`logo`, `brand outro`, `footage`, `recording`, `AI generated`, `music`, `voice`, `stock`, `thumbnail`, `caption`), preview, source, ownership/license, expiry, content hash, attribution, reuse count, tags, versions và nơi đã được sử dụng. Tách *asset nguồn*, *asset đã biên tập* và *render cuối*.

Cơ chế kiểm tra quyền sử dụng âm thanh, giọng và footage trước khi xuất bản; asset thiếu quyền phải chặn hoặc đòi nhân sự xác nhận.

## 3.10. Production Workflow & Team Collaboration

Workflow bài bản: `IDEA → RESEARCH → SCRIPT → STORYBOARD → TASK ASSIGNMENT → SHOOT/ASSET COLLECTION → EDIT → QC → APPROVAL → SCHEDULE → PUBLISHED → ANALYSIS`.

Từng task có owner, due date, checklist, comments, files, dependency, trạng thái; hỗ trợ bàn giao giữa biên kịch, người dựng, người duyệt và publisher; có notifications thích hợp (nếu kênh gửi thông báo được kết nối).

## 3.11. Quality Control & Approval Center

QC gồm 4 tầng:

1. **Factual:** claim-source coverage, lỗi thuật ngữ, claim chưa xác minh, demo bị trình bày như thật, số liệu quá hạn.
2. **Brand/editorial:** logo, tone, outro, CTA phù hợp với pillar, brand kit, không biến phần kiến thức thành quảng cáo dày đặc.
3. **Media/technical:** playable MP4, đúng aspect/codec preset, black frame/freeze, vùng an toàn, caption không tràn, âm thanh quá nhỏ/vỡ, overlap, lỗi sync A/V, asset missing.
4. **Governance:** quyền dùng media/voice, người có quyền duyệt, nội dung thương mại/AI disclosure tùy yêu cầu nền tảng, dữ liệu khách hàng nhạy cảm.

QC report cần `check_id`, mức độ, phát hiện, scene/timecode, evidence, decision và người xử lý. Lỗi blocker chưa sửa phải ngăn xuất bản. Không gọi QC PASS nếu chỉ chạy kiểm tra metadata mà chưa xem video hoặc chưa thực hiện kiểm tra yêu cầu.

## 3.12. Publishing & Distribution

Tạo publication package theo kênh: video đúng preset, cover, title, description, hashtags, thumbnails, disclosure, CTA link + UTM, lịch và trạng thái. Tích hợp kênh qua API được hỗ trợ và tài khoản đã cấp quyền; **kênh không đủ điều kiện API thì phải có manual export/handoff minh bạch**, không giả nút 'đăng thành công'.

Kênh mục tiêu: TikTok, YouTube/Shorts, Facebook/Instagram Reels, LinkedIn khi khả thi. Idempotency khi publish/retry để tránh đăng trùng. Có history và link bài đăng sau khi xác nhận bằng evidence API hoặc người duyệt.

## 3.13. Performance & Content Intelligence

Báo cáo theo video, kênh, series, pillar, hook, outro, CTA, provider/render cost và cohort đăng bài. Phân biệt `impressions`, `views`, `retention`, `avg watch time`, `completion rate`, `shares`, `saves`, `profile visits`, `link click`, `qualified leads` khi nguồn dữ liệu thực hỗ trợ. Không tự suy số liệu thiếu.

Có thử nghiệm A/B cho hook/outro/voice/template (nếu khả năng phân phối cho phép), đồng thời ghi rõ các yếu tố gây nhiễu; không tuyên bố nhân quả khi dữ liệu chỉ mang tính quan sát.

## 3.14. Lead Journey / Business Conversion

CTA và landing page phải mang bối cảnh nội dung: ví dụ xem video AI Agent → landing/demo AI workflow cho doanh nghiệp; xem video RAG → tài liệu kiến trúc truy vấn tri thức.

Lưu mối liên hệ `publication → CTA → landing session/form → lead` nếu có căn cứ consent và tracking. Thiết kế CRM adapter/webhook trong tương lai; không tự nhận đã tích hợp CRM khi chưa kết nối.

## 3.15. Branding & Design System

Định hướng giao diện: **premium editorial technology, tinh tế, ấm, đáng tin, không quá công nghiệp hoặc neon cyberpunk**. Nội dung và thao tác sản xuất là trung tâm. Ưu tiên neutral đậm (charcoal/navy ấm), off-white, nhấn muted teal/amber hợp lý, độ tương phản tốt, bảng màu có semantic tokens, spacing và typography nhất quán. Thiết kế cuối phải được xác nhận bằng screenshot/bản duyệt, không chọn theo cảm tính của agent.

Hệ thống brand kit quản lý wordmark/logo BAHA (dùng file thương hiệu thật), fonts được cấp phép, outro, palette, motion style, giọng đọc, nhạc, template thumbnail, lower-third, series opener; dữ liệu minh họa phải được đánh dấu.

## 3.16. RBAC & Quản trị theo cấp

Tối thiểu tách quyền: `OWNER / EXECUTIVE`, `ADMIN / OPERATIONS`, `CONTENT_LEAD`, `RESEARCHER`, `SCRIPTWRITER`, `EDITOR`, `QC_REVIEWER`, `PUBLISHER`, `ANALYST`, `VIEWER`. Đây là **permission presets**, không cố định danh sách role DB nếu hệ thống đang có mô hình khác.

Áp dụng quyền theo organization/workspace/channel/project/asset; tối thiểu có `view`, `create`, `edit`, `assign`, `review`, `approve`, `render`, `publish`, `manage_brand`, `manage_provider`, `manage_users`, `view_cost`, `view_leads`.

Không ai có thể tự cấp quyền nhạy cảm vượt phạm vi. API/backend kiểm tra quyền độc lập với UI. Có audit log cho thay đổi quyền, xóa nội dung, đăng bài, sửa brand template và chi tiêu API.

---

# 4. KIẾN TRÚC NGHIỆP VỤ VÀ HỢP ĐỒNG DỮ LIỆU

## 4.1. Menu/Information Architecture khuyến nghị

1. **Overview** — Tình trạng doanh nghiệp, chiến dịch, pipeline.
2. **Content Strategy** — Series, calendar, pillar, audience, campaign.
3. **Research & Ideas** — Topic radar, research packs, claim verification.
4. **Content Studio** — Brief, script, storyboards, template.
5. **Production Studio** — Projects, edit timeline, assets, voice/music, renders.
6. **Review & Approval** — QC, feedback, sign-off.
7. **Publish & Channels** — Lịch, phân phối, tài khoản và bài đã đăng.
8. **Analytics & Leads** — Hiệu suất kênh, CTA, lead.
9. **Team & Operations** — Task, nhân sự, worker, chi phí.
10. **Settings** — Brand kit, providers, policies, API credentials, RBAC.

Thực tế có thể gộp một số mục để tránh menu dài; điều bắt buộc là hành trình xuyên suốt, ít thao tác lặp và không tạo hai nguồn sự thật cho một entity.

## 4.2. Dữ liệu lõi (cần mapping vào schema hiện hữu)

`Organization`, `Workspace`, `User`, `Role`, `Permission`, `ChannelAccount`, `Series`, `Campaign`, `Topic`, `Source`, `Claim`, `ResearchPack`, `ContentBrief`, `ScriptVersion`, `Storyboard`, `Scene`, `MediaAsset`, `AssetLicense`, `VoiceProfile`, `ProviderConfig`, `ProviderCapability`, `TimelineProject`, `RenderJob`, `QCIssue`, `Approval`, `ProductionTask`, `Publication`, `ChannelMetricSnapshot`, `CTA`, `LeadAttribution`, `Experiment`, `AuditEvent`.

**Không nhất thiết tạo một bảng cho từng tên**. Dùng schema cũ nếu tương thích, khai báo migration cần thiết; chọn normalization/denormalization theo truy vấn thực tế. Những entity chứa nội dung quan trọng phải có versioning và ownership.

## 4.3. Hợp đồng project video (khung tham chiếu, không buộc giữ nguyên key)

```json
{
  "project_id": "sample-explainer-001",
  "series_id": "technology-in-60s",
  "topic": "AI Agent khác Chatbot như thế nào?",
  "audience": "business_owner",
  "pillar": "TECH_EXPLAINED",
  "language": "vi-VN",
  "target_duration_seconds": 60,
  "aspect_ratio": "9:16",
  "research_pack_id": "rp-001",
  "approved_script_version": 3,
  "outro_variant": "O1",
  "scenes": [
    {"scene_id": "s01", "type": "TEXT_MOTION", "duration_seconds": 3, "voice_segment_id": "v01", "evidence_claim_ids": []},
    {"scene_id": "s02", "type": "DIAGRAM", "duration_seconds": 12, "voice_segment_id": "v02", "evidence_claim_ids": ["c01"]},
    {"scene_id": "s03", "type": "SCREEN_RECORDING", "duration_seconds": 28, "voice_segment_id": "v03", "evidence_claim_ids": ["c02"]},
    {"scene_id": "s04", "type": "TEXT_MOTION", "duration_seconds": 12, "voice_segment_id": "v04", "evidence_claim_ids": ["c03"]},
    {"scene_id": "s05", "type": "BRAND_OUTRO", "duration_seconds": 5, "voice_segment_id": "v05", "evidence_claim_ids": []}
  ],
  "quality_status": "PENDING_REVIEW",
  "publication_status": "NOT_SCHEDULED"
}
```

Ví dụ chỉ mang tính minh họa thiết kế dữ liệu, **không phải bằng chứng endpoint/backend đã tồn tại**.

## 4.4. Nguyên tắc kiến trúc

- **Source of truth rõ ràng:** metadata/trạng thái nằm ở backend DB, file asset trong object storage/NAS phù hợp, hàng đợi job có kiểm soát.
- **Tách domain khỏi provider:** các workflow chỉ gọi interface; provider adapter xử lý auth, format request, error và billing.
- **Tách editor khỏi render:** timeline JSON/project file mở lại được; render worker xử lý export không khóa UI.
- **Asynchronous jobs:** idempotent, retry backoff, deduplication, timeout, cancellation, checkpoint, dead-letter, error classification.
- **Observability:** mỗi pipeline run có correlation ID, job history, provider response đã lược bí mật, usage/cost, trạng thái và artifact manifest.
- **Migration không mất dữ liệu:** backup, dry-run, rollback hoặc forward-fix, mapping ID cũ, giữ API compatibility nơi có phụ thuộc.
- **Không chuyển toàn bộ hệ thống sang microservices** nếu audit không chứng minh nhu cầu; ưu tiên kiến trúc dễ vận hành.

---

# 5. CÁC HÀNH TRÌNH NGƯỜI DÙNG BẮT BUỘC

## Journey A — Sản xuất video từ một chủ đề

**Input:** chủ đề thô + pillar + audience + kênh + độ dài + yêu cầu BAHA outro.  
**Flow:** Topic → Research Pack → Facts approval → Script → Storyboard → Generate/collect assets → TTS → Auto assembly → Preview → Technical/fact/brand QC → Human Approval → Final render → Publish package.  
**Output:** MP4 playable, SRT, thumbnail, captions/description/hashtags, timeline editable, source/evidence ledger, QC report, publication-ready artifacts.  
**Halt:** nếu thiếu nguồn cho claim, license, TTS, provider hoặc quyền phê duyệt, phải báo blocker rõ và giữ project có thể tiếp tục; không âm thầm giả hoàn thành.

## Journey B — Biên tập lại video cũ

**Input:** project hiện hữu đã render + yêu cầu “thay cảnh minh họa từ 15–25s, giữ lời đọc và outro”.  
**Flow:** mở timeline, xác định scene, thay asset/sửa overlay, cập nhật revision, preview cảnh ảnh hưởng, render mới, kiểm tra regression đoạn không đổi.  
**Output:** project version mới, MP4 mới, diff/revision, archive bản cũ.  
**Acceptance:** không mất dữ liệu, subtitle, audio và hiệu ứng ngoài phạm vi cần sửa; có thể rollback.

## Journey C — Xuất bản và đo lường

**Input:** video đã QC/approved, các channel account có quyền, phiên bản CTA, lịch.  
**Flow:** create platform package → validate requirements → schedule/post (nếu API được xác thực) hoặc manual handoff → lưu external publication ID/link → thu thập metrics khả dụng → gắn kết quả vào series và CTA/lead.  
**Output:** trạng thái được xác minh, báo cáo performance, insight đề xuất video tiếp theo.  
**Acceptance:** không đăng trùng, không báo published khi nền tảng chưa xác nhận, không ngụy tạo số liệu hoặc conversion.

## Journey D — Giao việc và duyệt nhiều cấp

**Input:** brief do content lead tạo, nhân viên research/script/editor/publisher và quản lý duyệt.  
**Flow:** giao research → reviewer xác nhận claim → giao script → lead duyệt nội dung → editor dựng → QC tạo issue → sửa → người có quyền approved → publisher lên lịch.  
**Output:** audit trail ai làm gì, thời điểm, phiên bản nào được phê duyệt, bình luận và blockers.  
**Acceptance:** người không có quyền không tự approve/publish qua API dù nút UI bị ẩn.

---

# 6. GIAO DIỆN & TRẢI NGHIỆM CẦN THAY ĐỔI

## 6.1. Tổng thể

Xây dựng hệ thống nhất quán thay vì các màn hình rời rạc; có left navigation hoặc adaptive navigation phù hợp, global search, command palette nếu hữu ích, create-action nổi bật, breadcrumb dự án, production status, cảnh báo cần duyệt. Không dùng hiệu ứng cầu kỳ làm chậm thao tác.

## 6.2. Các màn hình trọng tâm cần mô tả trong thiết kế

- **Overview:** activity/issue inbox, lịch đăng, hoạt động worker, KPI và lead chất lượng.
- **Topic Workspace:** research sources bên trái, claim ledger bên phải, tóm tắt chủ đề ở trung tâm.
- **Script Studio:** narrative, timestamps, citations, version diff, pronunciation notes, voice preview.
- **Storyboard:** scene cards dạng filmstrip, visual source/type, duration, trạng thái, batch actions.
- **Production Studio:** media pool, preview lớn, inspector, multi-track timeline, audio waveform, render/export.
- **QC Review:** player với timecode issue markers, factual evidence panel, checklist, approve/reject.
- **Publishing Calendar:** kênh, caption variants, status, schedule, review gate.
- **Performance:** phân tích series/pillar/hook/outro/CTA, nguồn metrics và chỉ số thiếu.
- **Brand Kit:** tài sản logo thực, outro variants, voice dictionary, theme tokens.
- **Provider Control:** adapter health, real/mocked badge trong nội bộ, cost/quota, last verified.

## 6.3. Responsive & Accessibility

Desktop là không gian thao tác dựng chính; tablet và mobile hỗ trợ kiểm duyệt, preview, lịch và giao việc. Khi mobile không đủ chỗ cho timeline đa track, cung cấp chế độ xem/điều khiển rút gọn thay vì thu nhỏ nguyên desktop. Keyboard navigation, labels, focus states, readable contrast, caption preview phải có kiểm tra.

---

# 7. QUY TRÌNH TRIỂN KHAI THEO PHASE & ĐIỀU KIỆN NGHIỆM THU

**Mỗi phase bắt buộc có**: `Inputs`, `Changes`, `Outputs`, `Evidence`, `Tests`, `Known gaps`, `Go/No-Go`. Agent không được tự động đánh dấu DONE nếu chưa đạt điều kiện nghiệm thu.

## P0 — Reality Audit / Baseline (bắt buộc trước mọi refactor)

**Input:** repo và môi trường hiện hữu, tài liệu sẵn có, cấu hình deploy, sample projects.  
**Thực hiện:** clone/checkout nếu có quyền; đọc source thay vì chỉ README; chạy build/test hiện hữu; liệt kê routes/screens/APIs/DB/jobs/providers/feature flags; xác định mọi chức năng thực/mocked; snapshot cấu trúc DB (không lộ secrets), screenshot các trang chính; kiểm thử ít nhất một luồng đang chạy nếu khả thi.  
**Output:** `docs/audit/AS_IS_REPORT.md`, architecture map, feature inventory, integration evidence, risk register, regression checklist, baseline screenshots/logs.  
**PASS:** danh sách KEEP/REFACTOR/EXTEND/DEPRECATE và mức độ tin cậy đã được chứng minh. Không có access? Ghi blocker chính xác; tuyệt đối không điền giả.

## P1 — Product Architecture & UX Foundation

**Input:** P0 được chấp thuận + bản đặc tả này.  
**Thực hiện:** thiết kế navigation, domain flow, design tokens, page wireframes, roles/permissions mapping, migration/feature-flag plan; tái sử dụng components tương thích.  
**Output:** `TO_BE_ARCHITECTURE.md`, IA sitemap, screen inventory, design system, DB/API delta, risk-based migration plan.  
**PASS:** routes cũ quan trọng còn hoạt động trong staging; role-level access test; UX journey đi từ idea đến project mà không phải dùng mock-only dead end.

## P2 — Topic → Research → Script

**Input:** config series/pillar, nguồn nghiên cứu, tiêu chuẩn fact check.  
**Thực hiện:** topic list, research pack, claims-evidence, script generator/editor/versioning, content brief, status workflow.  
**Output:** tạo được project explainer từ topic với script đã liên kết nguồn và có revision.  
**PASS:** thử 3 chủ đề khác nhau; claim thiếu chứng minh bị phát hiện; sửa script lưu revision; kiểm chứng API/DB thật và quyền theo role.

## P3 — Storyboard & Editable Production Project

**Input:** script được duyệt, brand kit, project assets.  
**Thực hiện:** scene planner, asset bind, timeline/project JSON, preview, sửa cảnh/timing, phiên bản.  
**Output:** storyboard và timeline edit được, xuất/nhập project giữ scene IDs.  
**PASS:** tạo ≥5 scene (diagram, screen recording, text motion, footage/AI asset khi khả dụng, outro); đổi thứ tự/thay cảnh/lưu-mở lại, không mất data.

## P4 — Cloud AI Adapters & Rendering

**Input:** P3 + provider credentials/quota được cấp phép, sample media thật, CPU worker hiện có.  
**Thực hiện:** adapter registry + health checks, TTS/ASR (khi provider được xác nhận), media generation phù hợp, FFmpeg/render pipeline, subtitle alignment, audio mixing/ducking, job lifecycle, budget tracking.  
**Output:** export playable MP4/SRT/timeline/artifact manifest từ project thật; có logs và usage ledger.  
**PASS:** ít nhất một video explainer thực 45–60s, 9:16, có narration, subtitle, đồ họa minh họa, âm thanh và BAHA outro; test retry/cancel/render lỗi; đo được kết quả thực chứ không phải progress animation giả. Nếu provider chưa được cấp quyền, tách rõ các bước đã chạy thật bằng asset được phép và những capability đang BLOCKED.

## P5 — QC, Approval & Collaboration

**Input:** video ở P4, role hierarchy và QC policies.  
**Thực hiện:** automated media validation, factual checklist, brand checks, approval gates, issue comments/timecodes, audit log.  
**Output:** QC report có evidence và workflow reject → fix → approve.  
**PASS:** cố tình đưa 1 claim unsupported, 1 cảnh thiếu asset, 1 lỗi subtitle hoặc aspect: pipeline phải phát hiện những lỗi nằm trong phạm vi validator đã triển khai; publisher không vượt approval gate.

## P6 — Publishing, Calendar, Analytics & Leads

**Input:** approved media, channel credentials/quyền thực tế, CTA routes, metrics API được hỗ trợ.  
**Thực hiện:** platform-specific packages, schedule, publishing/manual handoff, dashboard metrics với provenance, CTA/UTM tracking, lead capture khi được phép.  
**Output:** publication records liên kết tới project/series; metrics hiển thị với source và timestamp; tracking CTA hoạt động.  
**PASS:** kiểm tra live hoặc sandbox trên kênh được cấp quyền; nơi chưa hỗ trợ phải có export/manual handoff; không đăng trùng; số liệu thiếu hiển thị N/A không tự dựng; một đường dẫn CTA test có thể xác minh.

## P7 — End-to-End Regression, Security, Performance & Deployment Readiness

**Input:** toàn bộ phase trước, baseline P0.  
**Thực hiện:** E2E 4 user journeys, permission/security, secret scans, migration dry-run, resilience/retry, monitoring/logging, restore/rollback thử nghiệm, mobile QA, load smoke.  
**Output:** test report, release notes, migration scripts, runbook, rollback plan, issue backlog.  
**PASS:** baseline features không bị hỏng ngoài thay đổi đã duyệt; không lỗi blocker; secret không lộ; dữ liệu migrate/rollback an toàn; video mở xem và sửa lại được; chủ dự án duyệt trước khi go-live.

## P8 — Pilot Content & Optimization

**Input:** staging/production được duyệt, brand assets, tài khoản xuất bản và người chịu trách nhiệm.  
**Thực hiện:** sản xuất pilot với 3 series/chủ đề: AI Agent vs Chatbot, RAG vs Fine-tuning, ứng dụng AI workflow doanh nghiệp. Mỗi video có nguồn xác minh, storyboard, project editable, QC và intro/outro variant đã chọn. Chạy phân phối thật **chỉ khi được chủ dự án duyệt**.  
**Output:** bộ video mẫu, style guide cập nhật, cost/time report, hướng tối ưu theo data thực sau pilot.  
**PASS:** người dùng không kỹ thuật có thể khởi tạo một video, người dựng sửa một scene, reviewer QC, publisher export; mọi trạng thái được hệ thống lưu có bằng chứng.

---

# 8. BỘ TIÊU CHÍ NGHIỆM THU KHÔNG ĐƯỢC RÚT GỌN

## 8.1. End-to-end demo bắt buộc

Chủ đề mẫu: **“AI Agent khác Chatbot thông thường như thế nào?”**

1. Tạo project từ Content Strategy, chọn pillar Tech Explained, audience chủ doanh nghiệp, 60s 9:16.
2. Research Desk lưu ≥2 nguồn chất lượng và map rõ từng claim quan trọng; phản biện/nhận diện câu chưa đủ bằng chứng.
3. Script Studio tạo hook, narration, visual beats, brand outro; sửa nội dung và thấy version history.
4. Storyboard có ≥5 scenes và đa dạng loại hình: sơ đồ motion, text motion, screen recording/UI demo, kết luận, BAHA outro; media có quyền dùng.
5. Production Studio dựng **video thực** có voice, nhạc/âm thanh hợp lệ, caption tiếng Việt, transitions hợp lý, brand outro; không phụ thuộc GPU cục bộ.
6. QC phát hiện hoặc minh chứng đã kiểm tra sync, overflow, clip, nguồn factual, quyền và brand.
7. Video được reviewer có quyền duyệt; nhân viên thiếu quyền không thể bypass API.
8. Xuất MP4, SRT, thumbnail, script, editable timeline JSON và QC report; xem play video từ file output.
9. Sửa một scene, xuất revision mới, bản gốc còn nguyên.
10. Tạo package đăng TikTok/YouTube; publish thật chỉ khi integration được xác thực và có phê duyệt, còn lại export/manual.
11. Tạo CTA BAHA với UTM và kiểm thử đường dẫn; analytics phân biệt data thật/chưa có.

**Gói evidence:** commit/branch, test commands và kết quả, ảnh chụp theo route, log job ID, đường dẫn asset nội bộ, metadata ffprobe, bản phát video kiểm xem được, bản diff revision và báo cáo QC.

## 8.2. Quality Gates

| Gate | Tiêu chí | Kết quả khi fail |
|---|---|---|
| G0 — Repository reality | Checkout/build hoặc có blocker minh bạch; inventory hiện trạng có nguồn | Không khởi động refactor rủi ro |
| G1 — Data & existing features | Chứng minh giữ luồng cũ, migration an toàn | Ngăn merge/release |
| G2 — Research integrity | Không claim unsupported trong final voice | Block final approval |
| G3 — Editable video | Project lưu/mở lại/sửa/render được | Không được gọi Production Studio hoàn thành |
| G4 — Render reality | File MP4 và audio/video thực, metadata và playback | Không được gọi pipeline hoàn thành |
| G5 — Provider truth | Capability có evidence/live result hoặc nhãn blocked | Không quảng bá support giả |
| G6 — Rights / permissions | Media/voice hợp lệ, publish đúng role | Block publishing |
| G7 — Publishing truth | External result xác minh hoặc explicit manual step | Không ghi PUBLISHED |
| G8 — Analytics truth | Có provenance, timestamp, missing values rõ | Không dùng số giả |
| G9 — User acceptance | Chủ dự án kiểm tra end-to-end và đồng ý rollout | Không tự triển khai production |

---

# 9. QUẢN LÝ THAY ĐỔI VÀ BẢO TOÀN DỰ ÁN ĐÃ TRIỂN KHAI

**Yêu cầu bắt buộc:** Nhiệm vụ là **chuyển đổi sản phẩm hiện hữu**, không tự tạo app demo khác nằm bên cạnh. Agent phải tìm hiểu mã nguồn và chứng minh việc tái sử dụng.

- Tạo feature branch, snapshot config và backup phù hợp; không ghi đè dữ liệu production.
- Mapping các menu và route cũ → menu/route mới; redirect/deprecation plan cho deep links.
- Migration API/DB có script và test, bảo toàn ID/historical project, asset và channel connections.
- Rà soát mọi external integration, queue/job đang chạy, worker, shared UI libraries, logging, RBAC.
- Nếu có các dự án/suite khác của BAHA (ví dụ một công cụ biên tập video riêng) thì **chỉ** đề xuất tích hợp sau khi xác nhận ranh giới dự án, quyền truy cập và tính khả thi; không tự động coi đó là cùng codebase.
- Loại bỏ màn hình mock/đường dẫn dead-end khỏi luồng chính hoặc đánh dấu preview/beta; không đánh tráo trạng thái.
- Dùng feature flags/canary nếu cần để phát hành từng module mà không phá toàn bộ hệ thống.

---

# 10. THƯỚC ĐO THÀNH CÔNG

## 10.1. Product/engineering KPIs

- Tỷ lệ chức năng quan trọng có bằng chứng `REAL_VERIFIED`.
- Time từ topic đến first editable preview; từ approved đến publish package.
- Tỷ lệ render thành công, median render time, số lần retry, chi phí mỗi phút video/provider.
- Số lần content revision, QC rejection và nguyên nhân.
- Tỷ lệ người dùng hoàn tất flow mà không cần sửa DB/log thủ công.

## 10.2. Content/business KPIs

- Viewer retention và completion theo pillar/series/hook/outro (khi nguồn dữ liệu cho phép).
- Tỷ lệ lưu/chia sẻ, lượng audience đúng nhóm mục tiêu.
- CTR của CTA có tracking, số qualified leads thực, tỷ lệ chuyển demo/tư vấn, nội dung hỗ trợ lead.
- Phân tích điều gì có tương quan với kết quả; không suy nguyên nhân khi thử nghiệm chưa đủ kiểm soát.

**Không đặt KPI thành công chỉ dựa vào số video tạo ra hoặc số lượt xem.**

---

# 11. BÁO CÁO VÀ BÀN GIAO BẮT BUỘC CỦA AGENT

Tại mỗi phase, agent phải cập nhật:

1. `docs/transformation/AS_IS_TO_BE_MATRIX.md` — danh mục chức năng cũ và phương án chuyển đổi.
2. `docs/transformation/ARCHITECTURE.md` — sơ đồ luồng hệ thống, DB, API, worker, storage, providers.
3. `docs/transformation/IMPLEMENTATION_LOG.md` — file/commit thay đổi, lý do, blocker, quyết định thiết kế.
4. `docs/transformation/TEST_EVIDENCE.md` — command, kết quả, screenshots/log/artifacts và lỗi còn mở.
5. `docs/transformation/PROVIDER_CAPABILITIES.md` — từng API/provider, trạng thái thực tế, bằng chứng, quota/cost và fallback.
6. `docs/transformation/ROLLBACK_AND_DEPLOYMENT.md` — migration, backups, rollback/release instructions.
7. `docs/transformation/OPEN_GAPS.md` — những gì CHƯA hoàn thành, nguyên nhân, bước tiếp theo; không che giấu.

Nếu cấu trúc docs repo hiện có khác, được điều chỉnh đường dẫn nhưng **không được bỏ các nội dung**.

## 11.1. Mẫu báo cáo phase (bắt buộc)

```text
PHASE: P[n]
STATUS: REAL_VERIFIED | PARTIAL | BLOCKED | NOT_STARTED
BASELINE / INPUTS:
CHANGED FILES / COMMITS:
API + DB IMPACT:
WHAT WORKS (evidence IDs):
WHAT IS MOCKED / UNVERIFIED:
TEST COMMANDS & RESULTS:
REAL OUTPUT ARTIFACTS:
SCREENSHOTS / LOGS / JOB IDS:
REGRESSION RESULTS:
RISKS / BLOCKERS:
GO / NO-GO DECISION:
NEXT PHASE DEPENDENCIES:
```

## 11.2. Định nghĩa DONE

Một tính năng chỉ được gọi `DONE` khi **code đã tích hợp vào repo hiện hữu, build/test phù hợp, luồng UX có thể thao tác, backend/data path là thật hoặc được gắn nhãn phạm vi rõ ràng, có bằng chứng đầu ra, quyền và lỗi được xử lý**. Screenshot tĩnh hoặc mô tả thành công không đủ.

---

# 12. CHỈ THỊ KHỞI ĐỘNG — COPY CHO ANTIGRAVITY/AGENT

> Hãy tiếp nhận file `BAHA_CREATOR_STUDIO_MASTER_TRANSFORMATION_SPEC.md` là nguồn yêu cầu chuyển đổi sản phẩm BAHA Group Creator Studio hiện hữu. Mục tiêu là tái cấu trúc toàn diện sản phẩm theo mô hình **Technology Explainer & AI Solutions Media Operating System**, dùng video giải thích kiến thức công nghệ để thu hút khán giả, minh họa ứng dụng AI thực tế và giới thiệu **“BAHA Group — Cung cấp giải pháp AI toàn diện”** ở cuối một cách tinh tế. Không được chỉ sửa theme/landing page hoặc dựng UI mock.
>
> Bắt đầu từ **P0 Reality Audit**: đọc source thật, chạy build/test hiện có, lập ma trận chức năng và sơ đồ kiến trúc AS-IS, kiểm tra API, DB, worker, hệ thống biên tập, channel integrations, RBAC, dữ liệu và deployment. Không suy đoán dựa vào README, ảnh mockup hoặc báo cáo cũ. Sau đó xây dựng mapping TO-BE, kế hoạch migration và triển khai từng phase P1–P8 trên branch/staging, bảo tồn luồng cũ. Ưu tiên dịch vụ AI qua API/cloud và xử lý FFmpeg/CPU khi phù hợp, không yêu cầu GPU cục bộ; mọi tích hợp Flow/Flow Music/TTS/TikTok/YouTube phải kiểm tra capability thực tế và quyền truy cập trước khi tuyên bố hỗ trợ. Nêu rõ `REAL_VERIFIED / REAL_UNVERIFIED / MOCK / BLOCKED`.
>
> Mỗi phase phải có thay đổi mã nguồn thật, commit, test, screenshots/logs và artifact; đặc biệt phải xuất được **một video explainer 45–60 giây có kịch bản kiểm chứng nguồn, storyboard, lời đọc, phụ đề, motion/demo, outro BAHA, QC và project mở lại chỉnh sửa được**. Phải chứng minh sửa một cảnh và render lại không phá cảnh còn lại, kiểm thử phân quyền, xuất bản hoặc handoff theo trạng thái API thật, báo cáo analytics không giả số liệu. Không tự đụng production, dữ liệu thật hoặc đăng bài khi chưa được phê duyệt. Nếu thiếu access/credentials, tiếp tục các việc độc lập, đánh dấu chính xác blocker thay vì báo hoàn thành. Báo cáo tiến độ theo mẫu ở mục 11.1 và chỉ đánh dấu DONE khi đã có bằng chứng.

---

**Kết quả mong đợi sau chuyển đổi:** BAHA Group sở hữu một dây chuyền sản xuất nội dung công nghệ có tổ chức, có chuyên môn, có thể biên tập chuyên nghiệp và tự động hóa, đo được hiệu quả kinh doanh, có quản trị đa cấp và luôn minh bạch về tính năng nào đã thật sự vận hành.
