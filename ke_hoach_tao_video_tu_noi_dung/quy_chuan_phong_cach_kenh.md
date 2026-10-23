# Quy chuẩn phong cách công ty và kênh

Trạng thái: ĐỀ XUẤT ĐỂ DUYỆT, ngày 23/10/2026. Đây là hợp đồng thiết kế bổ sung cho `dac_ta_bo_tao_video_hoan_chinh.md`, `ke_hoach_trien_khai_va_checklist.md` và `ma_tran_nghiem_thu.md`; chưa có runtime, profile thương hiệu hay video mẫu được nghiệm thu. Các khóa cấu trúc dưới đây là tên hợp đồng dự kiến, không phải API đã có.

## 1. Mục tiêu và nguyên tắc khóa phong cách

Mỗi công ty có bộ nhận diện làm nguồn chân lý duy nhất; mỗi kênh gắn một phiên bản phong cách đã duyệt. Hai video khác chủ đề trên cùng kênh phải nhận ra cùng một hệ hình ảnh, chữ, lời đọc và nhịp dựng. Nội dung mới không phải lý do để tự đổi logo, bảng màu, giọng hoặc trường phái tạo hình.

Luồng bắt buộc: nội dung → harness điều phối và LLM → kế hoạch có cấu trúc → kiểm tra phong cách và duyệt → tạo tư liệu bằng Flow hoặc adapter phù hợp → dựng → QC và duyệt thành phẩm. Không cho content, prompt tự nhập, chế độ tạo lại cảnh hoặc endpoint clip cũ đi vòng qua bước này khi asset sẽ được dùng trong run sản xuất theo kênh. Công cụ tạo asset riêng vẫn có thể tồn tại, nhưng asset nhập vào run phải qua cùng kiểm tra và truy vết.

Harness là lớp thực thi quy tắc: đọc cấu hình đã duyệt, phân giải token, kiểm schema/quyền/hash/ngân sách, ghi snapshot và quyết định có được gọi provider. LLM đề xuất kịch bản, bố cục và prompt trong miền cho phép; LLM không được tự cấp quyền ngoại lệ hoặc tự đánh dấu profile đã duyệt. Flow nhận prompt từng shot đã biên dịch từ kế hoạch hợp lệ, không nhận nguyên content để tự chọn phong cách toàn phim.

## 2. Phân cấp và cơ chế phiên bản

| Lớp | Trách nhiệm và giới hạn |
|---|---|
| `company_style` | SSOT nhận diện của công ty: logo, màu, chữ, giọng, tài sản chuẩn, luật cấm và miền biến thể. Phiên bản đã duyệt bất biến. |
| `channel_binding` | Gắn đúng `company_id`, `channel_id`, `company_style_version_id` và `style_family_version_id`; thêm preset riêng đã được công ty cho phép. Không tham chiếu `latest`. |
| `series_variant` | Chỉ chọn token nằm trong danh sách cho phép của binding, chẳng hạn kiểu sơ đồ hoặc nhịp kể trong khoảng đã duyệt. Không thay nhận diện nền. |
| `scene_override` | Chỉ điều chỉnh trường được khai báo rõ theo loại cảnh, chẳng hạn mức zoom của recording hoặc bố cục sơ đồ. Không được đổi logo/màu/giọng/grade. |

Thứ tự ưu tiên ràng buộc là công ty > kênh > series > cảnh. Lớp thấp chỉ điền giá trị hoặc thu hẹp miền biến thể đã được lớp cao cấp phép; không dùng quy tắc “giá trị cuối cùng thắng”. Hai ràng buộc không giao nhau phải báo xung đột và chặn, không tự chọn một bên. `allowed_overrides` phải liệt kê đường dẫn trường, phạm vi, tập giá trị hoặc khoảng và người có quyền duyệt; trường không được liệt kê mặc định bị khóa.

Mỗi thay đổi có nghĩa tạo phiên bản mới với diff, lý do, người đề xuất, người duyệt, thời điểm duyệt và `effective_at`. Không sửa trực tiếp nội dung phiên bản đã duyệt. Phiên bản bị thu hồi có lý do và thời điểm; dừng sản xuất/xuất mới nếu liên quan quyền tài sản hoặc nhận diện sai, giữ artifact cũ để đối soát. Ngày hiệu lực chỉ áp dụng cho run mới đủ điều kiện, không tự nâng phiên bản run đang chạy.

Khi chốt kế hoạch, harness phân giải toàn bộ profile, binding, series và override thành `resolved_style_snapshot`; khóa hash SHA-256 của biểu diễn JSON chuẩn hóa cùng hash từng tài sản và phiên bản compiler/template. Dùng quy tắc chuẩn hóa duy nhất có version, sắp khóa, UTF-8 và số biểu diễn thống nhất. `run_id` tham chiếu snapshot/hash này từ đầu tới cuối, kể cả resume, retry, tạo lại cảnh, render và export. Worker không đọc lại `latest` giữa run. Tài sản chỉ được đọc nếu bytes khớp hash đã khóa.

Muốn đổi phong cách sau duyệt phải tạo revision kế hoạch và snapshot mới, hiển thị diff, vô hiệu approval/asset phụ thuộc và xin duyệt lại. Không trộn shot cũ với style mới âm thầm. Đổi binding có kiểm soát giữ lịch sử video trước/sau; run hiện hữu tiếp tục snapshot cũ nếu phiên bản vẫn hợp lệ, hoặc bị chặn rõ lý do nếu đã thu hồi.

Hợp đồng runtime chuẩn duy nhất là `KhoaPhongCach` trong `hop_dong_harness_llm_truoc_flow.md`. Các tên `company_style`, `channel_binding`, `resolved_style_snapshot` dưới đây mô tả profile cấu hình và ví dụ lưu trữ, không phải cho phép tạo type run song song: resolver ánh xạ company/profile ID và version sang `cong_ty_style_id`/`cong_ty_style_version`, channel sang `kenh_id`/`kenh_binding_revision`, snapshot/hash sang `style_snapshot`/`style_snapshot_hash`. Family/version và các tham chiếu nằm trong `style_snapshot` đã chuẩn hóa. Một resolver và một schema version do integrator đóng băng; không duy trì hai nguồn style cạnh tranh.

## 3. Hồ sơ phong cách bắt buộc

Các nhóm dưới đây phải có giá trị được duyệt hoặc trạng thái thiếu rõ ràng. `null`, tài sản mẫu và tên đề xuất không được coi là đã duyệt. Trường không dùng phải ghi `NOT_APPLICABLE` kèm lý do; không để rỗng gây rơi về mặc định provider.

| Nhóm khóa | Nội dung phải lưu và kiểm |
|---|---|
| `identity`, `governance` | `company_id`, `style_id`, `version_id`, tên, trạng thái DRAFT/IN_REVIEW/APPROVED/REVOKED, owner, reviewer, timestamps, `effective_at`, lý do/diff, hash, nguồn phê duyệt. |
| `logo_assets` | Asset ID logo thật do công ty cung cấp, phiên bản, SHA-256, định dạng, biến thể nền sáng/tối, quyền sử dụng, clear space, kích thước nhỏ nhất, vị trí được phép. Không yêu cầu AI vẽ lại hoặc sinh logo trong clip. |
| `palette` | Token ngữ nghĩa nền/chữ/nhấn/trạng thái với giá trị màu chính xác, cặp tương phản đã kiểm, miền sử dụng và tỷ lệ nhấn được duyệt. Không suy màu chính thức từ tên công ty hoặc ảnh tìm kiếm. |
| `typography` | Font asset ID/hash, họ/weight, hỗ trợ dấu tiếng Việt, bằng chứng license/quyền nhúng, fallback được duyệt, cỡ chữ/line height/phân cấp, template chữ tham chiếu có version/hash. Thiếu font thì chặn hoặc dùng fallback đã duyệt. |
| `layout`, `captions` | Grid, lề, vị trí logo/tiêu đề/caption/CTA, kích thước bounding box, kiểu nền caption, số dòng, cỡ chữ, giới hạn đọc, safe area theo tỷ lệ và độ phân giải. |
| `voice`, `pronunciation` | Provider/product surface, voice ID và version/cấu hình được phép, ngôn ngữ, âm sắc tham chiếu đã duyệt, tốc độ/khoảng nghỉ trong miền cho phép, từ điển phát âm BAHA và thuật ngữ có version, sample/hash và quyền dùng giọng. Không tự clone hoặc chọn giọng thay thế. |
| `music`, `pacing` | Nhạc/nhóm nhạc được phép, asset/license/hash, nhịp độ và mức năng lượng, luật ducking/đầu-cuối, khoảng độ dài shot, nhịp nghỉ và chuyển ý. Có chế độ không nhạc đã duyệt; không tự thêm nhạc từ nguồn chưa rõ quyền. |
| `visual_direction` | Ngôn ngữ tạo hình, bố cục, độ chi tiết, chất liệu, chủ thể, cách minh họa công nghệ, tham chiếu chuẩn và giới hạn hình AI so với bằng chứng thật. |
| `camera`, `lighting`, `color` | Preset góc máy, chuyển động và mức rung, lens/perspective được phép, ánh sáng, tương phản/nhiệt độ màu, color grade/LUT có version/hash và miền chỉnh. Trường quay thật và đồ họa có quy tắc tương ứng, không ép sơ đồ có lens giả. |
| `negative_prompt` | Các điều cấm chung và riêng loại shot, ví dụ không sinh chữ/logo, không đổi nhận diện, không thêm giao diện giả; phiên bản và mapping adapter. Negative prompt hỗ trợ chỉ dẫn, không thay kiểm tra đầu ra. |
| `formats`, `transitions`, `outro` | Tỷ lệ, độ phân giải/fps, template theo format, danh sách transition và giới hạn thời lượng, outro O1/O2/O3 được phép, logo/CTA/claim đã duyệt, tổng thời gian outro nằm trong thời lượng đích. |
| `reference_assets`, `templates` | Bộ ảnh/video/audio mẫu chuẩn, contact sheet, template sơ đồ/recording/title/outro, ID/version/hash, provenance/license, hạn dùng, nguồn approval và nơi lưu được phân quyền. URL biến đổi không thay asset bất biến. |
| `variation_policy`, `qc_policy` | Token cho phép thay đổi theo series/cảnh, giới hạn, tiêu chí hard/soft, rubric reviewer, ngưỡng đề xuất, ngân sách sửa/retry và điều kiện chặn. |

Pilot dọc kế thừa 1080 × 1920, 30 fps; vùng an toàn tối thiểu trên 150 px, dưới 320 px, phải 120 px và lề trái đề xuất 60 px. Logo, chữ và CTA phải có bounding box nằm trong vùng cho phép, không chỉ đúng điểm neo. Phụ đề dự kiến tối đa 2 dòng, 38 ký tự/dòng, tối đa 20 ký tự/giây, cue 0,7–6 giây và đo kích thước thực bằng font đã khóa. Thông số đề xuất phải được duyệt ở G1; profile không được nới vượt ràng buộc dự án. Preset ngang/tỷ lệ mới cần safe area và nghiệm thu riêng.

Thiếu logo, palette, font, giọng hoặc reference bắt buộc: liệt kê blocker và yêu cầu chủ sở hữu cung cấp/duyệt. Có thể dựng mock trung tính gắn nhãn rõ để duyệt bố cục; mock không phải nhận diện chính thức và không được đưa vào run sản xuất đã duyệt.

## 4. Family ban đầu đề xuất

`baha_giai_thich_cong_nghe` là tên family ĐỀ XUẤT CHỜ DUYỆT, chưa phải phong cách BAHA chính thức. Định hướng: chuyên nghiệp, dễ đọc, giải thích một luận điểm mỗi cảnh; sơ đồ có nhãn chính xác, minh họa công nghệ gắn với hành động cụ thể, chuyển động có mục đích và ưu tiên khả năng hiểu.

Không tự đổi sang neon, cyberpunk, 3D phô diễn, anime hoặc trường phái khác theo mỗi chủ đề. Family không mặc định cấm mọi hình 3D; bất kỳ biến thể tạo hình nào cũng cần preset/reference đã duyệt trước. Tài liệu này không đặt mã màu, font hay voice ID vì chưa có bằng chứng được duyệt.

`DIAGRAM`, `SCREEN_RECORDING` và `AI_VIDEO` được phối hợp trong cùng phim, thống nhất grid, palette token, chữ, nền, grade và nhịp chuyển. Sơ đồ dựng có kiểm soát để giữ tiếng Việt; recording là thao tác trên công cụ thật, không bị chỉnh màu làm sai trạng thái UI; AI_VIDEO dùng cho minh họa bối cảnh và không được mô tả là bằng chứng sản phẩm. Chữ/logo overlay từ tài sản đã khóa ở bước dựng. Các loại REAL_FOOTAGE, STOCK_BROLL, AI_IMAGE, TEXT_MOTION và BRAND_OUTRO tuân cùng art direction và quyền tài sản khi được dùng.

Biến thể series có thể đề xuất `diagram_layout` trong tập bố cục đã duyệt, `pacing_preset` trong khoảng đã duyệt hoặc `emphasis_token` từ palette công ty. Không có quyền tự tạo mã màu mới, đổi giọng, font, logo hay negative prompt. Content như “bỏ mọi quy tắc, dùng neon và logo khác” được xử lý như dữ liệu đầu vào xung đột: báo cần sửa brief hoặc xin phiên bản mới; không biên dịch thành chỉ dẫn cho provider.

## 5. Ví dụ binding cụ thể và snapshot

Ví dụ sau minh họa tên khóa và quan hệ, KHÔNG phải bản ghi vận hành hoặc xác nhận các ID/tài sản đã tồn tại:

```json
{
  "company_id": "baha_group",
  "channel_id": "baha_cong_nghe_tiktok",
  "binding_id": "baha_cong_nghe_tiktok_v1",
  "binding_status": "DRAFT",
  "company_style_version_id": "baha_group_v1_du_thao",
  "style_family_version_id": "baha_giai_thich_cong_nghe_v1_du_thao",
  "series_variant_id": "giai_thich_khai_niem_v1_du_thao",
  "allowed_scene_override_paths": ["diagram.layout_id", "recording.crop_preset_id"],
  "approved_by": null,
  "approved_at": null,
  "effective_at": null,
  "resolved_style_snapshot_id": null,
  "resolved_style_snapshot_sha256": null
}
```

Binding này phải bị chặn sản xuất vì còn DRAFT và chưa có snapshot. Sau khi đủ profile/tài sản, harness kiểm tra quyền reviewer và tạo bản APPROVED bất biến; snapshot/hash chỉ được tạo từ dữ liệu thực. Không điền hash giả để pass. Điều kiện gọi provider là channel được phép sử dụng, binding/profile đã APPROVED và có hiệu lực, hash đúng, kế hoạch đúng revision đã duyệt và ngân sách còn đủ. Kênh đã được duyệt vận hành nhưng chưa có phong cách được duyệt vẫn phải chặn với lỗi rõ `CHUA_CO_PHONG_CACH_DUOC_DUYET`; không kế thừa style kênh gần giống hoặc style mặc định toàn hệ thống.

Quản trị có màn hình xem trước profile, so sánh diff, duyệt/thu hồi, lịch hiệu lực và danh sách kênh/run chịu ảnh hưởng. Phân quyền đề xuất/dùng/duyệt theo quyền hiện hữu được kiểm định; không tự tạo hoặc nới quyền production. Mọi thao tác ghi actor, thời điểm, revision/hash và lý do; việc duyệt là hành động có chủ ý trên đúng artifact.

## 6. Kiểm định, sửa và review pack

Kiểm cứng trước gọi Flow: schema đủ, quan hệ công ty/kênh đúng quyền, binding/profile APPROVED hiệu lực, hash khớp, token override hợp lệ, license còn hiệu lực, tham chiếu thật, kế hoạch bao phủ nội dung và ngân sách đủ. Phát hiện yêu cầu prompt phá nhận diện phải tạo blocker. Kiểm lại ở từng lần resume/retry và trước render/xuất; không tái phân giải sang phiên bản khác.

Kiểm cứng đầu ra: manifest có cùng snapshot/hash, overlay logo đúng asset/hash, palette/font/template ở lớp dựng đúng token, tỷ lệ/fps/thời lượng/safe area/caption/âm thanh đạt chuẩn, transition/outro đúng preset, không thiếu asset hay provenance. Những gì không thể đo từ pixel một cách chắc chắn không được ghi là đã pass bằng regex hoặc chỉ metadata. Clip AI có logo/chữ giả, đổi nhân vật hoặc sai hướng hình ảnh phải bị phát hiện qua review kết hợp.

AI đánh giá style drift trên các khung đại diện, điểm nối cảnh và âm thanh so với reference/rubric: độ nhất quán tạo hình, chất liệu, ánh sáng/grade, nhịp, giọng, tính rõ ràng và nội dung minh họa. Lưu model/version, đầu vào/hash, nhận xét theo timecode và mức không chắc chắn. Điểm AI chỉ hỗ trợ xếp thứ tự kiểm; người duyệt phải xem/nghe phim, so với mẫu chuẩn và xác nhận từng lỗi còn mở. Không dùng một điểm tổng để vượt blocker, không tuyên bố mô hình sinh video deterministic hoặc hash prompt bảo đảm hình ảnh đồng nhất.

Review pack G1 gồm storyboard, style board, frame mẫu và sample giọng; pack nghiệm thu sản xuất gồm 3 video khác chủ đề cùng binding/snapshot: AI Agent và Chatbot 60 giây; RAG và Fine-tuning 120 giây; workflow doanh nghiệp 120 giây. Mỗi phim có contact sheet, manifest/hash, mẫu cạnh nhau với video trước, QC tự động, nhận xét AI, reviewer/ngày/quyết định và lỗi theo timecode. Khi chưa tạo video thật phải ghi đó là mẫu kế hoạch, không gọi là pack đã nghiệm thu.

Mỗi lỗi phong cách có tối đa 2 lượt sửa/tạo lại tự động sau lần tạo đầu, trong trần chi phí/credit và thời gian run đã duyệt. Mỗi lượt ghi nguyên nhân, cảnh chịu tác động, diff prompt/token, chi phí và reviewer đánh giá kết quả; không sửa cả phim khi chỉ một cảnh sai. Chỉ thực hiện khi xác định retry an toàn, không nộp lại mù khi provider chưa rõ trạng thái. Hết ngân sách, hết 2 lượt hoặc lỗi chưa giải quyết thì chuyển chờ reviewer, cho lựa chọn sửa kế hoạch, cung cấp tư liệu hoặc duyệt ngân sách/lượt thủ công mới; không lặp vô hạn hoặc tự hạ chuẩn. Giới hạn này không thay chính sách retry lỗi hạ tầng; mọi loại retry vẫn cộng vào cùng cost ledger.

## 7. Điều kiện nghiệm thu xuyên gate

| Gate | Công việc bắt buộc và bằng chứng cần có |
|---|---|
| G1 | Founder duyệt style board/profile/family, binding mẫu, màn hình quản trị, storyboard 3 chủ đề và rubric; ghi phần thiếu tài sản. Chưa duyệt thì chưa backend nặng. |
| G3 | Harness + LLM lập kế hoạch theo snapshot, kiểm phân cấp/override, prompt riêng từng shot, không cho content bypass; test mapping nội dung và xung đột style. |
| G4 | Voice/phát âm, pacing và timing dùng phiên bản đã khóa; audio sample thật, alignment/caption và ngân sách thời lượng có reviewer. Không đổi giọng khi thiếu quyền provider. |
| G5 | Chỉ gọi Flow/adapter sau preflight; lưu prompt chuẩn hóa/prompt adapter/reference/hash, model/capability và chi phí; kiểm các loại tư liệu cùng art direction. |
| G7 | QC file/render, đối chiếu video trước/sau và review pack 3 chủ đề; hard checks pass, style drift được người duyệt xử lý, approval gắn hash chính xác. |

G2 phải lưu được hợp đồng phiên bản/snapshot và audit; G6 giữ token trong timeline/render/package; G8 hiển thị blocker/phiên bản/duyệt đúng revision; G9 chỉ nghiệm thu pilot khi các bằng chứng trên có thật. Không đánh dấu gate pass bằng sự tồn tại của tài liệu này.

## 8. Checklist triển khai và kiểm thử bắt buộc

- [ ] Có tài sản thương hiệu thật và license/font/voice/reference được chủ sở hữu duyệt; không dùng giá trị bịa hoặc mock để mở sản xuất.
- [ ] Profile đã duyệt bất biến; sửa tạo revision mới, có diff, actor, thời điểm và hash; future effective date chưa được dùng trước giờ.
- [ ] Kênh được duyệt nhưng thiếu style bị chặn; binding nhầm công ty/kênh hoặc không đủ quyền bị từ chối.
- [ ] Series/cảnh chỉ override token được cấp; unknown key, màu/logo/giọng trái phép hoặc xung đột miền bị chặn, kể cả khi prompt yêu cầu bỏ quy tắc.
- [ ] Đổi binding/profile trong lúc run hoạt động không đổi snapshot của run; resume, tạo lại cảnh và export giữ hash cũ hoặc chặn khi version thu hồi.
- [ ] Asset cùng ID nhưng bytes đổi hash bị chặn; font/reference/license thiếu hoặc hết hiệu lực không âm thầm fallback.
- [ ] LLM bỏ trường, output malformed hoặc đề xuất sai style không gọi Flow; prompt adapter giữ đúng ràng buộc đã biên dịch và được lưu để đối soát.
- [ ] DIAGRAM, SCREEN_RECORDING và AI_VIDEO cùng phim qua review nhất quán; recording thật không biến thành UI minh họa giả.
- [ ] Kiểm bounding box logo/caption ở frame thật, chữ tiếng Việt, âm thanh/giọng/phát âm và outro; metadata đúng nhưng hình sai vẫn không pass.
- [ ] Ba video khác chủ đề dùng cùng snapshot qua kiểm cứng và reviewer; AI score cao nhưng người kiểm phát hiện drift vẫn chặn.
- [ ] Retry lần thứ ba tự động bị từ chối; budget hết dừng trước submit; trường hợp provider chưa rõ trạng thái được đối soát trước tạo lại.
- [ ] Đổi style làm approval liên quan mất hiệu lực; bản cũ giữ để rollback, không trộn phiên bản và không xóa lịch sử.
- [ ] Gói xuất có profile/binding/snapshot hash, reference manifest, QC và quyết định reviewer, không chứa cookie/key hoặc dữ liệu giọng ngoài quyền được phép.

Toàn bộ checklist hiện chưa được chạy cho runtime. Khi thi công, lưu test/log/run ID và review pack trong vùng ghi được phép; người phụ trách đưa bằng chứng nghiệm thu chính thức vào `08_kiem_thu/bang_chung/` theo quy định dự án. Không coi tài liệu thiết kế này là bằng chứng độ đồng nhất của mô hình hoặc kết quả video thực.
