# Báo cáo lỗi tổng hợp P01–P05

> **Bản cập nhật có P06:** [Báo cáo lỗi tổng hợp P01–P06](bao_cao_loi_pha_01_den_06_2026_10_21.md). Tệp P01–P05 giữ nội dung lần tổng hợp trước.

- **Dự án:** PRJ_069 — Hệ thống Content Intelligence.
- **Ngày lập:** 21/10/2026.
- **Người rà soát:** Codex.
- **Mục đích:** Bàn giao các lỗi P01–P05 để khắc phục và nghiệm thu lại.
- **Phạm vi:** Các pha Content Intelligence; không phải A01–A05 của gói phân quyền BAHA-AUTHZ-001.
- **Trạng thái:** Đã rà soát, chưa sửa mã ứng dụng; chưa đủ điều kiện nghiệm thu năm pha.

## 1. Tổng hợp mức độ

| Pha | Nội dung | P0 | P1 | P2 | Tổng |
|---|---|---:|---:|---:|---:|
| P01 | Xác thực, workspace, hạ tầng và CI | 1 | 3 | 1 | 5 |
| P02 | Brief, phiên bản, dữ liệu và phê duyệt | 0 | 3 | 3 | 6 |
| P03 | Adapter, import, ngân sách và xử lý lỗi | 0 | 8 | 2 | 10 |
| P04 | Ingestion, xuất xứ, snapshot và thời hạn lưu | 0 | 8 | 2 | 10 |
| P05 | Kế hoạch truy vấn và bộ dữ liệu vàng | 0 | 6 | 4 | 10 |
| **Tổng** | | **1** | **28** | **12** | **41** |

- **P0:** Ưu tiên xử lý ngay lỗi giả danh và truy cập dữ liệu khách hàng khác.
- **P1:** Lỗi an toàn, mất dữ liệu, sai bằng chứng hoặc chức năng cốt lõi cần sửa trước nghiệm thu.
- **P2:** Lỗi kiểm soát, tính nhất quán hoặc thiếu tiêu chí nghiệm thu cần hoàn thiện.

Mỗi phát hiện chỉ được đếm một lần dù có thể ảnh hưởng nhiều pha. Lỗi xác thực P01 cũng ảnh hưởng các endpoint P02/P03.

## 2. Bằng chứng thực chạy

| Phạm vi | Kết quả kiểm thử hiện có | Nhật ký |
|---|---|---|
| P01–P02 | 10/10 đạt, mã thoát 0, 9,42 giây | [Nhật ký P01–P02](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p01_p02_2026_10_21.txt) |
| P03 | 6/6 đạt, mã thoát 0, 3,37 giây | [Nhật ký P03](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p03_2026_10_21.txt) |
| P04 | 5/5 đạt, mã thoát 0, 2,31 giây | [Nhật ký P04](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p04_2026_10_21.txt) |
| P05 | 3/3 đạt, mã thoát 0, 2,48 giây | [Nhật ký P05](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p05_2026_10_21.txt) |

Kiểm thử hiện có đạt chưa chứng minh các cổng nghiệm thu hoàn chỉnh. Những tình huống bổ sung đã phát hiện các lỗi chưa được bao phủ:

- [Bằng chứng tái hiện P01–P02](../../08_kiem_thu/bang_chung/tai_hien_loi_p01_p02_2026_10_21.json).
- [Bằng chứng tái hiện P03](../../08_kiem_thu/bang_chung/tai_hien_loi_p03_2026_10_21.json).
- [Báo cáo gốc P01–P02](ra_soat_p01_p02_2026_10_21.md).
- [Báo cáo gốc P03](ra_soat_p03_2026_10_21.md).
- [Báo cáo gốc P04](ra_soat_p04_2026_10_21.md).
- [Báo cáo gốc P05](ra_soat_p05_2026_10_21.md).
- [Bằng chứng tái hiện P05](../../08_kiem_thu/bang_chung/tai_hien_loi_p05_2026_10_21.json).
- [Bằng chứng tái hiện P04](../../08_kiem_thu/bang_chung/tai_hien_loi_p04_2026_10_21.json).

Các lượt kiểm tra dùng SQLite chỉ trong RAM, thay engine trước khi nhập ứng dụng và bộ kiểm thử. Không thực hiện lệnh xóa bảng trên cơ sở dữ liệu dự án, không gọi nguồn mạng và không dùng credential thật. Tài liệu kế thừa bằng chứng P01–P04 và bổ sung lượt kiểm thử P05. Không chạy lại các pha trước khi chỉ cập nhật tài liệu.

Chưa xác nhận Docker build, PostgreSQL hoặc năng lực TikTok trực tiếp. Thiếu sót hạ tầng và CI được xác định bằng đối chiếu cấu hình/tệp. Tình huống synthetic trong production được mô phỏng bằng cấu hình ứng dụng thử nghiệm trong RAM.

## 3. Thứ tự xử lý và điều kiện đóng lỗi

1. Khắc phục giả danh và tách cơ sở dữ liệu kiểm thử trước khi chạy các bài có thao tác xóa bảng.
2. Bảo vệ workspace, brief đã duyệt, quyền xét duyệt và ràng buộc an toàn thương hiệu.
3. Bảo toàn nguồn gốc, dấu synthetic, dữ liệu import, vòng đời xóa và metadata chỉ số.
4. Hoàn thiện hạ tầng, CI, kiểm soát phiên bản, cập nhật dữ liệu, audit và xử lý lỗi provider.

- [ ] Mỗi mã lỗi có bản sửa được đối soát với tình huống trong báo cáo.
- [ ] Có kiểm tra hồi quy cho các nhánh bảo mật, phiên bản, import và xử lý lỗi được sửa.
- [ ] Kiểm thử dùng cơ sở dữ liệu riêng; nhật ký mới được lưu tại `08_kiem_thu/bang_chung/`.
- [ ] Đối soát lại nhãn PASS trong CURRENT_STATE, báo cáo pha và trang hành trình trước khi nghiệm thu lại.

**Bàn giao:** Chưa đóng lỗi nào và chưa tạo checkpoint mới. Vị trí dòng mã dưới đây thuộc thời điểm rà soát, có thể thay đổi sau bản sửa. Các ô trong danh sách là trạng thái khắc phục; chỉ đánh dấu sau khi có bằng chứng kiểm tra lại.

## 4. Danh sách giao xử lý

| Trạng thái | Mã lỗi | Mức độ | Nội dung |
|---|---|---|---|
| [ ] | P01-01 | P0 | Hai header cho phép giả danh người dùng khác |
| [ ] | P01-02 | P1 | Endpoint workspace công khai toàn bộ khách hàng |
| [ ] | P01-03 | P1 | Chạy test mặc định có thể xóa cơ sở dữ liệu ứng dụng |
| [ ] | P01-04 | P1 | Cấu hình Docker không có tệp để xây dựng API |
| [ ] | P01-05 | P2 | Chưa có CI thực thi cổng T012 |
| [ ] | P02-01 | P1 | Đổi trạng thái cho phép sửa đè brief từng được duyệt |
| [ ] | P02-02 | P1 | Có thể xóa ràng buộc an toàn thương hiệu rồi duyệt |
| [ ] | P02-03 | P1 | Editor được cấp quyền phê duyệt do xếp vai trò theo số |
| [ ] | P02-04 | P2 | Hai lần sửa cùng phiên bản tạo hai bản cùng số version |
| [ ] | P02-05 | P2 | API nhận cập nhật phân khúc/sự thật nhưng bỏ qua |
| [ ] | P02-06 | P2 | T022 không ghi sự kiện khi viewer bị từ chối |
| [ ] | P03-01 | P1 | Import biến dữ liệu tổng hợp thành dữ liệu thật |
| [ ] | P03-02 | P1 | Tự tạo URL TikTok không có trong dữ liệu nguồn |
| [ ] | P03-03 | P1 | Dữ liệu sai kiểu gây 500 và để lại tác dụng phụ chưa commit |
| [ ] | P03-04 | P1 | Kho RAM làm search mất, trùng hoặc trả lại dữ liệu đã xóa |
| [ ] | P03-05 | P1 | Adapter TikTok chưa gọi upstream vẫn báo tìm kiếm thành công nhưng rỗng |
| [ ] | P03-06 | P2 | Retry-after bị mất và registry vẫn gọi lại ngay |
| [ ] | P03-07 | P2 | Timeout thật không được chuẩn hóa hoặc tính vào circuit breaker |
| [ ] | P03-08 | P1 | Ngân sách 0 USD vẫn cho phép ghi nhận chi phí |
| [ ] | P03-09 | P1 | Import âm thầm bỏ bản ghi khi ID trùng provider khác |
| [ ] | P03-10 | P1 | Import thay đổi thời gian quan sát và độ chính xác chỉ số |

| [ ] | P04-01 | P1 | Trùng quan sát ngay trong một batch vẫn tạo hai snapshot |
| [ ] | P04-02 | P2 | Gửi lại bản chỉ có URL luôn tạo quan sát mới |
| [ ] | P04-03 | P1 | Quan sát mới bị bỏ vì dùng ID nội dung làm ID quan sát |
| [ ] | P04-04 | P1 | Sai kiểu synthetic vượt chốt production |
| [ ] | P04-05 | P1 | Ingestion nhận nguồn bị cấm và tự gán quyền sử dụng |
| [ ] | P04-06 | P1 | Thời điểm quan sát bị thay bằng thời điểm import |
| [ ] | P04-07 | P1 | Chỉ số sai kiểu bị biến thành số 0 hoặc chấp nhận số âm |
| [ ] | P04-08 | P2 | retention_days sai kiểu làm hỏng toàn yêu cầu |
| [ ] | P04-09 | P1 | Thời hạn lưu chỉ được ghi lại, chưa được thực thi |
| [ ] | P04-10 | P1 | Nguồn đã purge vẫn nhận lại payload nhạy cảm |

| [ ] | P05-01 | P1 | Bộ chuẩn được mã tự sinh nhưng công bố là con người gán nhãn |
| [ ] | P05-02 | P1 | Planner tạo truy vấn vượt trần chi phí |
| [ ] | P05-03 | P1 | Brief chưa duyệt vẫn được dùng tạo kế hoạch nghiên cứu |
| [ ] | P05-04 | P1 | workspace trong kế hoạch lấy từ payload, khác workspace lưu DB |
| [ ] | P05-05 | P1 | Provider bị cấm hoặc không tồn tại vẫn vào kế hoạch |
| [ ] | P05-06 | P1 | Kế hoạch bỏ mất điều kiện thời gian và chế độ dữ liệu |
| [ ] | P05-07 | P2 | plan_id trả về không đọc lại được qua API |
| [ ] | P05-08 | P2 | Lấy đơn giá đắt nhất gán cho cả nguồn miễn phí |
| [ ] | P05-09 | P2 | Cắt danh sách theo thứ tự làm mất cân bằng nhóm nhu cầu |
| [ ] | P05-10 | P2 | Template ngành hộp cơm được dùng cho serum và ngành khác |

## 5. Chi tiết lỗi P01

### P01-01 — P0 — Hai header cho phép giả danh người dùng khác

**Vị trí:** `sin_content_api/src/auth/tenancy.py:15–42`.

Hàm được gọi là xác thực phiên nhưng chỉ tìm membership theo `X-User-Id` và `X-Workspace-Id` do người gọi cung cấp. Đã đọc được brief thử nghiệm “Chiến lược B chưa công bố” bằng header của owner B mà không có mật khẩu, cookie hay token. Kiểm tra workspace sau đó không bảo vệ được dữ liệu khi danh tính đầu vào đã bị giả mạo; mã không giới hạn cơ chế này trong chế độ offline.

**Sửa:** Lấy người dùng từ phiên hoặc token được xác minh ở máy chủ, rồi kiểm tra membership. Nếu cần chế độ giả lập offline, cô lập rõ và chặn khi staging/production. Nếu bỏ qua, người biết ID của thành viên có thể đọc hoặc thực hiện quyền của thành viên đó.


### P01-02 — P1 — Endpoint workspace công khai toàn bộ khách hàng

**Vị trí:** `sin_content_api/src/modules/workspaces/router.py:11–13, 15–28`.

Gọi `GET /v1/workspaces` không có header nhận HTTP 200 cùng tên và ID của cả khách hàng A và B. Endpoint tạo workspace cũng không xác thực và không tạo membership cho người tạo, nên luồng tạo mới không dẫn đến workspace mà người tạo có thể sử dụng.

**Sửa:** Xác thực danh tính; danh sách chỉ trả workspace của người đó. Tạo workspace và membership owner trong một giao dịch theo quyền tạo được quy định. Nếu bỏ qua, thông tin khách hàng bị lộ và người ngoài có thể tạo workspace tùy ý.


### P01-03 — P1 — Chạy test mặc định có thể xóa cơ sở dữ liệu ứng dụng

**Vị trí:** `sin_content_api/tests/test_migrations.py:2–20`; `tests/conftest.py:1–7`; `src/migrations/runner.py:5, 16–18`.

Bộ kiểm thử nhập engine từ cấu hình thật; `conftest.py` chỉ thêm đường dẫn import, không cấp cơ sở dữ liệu kiểm thử. Bài migration gọi `drop_all()` trên engine đó rồi tạo lại bảng rỗng. Trên engine RAM có hai workspace thử nghiệm, thực hiện cùng chu trình làm số workspace về 0; nếu chạy scripts kiểm thử mặc định với DATABASE_URL của ứng dụng, dữ liệu ứng dụng sẽ bị xóa.

**Sửa:** Cấp engine/cơ sở dữ liệu tạm riêng cho toàn bộ bộ kiểm thử trước khi nhập các module; không dùng DATABASE_URL của ứng dụng. Bài migration chỉ được chạy trên engine kiểm thử đó. Nếu bỏ qua, một lệnh kiểm thử thông thường có thể mất dữ liệu thật.


### P01-04 — P1 — Cấu hình Docker không có tệp để xây dựng API

**Vị trí:** `ha_tang/compose.yaml:30–33`; `sin_content_api/requirements.txt:1–9`.

Compose khai báo build từ `sin_content_api/Dockerfile`, nhưng tệp này không tồn tại. Vì vậy nhánh khởi động bằng Compose không thể build API từ bản sao mã nguồn hiện tại. Ngoài ra requirements chưa khai báo driver PostgreSQL trong khi Compose cấu hình DATABASE_URL PostgreSQL; báo cáo mô tả Celery worker nhưng Compose hiện không có service worker.

**Sửa:** Hoàn thiện Dockerfile và phụ thuộc đúng với DATABASE_URL, rồi kiểm chứng lệnh khởi động từ môi trường sạch. Đồng bộ phạm vi worker thực tế vào báo cáo. Nếu bỏ qua, không thể nghiệm thu tuyên bố stack Docker đã sẵn sàng.


### P01-05 — P2 — Chưa có CI thực thi cổng T012

**Vị trí:** Thiếu `.github/workflows` tại gốc và vùng mã nguồn; `sin_content_api/scripts/scan_secrets.py` mới là script chạy thủ công.

Tìm các tệp YAML trong `03_ban_lam_viec` chỉ có Compose và cấu hình workspace frontend, không có workflow CI. T012 yêu cầu cổng CI được thực thi; chạy scanner thủ công trong báo cáo không đáp ứng yêu cầu đó.

**Sửa:** Thêm cấu hình CI trong vùng mã nguồn được phép, chạy kiểm thử trên cơ sở dữ liệu riêng và scanner với mã thoát chặn khi phát hiện vi phạm; bàn giao cấu hình kích hoạt phù hợp với kho Git. Nếu bỏ qua, lần thay đổi tiếp theo có thể bỏ qua mọi kiểm tra mà P01 được mô tả là đã có.

## 6. Chi tiết lỗi P02

### P02-01 — P1 — Đổi trạng thái cho phép sửa đè brief từng được duyệt

**Vị trí:** `sin_content_api/src/modules/briefs/router.py:169–171, 213–226, 261–262`.

Chuỗi `APPROVE → REQUEST_CHANGES → PUT` ghi đè nội dung của chính ID phiên bản 1. Tái hiện cho thấy objective đổi nhưng version vẫn 1, ID giữ nguyên và `approved_by_user_id` vẫn còn. Nhánh bảo toàn phiên bản chỉ kiểm tra trạng thái APPROVED hiện tại, không bảo vệ phiên bản đã từng được duyệt.

**Sửa:** Không cho chuyển bản đã duyệt sang trạng thái có thể sửa tại chỗ; yêu cầu sửa phải tạo draft mới. Kiểm tra các chuyển trạng thái hợp lệ và giữ metadata phê duyệt gắn với nội dung bất biến. Nếu bỏ qua, ý tưởng hoặc kịch bản tham chiếu brief cũ sẽ thấy nội dung đã bị thay mà vẫn giữ ID phê duyệt cũ.


### P02-02 — P1 — Có thể xóa ràng buộc an toàn thương hiệu rồi duyệt

**Vị trí:** `sin_content_api/src/schemas/contracts.py:83–91`; `src/modules/briefs/router.py:220–221, 247–250`.

Tạo mới bắt buộc danh sách chủ đề có phần tử, nhưng update chấp nhận `topics_excluded=[]` và `topics_included=[]`. Sau update, APPROVE vẫn trả HTTP 200 với danh sách cấm rỗng. Ràng buộc T020 vì vậy chỉ có hiệu lực khi tạo lần đầu.

**Sửa:** Áp dụng cùng ràng buộc cho trường được cập nhật và kiểm tra lại tính hợp lệ của toàn brief trước khi duyệt. Kiểm tra phần tử không chỉ chứa khoảng trắng. Nếu bỏ qua, bộ lọc truy vấn và sinh nội dung mất những giới hạn thương hiệu mà báo cáo tuyên bố là bắt buộc.


### P02-03 — P1 — Editor được cấp quyền phê duyệt do xếp vai trò theo số

**Vị trí:** `sin_content_api/src/auth/tenancy.py:71–84`; `src/modules/briefs/router.py:232`.

`reviewer=2`, `editor=3` làm editor tự động vượt yêu cầu reviewer. Tái hiện: editor tạo brief rồi tự APPROVE nhận HTTP 200. Cơ chế này không phân biệt quyền biên tập và quyền xét duyệt; mô tả P02 liệt kê reviewer/admin/owner cho phê duyệt.

**Sửa:** Kiểm tra quyền duyệt theo tập vai trò hoặc quyền hành động đã được thống nhất; không suy ra mọi quyền từ thứ tự số. Nếu bỏ qua, tài khoản được giao biên tập có thể tự xác nhận nội dung như đã qua người duyệt.


### P02-04 — P2 — Hai lần sửa cùng phiên bản tạo hai bản cùng số version

**Vị trí:** `sin_content_api/src/modules/briefs/router.py:169–174`; `src/models/entities.py`, thực thể `BrandBriefVersion`.

Gửi hai lần PUT đến brief APPROVED v1 tạo hai ID khác nhau nhưng cả hai đều version 2. Không cần chạy đồng thời để tái hiện; mô hình cũng không lưu định danh chuỗi phiên bản hoặc quan hệ bản cha để giải thích hai nhánh đó. Điều này không đáp ứng yêu cầu kiểm soát sửa xung đột của Gate P02.

**Sửa:** Lưu quan hệ chuỗi phiên bản, kiểm tra phiên bản gốc còn hợp lệ trước khi sửa và cấp số phiên bản duy nhất trong chuỗi bằng giao dịch/ràng buộc thích hợp. Nếu bỏ qua, việc gửi lại hoặc nhiều người biên tập làm lịch sử phiên bản mơ hồ.


### P02-05 — P2 — API nhận cập nhật phân khúc/sự thật nhưng bỏ qua

**Vị trí:** `sin_content_api/src/schemas/contracts.py:83–91`; `src/modules/briefs/router.py:188–206, 213–226`.

`BrandBriefUpdate` không có `segments` hoặc `allowed_facts`, và Pydantic mặc định bỏ qua các trường lạ. Gửi phân khúc mới cùng `allowed_facts=[]` nhận HTTP 200 nhưng phân khúc cũ và sự thật cũ còn nguyên. Không có endpoint riêng để sửa các mục này; khi tạo bản mới, router cũng chỉ sao chép bản cũ.

**Sửa:** Khai báo và xử lý hai trường trong luồng cập nhật/phiên bản; từ chối trường không hỗ trợ thay vì im lặng bỏ qua. Nếu bỏ qua, khách hàng tưởng đã sửa hoặc rút một tuyên bố sản phẩm nhưng các pha sau vẫn sử dụng nội dung cũ.


### P02-06 — P2 — T022 không ghi sự kiện khi viewer bị từ chối

**Vị trí:** `sin_content_api/src/auth/tenancy.py:79–84`; `tests/test_briefs.py:171–209`.

Viewer APPROVE bị trả 403 đúng, nhưng số `AuditEvent` trước và sau đều là 3. `require_role` chỉ ném lỗi, không ghi sự kiện; bài T022 cũng không hề kiểm tra audit dù tên/mô tả và báo cáo nghiệm thu nói có. Đây là tiêu chí bắt buộc của T022 chưa đạt.

**Sửa:** Ghi sự kiện từ chối quyền với người thực hiện, workspace, hành động và tài nguyên phù hợp; kiểm thử bản ghi đó. Nếu bỏ qua, hành vi thử vượt quyền không để lại dấu vết như yêu cầu nghiệm thu.

## 7. Chi tiết lỗi P03

### P03-01 — P1 — Import biến dữ liệu tổng hợp thành dữ liệu thật

**Vị trí:** `sin_content_api/src/modules/sources/customer_import_adapter.py:124–134`; `router.py:158, 184–192`.

Với `app_env=production`, gửi bản ghi có `synthetic=true`, `provider_id=test_fixture` vẫn nhận HTTP 200, `status=OK`. Bản lưu có `synthetic=false`, provider là customer_import và quyền sử dụng được gán customer_supplied. Adapter mặc định coi mọi dữ liệu khách hàng đưa vào là thật; endpoint này không đi qua rào chắn synthetic của ingestion P04.

**Sửa:** Bảo toàn dấu synthetic và nguồn gốc, chặn dữ liệu tổng hợp khi production trước khi ghi vào RAM hoặc DB; dùng chung bước kiểm tra với ingestion. Nếu bỏ qua, dữ liệu thử có thể đi vào nghiên cứu như bằng chứng thật.


### P03-02 — P1 — Tự tạo URL TikTok không có trong dữ liệu nguồn

**Vị trí:** `sin_content_api/src/modules/sources/customer_import_adapter.py:125–126`.

Thiếu canonical_url, adapter tự dựng `https://tiktok.com/@creator/video/{external_id}`. Đã tái hiện với ID chữ của bản ghi tổng hợp; URL được lưu như nguồn thật dù không có bằng chứng video tương ứng tồn tại. Một external_id nội bộ cũng có thể thuộc tài liệu khác TikTok.

**Sửa:** Giữ URL rỗng khi chưa có, sử dụng tham chiếu import có xuất xứ hoặc yêu cầu URL khi loại nguồn bắt buộc phải có; không suy ra đường dẫn video. Nếu bỏ qua, các pha sau có thể trích dẫn liên kết do hệ thống bịa ra.


### P03-03 — P1 — Dữ liệu sai kiểu gây 500 và để lại tác dụng phụ chưa commit

**Vị trí:** `sin_content_api/src/modules/sources/customer_import_adapter.py:73–90, 124–137`; `router.py:158`.

`text_excerpt` là object hoặc canonical_url là số đều gây HTTP 500, không có bản ghi quarantine. Với batch có bản hợp lệ đứng trước bản sai, yêu cầu vẫn báo 500 nhưng search đã trả bản hợp lệ từ RAM trong khi DB chưa có bản đó. Hàm chỉ cách ly trường bị thiếu, không bắt lỗi xác thực ProviderPost; nó thay đổi bộ nhớ trước khi toàn lô được kiểm tra.

**Sửa:** Xác thực từng bản ghi đầy đủ, cách ly lỗi kiểu dữ liệu với lý do cụ thể và trả PARTIAL/INVALID_DATA. Chỉ công bố dữ liệu hợp lệ sau khi lưu thành công; không để batch thất bại tạo trạng thái đọc được ngoài giao dịch. Nếu bỏ qua, dữ liệu hỏng làm đứt import và dữ liệu trả về không khớp kết quả lưu.


### P03-04 — P1 — Kho RAM làm search mất, trùng hoặc trả lại dữ liệu đã xóa

**Vị trí:** `sin_content_api/src/modules/sources/customer_import_adapter.py:31–35, 137, 169–184`; `router.py:177–208`.

Ba trường hợp cùng xuất phát từ hai kho dữ liệu không đồng bộ: gửi cùng import hai lần cho search_total=2 nhưng DB chỉ có 1 bản; adapter mới sau khởi động lại trả 0 dù DB còn bản; sau purge thành công, search vẫn trả nguyên nội dung cũ từ RAM. Với nhiều process, mỗi process cũng có kho riêng.

**Sửa:** Dùng DB làm nguồn đọc chính cho adapter import, với định danh chống trùng và kiểm tra trạng thái purge. Bảo đảm bình luận và payload có vòng đời lưu/xóa rõ ràng. Nếu bỏ qua, kết quả nghiên cứu tùy thuộc process và có thể tiếp tục lộ nội dung đã yêu cầu xóa.


### P03-05 — P1 — Adapter TikTok chưa gọi upstream vẫn báo tìm kiếm thành công nhưng rỗng

**Vị trí:** `sin_content_api/src/modules/sources/tiktok_official_adapter.py:54–62, 79–82, 99–124`.

Chuỗi thử nghiệm có tiền tố `act.` vượt kiểm tra, dù chưa xác thực OAuth. Search trả EMPTY, comments/profile cũng trả EMPTY và refresh_metrics trả danh sách rỗng; không có lệnh gọi upstream trong các nhánh đó. Trạng thái capability UNVERIFIED không ngăn API công bố kết quả rỗng như một lần truy vấn đã thành công.

**Sửa:** Khi adapter chưa triển khai hoặc chưa được phép gọi live, trả trạng thái không khả dụng/chưa được kiểm chứng tương ứng. Chỉ trả EMPTY sau phản hồi thành công thực sự của provider. Nếu bỏ qua, hệ thống nhầm thiếu khả năng thu thập với không có tín hiệu thị trường.


### P03-06 — P2 — Retry-after bị mất và registry vẫn gọi lại ngay

**Vị trí:** `sin_content_api/src/modules/sources/provider_registry.py:119–138`; `router.py:130–133`; `src/main.py`, hàm `http_exception_handler`.

Provider trả 429 với retry_after_seconds=120 nhưng hai yêu cầu API liên tiếp vẫn gọi provider hai lần. Response API không có trường retry_after_seconds hoặc header Retry-After; handler chỉ giữ mã và thông báo, bỏ các trường ProviderError. T032 hiện chỉ kiểm tra mã 429, chưa kiểm chứng chờ, backoff hoặc hủy.

**Sửa:** Bảo toàn metadata lỗi, trạng thái retryable và thời gian chờ; registry cần ghi thời điểm được gọi lại và từ chối gọi sớm. Mọi retry có giới hạn phải xét ngân sách và hủy. Nếu bỏ qua, caller không có hợp đồng thời gian chờ ổn định và có thể tiếp tục gây lỗi hạn ngạch.


### P03-07 — P2 — Timeout thật không được chuẩn hóa hoặc tính vào circuit breaker

**Vị trí:** `sin_content_api/src/modules/sources/provider_registry.py:133–138`; `provider_protocol.py:103`.

Khi provider ném TimeoutError, exception thoát khỏi execute_search và consecutive_failures vẫn bằng 0. Trường timeout_seconds trong Budget không được registry sử dụng. Cơ chế hiện chỉ xử lý lỗi đã được adapter tự đổi thành ProviderError; adapter gặp lỗi transport thật sẽ không có bảo vệ tương đương mô phỏng.

**Sửa:** Đặt timeout tại tầng I/O và đổi các lỗi transport đã biết thành lỗi provider an toàn, có khả năng retry; cập nhật circuit breaker cho đúng loại lỗi. Không tự động retry lỗi quyền truy cập. Nếu bỏ qua, timeout đi thành lỗi 500 và ngắt mạch không hoạt động như báo cáo.


### P03-08 — P1 — Ngân sách 0 USD vẫn cho phép ghi nhận chi phí

**Vị trí:** `sin_content_api/src/modules/sources/provider_protocol.py:98–114`; `tiktok_official_adapter.py:71–79`.

Budget có max_cost_usd=0 nhưng can_spend(0.005) trả true vì điều kiện so sánh chỉ áp dụng khi max_cost_usd lớn hơn 0. Tái hiện: gọi adapter giả lập ghi current_cost_usd=0.005 trong khi trần bằng 0. Đây là sai kiểm soát ngân sách trong mã; không có chi phí vendor thật phát sinh ở lượt kiểm tra.

**Sửa:** Trần 0 phải chặn khoản chi dương. Nếu cần ngân sách không giới hạn, biểu diễn riêng; kiểm tra các trường số không âm và lấy phần đã dùng từ trạng thái máy chủ. Nếu bỏ qua, mặc định miễn phí có thể cho phép chi khi adapter được nối live.


### P03-09 — P1 — Import âm thầm bỏ bản ghi khi ID trùng provider khác

**Vị trí:** `sin_content_api/src/modules/sources/router.py:178–195`.

Truy vấn chống trùng chỉ có workspace và raw_external_id, thiếu provider. Khi DB có bản từ other_approved_provider với ID same-id, nhập bản customer_import khác nguồn cùng ID trả valid_count=1, status=OK nhưng DB chỉ còn bản cũ; bản nhập mới không được lưu. Bộ nhớ search lại có bản mới, làm hai luồng đọc mâu thuẫn.

**Sửa:** Phân biệt ID theo namespace provider/nền tảng; chỉ hợp nhất đa nguồn khi có khóa canonical đã đối soát, lưu quan sát và xuất xứ riêng. Nếu bỏ qua, dữ liệu hợp lệ có thể mất mà API vẫn báo thành công.


### P03-10 — P1 — Import thay đổi thời gian quan sát và độ chính xác chỉ số

**Vị trí:** `sin_content_api/src/modules/sources/customer_import_adapter.py:92–106`; `router.py:197–205`.

Nhập VIEW_COUNT=100 có observed_at=2024-01-01 và precision=ROUNDED, search trả thời điểm hiện tại năm 2026 và precision=EXACT. Snapshot lưu tiếp tục dùng thời điểm hiện tại, observation_id rỗng; hai metrics cùng bản quan sát bị ghi thành hai hàng không có liên kết quan sát. Bản ghi lịch sử vì vậy trông như số liệu mới được đo chính xác.

**Sửa:** Bảo toàn thời điểm quan sát gốc, precision và nguồn metric; tách rõ thời điểm import với thời điểm đo. Lưu snapshot theo định danh quan sát và liên kết xuất xứ. Nếu bỏ qua, đánh giá độ mới, độ chắc chắn và biến động chỉ số ở các pha sau sẽ sai.


## 8. Chi tiết lỗi P04

### P04-01 — P1 — Trùng quan sát ngay trong một batch vẫn tạo hai snapshot

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:117–138, 171–180`; `src/database.py:17`.

Gửi hai phần tử giống hệt nhau, cùng external_id và observation_id trong một yêu cầu, API báo created_observations=2, deduplicated_observations=0; DB có một nguồn nhưng hai quan sát và hai snapshot. Session đặt autoflush=False nên truy vấn chưa nhìn thấy quan sát vừa được thêm; ORM cũng không có ràng buộc duy nhất cho khóa quan sát.

**Hướng sửa:** Theo dõi khóa đã nhận trong batch hoặc flush phù hợp trước truy vấn, đồng thời ràng buộc duy nhất theo định danh quan sát đã thống nhất để bảo vệ khi có nhiều yêu cầu. Nếu bỏ qua, cùng bằng chứng bị đếm nhiều lần và các tác vụ gửi lại không an toàn.

### P04-02 — P2 — Gửi lại bản chỉ có URL luôn tạo quan sát mới

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:63–72, 104, 117–120`.

API cho phép chỉ có canonical_url và title, nhưng thiếu external_id/observation_id thì sinh UUID ngẫu nhiên cho mỗi lần gửi. Gửi đúng cùng payload hai lần vẫn tạo hai quan sát và snapshot cho một nguồn. Đây là đầu vào được API chấp nhận nhưng chưa có cách xác định gửi lại hay quan sát mới.

**Hướng sửa:** Yêu cầu định danh quan sát hoặc khóa yêu cầu chống trùng ổn định; từ chối payload thiếu định danh cần thiết thay vì ngầm sinh khóa thay đổi mỗi lần. Nếu bỏ qua, client không thể gửi lại an toàn sau lỗi kết nối.

### P04-03 — P1 — Quan sát mới bị bỏ vì dùng ID nội dung làm ID quan sát

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:69, 117–126`.

Thiếu observation_id, lần đầu video có view_count=10 được lưu; lần quan sát tiếp theo cùng external_id với view_count=100 bị tính là bản trùng và bỏ qua, DB chỉ còn 10. Khóa chống trùng cũng không gồm provider, nên cùng ID quan sát do hai provider tự cấp cho cùng canonical record có thể bị gộp nhầm.

**Hướng sửa:** Tách định danh nội dung khỏi định danh lần quan sát; dùng khóa quan sát ổn định có namespace provider và bảo toàn mỗi lần đo hợp lệ. Nếu thiếu thông tin để phân biệt, yêu cầu bổ sung đầu vào. Nếu bỏ qua, dữ liệu snapshot mới và dòng xuất xứ có thể bị mất dù API báo OK.

### P04-04 — P1 — Sai kiểu synthetic vượt chốt production

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:35–40, 67, 108`; `router.py:18–20`.

Trong ứng dụng thử nghiệm cấu hình app_env=production, cả synthetic=1 và synthetic="true" đều được nhận HTTP 200 và lưu synthetic=true. Chốt kiểm tra dùng `is True`, còn bước lưu dùng bool(); hai bước hiểu khác nhau về cùng giá trị. Items chỉ là dict nên không có xác thực boolean trước chốt.

**Hướng sửa:** Xác thực kiểu synthetic rõ ràng trước khi kiểm tra; dùng cùng giá trị đã xác thực cho chốt và lưu, từ chối hoặc cách ly giá trị sai kiểu. Nếu bỏ qua, dữ liệu tổng hợp vẫn được ghi vào môi trường mà T043 yêu cầu phải chặn.

### P04-05 — P1 — Ingestion nhận nguồn bị cấm và tự gán quyền sử dụng

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:66–68, 101–109, 129–136`; đối chiếu `src/modules/sources/provider_registry.py:85–104`.

Nạp provider_id=mediacrawler qua `/v1/ingestion/batch` nhận HTTP 200; nguồn được lưu đúng tên bị cấm và rights_basis tự mặc định customer_supplied. Endpoint không kiểm tra danh mục cấm hoặc liên kết hồ sơ quyền sử dụng. Chốt T035 ở tuyến search không bảo vệ đường nạp này.

**Hướng sửa:** Kiểm tra nguồn và hồ sơ quyền sử dụng tại ranh giới ingestion; chặn nguồn cấm trước khi ghi, không tự coi thiếu thông tin quyền là đã được khách hàng cấp. Nếu bỏ qua, dữ liệu bị chính sách từ chối vẫn vào kho bằng chứng dưới nhãn quyền sử dụng hợp lệ.

### P04-06 — P1 — Thời điểm quan sát bị thay bằng thời điểm import

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:101–110, 129–137, 171–179`; các cột observed_at của ORM.

Payload có observed_at=2024-01-01T00:00:00Z nhưng SourceRecord, SourceObservation và MetricSnapshot đều lưu thời điểm hiện tại năm 2026. Service không chuyển trường này vào ORM nên default được dùng. Đây là lỗi ở đường batch P04, riêng với đường import P03 đã có lỗi tương tự tại P03-10.

**Hướng sửa:** Xác thực và bảo toàn thời điểm đo của nguồn, phân biệt với thời điểm tiếp nhận. Không tự khẳng định số liệu lịch sử là quan sát vừa thực hiện khi thiếu dữ liệu. Nếu bỏ qua, đánh giá độ mới và biến động chỉ số không còn đáng tin cậy.

### P04-07 — P1 — Chỉ số sai kiểu bị biến thành số 0 hoặc chấp nhận số âm

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:143–169`; `src/models/entities.py`, thực thể MetricSnapshot.

Gửi view_count=-5, false và 0.9 đều nhận HTTP 200, lần lượt lưu -5, 0 và 0. `int()` ép boolean/số thực thành số nguyên, không kiểm tra miền giá trị. Điều này tạo số 0 dù nguồn chưa báo số lượt xem bằng 0, trái nguyên tắc T041.

**Hướng sửa:** Chỉ nhận số nguyên không âm hợp lệ cho metric dạng đếm, loại boolean và phần thập phân; giá trị không hợp lệ phải có trạng thái lỗi/cách ly rõ ràng. Giữ NULL cho dữ liệu thật sự thiếu. Nếu bỏ qua, tính tỉ lệ và xếp hạng có thể dựa trên số liệu sai.

### P04-08 — P2 — retention_days sai kiểu làm hỏng toàn yêu cầu

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:72–81, 136`; `router.py:18–20`.

Gửi retention_days="không phải số" gây HTTP 500, không tạo QuarantineRecord. Service chỉ kiểm tra thiếu ID/title trước khi ép int() mà không bắt lỗi; dữ liệu sai một trường có thể chặn cả batch.

**Hướng sửa:** Xác thực thời hạn lưu theo kiểu và miền giá trị được quy định trước khi xử lý ghi; trả lỗi trường cụ thể hoặc cách ly từng bản theo hợp đồng batch. Nếu bỏ qua, một bản lỗi ngăn tiếp nhận các bản còn lại và không có dấu vết cách ly như dự kiến.

### P04-09 — P1 — Thời hạn lưu chỉ được ghi lại, chưa được thực thi

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:136, 199–247`; `router.py`, các endpoint đọc records/lineage; `sin_content_workers/worker.py`.

Quan sát thử được đặt thời điểm 10 ngày trước và retention_days=1 vẫn trả nguyên caption qua lineage, is_purged=false. Tìm mã sử dụng retention_days chỉ thấy lưu/hiển thị; không có tác vụ hết hạn hoặc kiểm tra hết hạn khi đọc. Purge hiện chỉ được kích hoạt thủ công bằng ID, trong khi báo cáo P04 khẳng định tuân thủ thời hạn lưu.

**Hướng sửa:** Xác định rõ mốc bắt đầu tính hạn, thực thi quy trình hết hạn có log kiểm toán và ngăn phục vụ nội dung quá hạn trong lúc chờ dọn dữ liệu. Nếu bỏ qua, thông tin được giữ và sử dụng quá thời hạn đã khai báo.

### P04-10 — P1 — Nguồn đã purge vẫn nhận lại payload nhạy cảm

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:98–99, 123–138, 223–231`.

Sau purge thành công, gửi cùng external_id với observation_id mới vẫn nhận HTTP 200. SourceRecord giữ is_purged=true nhưng SourceObservation mới có is_purged=false và raw_payload_json chứa lại caption nhạy cảm. Nhánh sử dụng nguồn hiện hữu không kiểm tra tombstone xóa.

**Hướng sửa:** Từ chối hoặc chặn lưu nội dung mới cho nguồn đã purge theo chính sách tái nhập được phê duyệt; bảo đảm trạng thái xóa nhất quán giữa nguồn và quan sát. Nếu bỏ qua, tác vụ nạp lại có thể khôi phục dữ liệu đã yêu cầu xóa mà trạng thái nguồn vẫn báo đã sạch.

## 9. Ghi chú đối soát P04

Các lỗi đã có không đếm lại: xác thực header P01-01 tiếp tục ảnh hưởng P04; xung đột ID giữa provider tại P03-09 cũng tồn tại trong truy vấn nguồn P04 không lọc provider. Purge chưa xóa nội dung dẫn xuất đã được ghi riêng tại báo cáo P06; kết quả tìm kiếm từ RAM sau purge thuộc P03-04.

Các lỗi cùng loại nhưng có đường ghi riêng ở P03/P04 cần sửa cả hai nơi; không coi sửa một endpoint là đã đóng lỗi endpoint còn lại. Tài liệu này không khẳng định an toàn đồng thời trên PostgreSQL; việc trùng trong một batch đã đủ tái hiện trên SQLite mà không cần giả định tranh chấp.

Chưa sửa mã hoặc đóng lỗi, chưa tạo checkpoint. Cần đối soát nhãn PASS P04 với kết luận này. Trang hành trình tại gốc do Antigravity đồng bộ theo phạm vi được phân công.

## 10. Chi tiết lỗi P05

### P05-01 — P1 — Bộ chuẩn được mã tự sinh nhưng công bố là con người gán nhãn

**Vị trí:** `sin_content_api/src/modules/research/gold_evaluator.py:46–113`; `evals/gold_sets/*.json`; `tests/test_planning_and_gold.py`, bài T051.

GoldDatasetManager tự sinh 90 ứng viên; nhãn và điểm hai reviewer, phân xử, cờ veto, lý do và URL đều được đặt theo chỉ số vòng lặp. Cả ba tệp JSON trùng hoàn toàn với đầu ra bộ sinh. API không nạp các tệp đánh giá được quản lý riêng mà khởi tạo lại từ mã. Các dòng đầu mang EVIDENCE_BACKED và lý do “video thực tế có số liệu” dù nội dung và URL được tạo bằng mẫu. T051 chỉ kiểm tra số lượng và trường hợp lệ, không kiểm tra bằng chứng hai người đánh giá độc lập.

**Hướng sửa:** Gắn nhãn bộ hiện tại là dữ liệu thử tổng hợp; không dùng nó chứng nhận chất lượng thực tế. Nạp bộ chuẩn có nguồn kiểm chứng và kết quả đánh giá độc lập, lưu định danh reviewer, thời điểm, rubric và phân xử; khóa phiên bản tập đánh giá. Nếu bỏ qua, nghiệm thu chất lượng P07 dựa trên nhãn dựng sẵn, trái tiêu chí T051.

### P05-02 — P1 — Planner tạo truy vấn vượt trần chi phí

**Vị trí:** `sin_content_api/src/modules/research/query_planner.py:94–103, 156–175`.

Ngân sách 0,001 USD, đơn giá TikTok khai báo 0,005 USD, planner vẫn tạo một truy vấn trị giá 0,005 USD vì ép max_allowed_queries tối thiểu bằng 1. Ngân sách bằng 0 lại bỏ qua kiểm tra tài chính; tình huống thử tạo 12 truy vấn với ước tính 0,06 USD. Không phát sinh chi phí vendor thật trong lượt kiểm tra.

**Hướng sửa:** Không tạo truy vấn có chi phí khi ngân sách không đủ; trả kế hoạch rỗng có lý do hoặc lỗi ngân sách. Trần 0 phải chặn chi phí dương, đồng thời đối chiếu tổng chi phí cuối cùng với trần. Nếu bỏ qua, chính kế hoạch đã vi phạm điều kiện T052 trước khi được thực thi.

### P05-03 — P1 — Brief chưa duyệt vẫn được dùng tạo kế hoạch nghiên cứu

**Vị trí:** `sin_content_api/src/modules/research/router.py:33–45`.

Router chỉ kiểm tra ID và workspace, không kiểm tra trạng thái phê duyệt. Cả brief DRAFT và CHANGES_REQUESTED đều tạo thành công kế hoạch 12 truy vấn, HTTP 200 và ResearchRun trạng thái PLANNED. Gate P05 yêu cầu đầu vào là approved brief.

**Hướng sửa:** Chỉ nhận phiên bản đã phê duyệt cho luồng nghiên cứu được phép thực thi; nếu cần xem trước bản nháp, biểu diễn rõ trạng thái xem trước và giới hạn thực thi. Nếu bỏ qua, nội dung chưa được duyệt có thể trở thành cấu hình nghiên cứu như đã hợp lệ.

### P05-04 — P1 — workspace trong kế hoạch lấy từ payload, khác workspace lưu DB

**Vị trí:** `sin_content_api/src/modules/research/query_planner.py:167–168`; `router.py:33–35, 48–52`.

Người dùng hợp lệ của workspace A gửi payload.workspace_id="workspace-khac-khong-ton-tai" vẫn nhận HTTP 200. Plan.workspace_id theo payload trong khi ResearchRun.workspace_id theo context A. Đây là sai định danh trong dữ liệu trả về/lưu kế hoạch; chưa phải bằng chứng endpoint đã đọc được brief của workspace khác.

**Hướng sửa:** Gán workspace cho plan từ context đã xác thực và từ chối payload mâu thuẫn hoặc bỏ trường này khỏi đầu vào do client quyết định. Nếu bỏ qua, bên sử dụng kế hoạch nhận hai thông tin chủ sở hữu trái nhau, gây sai định tuyến và kiểm toán.

### P05-05 — P1 — Provider bị cấm hoặc không tồn tại vẫn vào kế hoạch

**Vị trí:** `sin_content_api/src/modules/research/query_planner.py:87–92, 136–145`.

Với mediacrawler hoặc provider-khong-co, API trả HTTP 200 và sinh các QueryVariant mang đúng provider đó, ước tính chi phí 0. get_provider trả ProviderError nhưng planner chỉ bỏ qua việc tính giá nếu không có capabilities, rồi tiếp tục dùng mọi ID đầu vào. Cũng chưa kiểm tra quyền/capability theo chế độ thực thi.

**Hướng sửa:** Từ chối lỗi registry và xác minh khả năng nguồn trước khi tạo variant. Nguồn chưa được phép chỉ được hiển thị dưới trạng thái chưa thể thực thi nếu có nhu cầu dự thảo rõ ràng. Nếu bỏ qua, kế hoạch lưu chứa nguồn bị chính sách cấm hoặc không có bộ xử lý, dù được mô tả là hợp lệ.

### P05-06 — P1 — Kế hoạch bỏ mất điều kiện thời gian và chế độ dữ liệu

**Vị trí:** `sin_content_api/src/modules/research/query_planner.py:19–33, 42–53, 165–176`; `router.py:48–52`.

Hai yêu cầu lookback_days=1/OFFLINE và lookback_days=365/APPROVED_LIVE tạo cùng toàn bộ nội dung kế hoạch khi bỏ ID và thời điểm tạo. Plan được lưu không có lookback_days, mode, synthetic hoặc allow_hypotheses, nên không thể khôi phục yêu cầu thực thi. Schema API còn nhận mode tùy ý, schema_version=999 và tổ hợp APPROVED_LIVE/synthetic=true, trái schema tham chiếu.

**Hướng sửa:** Xác thực enum, phiên bản và quan hệ giữa các trường theo hợp đồng; bảo toàn điều kiện thực thi trong kế hoạch hoặc bản yêu cầu bất biến được liên kết. Nếu bỏ qua, worker không biết giới hạn thời gian hay ranh giới dữ liệu mà người dùng đã chọn.

### P05-07 — P2 — plan_id trả về không đọc lại được qua API

**Vị trí:** `sin_content_api/src/modules/research/query_planner.py:78, 166`; `router.py:48–57, 59–69`.

POST trả plan_id nhưng ORM tự sinh ResearchRun.id khác; GET lại tra theo ResearchRun.id. Gọi GET `/v1/research/plans/{plan_id}` ngay sau POST trả 404. Response không có run_id và không có endpoint liệt kê run để người gọi tìm ID đó.

**Hướng sửa:** Dùng chung ID hoặc trả run_id với đường dẫn truy xuất tương ứng; giữ hợp đồng tạo/đọc nhất quán. Nếu bỏ qua, client không thể mở lại kế hoạch vừa tạo bằng định danh nhận được.

### P05-08 — P2 — Lấy đơn giá đắt nhất gán cho cả nguồn miễn phí

**Vị trí:** `sin_content_api/src/modules/research/query_planner.py:87–101, 136–158`.

Chọn customer_import miễn phí và tiktok_official có đơn giá 0,005 USD, trần 0,005 USD và max_results=2: planner chỉ giữ một truy vấn customer_import nhưng gán chi phí 0,005 USD cho nó. Cách tính vừa báo sai chi phí vừa loại những truy vấn miễn phí không cần loại.

**Hướng sửa:** Tính giá từng variant theo provider thực tế rồi phân bổ dựa trên tổng chi phí và hạn ngạch riêng. Nếu bỏ qua, người dùng thấy chi phí ảo và phạm vi nghiên cứu bị thu hẹp vô lý khi chọn nhiều nguồn.

### P05-09 — P2 — Cắt danh sách theo thứ tự làm mất cân bằng nhóm nhu cầu

**Vị trí:** `sin_content_api/src/modules/research/query_planner.py:124–145, 156–163`.

Yêu cầu PROBLEMS, COMPARISONS và QUESTIONS với max_results=2 chỉ nhận hai variant PROBLEMS. Toàn bộ template của nhóm đầu được sinh trước rồi lấy lát cắt đầu danh sách; thứ tự đầu vào quyết định nhóm nào có cơ hội, không có phân bổ cân bằng hay ghi nhận nhóm bị bỏ. Gate P05 yêu cầu kiểm soát lấy mẫu theo chủ đề/nguồn.

**Hướng sửa:** Phân bổ hạn ngạch giữa các nhóm/nguồn theo quy tắc rõ ràng và ghi nhận phần bị bỏ do trần; có thể xen kẽ variant để hạn chế lệch thứ tự. Nếu bỏ qua, tập dữ liệu thu về thiên lệch dù kế hoạch vẫn liệt kê nhiều nhóm intent.

### P05-10 — P2 — Template ngành hộp cơm được dùng cho serum và ngành khác

**Vị trí:** `sin_content_api/src/modules/research/taxonomy.py`, template COMPARISONS/TRENDS; `query_planner.py:122–130`.

Với brief serum phục hồi da, COMPARISONS sinh “so sánh serum phục hồi da inox 304 và 316” và “nên mua serum phục hồi da hay hộp thủy tinh”. Planner chỉ thay primary_topic vào một bộ template chung; không kiểm tra thuộc tính/ngành hàng để chọn mẫu phù hợp. Các nhóm giữ nhiệt/đóng hộp khác cũng được áp dụng theo cách đó.

**Hướng sửa:** Tách mẫu theo bối cảnh/thuộc tính trong brief hoặc dùng mẫu trung tính khi chưa biết ngành; chỉ áp dụng inox, hộp và giữ nhiệt khi brief hỗ trợ. Nếu bỏ qua, truy vấn lạc đề tiêu tốn hạn ngạch và giảm chất lượng mẫu đầu vào cho P07.

## 11. Ghi chú đối soát P05

Không đếm lại lỗi xác thực nền P01 và lỗi adapter/ngân sách riêng tại P03. P05-02 là sai thuật toán planner khác với Budget.can_spend đã báo ở P03-08; sửa một lớp chưa đủ sửa lớp còn lại.

Không khẳng định có truy cập live, chi phí thật hoặc rò rỉ dữ liệu chéo workspace từ tình huống metadata P05-04. Kết quả test T051 hiện có chỉ xác nhận hình dạng bộ dữ liệu, chưa xác minh nguồn video hay người đánh giá.

Chưa khắc phục hoặc đóng lỗi, chưa tạo checkpoint. Cần cập nhật kết luận nghiệm thu P05 và làm bộ chuẩn thật trước khi lấy kết quả P07 làm bằng chứng chất lượng. Antigravity đồng bộ trang hành trình theo phạm vi được phân công.
