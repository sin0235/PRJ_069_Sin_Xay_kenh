# Kế hoạch triển khai bộ tạo video từ nội dung

> Dành cho người thi công: đọc `dac_ta_bo_tao_video_hoan_chinh.md` và `nghien_cuu_hien_trang_va_phuong_an.md` trước. Dùng kỹ năng executing-plans để thực hiện lần lượt theo gate. Mỗi ô chỉ được đánh dấu sau khi có bằng chứng; không tự hiểu tài liệu này là biên bản duyệt UX hoặc lệnh phát hành.

**Bản cập nhật 2.0:** Bắt buộc đọc thêm `hop_dong_harness_llm_truoc_flow.md`, `quy_chuan_phong_cach_kenh.md`, `quy_uoc_thi_cong_song_song.md`. Gate là thứ tự nghiệm thu phụ thuộc; các nhiệm vụ trong một đợt được chạy song song theo ma trận owner, không bắt toàn bộ agent chờ một chuỗi tuần tự. Phiên này chỉ sửa kế hoạch, chưa khởi động thi công runtime.

**Mục tiêu:** Nhân sự xây kênh nhập content và thời lượng 120 giây, hệ thống lập kế hoạch, chia cảnh/prompt, tạo lời và tư liệu, dựng phim hoàn chỉnh có QC, sửa từng cảnh và tải gói đăng.

**Kiến trúc:** Bổ sung bộ điều phối sản xuất từ nội dung trên FastAPI hiện hữu, dùng worker bền vững và provider adapter. Tái sử dụng kho asset, phiên bản kịch bản/timeline, editor và FFmpeg CPU. Không tạo ứng dụng mới bên cạnh.

Đường gửi Flow duy nhất: Harness mở phiên/khóa style kênh → LLM lập/kiểm kịch bản và prompt → Harness kiểm quyền/schema/timing/style/budget/approval → receipt bất biến → worker/adapter Flow → QC kết quả. Frontend và các route legacy phải đi cùng cổng, không gửi prompt thô vòng ngoài.

**Công nghệ:** Next.js/React/TypeScript, FastAPI/Pydantic/SQLAlchemy, DB hiệu lực được G0 xác nhận, FFmpeg/ffprobe. LLM lấy cấu hình chủ sở hữu qua `LLMClient.from_db`; cloud TTS/ASR/video chỉ bật theo kiểm chứng capability.

**Trạng thái:** Đã lập kế hoạch; các công việc triển khai dưới đây CHƯA HOÀN THÀNH. Nghiên cứu phiên này không thay cho nghiệm thu G0 đầy đủ. Các thông số pilot là quyết định đề xuất của Codex, chờ duyệt cùng G1.

## 1. Ràng buộc toàn cục

- Chỉ viết trong `03_ban_lam_viec/` và file trạng thái quy định tại `00_bat_dau/`; bảo vệ nguyên bản. Bằng chứng chính thức/snapshot/trang hành trình ngoài vùng ghi phải được người có trách nhiệm ghi đúng quy định trước đóng gate.
- Tên file mới tiếng Việt không dấu, snake_case, nội dung tiếng Việt có dấu; biểu tượng SVG. Tên file cũ giữ nguyên khi sửa để không phá import.
- Prototype và storyboard mẫu được Founder duyệt trước khi viết backend nặng.
- 9:16, 1080 × 1920, 30 fps; âm thanh -14 ± 1 LUFS, true peak ≤ -1,5 dBTP; concurrency tác vụ nặng = 1.
- Không lộ secret, không đổi quyền sống, không đăng bài/phát hành production trong quá trình thi công.
- Không phụ thuộc GPU local; không mặc định subscription Flow cấp quyền Gemini/Veo API.
- Không hủy dữ liệu/ID/API cũ; migration thử nghiệm và rollback phải có bằng chứng. Nếu đụng schema/quyền phải đọc đúng guardrails trước.
- Pilot 30–180 giây; ca 120 giây bắt buộc; không tự sửa độ dài, cắt lời, gán mock hoặc coi video không voice là video giải thích hoàn chỉnh.
- Không mở nhiệm vụ billing SaaS, tenant khách hàng hoặc CRM đầy đủ trong đường ưu tiên sản xuất nội bộ.
- Bắt buộc LLM preflight và receipt Harness hợp lệ trước mọi side effect Flow, kể cả tạo lại/sửa cảnh/I2V/extend; mất LLM thì dừng chờ, không fallback raw prompt.
- Một style công ty đã duyệt được bind theo kênh; run khóa snapshot/version/hash. Không để LLM, nội dung đầu vào hoặc cấu hình latest làm video sau tự khác style video trước.
- Mỗi file một owner tại một thời điểm; integrator độc quyền file chung, schema/migration và contract. Agent lane hiện hữu và lane mới chỉ sửa vùng đã nhận; không reset/revert thay đổi người khác.

## 2. Bản đồ file và trách nhiệm

Tất cả đường dẫn trong bảng tương đối với `03_ban_lam_viec/`. Tên module mới đề xuất: `tao_video_noi_dung`.

| File tạo/sửa | Trách nhiệm |
|---|---|
| Tạo `sin_content_api/src/modules/tao_video_noi_dung/hop_dong.py` | Request, kế hoạch, cảnh, shot, trạng thái, fingerprint và response; validate đầu vào |
| Tạo `.../lap_ke_hoach.py` | Content/research/script thành storyboard và prompt có schema |
| Tạo `.../can_thoi_gian.py` | Frame budget, timing voice thật, chia shot và transition handle |
| Tạo `.../danh_muc_nang_luc.py` | Capability registry cho mặt tích hợp đã kiểm chứng |
| Tạo `.../phong_cach_kenh.py` | Resolve company/channel/series, style snapshot/version/hash; không tạo palette/giọng chưa duyệt |
| Tạo `.../cong_harness.py` | Preflight LLM, kiểm policy, receipt, dispatcher duy nhất và nhận kết quả; tích hợp Harness dựng hiện có |
| Tạo `.../tao_giong_doc.py` | TTS/align adapter, phát âm thuật ngữ, metadata giọng và thời gian |
| Tạo `.../kho_phien_ban.py` | Lưu plan/run/step, CAS, idempotency, lease và dependency hash |
| Tạo `.../dieu_phoi.py` | DAG từng bước, resume/cancel, lỗi/đối soát và ngân sách |
| Tạo `.../lap_timeline.py` | Storyboard/voice/assets thành TimelineDocument/TimelineV2 đúng renderer |
| Tạo `.../kiem_dinh.py` | Technical/content/rights/brand gates, issue/timecode và phạm vi validator |
| Tạo `.../xuat_goi.py` | Artifact manifest, SRT, thumbnail và gói đăng |
| Tạo `.../bo_dinh_tuyen.py`, `.../__init__.py` | API authenticated, resource scoped, trả job ID |
| Sửa `sin_content_api/src/main.py` | Đăng ký router và vòng đời worker theo cấu hình đã duyệt |
| Sửa `sin_content_api/src/models/entities.py`, `src/migrations/runner.py` | Delta kế hoạch/run/step, index/constraint và migration an toàn |
| Sửa `sin_content_api/src/modules/scripts/script_service.py`, `timing_calculator.py`, `claim_checker.py` | Kịch bản trực tiếp, version nguồn và mở rộng claim công nghệ, giữ hồi quy |
| Sửa `sin_content_api/src/modules/media_studio/video_provider.py`, `job_engine.py`, `video_processor.py` | Adapter clip có capability, receipt và render contract thật |
| Sửa `sin_content_api/src/modules/dieu_phoi_dung/bo_render.py`, `hop_dong.py` nếu cần | Ánh xạ timeline không mất tính năng; không tạo editor thứ hai |
| Sửa `sin_content_workers/worker.py`; tạo `sin_content_workers/tac_vu_tao_video.py` | Durable dispatch/lease, kiểm lại quyền và chạy bước sản xuất |
| Sửa `sin_creator_os/src/app/(main)/video-studio/page.tsx`, `[projectId]/page.tsx` | Điểm vào content-first, các bước sản xuất và editor phụ trợ |
| Tạo `sin_creator_os/src/app/(main)/video-studio/[projectId]/_components/{nhap_noi_dung,duyet_phan_canh,tien_do_san_xuat,duyet_thanh_pham}.tsx` | Component sát route, không sửa thư viện UI nền |
| Tạo `sin_creator_os/src/lib/api/tao_video_noi_dung.ts`; sửa `src/lib/api/media-studio-api.ts` khi cần | Client API/type thật, auth tải file và typed errors |
| Tạo test tiếng Việt không dấu tại `sin_content_api/tests/kiem_thu_*.py` | Các ca được gắn theo gate bên dưới; chạy bằng đường dẫn tường minh |

Ký hiệu `.../` trong bảng chỉ module `sin_content_api/src/modules/tao_video_noi_dung/`, không phải thư mục tùy ý. Các file cần sửa được xác nhận lại qua `rg` ở G0; không tạo một file gần giống nếu tên hiện hữu khác. Không thêm thư viện cho chức năng mà built-in và dependencies sẵn có đáp ứng.

Bảng trên là phạm vi toàn dự án, không phải cấp quyền cho mọi agent cùng sửa. Owner/lease/đợt trong `quy_uoc_thi_cong_song_song.md` quyết định quyền ghi thực tế. `hop_dong.py`, `cong_harness.py`, entities, migrations, main, config và các entrypoint chung chỉ integrator sửa. Các lane gửi đề xuất thay đổi shared dưới file riêng trong vùng kế hoạch; không sửa trực tiếp file của lane khác.

## 3. Các tình huống trọng yếu phải có test

| Tình huống | Kỳ vọng | Gate sở hữu |
|---|---|---|
| Nội dung dài hơn lời đọc 120 giây ở chế độ giữ nguyên | Dừng chờ quyết định, không cắt hoặc tăng tốc quá mức | G3, G4 |
| Provider nhận request nhưng client timeout | Khôi phục receipt và poll; không submit/tính phí lần hai | G5 |
| Thay lời sau duyệt hoặc sửa một shot | Hủy hiệu lực approval liên quan, tạo revision, giữ asset không đổi | G2, G7 |
| Process chết, hai worker cùng resume | Một chủ lease, không mất kết quả và không tạo trùng | G2, G5 |
| Thiếu recording/voice/quyền media hoặc claim công nghệ chưa kiểm chứng | Blocker đúng bước, giữ project để tiếp tục | G3, G4, G7 |

## 4. Thứ tự và cổng triển khai

### G0 — Chốt hiện trạng thực và đường phục hồi

**Đầu vào:** source và master spec; báo cáo nghiên cứu phiên này. **Phụ thuộc:** không.

- [ ] Xác định repository quản lý, nhánh thử nghiệm và trạng thái file đang thay đổi; không git-init lên cấu trúc chưa xác minh.
- [ ] Đối chiếu DB runtime hiệu lực, storage và process; kiểm kê số lượng/ID/hashes project, script, asset, timeline, channel và quyền, chỉ đọc và không xuất secret.
- [ ] Đọc `AGENTS.md` ở frontend, tài liệu Next.js local và guardrails RBAC nếu chạm hook/quyền. Đọc bộ Postgres trước schema/migration chạy trên PostgreSQL.
- [ ] Lập inventory routes/API/jobs/provider với nhãn PLANNED/MOCK/REAL_UNVERIFIED/REAL_VERIFIED/BLOCKED và evidence.
- [ ] Lập bản đồ mọi đường gọi Flow hiện hữu gồm AI Studio/clip API/I2V/extend/sửa cảnh/Assisted UI; chỉ định owner wrapper để không còn đường bypass sau rollout policy.
- [ ] Kiểm kê style/brand assets thực, channel binding, font/logo/voice đã duyệt; không coi các default hardcode hiện tại là quy chuẩn công ty.
- [ ] Chạy baseline backend, `pnpm exec tsc --noEmit`, `pnpm run build`; ghi command, cwd, thời gian, exit code, log và hash source. Cấu hình DB test và `SIN_DUNG_DB_PATH` riêng; fixture dọn kho dựng không được chạm DB vận hành.
- [ ] Thử một luồng cũ bằng tài khoản đúng quyền: mở project, xem asset, lưu revision, render, tải và phát file; lưu screenshot/player, HTTP/job ID và ffprobe.
- [ ] Lập bản sao phục hồi trước migration, kiểm thử restore sang môi trường biệt lập; người có vùng ghi phù hợp giữ snapshot chính thức trong `90_sao_luu/`.

**Đầu ra:** baseline, ma trận KEEP/REFACTOR/EXTEND/DEPRECATE, map DB/API/routes và bản phục hồi kiểm chứng. **Kiểm thử:** không giảm số bản ghi/ID; log test/build; một output cũ phát được. **Bằng chứng:** báo cáo baseline, hash manifest, screenshot, metadata. **Khoảng trống hiện tại:** phiên nghiên cứu chưa hoàn tất toàn bộ G0. **Go/No-Go:** thiếu DB/runtime/backup xác định hoặc baseline có blocker thì chưa được refactor dữ liệu.

### G1 — Duyệt sản phẩm và prototype trước chức năng

**Đầu vào:** G0 và đặc tả bộ tạo video. **Thay đổi:** chỉ prototype và tài liệu UI, không backend nặng.

- [ ] Dựng prototype dùng đúng shell/components hiện hữu, trong thư mục kế hoạch; gắn nhãn mẫu thiết kế.
- [ ] Tạo hai mẫu 60 và 120 giây: form content/thời lượng, kịch bản, cards cảnh, prompt, thời gian, chi phí, trạng thái chờ tư liệu và nút duyệt.
- [ ] Cho thấy luồng sản xuất, preview, QC, sửa một cảnh và gói tải; người không kỹ thuật hoàn thành đường đi mà không phải nhập prompt từng shot.
- [ ] Thể hiện empty/loading/error/cancel/resume/revision conflict, quá dài lời, Flow mất phiên, thiếu TTS và thiếu recording.
- [ ] Chốt preset pilot, giọng, tốc độ lời, sai số thời lượng, caption, O1/O2/O3; ghi từng lựa chọn và người duyệt.
- [ ] Duyệt style family đầu tiên, token/reference/giọng cụ thể và biến thể series hợp lệ; xem 3 mẫu khác chủ đề cùng style theo `quy_chuan_phong_cach_kenh.md`.
- [ ] Đóng băng tài liệu hợp đồng v1 cho KhoaPhongCach/LenhTaoShot/DanhGiaLLM/BienNhanHarness và API; integrator công bố owner file, base hashes, lease, môi trường riêng và dependency waves trước chia việc.
- [ ] Founder duyệt prototype và storyboard mẫu trước G2–G6; lưu biên bản/phiên bản prototype được duyệt.

**Đầu ra:** prototype và quyết định UX. **Kiểm thử:** thao tác thử desktop, mobile review, bàn phím và hiển thị tiếng Việt; 120 giây phải thấy nhiều cảnh có tổng đúng. **Bằng chứng:** URL/file prototype, screenshot, biên bản. **Khoảng trống:** chưa có prototype được duyệt. **Go/No-Go:** chỉ chuyển gate khi có duyệt thật; không ghi ô này theo suy đoán.

### G2 — Hợp đồng, phiên bản và run bền vững

**File:** `hop_dong.py`, `kho_phien_ban.py`, entities/migration; `tests/kiem_thu_hop_dong_tao_video.py`, `tests/kiem_thu_luu_phien_tao_video.py`.

**Giao diện:** `tao_ke_hoach(db, tenant, yeu_cau: YeuCauTaoVideo) -> KeHoachVideo`; `luu_phien_ban(db, plan, expected_revision: int) -> KeHoachVideo`; `tao_luot(db, tenant, plan_id: str, revision: int, key: str) -> LuotSanXuat`; `nhan_buoc(db, worker_id: str, now) -> BuocSanXuat | None`.

- [ ] Viết test thất bại: `kiem_thu_tu_choi_thoi_luong_ngoai_pilot`, `kiem_thu_120_giay_3600_frame`, `kiem_thu_cas_409`, `kiem_thu_khoa_idempotency_khac_payload`, `kiem_thu_doc_cheo_workspace_404`, `kiem_thu_restart_giu_plan_run`.
- [ ] Thêm schema chặt, fingerprint canonical, scope và constraint unique; thêm delta schema tối thiểu; không nhân bản script/timeline.
- [ ] Integrator phát hành code contract v1 có schema fixtures và hash trước khi các lane import; thêm style snapshot, preflight/receipt và CHO_LLM/CHO_DUYET_PHONG_CACH vào state machine. Mọi đổi contract đi qua integration queue, không đổi lén từ lane.
- [ ] Migration dry-run trên bản sao, kiểm record count/ID trước–sau, rollback và migrate lại không trùng.
- [ ] Chạy `python -m pytest tests/kiem_thu_hop_dong_tao_video.py tests/kiem_thu_luu_phien_tao_video.py -q`; tất cả pass và kiểm hai worker cạnh tranh cùng bước chỉ một lease.
- [ ] Rà diff và commit trong repository đã xác nhận; không commit DB/media/secret.

**Đầu vào:** G1 được duyệt. **Đầu ra:** hợp đồng/version/run bền vững. **Bằng chứng:** migration/restore logs, test logs và record hash. **Khoảng trống:** schema cụ thể phải khớp DB G0. **Go/No-Go:** dữ liệu cũ còn nguyên, CAS/scope/lease pass mới chuyển.

### G3 — Content thành research, kịch bản, cảnh và prompt

**File:** `lap_ke_hoach.py`, scripts services; `tests/kiem_thu_phan_canh_noi_dung.py`, `tests/kiem_thu_claim_cong_nghe.py`.

**Giao diện:** `lap_ke_hoach(yeu_cau, research_pack, llm, capabilities) -> KeHoachVideo`; `kiem_tra_bao_phu(plan, yeu_cau) -> list[VanDe]`. `VanDe` khai báo tại `hop_dong.py`: mã, mức độ, scene/shot/timecode tùy chọn, thông điệp và evidence.

- [ ] Test thất bại với content 120 giây cần nhiều luận điểm, phủ định “không thêm nhân vật”, giữ nguyên thuật ngữ, input cực ngắn và content dài; mọi ý bắt buộc phải có scene mapping.
- [ ] Test `kiem_thu_json_llm_bi_cat_khong_thanh_cong_gia`, `kiem_thu_nguon_co_chi_dan_doc_hai_khong_doi_cau_hinh`, `kiem_thu_claim_chua_kiem_chung_chan_duyet`.
- [ ] Tạo entry trực tiếp qua brief/idea/script thật; LLM tập trung cấu hình, schema nhiều bước có token cap; map nguồn/claim và trạng thái; giữ script revision.
- [ ] Tạo scene IDs ổn định, continuity bible, shot/prompt riêng; tận dụng compiler một shot. Tách layout diagram/text khỏi AI video để không sinh chữ sai.
- [ ] Khóa style kênh trước planner; LLM chỉ chuẩn hóa trong phạm vi style, xuất đánh giá và hash; test prompt đòi đổi phong cách không ghi đè company/channel lock. Chưa có style duyệt thì chặn production.
- [ ] Chạy hai test file bằng `python -m pytest ... -q`, sau đó thử LLM thật với 3 brief được phép, lưu request đã scrub, response cấu trúc, coverage và blockers; không coi mock là live.
- [ ] Người phụ trách nội dung duyệt lời, sources và storyboard; commit phần code đã rà.

**Đầu vào:** G2, nguồn và LLM khả dụng. **Đầu ra:** script/storyboard/prompt versioned đủ 120 giây dự kiến. **Bằng chứng:** JSON, source ledger, diff và test logs. **Khoảng trống:** LLM/nguồn không khả dụng thì phần AUTO dừng tại đây; vẫn cho nhập script bằng tay. **Go/No-Go:** không claim unsupported được dùng như sự thật và không mất ý bắt buộc.

### G4 — Giọng đọc, căn phụ đề và thời gian thật

**File:** `tao_giong_doc.py`, `can_thoi_gian.py`, registry; `tests/kiem_thu_giong_doc_va_can_thoi_gian.py`.

**Giao diện:** `tao_giong_doan(scene, voice_profile, key: str) -> KetQuaGiong`; `can_thoi_gian(plan, voice_results: list[KetQuaGiong], capabilities) -> KeHoachVideo`. `KetQuaGiong` gồm asset ID, số mẫu, sample rate, duration đo thật, timing cues, provider receipt, voice version.

- [ ] Test frame allocation luôn tổng 3.600 ở 120 giây; cảnh duration dương; transition overlap được tính đúng; provider 8 giây làm cảnh 15 giây thành nhiều shot hợp lệ.
- [ ] Test lời 150 giây nhưng yêu cầu 120 ở GIU_NGUYEN_LOI trả `CHO_XU_LY_THOI_LUONG`, không thay chữ; narration rỗng khi cần voice bị chặn.
- [ ] Test alignment cues không âm, không vượt audio, sai cue có issue; chữ Việt dài không tràn bounding box; từ điển RAG/API/MCP giữ cách đọc đã duyệt.
- [ ] Cài adapter một giọng cloud tiếng Việt có quyền, hoặc nhập voice hợp lệ trong HYBRID. Sinh mẫu thật, đo audio, nghe và ghi quyết định; không bật AUTO nếu chỉ upload voice thủ công.
- [ ] Căn lời và caption theo audio thật, chốt timing; sửa nội dung tạo revision/duyệt mới; tối đa 2 vòng điều chỉnh timing tự động trước trả người dùng.
- [ ] Lấy voice/phát âm/nhạc/caption từ style snapshot; đổi voice hoặc template ngoài binding phải tạo revision và đi qua gate duyệt style, không tự thay giọng giữa hai video cùng kênh.
- [ ] Chạy test file bằng pytest; kiểm bằng tai và timecode mẫu đầu/giữa/cuối, ngưỡng đồng bộ 200 ms; commit sau rà.

**Đầu vào:** script/storyboard duyệt, giọng và alignment capability. **Đầu ra:** voice thật, SRT/cues và timeline budget thật. **Bằng chứng:** audio/hash/ffprobe, cues, nhật ký nghe. **Khoảng trống:** chưa có benchmark/credential thì đánh dấu BLOCKED cho AUTO. **Go/No-Go:** không cắt lời và không dùng ước lượng từ làm thời lượng cuối.

### G5 — Điều phối provider, retry, resume và ngân sách

**File:** `danh_muc_nang_luc.py`, `dieu_phoi.py`, `kho_phien_ban.py`, video_provider/job_engine và worker; `tests/kiem_thu_dieu_phoi_san_xuat.py`.

**Giao diện adapter:** `kiem_tra_nang_luc(account) -> NangLuc`; `gui(shot, idempotency_key: str) -> BienNhan`; `tra_cuu(receipt: BienNhan) -> KetQuaTao`; `huy(receipt) -> TrangThaiHuy`. Các hợp đồng khai báo tại `hop_dong.py`; không giả cancel thành công nếu provider không hỗ trợ.

- [ ] Test scope theo project/workspace, recheck grant trước side effect và sau thời gian chờ; giữ action map tĩnh của worker.
- [ ] Test process chết sau provider submit, timeout chưa biết kết quả, session hết hạn, quota, hai lần click, hai worker; cùng fingerprint không tạo/tính phí lần hai.
- [ ] Implement durable DAG/checkpoint/lease, global concurrency 1, receipt reconciliation, backoff và retry cap của đặc tả; không chạy workflow trong event handler trình duyệt.
- [ ] Integrator triển khai `cong_harness.py` theo chữ ký đóng băng; mọi dispatch cần DanhGiaLLM + BienNhanHarness khớp command/style/approval/policy hash, quyền và lease còn hiệu lực.
- [ ] Chuyển toàn bộ entrypoint tạo mới sang cổng; test raw prompt, receipt giả/hết hạn/khác workspace, sửa payload sau preflight, LLM timeout và legacy bypass đều có call-count Flow bằng 0.
- [ ] Chạy `python -m pytest tests/kiem_thu_cong_harness.py tests/kiem_thu_phong_cach_kenh.py -q`; kiểm receipt submit/resume không gọi LLM hoặc provider trùng; live shot có đủ audit chain.
- [ ] Bật Flow UI adapter theo capability/account thật; registry không gán nhãn API chính thức cho đường Flow UI. Không tự chuyển provider làm tăng phí khi chưa theo policy ngân sách.
- [ ] Giữ chỗ ngân sách cả run và bước; hoàn/đối soát đúng khi lỗi/hủy; lưu credit/phí chưa biết tách 0 đồng. Test hết budget giữa phim giữ các shot đã thành công.
- [ ] Chạy pytest file trên, test restart và kết quả muộn sau hủy; chạy tối thiểu một shot live có quyền và lưu receipt/file/hash. Commit sau rà.

**Đầu vào:** G4 và quyền provider. **Đầu ra:** asset theo shot, trạng thái bền vững và usage ledger. **Bằng chứng:** job ID, logs đã scrub, output thật và lỗi có chủ đích. **Khoảng trống:** không có entitlement thì capability BLOCKED; không thay bằng testsrc. **Go/No-Go:** provider đã bật phải có live evidence; không trùng side effect khi resume.

### G6 — Lắp ráp, render và xuất gói đầy đủ

**File:** `lap_timeline.py`, `xuat_goi.py`, video_processor/bo_render; `tests/kiem_thu_lap_rap_video_120_giay.py`.

**Giao diện:** `lap_timeline(plan, assets, voice) -> TimelineDocument`; `kiem_tra_chuyen_doi_v2(document) -> list[VanDe]`; `xuat_goi(run_id, timeline_version_id, output_asset_id) -> ManifestGoi`.

- [ ] Viết test nhiều cảnh có voice/music/caption/outro; clip ngắn bị chặn, mất asset bị chặn; không kéo/loop cảnh AI để bù phút.
- [ ] Map scene/shot sang timeline dùng chung; normalize format, giữ frame budget và audio master; không silently drop hiệu ứng/track từ V2.
- [ ] Tái sử dụng renderer FFmpeg; thêm adapter diagram/text/outro có version và transition tối thiểu theo prototype. Ảnh/SVG raster hóa chỉ trong bước render, không lưu icon unicode.
- [ ] Render preview sau đó final; tạo SRT, thumbnail, script, storyboard, prompt, editable timeline, manifest/hash, caption gói kênh và QC/usage.
- [ ] Chạy pytest file trên; xuất phim 120 giây từ assets có quyền và full decode bằng `ffmpeg -v error -i <video> -f null -`; ffprobe frame/codec/size/duration, đo EBU R128 và phát toàn bộ.
- [ ] Lưu/mở lại project, render revision mới; commit code sau rà.

**Đầu vào:** G5 hoàn tất assets, voice và kế hoạch đã khóa. **Đầu ra:** phim thật có thể xem và project mở lại. **Bằng chứng:** MP4/hash, ffprobe, full decode, loudness report, playback và manifest. **Khoảng trống:** phim từ asset thủ công là HYBRID, không thay nghiệm thu AUTO. **Go/No-Go:** file 120 ± 0,5 giây có lời/âm thanh/brand, không thiếu package và không lỗi decode.

### G7 — QC, approval gắn revision và sửa cục bộ

**File:** `kiem_dinh.py`, router, hậu kỳ hiện hữu; `tests/kiem_thu_qc_duyet_va_sua_canh.py`.

**Giao diện:** `kiem_dinh(run, artifacts) -> BaoCaoQC`; `duyet(tenant, artifact_hash: str, expected_revision: int) -> PheDuyet`; `tao_lai_canh(tenant, canh_id: str, expected_revision: int, instruction: str) -> LuotSanXuat`.

- [ ] Test cố ý một claim unsupported, một missing asset, caption tràn/sai dấu hoặc aspect sai, nhạc quá lớn và độ dài sai; validator nào chưa đo được phải chuyển reviewer, không đánh pass tự động.
- [ ] QC hard tokens cùng AI/human review style drift trên 3 video cùng binding; kiểm tham chiếu/voice/color grade/type/caption/outro. Score AI không được tự pass sai brand; tối đa 2 lần sửa style theo budget rồi trả reviewer.
- [ ] Khóa approval theo hash/revision/dependency; API người thiếu quyền không được approve/export/publish; không thay cơ chế RBAC đã có hoặc cấp thêm quyền sống.
- [ ] Thay riêng c08/shot b: giữ hash asset/voice/caption ngoài phạm vi, sinh revision và diff; bản cũ vẫn phát được. Được render lại composite nhưng không sinh lại tất cả nguồn.
- [ ] Sửa narration làm voice/alignment/timing/QC/approval liên quan mất hiệu lực; xuất gói cũ không được gắn nhãn revision mới.
- [ ] Kiểm thử reject → sửa → QC lại → approve → final render → QC file final. Chạy pytest file và các test quyền/harness bị ảnh hưởng; commit sau rà.

**Đầu vào:** G6 có file thật. **Đầu ra:** báo cáo QC, approval và revision chính xác. **Bằng chứng:** timecode issues, hash diff, audit trail và test quyền. **Khoảng trống:** độ đúng nội dung và cảm nhận giọng cần người duyệt. **Go/No-Go:** không có blocker QC; không thể dùng approval cũ cho nội dung mới.

### G8 — Giao diện content-first tích hợp thật

**File:** route/components/API client trong bảng file; router backend. **Phụ thuộc:** prototype G1, API G2–G7. Có thể phát triển UI theo mock contract sau G1 nhưng gắn nhãn mẫu và không báo tích hợp thật.

- [ ] Form nhập content, thời lượng và chế độ lời; lưu được khi refresh; dùng project ID thật và nguồn content đã nhập.
- [ ] Hiển thị kênh/style version đã khóa, mẫu tham chiếu và trạng thái duyệt; chỉ người được cấp quyền đổi binding. Form nhập content không cung cấp lối đổi style tự do trái quy chuẩn.
- [ ] Xem/sửa kịch bản, scene cards, prompt, voice, timing và blocker; thao tác duyệt gửi API đúng revision.
- [ ] Nút sản xuất tạo một run; polling theo ID, refresh/resume không làm mất phiên; phần trăm tính từ bước có kết quả thật, không chạy animation theo giờ giả.
- [ ] Hiển thị trạng thái lỗi kèm hành động đúng: đăng nhập lại, bổ sung recording, xử lý thời lượng, thử lại bước hoặc tiếp tục run; hủy phải gọi server.
- [ ] Mở editor chi tiết, sửa một cảnh và xem version; tải MP4/gói qua auth, kiểm hash file tải và mở player.
- [ ] Chạy `pnpm exec tsc --noEmit`, `pnpm run build`, kiểm trình duyệt qua tài khoản được cấp quyền; desktop, mobile review, keyboard/focus, loading/error và tiếng Việt.
- [ ] Test trình duyệt: nhập content 120 → xem nhiều cảnh → duyệt → sản xuất → refresh → preview/QC → sửa một cảnh → tải; lưu screenshot và job ID; commit sau rà.

**Đầu ra:** hành trình thực không cần sửa DB hoặc nhập prompt thủ công. **Bằng chứng:** build/typecheck, screenshots, HTTP/run ID và tải file. **Khoảng trống:** trang HTTP 200 chưa đủ để pass. **Go/No-Go:** người không kỹ thuật tự hoàn tất flow đã định.

### G9 — Nghiệm thu nội bộ và phát hành có kiểm soát

**Đầu vào:** G0–G8 pass và ma trận nghiệm thu đủ evidence.

- [ ] Sản xuất 3 video thật: AI Agent vs Chatbot 60 giây; RAG vs Fine-tuning 120 giây; workflow doanh nghiệp 120 giây. Nguồn/claim được reviewer xác nhận, đa dạng ít nhất 5 cảnh/loại tư liệu theo master spec.
- [ ] Có ít nhất một phim 120 giây chạy AUTO với provider live, nhiều shot AI khi storyboard yêu cầu, voice/alignment thật; chỉ manual/HYBRID thì không pass phần AUTO.
- [ ] Đo thời gian từng bước, chi phí/credit và công sửa, ghi phần chưa biết; không bịa KPI tiết kiệm. Thu phản hồi của người làm nội dung, người dựng và reviewer.
- [ ] Chạy hồi quy baseline G0, secret scan, permission tests, restart/cancel/lease/budget và restore; kiểm profile/cookie không vào artifact/public.
- [ ] Nghiệm thu song song: 2 lane giao trên cùng contract/base, không sửa chồng file, test DB/tmp/ports tách, integration queue xử lý thay đổi shared và stale hash; tổng hợp test trên bản tích hợp mới nhất trước merge/rollout.
- [ ] Nghiệm thu preflight và đồng nhất style NT32–NT42; lưu style snapshot + LLM evaluation + Harness receipt + provider receipt cho các shot live; không coi mẫu style/protocol đã viết là cơ chế đã chạy.
- [ ] Kiểm package theo kênh. Publish live chỉ theo quyền riêng; nếu chưa có thì handoff thủ công ghi NOT_PUBLISHED và đủ file, không tự gán PUBLISHED.
- [ ] Bật feature flag cho nhóm pilot; rollback tắt điểm vào mới, dừng enqueue mới, xử lý run đang chạy và mở lại editor/project cũ; không xóa schema khi còn dữ liệu mới.
- [ ] Đóng tài liệu vận hành, lỗi còn mở, đường khôi phục; Founder duyệt kết quả/rollout. Người có vùng ghi phù hợp ghi evidence chính thức, snapshot và trang hành trình; cập nhật CURRENT_STATE/CHECKPOINT chỉ khi gate thực đạt.

**Đầu ra:** dây chuyền nội bộ có nghiệm thu, runbook và phương án rollback. **Kiểm thử:** toàn bộ hàng bắt buộc trong ma trận. **Bằng chứng:** ba phim, project, logs, reviewer và biên bản duyệt. **Khoảng trống:** analytics/lead và API xuất bản chưa tích hợp phải ghi rõ, không cản gói đăng thủ công đã duyệt nhưng không được coi master spec toàn hệ thống đã hoàn tất. **Go/No-Go:** Founder chấp nhận pilot và không còn blocker; không tự triển khai production.

## 5. Nhánh tiếp theo bao phủ định hướng toàn hệ thống

Không bỏ các yêu cầu ngoài module video. Chia thành các nhánh sau bộ tạo phim hoạt động để không biến nhu cầu 120 giây thành dự án SaaS không liên quan.

| Master spec | Gate ưu tiên tương ứng | Phần mở rộng phải có kế hoạch/test riêng |
|---|---|---|
| P0, quản lý thay đổi mục 9 | G0 và G9 | Audit toàn dashboard, ingestion, publishing và deploy nếu chưa được kiểm trong baseline video |
| P1, UX mục 6 | G1 và G8 | Điều hướng chung, search/inbox/calendar hợp nhất; giữ deep links |
| P2, research/script | G3 và G4 | Topic Radar/series planner 40/40/20 có cấu hình, Research Desk lưu snapshot/độ mới; test 3 chủ đề và nguồn thiếu |
| P3, storyboard/editable | G2, G3, G6, G7 | Import/export nhiều định dạng khi chứng minh không mất scene ID/track |
| P4, adapters/render | G4–G6 | 16:9, 1:1, 4:5, long-form và remote render; test preset độc lập trước bật |
| P5, QC/collaboration | G7 và G8 | Giao việc/SLA/reviewer inbox đầy đủ; permission test từng action theo guardrails |
| P6, publishing/analytics/leads | Package G6, G9 | Xác minh API từng kênh, idempotent schedule, external ID; metrics provenance/N/A; CTA/UTM/lead nội bộ theo mục đích đã duyệt |
| P7, regression/security | G0, G9 | Tải thực tế đội nội bộ, RTO/RPO đo thật, monitoring, kiểm mobile/restore và quyền đa nhóm |
| P8, pilot/optimization | G9 | Phân phối khi được duyệt, retention/CTA/outro A/B theo dữ liệu thật; không suy nhân quả từ ít mẫu |

Mỗi nhánh trên phải giữ mẫu phase: đầu vào, file/commit thay đổi, API/DB impact, điều chạy thật/chưa xác minh, test/log/artifact, hồi quy, rủi ro/blocker và quyết định chuyển gate. Không xóa yêu cầu trong master spec; chỉ xác định rõ đường ưu tiên và phần chưa triển khai.

## 6. Hồ sơ bàn giao và rollback

Bộ kế hoạch hiện tại bao phủ: báo cáo AS-IS/TO-BE và tích hợp trong `nghien_cuu_hien_trang_va_phuong_an.md`; kiến trúc/domain/API trong `dac_ta_bo_tao_video_hoan_chinh.md`; file/tasks/migration/rollback/runbook trong tài liệu này; test evidence và open gaps trong `ma_tran_nghiem_thu.md` và `bang_chung/`. Khi thi công phải bổ sung nhật ký file/commit, provider capability ledger và release notes thực, không chỉ đổi các ô checklist.

Rollback dữ liệu: ưu tiên tắt feature flag và giữ dữ liệu additive; restore chỉ vào môi trường kiểm chứng trước, có mapping các revision mới. Không drop bảng mới để rollback khi đã có nội dung cần giữ. Không tự đổi quyền/kênh hoặc ghi đè nguồn.

## 7. Checklist hoàn tất phiên nghiên cứu

- [x] Đọc master spec và yêu cầu video 120 giây/nội bộ.
- [x] Đọc trạng thái, trang hành trình và checkpoint hiện hữu; không dùng self-report cũ làm bằng chứng chạy thật.
- [x] Đối chiếu đường đi tự động, compiler, provider, renderer, script, worker và schema.
- [x] Tra cứu nguồn chính thức cho clip capabilities, Flow, TTS và FFmpeg.
- [x] Lập đặc tả, kế hoạch file/task/test/gate và ma trận nghiệm thu.
- [ ] Prototype và Founder duyệt G1.
- [ ] Thi công G2–G8, video thật 120 giây và nghiệm thu G9.

Trạng thái hai ô cuối phải giữ chưa hoàn thành cho tới khi có bằng chứng thực.

## 8. Điểm vào thi công song song

Đọc `quy_uoc_thi_cong_song_song.md` để nhận lane và file cụ thể. Trình tự: G0 inventory/backup và G1 prototype/style → integrator khóa contract code ở G2 → giao tối đa 3 worker theo slot và dependency wave → tích hợp shared qua một hàng đợi → chạy kiểm thử trên bản tổng hợp → reviewer độc lập dùng lại slot rảnh. Sửa bảo trì hiện hữu được tiếp tục trong vùng không giao nhau; không chờ toàn bộ module mới xong, nhưng thay đổi public contract/shared phải qua integrator.

Không có worktree/Git đã xác minh thì dùng owner file + base hash + staging patch và integration tuần tự tại vùng dùng chung; không tự clone app thứ hai hoặc sửa cùng file để giả lập song song. Flow/render/voice nặng vẫn concurrency 1 toàn môi trường dùng chung, dù tác vụ viết code/tài liệu có thể song song.
