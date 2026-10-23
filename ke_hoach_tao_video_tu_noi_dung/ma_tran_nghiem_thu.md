# Ma trận nghiệm thu bộ tạo video từ nội dung

Ngày: 23/10/2026. Đây là điều kiện nghiệm thu tương lai; mặc định tất cả hàng triển khai CHƯA CHẠY, không phải báo cáo sản phẩm đã đạt. Kết quả khảo sát/test cơ sở ghi riêng bên dưới.

Bản 2.0 bổ sung NT32–NT42 theo yêu cầu Harness/LLM trước Flow, phong cách công ty cố định theo kênh và thi công song song. Tham chiếu ba tài liệu `hop_dong_harness_llm_truoc_flow.md`, `quy_chuan_phong_cach_kenh.md`, `quy_uoc_thi_cong_song_song.md`.

## 1. Ca nghiệm thu bắt buộc

| Mã | Đầu vào/thao tác | Điều kiện đạt cụ thể | Bằng chứng phải lưu | Gate |
|---|---|---|---|---|
| NT01 | Content 120 giây, dọc 30 fps | Target 3.600 frame; output 120 ± 0,5 giây; tổng tính cả outro và transition | Request, plan JSON, ffprobe | G2/G6 |
| NT02 | Content có nhiều luận điểm | Mọi ý bắt buộc có scene mapping; có hook, thân bài, kết luận; không mất ý vì chia số ký tự | Coverage ledger và reviewer | G3 |
| NT03 | Một cảnh dài hơn duration provider | Nhiều shot hợp capability; prompt riêng, duration/trim thật; không dùng prompt 120s cho một clip | Registry, prompt, receipt, file từng shot | G4/G5 |
| NT04 | Content có điều kiện phủ định và nhân vật xuyên suốt | Prompt bảo toàn phủ định; continuity IDs/ảnh chuẩn nhất quán; reviewer xác nhận từng cảnh | Prompt bundle, ảnh/keyframe, checklist | G3/G7 |
| NT05 | Lời dài 150s, target 120, GIU_NGUYEN_LOI | Dừng chờ quyết định; không cắt chữ/âm tiết hoặc tăng tốc quá phạm vi | Audio, diff, trạng thái/UI | G4 |
| NT06 | BIEN_SOAN và content quá dài | Đề xuất kịch bản rút có diff, giữ ý chính, duyệt lại trước tạo voice/asset | Script revisions, approval | G3/G4 |
| NT07 | Claim công nghệ thiếu nguồn | Không được duyệt câu khẳng định final; reviewer thấy source/claim/blocker | Claim ledger và API 409/validation | G3/G7 |
| NT08 | JSON LLM sai/bị cắt, nguồn có prompt injection | Không dùng dữ liệu sai để chạy provider; tối đa lượt sửa có giới hạn; cấu hình/key không bị tác động | Test logs đã scrub | G3 |
| NT09 | Giọng tiếng Việt có RAG/API/MCP | Voice thật nghe rõ, từ điển đúng; timing đo trên audio; không dùng độ dài ước lượng thay phép đo | Audio, từ điển, ffprobe, người nghe | G4 |
| NT10 | Phụ đề dài, có dấu và thuật ngữ | Cue theo audio, không quá 200ms lệch trên mẫu kiểm; 2 dòng, bounding box trong safe area; trường hợp vượt chuẩn có issue | SRT, cue JSON, screenshot đầu/giữa/cuối | G4/G7 |
| NT11 | Export final | H.264/yuv420p, AAC, 1080×1920, 30fps; full decode không lỗi | ffprobe JSON, full decode log | G6 |
| NT12 | Lời + nhạc + outro | -14 ± 1 LUFS; true peak ≤ -1,5 dBTP; không cắt câu; người nghe xác nhận nhạc không che lời | EBU R128, audio review | G6/G7 |
| NT13 | Thiếu asset/recording hoặc file hỏng | Dừng đúng scene, lưu checkpoint; không thay bằng stock/khung màu ngẫu nhiên | State, error, artifact manifest | G5/G6 |
| NT14 | Flow hết phiên, TTS thiếu quyền, quota hết | Đúng trạng thái chờ/blocker và hướng xử lý; không báo support/hoàn tất hoặc tự chuyển provider tính phí | Capability ledger, job/UI logs | G5/G8 |
| NT15 | Timeout sau provider submit | Receipt được lưu/poll; không submit lại mù; cost/credit không ghi trùng | Provider op ID, call-count, ledger | G5 |
| NT16 | Double click/refresh/restart/2 worker | Cùng fingerprint một run/shot; một lease; asset có sẵn được dùng lại; tiếp tục đúng bước | DB/test logs, hash/call-count | G2/G5/G8 |
| NT17 | Hủy run đang chờ/gọi provider | Ngừng bước tiếp theo, trạng thái hủy bền vững; kết quả về muộn không tự hoàn tất run | State history, late callback test | G5 |
| NT18 | Ngân sách thiếu giữa phim | Dừng trước gọi mới; giữ kết quả cũ; chi phí chưa biết không hiển thị 0 | Reservation/actual ledger | G5 |
| NT19 | Sửa một shot/cảnh sau preview | Revision mới; asset nguồn ngoài phạm vi giữ hash; bản cũ còn mở; không gọi lại toàn bộ AI | Diff, hashes, API call-count, 2 MP4 | G7 |
| NT20 | Sửa narration/brand sau duyệt | Vô hiệu hóa đúng approval/dependencies; không export bản mới bằng approval cũ | Version graph/audit, negative API test | G7 |
| NT21 | Lưu/mở lại/export/import project | Scene IDs, track, trim, caption, voice, brand không mất; hiệu ứng unsupported báo rõ | Timeline roundtrip và playback | G6/G7 |
| NT22 | User ngoài quyền/ngoài workspace | Backend chặn đọc/sửa/duyệt/hủy/xuất; UI ẩn nút không thay kiểm quyền | Permission tests và audit | G2/G7 |
| NT23 | Nguồn/voice/nhạc chưa có quyền dùng | Chặn final approval; giữ bản nháp và lý do; không coi nội bộ là tự có quyền tư liệu | Rights/consent ledger | G7 |
| NT24 | Nhân sự không kỹ thuật làm 120s từ UI | Nhập content → duyệt → sản xuất → preview/QC → sửa → tải, không sửa DB/không nhập prompt từng shot | Browser recording/screenshots, run IDs | G8/G9 |
| NT25 | Tải và phát gói | MP4/SRT/thumbnail/script/storyboard/prompt/editable/QC/usage đủ; tải có auth, hash khớp; phát được toàn phim | Package manifest/hash, downloaded file | G6/G8 |
| NT26 | Migration/rollback | ID/kênh/quyền/asset/timeline cũ bảo toàn; restore thử đạt; flag tắt quay về luồng cũ | Counts/IDs, restore logs, regression | G0/G2/G9 |
| NT27 | Secret/profile trong logs/gói | Không key/token/cookie/browser profile; chỉ receipt đã scrub | Scan report, manual sample review | G9 |
| NT28 | 3 chủ đề pilot | 60s + 120s + 120s, có nguồn, tối thiểu 5 scenes ở demo 60s; ít nhất một 120s AUTO live đầy đủ | 3 MP4, editable project, QC, reviewer | G9 |
| NT29 | Xuất bản chưa được cấp quyền API | Đủ gói handoff; NOT_PUBLISHED; không đăng thật hoặc ghi external ID giả | Package, publication state | G9 |
| NT30 | 30/60/120/180 giây và ngoài phạm vi | Không hardcode clip/nhạc 10/30s; các giá trị hợp lệ được lập đúng; ngoài phạm vi 422 giữ content | Parameterized tests, UI | G2/G4/G8 |
| NT31 | Transition overlap/clip thực ngắn hơn dự kiến | Tổng frame tính đúng; clip ngắn báo/replan; không freeze/loop âm thầm | Frame ledger, actual ffprobe | G4/G6 |
| NT32 | Gửi raw prompt hoặc receipt giả qua clip API/AI Studio/I2V/extend/sửa cảnh | Không bypass: số lần gọi Flow bằng 0; mọi tạo mới cần đánh giá LLM và receipt Harness server-side đúng scope | Entry point inventory, negative API tests/call-count | G5 |
| NT33 | LLM lỗi, timeout, JSON sai hoặc đổi nghĩa nội dung đã duyệt | CHO_LLM hoặc chờ duyệt revision; không fallback raw prompt/mock, không tự duyệt | State, evaluation/error, Flow call-count bằng 0 | G3/G5 |
| NT34 | Prompt/style/policy/approval đổi sau preflight; receipt hết hạn hoặc khác project | Hash/TTL/scope/revocation bị chặn trước side effect; receipt submit rồi được poll thay vì submit lại do TTL hết | Command hashes, receipt lifecycle, test replay/tamper | G2/G5 |
| NT35 | Kênh thiếu style đã duyệt, binding sai công ty, token override trái phép | Chặn production; giữ nháp và lý do; không tự lấy default/latest hoặc cho content ghi đè nhận diện | Style schema/permission tests, UI blocker | G2/G3/G8 |
| NT36 | Binding/style đổi giữa run, resume hoặc tạo lại shot | Run giữ snapshot/hash đã khóa nếu còn hợp lệ; version thu hồi bị chặn; đổi có chủ ý tạo revision và mất approval liên quan | Snapshot history, dependency/approval tests | G2/G5/G7 |
| NT37 | Ba video khác chủ đề cùng kênh | Cùng style snapshot được duyệt; logo/font/palette/voice/template đúng; hard checks và AI/người review không còn drift chưa xử lý | 3 video/contact sheets, references, QC/reviewer | G1/G7/G9 |
| NT38 | AI score cao nhưng sai logo/giọng/style, hoặc asset bị đổi bytes | Không tự pass; hard hash/token checks + reviewer chặn; tối đa 2 lượt sửa tự động dùng cùng ngân sách rồi chờ duyệt | Drift issues/timecodes, attempt/cost ledger | G5/G7 |
| NT39 | Hai lane cùng đề nghị sửa entities/router/contract/page chung | Một integrator áp tuần tự từ proposal có base hash; worker không ghi file shared; patch stale bị trả cập nhật | Owner/lease register, queue và before/after hashes | G0/G2/G9 |
| NT40 | Lane sửa hiện hữu và lane mới làm đồng thời | File owner không giao nhau; consumer dùng cùng contract version/fixture; tích hợp giữ regression cũ và flow mới pass | Task IDs, contract manifest, integrated test logs | G2–G9 |
| NT41 | Test song song/reset fixture/build/Flow/render | DB/tmp/cache/ports/profile cách ly; không dọn dữ liệu chung; tác vụ nặng tổng concurrency 1, không mở slot khi operation chưa rõ kết quả | Env/path checks, process/resource lease registry | G0/G5/G9 |
| NT42 | Agent hết lease, mất heartbeat hoặc source/contract đổi | Không ghi tiếp/stale overwrite; điều phối xác nhận chủ cũ dừng trước cấp lại; downstream đọc baseline mới và test lại | Lease events, stale hash refusal, handover logs | G2/G9 |

## 2. Phân loại mức nghiệm thu

- Mức hợp đồng: unit/integration với provider giả xác minh schema/state/idempotency; không chứng minh AI đã sinh video.
- Mức HYBRID: voice/recording/asset thật được upload, pipeline lắp ráp và sửa được; không gọi đây là AUTO end-to-end.
- Mức AUTO: content → kịch bản/cảnh/prompt → voice/align → tư liệu phù hợp → dựng/QC/gói chạy bằng tích hợp thật; vẫn có gate con người duyệt. AUTO không có nghĩa bỏ phê duyệt nội dung.
- Mức sử dụng nội bộ: AUTO/HYBRID đúng nhãn, UI thao tác được, hồi quy/restore/quyền pass và Founder duyệt pilot. Hoàn tất mức này không tự hoàn tất analytics/lead toàn master spec.

## 3. Hồ sơ cần có trên mỗi ca chạy thật

Mã ca, người chạy/reviewer, thời gian, source revision/hashes, input đã lược bí mật, plan/script/timeline revision, project/run/scene/shot ID, provider operation ID, chi phí/credit, command/cwd/exit code, log, đường dẫn artifact/hash, ffprobe/loudness/full decode, ảnh chụp/timecode, kết quả đạt/không đạt, lỗi mở và hành động tiếp theo. Thiếu evidence thì trạng thái CHƯA XÁC MINH, không tự điền pass.

Bằng chứng nghiệm thu chính thức đích đến `08_kiem_thu/bang_chung/tao_video_tu_noi_dung/`. Phiên nghiên cứu lưu tạm trong `03_ban_lam_viec/ke_hoach_tao_video_tu_noi_dung/bang_chung/` theo vùng ghi; chưa coi đã chuyển hồ sơ chính thức hoặc tạo checkpoint.

## 4. Bằng chứng khảo sát phiên lập kế hoạch

`bang_chung/khao_sat_thuc_te.json`: hash 8 file lõi và master spec, phản hồi health/readiness/API offline và trang frontend HTTP 200. Không có bằng chứng GUI end-to-end/provider mới từ phép thăm dò này.

`bang_chung/kiem_thu_co_so.txt`: tập test hiện hữu về compiler, video và đạo diễn đạt 45 bài, 1 cảnh báo deprecation, mã thoát 0 trong 115,07 giây. Test dùng provider mô phỏng và tư liệu tổng hợp để kiểm kỹ thuật; không phải phim nội dung thật và không chuyển capability thành REAL_VERIFIED. Cấu hình `SIN_DUNG_DB_PATH` trỏ kho dựng kiểm thử riêng trong thư mục bằng chứng để fixture không dọn kho vận hành.

`bang_chung/ket_qua_ra_soat_tai_lieu.json`: bằng chứng phiên 1.0 kiểm 10 gate và 31 mã nghiệm thu. Phiên 2.0 chạy lại kiểm tra tài liệu, 42 mã nghiệm thu và ba phụ lục bổ sung; kết quả mới lưu riêng tại `bang_chung/ket_qua_ra_soat_tai_lieu_v2.json` để không ghi đè kết quả cũ. Storyboard vẫn 12 cảnh liên tục đủ 120 giây/3.600 frame; bản sao master spec phải khớp hash nguồn. Source hash được đối chiếu với baseline khảo sát để báo drift, không tự sửa/revert nếu nguồn đã được agent khác cập nhật.

`bang_chung/ra_soat_doc_lap_ke_hoach.md`: lượt rà soát người thi công độc lập không còn quyết định quan trọng bị bỏ trống; không thay kiểm thử sản phẩm hoặc duyệt Founder.

## 5. Khoảng trống và quyết định tiếp theo

1. Xác định đúng DB/runtime/source repository và baseline toàn bộ trước refactor.
2. Chưa có prototype/biên bản Founder duyệt, chưa thi công bộ điều phối mới.
3. Chưa xác minh entitlement, giá/credit, duration/tỷ lệ thực của từng account/model, TTS và alignment.
4. Chưa có video 120 giây do dây chuyền mới tạo; không nghiệm thu bằng clip 10 giây hoặc nhạc dài riêng lẻ.
5. Chưa kiểm publishing/analytics/CTA/lead toàn hệ thống; kế hoạch giữ chúng ở nhánh sau có điều kiện cụ thể.
6. Chưa chạy migration, đổi quyền, thay dữ liệu production hoặc đăng bài thật.
7. Chưa có runtime receipt Harness/LLM gate hoặc style binding chính thức; các phụ lục mới là kế hoạch thi công. Chưa cấp lease sửa runtime; chia lane trong tài liệu không tự cho phép ghi chồng hoặc bỏ G1.

Gate tiếp theo được đề xuất: hoàn tất phần còn thiếu của G0 và tạo prototype G1 để Founder xem luồng 120 giây trước khi thi công backend.
