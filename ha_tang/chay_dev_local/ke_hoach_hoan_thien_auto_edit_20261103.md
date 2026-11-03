# Kế hoạch hoàn thiện AI edit video tự động

> Dành cho agent thực thi: dùng skill `executing-plans`, làm tuần tự từng đầu việc và ghi bằng chứng vào sổ bên dưới. Founder đã yêu cầu lập kế hoạch rồi làm theo; không hỏi lại quyền tiếp tục giữa các mốc. Không tự chia việc sang agent khác hoặc sửa luồng AI Video của AGY.

**Mục tiêu:** Video quay dài gồm nhiều kịch bản được AI hiểu từ tiếng nói, chọn take tốt, dựng thành các video hoàn chỉnh theo nhịp của hai mẫu, có diễn họa giấy 2D/3D, karaoke của hệ thống và ít việc chỉnh tay nhất có thể.

**Kiến trúc:** FE/BE và trình duyệt Flow chạy local. ASR, render, gỡ logo, chuẩn hóa âm thanh và QC chạy trên GitHub Actions, concurrency nặng = 1. Dùng pipeline Auto Edit hiện hữu; LLM 9Router thật quyết định nội dung, công cụ, thời điểm và bố cục. Renderer xác thực và thực thi timeline, không tự thay quyết định nội dung.

**Công nghệ:** FastAPI, SQLite hiện hữu, FFmpeg, HyperFrames/Remotion hiện hữu, Google Flow, 9Router, GitHub Actions, Cloudflare Tunnel.

**Đặc tả nguồn:** Yêu cầu Founder trong hội thoại; `AGENTS.md`; hai video mẫu chỉ đọc; các yêu cầu nghiệm thu bên dưới. Các đường dẫn code trong kế hoạch tương đối với gốc checkout local đã quản lý.

## 1. Phạm vi và trạng thái có bằng chứng

- Checkout: `C:/Users/Baha Group/Documents/PRJ_069_Sin_Xay_kenh_git_push_wt_auto_edit_ui`, nhánh `dev/local-remote-video-tests`.
- Mẫu 1: `Z:/01_du_an/PRJ_069_Sin_Xay_kenh/mau1.mp4`, 123,74 giây, 1080×1920, 30 fps, có âm thanh; ffprobe kiểm ngày 03/11/2026.
- Mẫu 2: `Z:/01_du_an/PRJ_069_Sin_Xay_kenh/mau2.mp4`, 63,09 giây, cùng kích thước/fps, có âm thanh. Hai mẫu cho thấy không được ép mỗi content xuống 20–25 giây.
- Nguồn thử: DJI gốc 8.428.283.732 byte; bản E2E hiện dùng đoạn đầu 120 giây stream-copy từ nguồn, không dùng lại video đã edit.
- Đã có MP4 66,47 giây, 5 cảnh Flow thật đã gỡ logo và 1 HyperFrames alpha; decode đạt, HTTP asset 200 và video Range 206. Đây là bằng chứng nối engine, chưa phải nghiệm thu chất lượng hoặc kiểm thử trọn 8 GB.
- Link bản hiện hữu: https://nhap-xaykenh-prj069.bahagroup.vn/auto-edit?project_id=d39ecdf3-07a1-5390-b938-dd171799bf20&asset_id=c6bde0f4-dc9a-5a18-ade5-e0f0aa5cda98
- Lỗi xác nhận qua mã và hình: overlay không có `setpts` dời tới thời điểm chèn; FFmpeg có thể giữ frame cuối đã giảm opacity. Checklist có chữ nhỏ do thu toàn canvas vào ô nhỏ. Style Auto Edit trước đó lấy quy tắc kính từ AI Video; đã tách lại origami ở `f40b9fd`, mới kiểm thử planner, chưa render lại style đó.
- Script `e2e_giong_sep.py` chỉ là công cụ chẩn đoán: có chia nhịp bằng tay và dùng file cache. Không được dùng script này thay bằng chứng pipeline sản phẩm chạy từ giao diện tới MP4.

## 2. Ràng buộc xuyên suốt

1. Không render/ASR nặng tại máy 8 GB; không dùng NAS làm máy tính toán. Không tắt máy/NAS.
2. Không sửa/xóa nguồn gốc, mẫu tham chiếu hoặc lấy video đã burn sub làm đầu vào lần sau.
3. Không mở lại hồ sơ Flow khi có job đang giữ khóa. Không sao chép cookie. Không gửi lại cảnh đã submit khi chưa đối chiếu trạng thái.
4. Flow tạo nguồn 10 giây; timeline chọn 3–6 giây phù hợp lời nói. Cache cảnh theo request/style để chạy lại không tạo trùng hoặc dùng nhầm style cũ.
5. 9Router thật, không mock trong E2E. Test unit có fake để tái hiện lỗi, phải ghi rõ khác với E2E thật.
6. Giữ mặt và tiếng thật của người nói. Diễn họa có thể full-frame, alpha overlay, nền đục hoặc speaker PIP tùy kịch bản; không ép mọi cảnh vào một bố cục.
7. Video đầu ra 9:16, 1080×1920, 30 fps; âm thanh -14 LUFS ±1, true peak ≤ -1 dBTP. Safe zone trên 150, dưới 320, phải 120 px.
8. Chỉ video edit hoàn chỉnh xuất hiện ở trang `/auto-edit`. AI Video là project/luồng riêng. Không đưa audio, sub, cảnh rời vào danh sách thành phẩm.
9. Không sửa chồng `runner.py`, `sfx.py`, `render_engines.py` đang có diff của AGY. Nếu cần thay interface, ghi giao điểm và kiểm tra diff trước.
10. Mỗi mốc có commit, log và artifact cụ thể. Không dùng số test đạt, hash khác nhau hay file MP4 tồn tại để kết luận nội dung đẹp hoặc đạt 95%.

## 3. Bảng nghiệm thu cuối

| Hạng mục | Bằng chứng bắt buộc | Điều kiện không đạt |
|---|---|---|
| Chia kịch bản, chọn take | Transcript có word ID; lý do LLM; đối chiếu audio ở điểm đầu/cuối | Cắt theo im lặng đơn thuần, cụt ý hoặc giữ take vấp hơn |
| Phong cách mẫu | Biên bản xem hai mẫu có timecode; xem bản kết quả liên tục | Chỉ có screenshot hoặc tự nhận tương đương |
| Diễn họa | Origami theo style, đúng ý lời; có cảnh 2D/3D và lựa chọn bố cục có lý do | Kính/kim loại lệch style, slide chữ tĩnh, hình không giải thích nội dung |
| Animation | Video trước/trong/sau mỗi cue; frame sai khác tại thời điểm nằm trong cảnh | Overlay đã chạy hết trước lúc hiện, lặp frame cuối hoặc đứng hình |
| Độ rõ | Xem ở viewport 360×640; chữ nội dung diễn họa tối thiểu 16 px trên viewport (48 px trên output 1080), nội dung không tràn | Checklist mờ/nhỏ, opacity ngoài ý đồ, chữ thiếu tương phản |
| Karaoke | Style hệ thống, cỡ 70 đã yêu cầu, hai màu, nhấn theo từ; nghe và xem tối thiểu 10 điểm neo | Sub chồng, lỗi từ quan trọng, lệch từ quá 150 ms tại điểm kiểm |
| Âm thanh | Báo cáo LUFS/true peak; nghe toàn clip | Clip giọng, mất âm, nhạc/SFX át lời hoặc tự thêm voice |
| Gỡ logo | Manifest đủ cảnh; kiểm tra khung góc logo đầu/giữa/cuối từng cảnh | Adapter fallback bản gốc hoặc chỉ prompt “không logo” |
| Web | Đăng nhập hiện hữu, project AUTO_EDIT, phát/seek được trên UI, Range đầu/cuối 206 | Chỉ health 200 hoặc chỉ file local |
| Nguồn lớn | Job từ upload file 8 GB; hash, resume, peak RAM/disk, output thật | Chỉ dùng đoạn nhỏ rồi nhận xử lý được 8 GB |

## 4. Các mốc thực thi theo thứ tự

### M0 — Chốt đối chiếu mẫu và một clip nghiệm thu

**Tệp:** tạo `ha_tang/chay_dev_local/doi_chieu_mau_auto_edit.md`; bằng chứng ở `sin_content_api/08_kiem_thu/bang_chung/hoan_thien_auto_edit_20261103/`.

- [ ] Xem mẫu 1 và 2, ghi timecode ít nhất hook, 2 overlay, 2 cutaway, 1 chuyển cảnh, phụ đề và kết thúc của từng mẫu. Phân biệt điều quan sát được với suy đoán.
- [ ] Ghi quy tắc áp dụng: nhịp lời, mật độ thay đổi hình, animation vào/ra, kích thước chữ, âm thanh; giữ style BAHA giấy gấp thay vì sao chép nhận diện mẫu.
- [ ] Dùng transcript nguồn để LLM chọn một content hoàn chỉnh khoảng 60–120 giây, giữ lý do, take và mốc từ. Không ép độ dài nếu content cần dài hơn.
- [ ] Lưu storyboard review được với thumbnail/layout từng cue, gồm khung đọc ở 360×640. Dựa trên mock/ý đồ đã được Founder duyệt trong hội thoại; thay đổi thiết kế lớn phải trình một mẫu cụ thể, không hỏi câu chung chung.

**Đạt M0:** có bảng đối chiếu timecode và một storyboard có đầy đủ lời, tool, layout, style và khoảng thời gian; không có mục chỉ ghi “thêm hiệu ứng cho đẹp”.

### M1 — Sửa đúng lỗi overlay đứng hình và khó đọc

**Tệp sửa:** `sin_content_api/src/modules/media_studio/video_processor.py`, `sin_content_api/src/modules/dieu_phoi_dung/dung_video_dai.py`. **Tệp test:** thêm `sin_content_api/tests/test_overlay_dung_moc.py`; cập nhật các test layout trong `sin_content_api/tests/dung_video_dai_test.py`. Chỉ sửa scene/CSS trong `hf_scenes.py` khi chứng minh cần thiết và kiểm tra không chồng công việc AGY.

**Interface:** giữ `VideoProcessor.render_timeline_document(...)`; mỗi overlay có `asset_id,start_ms,duration_ms,x,y,width,height`, PIP có trim nguồn. `_tao_timeline(...)` vẫn là một đường xây timeline cho cả sản phẩm và E2E.

- [ ] Viết test tái hiện overlay động 2 giây bắt đầu ở giây 5: trước cue không thấy, đầu cue là đầu hoạt ảnh, giữa cue có thay đổi, sau cue không giữ frame cuối. Dùng fixture 160×284/10 fps trên Actions, không encode full HD local.
- [ ] Chạy test thấy lỗi hiện tại. Sửa filter overlay: trim đúng nguồn, `setpts=PTS-STARTPTS+start/TB`, giới hạn cửa sổ và EOF không lặp frame; giữ alpha, không làm trượt tiếng nguồn. Kiểm cả nhiều overlay và PIP có trim.
- [ ] Kiểm tra bounds hữu ích của checklist trong canvas. Không chỉ phóng cả canvas có khoảng trống. Thêm ràng buộc kích thước chữ hiệu dụng vào chọn layout; nếu overlay không vừa mà không che mặt/sub, yêu cầu LLM chọn cutaway/PIP hoặc layout khác. Không tự giảm large thành medium một cách âm thầm.
- [ ] Kiểm mẫu checklist 3–6 giây ở đúng cue lời: thẻ nền đục, chữ tương phản, từng dòng vào/đánh dấu theo mốc từ, chuyển vào/ra ngắn và rõ. Opacity của bảng đang đọc phải đạt 1; alpha chỉ dành cho vùng ngoài bảng và chuyển cảnh.
- [ ] Render một đoạn nguyên liệu ngắn trên Actions với overlay xuất hiện muộn; xem animation liên tục và ở kích thước điện thoại. Commit khi đạt, kèm video trước/sau.

**Lệnh test:** `python -m pytest sin_content_api/tests/test_overlay_dung_moc.py -q`; planner/layout: `python -m pytest sin_content_api/tests/dung_video_dai_test.py -k 'overlay or checklist or timeline' -q` (chạy trên CI nếu có test render).

**Đạt M1:** không còn dùng frame cuối mờ làm cả overlay; checklist đọc được trên điện thoại, động đúng lời và không che mặt. Không sửa prompt để chữa lỗi timestamp.

### M2 — LLM lập storyboard đầy đủ trong pipeline chung

**Tệp sửa:** `dung_video_dai.py` (`tao_ke_hoach_dung_video`, `tao_y_tuong_dien_hoa_flow`, `_storyboard_visual_gaps`, `chon_dien_hoa`); test `dung_video_dai_test.py`.

**Interface:** giữ word ID làm neo chuẩn. Brief chứa renderer, scene/action, style snapshot/hash, target word IDs. Visual action chứa mode, layout_position, layout_size và lý do. Không để LLM viết lệnh shell hoặc Python tùy ý.

- [ ] Test content 25 giây, 66 giây, 2 phút: không cụt ý; giới hạn 3 visual mỗi request không trở thành giới hạn 3 visual cho cả clip. Thêm test lời nói lại, khoảng nghỉ dài trong cùng ý và khoản phí không được bịa số liệu.
- [ ] Tách nhịp theo ngữ nghĩa/word IDs do LLM chọn, hoặc bổ sung theo vùng còn thiếu; giữ toàn cảnh/ý chính trong ngữ cảnh. Không chia bốn phần bằng số học như script E2E.
- [ ] Planner giữ cảnh hợp lệ khi sửa khoảng trống; feedback xác định timecode và lời chưa được giải thích. Retry hữu hạn, không tạo cảnh để đủ số lượng. `needs_review` ghi đúng nguyên nhân sau lượt cuối.
- [ ] Layout dựa nội dung: checklist phụ có thể alpha, sơ đồ cần đọc chọn khung lớn hoặc người nói thu góc, cảnh kể chuyện chọn Flow. Không bắt buộc Flow nếu HyperFrames hợp lý, không áp cùng một layout cho mọi content.
- [ ] Cache/child job kiểm hash input, style, brief và renderer. Thay style phải tạo kế hoạch mới; không nhận cảnh kính cũ làm cảnh origami mới.
- [ ] 9Router thật lập kế hoạch clip M0; lưu request đã loại bí mật, kết quả và các cảnh bị loại. Không tạo Flow trước khi storyboard đạt tiêu chí kỹ thuật và nội dung.

**Đạt M2:** một plan sản phẩm có đầy đủ nhịp cần minh họa, rõ lý do tool/layout; không cần script E2E bổ sung cảnh bằng tay; transcript/caption đúng nghĩa.

### M3 — Đóng kín một pipeline sản phẩm và khả năng chạy tiếp

**Tệp sửa:** `sin_content_api/src/modules/dieu_phoi_dung/dung_video_dai.py`, media queue/provider hiện hữu, `sin_content_api/src/modules/tac_vu_tu_xa/{client,service,stages}.py`, `sin_content_api/scripts/chay_tac_vu_tu_xa.py`. Test hiện hữu `test_tac_vu_tu_xa.py`, `test_worker_dien_hoa_hyperframes.py`; bổ sung test tích hợp cần thiết vào đúng module.

- [ ] Submit job AUTO_EDIT từ API sản phẩm có source/project/workspace thật. Theo cùng job qua ASR → LLM take/storyboard/layout → child HyperFrames/Flow → gỡ logo nguồn gốc → render → QC → asset.
- [ ] Bắt buộc gỡ logo khi cấu hình đã bật. `FALLBACK_ORIGINAL` không được coi SUCCEEDED để publish. Gỡ trên nguồn Flow nguyên bản rồi normalize; xác minh đủ 10 giây.
- [ ] Lưu project Flow và trạng thái submitted trước chờ download. Timeout phải resume/download lại đúng request, không tự tiêu credit tạo cảnh lần nữa.
- [ ] Tắt tiến trình điều phối sau khi renderer bắt đầu, khởi động lại điều phối: lấy output task cũ theo hash thay vì tạo render/cảnh trùng. Không coi mất handle chờ local là runner đã chết.
- [ ] Tài nguyên nặng một task tại một thời điểm, runner giới hạn RAM/disk; job lỗi hiện nguyên nhân/action khắc phục lên UI.
- [ ] Không khởi động lại API khi đang có task mà chưa kiểm trạng thái và đường resume.

**Đạt M3:** một job sản phẩm tự chạy tới một asset MP4; ngắt/resume được mà không phải cứu file bằng script hoặc đăng ký asset thủ công.

### M4 — Video nghiệm thu và giao diện xem kết quả

**Tệp kiểm/sửa:** `sin_creator_os/src/app/(main)/auto-edit/page.tsx`, `sin_creator_os/src/components/video_studio/tu_dong_dung_video_dai.tsx`, media router/service hiện hữu. Không thiết kế lại toàn trang; giữ design system hiện tại.

- [ ] Render video M0 trên Actions từ job M3. Flow và HyperFrames phải theo snapshot origami mới; âm thanh nguồn sếp, sub karaoke hệ thống cỡ đọc được, nhấn 2 màu, không tag đen thô.
- [ ] Nhạc/SFX theo nội dung và tài nguyên đã có quyền sử dụng; ducking không át tiếng. Không thêm hiệu ứng ngẫu nhiên hoặc lặp mọi câu; không ép nhạc nếu nội dung không cần.
- [ ] Xem liên tục toàn video, nghe toàn audio. Kiểm checklist đầu/giữa/cuối, logo từng cảnh, caption ít nhất 10 mốc từ, chỗ nối tiếng và crop mặt. Đối chiếu bảng M0.
- [ ] Decode/loudness/black-frame/freeze-frame QC trên runner; báo rõ lỗi thẩm mỹ còn lại. Frame tĩnh có chủ ý không bị đánh đồng với lỗi đông hình.
- [ ] Mở browser đăng nhập hiện hữu tại `/auto-edit`, thấy chỉ thành phẩm, phát/seek đầu-giữa-cuối; reload không mất kết quả. Anonymous không đọc được file, workspace khác không đọc được asset.
- [ ] Commit/push code và báo cáo; đặt link xem video trong README và tài liệu trạng thái, có ảnh before/after và video minh chứng animation. Không ghi token vào link.

**Đạt M4:** một MP4 review được trên web đáp ứng bảng nghiệm thu, Founder chỉ còn phản hồi chi tiết chỉnh cuối. Không tự gắn nhãn 95% bằng bộ chấm điểm.

### M5 — Kiểm thử nguồn 8 GB và bàn giao vận hành

**Tệp kiểm/sửa:** upload streaming/resumable hiện hữu trong media studio, registry/transfer và workflow Actions. **Tệp test:** `test_media_studio_upload_stream.py`, `test_tac_vu_tu_xa.py`; bổ sung case lớn không cấp phát payload toàn bộ trong RAM.

- [ ] Preflight dung lượng free local/runner: bản gốc + scratch + output + dự phòng. Nếu runner SSD không đủ, dùng Range/window staging cho các đoạn được chọn; không tải 2–3 bản full 8 GB.
- [ ] Nạp file gốc 8.428.283.732 byte bằng upload chunk/resume. Ngắt giữa chừng rồi tiếp tục, so hash cuối; UI không đọc full file vào ArrayBuffer; API không `.read()` toàn bộ.
- [ ] ASR streaming/chunk và dựng từ các đoạn nguồn đúng mốc; không giả vờ test lớn bằng file đã edit hoặc đoạn 120 giây. TTS/voice clone không chạy nếu giọng nguồn đã đủ.
- [ ] Ghi peak RSS từng thành phần, peak scratch, byte transfer, thời gian từng stage, số request/cảnh Flow và số retry. Local không OOM, API không bị treo; đặt ngưỡng theo RAM khả dụng tại preflight và lưu ngưỡng vào báo cáo.
- [ ] Dọn file tạm chỉ khi output đã lưu và kiểm tra, theo tham chiếu/TTL; không xóa nguồn bất biến. Cancel job dừng task phù hợp, không tắt máy hay NAS.
- [ ] Cập nhật CURRENT_STATE và bàn giao Claude: cách chạy, link video, task/run ID, rollback commit, điểm còn thiếu. Rà từng dòng bảng nghiệm thu; chỉ đánh dấu goal complete khi toàn phạm vi có bằng chứng.

**Đạt M5:** nguồn lớn thật chạy từ upload tới thành phẩm trên web trong giới hạn tài nguyên đã ghi; có cơ chế phục hồi và dọn dữ liệu an toàn.

## 5. Quy tắc chống đi vòng

- Chỉ một mốc đang thực thi. Không đổi style, caption, render và auth cùng một vòng khi chưa xác định lỗi thuộc tầng nào.
- Hai lần thử cùng lỗi phải thu bằng chứng mới tại tầng lỗi, không đổi selector/prompt theo phỏng đoán lần thứ ba.
- Mỗi lần render cần biết đang kiểm điều gì; ưu tiên đoạn proof 3–6 giây trước full video. Không render lại cả phút chỉ để kiểm một filter.
- Không báo cập nhật chỉ lặp “vẫn chạy”: kiểm đúng task/run/heartbeat và ghi trạng thái; không restart vì polling timeout.
- Nghiên cứu repo chỉ phục vụ lỗ hổng cụ thể của mốc; không kéo framework thay thế hoặc sửa engine Claude đang làm. Những repo chưa rõ license không copy code. Mục tiêu mới không bắt buộc tích hợp cả danh sách repo.
- Không gọi video là hoàn chỉnh khi còn lỗi đã biết như overlay mờ, không động, logo, lệch style hay không phát được web.

## 6. Sổ thực thi

| Mốc | Trạng thái | Bằng chứng/việc tiếp theo |
|---|---|---|
| M0 | Đang làm | Đã ffprobe hai mẫu; cần xem và ghi timecode, chưa chốt bảng so sánh hình/nhịp |
| M1 | Chưa đạt | Xác định thiếu setpts và giữ khung cuối mờ; chưa sửa filter |
| M2 | Chưa đạt | 18 test planner đạt, 9Router thật trả 3 origami nhưng thiếu coverage; cần bỏ phụ thuộc chia nhịp tay |
| M3 | Chưa đạt | Engine chạy được qua script; chưa E2E job sản phẩm và resume tự động |
| M4 | Chưa đạt | Có bản sạch logo trên web, checklist mờ/nhỏ và style cảnh cũ chưa đạt |
| M5 | Chưa đạt | Chưa test trọn file 8 GB |

Mỗi cập nhật thêm: commit, lệnh đã chạy, kết quả, đường dẫn artifact, lỗi còn lại và bước tiếp theo. Không sửa trạng thái mốc thành đạt chỉ vì có thêm code.

### Cập nhật thực thi 03/11/2026

- M0: đã tạo `doi_chieu_mau_auto_edit.md`, 2 montage tổng thể và 4 chuỗi khung theo timecode. Đã quan sát cách dùng khung lớn và thứ tự xuất hiện trong mẫu; chưa nghe/xem toàn bộ, chưa chốt storyboard nên M0 còn mở.
- Quyết định thực thi: trong lúc đối chiếu M0, sửa lỗi timestamp đã tái hiện độc lập ở M1 vì đây là lỗi kỹ thuật làm mọi layout muộn mất animation, không phải thay đổi ý đồ thiết kế. Không đánh dấu vượt cổng M0/M1.
- M1: test `python -m pytest sin_content_api/tests/test_overlay_dung_moc.py -q --disable-warnings` đạt 2/2; test cũ đã thất bại với pixel xanh thay vì đỏ ở đầu cue. Renderer đã sửa trim/PTS/EOF. Độ rõ checklist, alpha/PIP/nhiều overlay và đoạn proof trên runner còn chưa đạt.
- M1 tiếp: commit `5c754bb` bỏ tự hạ `large` thành `medium`; 6 test checklist/overlay đạt. Commit `a1a57e5` tăng chữ checklist alpha dọc lên 64 px, nhãn dài tự xuống dòng, hàng 176 px; test SVG xuất thực tế đạt ngưỡng chữ hiệu dụng 22 px khi thu rộng 405. Ba test SVG/timestamp đạt trong 3,48 giây bằng fixture nhỏ; chưa xác nhận hết tràn/che mặt qua render thật.
- Proof animation (chưa có font mới) đang chạy trên Actions `41593346570`, commit `5c754bb`; output dự kiến `runtime/e2e_giong_sep/proof_checklist_doc_ro.mp4`. LLM thật chọn OVERLAY large và ghi rõ cần rà soát che mặt. Không được dùng proof này nhận đã kiểm font 64 mới hoặc đã đạt M1. Cần render lại native checklist bằng commit `a1a57e5` rồi ghép proof, giữ nguyên nguồn gốc và không gọi Flow.
- Cả hai proof đã hoàn tất: bản cũ chứng minh animation hiện từng mục; bản font 64 trên Actions `41593996775` xuất `proof_checklist_chu_64.mp4`, 8,5 giây, decode đạt. Đã xem bản ghép ở 360×640: vẫn nhỏ và sát mặt. M1 chưa đạt. Điều chỉnh tiêu chí trước đó nhầm đơn vị: 22 px trên output không đủ đọc ở điện thoại; yêu cầu 16 px trên viewport 360 (48 px output). Checklist này cần LLM chọn CUTAWAY hoặc bố cục thực sự đủ lớn, không tăng font trong ô góc vô hạn.
- Lượt tiếp: 9Router thật đã chọn CUTAWAY cho cùng checklist (không ép sửa action bằng tay), lý do đọc nhiều mục và tránh che mặt/phụ đề. Đã render `runtime/e2e_giong_sep/proof_checklist_toan_khung.mp4` trên runner hiện hữu, 8,5 giây, 1080×1920/30 fps, decode đạt. Xem khung đầu và giữa ở 360×640: chữ đọc rõ, số mục tăng đúng nhịp, không che mặt; ảnh/manifest trong `sin_content_api/08_kiem_thu/bang_chung/hoan_thien_auto_edit_20261103/`.
- Checklist cụ thể đã có bố cục dùng được, nhưng chưa đóng M1: cần kiểm alpha/PIP/nhiều overlay và kiểm hết cue cuối. `needs_review` vẫn được giữ vì asset dài 6 giây nhưng cửa sổ lời khoảng 5,34 giây; phải xác minh animation kết thúc trước khi bỏ cảnh báo, không xóa cờ chỉ để làm báo cáo xanh. Video 66 giây trên web chưa thay bằng proof.
- Kiểm alpha/PIP/nhiều overlay: `test_overlay_dung_moc.py` đạt 4 case video thật kích thước nhỏ (alpha 0,5 hoặc đục; trim 0/500 ms; hai lớp khác cue; PIP trim 1 giây). Pixel trước/sau cue và màu/độ alpha được kiểm trực tiếp, không chỉ kiểm chuỗi lệnh.
- Sau phản hồi Founder về nền đen: bản alpha checklist được đổi thành một thẻ giấy theo từng cue, chữ chính 128 px, có vẽ tick, đường nhấn, dịch chuyển/opacity vào cảnh và camera hiện hữu. Bản nền đục tiếp tục là danh sách. Cảnh dựng mới có `diagram_revision=2` trong tham số/hash job; chỉ asset revision này mới được mô tả cho LLM là `single_item_card` với cỡ chữ 128, không gán metadata mới lên cache bảng cũ.
- Proof alpha thực: 9Router chọn OVERLAY large; Actions `41596804006` dựng trên commit `3027b91`, xuất `runtime/e2e_giong_sep/proof_the_alpha_tren_video.mp4`, decode đạt. Pixel ngoài thẻ trên MOV có alpha 0. Hash ba frame trong cùng cue 2,06/2,3/2,8 giây khác nhau. Đã xem bản ghép ở 360×640 tại hai cue: thẻ đọc rõ, vùng ngoài thấy video gốc, không nền đen và không che mặt trong các khung đã kiểm. Mục cuối 5/5 đã hiện; chưa thay MP4 66 giây trên web. Bằng chứng trong `the_alpha_cue_chuyen_dong.json`, `the_alpha_qc.json` và hai ảnh `the_alpha_*_360.png`.
- M2: đã sửa giới hạn 3 cảnh của toàn kế hoạch thành tối đa 3 cảnh mỗi phản hồi và tích lũy có giới hạn. Test clip hai phút giữ 6 cảnh qua 4 lượt; 21 test planner liên quan đạt. 9Router thật trên clip 66 giây trả 4 cảnh, còn `needs_review` do cảnh sai mốc và khoảng trống; chưa đạt storyboard nghiệm thu. Không dùng số cảnh tăng lên để báo đạt.
- M2 tiếp: commit `51025b2` bỏ cắt cụt transcript ở 600 ký tự, giữ mốc thời gian trong phản hồi bổ sung. Rút gọn hướng dẫn bố cục để request nhỏ vẫn chia được trong giới hạn 5 KB, giữ quy tắc alpha/chuyển động/độ rõ/target. Tái hiện lỗi LLM trả cảnh cuối trước cảnh đầu khiến cảnh đầu bị bỏ nhầm; sửa bằng sắp theo mốc lời trước khi kiểm chồng lấn. Kiểm thử 109 đạt, 3 ca retranscribe chưa kiểm ở lượt này; log `kiem_tra_planner_sau_rut_gon.txt`.
- M2 thật: dùng 9Router hiện hữu với toàn bộ transcript của clip `part1_01` 30.000–96.460 ms do LLM đã chọn, không chia bốn phần bằng tay. Kết quả 2 Flow + 2 HyperFrames, không cờ rà soát ở bước này; request 20.580–23.517 byte dưới giới hạn cấu hình 200.000. Lưu `storyboard_llm_day_du.json`. Đây chỉ là kế hoạch hợp lệ; chưa chứng minh hình đẹp, nghe lời chính xác, sản phẩm tự chạy toàn bộ hoặc MP4 mới trên web. M3/M4/M5 còn mở.
- M3: phát hiện hai giới hạn 3 tác vụ con còn sót trong `worker._resume_waiting_auto_edit_jobs` và đầu vào render `dung_video_dai`; kế hoạch 4 cảnh sẽ không tiếp tục. Đã đồng bộ giới hạn 20 với kế hoạch tổng, giữ kiểm tra ID trùng/khác workspace/project. Kiểm thử hàng đợi 49 đạt, gồm 2/4/20 cảnh và từ chối 21; bỏ decorator thừa làm lỗi thu thập test. Log `kiem_tra_tiep_tuc_nhieu_canh.txt`.
- M3 E2E sản phẩm: đã upload đủ 1.054.104.321 byte nguồn 120 giây qua domain bằng API upload-session (khối 64 MiB), tạo asset `f85636f3-f8a0-489b-8ea2-9070d59b13dd`, dự án AUTO_EDIT `786676f6-e3c7-457d-9ccd-a22158507fdf`, gọi API tạo job `d9104d44-9d77-445e-90b5-b58cc0e202db` với khóa idempotency cố định. Không ghi asset trực tiếp DB. RAM quan sát upload 209–357 MiB, API 61–65 MiB; đây không phải phép đo peak liên tục hay kiểm 8 GB.
- Lượt mới đang QUEUED vì AI_VIDEO run `2cabaeda-fffc-48db-80f2-d6b67e578deb` giữ lease chung và Actions `41600096928` đang hoạt động. Giữ concurrency=1; không hủy tác vụ AI_VIDEO đó. Worker PID15788 được nạp lại trước khi gửi job sau khi kiểm không có media job lease hợp lệ. Chưa có MP4 mới từ job E2E này; theo dõi trạng thái thật, không gửi lại hoặc chạy script render thay pipeline.
- M3 rà soát quyết định LLM: bỏ nhánh tự chèn HyperFrames `OVERLAY small` khi LLM đã bỏ qua asset sau lượt nhắc. Asset bị gán sai target vẫn bị loại, cả clip thiếu cảnh và clip nhận nhầm được đánh dấu rà soát; không tự đổi clip/mode để làm đầy timeline. 9 ca mục tiêu đạt (`kiem_tra_khong_ep_bo_cuc.txt`).
- M3 karaoke: phát hiện cấu hình chữ 70 px/hai dòng chỉ có trong script thử, timeline sản phẩm chưa truyền `karaoke_settings`. Đã đưa cùng cấu hình vào `_tao_timeline`: renderer karaoke hiện hữu, champagne/trắng, outline/shadow/word_pop, không đổi style AI_VIDEO. 22 kiểm thử bố cục/karaoke/storyboard đạt (`kiem_tra_bo_cuc_va_karaoke.txt`); chưa xác minh trên MP4 mới. Nhãn tĩnh/callout trong sản phẩm còn cần đối chiếu chất lượng mẫu ở M4.
- M3 vị trí: bỏ nhánh tự đổi mọi overlay alpha dạng diagram sang `upper_left`; giữ vị trí LLM chọn. Test tái hiện chọn `upper_right` nhưng nhận `upper_left`, sau sửa 15 test liên quan đạt (`kiem_tra_giu_vi_tri_llm.txt`). Chưa kiểm che mặt trên video mới; LLM hiện chưa có bằng chứng vị trí mặt từ frame nguồn.
- Chuẩn bị M5: xác nhận nguồn local `C:/Users/Baha Group/Downloads/DJI_20261027202121_0203_D.MP4`, 8.428.283.732 byte, ổ C còn khoảng 37 GB. Bắt đầu kiểm riêng upload qua domain bằng khối 64 MiB, không enqueue render/ASR cho nguồn này. Trạng thái phục hồi lưu `ha_tang/chay_dev_local/runtime/e2e_auto_edit_8gb/trang_thai.json`; gọi lại cùng script với `--nguon-8gb` sẽ hỏi offset server trước, không gửi lại từ đầu. Chưa nhận đủ file thì không báo upload 8 GB đạt; đây không phải E2E 8 GB và không đóng M5.
- M2/M3 nhiều kịch bản: planner trước đó dùng chung 4 lượt cho mọi clip và lấy mẫu 20 clip, nên có thể bỏ kịch bản hoặc thiếu cảnh ở cuối. Đã lập storyboard tuần tự từng clip, không lấy mẫu bỏ clip; mỗi clip vẫn tối đa 3 cảnh mới mỗi phản hồi, có sửa kế hoạch và chặn chồng mốc như cũ. Đồng bộ giới hạn danh sách con theo trần schema 100 clip × 20 cảnh, không tăng concurrency. 58 test đạt; có 21 clip liên tiếp và kiểm render nhận 21 tác vụ nhưng chặn 2001 (`kiem_tra_nhieu_kich_ban.txt`). Chưa kiểm LLM thật trên toàn nguồn nhiều kịch bản.
- Upload 8 GB: ở khoảng 1 GB, công cụ gửi thử đọc cả khối 64 MiB vào bytes và RAM quan sát tăng đến 604 MiB. Đã dừng đúng PID uploader, không dừng API/worker/Actions; đổi công cụ thử sang generator đọc 1 MiB với Content-Length của khối, rồi hỏi offset server để tiếp tục. Tại offset 1.543.503.872 byte, RAM uploader khoảng 81 MiB, API khoảng 56 MiB. Đây là sửa công cụ kiểm thử; backend upload vốn spool luồng xuống đĩa. Session upload không đổi `5d4cfdb5aa2648528babebf986b26769`, dự án `685d269c-def5-4e35-9038-a75d2119dd80`; chưa hoàn tất.
- M4 nhãn, phạm vi thiết kế: tái sử dụng Be Vietnam Pro và trắng/champagne của hệ thống; tiêu đề 72 px, từ nhấn 70 px, không hộp đen/xanh, vào cảnh bằng dịch 24 px + scale 92→100% trong 180 ms, fade vào/ra 120 ms. Nội dung và mốc callout giữ từ quyết định LLM; `animated_label` mặc định false nên caption khác không tự đổi style. Cờ đi qua schema, kiểu FE, phân loại caption trong renderer rồi ASS; không tạo engine mới hoặc sửa luồng Remotion/HyperFrames của AGY.
- M4 nhãn thực: dựng thử 4 giây ở 360×640 từ một frame lấy trực tiếp ở giây 31 nguồn quay local, chỉ để xem chữ, không coi là video E2E. Đã xem `nhan_dong_360.png`: tiêu đề hai dòng nằm trên tường, không che mặt trong frame này, không có hộp nền. Test renderer thật 160×284/2 giây kiểm pixel trước/giữa/sau cue và frame chuyển động khác nhau, schema giữ cờ, caption cũ không tự đổi. 18 test liên quan đạt (`kiem_tra_nhan_dong.txt`); thêm test vào CI. Chưa xác minh nhãn/callout của toàn clip, che mặt ở các frame khác hoặc bản 1080 trên runner mới.
- Upload đang qua mốc 4 GiB (server đã xác nhận 4.362.076.160 byte); chưa đủ 8.428.283.732 byte, chưa đóng M5. Lượt AI_VIDEO đang tiến qua các cảnh trên Actions; job Auto Edit sản phẩm vẫn QUEUED. Cần dùng runner có commit nhãn mới trước bước RENDER_FINAL của lượt Auto Edit; không hủy runner khi còn task đang chạy.
