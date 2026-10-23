# Quy ước thi công song song: sửa hệ thống hiện hữu và bổ sung bộ tạo video

Trạng thái: KẾ HOẠCH ĐỀ XUẤT, CHƯA CẤP LEASE THI CÔNG RUNTIME. Tài liệu này bổ sung `ke_hoach_trien_khai_va_checklist.md` và `dac_ta_bo_tao_video_hoan_chinh.md`; không thay thế cổng G0, phê duyệt prototype/storyboard G1 hoặc quyền của Founder. `00_bat_dau/COMMAND_CONTROL_CARD.md` đang giới hạn phiên hiện tại ở tài liệu, chưa cho phép sửa runtime. Các bảng dưới đây là phân công dự kiến, chỉ hiệu lực khi điều phối ghi task và lease cụ thể vào thẻ.

Mục tiêu là giảm và phát hiện xung đột, không bảo đảm loại bỏ mọi xung đột. Một thay đổi có thể không trùng dòng nhưng vẫn phá hợp đồng, quyền, dữ liệu hoặc hành vi; vì vậy bắt buộc tích hợp và kiểm thử lại theo baseline.

## 1. Ranh giới chung và số người làm đồng thời

- Có tối đa 4 phiên agent hoạt động, gồm 1 điều phối kiêm người tích hợp và tối đa 3 worker. Người rà soát tái sử dụng slot worker đã trả; không mở slot thứ năm. Không hiểu ba vai trò theo module là ba worker bổ sung ngoài giới hạn này.
- Một file chỉ có một owner được ghi tại một thời điểm. Không chia hai đoạn của cùng file cho hai agent. Thư mục con, fixtures, test và file sinh tự động cũng phải có owner cụ thể; không dùng quyền sở hữu rộng che lên danh sách file đã cấp cho agent khác.
- Điều phối duy nhất sửa thẻ điều phối và registry lease; worker báo heartbeat qua điều phối, không cùng ghi thẻ. Điều phối cũng là integrator độc quyền các file shared liệt kê bên dưới.
- Mọi mã nguồn, patch, đề xuất và dữ liệu thử chỉ trong `03_ban_lam_viec/`; các file trạng thái chỉ theo quyền đã quy định. Không sửa nguyên bản, quyền sống hoặc production. Bằng chứng chính thức ngoài vùng này do người có quyền ghi đúng quy định.
- Không `reset`, `clean`, `checkout`, `restore`, `revert`, force push hoặc chép đè nhằm xóa thay đổi của agent khác. Muốn bỏ thay đổi của chính task phải đối chiếu hash và chủ sở hữu hiện tại; rollback liên quan nhiều owner do integrator lập kế hoạch giữ nguyên dữ liệu người khác.

## 2. Hai lane và quyền sở hữu file shared

Mọi đường dẫn runtime trong tài liệu tương đối với `03_ban_lam_viec/`. Trước khi cấp lease, G0 phải xác nhận tên/path thực bằng khảo sát chỉ đọc; danh sách dưới đây không cho phép tự tạo bản sao gần giống file cũ.

| Lane | Công việc được giao | Vùng được ghi khi có lease | Cách phối hợp |
|---|---|---|---|
| Sửa hệ thống hiện hữu | Sửa lỗi đã xác định của script, provider, render, quyền hoặc giao diện cũ, kèm test hồi quy | Chỉ file hiện hữu được liệt kê đích danh, không giao cả ứng dụng | Worker sửa cũ không đồng thời thêm API/hành vi mới vào cùng file; phần chạm shared gửi đề xuất riêng |
| Bổ sung module mới | Planner, timing, điều phối, QC, component theo hợp đồng đã khóa | Chỉ file mới được phân công trong bảng mục 3 | Không tự sửa caller, registry hoặc shared để nối module; gửi patch tích hợp |
| Tích hợp dùng chung | Schema/hợp đồng dùng chung, đăng ký route, dispatch worker, trang route, cấu hình và migration | Chỉ integrator, mỗi lần một gói tích hợp | Xếp hàng cả sửa cũ và tính năng mới; test hồi quy cũ trước khi công bố baseline mới |

Integrator độc quyền các file shared sau, kể cả khi phần sửa chỉ vài dòng:

| Nhóm | File/vùng shared cần khóa |
|---|---|
| Dữ liệu và khởi động | `sin_content_api/src/models/entities.py`, `sin_content_api/src/main.py`, `sin_content_api/src/migrations/runner.py`, mọi file migration mới/cũ và registry migration |
| Hợp đồng và cấu hình | Hợp đồng dùng chung hiện hữu, `sin_content_api/src/config.py`, cấu hình môi trường/build/package/lockfile, `tests/conftest.py` và fixture chung; danh sách thực được G0 xác nhận |
| API lớn và liên kết module | Router hiện hữu, đặc biệt `sin_content_api/src/modules/media_studio/router.py`; các khai báo action/quyền và hook tenancy; không thay cơ chế RBAC chỉ để tích hợp |
| Worker | `sin_content_workers/worker.py`, registry/action map và cấu hình khởi động worker |
| Trang và API client | `sin_creator_os/src/app/(main)/video-studio/page.tsx`, `sin_creator_os/src/app/(main)/video-studio/[projectId]/page.tsx`, `sin_creator_os/src/lib/api/media-studio-api.ts` và client/type registry dùng chung |
| Cầu nối cũ | `sin_content_api/src/modules/scripts/script_service.py`, `timing_calculator.py`, `claim_checker.py`; `sin_content_api/src/modules/media_studio/video_provider.py`, `job_engine.py`, `video_processor.py`; `sin_content_api/src/modules/dieu_phoi_dung/bo_render.py`, `hop_dong.py` |

Các cầu nối cũ được coi là shared vì cả lane sửa hiện hữu và lane mới cần chúng. Worker có thể khảo sát và gửi patch, không được ghi trực tiếp. File phát hiện mới có nhiều consumer phải đưa vào registry shared trước khi sửa; không tự suy ra quyền từ việc file chưa có trong bảng.

## 3. Danh sách sở hữu module mới

Các nhãn owner là vai trò; điều phối phải điền agent/task ID thực trước mỗi wave. Một worker có thể nhận tuần tự nhiều vai trò, không chạy tất cả các vai trò cùng lúc. Viết `__init__.py` là ngoại lệ tên bắt buộc của Python; giữ nguyên tên file hiện hữu để không phá import.

| Owner dự kiến | File mới sở hữu độc quyền | Test riêng sở hữu |
|---|---|---|
| Integrator | `sin_content_api/src/modules/tao_video_noi_dung/hop_dong.py`, `__init__.py`, `bo_dinh_tuyen.py`, `kho_phien_ban.py`, `cong_harness.py` | `sin_content_api/tests/kiem_thu_hop_dong_tao_video.py`, `kiem_thu_luu_phien_tao_video.py`, `kiem_thu_cong_harness.py` |
| Worker nội dung | `sin_content_api/src/modules/tao_video_noi_dung/lap_ke_hoach.py`, `phong_cach_kenh.py` | `sin_content_api/tests/kiem_thu_phan_canh_noi_dung.py`, `kiem_thu_claim_cong_nghe.py`, `kiem_thu_phong_cach_kenh.py` |
| Worker giọng và timing | `sin_content_api/src/modules/tao_video_noi_dung/tao_giong_doc.py`, `can_thoi_gian.py` | `sin_content_api/tests/kiem_thu_giong_doc_va_can_thoi_gian.py` |
| Worker điều phối | `sin_content_api/src/modules/tao_video_noi_dung/danh_muc_nang_luc.py`, `dieu_phoi.py`; `sin_content_workers/tac_vu_tao_video.py` | `sin_content_api/tests/kiem_thu_dieu_phoi_san_xuat.py` |
| Worker lắp ráp | `sin_content_api/src/modules/tao_video_noi_dung/lap_timeline.py`, `xuat_goi.py` | `sin_content_api/tests/kiem_thu_lap_rap_video_120_giay.py` |
| Worker QC | `sin_content_api/src/modules/tao_video_noi_dung/kiem_dinh.py` | `sin_content_api/tests/kiem_thu_qc_duyet_va_sua_canh.py` |
| Worker giao diện | `sin_creator_os/src/app/(main)/video-studio/[projectId]/_components/nhap_noi_dung.tsx`, `duyet_phan_canh.tsx`, `tien_do_san_xuat.tsx`, `duyet_thanh_pham.tsx`; `sin_creator_os/src/lib/api/tao_video_noi_dung.ts` | Test component hoặc E2E mới theo đường dẫn được thẻ điều phối cấp riêng trước khi tạo |

Các đường dẫn rút gọn trong cùng ô có cùng thư mục với file đầy đủ đầu tiên của nhóm. Client API mới do worker giao diện viết theo hợp đồng đã khóa; việc nối vào trang route/client cũ chỉ integrator thực hiện. Worker không thêm dependency, sửa exports hoặc fixture chung để làm test của mình chạy; phải gửi yêu cầu tích hợp. Nếu cần chuyển owner giữa wave, bàn giao hash và đóng lease cũ trước, không có thời điểm hai owner cùng hiệu lực.

## 4. Khóa hợp đồng trước khi tách việc

1. Hoàn tất G0 liên quan, xác nhận dữ liệu/đường phục hồi và G1 được Founder duyệt trước backend nặng. Lane sửa lỗi cũ chỉ làm đúng nhiệm vụ đã được cấp; không dùng lane đó để đi vòng cổng G1.
2. Integrator chốt hợp đồng nền: request/response, mã lỗi, trạng thái, revision/CAS, idempotency fingerprint, scene/shot IDs, frame/timebase, capability receipt, quyền/resource scope, approval hash, mô hình plan/run/step và mapping timeline. Bắt buộc gồm `KhoaPhongCach`, `DanhGiaLLM`, `LenhTaoShot`, `BienNhanHarness` và chữ ký trong `hop_dong_harness_llm_truoc_flow.md`; không để mỗi lane tạo type riêng.
3. Ghi một manifest hợp đồng có phiên bản, ngày khóa, hash SHA-256 từng file/schema, baseline và fixture mẫu hợp lệ/không hợp lệ tại `ke_hoach_tao_video_tu_noi_dung/dieu_phoi_song_song/hop_dong_khoa_<phien_ban>.md`. Tên phiên bản dùng chữ/số không dấu snake_case. Chỉ integrator ghi manifest này.
4. Mỗi task nhận chính xác phiên bản/hashes, chữ ký hàm và mẫu đã khóa. Kiểm schema/contract qua test trước khi phát lease. Mock UI phải mang nhãn mẫu; mock không được tính là bằng chứng tích hợp thật.
5. Thay hợp đồng phải có đề xuất tương thích, consumer bị ảnh hưởng, test và cách chuyển đổi. Integrator dừng các lease bị ảnh hưởng, phát phiên bản/hash mới và yêu cầu owner rebase/đọc lại; không sửa âm thầm dưới cùng phiên bản. Task chưa cập nhật không được tích hợp.

## 5. Dependency waves và điều kiện mở việc

| Wave | Công việc có thể đồng thời | Điều kiện ra wave |
|---|---|---|
| W0: khảo sát và thiết kế | Khảo sát hiện hữu, baseline chỉ đọc và prototype theo phạm vi đã cấp | G0 được xác minh, G1 duyệt thật; xác nhận repo, shared map, môi trường thử và owner |
| W1: nền hợp đồng | Integrator làm G2; tối đa 3 worker khảo sát/test hồi quy cũ hoặc chuẩn bị fixture/proposal riêng, chưa dựa vào hợp đồng chưa khóa để triển khai backend nặng | Contract phiên bản khóa; CAS/scope/idempotency/lease và migration trên bản sao có bằng chứng |
| W2: nhánh độc lập | Tối đa 3 worker chia giữa sửa cũ, nội dung G3, timing G4, UI component theo mock hợp đồng; điều phối chọn 3 task cụ thể, không phát cả 4 | Test riêng pass; proposal shared sẵn sàng; G4 live vẫn phụ thuộc lời/storyboard G3 được duyệt |
| W3: điều phối và dựng | G5, lắp ráp G6 và UI có thể viết/test cô lập trên contract đã khóa; G5 live đợi G4, render live đợi asset/voice thật | Hàng đợi shared đã tích hợp, không ghi nhận mock là live; provider/render có lease nặng riêng |
| W4: QC và tích hợp UI | G7, G8 cùng hồi quy lane sửa cũ trên baseline tích hợp; reviewer dùng lại một slot worker | Kiểm full flow, approval/revision, deep link và quyền; không còn xung đột hash/contract |
| W5: nghiệm thu | G9 và kiểm hồi quy có thứ tự; tác vụ nặng tuần tự | Bằng chứng đúng ma trận, lỗi mở có quyết định, Founder duyệt pilot/rollout |

Wave chỉ cho phép song song phần không phụ thuộc nhau; không hạ điều kiện G2–G9 của kế hoạch chính. Thiếu đầu vào thì task chuyển `cho_phu_thuoc`, không tự dựng dữ liệu hoặc bỏ kiểm tra để tiếp tục.

## 6. Thẻ điều phối, lease và chống nguồn cũ

Mỗi dòng task trong `00_bat_dau/COMMAND_CONTROL_CARD.md` khi thi công phải có: `task_id` duy nhất; lane/wave/gate; agent owner; danh sách file được ghi; danh sách shared chỉ đọc; baseline repo/commit nếu có và manifest SHA-256; phiên bản hợp đồng; dependency task IDs; tên DB/tmp/profile/cổng; lease ID; thời điểm cấp/hết hạn theo múi giờ rõ ràng; heartbeat gần nhất; trạng thái; bằng chứng/proposal; người nhận bàn giao.

- Trạng thái task: `du_kien`, `san_sang`, `dang_lam`, `cho_phu_thuoc`, `cho_tich_hop`, `dang_kiem_tra`, `hoan_tat`, `bi_chan`, `tam_dung`. `hoan_tat` chỉ sau integrator xác nhận kiểm thử và hash tích hợp, không theo tự báo worker.
- Lease ghi file đề xuất TTL 30 phút, heartbeat mỗi tối đa 5 phút. Điều phối gia hạn khi task vẫn hoạt động và không trùng file. Thời gian có thể đổi trước wave nhưng phải ghi cụ thể; không mặc định lease vô hạn.
- Mất heartbeat hoặc hết TTL: dừng cấp việc phụ thuộc và không được tiếp tục ghi. Hết hạn không đồng nghĩa tự động chuyển file cho người khác: điều phối xác nhận agent/process cũ đã dừng, đối chiếu diff/hashes, thu hồi lease rồi mới cấp owner mới. Không xác minh được thì giữ `bi_chan`.
- Trước khi đọc để sửa, ngay trước ghi và trước bàn giao, worker so hash với baseline/manifest được cấp. Hash khác hoặc có dấu hiệu người khác ghi thì dừng, giữ đề xuất riêng và báo điều phối; không dùng bản đệm cũ đè file mới.
- Với bản làm việc cùng filesystem không có cơ chế compare-and-swap ở file, kiểm hash không thay thế lease độc quyền. Integrator phải giữ khóa tích hợp trong suốt kiểm hash, áp patch và ghi kết quả.

## 7. Đề xuất shared và hàng đợi tích hợp

Worker chỉ ghi gói bàn giao trong phạm vi riêng `ke_hoach_tao_video_tu_noi_dung/dieu_phoi_song_song/de_xuat/<task_id>/`, sau khi được thẻ cấp đường dẫn này. Gói gồm `de_xuat.md`, `thay_doi.patch` nếu có và `ket_qua_kiem_tra.md`; các tên là đề xuất cho tương lai, phiên kế hoạch chưa tạo gói runtime.

Nội dung bàn giao tối thiểu: file/hunk đích, lý do, hash trước, hợp đồng phiên bản, diff dự kiến, consumer/fixture/config bị ảnh hưởng, command/cwd/exit code đã kiểm, điều chưa kiểm và cách rollback giữ thay đổi khác. Không chép secret hoặc DB/media vào patch.

Integrator xử lý tuần tự:

1. Xếp thứ tự theo phụ thuộc: sửa blocker hiện hữu và bảo toàn baseline trước; thay schema/hợp đồng trước consumer; đăng ký router/worker/page sau module. Không chọn đơn thuần ai gửi trước.
2. Giữ lease shared; so hash đích với `hash trước`. Nếu khác, trả proposal cho owner cập nhật/rebase theo baseline mới; không áp cưỡng bức hoặc auto chọn một phía khi conflict.
3. Rà quyền, dữ liệu, contract và tính tương thích; áp từng proposal, chạy test liên quan cùng test hồi quy cũ. Nếu fail, giữ trạng thái `bi_chan`/`cho_tich_hop`, không công bố baseline pass.
4. Ghi hash sau, kết quả test, proposal đã tích hợp và baseline mới. Task downstream đọc lại baseline, rebase nếu dùng Git hoặc cập nhật snapshot/diff có kiểm soát nếu không Git, rồi chạy lại test bị ảnh hưởng.
5. Đóng lease và task chỉ khi output được kiểm; reviewer nhận diff cuối trên baseline mới bằng slot worker đã rảnh. Không coi test của worker trên baseline cũ là nghiệm thu tích hợp.

## 8. Git/worktree và phương án khi chưa có repository

Khảo sát trước ghi nhận thư mục dự án gốc chưa phải Git repository; chưa kết luận các thư mục con. G0 phải kiểm `git rev-parse --show-toplevel`, `git status --short`, remote và repository chứa đúng file cần sửa. Không tự `git init`, dựng commit/branch giả hoặc dùng worktree trước xác minh.

Nếu có repo phù hợp và được cấp quyền: mỗi task dùng nhánh/worktree riêng dưới vùng ghi đã cho phép, ghi repo/commit nền trong thẻ. Worktree chỉ cách ly mã nguồn; DB, môi trường, profile và tiến trình vẫn phải tách. Integrator nhận commit/patch, rebase theo baseline mới và kiểm lại; không merge đè thay đổi chưa được ghi nhận. Nếu có nhiều repo con, ghi dependency commit từng repo và tích hợp đúng thứ tự, không giả định một commit nguyên tử cho toàn dự án.

Nếu chưa có repo: dùng exclusive write scope theo file và manifest hash, không cần lập repo để bắt đầu các việc đã được duyệt. Worker chỉ sửa file riêng; shared đi qua proposal. Trước thay đổi rủi ro, người có quyền tạo bản phục hồi theo quy định; bản sao thử nằm trong vùng `03_ban_lam_viec/` được cấp, snapshot chính thức do đúng vai trò ghi. Không dùng thao tác chép cả cây để cập nhật baseline vì có thể ghi đè file người khác.

## 9. Cách ly kiểm thử và tài nguyên nặng

- Mỗi task có DB thử riêng, tên DB/schema hoặc file SQLite riêng; `SIN_DUNG_DB_PATH`, kho asset, thư mục tạm/output/cache, port API/UI và browser profile riêng được ghi trong thẻ. Giá trị thật cần được xác nhận không trỏ DB/storage vận hành hoặc môi trường task khác trước chạy lệnh có ghi.
- Không chạy `drop`, reset schema, truncate, migration hoặc fixture dọn kho trên DB chung. Test dọn dữ liệu chỉ xóa đúng namespace/path của task sau khi kiểm đường dẫn tuyệt đối thuộc vùng thử được cấp. PostgreSQL dùng database/schema và tài khoản thử được cách ly; không chạy migration production. Đọc guardrails RBAC/Postgres trước thay schema/quyền.
- Test suite dùng fixture chung hoặc có khả năng reset DB phải được integrator khảo sát và chạy tuần tự đến khi chứng minh cách ly. Mỗi build frontend có output/cache riêng hoặc chạy tuần tự; không cho hai tiến trình cùng ghi `.next`.
- Không dùng chung browser profile Flow hoặc cookie/session giữa agent; không xuất profile vào bằng chứng. Không đổi tài khoản, tự tải provider hoặc tăng phí ngoài nhiệm vụ được cấp.
- Tác vụ Flow và render/AI nặng dùng chung một hàng đợi tài nguyên toàn máy: tổng tối đa 1 tác vụ nặng đang chạy, kể cả lane sửa cũ, kiểm thử và tiến trình ngoài worker mới. Không diễn giải là mỗi agent/process được 1 tác vụ. Nếu không kiểm kê/điều khiển được tiến trình khác thì chưa chạy task nặng.
- Integrator là quản tài nguyên: giữ registry task/process/host, owner, loại tác vụ, thời điểm cấp, TTL/heartbeat và trạng thái. Worker phải xin lease nặng riêng trước khi gọi. Khi triển khai khóa runtime, dùng cơ chế liên tiến trình/DB đã được kiểm thử; `threading.Lock` riêng process không đủ.
- Lease nặng hết hạn không tự mở slot: xác nhận process/provider operation cũ đã kết thúc hoặc đối soát receipt trước cấp lại. Timeout chưa biết kết quả phải chờ đối soát, không gọi lại mù. Tài nguyên Flow/render vẫn chỉ một slot khi tăng số worker.

## 10. Checklist nghiệm thu khả năng làm song song

Các ô dưới đây là điều kiện tương lai, chưa được đánh dấu trong phiên lập kế hoạch.

- [ ] Lệnh thi công hợp lệ, G0/G1 đạt theo phạm vi; command card có task IDs, owner, lease và tối đa 4 phiên gồm điều phối.
- [ ] Mỗi file có đúng một owner; toàn bộ shared đã khoanh và chỉ integrator ghi; fixture/export/config mới có owner trước tạo.
- [ ] Hợp đồng khóa có version/hash/mẫu và test; mọi task khai báo cùng phiên bản hoặc có chuyển đổi được duyệt.
- [ ] Tối thiểu một task sửa cũ và một task module mới chạy trong vùng không trùng, bàn giao hash/proposal và tích hợp tuần tự trên baseline mới.
- [ ] Thử tình huống hash cũ, lease hết hạn và proposal chạm cùng file: task bị dừng, không ghi đè, không tự chuyển quyền hoặc tự reset.
- [ ] DB/tmp/output/profile/ports được tách; chứng minh fixture/migration không sửa DB/chỗ lưu chung, dữ liệu/ID cũ không mất.
- [ ] Thử hai bên yêu cầu Flow/render: chỉ một bên có lease nặng; process chết/timeout phải đối soát trước cấp lại, không tăng phí trùng.
- [ ] Integration queue có hash trước/sau, baseline, test/exit code; rebase hoặc cập nhật baseline xong mới tiếp tục dependency wave.
- [ ] Test module mới và hồi quy phần cũ bị ảnh hưởng pass trên chính source hash cuối; reviewer dùng slot rảnh, không mở vượt giới hạn.
- [ ] Các lỗi mở, phần mock/chưa kiểm/live chưa chạy và thay đổi hợp đồng đều được ghi rõ; evidence chính thức do người có quyền lưu đúng nơi trước đóng gate.

Không được báo “thi công song song an toàn đã nghiệm thu” chỉ vì có tài liệu này. Điều kiện đạt là có bằng chứng diễn tập cơ chế khóa/cách ly và kiểm thử trên bản tích hợp thực; các xung đột hành vi còn phát sinh phải được xử lý theo hàng đợi, không che bằng kết quả test cũ.
