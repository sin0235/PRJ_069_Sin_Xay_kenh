# Kế hoạch triển khai harness dựng và sửa video chuyên nghiệp BAHA

> **Dành cho AGY và agent thực thi:** đọc đặc tả, nghiên cứu và ma trận nghiệm thu trước khi nhận task. Khi được giao triển khai, dùng skill executing-plans theo từng task; chỉ dùng subagent-driven-development nếu phương thức đó đã được chọn. Tất cả checkbox đang là việc tương lai. Không có phase sản phẩm nào được nghiệm thu trong phiên lập kế hoạch.

**Mục tiêu:** tối ưu toàn diện công việc dựng video BAHA bằng agent thao tác thật từ ảnh/video, hậu kỳ chuyên nghiệp, sửa cảnh qua Flow/API và sửa theo phản hồi, có bản xuất và project tiếp tục chỉnh sửa được.

**Kiến trúc:** kế thừa Media Studio đã qua M-P7, dùng timeline/version BAHA làm ranh giới điều phối; tool broker kiểm soát agent và engine/NLE. Agent làm việc trên draft, provider tạo derivative riêng, QC độc lập kiểm tra artifact trước duyệt và commit. Một bên ghi project tại một thời điểm.

**Công nghệ:** Next.js/React/TypeScript, FastAPI/Pydantic, SQLAlchemy và cơ sở dữ liệu hiện hành, FFmpeg/FFprobe CPU; API hosted cho ASR/VLM/LLM/sửa ảnh-video; engine/NLE chọn bằng PoC. Chưa chọn thêm framework agent, database, queue server hay editor repo vào sản phẩm.

**Đặc tả:** [dac_ta_harness_dung_video_baha.md](dac_ta_harness_dung_video_baha.md).

**Nghiên cứu:** [nguồn, hiện trạng và quyết định](nghien_cuu_harness_dung_video_2026_10_23.md).

**Nghiệm thu:** [ma trận fixture, kiểm tra và ngưỡng](ma_tran_nghiem_thu_harness_dung_video_baha.md).

**Tiền nhiệm bắt buộc:** [plan media-first M-P0..M-P7](../ke_hoach_tich_hop_media_studio/ke_hoach_mo_rong_video_studio_media_first_2026_10_23.md). Không sửa hoặc thay thế plan đó. Nghiên cứu này được phép thực hiện hiện tại; triển khai H00 trở đi chỉ mở sau M-P7 có biên bản nghiệm thu thật.

## 1. Ràng buộc toàn cục

- Code/tài liệu mới chỉ ở `03_ban_lam_viec/`; state theo quyền đã quy định tại `00_bat_dau/`. Bảo vệ 01/02. Tên mới tiếng Việt không dấu snake_case, nội dung tiếng Việt, biểu tượng SVG.
- H00 chốt quyền ghi evidence và snapshot với AGY/Owner theo AGENTS; không mặc định được ghi 08/90. Kế hoạch chỉ ghi tài liệu trong 03, chưa tạo checkpoint sản phẩm.
- Mọi phase có gate, artifact hash, lệnh/exit code hoặc xác nhận thao tác thật. DOC_VERIFIED, CODE_READ, LOCAL_TESTED, LIVE_TESTED, HUMAN_VERIFIED là các mức khác nhau.
- Tất cả AI inference dùng hosted API/Flow; FFmpeg worker CPU. Không tải/chạy mô hình AI local từ dependency hoặc script setup. Tác vụ nặng concurrency tối đa 1; tăng tài nguyên là quyết định riêng.
- H01 phải có prototype và Founder duyệt trước code backend nặng, PoC engine hoặc kết nối live tài khoản.
- Dùng lại MediaAsset/TimelineVersion, quyền, budget guard, audio/video processors và review workflow khi đã đối soát. Không tạo timeline hoặc hệ phân quyền song song.
- Provider chính thức phải có chứng cứ gọi endpoint công bố; không lấy tên class, model hay file làm bằng chứng. Flow assisted không biến thành browser bot trong plan này.
- Giữ bản gốc; generated/edited media là asset mới UNREVIEWED. Agent không tự duyệt bản cuối, xuất bản, xóa nguồn hoặc xóa lịch sử.
- TikTok: 1080x1920/30 FPS, -14 LUFS ±1, safe zone trên 150/dưới 320/phải 120 px. Profile khác có cấu hình riêng. True peak -1,5 dBTP và các KPI khác là mục tiêu đề xuất phải duyệt tại H01.
- Các file/test/endpoint ghi là mới dưới đây chưa tồn tại theo kế hoạch. Nếu M-P7 đã tạo phần tương đương, H00 ánh xạ lại, dùng lại và lưu biên bản sai khác trước khi tiếp tục.

## 2. Các lỗi cần chú ý xuyên suốt

| Tình huống | Hành vi phải có | Task và test chịu trách nhiệm |
|---|---|---|
| Agent quay lại sau restart nhưng provider đã nhận request | Tra pending job/cost cũ, không generation hoặc thu phí lần hai | T04, T08; `test_khoi_dong_lai_khong_gui_lai`, `test_timeout_khong_ro_trang_thai` |
| Editor sửa native project chứa effect không chuyển ngược được | Render từ đúng native revision; chặn BAHA render từ timeline cũ | T09; `test_sua_tiep_native_khong_mat_finishing` |
| Ripple/retime/đổi camera tác động captions/audio | Source map và liên kết cập nhật cùng giao dịch | T06A/T06D; `test_ripple_cap_nhat_caption_va_audio`, `test_retime_va_goc_may_co_map_nguon` |
| Media/ref chứa yêu cầu vượt quyền hoặc gửi tệp khách khác | Nội dung chỉ là dữ liệu; broker tự giới hạn công cụ và outbound | T04/T11; `test_injection_khong_thay_doi_quyen`, `test_khong_truy_cap_cheo_workspace` |
| Flow trả clip dài hơn và đổi chi tiết ngoài preserve list | Giữ placement, chặn thay thế tự động và yêu cầu quyết định rõ | T08; `test_ket_qua_khac_duration_bi_chan`, `test_bao_toan_phan_khong_yeu_cau_sua` |

## 3. Phạm vi và trách nhiệm

AGY quản lý gate, đối soát claim/evidence, chọn task trong command card và bàn giao. Agent thực thi hoàn thiện từng task có test; lead editor BAHA cung cấp fixture/nhận xét nghề dựng. Founder duyệt trải nghiệm, chính sách dữ liệu/chi phí, lựa chọn NLE và các mốc phát hành. Người tạo bản dựng không tự nhận vai người duyệt cuối.

C01–C16 trong đặc tả đều thuộc kế hoạch. Mức agent tối thiểu tại đặc tả mục 4 là bắt buộc; HUMAN_REQUIRED chỉ dùng cho thao tác chuyên sâu vượt mức đó. Thiếu một nhóm bắt buộc thì chỉ nghiệm thu phần đã đạt, chưa đóng toàn bộ H12. Giữ riêng trạng thái “agent tự sửa cảnh API” và “Flow assisted đã kiểm tra”.

## 4. Bản đồ file dự kiến

Các đường dẫn tính từ `03_ban_lam_viec/`. H00 lập mapping cuối theo code sau M-P7. Các tệp mới phải nhỏ theo trách nhiệm; không tách thêm lớp nếu một hàm hiện hữu đã đáp ứng.

| Tệp | Tạo/sửa khi triển khai | Trách nhiệm |
|---|---|---|
| `sin_content_api/src/modules/dieu_phoi_dung/hop_dong.py` | Mới, T03 | Pydantic schema và error enum theo đặc tả |
| `sin_content_api/src/modules/dieu_phoi_dung/thoi_gian.py` | Mới, T03 | Rational/PTS, chuyển v1-v2 và source mapping |
| `sin_content_api/src/modules/dieu_phoi_dung/phien_dung.py` | Mới, T04 | Run/draft/checkpoint, CAS, resume/cancel và commit |
| `sin_content_api/src/modules/dieu_phoi_dung/cong_cu.py` | Mới, T04/T06 | Allowlist tool, validation/authorization, dispatch/readback |
| `sin_content_api/src/modules/dieu_phoi_dung/bo_dinh_tuyen.py` | Mới, T04 | HTTP API run/draft/ops/review và lỗi chuẩn |
| `sin_content_api/src/modules/dieu_phoi_dung/hieu_tu_lieu.py` | Mới, T05 | Bằng chứng từ ASR/VLM, retrieval theo nguồn |
| `sin_content_api/src/modules/dieu_phoi_dung/dao_dien.py` | Mới, T07 | Brief -> plan -> thao tác draft -> phản hồi |
| `sin_content_api/src/modules/dieu_phoi_dung/sua_bang_flow.py` | Mới, T08 | Capability, đơn sửa, assisted/API, import và provenance |
| `sin_content_api/src/modules/dieu_phoi_dung/ket_noi_phan_mem_dung.py` | Mới T06, mở rộng T09 | Adapter thao tác engine/NLE đã chọn, rồi mapping native/canonical và bàn giao |
| `sin_content_api/src/modules/dieu_phoi_dung/kiem_dinh.py` | Mới, T11 | QA đọc snapshot/render, chỉ phát hành kết quả đo |
| `sin_content_api/src/models/entities.py` | Sửa tối thiểu T03/T04 | Lưu run/draft/journal còn thiếu; dùng timeline/asset cũ |
| `sin_content_api/src/main.py` | Sửa T04 | Đăng ký router mới; giữ guard/service hiện hành |
| `sin_content_api/src/modules/media_studio/{router,service,job_engine,video_provider,video_processor,audio_processor}.py` | Sửa theo khoảng trống T04/T06/T08/T11 | Tái dùng upload/render/job/budget; không nhân đôi chức năng |
| `sin_content_workers/worker.py` | Sửa nếu là worker được M-P7 chọn, T04 | Hàng đợi bền vững và lease liên tiến trình; không tạo queue RAM thứ hai |
| `sin_creator_os/src/app/(main)/video-studio/[projectId]/page.tsx` | Sửa T01/T10 | Prototype và luồng điều phối trong studio hiện có |
| `sin_creator_os/src/components/video_studio/bang_dieu_phoi_dung.tsx` | Mới nếu cần T10 | Run status, diff, phản hồi, Flow roundtrip, review |
| `sin_creator_os/src/lib/api/bo_dieu_phoi_dung_api.ts` | Mới T10 | Client typed theo OpenAPI thật |
| `sin_creator_os/src/lib/api/media-studio-api.ts` | Sửa khi cần T10 | Tái sử dụng media/timeline đã có |
| `sin_content_api/tests/test_harness_*.py` | Mới theo từng task, tên cụ thể ở dưới | Offline unit/integration, live tách riêng |
| `sin_creator_os/tests/e2e/run_ui_verification.py` | Mở rộng T10 | Kịch bản thao tác thật và đường dẫn evidence truyền được |
| `ke_hoach_harness_dung_video_baha/anh_xa_engine_da_chon.md` | Tạo tương lai T02/T03 | Commit/license/runtime, type tham số, op coverage và loss report |
| `ke_hoach_harness_dung_video_baha/ho_so_nghiem_thu/` | Tạo tương lai sau chốt quyền H00 | Chỉ mục link evidence; không thay kho evidence canonical |

Không tạo mọi file ngay từ đầu. Adapter thứ hai/MCP facade chỉ tạo khi H02 chứng minh cần và ghi tên file/type trong phụ lục đã duyệt. Không đưa upstream repo nguyên trạng vào module sản phẩm.

## 5. Hợp đồng nối các task

Các kiểu dưới đây định nghĩa một lần tại `hop_dong.py`, nội dung theo đặc tả mục 6; đây là giao diện mới đề xuất. `Db` là SQLAlchemy Session hiện hành; `NguCanhQuyen` lấy từ tenant dependency/worker grant đã đối soát. Kiểu ID là `str`, revision là `int`, lỗi có enum và không chứa secret.

| Giao diện | Tệp | Task cung cấp |
|---|---|---|
| `kiem_tra_ke_hoach(plan: KeHoachDung, snapshot: TimelineV2, evidence: list[BangChungNguon], policy: ChinhSachPhien) -> list[LoiHopDong]` | `hop_dong.py` | T03 |
| `chuyen_timeline_v1(doc: dict, profile: CauHinhDauRa) -> TimelineV2` | `thoi_gian.py` | T03 |
| `tao_phien(db: Db, ctx: NguCanhQuyen, payload: TaoPhienDung) -> DinhDanhPhien` | `phien_dung.py` | T04 |
| `tao_ban_nhap(db: Db, ctx: NguCanhQuyen, run_id: str, base_revision: int, base_hash: str) -> BanNhapDung` | `phien_dung.py` | T04 |
| `thuc_hien_lenh(db: Db, ctx: NguCanhQuyen, run_id: str, commands: list[LenhDung]) -> KetQuaCongCu` | `cong_cu.py` | T04/T06 |
| `tiep_tuc_phien(db: Db, ctx: NguCanhQuyen, run_id: str) -> TrangThaiPhien` | `phien_dung.py` | T04 |
| `phan_tich_tu_lieu(db: Db, ctx: NguCanhQuyen, asset_ids: list[str], config: CauHinhPhanTich) -> PhienPhanTich` | `hieu_tu_lieu.py` | T05 |
| `lap_ke_hoach(snapshot: TimelineV2, evidence: list[BangChungNguon], brief: YeuCauDung, policy: ChinhSachPhien) -> KeHoachDung` | `dao_dien.py` | T07 |
| `lap_ke_hoach_sua(snapshot: TimelineV2, evidence: list[BangChungNguon], feedback: PhanHoiDung, policy: ChinhSachPhien) -> KeHoachDung` | `dao_dien.py` | T07 |
| `tao_don_sua_canh(db: Db, ctx: NguCanhQuyen, request: DonSuaCanh) -> TrangThaiDonSua` | `sua_bang_flow.py` | T08 |
| `nhan_ket_qua_canh(db: Db, ctx: NguCanhQuyen, request_id: str, output_asset_id: str) -> KetQuaNhapCanh` | `sua_bang_flow.py` | T08 |
| `xuat_goi_ban_giao(db: Db, ctx: NguCanhQuyen, revision_id: str, adapter_id: str) -> GoiBanGiao` | `ket_noi_phan_mem_dung.py` | T09 |
| `nhap_phien_ban_native(db: Db, ctx: NguCanhQuyen, bundle: GoiBanGiao, expected_revision: int) -> BanNhapDung` | `ket_noi_phan_mem_dung.py` | T09 |
| `kiem_dinh(db: Db, ctx: NguCanhQuyen, request: YeuCauKiemDinh) -> BienBanKiemDinh` | `kiem_dinh.py` | T11 |

Các kiểu phụ `CauHinhDauRa`, `LoiHopDong`, `NguCanhQuyen`, `TaoPhienDung`, `BanNhapDung`, `TrangThaiPhien`, `CauHinhPhanTich`, `PhienPhanTich`, `YeuCauDung`, `TrangThaiDonSua`, `KetQuaNhapCanh`, `YeuCauKiemDinh` được T03 khai báo cùng schema và ví dụ hợp lệ/không hợp lệ; không để task sau tự dựng type khác. `PhienPhanTich` chứa analysis ID/version, evidence IDs, trạng thái và artifact refs; `TrangThaiDonSua` chứa request/job/interaction IDs, route, state, reserved/actual cost và artifact refs. Type cấu hình chỉ chứa các field được policy/engine schema cho phép; không có object `parameters` mở để model gửi tùy ý.

HTTP đề xuất dưới prefix `/v1/media/projects/{project_id}/dung`: `POST/GET /phien`, `GET /phien/{run_id}`, `POST /phien/{run_id}/tiep-tuc`, `POST /phien/{run_id}/huy`, `POST /ban-nhap`, `POST /ban-nhap/{draft_id}/lenh`, `GET /ban-nhap/{draft_id}/khac-biet`, `POST /ban-nhap/{draft_id}/trinh-duyet`, `POST /ban-nhap/{draft_id}/ghi-nhan`, `POST /don-sua-canh`, `POST /don-sua-canh/{request_id}/ket-qua`, `POST /kiem-dinh`, `POST /ban-giao`. Request IDs không được tự xác định workspace/quyền. Timeline/render/media vẫn dùng API plan trước nếu phù hợp. H03 xuất OpenAPI contracts, xác minh route không trùng và bổ sung path/query cần thiết cho get/diff; không để frontend gọi route chỉ tồn tại trong tài liệu.

## 6. Cách thực hiện mỗi task

Theo thứ tự: đối chiếu input gate -> ghi file/hash baseline -> viết test theo tên/assertion chỉ định -> chạy thấy FAIL đúng hành vi còn thiếu -> thêm mã nhỏ nhất -> chạy PASS và regression liên quan -> lưu evidence -> reviewer xác nhận gate. Không xóa test hoặc bọc fallback để tạo xanh. Test mock chỉ là LOCAL_TESTED.

Lệnh test dưới đây **chỉ dùng ở phiên triển khai sau khi tạo các test**; không phải lệnh đã chạy trong nghiên cứu. Working directory backend là `03_ban_lam_viec/sin_content_api`; frontend là `03_ban_lam_viec/sin_creator_os`. Test offline phải mock transport provider và chặn mạng. File `tests/test_harness_live.py` chỉ chạy khi `BAHA_HARNESS_LIVE=1` và đã có grant/budget/fixture; thiếu điều kiện phải SKIP/NOT_RUN, không mock rồi báo live.

Sau mỗi task, AGY cập nhật command card và chỉ mục evidence. Nếu có Git đã kiểm tra thì checkpoint thay đổi theo quy trình dự án; nếu không có thì manifest SHA256/diff, không bịa commit. Không chạy cả suite chưa phân loại vì repo có provider tests thật.

## 7. Các phase và cổng nghiệm thu

### H00 — Nhận nền tảng đã nghiệm thu và chốt baseline công việc

**Task T00.** Đầu vào: biên bản M-P7, source snapshot và quyền kiểm tra. Chỉ kiểm kê; chưa sửa code.

- [ ] Đối chiếu từng điều kiện M-P7 bằng source và artifact; kiểm tra nguồn/download/upload/timeline/render/worker, không dùng dòng trạng thái “production ready” làm bằng chứng.
- [ ] Lập bảng sai khác so với L01–L12 của nghiên cứu; đặc biệt không lặp lại nhận định download chưa có auth hay unique index chưa có.
- [ ] Kiểm kê NLE/edition/license, CPU/RAM/disk/NAS, loại project, render profiles, phiên bản FFmpeg, template/font/LUT và quyền media thực tế.
- [ ] Chọn 10 project đại diện để đo baseline ghép cặp, tối thiểu 2 project cho mỗi nhóm: footage có lời, sản phẩm không lời, ảnh, đa camera, sửa cảnh. Lưu nguồn/brief/độ phức tạp và thời gian editor hiện tại.
- [ ] Chốt vùng ghi evidence/snapshot đúng quyền AGENTS; lập command card chỉ rõ owner từng module, nguồn fixture, cấm gọi live trong offline test.
- [ ] Đọc test fixtures/provider trước khi chốt lệnh baseline; ghi lệnh cụ thể đã chọn và exit code trong biên bản H00. Typecheck dùng `pnpm exec tsc --noEmit`, build dùng `pnpm run build`; không dùng script giả định.

**Artifact:** `bien_ban_h00.md`, `baseline_cong_viec.csv`, manifest source/fixture và danh sách safe test; chỉ tạo tại vùng được phép khi triển khai.

**Gate:** M-P7 có đủ chứng cứ, không còn blocker bảo toàn nguồn/tenant/worker bền vững/tự duyệt; dữ liệu và baseline đo được; có quyền ghi evidence. Nếu worker sau M-P7 vẫn trong RAM thì quay lại điều kiện M-P5/M-P7, chưa mở H01. Không coi T04 tương lai là lý do bỏ điều kiện nền tảng.

### H01 — Duyệt trải nghiệm và chính sách vận hành

**Task T01.** Dùng màn Video Studio và component hiện có, prototype tĩnh; mock phải gắn nhãn minh họa.

- [ ] Dựng prototype: brief/media bin/transcript; lệnh agent và draft diff; preview nhiều lớp; comment theo timecode; đơn sửa Flow; native project; tiến độ/chi phí/dừng/tiếp tục.
- [ ] Mô tả 7 luồng đặc tả bằng một ví dụ BAHA cụ thể mỗi luồng; dựng trạng thái lỗi provider, stale revision, thiếu evidence, native edit required và vượt ngân sách.
- [ ] Cho lead editor kiểm tra công việc thường ngày và Founder duyệt trước backend. Không chỉ duyệt một ảnh dashboard.
- [ ] Chốt policy version: mức tự động hóa tối thiểu C01–C16, dữ liệu gửi cloud, người duyệt, provider/credit grant, session limits, true peak, KPI và dataset/ngưỡng ở ma trận.
- [ ] Ghi quyết định có định danh, người duyệt, prototype hash và ngày; lựa chọn chưa được duyệt giữ PROPOSED.

**Gate:** luồng full edit và sửa Flow đã được duyệt; không hiểu nhầm HUMAN_REQUIRED là agent đã thực hiện. Các thử nghiệm H02 có phạm vi/tài nguyên/ngân sách cụ thể. Không cần hỏi lại từng thao tác nằm trong grant đã duyệt.

### H02 — PoC và quyết định chọn engine, NLE, provider

**Task T02.** Workspace PoC riêng trong 03, không sửa production, không nhập nguyên upstream vào SSOT sản phẩm.

- [ ] Đối chiếu commit audit, tìm script/manifest mà audit nói có; thiếu thì ghi NOT_FOUND. Lập quy trình tái lập bằng lệnh đã đọc, không chạy attachment chưa xác thực.
- [ ] Chọn bản release/commit ghim cho FableCut/OpenChatCut và ghi lockfile/license/dependency scripts; rà local model trước install. Bản branch web khác commit ghim không được dùng lẫn như cùng bản.
- [ ] Thử core BAHA sau M-P7 và FableCut trên cùng fixture F03/F04: thao tác, mở lại, preview/render, CPU/RAM, lock/revision, thiếu effect. OpenChatCut chỉ thử tái sử dụng mã sau quyết định license; nếu không phù hợp, ghi REJECTED và chỉ tham khảo workflow.
- [ ] Kiểm tra kết nối AI assistant/scripting chính thức của NLE BAHA thực dùng, ưu tiên Resolve chính thức khi phù hợp. Chỉ thử MCP cộng đồng nếu chính thức không đủ; ghi đúng repo/commit, không gộp kết quả giữa repo.
- [ ] Kiểm tra provider/account/region bằng capability document trước; live probe nhỏ chỉ dùng fixture được phép và grant. Ghi bất đồng tài liệu UI/API, thực tế account và thao tác chưa hỗ trợ.
- [ ] Lập `anh_xa_engine_da_chon.md`: runtime, exact callable ops, tên/range tham số, editable support, mức tự động hóa, native export/import, failure/rollback và resource budget. Chọn đúng một engine chính, tối đa một NLE finishing đầu tiên; ghi lý do loại các ứng viên còn lại.

**Gate H02-ENGINE:** có đường engine/NLE được chứng minh cho các thao tác C01–C11/C15/C16 liên quan, artifact dựng/đọc lại/render thật, license được người có thẩm quyền chấp nhận, không AI local, không vượt tài nguyên. Không đạt thì BLOCKED/REJECTED, chưa mở T03/T04/T06/T09 dựa trên giả định.

**Gate H02-PROVIDER:** schema/route được tài liệu chính thức hỗ trợ và live probe xác nhận account/model cho các đường C02/C03/C12 đã chọn. Thiếu credential thì NOT_RUN; sau H02-ENGINE được triển khai hợp đồng và các task offline T03–T07 với transport mock gắn nhãn, nhưng không mở live provider/không đóng toàn H02 hoặc H12. Chỉ tạo generation live khi có grant. Hai gate có artifact và trạng thái riêng.

### H03 — Chốt hợp đồng, thời gian và lưu trữ tương thích

**Task T03.** Tạo `hop_dong.py`, `thoi_gian.py`; chỉ sửa model/migration nếu H00/H02 chứng minh cần.

**Input/output:** cung cấp toàn bộ type/giao diện mục 5; nhận mapping engine đã duyệt. Bổ sung phụ lục payload chính xác cho từng LenhDung trước khi code thao tác.

- [ ] Khai báo schema/range: field rational, clip/track/word/evidence IDs, effect enum, role reference, locks, approval binding, request/result và các lỗi; API không nhận shell/path/code/provider URL tùy ý.
- [ ] Định nghĩa dữ liệu bền vững tối thiểu cho run, draft và journal idempotency; liên kết AIGenerationJob/AuditEvent/MediaAsset/TimelineVersion hiện có. Chỉ tạo entity bổ sung cho khoảng trống; không dùng memory dictionary hoặc file JSON làm transaction database.
- [ ] Thêm `test_truong_la_va_thoi_gian_sai_bi_tu_choi`, `test_nguon_ngoai_pham_vi_bi_tu_choi`, `test_v1_v2_giu_nguyen_version_cu`, `test_vfr_dung_pts_khong_dung_fps_trung_binh`, `test_effect_khong_ho_tro_khong_bi_bo_qua` trong `tests/test_harness_hop_dong.py`.
- [ ] Assertion: invalid/unknown/NaN/bool-int/OOB không đổi snapshot; nguồn chéo workspace không hợp lệ; migration không sửa JSON v1 cũ; VFR map đúng nhãn PTS; effect chưa biết trả lỗi trước ghi. Fixture FPS 24000/1001, 25, 30000/1001, 30 và VFR.
- [ ] Chạy đỏ `python -m pytest -q tests/test_harness_hop_dong.py`; thêm converter/validator; chạy lại đạt, migration forward/rollback trên DB test và regression timeline plan trước.

**Gate:** schema version, migration, rational mapping và compatibility được duyệt. Không có payload mở hoặc type giao diện chưa định nghĩa. Mô hình CSDL dùng backend hiện hành; nếu chuyển Postgres là thay đổi kiến trúc riêng, không tự thực hiện trong task.

### H04 — Tool broker, phiên dựng và job bền vững

**Task T04.** Cung cấp tool core/run API tại mục 5; nhận schema T03 và worker nền tảng M-P7.

- [ ] Thêm `tests/test_harness_phien_dung.py`: `test_draft_khong_doi_live`, `test_lenh_nguyen_tu_va_doc_lai`, `test_cung_key_khac_payload_xung_dot`, `test_ghi_stale_hoac_khoa_bi_chan`, `test_khoi_dong_lai_khong_gui_lai`, `test_thu_hoi_grant_truoc_side_effect`, `test_khoa_tac_vu_nang_lien_tien_trinh`.
- [ ] Assertion: rollback toàn batch khi một op sai; revision draft tăng đúng một; project live không đổi trước duyệt; cùng op không lặp; CAS/lease chống hai writer; process mới tiếp tục từ checkpoint; grant đổi hash/version/quyền bị từ chối.
- [ ] Chạy đỏ `python -m pytest -q tests/test_harness_phien_dung.py`; triển khai `phien_dung.py`, `cong_cu.py`, router và main registration; cập nhật worker đã chọn nếu cần, không tạo framework queue thứ hai.
- [ ] Ghi event và checkpoint cùng transaction intent trước gọi bên ngoài; lưu accepted provider ID/cost/result riêng; resume đọc trạng thái cũ, không giữ DB transaction mở trong network/render.
- [ ] Triển khai các state, stop limits và no-progress của đặc tả; đăng ký tool có schema/output/error và budget preflight. HTTP/MCP cùng service guard; không expose `execute_script`/shell của NLE.
- [ ] Chạy lại test đạt; fault injection trước dispatch/sau provider accept/sau file save/trước commit; thử restart hai tiến trình, cancel và lease timeout.

**Gate:** không mất draft/job qua restart; không duplicate side effect đã biết; không vượt scope; concurrency nặng thực tế tối đa 1. Không báo transaction DB có thể rollback một generation đã tính phí; generation đến muộn giữ derivative/journal chờ xử lý.

### H05 — Hiểu tư liệu và truy vấn có bằng chứng

**Task T05.** Cung cấp `phan_tich_tu_lieu`, tool tìm/xem đoạn và evidence theo source hash.

- [ ] Thêm `tests/test_harness_hieu_tu_lieu.py`: `test_tieng_viet_co_word_id_va_nguon`, `test_khong_loi_khong_bia_transcript`, `test_canh_nhanh_can_xem_bo_sung`, `test_doi_source_lam_het_hieu_luc_evidence`, `test_cache_khong_dung_cheo_workspace`, `test_asr_thieu_confidence_khong_tu_gan`.
- [ ] Assertion: mọi selection có asset/range/word/frame refs; silence không sinh speech giả; cảnh 200 ms không được kết luận từ mẫu thưa; evidence cũ bị vô hiệu khi SHA đổi; confidence thiếu là null; ASR/VLM errors không sinh plan tự tin giả.
- [ ] Chạy đỏ `python -m pytest -q tests/test_harness_hieu_tu_lieu.py`; dùng FFmpeg tạo proxy/audio/frame và API hosted được chọn; lượt xem tổng quan rồi lấy evidence chi tiết theo nhu cầu. Không gửi cả thư viện mặc định.
- [ ] Cache khóa workspace/source hash/provider-model/config-version; ghi quyền đưa dữ liệu cloud, thời gian nguồn và token/usage nếu provider trả. Nguồn chưa có phép chỉ phân tích phần nội bộ được phép.
- [ ] Chạy lại đạt; live F01/F02 theo grant để đo transcript/timestamp; ghi LOCAL_TESTED và LIVE_TESTED riêng.

**Gate:** evidence source map kiểm tra được, ASR đạt ngưỡng matrix, cảnh nhanh có mẫu bổ sung, không inference local. Kết quả semantic chưa chắc chắn giữ UNKNOWN/REVIEW_REQUIRED.

### H06 — Lõi thao tác dựng chuyên nghiệp

Thực thi qua engine T02; không viết lại tính năng đã có. Mỗi task sau có vòng test đỏ -> mã tối thiểu -> test đạt -> regression và artifact độc lập.

**Task T06A — Thời gian và nhiều lớp.** Sửa broker, adapter đã chọn và processor hiện hành.

- [ ] Tạo `tests/test_harness_thao_tac.py` với `test_split_trim_insert_overwrite_ripple_slip`, `test_ripple_cap_nhat_caption_va_audio`, `test_ba_lop_video_bon_lop_audio`, `test_lock_va_transition_handle`.
- [ ] Assertion từng lệnh bằng source range/frame thực: tổng thời lượng, vị trí, layer order, linked audio/captions đúng; không cắt hết câu hoặc kéo effect qua lock; transition thiếu handle bị chặn.
- [ ] Chạy `python -m pytest -q tests/test_harness_thao_tac.py` trước/sau triển khai; render F03, mở lại và đọc timeline.

**Task T06B — Âm thanh và phụ đề.** Dùng `audio_processor.py`, timeline caption của plan trước.

- [ ] Tạo `tests/test_harness_am_thanh_phu_de.py`: `test_sync_giong_nhac_sfx_va_j_l_cut`, `test_duck_chi_theo_voice`, `test_phu_de_tieng_viet_va_glossary`, `test_gain_eq_fade_va_peak`, `test_mute_co_chu_y_khong_bi_qa_bao_sai`.
- [ ] Assertion captions vẫn neo word/source sau cắt; chữ có dấu/font/safe zone đúng; J/L cut đúng map; output đo loudness/peak/sync; source silent và track mute được hiểu theo brief.
- [ ] Chạy `python -m pytest -q tests/test_harness_am_thanh_phu_de.py` trước/sau mã; editor nghe F01/F03 và lưu nhận xét, không chỉ đo waveform.

**Task T06C — Hình, màu và compositing.** Dùng adapter engine/NLE đã chọn; profile không có khả năng thì reject.

- [ ] Tạo `tests/test_harness_hau_ky_hinh.py`: `test_transform_keyframe_easing_va_reframe`, `test_color_lut_va_khong_doi_color_space_ngam`, `test_mask_keying_va_quy_dao_tracking`, `test_preview_render_khong_mat_effect`, `test_font_lut_thieu_khong_tu_thay`.
- [ ] Assertion keyframe đầu/giữa/cuối, layer/alpha/mask đúng; color profile/range không bị đổi âm thầm; LUT hash hợp lệ; fixture redaction được kiểm tra mọi frame; preview và export giữ effect tương ứng.
- [ ] Chạy `python -m pytest -q tests/test_harness_hau_ky_hinh.py` trước/sau mã; lưu frames/reference render, color metadata và kết luận editor. Mọi effect thêm ngoài schema đã chọn phải qua T03 cập nhật có test.

**Task T06D — Retime và đa camera.** Dùng time mapping T03, không đồng nhất PTS nguồn và frame timeline.

- [ ] Tạo `tests/test_harness_da_camera.py`: `test_retime_va_goc_may_co_map_nguon`, `test_freeze_reverse_va_audio_policy`, `test_hai_camera_audio_roi_khong_troi_sync`.
- [ ] Assertion 2 camera/audio rời sync tại clap và cuối fixture; speed/reverse/freeze giữ đúng source map, captions/audio được xử lý theo chính sách rõ; góc thay không làm thay audio vô ý.
- [ ] Chạy `python -m pytest -q tests/test_harness_da_camera.py` trước/sau mã; xuất timeline/project và render F04 có marker xác minh.

**Gate H06:** C04–C11 đạt mức agent tối thiểu trên tool thật, frame/time/audio và render/mở lại kiểm tra được. Chuyển task cho người không được thay PASS của các thao tác tối thiểu. Effect chuyên sâu chưa tự động có bảng giới hạn, không bị flatten âm thầm.

### H07 — Agent lập dựng, sửa theo phản hồi và tự giới hạn

**Task T07.** Cung cấp `lap_ke_hoach`, `lap_ke_hoach_sua`; chỉ gọi tool T04/T06, không tự thay DB/file.

- [ ] Thêm `tests/test_harness_dao_dien.py`: `test_plan_chi_dung_nguon_va_evidence_hop_le`, `test_phan_hoi_neo_revision_va_giu_phan_con_lai`, `test_thieu_y_nghia_can_hoi_lai`, `test_vong_lap_dung_khi_khong_tien_trien`, `test_prompt_recipe_co_version`, `test_json_hop_le_nhung_sai_nguon_van_bi_chan`.
- [ ] Assertion rough cut theo brief và lựa chọn có lý do kiểm tra được; patch chỉ vùng được phép; feedback mơ hồ không tự phá bản dựng; giới hạn turn/tool/repair giữ qua resume; giá/sản phẩm/tên riêng không tự bịa.
- [ ] Chạy đỏ `python -m pytest -q tests/test_harness_dao_dien.py`; triển khai director với structured result và validator T03. Dùng lại chính sách lỗi/log LLM hiện có, thêm multimodal transport chỉ khi cần; không giả định text client gửi được video.
- [ ] Tạo recipe có version cho 5 loại việc từ dataset: dựng có lời, product montage, ảnh, multicam và sửa cảnh; chứa input/output/checklist, không nhúng secret và không tự cài skill từ media.
- [ ] Chạy lại đạt; chạy live các brief khác nhau với seed/model/config đã ghi để đánh giá, không kiểm tra bằng chỉ matching câu agent trả lời.

**Gate:** rough cut và lần sửa là draft thực, readback đúng; thiếu evidence hoặc mơ hồ không biến thành hoàn thành. Không yêu cầu swarm nhiều agent trước khi benchmark chứng minh cần.

### H08 — Sửa ảnh/video và quay lại timeline bằng Flow/API

**Task T08.** Cung cấp DonSuaCanh, capability và import; hai đường có trạng thái nghiệm thu riêng.

- [ ] Thêm `tests/test_harness_sua_flow.py`: `test_route_ui_va_api_doc_lap`, `test_capability_het_han_khong_duoc_goi`, `test_reference_khong_bi_nham_nguon_edit`, `test_output_sai_request_hoac_workspace_bi_chan`, `test_ket_qua_khac_duration_bi_chan`, `test_timeout_khong_ro_trang_thai`, `test_bao_toan_phan_khong_yeu_cau_sua`, `test_session_het_han_tiep_tuc_tu_asset_da_luu`.
- [ ] Assertion không chuyển UI constraints thành API constraints; current grant/capability trước gọi; output hỏng/sai source không tạo replacement; timeout unknown không resubmit; session hết hạn không làm mất local result; mặc định audio/placement giữ nguyên; đoạn khác và native finishing không mất.
- [ ] Chạy đỏ `python -m pytest -q tests/test_harness_sua_flow.py`; triển khai adapter chính thức đã chọn và gói assisted từ cùng request. Tách generation có side effect khỏi transaction draft.
- [ ] Assisted: xuất gói source/reference/prompt/preserve list và hướng dẫn; operator thao tác UI chính thức; nhập file với request ID và xác nhận người vận hành. Không thêm browser automation hoặc tái dùng profile/cookie.
- [ ] API: chứng minh request tới endpoint chính thức, actual model/account access, job/interaction chain và tải asset; không dùng class Official cũ nếu vẫn đi qua Flow browser. Ghi quyền retention/store và cách resume.
- [ ] Live bắt buộc: sửa ảnh; ảnh -> clip; sửa một đoạn footage thật rồi ghép lại bản dựng. First/last/reference/continuation thử theo capability; unsupported ghi nguyên trạng, không giả lập. Cho editor duyệt identity/product/dialogue/preserve và chuyển cảnh nối.
- [ ] Chạy lại offline đạt; chỉ chạy live bằng `BAHA_HARNESS_LIVE=1` rồi `python -m pytest -q tests/test_harness_live.py -k sua_media` sau grant. Lưu provider metadata đã làm sạch, SHA và QC thành phẩm.

**Gate:** H08-ASSISTED cần thao tác người thật và roundtrip; H08-API cần agent tự chạy 3 đường tối thiểu C12. Thiếu API access là BLOCKED cho nhánh tự động/H12, không thay bằng mock hoặc đường assisted. Không tự trim/speed để che sai duration, không lấy video khác thay lỗi generation.

### H09 — Bàn giao NLE và sửa tiếp không mất finishing

**Task T09.** Cung cấp `xuat_goi_ban_giao`, `nhap_phien_ban_native`; dùng một adapter NLE đầu tiên đã chốt.

- [ ] Tạo `tests/test_harness_ban_giao.py`: `test_mo_lai_relink_giu_nguon`, `test_loss_report_khong_bo_mat_effect`, `test_sua_tiep_native_khong_mat_finishing`, `test_native_hash_sai_khong_duoc_render`, `test_bake_can_duyet_va_giu_nhanh_goc`, `test_mat_ket_noi_khong_ghi_de_native`.
- [ ] Assertion native-bound chặn renderer canonical cũ; một bên ghi; xuất -> editor sửa grade/mask native -> nhập version -> agent sửa caption/gain/cut được adapter hỗ trợ -> render giữ grade/mask; op không hỗ trợ trả NATIVE_EDIT_REQUIRED không đổi project.
- [ ] Chạy đỏ `python -m pytest -q tests/test_harness_ban_giao.py`; triển khai mapping và readback, project native có hash/checkpoint, loss report explicit; chỉ dùng OTIO/AAF/XML nếu PoC chứng minh adapter cần và giữ đúng phần cam kết.
- [ ] Thử mở gói trên máy editor khác, relink không sửa source, sửa thật, render; nếu không có máy thứ hai thì ca portability chưa PASS.
- [ ] Chạy lại offline đạt và live NLE `python -m pytest -q tests/test_harness_live.py -k ban_giao` khi connector/NLE thật đã sẵn sàng; lưu native project và kết quả readback/render.

**Gate:** gói editable/mapping rõ, vòng đi-về-sửa tiếp đạt, project native quyết định render khi NATIVE_BOUND. Giao MP4 hoặc file XML chưa mở không đủ. Agent không được ép chuyển canonical làm mất hậu kỳ.

### H10 — Studio cho đội edit, thương hiệu và biến thể

**Task T10.** Nối UI prototype H01 với API thật, giữ luồng manual hiện có.

- [ ] Thêm `tests/test_harness_bien_the.py`: `test_template_version_khong_sua_nguon`, `test_bien_the_khong_goi_lai_generation`, `test_comment_ban_cu_khong_sua_nham_ban_moi`.
- [ ] Assertion brand kit/glossary/font có version; variant khác tỷ lệ/duration/caption có revision và QC riêng; đổi đóng gói không gọi lại provider; comment cũ gắn phiên bản cũ.
- [ ] Chạy đỏ `python -m pytest -q tests/test_harness_bien_the.py`; triển khai API/client/components và thao tác keyboard/labels/status/error. Hiển thị rõ bản draft, pending provider, chi phí thực tế/chưa biết và phần cần editor.
- [ ] Mở rộng `run_ui_verification.py` bằng scenario `harness_dung` và tham số `--kich-ban`, `--dia-chi`, `--thu-muc-bang-chung` nếu plan trước chưa có tham số tương đương. API/fixture workspace riêng, không hardcode token/tài khoản thật hoặc output ngoài quyền.
- [ ] E2E: import -> yêu cầu rough cut -> preview/diff -> editor sửa -> conflict -> comment -> Flow import -> duyệt đúng hash -> render -> reload/resume -> variant -> gói NLE. Assertion dữ liệu API/render và DOM, không chỉ ảnh chụp route.
- [ ] Chạy lại backend đạt; frontend `pnpm exec tsc --noEmit`, `pnpm run build`; khi test server đã xác minh chạy `python tests/e2e/run_ui_verification.py --kich-ban harness_dung --dia-chi http://127.0.0.1:3000 --thu-muc-bang-chung <duong_dan_da_duyet>`.

**Gate:** luồng người/agent thống nhất, reload giữ trạng thái, accessibility cơ bản đạt, không demo track/sample URL, mỗi variant có provenance/QC. Không cài Playwright JS framework mới khi Python harness hiện có đáp ứng.

### H11 — Kiểm định độc lập, lỗi và đánh giá agent

**Task T11.** Cung cấp `kiem_dinh`; nhận render/version thật, không tin success flag.

- [ ] Thêm `tests/test_harness_kiem_dinh.py`: `test_success_token_khong_du_thieu_file`, `test_file_hong_va_duoi_den_bi_phat_hien`, `test_im_lang_co_chu_y_khong_bi_chan`, `test_qa_dung_render_hash`, `test_khong_truy_cap_cheo_workspace`, `test_injection_khong_thay_doi_quyen`, `test_approval_khong_duoc_dung_lai_sau_thay_doi`.
- [ ] Assertion full decode thất bại thì FAIL; absence evidence là UNKNOWN; check profile/loudness/peak/caption/sync/cut boundaries; chính sách cloud và tool allowlist thắng nội dung OCR/transcript; approval bind artifact/hash/version và actor.
- [ ] Chạy đỏ `python -m pytest -q tests/test_harness_kiem_dinh.py`; triển khai deterministic QA và model-assisted nhận xét tách khỏi quyết định. Mọi business claim critical/preserve list do editor xác nhận.
- [ ] Chạy lại đạt; fault injection 401/403/429/503/timeout/output partial/cancel/restart, file path escape, URL redirect, stale source, hết disk và connector chết. Không bật fallback đổi provider nếu chưa được grant.
- [ ] Đóng băng corpus riêng cho eval; chạy ít nhất 3 trial cho các ca agent không tất định đã chỉ định, lưu cả trial lỗi, không chọn bản đẹp nhất rồi bỏ lỗi.
- [ ] Ánh xạ A01–A12 audit sang HV01–HV36; thử queue 5/20 job nhưng concurrency thực tế 1, đo peak RAM/CPU/disk/duration. Không lấy kết quả workstation GPU làm bằng chứng worker CPU.

**Gate:** kiểm tra critical trong ma trận đều đạt trên đường thật tương ứng; testcase chưa chạy là NOT_RUN và chặn gate bắt buộc. Chỉ số AI judge hoặc full-decode đơn lẻ không chứng minh chất lượng edit.

### H12 — Pilot BAHA, chốt mức tối ưu và bàn giao vận hành

**Task T12.** Đầu vào: H00–H11 đủ gate, cả nhánh API bắt buộc và NLE thật; toàn bộ C01–C16 có evidence.

- [ ] Chạy 10 project ghép cặp đã chốt; giữ cùng brief/scope/source/đầu ra giữa cách cũ và harness, đổi thứ tự người làm để giảm hiệu ứng quen bài. Đo cả thời gian sửa đầu ra AI và lúc chờ provider.
- [ ] Hai editor chấm độc lập theo rubric, không cho điểm dựa tên engine; lead phân xử khác biệt critical. Lưu phản hồi thực tế và bản được duyệt; không tự tạo lời khen khách hàng.
- [ ] Kiểm tra ngưỡng ma trận: giảm median phút thao tác ít nhất 30%, chất lượng không kém baseline, không lỗi critical, chi phí không vượt grant; báo thêm cycle time/queue time/repair rate.
- [ ] Nếu mục tiêu không đạt, ghi kết quả pilot và nguyên nhân, sửa đúng task có evidence rồi chạy lại phần bị ảnh hưởng; không đổi KPI sau khi thấy số để mở gate.
- [ ] Hoàn thiện hướng dẫn nhận ca dưới 2 phút, state machine, cách resume/reconcile, recipe/version, provider rotation, project relink/native-bound, rollback, hạn chế HUMAN_REQUIRED và owner hỗ trợ.
- [ ] Diễn tập tắt harness feature flag, mở dự án bằng đường manual, giữ nguồn/timeline/native/ledger; khôi phục một version và mở lại trên máy editor.
- [ ] AGY bàn giao biên bản C01–C16, HV01–HV36, cost/license và mốc snapshot có thật; cập nhật state/checkpoint theo đúng quyền và kết quả nghiệm thu. Founder duyệt phát hành có phạm vi, không tự bật Production.

**Gate:** đủ năng lực tối thiểu, chất lượng và mức tối ưu đo được; không còn ca mandatory NOT_RUN/BLOCKED. Nếu chỉ một nhóm đạt hoặc chỉ Flow assisted hoạt động, được bàn giao mốc đó nhưng kế hoạch tổng thể chưa COMPLETE.

## 8. Ma trận phụ thuộc và trạng thái khởi tạo

| Phase | Phụ thuộc | Loại kết quả | Trạng thái hiện tại |
|---|---|---|---|
| H00 | M-P7 nghiệm thu | Baseline và quyền | CHƯA THỰC HIỆN |
| H01 | H00 | Prototype/policy được Founder duyệt | CHƯA THỰC HIỆN |
| H02 | H01 | PoC/ADR chọn engine-NLE-provider | CHƯA THỰC HIỆN |
| H03 | H02-ENGINE + mapping/schema provider đã duyệt | Contract/time/storage, offline nếu H02-PROVIDER thiếu | CHƯA THỰC HIỆN |
| H04 | H03 | Tool/run bền vững | CHƯA THỰC HIỆN |
| H05 | H04 | Evidence và media understanding | CHƯA THỰC HIỆN |
| H06 | H04 + evidence H05 khi cần | Dựng chuyên nghiệp bằng tool | CHƯA THỰC HIỆN |
| H07 | H05,H06 | Agent dựng và sửa | CHƯA THỰC HIỆN |
| H08 | H04,H05,H06 + provider grant | Flow assisted và API sửa cảnh | CHƯA THỰC HIỆN |
| H09 | H06 + connector H02 | Native roundtrip/sửa tiếp | CHƯA THỰC HIỆN |
| H10 | H07,H08,H09 | UI, templates và variants | CHƯA THỰC HIỆN |
| H11 | H10 | QC/eval/failure/security | CHƯA THỰC HIỆN |
| H12 | H00..H11 đạt đầy đủ | Pilot/operational handoff | CHƯA THỰC HIỆN |

Thiết kế này không yêu cầu triển khai đồng thời nhiều agent hoặc tác vụ nặng. Có thể đọc/nghiên cứu trước; code chỉ mở khi gate phụ thuộc tương ứng đã đạt, theo ngoại lệ offline có điều kiện tại H02. Ngoại lệ này không tạo PASS cho provider/live.

## 9. Gói tiếp quản cho AGY

Thứ tự đọc: trạng thái dự án -> plan tiền nhiệm/biên bản M-P7 -> nghiên cứu -> đặc tả -> kế hoạch này -> ma trận nghiệm thu -> command card. Đầu phiên kiểm tra hash source/plan và xác định phase đang mở, blocker, người duyệt và lệnh an toàn.

Mỗi task giao phải kèm: phạm vi file, input gate, giao diện mục 5, test names/assertions/lệnh, fixture/evidence path đã có quyền, giới hạn provider/cost, cách rollback. Agent chỉ sửa phạm vi task; phát hiện ngoài phạm vi được ghi lại và giao đúng owner.

Biên bản một gate chứa: mã task/test; source/runtime/model/engine versions; fixture hash; lời gọi/lệnh hoặc thao tác thật; stdout/stderr/exit code; request ID đã làm sạch nếu có; timeline/native/render hashes; PASS/FAIL/BLOCKED/NOT_RUN; reviewer và link artifact. Không dùng file rỗng, snapshot thư mục rỗng hoặc ảnh dashboard làm bằng chứng đầy đủ.

## 10. Tự rà soát kế hoạch

- Phủ yêu cầu: 7 luồng nghiệp vụ và C01–C16 có phase; mức agent tối thiểu không bị thay bằng task người.
- Hợp đồng: type chung T03, broker/session T04, engine mapping T02, timebase v2 và native-bound tránh hai nguồn chân lý.
- Các bẫy: mất context/interaction, duplicate generation, native finishing, linked A/V/caption, provider capabilities, tự duyệt và source injection đều có test và gate.
- Các số liệu 30%, phiên limits, peak, ASR/QA là ngưỡng đề xuất; H01 đóng băng trước thử nghiệm. Không có số PASS đo thực tế trong plan này.
- Sau builder-check thiết kế, đã làm rõ điều kiện đóng toàn bộ H12, mức tự động hóa bắt buộc, native-bound khi sửa tiếp và recovery khi interaction hết hạn. Đây là rà soát tài liệu; chưa thay thế kiểm thử runtime.
- Reviewer độc lập đọc lại đặc tả/plan/ma trận sau sửa và không còn nêu blocker buộc AGY phải đoán trong các phụ thuộc và hợp đồng được rà. Phạm vi kết luận chỉ là thiết kế; provider/engine vẫn cần PoC và bằng chứng chạy tại H02/H08/H09.
