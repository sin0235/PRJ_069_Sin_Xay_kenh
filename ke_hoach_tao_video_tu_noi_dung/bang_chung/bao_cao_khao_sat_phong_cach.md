# Báo cáo khảo sát phong cách Baha Explainer G0/G1

Ngày khảo sát: 23/10/2026  
Phạm vi: đọc tài sản nhận diện, tài liệu định hướng và cấu trúc schema trong vùng làm việc; không đọc giá trị bản ghi nghiệp vụ trong cơ sở dữ liệu, không mở WAL, không chạy provider, Flow hoặc kiểm thử. Báo cáo này là đầu vào đề xuất cho Founder, chưa phải style board được duyệt.

## Kết luận

Dự án có một logo BAHA đang dùng trên giao diện web và bộ màu giao diện hiện hữu. Đây là bằng chứng về tài sản/triển khai giao diện, chưa đủ bằng chứng về quyền sử dụng, phiên bản thương hiệu hoặc phê duyệt profile video. Tài liệu `quy_chuan_phong_cach_kenh.md` đã nêu rõ family `baha_giai_thich_cong_nghe` đang chờ duyệt và không ấn định mã màu, font hay voice ID. Vì vậy style board có thể thống nhất cách kể và bố cục, còn màu chính thức, font, giọng, nhạc và outro phải để Founder lựa chọn hoặc cung cấp.

Mẫu hình ảnh phù hợp để đưa vào G1 là explainer biên tập, rõ ràng, đáng tin: mỗi cảnh giải thích một luận điểm; sơ đồ gọn có nhãn chính xác; màn hình ghi lại dùng sản phẩm thật; hình AI chỉ minh họa bối cảnh; chuyển động giúp hiểu nội dung; kết thúc bằng outro BAHA sau khi có asset và CTA được duyệt. Đây là hướng đã có trong tài liệu định hướng, không phải nhận diện cuối cùng.

## Tài sản và bằng chứng đã tìm thấy

| Hạng mục | Bằng chứng đọc được | Trạng thái quyền, phiên bản và duyệt |
|---|---|---|
| Logo giao diện | `03_ban_lam_viec/sin_creator_os/public/logo.png` (PNG, 1.200 x 1.382 theo biên bản CP18), `logo.webp`, `logo-square.png`; biên bản CP18 ghi nhận bộ favicon/app/social icons và sử dụng logo trên giao diện. Logo có hình khối BAHA ba chiều với các mảng xanh dương, đỏ và vàng. | Có SHA-256 cho các tệp hiện có: `logo.png` F3B05DCD6B845CB2E3E318089D1CFBFC4B869DD6090342511DE124BED9810A13; `logo-square.png` 3972C8B04B98356E5B065A5F0C420964000C8C8D25D9EDAC95460E65A0DC350A; `logo.webp` CB6D020AF4E913054C618A7F870972E340AC0B5F83ECF4BE590CBF6B13A16E77. Có biên bản nghiệm thu triển khai web CP18, nhưng chưa thấy giấy phép/quyền dùng cho video, clear space/kích thước tối thiểu, biến thể nền sáng/tối có kiểm chứng, mã phiên bản thương hiệu hoặc phê duyệt style video. Hash chỉ nhận diện byte hiện tại, không chứng minh quyền hay approval. Tệp `logo.png` ở gốc có hash khác với bản public; cần ghi quan hệ nguồn/biến thể vào manifest asset trước khi khóa sản xuất.
| Palette giao diện | `sin_creator_os/src/app/globals.css` định nghĩa token giao diện: primary `#2b6fb8`, nền `#f8fafd`, chữ `#223247`, card `#ffffff`, secondary/accent `#eaf3ff`, muted foreground `#526477`, border `#e3eaf2`, success `#246849`; có giá trị riêng cho dark mode. | Đây là palette ứng dụng, chưa có bằng chứng rằng các màu này được duyệt làm palette video. Dùng làm mẫu tham chiếu để Founder đối chiếu; không tự chuyển thành token kênh.
| Font | `sin_creator_os/src/lib/fonts/registry.ts` khai báo nhiều font web qua `next/font/google`; tất cả cấu hình đọc được dùng `subsets: ["latin"]`. Không tìm thấy tệp font TTF/OTF/WOFF/WOFF2 trong `03_ban_lam_viec`. | Chưa có font video được chọn/duyệt, bằng chứng license/nhúng hoặc kiểm tra glyph tiếng Việt. Cấu hình Latin hiện tại không phải bằng chứng hỗ trợ đầy đủ dấu tiếng Việt trong xuất video. Founder cần chọn font được cấp phép và kiểm tra đủ dấu/weight trước khi chốt.
| Voice, phát âm, nhạc | Tài liệu G0/G1 quy định cần voice ID/version, mẫu/hash và quyền dùng; schema hiện có bảng `voice_consents` và asset media có trường `license_record_id`, `approval_state`. | Đây là cấu trúc ghi nhận consent/asset, không xác nhận có consent, voice profile hay license record đã duyệt. Không đọc bản ghi DB nên tình trạng giá trị thực tế chưa xác định. Chưa tìm thấy tài sản voice/style/outro trong tên tệp media được khảo sát.
| Outro và template | Tài liệu định hướng yêu cầu BAHA outro; đặc tả nhắc các biến thể O1/O2/O3 và storyboard mẫu. | Chỉ thấy yêu cầu/placeholder trong tài liệu, chưa thấy tệp outro, template, CTA, hash hay bằng chứng duyệt thực tế.
| Kịch bản/brief | Schema `BrandBriefVersion` lưu tên thương hiệu, mô tả giọng, ngôn ngữ, đối tượng, chủ đề, giới hạn và trạng thái duyệt; có bảng `owned_channels` cho kênh. | Schema brief có vòng đời duyệt, nhưng không thay thế profile style có version/hash, logo/palette/font/outro binding. Không đọc giá trị workspace, channel hoặc brief trong DB; không kết luận có hay không có bản ghi được duyệt.

## Tình trạng schema và dữ liệu

Trong các model/migration được khảo sát có `workspaces`, `brand_brief_versions`, `owned_channels`, `media_assets` và `voice_consents`. `MediaAsset` có SHA-256, loại MIME, `license_record_id` và `approval_state`, là nền tảng truy vết tài sản. `BrandBriefVersion` có trạng thái và người/thời điểm duyệt. Chưa tìm thấy model/migration style chuyên biệt cho company style, channel binding, style family, resolved snapshot hoặc approval/hash của profile. Các trường trong schema cho biết khả năng lưu, không chứng minh dữ liệu đã được nhập.

Không truy vấn DB hay WAL trong khảo sát này. Do đó không thể xác nhận trạng thái bản ghi workspace/channel/brand, quyền của từng asset hay sự tồn tại của bản ghi approved. Tài liệu kế hoạch cũng ghi nhận profile phong cách và video mẫu chưa được nghiệm thu.

## Bảng token đưa vào style board G1

Các giá trị dưới đây chỉ dùng tài sản/cấu hình đã tìm thấy hoặc giữ ở trạng thái cần Founder chọn. Không tự đặt HEX, tên font, voice hoặc CTA mới.

| Token | Giá trị đưa lên board | Nguồn/trạng thái |
|---|---|---|
| `brand.logo.primary` | Logo BAHA từ asset public hiện có; dùng nguyên hình, không sinh lại bằng AI | Asset thật có hash; CP18 nghiệm thu tích hợp web. Founder xác nhận quyền, biến thể dùng trong video và vùng trống trước khi approve.
| `brand.color.logo_family` | Các mảng xanh dương/đỏ/vàng đang hiện diện trong logo; mã màu, sắc độ và tỷ lệ dùng: **Founder chọn** | Quan sát tài sản; chưa chuẩn hóa thành palette hay có bằng chứng approval.
| `surface.background` | **Founder chọn** từ style board; có thể so sánh với nền giao diện hiện tại `#f8fafd` | Mã màu ứng dụng có thật, chỉ là tham chiếu UI, chưa duyệt cho video.
| `text.primary` | **Founder chọn**; tham chiếu giao diện hiện tại `#223247` | Mã màu ứng dụng có thật, chưa duyệt cho video.
| `color.accent` | **Founder chọn**; tham chiếu primary giao diện `#2b6fb8` và màu nhấn logo | Không mặc định lấy màu giao diện làm màu kênh.
| `typography.title`, `typography.caption` | **Founder chọn font có license, hỗ trợ đầy đủ tiếng Việt, weight và fallback** | Không có font asset local hoặc bằng chứng license/duyệt trong phạm vi khảo sát.
| `voice.profile` và `pronunciation.dictionary` | **Founder chọn/cung cấp mẫu và quyền dùng** | Chưa có voice ID/version/mẫu/hash được xác nhận; không suy giọng từ brief schema.
| `music.profile` | **Founder chọn asset hoặc duyệt chế độ không nhạc** | Chưa xác minh license/asset nhạc phù hợp style board.
| `layout.grid`, `caption.safe_area` | Dọc 1080 x 1920, 30 fps; vùng tránh trên 150 px, dưới 320 px, phải 120 px; lề trái 60 px là đề xuất trong quy chuẩn | Các kích thước cơ sở nằm trong tài liệu dự án; thông số phụ đề/bounding box cần duyệt ở G1.
| `visual.language` | Editorial explainer; một luận điểm mỗi cảnh; DIAGRAM + SCREEN_RECORDING + AI_VIDEO phối hợp cùng grid; AI chỉ minh họa, không giả làm bằng chứng sản phẩm | Hướng trong quy chuẩn phong cách; `baha_giai_thich_cong_nghe` còn là family đề xuất, chờ duyệt.
| `motion.pacing` | Chuyển động có mục đích, nhất quán giữa sơ đồ, recording và footage; nhịp và thời lượng shot: **Founder duyệt bằng storyboard** | Chưa thấy preset/reference được duyệt.
| `outro.template`, `outro.cta` | **Founder cung cấp/chọn asset và CTA**; chưa bật O1/O2/O3 như giá trị vận hành | Các mã O1/O2/O3 hiện là lựa chọn trong tài liệu, chưa có tệp/hash/approval.

## Những quyết định/bằng chứng còn thiếu trước khi khóa G1

1. Founder xác nhận logo nào là nguồn chuẩn cho video, nguồn gốc/quyền dùng, biến thể nền, clear space, kích thước tối thiểu và vị trí cho phép; lưu asset ID, phiên bản và hash.
2. Founder duyệt palette video có mã màu, vai trò semantic, tỷ lệ dùng và cặp tương phản. Palette CSS chỉ nên xuất hiện như phương án đối chiếu.
3. Founder chọn font đã cấp phép, xác nhận quyền nhúng/xuất video, đủ dấu tiếng Việt và fallback; ghi phiên bản/hash.
4. Founder chọn/cấp mẫu giọng, voice ID/version, từ điển phát âm và quyền sử dụng; nếu không dùng voice, ghi `NOT_APPLICABLE` cùng lý do.
5. Cung cấp hoặc duyệt nhạc, outro, CTA, template sơ đồ/lower-third và reference frame; mỗi tài sản có provenance, license, hash, người duyệt và hạn dùng nếu có.
6. Duyệt storyboard/frame mẫu cho ba chủ đề pilot và rubric nhất quán giữa sơ đồ, recording, AI minh họa, caption và outro. Chỉ sau duyệt mới đóng phiên bản family và binding cho kênh.
7. Đối chiếu bản ghi thực bằng quy trình chỉ đọc được phê duyệt riêng nếu cần xác minh workspace/channel/brand status; lần khảo sát này chỉ xác nhận schema, không đọc dữ liệu DB.

Nguồn nội bộ đã đọc: `00_bat_dau/CURRENT_STATE.md`, `00_bat_dau/CHECKPOINT.json`, `03_ban_lam_viec/ke_hoach_tao_video_tu_noi_dung/quy_chuan_phong_cach_kenh.md`, `dinh_huong_goc_cua_founder.md`, `nghien_cuu_hien_trang_va_phuong_an.md`, model `sin_content_api/src/models/entities.py`, `sin_creator_os/src/lib/fonts/registry.ts`, `sin_creator_os/src/app/globals.css`, các logo trong `sin_creator_os/public/`, và biên bản `08_kiem_thu/bang_chung/CP18_LOGO_FAVICON_EVIDENCE.md`.
