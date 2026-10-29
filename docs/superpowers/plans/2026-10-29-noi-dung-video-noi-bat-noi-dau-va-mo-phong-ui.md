# Nâng chất lượng nội dung video (nỗi đau, kiến thức, giải pháp, mô phỏng chatbot/AI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Storyboard do planner sinh ra phải kể được mạch nỗi đau, nguyên nhân, kiến thức, giải pháp, kết quả của content; phủ đủ ý chính; có chuyển động nhiều nhịp trong mỗi shot; và những ý cần thấy chữ hoặc giao diện (chatbot, AI, dashboard) được dựng bằng mô phỏng UI thật thay vì nhờ Flow.

**Architecture:** Thêm một bước "brief" trước khi viết storyboard (rút nỗi đau, thông điệp chính có mã, giải pháp, CTA). Storyboard hợp đồng v4 gắn mỗi shot với một nhịp kể chuyện, các mã thông điệp, nhiều "action beat" theo mốc thời gian, và loại shot `FLOW_ORIGAMI` hoặc `UI_SIM`. Shot `UI_SIM` được render cục bộ thành mp4 rồi đi vào timeline sẵn có. Một bộ chấm điểm offline chặn storyboard thiếu ý hoặc quá tĩnh trước khi người dùng duyệt.

**Tech Stack:** Python/Pydantic (`sin_content_api`), Playwright + ffmpeg (đã có trong image backend), Next.js/TypeScript (`sin_creator_os`), unittest/pytest hiện có.

**Spec:** Không có spec riêng; yêu cầu của người dùng ngày 2026-10-29 (hoạt hình chưa đi từ nỗi đau doanh nghiệp, video quá đơn giản, chỉ minh họa lời thoại, cần mô phỏng chatbot/AI). Phần "Kết quả review" bên dưới là cơ sở.

## Global Constraints

- Narration cho TTS: không chữ số hay ký hiệu, từ tiếng Anh phiên âm tiếng Việt (giữ đúng rule tại `planner.py:137-141` và kiểm tra regex tại cuối `generate_storyboard`).
- Nguyên tắc thiết kế: người dùng chọn tổng thời lượng; LLM quyết định số shot, thời lượng từng shot, mốc thời gian action beat, mô tả cảnh, nhân vật phụ và cách phân bổ nhịp kể chuyện. Code và prompt không ép con số cố định (không công thức số shot theo thời lượng, không tỷ lệ phần trăm từng nhịp); code chỉ kiểm hợp lệ và các ràng buộc cứng bên dưới.
- Ràng buộc cứng: mỗi shot `duration_seconds` từ 1 đến 10 (giới hạn Flow hiện có), tổng bằng `target_duration_seconds` (20 đến 180), tối đa 30 shot; `aspect_ratio` chỉ `9:16` hoặc `16:9`.
- Plan đã lưu (hợp đồng v3, không có trường mới) phải đọc và chạy được như cũ; trường mới đều có default. `Storyboard` và `StoryboardShot` giữ `extra="forbid"`.
- Không thêm cột DB và không migration: dữ liệu mới nằm trong `storyboard_json`.
- Flow không được nhận yêu cầu vẽ chữ (giữ `planner.py:117`); mọi chữ nhìn thấy do UI_SIM hoặc phụ đề của renderer tạo.
- Không ghi, seed hay migrate dữ liệu thật trên NAS trong quá trình phát triển; chạy thử planner chỉ qua LLM, không qua Flow.

## Kết quả review (có bằng chứng)

Nguồn: storyboard của plan `475edd4d-9ab7-442d-8028-a02751bee983` (content "AI trong Sales", 60 giây, 6 shot) và code `sin_content_api/src/modules/tao_video_noi_dung/`.

| # | Phát hiện | Bằng chứng |
|---|---|---|
| 1 | Không có mạch kể chuyện. Planner không được yêu cầu dựng chuỗi nỗi đau, hệ quả, kiến thức, giải pháp, kết quả, CTA. Shot 1 mở bằng "văn phòng giấy yên tĩnh", không thấy tổn thất nào (khách bị bỏ sót, nhân viên quá tải). | `planner.py:131-160` (system prompt không có bước nào về cấu trúc kể chuyện); `scene` của `shot_01` |
| 2 | Luật chuyển động ép về tối thiểu: "Chỉ một hành động chính đơn giản", "chuyển động duy nhất, chậm", mỗi shot đúng một chuyển động camera. Mỗi clip 10 giây chỉ có một động tác nhỏ (đưa tay tới thiết bị, chỉ vào thẻ, đẩy tập giấy). | `planner.py:114`, `planner.py:159`; prompt `shot_01..06` |
| 3 | Lời thoại dày hơn hình: narration được ép "lấp đầy" ở 4,2 từ/giây (khoảng 42 từ cho 10 giây, 3 đến 4 ý) trong khi hình chỉ thể hiện một ý. Hình chỉ minh họa lời thoại. | `planner.py:138`; `narration` và `prompt` của từng shot |
| 4 | Nhịp đều như máy: số shot do công thức cố định thay vì do nội dung quyết định (60 giây thành 6 shot x 10 giây), mọi shot `continues_previous=false`, một nhân vật chính mặc cùng bộ đồ ở cả 6 cảnh. Không có khách hàng, đối thủ, hay tình huống tương phản trước và sau. | `planner.py:125` (công thức `max(3, (target+9)//10)` ép số shot theo thời lượng; sẽ bỏ); `continuity_anchor` và danh sách shot |
| 5 | Mô phỏng chatbot/AI không thể đạt trong thiết kế hiện tại: cấm chữ trong hình ("tuyệt đối không có chữ", "không biến dữ liệu thành chữ hay biểu đồ có nhãn") nên tin nhắn chỉ là "ô sáng trừu tượng". Cuộc hội thoại lúc hai giờ sáng không bao giờ hiện ra. | `planner.py:117`, `service.py:35`; prompt `shot_04`, `shot_05` |
| 6 | Không có kiểm tra phủ ý. Câu "phủ đủ các ý chính" chỉ là lời dặn, không validator nào kiểm. QC ở runner chỉ đo kỹ thuật (kích thước, codec, thời lượng, FPS, decode), không đo nội dung hay chuyển động. | `planner.py:147`; `runner.py:47-90` |
| 7 | Prompt gửi Flow bị pha loãng bởi khoảng 20 câu quy tắc cố định (giải phẫu, khuôn mặt, âm thanh, chống rung) nối sau phần nội dung của shot. | `build_shot_prompt` `planner.py:75-118` |
| 8 | Một lần gọi LLM làm tất cả (tiêu đề, anchor, lời dẫn, prompt từng shot) với `max_tokens` tối đa 6000, không có bước phân tích content trước. | `planner.py:192` |
| 9 | Một nguyên nhân gốc về nội dung: content nguồn mang giọng quảng bá tích cực, gần như không nêu nỗi đau cụ thể. Planner lại bị dặn "không thêm sự kiện làm đổi nghĩa" nên không dám dựng tình huống nỗi đau. Cần cơ chế cho phép suy ra nỗi đau nhưng gắn nhãn rõ để người duyệt thấy. | `planner.py:152`; `source_content` của plan |

Điều chưa kiểm: chất lượng video Flow thực tế, vì run `fe85ee52...` đang kẹt `BLOCKED_FLOW_SETUP` nên chưa có clip nào để xem. Các nhận định về "quá tĩnh" dựa trên prompt, chưa dựa trên clip.

## Nghiên cứu bên ngoài (nguồn thứ ba, chưa xác minh với tài liệu chính thức của Google)

- Cấu trúc video giải thích: nhiều hướng dẫn thống nhất dùng Problem, Agitate, Solution quanh hook, proof, CTA; các nguồn đưa tỷ lệ thời gian mẫu nhưng chỉ để tham khảo, plan này không dùng làm quy tắc cứng vì LLM tự phân bổ theo nội dung và thời lượng người dùng chọn. Nguồn: [Biteable](https://biteable.com/blog/explainer-video-script-template/), [Video Explainers](https://videoexplainers.com/blog/how-to-write-explainer-video-script), [Yans Media](https://yansmedia.com/blog/explainer-video-structure).
- Chữ trong video AI: các hướng dẫn cộng đồng cho rằng chữ vẫn dễ hỏng; cách bền hơn là cho chữ vào bước hậu kỳ hoặc dùng ảnh có sẵn rồi image-to-video. Nguồn: [veo3gen.app](https://www.veo3gen.app/blog/text-in-ai-video-is-still-tricky-2026-9-prompt-patterns-that-make-labels-signs-a). Đây là lý do chọn UI_SIM dựng ngoài Flow.
- Nhiều nhịp trong một clip: có mẫu prompt chia clip 8 giây thành các đoạn theo mốc giây (ví dụ 0 đến 1,5 giây, 1,5 đến 3 giây). Nguồn cộng đồng, cần thử với Flow thật trước khi tin. [veo3 prompting guide](https://developer.tenten.co/veo-331-pro-json-prompting-step-by-step.md).
- Tính năng Flow liên quan: Ingredients to Video, Frames to Video (khung đầu/cuối), Extend; chi tiết khác nhau giữa các nguồn. [Google Flow FAQ](https://labs.google/fx/tools/flow/faq).

## Review Focus

- Content không có nỗi đau rõ (như bài "AI trong Sales"): storyboard vẫn phải có beat `PAIN` nhưng nội dung suy ra được đánh dấu `inferred` và không đưa số liệu bịa.
- Content không nhắc chatbot, AI hay dữ liệu: không shot nào bị ép thành `UI_SIM`.
- Content rất ngắn (40 ký tự) và rất dài (12 KB): brief và storyboard vẫn hợp lệ hoặc báo lỗi rõ ràng, không treo.
- Plan cũ hợp đồng v3 mở lại trên UI và chạy tiếp: không lỗi schema, không đổi hash duyệt.
- Narration có số, ký hiệu hoặc từ tiếng Anh trong tin nhắn UI_SIM: chữ hiển thị là chữ viết, còn lời đọc TTS vẫn phải qua rule phiên âm.

## File Structure

- Create `sin_content_api/src/modules/tao_video_noi_dung/danh_gia.py`: chấm điểm storyboard (phủ ý, thứ tự nhịp, số action beat, tỷ lệ chữ).
- Create `sin_content_api/src/modules/tao_video_noi_dung/brief.py`: `ContentBrief` và `generate_brief`.
- Modify `planner.py`: hợp đồng v4 (`Beat`, `ShotKind`, `UiScene`), validator, system prompt, `build_shot_prompt` nhánh v4.
- Create `sin_content_api/src/modules/tao_video_noi_dung/ui_sim.py`: render `UiScene` thành mp4.
- Modify `runner.py` (và `cong_harness.py` nếu cần): shot `UI_SIM` không gọi `dispatch_shot`.
- Modify `service.py`: gọi brief rồi storyboard, tính lại hash như cũ.
- Modify `sin_creator_os/src/lib/api/content-video-api.ts` và `.../production/_components/content_video_production.tsx`: kiểu dữ liệu và hiển thị trường mới, đảm bảo `updatePlan` giữ nguyên trường mới.
- Tests: `sin_content_api/tests/test_content_video_storyboard_quality.py` (mới), mở rộng `tests/test_content_video_pipeline.py`.

## Tasks

### Task 1: Bộ chấm điểm storyboard và baseline

**Files:**
- Create: `sin_content_api/src/modules/tao_video_noi_dung/danh_gia.py`
- Test: `sin_content_api/tests/test_content_video_storyboard_quality.py`
- Fixture: `sin_content_api/tests/fixtures/storyboard_ai_sales_v3.json` (storyboard hiện tại của plan `475edd4d...`, lấy qua API, không chứa dữ liệu nhạy cảm)

**Interfaces:**
- Produces: `score_storyboard(storyboard: Storyboard, brief: ContentBrief | None = None) -> StoryboardScore` với `StoryboardScore(coverage: float, pain_before_solution: bool, static_shot_ratio: float, text_dependent_shots: int, issues: list[str])`. `static_shot_ratio` là tỷ lệ shot có thời lượng trên 3 giây mà chỉ có một action beat; chỉ để báo cáo, không chặn.

- [x] **Step 1: Viết test baseline**: `test_baseline_ai_sales_storyboard_fails_quality_gates` nạp fixture v3, assert `static_shot_ratio == 1.0` (mọi shot v3 coi là một beat), `pain_before_solution is False`, `"NO_PAIN_BEAT" in issues`.
- [x] **Step 2: Chạy test, thấy FAIL** vì module chưa có: `cd sin_content_api && python -m pytest tests/test_content_video_storyboard_quality.py -v`.
- [x] **Step 3: Cài `score_storyboard`** trong `danh_gia.py`. Với shot v3 (không có trường mới) coi như không có beat và không có action beat.
- [x] **Step 4: Chạy lại, thấy PASS**, rồi commit.

### Task 2: Brief nội dung

**Files:**
- Create: `sin_content_api/src/modules/tao_video_noi_dung/brief.py`
- Test: `sin_content_api/tests/test_content_video_storyboard_quality.py`

**Interfaces:**
- Produces: `KeyMessage(id: str, text: str, source: Literal["content", "inferred"])`; `ContentBrief(pains: list[KeyMessage], consequences: list[KeyMessage], insights: list[KeyMessage], solutions: list[KeyMessage], outcomes: list[KeyMessage], cta: KeyMessage | None, needs_ui_demo: bool)`; `generate_brief(content: str, client: Any) -> ContentBrief`.
- Rule: `pains` luôn có ít nhất một phần tử; phần tử không có trong content phải `source="inferred"` và không chứa chữ số.

- [x] **Step 1: Viết test** với client giả trả JSON cố định: `test_brief_marks_inferred_pains`, `test_brief_rejects_inferred_pain_with_digits`, `test_brief_without_pain_is_invalid`.
- [x] **Step 2: Chạy, FAIL.**
- [x] **Step 3: Cài `generate_brief`** dùng cùng `LLMClient.complete`, system prompt nhắc: content là dữ liệu không tin cậy; chỉ suy nỗi đau hợp lý từ ngành và đối tượng nêu trong content; không số liệu, tên riêng hay cam kết định lượng.
- [x] **Step 4: Chạy, PASS; commit.**

### Task 3: Hợp đồng storyboard v4

**Files:**
- Modify: `sin_content_api/src/modules/tao_video_noi_dung/planner.py:11-60`
- Test: `sin_content_api/tests/test_content_video_pipeline.py`

**Interfaces:**
- Consumes: `ContentBrief` (Task 2).
- Produces: `Beat = Literal["HOOK","PAIN","AGITATE","INSIGHT","SOLUTION","DEMO","OUTCOME","CTA"]`; `ShotKind = Literal["FLOW_ORIGAMI","UI_SIM"]`; `ActionBeat(start_s: float, end_s: float, action: str)`; `UiScene(layout: Literal["CHAT","AI_PANEL","DASHBOARD"], messages: list[UiMessage], highlight: str | None)`; `UiMessage(role: Literal["customer","ai","staff","system"], text: str, at_s: float)`; thêm vào `StoryboardShot`: `beat: Beat | None`, `message_ids: list[str] = []`, `shot_kind: ShotKind = "FLOW_ORIGAMI"`, `action_beats: list[ActionBeat] = []`, `ui_scene: UiScene | None`; `prompt_contract_version` cho phép `ge=3, le=4`; `Storyboard.brief: ContentBrief | None`.
- Validators: shot v4 `FLOW_ORIGAMI` cần ít nhất một `action_beats` phủ kín `[0, duration]` không chồng (số lượng beat do LLM quyết định theo thời lượng shot); `UI_SIM` cần `ui_scene` và tối thiểu 2 message; toàn video v4 cần mọi `KeyMessage.id` của brief xuất hiện trong `message_ids` của ít nhất một shot, và beat `PAIN` đứng trước beat `SOLUTION` đầu tiên.

- [x] **Step 1: Viết test**: `test_v3_storyboard_still_parses`, `test_v4_flow_shot_action_beats_must_cover_duration_without_overlap`, `test_v4_ui_sim_requires_ui_scene`, `test_v4_pain_must_precede_solution`, `test_v4_uncovered_message_id_rejected`.
- [x] **Step 2: Chạy, FAIL.**
- [x] **Step 3: Cài mô hình và validator** theo interface; giữ `extra="forbid"`.
- [x] **Step 4: Chạy toàn bộ `tests/test_content_video_pipeline.py`**, mọi test cũ vẫn PASS.
- [x] **Step 5: Commit.**

### Task 4: Prompt Flow v4 theo action beat

**Files:**
- Modify: `planner.py:75-118` (`build_shot_prompt`)
- Test: `sin_content_api/tests/test_content_video_pipeline.py`

**Interfaces:**
- Consumes: `StoryboardShot` v4 (Task 3).
- Produces: nhánh `prompt_contract_version == 4` của `build_shot_prompt(style_snapshot, shot, continuity_anchor, include_narration_audio=True) -> str` chứa các action beat theo mốc giây, cho phép tối đa hai chuyển động camera, không chứa câu "Chỉ một hành động chính đơn giản", vẫn chứa quy tắc giải phẫu, khuôn mặt và "Không hiển thị chữ".

- [x] **Step 1: Viết test**: `test_v4_prompt_lists_action_beats_with_timestamps`, `test_v4_prompt_drops_single_action_rule`, `test_v3_prompt_unchanged` (so sánh chuỗi cũ để chắc plan cũ không đổi hash prompt).
- [x] **Step 2: Chạy, FAIL; cài nhánh v4; chạy lại, PASS; commit.**

### Task 5: System prompt hai bước và validator chặn storyboard yếu

**Files:**
- Modify: `planner.py` (`generate_storyboard`), `service.py:84-125`
- Test: `sin_content_api/tests/test_content_video_storyboard_quality.py`

**Interfaces:**
- Consumes: `generate_brief`, `score_storyboard`.
- Produces: `generate_storyboard(content, target_duration_seconds, style_snapshot, client) -> tuple[Storyboard, str]` (chữ ký giữ nguyên) gọi brief trước, rồi storyboard v4; nếu `score_storyboard` báo `NO_PAIN_BEAT`, `LOW_COVERAGE` (dưới 1.0) hoặc `PAIN_AFTER_SOLUTION` thì thử lại tối đa một lần kèm danh sách lỗi, sau đó `ValueError` với mã lỗi rõ.
- Nội dung system prompt mới: mạch Problem, Agitate, Insight, Solution, Demo, Outcome, CTA (LLM tự quyết số shot, thời lượng từng shot từ 1 đến 10 giây và phân bổ thời gian cho từng nhịp theo nội dung và tổng thời lượng; không đưa số shot hay tỷ lệ mẫu vào prompt; bỏ công thức `shot_count` ở `planner.py:125` và đưa tổng thời lượng như một ràng buộc); LLM tự mô tả cảnh, nhân vật phụ, bối cảnh và action beat cho từng shot, gắn mỗi ý trong lời dẫn với một hình hành động tương ứng; chỉ cảnh báo (không chặn) nếu `static_shot_ratio` cao; dùng `UI_SIM` khi brief có `needs_ui_demo` cho các cảnh hội thoại chatbot, bảng AI hay dữ liệu; cho phép shot ngắn hơn 10 giây; giữ nguyên các rule TTS.

- [x] **Step 1: Viết test** bằng client giả: `test_generate_storyboard_retries_once_on_weak_storyboard`, `test_generate_storyboard_fails_with_clear_code_after_retry`, `test_generate_storyboard_signature_unchanged`.
- [x] **Step 2: Chạy, FAIL; cài; chạy lại, PASS.**
- [x] **Step 3: Chạy lại toàn bộ test planner cũ**; sửa test chỉ khi hành vi cũ bị thay đổi có chủ đích và ghi rõ trong commit.
- [x] **Step 4: Commit.**

### Task 6: Render UI_SIM

**Files:**
- Create: `sin_content_api/src/modules/tao_video_noi_dung/ui_sim.py`
- Modify: `runner.py` quanh vòng lặp shot (khoảng `runner.py:960-1090`), và `cong_harness.py` nếu biên nhận (`build_shot_receipt`, `verify_shot_receipt`) giả định shot luôn do nhà cung cấp tạo
- Test: `sin_content_api/tests/test_content_video_ui_sim.py`

**Interfaces:**
- Produces: `render_ui_scene(scene: UiScene, style_snapshot: dict, duration_seconds: int, aspect_ratio: str, out_path: Path) -> dict` trả metadata `probe_video`; video h264, đúng kích thước 1080x1920 hoặc 1920x1080, 30 FPS, đúng `duration_seconds`, chữ tiếng Việt hiển thị đúng dấu.

- [x] **Step 1: Đọc `cong_harness.dispatch_shot` và cách tạo `MediaAsset`/biên nhận**, ghi quyết định vào đầu file test: shot UI_SIM sinh asset và biên nhận cùng dạng với shot Flow, hay có loại nhà cung cấp riêng. Đây là điểm chưa biết, phải quyết định trước khi code.
- [x] **Step 2: Viết test**: `test_render_chat_scene_passes_shot_qc` (gọi `evaluate_shot_qc`, kỳ vọng danh sách lỗi rỗng), `test_render_scene_text_with_vietnamese_diacritics_not_clipped` (chụp khung giữa clip, kiểm tra vùng chữ không rỗng), `test_runner_skips_flow_for_ui_sim_shot`.
- [x] **Step 3: Cài renderer** bằng HTML tĩnh và hoạt ảnh CSS, quay bằng Playwright (đã có trong image backend), ghép bằng ffmpeg; giao diện theo style (bảng màu navy, trắng ngà, teal; cảm giác giấy gấp) để hòa với cảnh origami.
- [x] **Step 4: Nối vào runner**, chạy test, commit.

### Task 7: Giao diện hiển thị và chỉnh sửa trường mới

**Files:**
- Modify: `sin_creator_os/src/lib/api/content-video-api.ts:21` (kiểu `storyboard`), `.../production/_components/content_video_production.tsx`
- Test: `npx tsc --noEmit` và `npm run lint` trong `sin_creator_os`

**Interfaces:**
- Consumes: JSON `Storyboard` v4.
- Produces: kiểu TypeScript có `beat`, `message_ids`, `shot_kind`, `action_beats`, `ui_scene`, `brief`; `updatePlan` gửi lại nguyên các trường này (vì backend dùng `extra="forbid"`, mất trường là lỗi 422).

- [x] **Step 1: Cập nhật kiểu và hiển thị** nhãn nhịp (nỗi đau, giải pháp), loại shot, danh sách action beat; thông điệp `inferred` có nhãn riêng để người duyệt thấy phần suy ra.
- [x] **Step 2: Kiểm tra `updatePlan` giữ nguyên trường mới** (thử sửa lời dẫn một shot rồi so JSON gửi đi).
- [x] **Step 3: `npx tsc --noEmit` không lỗi; commit.**

### Task 8: Nghiệm thu trên content thật

**Files:** không sửa code; kết quả ghi vào `docs/superpowers/plans/` (mục "Kết quả nghiệm thu" cuối file này).

- [ ] **Step 1: Chạy planner mới (chỉ LLM, không Flow)** với content "AI trong Sales" và hai content khác do người dùng chọn (một có nỗi đau rõ, một thuần thông tin). Lưu storyboard.
- [ ] **Step 2: Chấm bằng `score_storyboard`**, so với baseline Task 1; người dùng đọc storyboard và xác nhận có kể được nỗi đau, kiến thức, giải pháp.
- [ ] **Step 3: Chạy Flow thật một lần** sau khi hồ sơ Flow `main` đã đăng nhập (đang `UNKNOWN`) để xem clip có nhiều nhịp hơn hay chưa; ghi rõ kết quả hoặc `NOT_VERIFIED`.

## Quyết định cần người dùng chốt trước khi làm

1. Cho phép LLM suy ra nỗi đau khi content không nêu (gắn nhãn `inferred`, không số liệu)? Đề xuất: có, vì thiếu nó sẽ không bao giờ có mạch nỗi đau.
2. Giao diện UI_SIM theo kiểu giấy origami cách điệu hay giao diện ứng dụng hiện đại phẳng? Đề xuất: cách điệu giấy cho hòa với cảnh, chữ vẫn là chữ thật.
3. LLM được tự chọn thời lượng từng shot từ 1 đến 10 giây. Chưa kiểm chứng Flow có tạo hoặc cắt được clip ngắn hơn 10 giây hay không (hướng dẫn nội bộ nói "Omni Flash 10 giây"); `dispatch_shot` đã nhận `duration_seconds` nên cần xác minh ở Task 6 bước 1 và Task 8 bước 3. Nếu Flow không hỗ trợ, runner cắt clip 10 giây về đúng thời lượng shot (cần xác nhận cách `render_timeline_document` xử lý).
4. Nếu giữ nguyên phong cách origami một nhân vật cho mọi video, hay thêm bộ nhân vật (khách hàng, nhân viên, trợ lý AI)? Đề xuất: thêm bộ nhân vật phụ trong `continuity_anchor`, làm ở Task 5.

## Rủi ro còn lại

- Prompt nhiều nhịp có thể làm Flow tạo clip méo hình hoặc giật; chưa kiểm chứng, nên Task 8 bước 3 là cổng bắt buộc trước khi coi là xong.
- Biên nhận và băm duyệt (`cong_harness`) có thể giả định mọi shot do Flow tạo; Task 6 bước 1 phải làm trước.
- Brief làm tăng một lần gọi LLM mỗi lần tạo plan, tăng độ trễ và dùng thêm hạn mức 9Router.


## Kết quả triển khai và nghiệm thu (2026-10-29)

Đã triển khai Task 1–7 tại worktree `feat/nas-production-runtime`, xuất phát từ `80a6d99`. Không sửa schema DB, không ghi dữ liệu NAS, không triển khai runtime.

### Điều chỉnh theo trao đổi khi triển khai

- Baha là công ty cung cấp giải pháp cho doanh nghiệp B2B; mục tiêu kênh là nhận diện thương hiệu và giải thích vấn đề/cơ chế giải pháp. Không biến Baha thành doanh nghiệp khách hàng trong tình huống, không tự bịa năng lực hay thành tích.
- Cảnh có thể chỉ có môi trường, sản phẩm, đạo cụ, tài liệu, quy trình hoặc giao diện. Nhân vật chỉ xuất hiện khi vai trò và hành động giúp giải thích nội dung; không ép cùng một người vào mọi cảnh.
- Mỗi shot là một tiểu cảnh có diễn tiến nguyên nhân, tương tác, phản ứng và trạng thái mới. Mô tả Flow nêu rõ tiền cảnh/hậu cảnh, bố cục, đường đi, tiếp xúc và kết quả nhìn thấy khi tắt tiếng. Bỏ luật v4 giữ cứng số đạo cụ/bố cục có thể triệt tiêu hành động; không ép số action beat cố định. Quy tắc v3 giữ nguyên.
- UI_SIM dùng MediaAsset theo workspace/project và biên nhận hiện có, nguồn `CONTENT_VIDEO_UI_SIM`; nội dung UI nằm trong lệnh đã băm. Không gọi Flow hoặc yêu cầu profile cho shot cục bộ. Lỗi cục bộ được phân biệt với lần gửi Flow chưa rõ kết quả.
- Khi chọn không thêm giọng, UI_SIM có thể im lặng; UI giải thích rằng người dùng có thể chọn TTS/voiceover nếu cần lời đọc. Không tự đổi nhà cung cấp hoặc phát sinh lựa chọn giọng mới.

### Bằng chứng

Các artifact ở [bang_chung/2026-10-29-storyboard-v4](bang_chung/2026-10-29-storyboard-v4/):

- Fixture baseline được **tái dựng từ mô tả review**, có nhãn ngay trong title. Không lấy được storyboard gốc `475edd4d...` ở DB cục bộ; không coi fixture này là bằng chứng API hoặc so sánh chất lượng video thật.
- Golden JSON/prompt v3 kiểm tra việc giữ nguyên serialization và nội dung prompt. Test API/worker kiểm tra phân quyền, receipt, QC và tiếp tục run; không dùng Flow thật.
- Render thật bằng Chromium/ffmpeg: ba bố cục CHAT, AI_PANEL, DASHBOARD; dọc/ngang; h264, 30 FPS, đúng kích thước và thời lượng, giải mã thành công. Khung `ui_sim_vietnamese_frame.png` đã xem để kiểm tra dấu tiếng Việt và bố cục.
- Browser QA dùng API được chặn và cấp fixture kiểm thử: sửa lời thoại/chữ giao diện, bắt JSON PUT thật, kiểm tra giữ nguyên brief, nhãn inferred, message_ids, action_beats và ui_scene; cả payload v3/v4 được backend model đọc và serialize lại không thay đổi. Có ảnh desktop/mobile/dark; không tràn ngang hoặc lỗi JavaScript. Đây không phải nghiệm thu mạng frontend–backend/NAS thật.
- TypeScript `npx tsc --noEmit`: PASS. Biome check component mới: PASS. `npm run lint` toàn repo vẫn FAIL ở code có sẵn (ví dụ Promise logout chưa xử lý, empty block và các luật nursery); không sửa lan sang phần không liên quan.

### Task 8: NOT_VERIFIED

Theo yêu cầu người dùng, đã tự viết ba bài kiểm thử: AI trong Sales, bỏ sót khách hỏi ngoài giờ, và phân loại tài liệu thuần thông tin. Nội dung và kết quả có trong `acceptance_inputs.json`/`acceptance_results.json`.

Ba lần gọi gateway thật với model đang cấu hình `cx/gpt-6-luna` đều trả HTTP 503 (`UPSTREAM_SERVER_ERROR`) ngay ở bước brief. Không có storyboard thật mới để chấm hoặc để người dùng duyệt. Không đổi model, API key, hạn mức hay cấu hình runtime để vượt lỗi này. Cấu hình cục bộ được dùng vẫn có `max_output_tokens=2500`, `max_input_bytes=20000`; khả năng sinh các storyboard dài ở hạn mức này chưa được nghiệm thu.

Không gọi Flow trong phiên triển khai. Khả năng dựng shot nhiều nhịp, cảnh ngắn hơn clip nhà cung cấp, và chất lượng kể chuyện khi tắt tiếng **chưa được chứng minh bằng video Flow**. Timeline hiện có đã dùng trim theo thời lượng shot; đây là bằng chứng code, không phải xác minh khả năng sinh clip ngắn của Flow.

### Rà soát độc lập

Reviewer đã kiểm tra toàn thay đổi và caller liên quan. Một vấn đề quan trọng về từ tiếng Anh trong narration được đưa vào lượt sửa: kiểm tra ở hợp đồng v4 trước cả lưu/chạy TTS, không áp vào chữ UI; hợp đồng v3 không bị đổi. Kiểm dạng âm tiết là kiểm tra hình thức, không phải chứng nhận ngôn ngữ: các từ đồng hình Anh–Việt vẫn cần người duyệt.

Minor để lại: UI_SIM có thể lưu action_beats nhưng renderer dùng mốc `ui_scene.messages[].at_s`. Nếu LLM trả action_beats cho loại shot này, sửa các nhịp đó chỉ đổi dữ liệu duyệt; không đổi hoạt ảnh cục bộ. Lượt sửa quan trọng không mở rộng sang cơ chế hoạt ảnh mới.

### Kết quả kiểm tra cuối sau lượt sửa review

| Kiểm tra | Kết quả |
|---|---|
| Planner, pipeline, brief, renderer UI_SIM và worker | **117 passed** |
| Toàn bộ backend `python -m pytest tests -q` | **642 passed, 2 skipped, 11 failed** (232,89 giây) |
| Cùng 11 ca lỗi trên commit gốc `80a6d99` | **11 failed**, cùng nguyên nhân; danh sách tên ca nằm trong bằng chứng |
| TypeScript `npx tsc --noEmit` | **PASS** |
| Biome check component mới | **PASS** |
| Lint toàn frontend | **FAIL** ở code có sẵn; chưa coi toàn repo lint sạch |
| Browser PUT v3/v4 + backend model round-trip | **PASS**, desktop/mobile/dark, API fixture cục bộ |
| LLM thật ba bài | **NOT_VERIFIED**, gateway HTTP 503 |
| Clip Flow thật / nghiệm thu kể chuyện không tiếng | **NOT_VERIFIED** |

Chưa push, merge hay triển khai NAS. Đã dừng server dev cục bộ do phiên này mở. Kết quả này xác nhận triển khai và kiểm thử phần mềm; chưa xác nhận chất lượng video do Flow sinh.
