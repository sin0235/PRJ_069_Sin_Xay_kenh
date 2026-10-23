# Ma trận nghiệm thu harness dựng video BAHA

Ngày 23/10/2026. Đi cùng [đặc tả](dac_ta_harness_dung_video_baha.md) và [plan H00–H12](ke_hoach_harness_dung_video_baha_2026_10_23.md). **Tất cả ca dưới đây CHƯA CHẠY.** Tên fixture/test là yêu cầu cho phiên triển khai, không phải dữ liệu hoặc kết quả đã có.

## 1. Quy tắc nghiệm thu

- Trạng thái: PASS, FAIL, BLOCKED, NOT_RUN; thiếu dữ liệu không được đổi thành PASS. Test skip không tính vào số đạt của ca bắt buộc.
- Mức bằng chứng ghi riêng: CODE_READ/DOC_VERIFIED, LOCAL_TESTED, LIVE_TESTED, HUMAN_VERIFIED. Mock chỉ kiểm tra giao thức/lỗi, không chứng minh AI/Flow/NLE hoạt động.
- Mỗi ca có fixture SHA, brief/policy/engine/model version, thao tác/lệnh, stdout/stderr/exit code nếu có, kết quả đo, source map và artifact hashes. Evidence tại vị trí AGY/Owner đã phân xử ở H00; không tự ghi 08/90 khi chưa có quyền.
- Ngưỡng là đề xuất thiết kế; Founder/lead editor đóng băng ở H01 trước các phép đo. Đổi ngưỡng phải có version mới, lý do và chạy lại; không sửa ngưỡng để hợp thức hóa trial đã thất bại.
- PASS kỹ thuật không tự duyệt sản phẩm. Trường hợp sửa nội dung cần editor xác nhận sự thật/preserve list. Chuỗi agent “đã xong”, HTTP 200, provider success token, file tồn tại hay ảnh screenshot riêng lẻ đều chưa đủ.
- HV01–HV36 đều thuộc nghiệm thu; các chức năng first/last/reference/continuation thêm trong HV22 được tách nhỏ theo capability và phạm vi H01. Không áp điều kiện không liên quan một cách máy móc, ví dụ loudness với video được brief yêu cầu hoàn toàn không âm thanh.

## 2. Bộ fixture phải tạo/chuẩn bị khi triển khai

| Mã | Nội dung và mục đích | Nhãn chuẩn cần có |
|---|---|---|
| F01 | Footage tiếng Việt có lời khoảng 3 phút, nhiều tên/số/giá sản phẩm, nhạc rời; brief bản 45 giây | Transcript người duyệt, word ranges một mẫu tối thiểu 200 token, tên/số quan trọng, điểm cắt được editor nhận |
| F02 | Footage sản phẩm/hành động không lời, có chi tiết chỉ xuất hiện khoảng 200 ms, có ảnh sản phẩm/logo | Mốc visual, khoảng hợp lệ, đối tượng bắt buộc, không transcript speech |
| F03 | 5 video nguồn, 3 B-roll, ít nhất 2 file âm thanh rời, audio nguồn, ảnh/logo; ít nhất 3 video layer và 4 audio layer cùng có nội dung trong bài thử | Timeline mẫu, layer order, transitions/handles, J/L cuts, vùng cấm chữ, bảng âm thanh/độ dài |
| F04 | 24000/1001, 25, 30000/1001, 30 FPS; VFR; rotation; nguồn Log/HDR; 2 camera và audio rời, phần sync dài 10 phút | PTS/marker/clap đầu-cuối, source proxy map, color profile, keyframes/tracking/mask chuẩn |
| F05 | Ảnh và video thật được phép gửi cloud; yêu cầu sửa ảnh, ảnh sang clip và sửa hình một cảnh trong timeline | Preserve list: nhận dạng sản phẩm/chữ/brand/đối thoại, request/reference roles, vị trí thay clip, audio phải giữ, tiêu chí editor duyệt |
| F06 | Tệp hỏng/MIME giả, thiếu font/media/LUT, path/URL nguy hiểm; OCR/transcript chứa lệnh độc; grant hết hạn; 2 workspace cùng tên file | Kết quả từ chối mong đợi; snapshot trước; trace không chứa secret; lỗi API/queue/connector được inject có kiểm soát |

Một phần F03/F04/F06 được tạo tổng hợp để kiểm tra tất định; chỉ gắn nhãn SYNTHETIC. Nghiệm thu khả năng provider và chất lượng nghề dựng phải dùng thêm nguồn BAHA được cấp quyền. Không tự trích âm thanh/video của khách hàng/reference chưa rõ quyền để làm fixture.

10 project pilot bao gồm ít nhất 2 project cho mỗi nhóm F01, F02, ảnh, đa camera và sửa cảnh F05; không dùng 10 biến thể của cùng một clip như 10 project độc lập.

## 3. Ngưỡng định lượng và cách đo

| Chỉ số | Cách xác định | Ngưỡng đề xuất |
|---|---|---|
| Frame/time cut | So PTS/source map và nhãn frame, đầu ra CFR theo profile | Sai lệch không quá 1 frame đầu ra ở cut boundary; không tích lũy drift theo số clip |
| Audio sync | Nhãn clap/chuyển động-nghe đầu và cuối nguồn dài | Không quá 1 frame tại marker fixture tổng hợp; footage dài thật không quá 2 frame sau conform, hoặc yêu cầu editor xử lý trước PASS |
| Độ dài timeline | Dựa frame count/profile, không byte-size | Render đúng số frame dự kiến; duration container chênh tối đa 1 frame |
| ASR tiếng Việt | NFC, lowercase, bỏ dấu câu, giữ dấu tiếng Việt; token phân cách khoảng trắng; đo `(S+D+I)/N` trên bộ transcript cố định | Tỷ lệ lỗi token trung vị không quá 10%; báo rõ đây là phép đo token âm tiết, không so với WER khác tokenizer |
| Word timestamp | So với 200 token gán nhãn ở F01 | p95 sai lệch không quá 200 ms; timestamp ASR không được xem là frame-accurate |
| Caption thành phẩm | Người kiểm tra danh sách từ/số/giá quan trọng và mốc mẫu | 100% từ quan trọng đúng sau hiệu chỉnh; không overflow; tối đa 2 dòng theo template đã duyệt, vị trí đúng profile |
| Loudness/peak | Đo lại file render cuối có chương trình âm thanh; ghi input/output stats | TikTok -14 LUFS ±1; true peak không quá -1,5 dBTP khi ngưỡng đã duyệt |
| Mask/redaction | So ROI ground truth qua mọi frame cần bảo vệ trong fixture | ROI nằm trong vùng che đã duyệt ở mọi frame; không dùng sampling thưa để chứng minh không rò nội dung |
| Đúng phạm vi sửa | Diff snapshot, source maps và preserve list | Không đổi thuộc tính/nguồn ngoài patch được duyệt; ripple chỉ thay đổi các liên kết/thời điểm được chỉ rõ |
| QC tự động critical | Ca hỏng có nhãn F06 | Phát hiện 100% ca critical trong corpus cố định; false positive phải được báo, không xóa kiểm tra |
| Tài nguyên | CPU/RAM/disk/job wall time trên máy chọn ở H00 | Trong ngân sách hạ tầng đã duyệt; heavy active = 1; không có cam kết realtime khi chưa đo |
| Chất lượng edit | Hai editor chấm 5 trục 1–5; lead phân xử bất đồng critical | Mỗi project điểm tổng hợp ít nhất 4/5, không trục nào dưới 3; không lỗi critical; median không thấp hơn baseline |
| Tiết kiệm thao tác | Với mỗi project, đo phút thao tác đến cùng định nghĩa hoàn thành; so median ghép cặp | `median((phut_cu-phut_moi)/phut_cu)` ít nhất 30%; báo cả từng cặp, không lấy tỷ lệ từ project có baseline bằng 0 |

Không áp một ngưỡng bitrate/4K detail/độ chính xác semantic chưa được đo. Với color/finishing, so metadata/reference và editor trên màn hình phù hợp; không lấy histogram hoặc model confidence làm chuẩn màu duy nhất. Tính đủ chi phí request thất bại, lần sửa lại, credits, render/storage và giờ editor.

## 4. Các ca nghiệm thu

| Ca | Nội dung và fixture | Assertion/kết quả phải quan sát | Phase chịu trách nhiệm và bằng chứng |
|---|---|---|---|
| HV01 | Nền tảng trước harness | Upload ảnh/video, timeline save/reload, preview/render thật và tenant boundary đạt M-P7; đối chiếu lại source | H00; biên bản M-P7, hash và kết quả kiểm tra mới |
| HV02 | Kiểm kê/khả năng engine | Ghim commit/license/runtime; renderer BAHA/FableCut và NLE có bảng op/parameter; không tự suy ra tính năng từ README | H02-ENGINE; logs PoC, project và render |
| HV03 | Compatibility/timebase F04 | v1 cũ không bị sửa; v2 rational và VFR PTS mapping chính xác theo ngưỡng; invalid times bị từ chối | H03; `test_harness_hop_dong.py`, DB trước/sau, source map |
| HV04 | Input sai F06 | Field lạ/NaN/bool-int/OOB/asset ID sai/clip lock/effect chưa hỗ trợ bị reject, version/hash không đổi | H03/H04; response lỗi và snapshot |
| HV05 | Draft/atomic commit | Agent sửa draft không đổi live; lỗi op thứ hai hủy toàn batch; commit chỉ áp một version đúng base/hash/approval | H04; journal, draft/live versions, race test |
| HV06 | Idempotency/cancel/restart | Crash ở các boundary không sinh asset/fee/op lặp; cùng key khác payload conflict; output đến muộn không tự ghép; cancel ghi cost chưa rõ | H04/H08; fault trace và ledger trước/sau |
| HV07 | ASR F01 | Transcript/word IDs/ranges/provenance có thật; đạt ngưỡng token/timestamp; confidence thiếu không bịa; caption sửa tên/số đúng | H05; raw response lưu có quyền, nhãn người, báo cáo đo |
| HV08 | Hiểu hình F02 | Chọn cảnh theo visual evidence, không bịa lời; sự kiện 200 ms cần mẫu bổ sung; bỏ sót thì UNKNOWN/review | H05; sampled frames có PTS và nhãn editor |
| HV09 | Nguồn và cache | SHA nguồn đổi làm invalid evidence; cache theo workspace/model/config; source/proxy map có version | H05; cache keys và test không rò workspace |
| HV10 | Dựng thời gian F03 | Split/trim/insert/overwrite/ripple/slip, marker/gap/lock đúng ý đồ; linked captions/audio cập nhật nguyên tử | H06A; timeline diff, cut frames, rendered sequence |
| HV11 | Nhiều lớp F03 | Tối thiểu 3 video/4 audio layer có nội dung; order/alpha/PiP/B-roll/transition và handle chính xác | H06A; project mở lại, multi-track screenshot và frame/audio evidence |
| HV12 | Audio F01/F03 | Sync, J/L, gain/EQ/fades/duck theo voice; không cắt thoại hoặc âm thanh vô ý; loudness/peak đầu ra đạt | H06B; đo âm thanh, stems và người nghe duyệt |
| HV13 | Caption/typography | Tiếng Việt/font/glossary, word/câu, export SRT/ASS và safe zone; retime/ripple không lệch; thiếu font phải báo | H06B; subtitle files, frame captures và word-source map |
| HV14 | Transform/color F04 | Crop/reframe/keyframe/easing giữ bố cục; exposure/WB/saturation/LUT có quyền, color space/range đúng; không gọi resize/blur là AI outpaint | H06C; parameter readback, frames và color metadata |
| HV15 | Mask/composite/tracking F04 | Agent áp mask/keying/quỹ đạo có chứng cứ; che ROI mọi frame; không mất effect khi render | H06C; ROI coverage report, effect schema và video |
| HV16 | Retime/multicam F04 | Speed/freeze/reverse/source mapping và chọn góc 2 camera; audio rời không drift; captions theo policy | H06D; clap markers, source map và project |
| HV17 | Rough cut F01/F02/F03 | Agent tự dựng timeline theo brief qua tools; mọi đoạn chọn có nguồn/lý do; đúng phần bắt buộc và độ dài | H07; plan -> op journal -> draft/render -> editor score |
| HV18 | Feedback có phạm vi | “Sửa clip X/tại frame Y, giữ phần khác” chỉ sửa đúng version/range; mơ hồ thì hỏi; comment bản cũ không sửa nhầm bản mới | H07/H10; feedback/diff/readback, output so trước/sau |
| HV19 | Stop/context/resume | Run chạm quota/no-progress dừng có checkpoint; phiên mới tiếp tục draft cũ, không reset counters hoặc báo xong sớm | H04/H07; event log, counters và restart trace |
| HV20 | Đường sửa ảnh và ảnh sang video F05 | Agent qua API chính thức tạo derivative đúng nguồn/reference/preserve; ảnh/clip tải và decode được; metadata/cost thật | H08-API; 3 trial mỗi đường, request metadata, output SHA và editor review |
| HV21 | Sửa video upload F05 | Agent gửi đúng đoạn nguồn/route, nhận bản sửa, QC, thay đúng clip trong draft, giữ audio/placement ngoài scope | H08-API; 3 trial, before/after, journal và full render |
| HV22 | Flow UI, frames/reference/continuation | Assisted sửa ảnh/video có operator và receipt; first/last/reference/extend chỉ PASS theo đúng route/model đã xác minh; extension không ghép trùng source | H08-ASSISTED và ca con capability H08; ảnh UI đã làm sạch, đơn/file nhập/nhận xét; unsupported ghi rõ |
| HV23 | Kết quả provider bất thường | Wrong request/workspace/hash, hỏng file, sai duration, unexpected dialogue/product/identity không tự thay timeline; không dùng clip cũ/mẫu để bù | H08; negative tests, preserve review và snapshot không đổi |
| HV24 | Lỗi API/session/cost | 401/403 không retry mù; 429/503 theo policy; timeout không rõ accept/bill đi reconcile; session expiry dùng asset cục bộ có grant; không giả giữ context | H04/H08; job/interaction chain, logs đã làm sạch và cost ledger |
| HV25 | Bàn giao mở lại F03/F04 | Native/format project giữ thứ tự/nguồn/track; máy editor khác relink và sửa/render được; effect loss/bake có người duyệt | H09; bundle, native project, second-machine evidence và loss report |
| HV26 | Vòng native -> agent sửa tiếp | Sau native grade/mask, NATIVE_BOUND render đúng native hash; agent sửa op được hỗ trợ mà giữ finishing; unsupported reject; fork/bake có duyệt | H09; 4 bước roundtrip, native checkpoints và render so sánh |
| HV27 | UI người/agent | Luồng H01 chạy trên API thật, diff/review/cancel/resume/reload/conflict; keyboard/labels; không sample timeline hoặc giả progress | H10; E2E assertions, screenshot các trạng thái và API records |
| HV28 | Template và variants | Áp brand kit/version, caption/style/preset; tạo 9:16/16:9/1:1 có QC riêng; không generation lại nếu chỉ đổi packaging | H10; version/source maps, provider call count, bản xuất |
| HV29 | Full decode/QA F06 | Success token/file rỗng/corrupt/thiếu đuôi không PASS; output specs và timeline hash khớp; intentional black/silence có lý do, ngoài ý đồ bị phát hiện | H11; ffprobe/full-decode/audio/frames và per-check report |
| HV30 | Quyền và dữ liệu F06 | Hai workspace cùng tên file không đọc/ghi/list/cache chéo; revoke grant trước job bị chặn; path/symlink/UNC/URL redirect không thoát phạm vi | H04/H11; server/connector denied traces và snapshot |
| HV31 | Injection/secret F06 | Lời thoại/OCR/reference/metadata không đổi system/tool/grant, không tải skill/model, không gửi media trái policy; không secret trong logs/gói giao | H05/H07/H11; outbound/tool traces và scan artifact đã làm sạch |
| HV32 | Duyệt/khôi phục | Người có quyền duyệt đúng hash/version; agent không tự APPROVED; sửa sau duyệt làm duyệt cũ hết hiệu lực; restore tạo version mới bằng nội dung version cũ | H04/H10/H11; approval records, versions và native rollback |
| HV33 | Resource/throughput | Queue 5 và 20 job, heavy active tối đa 1, resume sau worker chết; không vượt budget RAM/disk/duration H00; đo CPU worker riêng NLE | H11; process metrics, queue logs, tài nguyên và timings |
| HV34 | Chất lượng agent nhiều trial | Với HV17/HV18/HV20/HV21 chạy tối thiểu 3 trial, ghi cả thất bại và repair; output sau repair phải đạt ngưỡng trong grant | H07/H08/H11; corpus frozen, trial IDs và rubric hai editor |
| HV35 | Tối ưu BAHA | 10 project ghép cặp đạt mục tiêu giảm thao tác, không giảm chất lượng, không lỗi critical, chi phí trong grant; báo thêm cycle time/repair và điểm từng job | H12; baseline/raw time sheet, cost, blind review và kết quả thống kê |
| HV36 | Vận hành/rollback/tiếp quản | Người nhận ca đọc gói và xác định đúng bước kế tiếp trong dưới 2 phút; tắt harness vẫn mở manual/native; restore không mất source/timeline/ledger | H12; diễn tập, owner, hướng dẫn, snapshot thật và xác nhận Founder |

## 5. Liên kết năng lực và phạm vi agent

| Năng lực đặc tả | Ca chứng minh | Điều không được dùng để thay thế |
|---|---|---|
| C01 | HV01/HV09/HV25/HV30 | Chỉ thấy file trong media bin |
| C02 | HV07/HV08/HV09 | Transcript hoặc timecode bịa, regex thay hiểu video |
| C03 | HV17/HV34 | Agent chỉ trả lời một kịch bản chữ |
| C04 | HV03/HV04/HV05/HV10 | JSON thao tác chưa được áp/readback |
| C05 | HV11 | Nhiều track trống hoặc video đã flatten |
| C06 | HV07/HV13 | Caption chỉ ở preview, không đi vào output |
| C07 | HV12 | Metadata tự ghi -14 LUFS |
| C08 | HV14 | Preset crop tĩnh thay mọi yêu cầu reframe |
| C09 | HV14/HV26 | Label màu hoặc LUT không áp khi render |
| C10 | HV15/HV26 | Một frame đã che thay coverage cả đoạn |
| C11 | HV16 | Đổi playbackRate preview, không render/source map |
| C12 | HV20/HV21/HV22/HV23/HV24 | Assisted/mock thay agent tự sửa cảnh API |
| C13 | HV18/HV32 | Comment không neo version hoặc full rewrite |
| C14 | HV28 | Nhân bản file xuất không có timeline/version |
| C15 | HV25/HV26/HV29 | MP4/XML chưa mở thay project editable |
| C16 | HV06/HV19/HV24/HV30/HV31/HV32/HV33/HV36 | Worker RAM/HTTP 200/self-report |

Mỗi nhóm phải có đủ tool tự thực thi mức tối thiểu tại đặc tả mục 4. Native grading/roto phức tạp có thể do editor làm thêm; không được lấy thao tác đó làm bằng chứng rằng agent đã thực thi một công cụ chưa có.

## 6. Kế thừa A01–A12 của audit

| Ca audit | Ca harness | Điều chỉnh cho ràng buộc BAHA |
|---|---|---|
| A01 speech | HV07/HV12/HV13/HV17/HV29 | Tiếng Việt và source map/caption thật |
| A02 visual-only | HV08/HV17 | Không dựa transcript giả; cảnh nhanh có evidence |
| A03 montage | HV10/HV11/HV25 | Tăng bài thử lên 3 video/4 audio layer có nội dung |
| A04 no-local-model | HV02/HV20/HV21/HV31/HV33 | Scan install/exec/model cache và API usage; FFmpeg CPU |
| A05 bounds | HV03/HV04/HV23 | Từ chối, không silent clamp làm đổi nội dung |
| A06 timebase | HV03/HV10/HV16 | Thêm VFR, retime và multicam |
| A07 audio/caption | HV07/HV12/HV13 | Word timing và kiểm tra nghe/nhìn |
| A08 render | HV23/HV29 | Full decode và QC theo ý đồ |
| A09 rollback | HV05/HV06/HV26/HV32 | Thêm native-bound và operation idempotency |
| A10 cloud API | HV20/HV21/HV24 | Route UI/API, session expiry, reconciliation và thực phí |
| A11 tenant | HV09/HV30/HV31 | Thêm cache, connector và dữ liệu khách hàng |
| A12 throughput | HV33/HV35 | Giữ queue 5/20, heavy concurrency = 1; không chạy đồng thời 20 render trái AGENTS |

## 7. Hồ sơ kết thúc gate và phát hành

Manifest từng ca gồm `test_id`, trạng thái, mức bằng chứng, fixture/version/hash, lệnh hoặc thao tác, observed/expected, artifact links, provider/engine versions, reviewer/time và giới hạn. Tất cả ca con unsupported phải giữ trong báo cáo; không xóa hàng để tăng tỷ lệ PASS.

H12 chỉ COMPLETE khi các ca mandatory và C01–C16 đủ bằng chứng, branch H08-API đạt mức tự động, prototype/policy đã duyệt, pilot đạt, rollback/tiếp quản đạt. Duyệt phát hành là quyết định riêng của Founder. Nếu không đạt chỉ số 30% hoặc nhóm bắt buộc còn BLOCKED, ghi pilot chưa đạt và giữ kế hoạch mở; không tự đổi định nghĩa “toàn diện”.
