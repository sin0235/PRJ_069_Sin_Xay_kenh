# Bàn giao khắc phục phân quyền — BAHA-AUTHZ-001

Người thực hiện: ba agent triển khai Luna 6 (`gpt-6-luna`, suy luận `max`), các agent Luna kiểm tra độc lập và Codex điều phối. Phạm vi là 16 phát hiện trong `ra_soat_phan_quyen_2026_10_21.md`, cùng các lỗi liên quan được phát hiện khi kiểm tra bản sửa.

## Kết quả mã nguồn

| Phát hiện gốc | Thay đổi đã thực hiện | Trạng thái và giới hạn |
|---|---|---|
| 1 — giả danh qua header | Xác minh bearer có chữ ký, issuer/audience/subject/thời hạn; nạp membership và vai trò từ kho quyền chuẩn | Đã có kiểm thử từ chối header giả. Chưa có nhà cung cấp danh tính thật được kết nối; thiếu cấu hình thì từ chối |
| 2 — RBAC chưa bảo vệ nghiệp vụ | Gắn action và kiểm tra tài nguyên vào API; dùng kho quyền chung, bỏ so sánh thứ bậc role cũ | Đã kiểm thử tích hợp cùng tiến trình với hai kho RAM riêng. Các bộ test nghiệp vụ legacy chưa được chuyển hết sang xác thực mới |
| 3–4 — cấp quyền vượt phạm vi/vai trò | Kiểm tra vai trò được cấp và phạm vi từ cùng một assignment; xác minh tổ chức phía server; bỏ ngoại lệ Owner cấp tùy ý | Ca mời/cấp đúng nhóm được phép, khác nhóm hoặc vai trò cấm bị chặn. API cấp PROJECT chưa hỗ trợ |
| 5–6 — hết hạn và trộn phạm vi | Lọc hiệu lực, trạng thái user/workspace/role; giữ quyền gắn với scope của từng assignment | Có ca nhiều nhóm, vai trò hết hạn và hai vai trò ở phạm vi tách biệt |
| 7, 14 — dịch vụ tài nguyên | Sửa action `ideas.read`, kiểm tra quyền đọc/sửa/tổng hợp theo resource; tải media dùng `media.read` | Không còn tự dựng URL tải. Chưa có dịch vụ ký URL nên tải trả kết quả không khả dụng |
| 8 — đánh giá tin dữ liệu client | Đọc thuộc tính tài nguyên từ DB; strict schema bỏ owner/creator/scope tự khai | ID không tồn tại hoặc ngoại tenant bị từ chối |
| 9 — worker | Grant giới hạn action/tài nguyên/version/hash/policy/TTL; xác thực worker; kiểm tra lại quyền hiện tại; đối chiếu payload với snapshot và binding | Token worker cần workspace được ký; từ chối thiếu/sai tenant, quyền bị thu hồi, payload thay đổi hoặc job phát lại. Chưa chạy dịch vụ từ xa/provider thật |
| 10–11 — duyệt | Nạp policy, phiên bản/hash/tác giả từ server; đúng người/chặng; cấm bên có lợi ích tự duyệt; chuyển trạng thái có điều kiện, khóa duy nhất và phát lại nhất quán | Có ca owner khác creator, thiếu attribution, bỏ chặng, stale version và quyết định trùng. Chưa kiểm tra tranh chấp thực tế trên PostgreSQL |
| 12 — DB tenant/RLS | Thêm FK ghép tenant, migration ngoại tuyến, context theo từng giao dịch | Ràng buộc được kiểm tra trên SQLite RAM. Migration/RLS PostgreSQL chưa được thực thi; chưa đóng nghiệm thu tầng DB |
| 13 — audit | Ghi quyết định và thao tác nhạy cảm, băm định danh tài nguyên, làm sạch metadata; chặn sửa/xóa nhật ký | Có kiểm thử SQLite. Trigger và chính sách PostgreSQL chưa chạy thật |
| 15 — báo cáo PASS vượt bằng chứng | Ghi ưu tiên tiếp quản ở đầu CURRENT_STATE, báo cáo mới và thẻ điều phối | Không tạo checkpoint, không tự coi A00–A10 PASS hoặc A11 sẵn sàng. Tài liệu gốc ngoài vùng ghi cần Antigravity đối soát |
| 16 — giao diện mẫu | Bỏ danh sách/ma trận/audit giả; giữ tab và trạng thái chưa kết nối; tắt thao tác chưa khả dụng | Giao diện quản trị chưa kết nối dữ liệu thật; chưa nghiệm thu A08 |

## Rà soát độc lập và sửa bổ sung

- `ra_soat_doc_lap_nhom_2.md` phát hiện worker thiếu tenant context khi bật RLS và SoD bỏ sót owner khác creator. Đã sửa vòng 1: tenant lấy từ claim được ký, gắn context trước query; kiểm tra cả owner và creator, đồng thời cấm người tạo run tự duyệt. Bằng chứng nhóm 2 ghi RED trước sửa và GREEN sau sửa.
- Bộ đánh giá từ chối mọi action duyệt khi thiếu ngữ cảnh tài nguyên hoặc attribution. Kiểm thử P09 xác nhận HTTP 403, không gọi service duyệt hoặc thay đổi script. Không chỉnh nghiệp vụ P09 đang được triển khai ngoài nhóm.
- `ra_soat_doc_lap_tong_hop.md` nêu giới hạn PROJECT và lỗi phân biệt ID brief ngoại tenant với ID không tồn tại. Đã làm rõ giới hạn PROJECT và xóa truy vấn tìm brief toàn cục; kiểm thử cả hai ID trả cùng 404, không lộ thuộc tính hoặc đổi dữ liệu.

## Kiểm chứng có thể chạy lại

Lệnh điều phối: `python 03_ban_lam_viec/baha_auth/kiem_tra_tong_hop_phan_quyen.py`.

Lượt kiểm tra cuối: **111 bài đạt — 86 phân quyền, 11 API tích hợp, 14 worker; cả ba tiến trình và công cụ điều phối thoát mã 0**. Không có lỗi cú pháp hoặc tệp đổi mã băm trong lượt kiểm tra. Có cảnh báo phụ thuộc Starlette/httpx và SQLAlchemy; không có bài thất bại. Rà soát độc lập cuối đã đối chiếu các bản sửa, không còn phát hiện P0/P1/P2 đang mở trong phạm vi đã rà soát; các giới hạn bên dưới vẫn giữ nguyên.

Lệnh này chạy các tiến trình riêng, cấu hình DB RAM trước import; chạy toàn bộ bộ kiểm thử `baha_auth`, bộ API `tests/test_tich_hop_phan_quyen.py` và bộ worker `tests/test_kiem_tra_quyen_worker.py`. Công cụ kiểm tra cú pháp Python và băm nguồn trước/sau; mã thoát khác 0 nếu kiểm thử lỗi, cú pháp lỗi hoặc tệp thay đổi trong lượt chạy.

Kết quả và hash nghiệm thu lấy tại `08_kiem_thu/bang_chung/ket_qua_tong_hop_sua_phan_quyen_2026_10_21.json`; đầu ra từng bộ ở `kiem_thu_tong_hop_phan_quyen_baha_auth_2026_10_21.txt`, `kiem_thu_tong_hop_phan_quyen_sin_content_api_2026_10_21.txt`, `kiem_thu_tong_hop_phan_quyen_sin_content_workers_2026_10_21.txt` trong cùng thư mục bằng chứng. Không dùng kết quả cũ nếu hash nguồn sau đó thay đổi.

Chi tiết từng nhóm: `bao_cao_sua_nhom_1.md`, `bao_cao_sua_nhom_2.md`, `../sin_content_api/bao_cao_sua_phan_quyen_nghiep_vu.md`, `../sin_content_api/kiem_tra_tich_hop_cuoi.md`, `../sin_content_api/kiem_tra_lo_lo_ton_tai_brief.md`.

## Điều kiện còn lại trước phát hành

Chưa được coi hệ thống sẵn sàng production. Cần cấu hình nhà cung cấp danh tính và cấp token thật; ánh xạ tenant/membership trên bản sao dữ liệu được phê duyệt; diễn tập migration/khôi phục; kiểm chứng PostgreSQL/RLS bằng runtime role và kiểm thử đồng thời; hoàn thiện metadata cùng các phạm vi còn thiếu, giao diện quản trị và các bài test legacy; staging và văn bản phát hành Founder.

Các scope B/H/R/A/O chưa có resolver đáng tin cậy bị từ chối. PROJECT chỉ được evaluator xử lý trên dữ liệu đã xác minh; API cấp mới theo PROJECT vẫn từ chối. Các action chưa đăng ký `workspace.create`, `evidence.import`, `evidence.purge` giữ DENY. Không tự ánh xạ quyền legacy hoặc thêm quyền mới để làm cho các thao tác này chạy được.

Worker hiện dùng token được cấu hình theo từng tiến trình/tenant. Việc bắt buộc claim workspace có nghĩa token worker cũ phải cấp lại; quản lý nhiều tenant trong một pool cần thiết kế riêng. Quy tắc không cho owner tự duyệt có nghĩa quản lý được ghi owner nhưng không phải creator vẫn cần người duyệt độc lập; phải xác nhận ngữ nghĩa ownership trước phát hành. Tạo draft brief dùng action soạn thảo `brief.edit` đã có, không thêm quyền vào ma trận.

Không chạy migration trên DB dự án, không đổi quyền sống, không gọi provider thật, không commit toàn bộ kho đang chưa có baseline tracked. Nguồn ngoài nhóm thay đổi trong quá trình làm việc đã được ghi nhận; trước mỗi lần tiếp tục phải đọc thẻ điều phối và kiểm tra hash. Hướng dẫn vận hành và hoàn nguyên an toàn nằm tại `huong_dan_van_hanh_an_toan.md`; không thực thi hướng dẫn cũ tắt cách ly hoặc `drop_all` trên dữ liệu dự án.
