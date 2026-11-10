# Hướng dẫn thực thi cho agent: 6 mẫu video HyperFrames

**ĐÍNH CHÍNH QUAN TRỌNG (đọc trước):** "6 mẫu" của dự án là **6 MẪU VIDEO trọn vẹn (V1 đến V6, mỗi mẫu một khuôn video 100 giây)**, được đặc tả ở `dac_ta_6_mau_video_20261109.md`. Trong tài liệu này, các "mẫu A, B, C, D, E, F" (CASH_RIVER, PIPELINE_RAIL, STACK_WAREHOUSE, BOOK_FLIP, LIVE_DASHBOARD, TEAM_BOARD) chỉ là **cảnh thành phần** dùng bên trong các mẫu video; chúng không phải sản phẩm cuối. Mọi chỗ ghi "mẫu A đến F" ở dưới đọc là "cảnh thành phần A đến F". Chuỗi M1 đến M10 ở mục 4 áp dụng cho cảnh thành phần; mẫu video có chuỗi riêng ở nhiệm vụ TV (mục 3).

Ngày lập: 09/11/2026. Đối tượng đọc: agent AI thực hiện kế hoạch. Tài liệu đi kèm: `ke_hoach_6_mau_video_hyperframes_20261109.md` (kế hoạch tổng, các cổng và rubric). Tài liệu này là bản "làm từng bước"; nếu hai tài liệu mâu thuẫn thì tài liệu này thắng, trừ khi mục 0.4 yêu cầu dừng.

Tài liệu không chứa mã. Mọi chỗ cần viết mã đều ghi rõ yêu cầu, tệp, tiêu chí hoàn thành và cách kiểm.

---

## 0. Cách dùng tài liệu này (đọc kỹ trước khi làm bất cứ gì)

### 0.1 Nguyên tắc làm việc
1. Làm đúng một nhiệm vụ tại một thời điểm, theo thứ tự ở mục 3. Không làm trước, không làm song song.
2. Trước khi sửa bất kỳ tệp nào, đọc toàn bộ tệp đó và đọc một ví dụ tương tự đã có trong repo (mục 2 nêu ví dụ cần đọc).
3. Mỗi nhiệm vụ kết thúc bằng một báo cáo theo mẫu mục 8. Không báo "xong" nếu chưa có bằng chứng (đường dẫn tệp ảnh, tệp log, kết quả kiểm).
4. Nếu không chắc một điều, đừng đoán: tra trong repo; nếu repo không trả lời, dừng và hỏi theo mục 0.4.
5. Không mở rộng phạm vi. Chỉ làm việc nhiệm vụ yêu cầu; việc phát hiện thêm thì ghi vào mục "Phát hiện ngoài phạm vi" của báo cáo.
6. Không commit, không push, trừ khi người giao việc yêu cầu rõ. Làm trên một nhánh mới tên `feat/hf-6-mau` tạo từ nhánh hiện tại.

### 0.2 Những thứ tuyệt đối không được chạm
- Các tệp sub: `sin_content_api/src/modules/media_studio/ass_captions.py`, `phan_tich_phu_de_da_tang.py`, và các test `tests/test_phu_de_da_tang.py`, `tests/test_vietsub.py`. Đang có nhánh khác làm.
- Thư mục `cong_cu_tu_dong/` và mọi thay đổi chưa commit ở đó.
- `sin_creator_os/src/components/ui/` và `sin_creator_os/src/components/calendar/` (quy định trong `sin_creator_os/AGENTS.md`).
- Các tiến trình đang chạy: không dừng, không khởi động lại API, worker, web, gateway, tunnel. Không chạm trạng thái run trong cơ sở dữ liệu. Không gọi Flow, không gọi TTS, không tạo lượt dựng sản xuất.
- Thư mục dữ liệu `ha_tang/chay_dev_local/data/` (video, cơ sở dữ liệu). Chỉ đọc.
- Tệp `.env.dev` và mọi tệp bí mật. Không in giá trị biến môi trường.

### 0.3 Quy tắc kỹ thuật bắt buộc (rút ra từ lỗi thực tế đã gặp trong repo)
1. **Giữ đúng kiểu xuống dòng của từng tệp.** Nhiều tệp là LF, một số là CRLF. Sau khi sửa, so sánh `git diff --stat`; nếu một tệp nhỏ hiện hàng trăm dòng đổi thì kiểu xuống dòng đã bị đổi, phải khôi phục ngay.
2. **Ghi tệp bằng công cụ ghi tệp**, không dán nội dung có dấu gạch chéo ngược vào lệnh shell nhiều dòng (dấu gạch chéo bị nuốt làm hỏng nội dung).
3. **Luôn đặt mã hoá UTF-8 khi chạy công cụ in tiếng Việt** (biến `PYTHONIOENCODING=utf-8`), nếu không sẽ lỗi `charmap`.
4. **Máy chỉ có 8 GB RAM, không GPU.** Chỉ một tiến trình Chrome dựng tại một thời điểm (đã có khoá `_RENDER_LOCK`), `workers` luôn bằng 1. Không chạy hai lần dựng song song.
5. **Chạy kiểm thử theo nhóm nhỏ.** Bộ test video và pipeline mất hơn 50 phút. Chỉ chạy các tệp test liên quan (mục 2.3), thêm tuỳ chọn không dùng bộ nhớ đệm (`-p no:cacheprovider`).
6. **Mọi chữ hiển thị là tiếng Việt có dấu.** Không emoji. Không URL ngoài, không CDN. Font dùng Be Vietnam Pro đã có trong repo.
7. **Chuyển động tất định.** Cùng dữ liệu vào phải cho ra cùng video. Cấm dùng số ngẫu nhiên không có hạt giống cố định.

### 0.4 Khi nào phải dừng và hỏi người giao việc
Dừng ngay, ghi vào báo cáo và chờ trả lời nếu gặp một trong các tình huống:
1. Cần thêm trường vào `DiagramSpec` hoặc đổi kiểu dữ liệu `UiScene` ngoài việc thêm tên layout (đổi schema ảnh hưởng bản băm storyboard cũ và lời nhắc).
2. Một cổng không đạt sau 3 vòng sửa liên tiếp.
3. Thời gian dựng một cảnh vượt gấp đôi ngân sách (mục 7.5).
4. Cần cài thêm gói, tải tệp từ internet, hay sửa tệp thuộc danh sách cấm ở mục 0.2.
5. Phát hiện bài test nền (mục 3, nhiệm vụ T00) đang đỏ trở nên đỏ thêm sau thay đổi của mình mà không rõ nguyên nhân.
6. Có hai cách hiểu hợp lý cho một yêu cầu và chúng dẫn đến thiết kế khác nhau.

---

## 1. Bối cảnh ngắn gọn

- Mục tiêu: giảm clip Flow còn tối đa 2 clip mỗi video; các cảnh giải thích dựng bằng HyperFrames, nhiều hoạt hoạ, lia máy, vật thể chuyển động có quy luật.
- **Sản phẩm cuối: 6 mẫu video** V1 đến V6 (điểm đau-nguyên nhân-cách gỡ, con số tố cáo, dòng chảy, trước và sau, ba sai lầm, một ngày thật), mỗi mẫu một khuôn video 100 giây gồm 13 đến 14 cảnh. Xem `dac_ta_6_mau_video_20261109.md`.
- **Nguyên liệu: cảnh thành phần mới** (mỗi cảnh là một layout mới): A `CASH_RIVER`, B `PIPELINE_RAIL`, C `STACK_WAREHOUSE`, D `BOOK_FLIP`, E `LIVE_DASHBOARD`, F `TEAM_BOARD`, cộng các cảnh có sẵn.
- Thứ tự làm cảnh thành phần: E rồi A (đủ cho pilot V2), sau đó B, C, D, F theo nhu cầu của các mẫu video tiếp theo (xem mục 7 của tài liệu đặc tả).

---

## 2. Bản đồ repo (đã kiểm; agent đọc các tệp này trước khi làm)

### 2.1 Nơi mỗi thứ nằm
| Vai trò | Đường dẫn | Ghi chú |
|---|---|---|
| Khối HyperFrames dựng sẵn (HTML) | `sin_content_api/engines/hyperframes/blocks/<ten-khoi>.html` | Mỗi khối là một sub-composition dùng GSAP, đọc biến qua `window.__hyperframes.getVariables()` |
| Danh mục khối | `sin_content_api/engines/hyperframes/blocks/catalog.json` và `index.json`, `danh_sach_khoi_da_kiem.txt` | Ghi nhận khối đã kiểm bằng ảnh chụp |
| Hợp đồng biến của từng biến thể | `sin_content_api/engines/hyperframes/blocks/manifest/<layout>_<bien_the>.json` | Trường chính: `layout`, `variant_key`, `block`, `max_chars`, `portrait_scale`, `square`, `variables` (ánh xạ từ trường của `diagram` bằng `field` hoặc hàm như `default`, `nth`, `concat`, `to_int`), `literals` |
| Nạp khối, đổi định danh, làm sạch CDN, bản địa hoá chữ | `sin_content_api/src/modules/tao_video_noi_dung/hf_blocks.py` | Hàm `prepare_block`, `scene_composition`, `pick_variant`; bảng `_VIETNAMESE_TEXT`; `PORTRAIT_SCALE` |
| Đọc và kiểm hợp đồng biến | `.../hf_manifest.py` | `validate_manifest`, `load_manifests` |
| Mô tả layout cho bộ lập kế hoạch (LLM) | `.../hf_prompt.py` | Bảng `LAYOUT_PROMPTS`; `BLOCK_LAYOUTS` suy ra từ khoá của bảng này |
| Schema storyboard, danh sách layout hợp lệ, kiểm dữ liệu, giới hạn thời lượng | `.../planner.py` | `UiScene.layout` (danh sách chuỗi cố định), `DiagramSpec`, `validate_diagram`, `UI_SHOT_MIN_SECONDS`/`UI_SHOT_MAX_SECONDS` (hiện 3 và 6), `UI_LAYOUT_MAX_SECONDS`, `DIAGRAM_SECONDS_PER_EVENT` (2,5), `_suggested_shot_counts` (đang đặt 60% là Flow), `FLOW_SHOT_SECONDS` (10) |
| Cảnh dựng bằng mã 16:9 và giàn camera | `.../hf_scenes.py`, `.../dieu_khien_may_quay.js` | Có `__bahaCamera`, các lớp `-cam`, `-backCam`, `-frontCam` |
| Dựng dự án, kiểm, dựng video | `.../hf_project.py` | `build_project`, `check_project` (gọi `hyperframes check --json`), `render_project` (tham số chất lượng `-q`, `-w` luôn 1) |
| Camera và chuyển cảnh cơ bản | `.../hf_camera.py`, `.../hf_transitions.py` | 4 kiểu camera, 8 kiểu chuyển cảnh |
| Lớp phủ, hạt, nền | `.../hf_layers.py` | |
| Âm thanh hoạt hoạ | `.../am_thanh_hoat_hoa/*.wav` và `nguon_am_thanh.md` | 9 tệp: bat_mo, canh_bao, cho_nhe, dong_dau, go_nhe, go_phim, lat_trang, luot_nhanh, luot_nhe |
| Cổng chất lượng hiện có | `ha_tang/hyperframes/cong_chat_luong.py` | Chạy kiểm HyperFrames, quét từ mẫu tiếng Anh, quét URL ngoài, chụp ảnh ở 60% để kiểm chữ tràn |
| Kiểm khói khối | `ha_tang/hyperframes/kiem_thu_khoi.py`, `quet_danh_muc.py` | |
| Mẫu 3D thử nghiệm | `sin_content_api/engines/hyperframes/mau_ba_chieu/index.html` | Tham khảo cách dùng phối cảnh |

### 2.2 Ví dụ cần đọc trước khi tạo layout mới
- Layout khối có ít dữ liệu: `PILE_UP`, `DRAG_TASKS`, `CARD_SHIFT`, `STAT_RING`, `CHART_STORY`. Xem từng mục tương ứng trong `hf_prompt.py` (`LAYOUT_PROMPTS`), trong `planner.py` (hàm `validate_diagram`, chuỗi lỗi `*_FIELDS`, bảng giới hạn ký tự khoảng dòng 1139) và tệp manifest tương ứng trong thư mục `manifest/`.
- Khối có chuyển động giàu: `paper-collage-reveal.html`, `kinetic-center-build.html`, `cursor-drag-drop.html`, `focus-rack.html`, `chart-story.html`, `overwhelm-surround.html`.

### 2.3 Tệp test liên quan (chỉ chạy các tệp này)
`tests/test_hf_manifest.py`, `tests/test_hf_prompt.py`, `tests/test_hf_catalog.py`, `tests/test_hf_camera.py`, `tests/test_hf_transitions.py`, `tests/test_hf_layers.py`, `tests/test_hf_vendor.py`, `tests/test_chuyen_dong_hyperframes.py`, `tests/test_hf_tich_hop.py` (có 2 test nền đang đỏ, xem T00).

### 2.4 Biến môi trường điều khiển dựng (không sửa giá trị mặc định trong repo)
`CONTENT_VIDEO_HF_CAMERA`, `CONTENT_VIDEO_HF_TRANSITIONS`, `CONTENT_VIDEO_HF_AMBIENT` (mặc định tắt), `CONTENT_VIDEO_HF_WORKERS`, `CONTENT_VIDEO_HF_RENDER_TIMEOUT_SECONDS`, `CONTENT_VIDEO_HF_CHECK`. Khi dựng thử một mẫu, dùng chất lượng nháp (`-q draft`), chất lượng sản xuất chỉ ở cổng G5 và G6.

### 2.5 Hai sự thật làm thay đổi thiết kế (đã kiểm trong `planner.py`)
1. Một shot tối đa 10 giây (`duration_seconds` từ 1 đến 10). Cảnh dựng bằng mã hiện bị giới hạn 3 đến 6 giây. Vì vậy mọi mẫu mới thiết kế dài **tối đa 10 giây**, và phải thêm mục cho 6 layout vào `UI_LAYOUT_MAX_SECONDS` để cho phép dài hơn 6 giây (nhiệm vụ T50).
2. `DiagramSpec` dùng `extra="forbid"`: không thêm được trường lạ. Mọi mẫu phải dùng lại các trường có sẵn (mục 5.2 liệt kê cách ánh xạ).

---

## 3. Danh sách nhiệm vụ theo thứ tự

Quy ước tên nhiệm vụ: `T<giai đoạn><số>`. Mỗi nhiệm vụ có điều kiện bắt đầu (đầu vào), việc làm, tiêu chí hoàn thành, và điểm dừng.

| Mã | Nhiệm vụ | Phụ thuộc | Ước lượng |
|---|---|---|---|
| T00 | Khảo sát và ghi đường cơ sở | không | 0,5 ngày |
| T01 | Bộ tài sản origami dùng chung | T00 | 3 ngày |
| T02 | Công cụ ghi vết chuyển động và quy ước thuộc tính | T00 | 2 ngày |
| T03 | Bộ chạy cổng tự động G2 đến G5 | T02 | 3 ngày |
| T10 | Cảnh thành phần E `LIVE_DASHBOARD` trọn chuỗi M1 đến M10 | T01, T02, T03 | 4 ngày |
| T20 | Cảnh thành phần A `CASH_RIVER` | T10 | 4 ngày |
| T50 | Nối vào bộ lập kế hoạch: nâng giới hạn thời lượng cảnh, đăng ký layout (làm cho E và A trước pilot) | T10, T20 | 3 ngày |
| **TV2** | **Pilot mẫu video V2** (chuỗi TV bên dưới) và báo cáo hiệu chỉnh ngưỡng (T11) | T20, T50 | 5 ngày, rồi **DỪNG chờ Founder** |
| T21 | Cảnh thành phần B `PIPELINE_RAIL` | TV2 được duyệt | 4 ngày |
| **TV1** | Mẫu video V1 | T21 | 4 ngày |
| T30 | Cảnh thành phần C `STACK_WAREHOUSE` | T21 | 5 ngày |
| **TV3** | Mẫu video V3 | T30 | 4 ngày |
| T31 | Cảnh thành phần D `BOOK_FLIP` | T21 | 5 ngày |
| T40 | Cảnh thành phần F `TEAM_BOARD` | T30, T31 | 7 ngày |
| **TV4** | Mẫu video V4 | T31, T40 | 4 ngày |
| **TV6** | Mẫu video V6 | T31, T40 | 4 ngày |
| **TV5** | Mẫu video V5 | T20, T21, T30 | 4 ngày |
| T51 | Lời nhắc cho LLM và kiểm tự động storyboard (chọn mẫu video theo bài, giảm Flow) | TV2 | 2 ngày |
| T52 | Kiểm hồi quy toàn bộ | TV1 đến TV6, T51 | 2 ngày |
| T53 | Thí điểm 5 video thật và báo cáo hiệu quả | T52 | 3 ngày |

**Chuỗi TV (làm một mẫu video, áp dụng cho TV1 đến TV6):**
1. **TV-a. Đọc đặc tả** mẫu tương ứng trong `dac_ta_6_mau_video_20261109.md` (mục 3) và các quy tắc chung (mục 1). Kiểm các cảnh thành phần mà mẫu cần đã đạt G7. Thiếu cảnh nào thì dừng, quay lại tác vụ cảnh đó.
2. **TV-b. Khung kịch bản (GV1).** Tạo `ha_tang/hyperframes/mau_video/<v?>/01_khung.md` chép bảng phân cảnh, thêm cột: số âm tiết lời đọc mỗi cảnh (theo 3,0 đến 4,2 âm tiết mỗi giây), trường dữ liệu cần điền, sự kiện bám lời. Kiểm thủ công quy tắc nhịp (mục 1.2) và liền mạch (mục 1.3) của đặc tả; ghi kết quả. Chờ Founder duyệt khung.
3. **TV-c. Điền ba bài (GV2).** Chọn đúng ba bài khác nhau gán cho mẫu (bảng 3.1 của đặc tả; mẫu chỉ có hai bài thì dùng cả hai cộng một bài tự chọn có lý do). Tạo storyboard cho từng bài bằng bộ lập kế hoạch theo khung (xem T51); nếu chưa có T51 thì tạo storyboard bằng tay theo cấu trúc dữ liệu của `planner.py`. Kiểm qua các kiểm tự động của bộ lập kế hoạch; ghi lỗi.
4. **TV-d. Dựng nháp từng video.** Dựng chất lượng nháp cả ba video bằng quy trình dựng hiện có ở chế độ **không Flow** (cột "Thay thế khi không Flow"). Chụp ảnh các mốc và ghi vết chuyển động cho từng cảnh mới. Không gọi Flow.
5. **TV-e. Chạy cổng GV3 đến GV7** theo mục 5 của đặc tả; ghi báo cáo từng cổng.
6. **TV-f. Gói duyệt GV8.** Dựng chất lượng sản xuất ba video, ảnh chụp, báo cáo cổng, phiếu chấm (mục 6 của đặc tả). Dừng chờ Founder chấm.
7. **TV-g. GV9.** Sau khi đạt, ghi vào danh mục mẫu video, viết hướng dẫn một trang "khi nào dùng mẫu này", cập nhật tài liệu.
**Chế độ có Flow:** chỉ làm sau GV9, khi Founder cho phép tạo clip Flow, và chỉ cho đúng các cảnh ghi "Flow" trong bảng. Agent không tự tạo clip Flow.

### T00. Khảo sát và ghi đường cơ sở
**Mục đích:** biết chính xác tình trạng ban đầu để sau này phân biệt lỗi mới với lỗi cũ.
**Việc làm:**
1. Ghi phiên bản: Node, hyperframes CLI (kỳ vọng 0.8.222), FFmpeg, Python; dung lượng RAM trống; dung lượng đĩa trống.
2. Chạy nhóm test ở mục 2.3 và ghi danh sách test đỏ hiện có làm "đường cơ sở". Biết trước: `test_hf_tich_hop.py` có 2 test đỏ liên quan `tr01` (`test_caption_style_env_sai_thi_lui_ve_karaoke`, `test_mac_dinh_van_la_karaoke_va_collage`).
3. Dựng thử một khối có sẵn (ví dụ `chart-story`) 3 giây ở chất lượng nháp bằng công cụ kiểm khói; ghi thời gian thực để làm cơ sở ngân sách (kỳ vọng khoảng 8 giây thực cho mỗi giây video ở chất lượng sản xuất).
4. Chụp ảnh bảng màu và font đang dùng (`THEME_STYLE` trong `hf_blocks.py`): navy `#0a1c2b`, ngà `#f6efe0`, bề mặt `#12324a`, vàng `#ffd54a`, ngọc lam `#5cc8c0`, san hô `#e8695a`, xám xanh `#9fb4c4`.
**Đầu ra:** `ha_tang/hyperframes/mau_6/bao_cao/T00.md` gồm bảng phiên bản, danh sách test đỏ nền, thời gian dựng cơ sở.
**Hoàn thành khi:** báo cáo có đủ 4 mục trên. Không sửa tệp nào của dự án.

### T01. Bộ tài sản origami dùng chung
**Mục đích:** để cả 6 mẫu cùng một thế giới, tránh sáu phong cách khác nhau.
**Việc làm:**
1. Tạo thư mục `ha_tang/hyperframes/mau_6/tai_san/` với các tệp SVG vector (không ảnh điểm). Mỗi tệp một vật, đặt tên theo kiểu `vat_<ten>.svg`.
2. Danh sách tối thiểu (mỗi vật có phiên bản màu ngà, ngọc lam, vàng, san hô khi cần): đồng xu giấy (đường kính chuẩn 64 px), túi tiền, hộp giấy (3 cỡ), thẻ hồ sơ (chữ nhật bo góc, 3 màu), thẻ KPI, cột biểu đồ (bệ và thân), kim đồng hồ đo và mặt đồng hồ, băng chuyền (một đoạn nối được), trạm kiểm, kệ kho, xe nâng, bàn làm việc, trang giấy (hai mặt), ghi chú dán, ngăn tủ, ghế, nhân vật origami ngồi (2 tư thế: nhìn thẳng, nghiêng), nhân vật rời đi, đèn báo (xanh, đỏ).
3. Phong cách thống nhất: nếp gấp nhìn thấy được, cạnh giấy mảnh sáng hơn 8%, không viền đen, bóng đổ do mã tạo (không vẽ bóng trong SVG).
4. Quy ước hệ toạ độ: mỗi SVG có điểm gốc `(0,0)` ở giữa đáy vật (để vật đặt xuống sàn đúng điểm tiếp xúc) và thuộc tính `data-anchor` ghi toạ độ các điểm neo cần thiết (ví dụ điểm tay cầm của thẻ).
5. Ghi tệp `tai_san/DANH_MUC.md`: mỗi vật gồm tên, kích thước chuẩn, điểm neo, mô tả dùng cho mẫu nào, giấy phép (tự vẽ).
**Hoàn thành khi:** (a) mọi SVG mở được và hiển thị đúng trong trình duyệt; (b) không tệp nào chứa liên kết ngoài, chữ nhúng, hay font ngoài; (c) `DANH_MUC.md` đủ cột; (d) một ảnh tổng hợp tất cả vật xếp cạnh nhau (`tai_san/tong_hop.png`) để người duyệt xem một lần.
**Điểm dừng:** gửi ảnh tổng hợp cho người duyệt trước khi dùng. Chờ duyệt phong cách.

### T02. Công cụ ghi vết chuyển động và quy ước thuộc tính
**Mục đích:** biến luật "vật có nguồn vào, đích ra, không tức thời" thành kiểm tra tự động được (cổng G3).
**Quy ước bắt buộc cho mọi mẫu (agent viết vào `tai_lieu/quy_uoc_thuoc_tinh.md`):**
- Mỗi vật chuyển động là một phần tử có thuộc tính `data-obj` (tên duy nhất trong cảnh, kiểu `coin-03`), `data-kind` (một trong `prop`, `text`, `light`, `fx`), `data-src`, `data-dst`.
- Giá trị `data-src`: `static` (có sẵn trong thế giới từ đầu), `offscreen-left`, `offscreen-right`, `offscreen-top`, `offscreen-bottom`, `spawn-from:<data-obj khác>`, `unfold-from:<data-obj khác>`.
- Giá trị `data-dst`: `stay` (ở lại đến hết cảnh), `offscreen-left` (và tương tự các hướng khác), `sink-into:<data-obj>`, `fold-into:<data-obj>`, `occluded-by:<data-obj>`.
- Quy tắc theo `data-kind`: `prop` bắt buộc có `data-src` và `data-dst` khác `static` hoặc `stay` ít nhất ở một đầu nếu vật có xuất hiện hoặc biến mất; `text` và `light` được phép hiện hoặc tan bằng độ mờ; `fx` chỉ là hạt hoặc ánh sáng phụ, không tính vào giới hạn vật.
**Việc làm:**
1. Thiết kế "chế độ ghi vết": khi bật, trình duyệt dựng chạy dòng thời gian của cảnh, tại mỗi khung (30 khung mỗi giây) ghi lại với mọi phần tử có `data-obj`: toạ độ tâm và kích thước (tính theo phần trăm khung 1920×1080), độ mờ, độ xoay, và độ phóng của camera (từ phần tử `-world`). Kết quả lưu thành một tệp JSON mỗi cảnh, đặt tên `<layout>_<so>_ghi_vet.json`. (Chi tiết định dạng ở Phụ lục A.)
2. Tạo công cụ phân tích đọc tệp ghi vết và tính các chỉ số G3 (mục 7.3).
3. Viết mô tả sử dụng ngắn (một trang) cho người làm mẫu: bật chế độ ghi vết thế nào, đọc báo cáo ra sao.
**Hoàn thành khi:** chạy công cụ trên một khối có sẵn (`chart-story`) cho ra tệp ghi vết đủ 30 khung mỗi giây và bản báo cáo G3 mẫu (có thể đỏ vì khối cũ chưa theo quy ước; điều đó chấp nhận được, chỉ cần công cụ chạy và báo cáo rõ ràng).
**Đầu ra:** `ha_tang/hyperframes/mau_6/cong_cu/` (công cụ), `tai_lieu/quy_uoc_thuoc_tinh.md`, `bao_cao/T02.md`.

### T03. Bộ chạy cổng tự động G2 đến G5
**Việc làm:**
1. Dùng lại `cong_chat_luong.py` làm nền cho G2 (kiểm HyperFrames, từ mẫu tiếng Anh, URL ngoài). Không sửa tệp gốc; tạo công cụ mới gọi các hàm của nó.
2. Thêm G4: chụp ảnh ở 10%, 30%, 50%, 70%, 90% thời lượng và ở mỗi mốc đổi cú máy; kiểm chữ không tràn và không bị che, độ tương phản, vùng an toàn (mục 7.4).
3. Thêm G5: đo thời gian thực của lần dựng chất lượng sản xuất chia cho số giây video, đỉnh RAM, dung lượng tệp.
4. Công cụ nhận tham số là tên layout và tập dữ liệu thử, xuất một báo cáo Markdown có bảng đạt hoặc không đạt cho từng tiêu chí kèm bằng chứng (đường dẫn ảnh, số đo).
**Hoàn thành khi:** chạy trọn bộ trên một khối có sẵn cho ra báo cáo đủ các cổng G2, G3, G4, G5; báo cáo liệt kê tiêu chí nào đạt, không đạt, và vì sao.
**Đầu ra:** `bao_cao/T03.md` và một báo cáo mẫu.

### T10 đến T40. Làm một mẫu (chuỗi M1 đến M10)
Áp dụng cho từng mẫu theo thông số riêng ở mục 6. Chuỗi M1 đến M10 ở mục 4.

### T11. Hiệu chỉnh ngưỡng và báo cáo thử nghiệm
**Việc làm:** từ số đo thật của Mẫu E, đề xuất điều chỉnh các ngưỡng ở mục 7 (ví dụ giới hạn số phần tử, ngân sách dựng). Ghi rõ ngưỡng cũ, ngưỡng đề xuất, số đo làm căn cứ.
**Đầu ra:** `bao_cao/T11.md` gồm: kết quả G0 đến G6 của Mẫu E, ảnh chụp, video nháp, số đo, đề xuất điều chỉnh, danh sách việc cần quyết.
**DỪNG:** chờ Founder duyệt báo cáo này trước khi bắt đầu T20.

### T50. Nối vào bộ lập kế hoạch (làm sau khi Mẫu E đạt G7)
**Phạm vi thay đổi (chỉ các tệp sau):** `planner.py`, `hf_prompt.py`, và các test liên quan. Mỗi layout mới được đăng ký ở bốn chỗ:
1. Khối HTML và manifest (đã làm trong chuỗi M).
2. Mục mô tả trong `LAYOUT_PROMPTS` (`hf_prompt.py`): một câu mô tả dữ liệu cần nhập, theo đúng kiểu các mục có sẵn (số từ, giới hạn ký tự từng trường).
3. Tên layout trong danh sách chuỗi của `UiScene.layout` (`planner.py`).
4. Kiểm dữ liệu trong `validate_diagram` (mẫu: `PILE_UP`, `DRAG_TASKS`), thông báo lỗi `<LAYOUT>_FIELDS` trong bảng thông báo, và giới hạn ký tự trong bảng giới hạn khoảng dòng 1139.
Ngoài ra:
5. Thêm 6 mục vào `UI_LAYOUT_MAX_SECONDS` với giá trị 10 để cho phép cảnh dài hơn 6 giây (hiện mặc định `UI_SHOT_MAX_SECONDS` là 6).
6. Đổi `_suggested_shot_counts` để số shot Flow không quá 2 và phần còn lại là cảnh dựng bằng mã (hiện đặt 60% Flow). Cập nhật các thông điệp gợi ý đi kèm.
7. Quy tắc `DIAGRAM_LAYOUT_REPEATED` (tối đa 2 lần mỗi layout) giữ nguyên.
**Điều kiện dừng:** nếu cần thêm trường vào `DiagramSpec`, dừng theo mục 0.4 điểm 1.
**Hoàn thành khi:** test `test_hf_prompt.py`, `test_hf_manifest.py` và các test planner liên quan xanh (hoặc chỉ đỏ ở các test nền đã ghi trong T00); một storyboard mẫu có ít nhất một cảnh dùng layout mới qua được bước kiểm.

### T51. Lời nhắc cho LLM và kiểm tự động storyboard
**Việc làm:** (1) Cập nhật các đoạn lời nhắc trong `planner.py` liên quan đến cảnh dựng bằng mã để mô tả 6 layout, chỉ dẫn khi nào dùng layout nào theo bảng Phụ lục B. (2) Sửa các câu trong lời nhắc Flow đang mâu thuẫn: các đoạn đòi "2–4 lớp chuyển động" và "không phải lý do để giảm chuyển động" (khoảng dòng 904 đến 940 và 1441 đến 1470) cần đổi thành: một hành động chính liên tục, camera chậm, cấm vật tự bay, tự xuất hiện, tự biến mất. (3) Thêm quy tắc kiểm mềm: video có quá 2 shot Flow thì báo vấn đề cho vòng sửa của LLM.
**Hoàn thành khi:** test lời nhắc đạt; chạy bộ lập kế hoạch ở chế độ thử trên 3 bài, mỗi storyboard có không quá 2 shot Flow và dùng ít nhất 3 layout mới khác nhau. (Chế độ thử này gọi LLM và tốn hạn mức LLM; hỏi người giao việc trước khi chạy.)

### T52. Kiểm hồi quy toàn bộ
Chạy toàn bộ nhóm test mục 2.3 và so với đường cơ sở T00. Không được có test đỏ mới. Chạy cổng G2 đến G5 cho cả 6 mẫu với mỗi mẫu 3 bộ dữ liệu. Báo cáo tổng.

### T53. Thí điểm 5 video thật
**DỪNG trước khi chạy:** xin người giao việc xác nhận danh sách 5 bài và xác nhận được phép tạo lượt dựng. Việc này tốn tài nguyên máy nhiều giờ. Không tự chạy.

---

## 4. Chuỗi M1 đến M10: cách làm trọn một mẫu

Mỗi bước có đầu ra cụ thể nộp vào thư mục `ha_tang/hyperframes/mau_6/<ma_mau>/` (ví dụ `mau_6/e_live_dashboard/`). Không bỏ bước nào.

### M1. Tờ yêu cầu (`01_to_yeu_cau.md`)
Điền đủ: tên layout, bài áp dụng (Phụ lục B), ý chính một câu, thời lượng (≤10 giây), danh sách vật chuyển động với số lượng tối đa, cú máy chính, trường dữ liệu dùng (mục 5.2), giới hạn ký tự từng trường, các trường hợp biên cần thử. Lấy nguyên từ bảng mẫu ở mục 6; không tự đổi con số mà không ghi lý do.

### M2. Tham chiếu (`02_tham_chieu/`)
Thu 6 đến 10 ảnh hoặc đoạn ngắn tham chiếu về chất liệu giấy, ánh sáng, loại chuyển động (từ thư mục có sẵn trong dự án như `engines/hyperframes/mau_ba_chieu`, các video Flow đã duyệt). Mỗi tham chiếu kèm một dòng "học được gì". Không sao chép nguyên khung.

### M3. Kế hoạch lớp và danh sách vật (`03_ke_hoach_lop.md`)
Bảng các lớp (mục 5.1) và bảng vật: mã `data-obj`, tên, lớp, `data-src`, `data-dst`, kích thước (phần trăm khung), số lượng. Kiểm bằng tay: mỗi vật `prop` phải có nguồn vào và đích ra phù hợp luật 3 và 4.

### M4. Bảng nhịp (`04_bang_nhip.md`)
Bảng theo thời gian, mỗi hàng: khoảng thời gian, sự kiện, vật nào, hàm làm chậm (easing), thời lượng, trạng thái camera đầu và cuối, âm thanh, mốc từ lời đọc (biến sự kiện). Lấy mục 6 làm bản nháp đầu và điều chỉnh. **Cổng G1** kiểm tài liệu này; không dựng khi chưa G1 đạt.

### M5. Dựng thế giới tĩnh (`05_the_gioi_tinh/`)
Dựng bố cục các lớp, chưa có chuyển động. Chụp ảnh khung giữa và khung ở 3 bộ dữ liệu (ngắn, trung bình, dài nhất). Kiểm chữ không tràn, vùng an toàn (mục 7.4), dấu tiếng Việt.

### M6. Chuyển động chính (`06_chuyen_dong/`)
Thêm theo bảng nhịp, từng sự kiện một: (1) camera, (2) vật chính, (3) vật phụ, (4) vi chuyển động nhàn rỗi. Sau mỗi sự kiện chạy ghi vết và kiểm nhanh; không thêm sự kiện mới khi sự kiện trước chưa qua kiểm.

### M7. Lớp hoàn thiện
Bóng đổ nhất quán, hạt phim, vân giấy, làm mờ chiều sâu, âm thanh từ bộ có sẵn. Giá trị chuẩn ở mục 5.3.

### M8. Đăng ký vào hệ thống (`08_dang_ky.md`)
Làm theo T50 mục 1 đến 4 cho layout này (khối HTML, manifest, `LAYOUT_PROMPTS`, `UiScene.layout`, `validate_diagram`, giới hạn ký tự, bản địa hoá chữ trong `_VIETNAMESE_TEXT` nếu khối có chữ cố định). Ghi lại mỗi tệp đã sửa và dòng thay đổi.

### M9. Thử ba nội dung (`09_ba_noi_dung/`)
Điền ba bộ dữ liệu thật lấy từ ba bài khác nhau trong Phụ lục B (kể cả bộ có chữ dài nhất cho phép và bộ có số lượng phần tử ít nhất cho phép). Dựng nháp cả ba, chụp ảnh, ghi vết. Mẫu phải không vỡ ở cả ba.

### M10. Chạy cổng (`10_cong/`)
Chạy G2, G3, G4, G5 bằng bộ công cụ T03; điền phiếu G6 để Founder chấm; ghi G7. Mỗi cổng một báo cáo; nếu không đạt thì sửa và chạy lại (tối đa 3 vòng, rồi dừng theo mục 0.4).

---

## 5. Quy ước chung cho cả 6 mẫu

### 5.1 Cấu trúc thế giới (bắt buộc)
- Khung 1920×1080. Mọi toạ độ trong tài liệu này là phần trăm khung, gốc ở góc trên trái.
- Phần tử gốc của cảnh chứa một phần tử `-world`. Camera là phép biến đổi áp lên `-world`; không áp camera lên từng vật.
- Bốn lớp theo thứ tự từ xa đến gần: `-back` (nền, hệ số thị sai 0,5), `-mid` (vật chính, hệ số 1,0), `-front` (tiền cảnh, hệ số 1,6), `-fx` (hạt và ánh sáng, hệ số 1,0, không nhận bóng).
- Mỗi lớp có thể bật làm mờ chiều sâu: `-back` 2 px khi không là tiêu điểm, `-front` 3 px khi không là tiêu điểm; tiêu điểm 0 px.
- Vùng an toàn cho sub: không đặt chữ hoặc vật quan trọng ở dải y từ 70% đến 100% (sub ngang nằm ở dải này). Nội dung chính nằm trong y từ 8% đến 68% và x từ 6% đến 94%.

### 5.2 Ánh xạ dữ liệu: dùng lại các trường có sẵn của `DiagramSpec`
Giới hạn hiện có: `title` ≤60, `labels` tối đa 12, `series` tối đa 2, `tag` ≤24, `docs` tối đa 2 (mỗi `title` ≤28, `label` ≤28, `value` ≤14), `diff_label` ≤20, `steps` tối đa 5, `block_step` 0 đến 4, `sources` và `uses` tối đa 4 (mỗi mục `label` ≤24 và `value`), `items` tối đa 5, `value` ≤12, `caption` ≤40, `to_value`, `pick` 0 đến 5, `unit` ≤16, `target`.
| Mẫu | Layout | Trường dùng và ý nghĩa |
|---|---|---|
| A | `CASH_RIVER` | `title` chủ đề; `sources` (2 đến 4) dòng tiền vào; `uses` (2 đến 4) dòng tiền ra; `tag` tên chỗ rò (≤24); `value` số lớn kết (≤12); `caption` kết luận (≤40); `unit` |
| B | `PIPELINE_RAIL` | `title`; `steps` (3 đến 5, mỗi ≤14) các trạm; `block_step` trạm kẹt (từ 1 đến số trạm trừ 2, giống `PROCESS_RAIL`); `tag` nhãn thẻ khách (≤24); `value` số đơn mất (≤12); `caption` |
| C | `STACK_WAREHOUSE` | `title`; `items` (2 đến 5) chiều cao từng chồng; `target` vạch sức chứa; `tag` món cần tìm bị che (≤24); `value`; `caption` |
| D | `BOOK_FLIP` | `title`; `docs` (đúng 2: trước và sau); `steps` (3 đến 5) các vật bay về chỗ (≤14); `diff_label` con dấu kết quả (≤20); `caption` |
| E | `LIVE_DASHBOARD` | `title`; `labels` (3 đến 5, mỗi ≤10); `series` (1 đến 2, mỗi chuỗi số giá trị bằng số nhãn); `unit`; `to_value` (0 đến 100) kim đồng hồ; `tag` nhãn cột nổi bật (≤24); `caption` |
| F | `TEAM_BOARD` | `title` vai trò vắng mặt (≤24 thực tế); `steps` (3 đến 5 thẻ việc, mỗi ≤26); `pick` thứ tự nhân vật vắng mặt (từ 0); `tag` nhãn thẻ đỏ (≤24); `value` số việc dồn (≤12); `caption` |
Nếu thấy trường nào không đủ, dừng theo mục 0.4 điểm 1. Không tự thêm trường.

### 5.3 Giá trị chuẩn cho chuyển động và hoàn thiện
- Tốc độ khung hình dựng: 30. Thời lượng cảnh: không quá 10 giây; mẫu D là 9 giây.
- Vi chuyển động nhàn rỗi: vật nổi lên xuống biên độ 6 px (khung 1080), chu kỳ 3 giây, hàm `sine.inOut` lặp qua lại; lá giấy mỏng có thêm xoay ±1,5 độ chu kỳ 4 giây.
- Bóng đổ: lệch xuống phải 10 px ngang và 16 px dọc, làm mờ 22 px, màu `#06111b` độ mờ 30%. Bóng tiếp xúc (khi vật chạm sàn hoặc vật khác): ellipse đậm hơn, độ mờ 45%, co lại khi vật bay lên.
- Hạt phim: một lớp phủ độ mờ 5%, không động hoặc nhấp nháy chậm; vân giấy độ mờ 4%.
- Vào cảnh vật thường: 0,6 giây, `power3.out`, kèm xoay lắng từ 4 độ về 0.
- Vật nặng chạm đất: rơi 0,55 giây `power2.in`, nảy lên 0,35 giây `back.out(1.6)`, ép dẹt 0,94 theo chiều dọc trong 80 ms rồi hồi.
- Con số lớn đặt xuống: từ trên khung, 0,6 giây `back.out(1.8)`, đóng dấu SFX `dong_dau` ngay lúc chạm.
- Làm chậm cho camera: `power2.inOut` hoặc `sine.inOut`; cấm `linear` cho camera trừ cú trượt đều ghi rõ.
- Chuyển cảnh vào và ra: dùng đúng một trong tám kiểu có sẵn (push, cover, scale, dissolve, radial, grid, blur, split), mỗi mẫu một kiểu mặc định ghi ở mục 6; khối thoát cảnh bằng mờ dần 0,25 giây cuối (cơ chế hiện có).
- Giới hạn camera (đề xuất, hiệu chỉnh ở T11): lia ngang tối đa 12% bề rộng khung mỗi giây; cú "quét nhanh rồi dừng" tối đa 40% mỗi giây và kéo dài không quá 0,5 giây; phóng vào hoặc ra tối đa 8% mỗi giây; nâng hoặc hạ tối đa 10% bề cao khung mỗi giây. Mọi cú máy bắt đầu và kết thúc êm (không đạt tốc độ tối đa ngay lập tức).

---

## 6. Thông số riêng của từng mẫu

Cách đọc bảng nhịp: "Máy" ghi trạng thái camera cuối đoạn theo dạng (phóng, dịch ngang %, dịch dọc %) tính từ trạng thái trung tính (1,00; 0; 0). "Từ" là biến sự kiện bám lời (mục 5.2): sự kiện đó phải gắn với một cụm nguyên văn trong lời đọc của chính cảnh.

### 6.1 Mẫu E. `LIVE_DASHBOARD` (làm đầu tiên, thời lượng 10 giây)
**Thế giới:** `-back` bóng nhà thành phố (xám xanh, 3 dải, thị sai 0,5); `-mid` bệ dài ở y 60%, 3 đến 5 cột biểu đồ đặt cách đều từ x 14% đến 70%, đồng hồ đo ở x 82% y 38% đường kính 20% bề cao; `-front` hai thẻ KPI nổi ở x 20% và x 40% y 18% (thị sai 1,6); `-fx` hạt sáng.
**Vật:** cột (tối đa 5, `data-src=static` thân bắt đầu cao 0 và mọc, `data-dst=stay`), đường xu hướng (nét vẽ dần), chấm sáng chạy dọc đường (`fx`), kim đồng hồ (`static`), thẻ KPI (`data-src=offscreen-right`, `data-dst=stay`), chip kết luận (`text`).
**Chuyển cảnh mặc định:** push vào, scale ra.
| Giây | Sự kiện | Chi tiết chuyển động | Máy | SFX | Từ |
|---|---|---|---|---|---|
| 0,0 đến 0,8 | Mở cảnh | Nền và bệ hiện; tiêu đề trượt vào từng từ trễ 0,08 giây, `power3.out` | (1,06; +3; 0) bắt đầu | | |
| 0,6 đến 3,0 | Cột mọc | Mỗi cột mọc 0,8 giây `back.out(1.3)`, cách nhau 0,35 giây; nhãn trục hiện sau khi cột chạm đỉnh; đường xu hướng vẽ dần 1,2 giây, chấm sáng chạy theo | lướt thị sai (1,00; -6; 0) trong 2,4 giây (2,5%/giây) | `luot_nhe` lúc 0,6 | sự kiện 1: cụm nói tới chuỗi dữ liệu |
| 3,0 đến 4,2 | Nhấn cột nổi bật | Máy đẩy vào cột có nhãn `tag`; các cột khác mờ về 55% | (1,09; -9; -3) | | sự kiện 2: cụm nói tới điểm nổi bật |
| 3,2 đến 5,2 | Kim đồng hồ | Kim quét từ 0 tới `to_value` theo `elastic.out(1,0,6)` thực tế 1,1 giây, vượt 4% rồi lắng; qua ngưỡng 70% đổi màu san hô | | `go_nhe` lúc 3,4; `canh_bao` nếu ≥70% | sự kiện 3: cụm nói tới tỉ lệ |
| 4,6 đến 5,6 | Thẻ KPI vào | Thẻ vào từ ngoài phải 0,6 giây `power3.out`, nảy nhẹ 6 px, thẻ thứ hai trễ 0,25 giây | | `bat_mo` lúc 4,6 | |
| 5,8 đến 8,0 | Chuỗi thứ hai | Chuỗi 2 vẽ dần 1,6 giây; hai đường giao nhau ở điểm giao: vòng sáng xung 2 nhịp mỗi 0,5 giây | quét ngang (1,03; +4; 0) | `luot_nhanh` lúc 5,8 | sự kiện 4: cụm nói tới chuỗi thứ hai |
| 8,0 đến 9,4 | Lùi ra, kết luận | Máy lùi toàn cảnh; chip `caption` trượt từ dưới lên 0,5 giây `power3.out` | (1,00; 0; 0) | `dong_dau` lúc 8,6 | sự kiện 5: câu kết |
| 9,4 đến 10,0 | Giữ khung | Chỉ còn vi chuyển động; thoát mờ 0,25 giây cuối | | | |
**Giới hạn:** tối đa 5 cột, 2 thẻ KPI, 1 đồng hồ, 2 đường xu hướng. Không thêm hạt. Số phần tử chuyển động đồng thời không quá 12.
**Ba bộ dữ liệu thử:** (1) bài 04 quảng cáo (cột lượt xem cao, cột đơn thấp, 3 nhãn), (2) bài 07 doanh thu tăng lợi nhuận giảm (2 chuỗi, 4 nhãn), (3) bài 17 báo cáo (5 nhãn, nhãn dài 10 ký tự, `tag` dài 24 ký tự).
**Trường hợp biên:** 3 nhãn so với 5 nhãn; chuỗi phẳng (kiểm tra không vẽ đường thẳng nhàm chán: yêu cầu giá trị không phẳng theo quy tắc hiện có của `CHART_STORY`); `to_value` bằng 0 và bằng 100.

### 6.2 Mẫu A. `CASH_RIVER` (10 giây)
**Thế giới:** `-back` trời giấy và đồi xa (thị sai 0,5); `-mid` dòng sông giấy chạy từ trái sang phải ở y 38% đến 52% gồm 3 dải cong; các nhánh phụ đổ vào từ trái (số nhánh bằng số `sources`) hội tụ ở x 22%; ở x 50% sông tách nhánh theo `uses`; lỗ cống ở x 62% y 58% (chỗ rò); hồ chứa bên phải x 74% đến 94% y 30% đến 62%; `-front` cỏ giấy và đá nhô lên (thị sai 1,6, làm mờ 3 px khi không tiêu điểm).
**Vật:** đồng xu (tối đa 24 tạo ra, tối đa 14 hiện cùng lúc; `data-src=offscreen-left`; `data-dst=sink-into:cong` hoặc `stay` trong hồ), túi tiền (2), xoáy cống (`fx`), vạch mực nước (`prop`), nhãn nguồn và nhãn dùng (`text`).
**Chuyển cảnh mặc định:** cover vào, blur ra.
| Giây | Sự kiện | Chi tiết | Máy | SFX | Từ |
|---|---|---|---|---|---|
| 0,0 đến 1,0 | Mở cảnh | Máy lùi ra lộ sông; tiêu đề trồi theo từng từ; xu 1 đến 6 vào từ ngoài trái cách nhau 0,35 giây, tốc độ 18% bề rộng mỗi giây, nhấp nhô 5 px | (1,12; +4; 0) tới (1,00; 0; 0) | `luot_nhe` lúc 0,2 | |
| 1,0 đến 3,5 | Nguồn vào | Nhãn nguồn bật lên `back.out(1,4)` đúng mốc từ; xu tăng tới 12 và chia nhánh theo đường dẫn | lia theo dòng (1,00; -10; 0) trong 2,5 giây (4%/giây) | | sự kiện theo từng nguồn |
| 3,5 đến 6,0 | Cống mở | Xoáy cống mở 0,5 giây `back.out`; xu gần cống tăng tốc `power2.in`, quay vòng cung, xoay 360 độ, co về 0 trong xoáy (không tan đột ngột), cách nhau 0,35 giây; chip `tag` trượt lên 0,5 giây | đẩy vào (1,08; -10; +5) | `canh_bao` lúc 3,8 | sự kiện: cụm nói tới chỗ rò |
| 6,0 đến 8,0 | Hồ cạn | Mực nước hạ 18% chiều cao trong 1,6 giây `power2.inOut`; đống xu đáy hồ rung nhẹ | | `go_nhe` khi xu chạm đáy | sự kiện: cụm nói tới hậu quả |
| 8,0 đến 9,4 | Đổi nét, số lớn | Đổi nét từ cống (mờ 0 lên 4 px) sang hồ (mờ 4 xuống 0 px) trong 0,8 giây; số `value` rơi từ trên xuống y 30% theo mục 5.3 | (1,04; +2; 0) | `dong_dau` | sự kiện: con số |
| 9,4 đến 10,0 | Chip kết luận | `caption` trượt vào; thoát mờ | | | |
**Giới hạn:** xu tối đa 24 tạo, 14 hiện cùng lúc; tối đa hai lớp làm mờ; không bộ lọc nặng khác.
**Ba bộ dữ liệu thử:** bài 08 thiếu tiền trả lương, bài 09 không vay được vốn, bài 10 giảm giá lỗ nặng. **Biên:** 2 so với 4 nguồn và dùng; nhãn 24 ký tự; `value` 12 ký tự.

### 6.3 Mẫu B. `PIPELINE_RAIL` (10 giây)
**Thế giới:** băng chuyền ngang rộng 300% bề rộng khung (máy lia dọc theo nó); trạm đặt đều tại x 30%, 90%, 150%, 210%, 270% khung theo số `steps`; `-back` tường xưởng và cửa sổ (thị sai 0,5); `-front` bóng đèn trạm và dây điện (thị sai 1,6).
**Vật:** thẻ hồ sơ (6 đến 8; `data-src=offscreen-left`; thẻ cuối `data-dst=offscreen-bottom`, các thẻ khác `occluded-by:` trạm cuối hoặc `stay`), đèn trạm (`light`), bảng tên trạm (`text`), chip mất đơn (`text`).
**Chuyển cảnh mặc định:** push vào, scale ra.
| Giây | Sự kiện | Chi tiết | Máy | SFX | Từ |
|---|---|---|---|---|---|
| 0,0 đến 1,2 | Mở cảnh | Băng chuyền hiện; bảng tên trạm trồi ra trễ 0,12 giây; thẻ 1 vào từ trái với tốc độ 14% bề rộng khung mỗi giây | (1,00; 0; 0) | | |
| 1,2 đến 4,0 | Chạy qua trạm | Mỗi thẻ qua trạm có chớp đèn 0,15 giây; thẻ lên xuống nhẹ theo mối nối 3 px | lia ngang tới (1,00; -30; 0) trong 2,8 giây (khoảng 10,7%/giây, trong giới hạn 12%/giây) | `go_nhe` mỗi trạm | sự kiện: tên từng trạm |
| 4,0 đến 6,0 | Kẹt | Thẻ dừng ở trạm `block_step` (giảm tốc 0,3 giây `power2.out`, ép dẹt 0,96); các thẻ sau dồn lại, mỗi thẻ nén 6 px; đèn trạm đỏ nhấp 2 nhịp | đẩy vào (1,07; -34; 0) | `canh_bao` lúc 4,2 | sự kiện: cụm nói tới chỗ kẹt |
| 6,0 đến 8,0 | Thẻ rơi | Thẻ cuối hàng nghiêng 18 độ, trượt khỏi mép băng chuyền, rơi 0,7 giây `power2.in` xoay 35 độ, nảy một lần, rồi trượt ra khỏi khung xuống dưới (có đích) | (1,07; -34; +3) | `go_nhe` khi chạm | sự kiện: cụm nói tới thiệt hại |
| 8,0 đến 9,4 | Đổi nét, số đếm | Đổi nét sang thẻ vừa rơi; chip mất đơn hiện; con số `value` đếm 0 tới giá trị trong 1,0 giây `power1.out` | | `dong_dau` lúc 8,6 | sự kiện: con số |
| 9,4 đến 10,0 | Giữ khung | Thoát mờ | | | |
**Giới hạn:** tối đa 8 thẻ, 5 trạm; thẻ khi dồn không chồng lên nhau quá 30% bề rộng.
**Ba bộ dữ liệu thử:** bài 01 phễu bán hàng, bài 02 báo giá im lặng, bài 13 giao hàng trễ.

### 6.4 Mẫu C. `STACK_WAREHOUSE` (10 giây)
**Thế giới:** `-back` tường kho và kệ cao (thị sai 0,5); `-mid` sàn kho ở y 66%, các chồng hộp đặt cách đều theo số `items`, vạch sức chứa `target` là đường đứt ngang; `-front` cột kho và biển báo (thị sai 1,6).
**Vật:** hộp giấy (tối đa 20 hộp, ba cỡ; `data-src=offscreen-top`; `data-dst=stay`), bụi khi chạm (`fx`), xe nâng (`data-src=offscreen-right`, `data-dst=stay`), nhãn món bị che (`text`).
**Chuyển cảnh mặc định:** cover vào, blur ra.
| Giây | Sự kiện | Chi tiết | Máy | SFX | Từ |
|---|---|---|---|---|---|
| 0,0 đến 2,0 | Hộp rơi | Hộp rơi từ ngoài trên theo mục 5.3, cách nhau 0,18 giây, xếp chồng đúng chiều cao `items`; bụi 0,4 giây mỗi lần chạm | (1,00; 0; 0) tới (1,03; 0; 0) | `go_nhe` mỗi hộp | |
| 2,0 đến 5,0 | Nâng máy | Máy nâng lên lộ tầng trên; chồng vẫn cao thêm qua vạch sức chứa; chồng lắc xoay ±1,2 độ, hai nhịp 0,6 giây | nâng tới (0,92; 0; +22) trong 3 giây (khoảng 7,3%/giây, trong giới hạn 10%/giây) | | sự kiện: cụm nói tới đầy kho |
| 5,0 đến 7,0 | Chồng nghiêng | Chồng chính nghiêng 4 độ; hộp giữa chứa món cần tìm bị đẩy lệch ngang 8 px; chip `tag` chỉ vào hộp; hộp trên cùng xê dịch | (0,96; 0; +12) | `canh_bao` lúc 5,2 | sự kiện: cụm nói tới món bị che |
| 7,0 đến 9,0 | Xe nâng | Xe nâng vào từ ngoài phải 1,6 giây `power1.out`, giảm tốc, dừng trước chồng, lắc càng nâng 2 nhịp (không với tới) | đổi nét sang xe nâng | | |
| 9,0 đến 10,0 | Kết | `value` đặt xuống; thoát mờ | (1,00; 0; 0) | `dong_dau` | sự kiện: con số |
**Giới hạn:** tối đa 20 hộp, 1 xe; số lớp bóng đổ không vượt 2.
**Ba bộ dữ liệu thử:** bài 11 kho đầy, bài 12 đội xe, bài 10 hàng tồn (biên: 2 chồng so với 5 chồng).

### 6.5 Mẫu D. `BOOK_FLIP` (9 giây)
**Thế giới:** mặt bàn nhìn từ trên, nghiêng phối cảnh 18 độ quanh trục ngang, khoảng cách phối cảnh 1600 px; trang giấy lớn ở giữa chiếm x 18% đến 82%, y 14% đến 66%; `-back` mặt bàn gỗ giấy; `-front` bút và kẹp giấy nhô vào khung (thị sai 1,6).
**Vật:** đống giấy lộn xộn bên trái (8 đến 10 mảnh, xoay ngẫu nhiên có hạt giống cố định trong ±12 độ), ghi chú dán (3, rung nhẹ), trang lật (hai mặt), các vật bay về chỗ (`steps`, tối đa 5), ngăn sắp xếp.
**Chuyển cảnh mặc định:** scale vào, dissolve ra.
| Giây | Sự kiện | Chi tiết | Máy | SFX | Từ |
|---|---|---|---|---|---|
| 0,0 đến 2,5 | Trạng thái trước | Nhãn "trước" từ `docs[0]`; ghi chú dán rung nhẹ; giấy nhấp nhô 4 px | vòng cung (1,02; +2; 0), xoay khung -6 độ tới +2 độ | | sự kiện: cụm nói tới tình trạng trước |
| 2,5 đến 4,0 | Lật trang | Trang quay 0 tới -170 độ quanh gáy, 1,5 giây `power2.inOut`; đổ bóng quét qua; tới 90 độ thì đổi nội dung sang `docs[1]`; mặt sau dùng giấy trắng có vân | | `lat_trang` lúc 2,6 | sự kiện: cụm chuyển ý |
| 4,0 đến 7,5 | Giấy bay về | Mỗi vật rời đống (`spawn-from:dong_giay`) bay theo đường cong cao hơn điểm đầu 18% bề cao, 0,7 giây `power2.inOut`, trễ 0,35 giây giữa hai vật, xoay về 0 độ, rơi vào ngăn, ép dẹt 0,97 | máy giữ (1,02; +1; 0) | `luot_nhanh` đầu mỗi vật; `go_nhe` khi vào ngăn | sự kiện: mỗi vật gắn một cụm trong lời đọc |
| 7,5 đến 9,0 | Con dấu | Đẩy vào kết quả; con dấu `diff_label` phóng 1,6 về 1, xoay -4 độ về 0, 0,4 giây `back.out(1,8)` | (1,06; 0; 0) | `dong_dau` lúc 8,0 | sự kiện: câu kết |
**Giới hạn:** tối đa 10 mảnh giấy lộn xộn, 5 vật bay về; nội dung hiển thị ở mặt sau trang phải được thiết kế riêng, không để lộ mặt gương.
**Ba bộ dữ liệu thử:** bài 06 khách cũ, bài 18 quay lại Excel, một bài tự chọn khác có hai trạng thái trước và sau.

### 6.6 Mẫu F. `TEAM_BOARD` (10 giây; làm sau cùng)
**Thế giới:** mặt bàn giao việc nhìn từ trên: hàng nhân vật origami ngồi phía trên (3 hoặc 4, bằng số `steps` nhỏ hơn hoặc bằng 4), bảng ba cột phía dưới (nhãn cột cố định bằng tiếng Việt: "Mới", "Đang làm", "Chờ"); `-back` bàn gỗ giấy; `-front` cốc bút và giấy ghi chú nhô vào (thị sai 1,6).
**Vật:** nhân vật (3 đến 4; mỗi người có hai tư thế: thẳng, nghiêng; người vắng mặt có `data-dst=offscreen-left`), thẻ việc (tối đa 8; `data-src=spawn-from:<nhân vật>`), thẻ đỏ (`data-src=spawn-from:cot_cho`), ghế trống (`static`).
**Chuyển cảnh mặc định:** push vào, scale ra.
| Giây | Sự kiện | Chi tiết | Máy | SFX | Từ |
|---|---|---|---|---|---|
| 0,0 đến 3,0 | Chuyền việc trôi chảy | Thẻ bay giữa hai nhân vật theo đường cong 0,8 giây `power2.inOut`; người gửi nghiêng 6 độ trước khi gửi 0,2 giây (dự báo), người nhận nghiêng đón; hai nhân vật tham gia ở nét, nhân vật còn lại mờ 3 px | đổi nét giữa hai người (1,02; 0; 0) | `go_nhe` mỗi thẻ | sự kiện: cụm nói tới giao việc |
| 3,0 đến 6,0 | Người ra quyết định vắng | Nhân vật thứ `pick` đứng dậy, đi ra ngoài trái 1,2 giây `power1.inOut`; ghế trống; thẻ gửi cho người đó trượt xuống đáy cột và chất đống, mỗi thẻ nảy 4 px; cột tối dần xuống 55% trong 1,5 giây | (1,02; 0; 0) | `luot_nhe` lúc 3,2 | sự kiện: cụm nói tới sự vắng mặt |
| 6,0 đến 9,0 | Dồn việc | Đống thẻ cao dần; thẻ đỏ `tag` bật lên scale 0 tới 1,2 tới 1 theo `elastic.out(1,0,6)` 0,6 giây rồi rung 3 nhịp ±3 px | đẩy vào (1,06; 0; +3) | `canh_bao` lúc 6,3 | sự kiện: cụm nói tới hậu quả |
| 9,0 đến 10,0 | Kết | Lùi toàn bàn; `value` và `caption` hiện; thoát mờ | (1,00; 0; 0) | `dong_dau` | |
**Giới hạn:** tối đa 4 nhân vật, 8 thẻ; hoạt hình nhân vật chỉ gồm 2 tư thế cộng nội suy; nếu nhân vật trông cứng ở cổng G6, theo kế hoạch tổng có thể thay Mẫu F bằng Mẫu B (báo người giao việc, không tự thay).
**Ba bộ dữ liệu thử:** bài 14 giám đốc nghỉ, bài 03 gọi khách, một bài tự chọn khác có nhiều người xử lý.

---

## 7. Hướng dẫn chạy các cổng (thủ tục cụ thể)

Mỗi cổng ghi báo cáo vào `<ma_mau>/10_cong/<ten_cong>.md` gồm: ngày giờ, tên người hoặc agent chạy, bảng tiêu chí (đạt hoặc không đạt), bằng chứng, kết luận.

### 7.1 G0. Chuẩn bị
Kiểm: tờ yêu cầu đủ mục; mọi tài sản là SVG tự vẽ, không liên kết ngoài, không chữ nhúng; thử hiển thị mọi dấu tiếng Việt kể cả chữ hoa Đ, Ắ, Ễ, Ộ, Ứ ở cỡ nhỏ nhất của mẫu; không từ mẫu tiếng Anh (dùng quét có sẵn).

### 7.2 G1. Thiết kế chuyển động
Kiểm bảng nhịp: (1) mỗi vật `prop` có nguồn vào và đích ra; (2) mỗi cảnh một hành động chính, không quá hai hành động phụ; (3) có đúng một cú máy chính trong bộ từ vựng; (4) khoảng cách giữa hai sự kiện liên tiếp không quá 2,5 giây (khớp `DIAGRAM_SECONDS_PER_EVENT`); (5) mỗi sự kiện chính có mốc từ; (6) số phần tử không vượt giới hạn; (7) các giá trị camera nằm trong giới hạn mục 5.3. Người duyệt: Founder hoặc người được ủy quyền; hạn 2 ngày làm việc.

### 7.3 G3. Chuyển động (cổng quan trọng nhất)
Dùng công cụ ghi vết (T02) chạy trên cả ba bộ dữ liệu. Các phép kiểm, mỗi phép phải đạt trên cả ba:
1. **Không dịch chuyển tức thời:** giữa hai khung liền nhau, tâm của bất kỳ vật `prop` nào không dịch quá 12% bề rộng khung (trừ cú quét nhanh có chủ ý được ghi trong bảng nhịp, ngưỡng 24%).
2. **Xuất hiện và biến mất đúng luật:** mọi lần số vật `prop` nhìn thấy được tăng phải khớp một vật có `data-src` bắt đầu đúng lúc và ở đúng nguồn (vật bắt đầu ngoài khung hoặc bên trong vật nguồn); mọi lần giảm phải khớp `data-dst`. Một vật chuyển từ độ mờ 0 lên độ mờ trên 0,3 trong khung giữa tại chỗ (không từ ngoài khung hoặc từ vật nguồn) là lỗi.
3. **Nhịp 2 giây:** trong mọi cửa sổ trượt 2,5 giây có ít nhất một sự kiện bắt đầu (vật mới vào, thay đổi cú máy, thay đổi tiêu điểm).
4. **Tốc độ camera:** đo từ chuỗi độ phóng và dịch của `-world`; không vượt giới hạn mục 5.3.
5. **Chuyển động có khối lượng:** với mỗi vật `prop` có điểm dừng, gia tốc giảm dần trong 0,15 giây trước điểm dừng (không dừng đột ngột); vật nặng (hộp, xe) có phản ứng (nảy hoặc ép dẹt) ngay khung sau va chạm.
6. **Bám lời:** mỗi sự kiện chính nằm trong ±200 ms so với mốc từ của cụm tương ứng (lấy mốc từ từ dữ liệu thử có thời gian từng từ).
7. **Soát bằng mắt:** người duyệt xem lại toàn bộ cảnh ở tốc độ 0,5 lần, ghi mọi chỗ vật "tự di chuyển" vô lý.
**Đạt khi:** 0 vi phạm ở phép 1 và phép 2; các phép 3 đến 6 đạt; soát bằng mắt không có lỗi nặng.

### 7.4 G4. Thị giác
Ảnh chụp ở 10%, 30%, 50%, 70%, 90% và mỗi mốc đổi cú máy, cho cả ba bộ dữ liệu. Kiểm: chữ không tràn mép và không bị che; tương phản chữ nền từ 4,5 trên 1 cho chữ nhỏ (tỉ lệ độ sáng tương đối chuẩn WCAG); không chữ hoặc vật quan trọng trong dải y 70% đến 100%; bảng màu đúng mục T00; không lộ mặt sau hoặc cạnh vật; dấu tiếng Việt rõ ở cỡ nhỏ nhất; vùng sub không bị vật chính che khi giả lập sub 3 dòng đặt ở đáy.

### 7.5 G5. Hiệu năng
Dựng ở chất lượng sản xuất, một tiến trình, `workers` bằng 1. Đạt khi: thời gian thực không quá 10 giây cho mỗi giây video; đỉnh RAM tiến trình dựng không quá 6 GB; tệp ra không quá 4 MB cho mỗi giây video. Nếu vượt gấp đôi ngân sách, dừng theo mục 0.4 điểm 3.

### 7.6 G6. Duyệt của Founder
Agent chuẩn bị gói duyệt: video chất lượng sản xuất của ba bộ dữ liệu, bộ ảnh chụp G4, báo cáo G3, phiếu chấm trống (Phụ lục C). Founder chấm 8 tiêu chí thang 5; đạt khi trung bình từ 4,0 và không tiêu chí nào dưới 3. Agent không tự chấm thay.

### 7.7 G7. Vào sản xuất
Đạt khi: G0 đến G6 đạt; mẫu chạy tốt với ba bộ dữ liệu; đã đăng ký theo T50; hợp đồng biến được ghi chép; thêm vào `catalog.json` hoặc danh mục tương ứng đúng định dạng hiện có; có hướng dẫn một trang "khi nào dùng mẫu này"; có ghi chú hồi quy.

---

## 8. Mẫu báo cáo mỗi nhiệm vụ (`bao_cao/<ma_nhiem_vu>.md`)
1. **Nhiệm vụ và trạng thái:** đạt, chưa đạt, hoặc đang chờ quyết định.
2. **Việc đã làm:** liệt kê từng bước, mỗi bước một dòng.
3. **Tệp đã tạo hoặc sửa:** đường dẫn đầy đủ và số dòng đổi (từ `git diff --stat`).
4. **Bằng chứng:** đường dẫn ảnh, video nháp, tệp ghi vết, kết quả test (tên test, đạt hoặc đỏ).
5. **So với đường cơ sở:** test đỏ mới (nếu có) và nguyên nhân.
6. **Phát hiện ngoài phạm vi:** việc thấy cần làm nhưng chưa làm.
7. **Câu hỏi hoặc quyết định cần người giao việc:** đánh số.
8. **Bước tiếp theo đề xuất.**

---

## 9. Xử lý sự cố thường gặp
| Hiện tượng | Nguyên nhân thường gặp | Việc làm |
|---|---|---|
| Vật giật hoặc nhảy vị trí | Hai chuyển động cùng điều khiển một thuộc tính | Tách thành hai lớp phần tử hoặc gộp thành một dòng thời gian |
| Vật hiện đột ngột | Quên nguồn vào, hoặc thời điểm bắt đầu sớm hơn lúc vật vào khung | Dựng lại đường vào từ ngoài khung |
| Chữ hiển thị tiếng Anh | Chữ cố định trong khối chưa bản địa hoá | Thêm vào `_VIETNAMESE_TEXT` hoặc dùng biến |
| Dựng treo hoặc quá chậm | Quá nhiều phần tử, bộ lọc nặng | Giảm số phần tử về giới hạn, bỏ bộ lọc nặng, dựng chất lượng nháp |
| Kiểm HyperFrames báo lỗi cấu trúc | Định danh trùng giữa hai lần dùng khối | Dùng cơ chế đổi định danh `prepare_block` (đã đổi tên theo `cid`) |
| Mặt sau trang lật lộ ra | Lật 3D không ẩn mặt sau | Ẩn mặt sau hoặc thiết kế mặt sau |
| `git diff` hiện hàng trăm dòng cho một thay đổi nhỏ | Kiểu xuống dòng bị đổi | Khôi phục đúng kiểu xuống dòng của tệp (mục 0.3) |
| Lỗi mã hoá `charmap` khi in | Thiếu UTF-8 | Đặt `PYTHONIOENCODING=utf-8` |
| Test đỏ không rõ nguyên nhân | Có thể là test nền | Đối chiếu danh sách đường cơ sở T00 |

---

## Phụ lục A. Định dạng tệp ghi vết chuyển động (mô tả, không mã)
Một tệp JSON mỗi cảnh. Trường mức đầu: tên layout, thời lượng giây, tốc độ khung hình (30), bộ dữ liệu dùng, danh sách khung. Mỗi khung có: chỉ số khung, thời điểm giây, trạng thái camera (độ phóng, dịch ngang phần trăm, dịch dọc phần trăm), và danh sách vật. Mỗi vật có: `data-obj`, `data-kind`, `data-src`, `data-dst`, tâm x và y (phần trăm khung), bề rộng và bề cao (phần trăm khung), độ mờ (0 đến 1), góc xoay (độ), cờ nhìn thấy được (độ mờ trên 0,05 và nằm ít nhất một phần trong khung). Công cụ phân tích dùng cờ nhìn thấy được để phát hiện xuất hiện và biến mất.

## Phụ lục B. Gán bài vào mẫu (đề xuất, dùng cho bộ dữ liệu thử và quy tắc chọn)
| Bài | Mẫu chính | Bài | Mẫu chính |
|---|---|---|---|
| 01 | B | 11 | C |
| 02 | B | 12 | C |
| 03 | F | 13 | B |
| 04 | E | 14 | F |
| 06 | D | 17 | E |
| 07 | E | 18 | D |
| 08 | A | | |
| 09 | A | | |
| 10 | A | | |
Dữ liệu thử lấy từ nội dung bài tại `Documents/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/kich_ban/noi_dung_abstract_2026` (tên tệp bắt đầu bằng số bài). Chỉ đọc.

## Phụ lục C. Phiếu chấm G6
| Tiêu chí | Điểm 1 đến 5 | Ghi chú sửa |
|---|---|---|
| Chất liệu và nhất quán | | |
| Chuyển động tự nhiên | | |
| Lia máy | | |
| Nhịp | | |
| Bám lời | | |
| Dễ đọc | | |
| Độc đáo | | |
| Sẵn sàng sản xuất | | |
| Trung bình | | |
| Kết luận (Đạt, Sửa, Loại) | | |

## Phụ lục D. Thuật ngữ
- **Layout:** tên một loại cảnh trong storyboard (ví dụ `LIVE_DASHBOARD`).
- **Khối (block):** tệp HTML dựng sẵn của HyperFrames.
- **Manifest:** tệp JSON ánh xạ dữ liệu storyboard sang biến của khối.
- **Cổng (gate):** điểm kiểm bắt buộc, không đạt thì không sang bước sau.
- **Ghi vết:** tệp ghi vị trí mọi vật tại mỗi khung hình để kiểm tự động.
- **Thị sai:** các lớp trôi với tốc độ khác nhau khi camera dịch chuyển, tạo chiều sâu.
- **Đổi nét (rack focus):** chuyển độ nét từ vật này sang vật khác.
