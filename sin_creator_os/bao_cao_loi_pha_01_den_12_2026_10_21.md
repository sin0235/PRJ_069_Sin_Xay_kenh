# Báo cáo lỗi tổng hợp P01–P12

- **Dự án:** PRJ_069 — Hệ thống Content Intelligence.
- **Ngày lập:** 21/10/2026.
- **Người rà soát:** Codex.
- **Mục đích:** Bàn giao các lỗi P01–P12 để khắc phục và nghiệm thu lại.
- **Phạm vi:** Các pha Content Intelligence; không phải các pha A00–A11 của gói phân quyền BAHA-AUTHZ-001.
- **Trạng thái:** Đã rà soát, chưa sửa mã ứng dụng; chưa đủ điều kiện nghiệm thu mười hai pha theo kết quả các lượt rà soát.

> **Lưu ý phiên bản:** Đã có bản bàn giao khắc phục xác thực/RBAC riêng. Phát hiện P01–P11 là lịch sử rà soát, chưa được kiểm tra lại trong lượt P12; 106 là tổng phát hiện đã ghi nhận, không phải xác nhận toàn bộ vẫn còn trên mã mới nhất. P09 kiểm tra logic service riêng và ghi rõ 3 test tích hợp bị chặn 403. P10 chạy 3 test API đạt, bổ sung kiểm tra HTTP/service và đối chiếu frontend; chưa chạy E2E trình duyệt. P11 chạy 4 test nghiệp vụ và 11 test quyền đạt, nhưng các ca bổ sung chưa đáp ứng Gate.

## 1. Tổng hợp mức độ

| Pha | Nội dung | P0 | P1 | P2 | Tổng |
|---|---|---:|---:|---:|---:|
| P01 | Xác thực, workspace, hạ tầng và CI | 1 | 3 | 1 | 5 |
| P02 | Brief, phiên bản, dữ liệu và phê duyệt | 0 | 3 | 3 | 6 |
| P03 | Adapter, import, ngân sách và xử lý lỗi | 0 | 8 | 2 | 10 |
| P04 | Ingestion, xuất xứ, snapshot và thời hạn lưu | 0 | 8 | 2 | 10 |
| P05 | Kế hoạch truy vấn và bộ dữ liệu vàng | 0 | 6 | 4 | 10 |
| P06 | Hiểu nội dung, tín hiệu, gom cụm và ASR | 0 | 6 | 1 | 7 |
| P07 | Truy xuất, chấm điểm và benchmark | 0 | 8 | 3 | 11 |
| P08 | Sinh ý tưởng, trích dẫn, kiểm chứng và phê duyệt | 0 | 9 | 2 | 11 |
| P09 | Kịch bản, kiểm định tuyên bố và phiên bản | 0 | 8 | 1 | 9 |
| P10 | Workbench giao diện và quy trình reviewer | 0 | 6 | 2 | 8 |
| P11 | Phản hồi bài đã đăng, hiệu suất và phân nhóm | 0 | 7 | 2 | 9 |
| P12 | An ninh, độ tin cậy và nghiệm thu phát hành | 0 | 10 | 0 | 10 |
| **Tổng** | | **1** | **82** | **23** | **106** |

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
| P06, kiểm tra lại | 4/4 đạt, mã thoát 0, 10,13 giây | [Nhật ký P06](../../08_kiem_thu/bang_chung/kiem_tra_lai_p06_2026_10_21.txt) |
| P07 | 4/4 đạt, mã thoát 0, 3,04 giây | [Nhật ký P07](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p07_2026_10_21.txt) |
| P08 | 6/6 đạt, mã thoát 0, 3,29 giây | [Nhật ký P08](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p08_2026_10_21.txt) |
| P09 | 1 đạt, 3 thất bại ở approve do 403; mã thoát 1, 5,97 giây | [Nhật ký P09](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p09_2026_10_21.txt) |
| P10 | 3/3 đạt, mã thoát 0, 3,80 giây | [Nhật ký P10](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p10_2026_10_21.txt) |
| P11 | 4/4 đạt, mã thoát 0, 3,95 giây; quyền 11/11 đạt, 4,94 giây | [Nhật ký P11](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p11_2026_10_21.txt), [quyền](../../08_kiem_thu/bang_chung/kiem_thu_tich_hop_quyen_p11_2026_10_21.txt) |
| P12 | 6/6 đạt, 7,28 giây; quyền 11/11 đạt, 5,42 giây; mã thoát 0 | [Nhật ký P12](../../08_kiem_thu/bang_chung/kiem_thu_ra_soat_p12_2026_10_21.txt), [quyền](../../08_kiem_thu/bang_chung/kiem_thu_tich_hop_quyen_p12_2026_10_21.txt) |

Kiểm thử hiện có đạt chưa chứng minh các cổng nghiệm thu hoàn chỉnh. Những tình huống bổ sung đã phát hiện các lỗi chưa được bao phủ:

- [Bằng chứng tái hiện P01–P02](../../08_kiem_thu/bang_chung/tai_hien_loi_p01_p02_2026_10_21.json).
- [Bằng chứng tái hiện P03](../../08_kiem_thu/bang_chung/tai_hien_loi_p03_2026_10_21.json).
- [Báo cáo gốc P01–P02](ra_soat_p01_p02_2026_10_21.md).
- [Báo cáo gốc P03](ra_soat_p03_2026_10_21.md).
- [Báo cáo gốc P04](ra_soat_p04_2026_10_21.md).
- [Báo cáo gốc P05](ra_soat_p05_2026_10_21.md).
- [Báo cáo P06 đã kiểm tra lại](ra_soat_p06_2026_10_21.md).
- [Báo cáo P07](ra_soat_p07_2026_10_21.md).
- [Báo cáo P08](ra_soat_p08_2026_10_21.md).
- [Báo cáo P12](ra_soat_p12_2026_10_21.md).
- [Bằng chứng P12](../../08_kiem_thu/bang_chung/tai_hien_loi_p12_2026_10_21.json).
- [Báo cáo P11](ra_soat_p11_2026_10_21.md).
- [Bằng chứng P11](../../08_kiem_thu/bang_chung/tai_hien_loi_p11_2026_10_21.json).
- [Báo cáo P10](ra_soat_p10_2026_10_21.md).
- [Bằng chứng P10](../../08_kiem_thu/bang_chung/tai_hien_loi_p10_2026_10_21.json).
- [Báo cáo P09](ra_soat_p09_2026_10_21.md).
- [Bằng chứng kiểm tra nghiệp vụ P09](../../08_kiem_thu/bang_chung/tai_hien_loi_p09_2026_10_21.json).
- [Bằng chứng tái hiện P08](../../08_kiem_thu/bang_chung/tai_hien_loi_p08_2026_10_21.json).
- [Bằng chứng tái hiện P07](../../08_kiem_thu/bang_chung/tai_hien_loi_p07_2026_10_21.json).
- [Bằng chứng kiểm tra lại P06](../../08_kiem_thu/bang_chung/tai_hien_lai_loi_p06_2026_10_21.json).
- [Bằng chứng tái hiện P05](../../08_kiem_thu/bang_chung/tai_hien_loi_p05_2026_10_21.json).
- [Bằng chứng tái hiện P04](../../08_kiem_thu/bang_chung/tai_hien_loi_p04_2026_10_21.json).

Các lượt kiểm tra dùng SQLite chỉ trong RAM, thay engine trước khi nhập ứng dụng và bộ kiểm thử. Không thực hiện lệnh xóa bảng trên cơ sở dữ liệu dự án, không gọi nguồn mạng và không dùng credential thật. Tài liệu kế thừa bằng chứng P01–P08 và bổ sung lượt kiểm thử P09, P10, P11 và P12. Không chạy lại các pha trước khi chỉ cập nhật tài liệu.

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

| [ ] | P06-01 | P1 | ASR báo đã kiểm chứng và trả số liệu không được đo |
| [ ] | P06-02 | P1 | Người gọi tự nâng tuyên bố nhân khẩu học thành dữ liệu đã kiểm chứng |
| [ ] | P06-03 | P1 | Xóa nguồn không xóa các bản sao nội dung P06 |
| [ ] | P06-04 | P1 | Viewer có thể ghi dữ liệu và thay đổi cụm |
| [ ] | P06-05 | P1 | Biến thể nhân khẩu học thông thường bị coi là sự thật |
| [ ] | P06-06 | P1 | Có thể gắn caption bịa đặt vào một nguồn thật |
| [ ] | P06-07 | P2 | Gửi lại yêu cầu làm tăng giả số lượng tín hiệu |

| [ ] | P07-01 | P1 | Benchmark dùng đáp án để nâng hoặc hạ điểm xếp hạng |
| [ ] | P07-02 | P1 | Endpoint công khai đọc đường dẫn JSON ngoài thư mục gold |
| [ ] | P07-03 | P1 | Thiếu lọc quyền sử dụng và phân biệt dữ liệu tổng hợp |
| [ ] | P07-04 | P1 | intent_group và need_category bị nhận rồi bỏ qua |
| [ ] | P07-05 | P1 | Bằng chứng tự khai hoặc suy luận bị nâng thành quan sát chắc chắn |
| [ ] | P07-06 | P1 | Thiếu hoặc sai thời gian vẫn tạo tăng trưởng đã kiểm chứng |
| [ ] | P07-07 | P1 | Brief chưa duyệt vẫn được chấm điểm và truy xuất |
| [ ] | P07-08 | P1 | Nội dung hoàn toàn lạc đề vẫn vào danh sách kết quả |
| [ ] | P07-09 | P2 | Đáp ứng giới hạn sản xuất lại bị coi là vi phạm |
| [ ] | P07-10 | P2 | limit âm được chấp nhận và trả gần toàn bộ kết quả |
| [ ] | P07-11 | P2 | Phân rã điểm không có lý do cho từng thành phần |

| [ ] | P08-01 | P1 | ID thật đủ để thông qua quote và số liệu bịa |
| [ ] | P08-02 | P1 | Nguồn đã purge, synthetic hoặc không có quyền vẫn thành bằng chứng thật |
| [ ] | P08-03 | P1 | Bỏ qua ứng viên và nhóm nhu cầu đã chọn |
| [ ] | P08-04 | P1 | Brief nháp được dùng và brief không tồn tại làm bỏ qua brand safety |
| [ ] | P08-05 | P1 | Viewer có thể tự sinh và phê duyệt ý tưởng |
| [ ] | P08-06 | P1 | APPROVE không kiểm chứng lại thẻ và trạng thái bằng chứng |
| [ ] | P08-07 | P2 | Mất nội dung trích dẫn và metadata sau khi lưu thẻ |
| [ ] | P08-08 | P2 | Bộ sửa JSON chưa kiểm schema và có thể đổi nội dung chuỗi |
| [ ] | P08-09 | P1 | Mẫu sinh tự thêm tuyên bố định lượng và ý tưởng sai ngành |
| [ ] | P08-10 | P1 | Không có bằng chứng vẫn xác nhận card mang nhãn EVIDENCE_BACKED |
| [ ] | P08-11 | P1 | Chủ đề cấm trong target_need không được kiểm tra |

| [ ] | P09-01 | P1 | Chung một từ khóa đủ để xác minh cả tuyên bố sai |
| [ ] | P09-02 | P1 | AllowedFact chưa được duyệt vẫn được sử dụng như sự thật đã duyệt |
| [ ] | P09-03 | P1 | Bỏ sót phần trăm, ngôn ngữ khác và tuyên bố so sánh |
| [ ] | P09-04 | P1 | Bản SUPERSEDED hoặc bản đã duyệt bị REJECT vẫn có thể sửa đè |
| [ ] | P09-05 | P1 | Sai dung sai thời lượng vẫn READY_FOR_REVIEW và được duyệt |
| [ ] | P09-06 | P1 | Đường edit nhận kịch bản rỗng, hook rỗng và thời lượng âm |
| [ ] | P09-07 | P1 | Không kiểm tra điều kiện ý tưởng, brief và giới hạn thương hiệu |
| [ ] | P09-08 | P2 | Tham chiếu fact chưa khóa phiên bản tài liệu và SKU |
| [ ] | P09-09 | P1 | Tiêu đề script không được kiểm tra tuyên bố |
| [ ] | P10-01 | P1 | Workbench vẫn dùng dữ liệu mẫu, chưa có luồng duyệt qua giao diện |
| [ ] | P10-02 | P1 | Bỏ expected_version vẫn phê duyệt thành công |
| [ ] | P10-03 | P1 | Kiểm tra phiên bản rồi ghi không ngăn hai phiên ghi đè nhau |
| [ ] | P10-04 | P1 | Nhãn đang thịnh hành chỉ dựa vào tổng lượt xem của một snapshot |
| [ ] | P10-05 | P1 | Snapshot trong tương lai được coi là hợp lệ |
| [ ] | P10-06 | P1 | Lưu trạng thái duyệt và audit bằng hai transaction riêng |
| [ ] | P10-07 | P2 | Lịch sử thẻ lấy cả sự kiện của thẻ khác nhắc ID trong lý do |
| [ ] | P10-08 | P2 | Thiếu lượt xem làm mất cả chỉ số còn có và thời gian quan sát |
| [ ] | P11-01 | P1 | Trả số liệu cố định dưới nhãn hiệu suất chính thức đã xác thực |
| [ ] | P11-02 | P1 | Người gọi tự khai scope OAuth và kết nối hết hạn vẫn có hiệu lực |
| [ ] | P11-03 | P1 | Chỉ số chưa biết bị đổi thành số 0 và vận tốc có vẻ hợp lệ |
| [ ] | P11-04 | P1 | Tính lại cùng cặp snapshot làm lệch trung bình hiệu suất |
| [ ] | P11-05 | P1 | Thông tin quảng cáo bị mất khi nhập và lọt vào nhóm tự nhiên |
| [ ] | P11-06 | P1 | Nguồn synthetic hoặc đã purge vẫn được dùng cho phản hồi hiệu suất |
| [ ] | P11-07 | P1 | Chưa có luồng nối bài đã đăng với bản kịch bản và phản hồi học tập |
| [ ] | P11-08 | P2 | Đổi ngầm khoảng thời gian làm sai vận tốc ở hai snapshot gần nhau |
| [ ] | P11-09 | P2 | Bộ lọc cohort chỉ được ghi vào nhãn mà không lọc kết quả |
| [ ] | P12-01 | P1 | Cache tác vụ trả artifact của workspace khác |
| [ ] | P12-02 | P1 | Mất cache RAM khiến tác vụ đã hoàn thành bị tạo và trừ phí lại |
| [ ] | P12-03 | P1 | Ledger cũ cho phép vượt ngân sách bằng gọi lại hoặc đổi payload |
| [ ] | P12-04 | P1 | Hai phiên giữ chỗ vượt cap nhưng bảng ngân sách ghi thiếu |
| [ ] | P12-05 | P1 | Bài thử timeout chưa thực thi công việc hoặc side effect downstream |
| [ ] | P12-06 | P1 | Backup cam kết đã tẩy secrets nhưng chỉ thay mật khẩu một cột |
| [ ] | P12-07 | P1 | Restore xóa database đích trước khi biết backup có hợp lệ |
| [ ] | P12-08 | P1 | Đánh giá prompt tự đếm nhãn ghi sẵn, không đo hệ thống hay thẩm định người |
| [ ] | P12-09 | P1 | Kiểm toán phụ thuộc trả số vi phạm bằng 0 mà chưa kiểm tra |
| [ ] | P12-10 | P1 | Hồ sơ phát hành mở Gate P13 dù chưa có bằng chứng đạt Gate P12 |


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

## 12. Chi tiết lỗi P06

### P06-01 — P1 — ASR báo đã kiểm chứng và trả số liệu không được đo

**Vị trí:** `sin_content_api/src/modules/understanding/asr_evaluator.py:58–65`.

Chỉ cần gọi `GET /v1/understanding/asr-status?licensed_audio_count=1`, API trả `VERIFIED`, `offline_stub=false`, WER 14,5% và độ chính xác thuật ngữ 92%. Không có audio, hồ sơ cấp phép hoặc kết quả đánh giá nào được kiểm tra; hai con số được gán cố định trong mã. Điều này trái tiêu chí T063 và làm sai báo cáo năng lực.

**Sửa tối thiểu:** Bỏ nhánh số liệu mẫu. Giữ `UNVERIFIED` và chỉ số rỗng cho đến khi máy chủ có kết quả đánh giá gắn với tập audio đã xác minh quyền sử dụng. Số lượng do người gọi cung cấp không phải bằng chứng nghiệm thu.

### P06-02 — P1 — Người gọi tự nâng tuyên bố nhân khẩu học thành dữ liệu đã kiểm chứng

**Vị trí:** `sin_content_api/src/modules/understanding/service.py:59–62`; `src/schemas/contracts.py`, thực thể `EvidenceExcerptCreate`.

Gửi “90% người xem là dân văn phòng” cùng `has_official_analytics=true`, không nộp báo cáo, vẫn nhận `OBSERVED_DIRECT`, confidence 0,95 và không có bản ghi suy luận chưa kiểm chứng. Cờ trong payload được truyền thẳng vào bộ phân loại, làm vô hiệu rào chắn T062.

**Sửa tối thiểu:** Xác định trạng thái kiểm chứng ở máy chủ từ hồ sơ Analytics được phép truy cập, có liên kết nguồn và đối chiếu đúng tuyên bố. Khi thiếu hồ sơ, luôn giữ nhãn chưa kiểm chứng.

### P06-03 — P1 — Xóa nguồn không xóa các bản sao nội dung P06

**Vị trí:** `sin_content_api/src/modules/understanding/service.py:47–75, 103–124`; đối chiếu `src/modules/ingestion/service.py:221–232`.

Sau khi tạo trích đoạn và gom cụm, gọi purge thành công vẫn đọc được “Hộp bị tràn canh” qua `/signals` và `/clusters`; các trích đoạn của nguồn vẫn tồn tại. Lượt kiểm tra lại ghi nhận 6 trích đoạn sau khi thử tiếp nhận thêm từ nguồn đã purge. P06 tạo thêm bản sao nội dung nhưng chưa tích hợp vào vòng đời xóa của P04. API còn nhận thêm trích đoạn từ chính nguồn đã purge với HTTP 200.

**Sửa tối thiểu:** Xóa hoặc làm rỗng nội dung dẫn xuất và liên kết tương ứng trong cùng giao dịch purge, cập nhật số lượng cụm, đồng thời từ chối trích xuất từ nguồn đã purge. Nếu bỏ qua, nội dung cần xóa vẫn được lưu và tiếp tục đưa vào truy xuất.

### P06-04 — P1 — Viewer có thể ghi dữ liệu và thay đổi cụm

**Vị trí:** `sin_content_api/src/modules/understanding/router.py:25, 53`.

Hai endpoint ghi chỉ kiểm tra membership, không kiểm tra vai trò. Thành viên `viewer` gọi `/extract-signals` và `/cluster` đều nhận HTTP 200, tạo tín hiệu và cụm thành công. Đây là đường ghi vượt quyền đọc của thành viên, khác với các endpoint ingestion đã dùng `require_role`.

**Sửa tối thiểu:** Áp dụng kiểm tra quyền ghi phù hợp bằng cơ chế phân quyền hiện có cho hai endpoint; bổ sung trường hợp viewer bị từ chối. Nếu bỏ qua, người chỉ có quyền xem vẫn có thể làm thay đổi dữ liệu nghiên cứu.

### P06-05 — P1 — Biến thể nhân khẩu học thông thường bị coi là sự thật

**Vị trí:** `sin_content_api/src/modules/understanding/need_extractor.py:75–79, 119–138, 187–196`.

Không có Analytics, cả “Khán giả phần lớn là dân văn phòng”, “Người xem đa số là phụ nữ” và “90 phần trăm người xem là dân văn phòng” đều được lưu `OBSERVED_DIRECT`. Biểu thức nhận diện chỉ bao phủ một số cách nói; nhánh mặc định biến phần bị bỏ sót thành dữ liệu quan sát, confidence 0,7 hoặc 0,95. T062 hiện chỉ kiểm tra câu có đúng cấu trúc đã mã hóa.

**Sửa tối thiểu:** Xử lý các cách diễn đạt đã tái hiện và ngăn nhánh mặc định khẳng định nhân khẩu học khi chưa có bằng chứng. Bổ sung các biến thể này vào kiểm thử; không tuyên bố regex bao phủ toàn bộ ngôn ngữ tự nhiên. Nếu bỏ qua, P07 sẽ xếp hạng dựa trên đặc điểm khán giả chưa được chứng minh.

### P06-06 — P1 — Có thể gắn caption bịa đặt vào một nguồn thật

**Vị trí:** `sin_content_api/src/modules/understanding/service.py:30–54`.

Nguồn có caption “Hộp bị tràn canh”, nhưng gửi trích đoạn loại `CAPTION` là “Một tuyên bố hoàn toàn bịa đặt không có trong nguồn” vẫn được nhận và sinh `OBSERVED_DIRECT`. Dịch vụ chỉ kiểm tra nguồn tồn tại trong workspace; không xác thực trích đoạn thực sự thuộc nguồn. Liên kết bằng ID vì vậy chưa đủ bảo đảm tiêu chí bằng chứng truy được về nguồn.

**Sửa tối thiểu:** Với caption, lấy nội dung từ nguồn hoặc đối chiếu trích đoạn với bản quan sát đã lưu. Với bình luận và transcript, yêu cầu liên kết đến bản ghi tương ứng có xuất xứ; nội dung nhập thủ công chưa đối soát phải thể hiện trạng thái đó. Nếu bỏ qua, văn bản tùy ý có thể xuất hiện như bằng chứng của video thật.

### P06-07 — P2 — Gửi lại yêu cầu làm tăng giả số lượng tín hiệu

**Vị trí:** `sin_content_api/src/modules/understanding/service.py:47–78`.

Gửi đúng cùng nguồn, loại trích đoạn và nội dung hai lần tạo hai `EvidenceExcerpt` và hai bộ `NeedSignal` có ID khác nhau. Bộ gom cụm đếm các tín hiệu này độc lập, nên việc gửi lại sau lỗi kết nối làm tăng số bằng chứng cho cùng một phản hồi.

**Sửa tối thiểu:** Dùng định danh quan sát/bình luận ổn định hoặc khóa yêu cầu chống trùng, kèm ràng buộc duy nhất và trả lại kết quả cũ khi gửi lại. Không dùng riêng nội dung làm khóa vì hai người có thể bình luận giống nhau. Nếu bỏ qua, số lượng tín hiệu và xếp hạng P07 sẽ bị thổi phồng.

## 13. Ghi chú đối soát P06

Không sửa mã ứng dụng hoặc tạo thêm bài kiểm thử trong kho mã; không đánh giá production, PostgreSQL, tải đồng thời hay nhà cung cấp trực tiếp. Các tình huống chạy qua FastAPI TestClient và bộ trích xuất hiện có. Không thấy đường thực thi công cụ trong luồng P06 hiện tại; điều này không chứng minh khả năng chống prompt injection cho tích hợp LLM tương lai.

P06-03 kiểm tra bản sao nội dung dẫn xuất, khác với P04-10 về tái nhập quan sát gốc và P03-04 về kho RAM. Lỗi xác thực nền đã ghi ở P01 không được đếm lại. Không tạo checkpoint mới. Antigravity đồng bộ trang hành trình tại gốc và đối soát nhãn PASS theo phạm vi được phân công.

## 14. Chi tiết lỗi P07

### P07-01 — P1 — Benchmark dùng đáp án để nâng hoặc hạ điểm xếp hạng

**Vị trí:** `sin_content_api/src/modules/retrieval/ranking_service.py:159–170`; `scorer.py:210–221`.

Benchmark truyền adjudication_label và cờ veto chuẩn vào scorer trước khi xếp hạng. RELEVANT nâng các điểm audience/evidence/brand, IRRELEVANT hạ các điểm đó. Giữ nguyên nội dung, chỉ đổi nhãn đáp án làm overall_score đổi từ 7,9 xuống 3,875. Cả ba bộ hiện trả Precision@10=1,0 nhưng không phải đánh giá độc lập; luồng này cũng không chạy đường HybridSearchEngine được dùng bởi endpoint search.

**Hướng sửa:** Chấm và xếp hạng khi không nhìn nhãn chuẩn, sau đó mới so kết quả với nhãn để tính precision. Đánh giá đúng đường truy xuất/xếp hạng dùng thật trên bộ chuẩn có nguồn gốc hợp lệ. Nếu bỏ qua, điểm benchmark cao không phản ánh khả năng tìm nội dung liên quan.

### P07-02 — P1 — Endpoint công khai đọc đường dẫn JSON ngoài thư mục gold

**Vị trí:** `sin_content_api/src/modules/retrieval/router.py:73–82`; `ranking_service.py:127–132`.

dataset_name do người gọi điều khiển được ghép thẳng vào đường dẫn, không xác minh đường dẫn sau chuẩn hóa. Gọi không có header xác thực với đường dẫn tuyệt đối đến tệp thử ngoài gold_sets nhận HTTP 200, trả brief_name và tiêu đề ứng viên từ tệp đó. Endpoint vì vậy không bị giới hạn ở danh sách dataset được phép. Tái hiện chỉ chứng minh đọc và trả trường từ JSON có cấu trúc phù hợp; không khẳng định mọi loại tệp đều đọc được.

**Hướng sửa:** Chọn dataset bằng ID trong danh mục cho phép; xác minh đường dẫn cuối nằm trong thư mục được chỉ định và kiểm tra quyền đánh giá. Nếu bỏ qua, người ngoài có thể yêu cầu máy chủ xử lý và tiết lộ dữ liệu JSON ngoài phạm vi dataset dự kiến.

### P07-03 — P1 — Thiếu lọc quyền sử dụng và phân biệt dữ liệu tổng hợp

**Vị trí:** `sin_content_api/src/modules/retrieval/hybrid_search.py:62–70, 126–134`.

Search chỉ lọc workspace, is_purged và tùy chọn provider. Nguồn thử có rights_basis=NOT_GRANTED vẫn nằm trong kết quả; nguồn synthetic=true cũng được trả mà response không mang cờ synthetic. Do đó bên nhận không thể phân biệt dữ liệu thử với dữ liệu thật từ hợp đồng kết quả này. Gate P07 yêu cầu lọc nguồn không có quyền trước khi xếp hạng.

**Hướng sửa:** Kiểm tra quyền sử dụng/trạng thái nguồn trước ranking; áp dụng chế độ dữ liệu thật hoặc dữ liệu thử rõ ràng và bảo toàn cờ nguồn gốc trong response. Nếu bỏ qua, nội dung chưa được phép sử dụng và dữ liệu tổng hợp có thể đi vào đề xuất tiếp theo.

### P07-04 — P1 — intent_group và need_category bị nhận rồi bỏ qua

**Vị trí:** `sin_content_api/src/schemas/contracts.py:293–299`; `ranking_service.py:103–109`; `hybrid_search.py:50–58`.

Yêu cầu QUESTIONS/MICROWAVE_SAFETY vẫn trả cả bốn nguồn thử, dù không có tín hiệu nào thuộc bộ lọc này. Hai trường có trong DTO nhưng không được truyền xuống engine và engine không lọc NeedSignal.

**Hướng sửa:** Truy vấn qua tín hiệu nhu cầu cùng workspace để áp dụng bộ lọc đã nhận; nếu chưa hỗ trợ, trả lỗi rõ thay vì trả kết quả như đã lọc. Nếu bỏ qua, dữ liệu được đề xuất không tuân theo nhóm nhu cầu người dùng chọn.

### P07-05 — P1 — Bằng chứng tự khai hoặc suy luận bị nâng thành quan sát chắc chắn

**Vị trí:** `sin_content_api/src/modules/retrieval/hybrid_search.py:79–83, 108–110, 133`; `ranking_service.py:68–78`; `scorer.py:164–174`.

Nguồn chỉ có excerpt “90% người xem là dân văn phòng”, NeedSignal tương ứng INFERRED_UNVERIFIED và confidence=0,3, vẫn được search gắn EVIDENCE_BACKED và observed_evidence_score=9,5. Chỉ cần tồn tại excerpt là engine gắn mức bằng chứng cao và truyền OBSERVED_DIRECT, bỏ qua trạng thái tín hiệu. Endpoint score cũng nhận candidate_id không tồn tại cùng cờ EVIDENCE_BACKED tự khai và trả APPROVED_RANKED; chưa có tham chiếu bằng chứng xác minh các cờ đó. Kết quả search không có ID excerpt/tín hiệu để đối soát trích dẫn cụ thể.

**Hướng sửa:** Tính mức bằng chứng từ nguồn/tín hiệu được kiểm tra, bảo toàn observed/inferred và confidence, trả ID trích dẫn. Nếu hỗ trợ chấm điểm văn bản chưa lưu, kết quả phải thể hiện mức chưa xác minh. Nếu bỏ qua, giới hạn suy luận P06 bị mất khi vào ranking và phía sau có thể coi giả định là bằng chứng.

### P07-06 — P1 — Thiếu hoặc sai thời gian vẫn tạo tăng trưởng đã kiểm chứng

**Vị trí:** `sin_content_api/src/modules/retrieval/scorer.py:69–104`; `schemas/contracts.py:286`.

Hai snapshot 10 và 100 views nhưng không có observed_at, có cùng observed_at hoặc có chuỗi ngày sai đều trả growth_velocity=90, CALCULATED, VERIFIED_MULTI_SNAPSHOT. Khi không có khoảng thời gian hợp lệ, hàm tự gán delta_days=1; chỉ đếm số snapshot đã được coi là đủ bằng chứng.

**Hướng sửa:** Xác thực metric, thời gian, thứ tự và tính tương đương nguồn quan sát; chỉ tính khi có hai mốc hợp lệ khác nhau. Thiếu dữ liệu phải giữ NOT_AVAILABLE và lý do cụ thể, không mặc định một ngày. Nếu bỏ qua, hệ thống công bố tăng trưởng không được dữ liệu hỗ trợ.

### P07-07 — P1 — Brief chưa duyệt vẫn được chấm điểm và truy xuất

**Vị trí:** `sin_content_api/src/modules/retrieval/ranking_service.py:58–66, 95–103`.

Đổi brief thử sang DRAFT, cả score và search vẫn nhận HTTP 200. Service chỉ kiểm tra ID/workspace, không kiểm tra trạng thái phê duyệt, dù hợp đồng đầu vào P07 yêu cầu phiên bản brief được duyệt.

**Hướng sửa:** Kiểm tra phiên bản được phép dùng trước ranking; nếu có chế độ xem trước bản nháp, biểu diễn và giới hạn riêng. Nếu bỏ qua, kết quả nghiên cứu có thể dựa trên giới hạn thương hiệu chưa được chấp thuận.

### P07-08 — P1 — Nội dung hoàn toàn lạc đề vẫn vào danh sách kết quả

**Vị trí:** `sin_content_api/src/modules/retrieval/hybrid_search.py:99–138`; `scorer.py:147–187, 245`.

Brief hộp cơm cho dân văn phòng, query “hộp cơm”, nhưng nguồn “Bóng đá thể thao giải ngoại hạng” vẫn được trả với hybrid_score=0,2575, overall_score=5,15. Nguồn không có từ truy vấn, chủ đề phù hợp hay ngữ cảnh khán giả; engine chỉ loại veto, không có điều kiện phù hợp tối thiểu trước ranking. Việc cho điểm thấp chưa đáp ứng bộ lọc bắt buộc đối với nội dung không có ngữ cảnh liên quan theo Gate P07.

**Hướng sửa:** Áp dụng quy tắc phù hợp tối thiểu có thể giải thích trước khi xếp hạng; chấp nhận trả ít kết quả hoặc không có bằng chứng. Nếu bỏ qua, danh sách thiếu nội dung tốt sẽ bị lấp bởi video không liên quan và pha sinh ý tưởng nhận đầu vào sai chủ đề.

### P07-09 — P2 — Đáp ứng giới hạn sản xuất lại bị coi là vi phạm

**Vị trí:** `sin_content_api/src/modules/retrieval/scorer.py:198–205`.

Brief yêu cầu “thời lượng dưới 60s”. Nội dung ghi đúng “thời lượng dưới 60s” bị cho feasibility=3, trong khi nội dung không nói thời lượng được 8. Hàm đang xem việc xuất hiện nguyên văn điều kiện là vi phạm điều kiện đó.

**Hướng sửa:** So sánh thuộc tính sản xuất thực tế với ràng buộc, hoặc giữ trạng thái chưa đủ thông tin khi chưa phân tích được; không dùng khớp nguyên văn để suy ra vi phạm. Nếu bỏ qua, ứng viên đáp ứng yêu cầu bị xếp dưới ứng viên chưa biết có đáp ứng hay không.

### P07-10 — P2 — limit âm được chấp nhận và trả gần toàn bộ kết quả

**Vị trí:** `sin_content_api/src/schemas/contracts.py:298`; `hybrid_search.py:138`.

limit=-1 nhận HTTP 200 và trả ba trong bốn nguồn do phép cắt danh sách Python `results[:-1]`. Không có giới hạn dưới/trên ở DTO; engine còn nạp và chấm toàn bộ nguồn trước khi cắt.

**Hướng sửa:** Quy định limit nguyên dương với trần hợp lý, từ chối giá trị ngoài miền; giới hạn tập ứng viên trước các bước tốn tài nguyên theo thiết kế truy xuất. Nếu bỏ qua, đầu vào sai tạo kết quả bất ngờ và thiếu kiểm soát khối lượng trả về.

### P07-11 — P2 — Phân rã điểm không có lý do cho từng thành phần

**Vị trí:** `sin_content_api/src/schemas/contracts.py:266–277`; `scorer.py:233–245`.

Response chỉ có số điểm, cờ veto và trạng thái velocity, không có lý do hoặc tham chiếu cho audience/evidence/brand/novelty/feasibility. T070 yêu cầu all component reasons available. Một tổng điểm lặp lại được chưa đủ để người duyệt biết vì sao hệ thống cho 9,5 về bằng chứng hoặc 3 về tính khả thi.

**Hướng sửa:** Trả lý do và dữ liệu đầu vào giải thích từng thành phần, gắn tham chiếu nguồn khi có; kiểm thử lý do đúng nhánh. Nếu bỏ qua, người dùng không thể đối soát hoặc phát hiện lý do sai của xếp hạng.

## 15. Ghi chú đối soát P07

Không đếm lại dữ liệu vàng tự sinh của P05-01; P07-01 là lỗi riêng khi thuật toán đánh giá nhìn trước đáp án. Không đếm lại giả danh nền P01 hay lỗi nội dung P06; P07-05 là bước ranking làm mất trạng thái kiểm chứng đã có.

Mã hiện tại dùng Jaccard token và cosine trên tập n-gram ký tự trong bộ nhớ; chưa xác nhận BM25 hoặc pgvector/embedding như báo cáo nghiệm thu mô tả. Không thực hiện đo tải hoặc kiểm chứng PostgreSQL; chỉ khẳng định các tình huống và đường mã đã đọc/chạy. Chưa kiểm tra hệ thống production hoặc quyền truy cập tệp thật nhạy cảm.

Chưa sửa mã, chưa đóng lỗi hoặc tạo checkpoint. Cần nghiệm thu lại benchmark với nhãn độc lập và đúng đường truy xuất trước khi dùng kết quả P07 cho P08. Antigravity đối soát nhãn PASS và đồng bộ trang hành trình theo phạm vi được phân công.

## 16. Chi tiết lỗi P08

### P08-01 — P1 — ID thật đủ để thông qua quote và số liệu bịa

**Vị trí:** `sin_content_api/src/modules/ideation/verifier.py:50–129`.

Trích đoạn chỉ có “Da hơi khô sau khi rửa mặt”. Gửi đúng ID nhưng quote_text là câu không có trong nguồn, hook tự nhận 99.999.999 lượt xem và giữ ẩm 999 giờ, verifier vẫn trả is_valid=true, verified_excerpts_count=1, READY_FOR_REVIEW. Hàm chỉ đối chiếu ID/workspace và URL, không đối chiếu quote hoặc số liệu với snapshot/tài liệu.

**Hướng sửa:** Kiểm tra quote nguyên văn với excerpt, kiểm tra từng số liệu/tuyên bố với nguồn phù hợp và chỉ gắn verified cho phần thực sự được xác minh. Nếu bỏ qua, T081 không chặn được bịa nội dung khi người gọi dùng một ID nguồn có thật.

### P08-02 — P1 — Nguồn đã purge, synthetic hoặc không có quyền vẫn thành bằng chứng thật

**Vị trí:** `sin_content_api/src/modules/ideation/ideation_service.py:46–59, 112–124`; `verifier.py:78–106`; `generator.py:185–193`.

Lần lượt đặt nguồn thử is_purged=true, synthetic=true hoặc rights_basis=NOT_GRANTED, mỗi lần generate đều trả SUCCESS, EVIDENCE_BACKED, READY_FOR_REVIEW và synthetic=false. Việc chọn bằng chứng chỉ lọc workspace; verifier không đánh giá trạng thái nguồn. Lượt thử có excerpt của nguồn đã đánh dấu purge để kiểm tra trạng thái, không khẳng định P04 đã xóa toàn bộ excerpt.

**Hướng sửa:** Lọc nguồn được phép dùng, chưa purge/hết hạn và đúng chế độ dữ liệu trước sinh; verifier kiểm tra lại quyền/trạng thái tại thời điểm xác minh. Bảo toàn synthetic và phân biệt suy luận với quan sát. Nếu bỏ qua, luồng P08 tiếp tục sử dụng dữ liệu đã bị thu hồi hoặc dữ liệu thử như bằng chứng thị trường.

### P08-03 — P1 — Bỏ qua ứng viên và nhóm nhu cầu đã chọn

**Vị trí:** `sin_content_api/src/schemas/contracts.py`, thực thể IdeaGenerationRequest; `ideation_service.py:46–80`.

Gửi candidate_ids=["khong-ton-tai"] và selected_need_categories=["NHU_CAU_KHONG_KHOP"] vẫn sinh một thẻ từ excerpt bất kỳ trong workspace. Hai trường được nhận nhưng không dùng; service không lấy danh sách đã xếp hạng của P07, mà nạp toàn bộ excerpt.

**Hướng sửa:** Đối chiếu ứng viên/nhu cầu thuộc cùng workspace và brief, lấy đúng tập bằng chứng được chọn hoặc trả lỗi/thiếu bằng chứng. Nếu bỏ qua, ý tưởng không dựa trên cơ hội người dùng chọn và có thể bỏ qua bộ lọc đã làm ở P07.

### P08-04 — P1 — Brief nháp được dùng và brief không tồn tại làm bỏ qua brand safety

**Vị trí:** `sin_content_api/src/modules/ideation/ideation_service.py:38–44, 180–186`; `verifier.py:38–48`.

Generate từ brief DRAFT nhận HTTP 200 và sinh thẻ. Verify với brief_version_id không tồn tại vẫn truyền brief=None vào verifier; hook chứa “kem trộn” vốn bị brief thật cấm được trả is_valid=true vì toàn bộ kiểm tra brand safety bị bỏ qua khi thiếu brief.

**Hướng sửa:** Bắt buộc resolve brief thuộc workspace và trạng thái được phép trước sinh/xác minh; trả 404 hoặc lỗi trạng thái thay vì tiếp tục khi không có brief. Nếu bỏ qua, card được xác nhận dù không có cấu hình thương hiệu làm căn cứ.

### P08-05 — P1 — Viewer có thể tự sinh và phê duyệt ý tưởng

**Vị trí:** `sin_content_api/src/modules/ideation/router.py:16–25, 63–73`.

Generate và review chỉ kiểm tra membership, không kiểm tra quyền hành động. Tài khoản viewer tự generate rồi APPROVE cùng thẻ nhận HTTP 200 và trạng thái APPROVED. Đây là lỗi quyền ở endpoint P08, độc lập với việc giả danh bằng header đã báo tại P01.

**Hướng sửa:** Kiểm tra quyền sinh và quyền duyệt theo chính sách đã thống nhất trước khi thay đổi dữ liệu. Nếu bỏ qua, người chỉ có quyền xem có thể xuất bản quyết định duyệt như reviewer.

### P08-06 — P1 — APPROVE không kiểm chứng lại thẻ và trạng thái bằng chứng

**Vị trí:** `sin_content_api/src/modules/ideation/ideation_service.py:209–227`.

Thẻ thử ở NEEDS_EVIDENCE, mang EVIDENCE_BACKED nhưng không có ID trích dẫn, vẫn được APPROVE thành công. Hàm chỉ đổi status; không gọi verifier, kiểm tra điều kiện chuyển trạng thái hoặc kiểm tra nguồn còn hợp lệ. Lỗi này tồn tại ngay cả với người có quyền duyệt hợp lệ.

**Hướng sửa:** Kiểm tra điều kiện trước phê duyệt và xác minh bằng chứng hiện tại; từ chối thẻ chứng nhận bằng chứng nhưng thiếu nguồn, nguồn bị thu hồi hoặc nội dung không hợp lệ. Nếu bỏ qua, hàng đợi kiểm chứng có thể bị vượt qua chỉ bằng một lệnh review.

### P08-07 — P2 — Mất nội dung trích dẫn và metadata sau khi lưu thẻ

**Vị trí:** `sin_content_api/src/modules/ideation/ideation_service.py:87–97, 112–146, 307–322`; `src/models/entities.py:313–330`; schemas IdeaCardOut.

Generator tạo citations gồm quote_text, URL, observed/inferred và confidence, nhưng service chỉ lưu evidence_excerpt_ids_json. GET card không có citations và ORM không có trường hoặc bảng lưu các nội dung đó. ID còn được giữ, nhưng không lưu được chính trích dẫn/metadata đã dùng để kiểm chứng nếu nguồn thay đổi sau này.

**Hướng sửa:** Lưu và trả các liên kết bằng chứng có nội dung/phiên bản cần thiết để đối soát, giữ vòng đời xóa phù hợp; không chỉ bỏ citations sau lần kiểm tra đầu. Nếu bỏ qua, người duyệt và các pha sau thiếu dấu vết của phát biểu từng được xác nhận.

### P08-08 — P2 — Bộ sửa JSON chưa kiểm schema và có thể đổi nội dung chuỗi

**Vị trí:** `sin_content_api/src/modules/ideation/generator.py:20–69`; `ideation_service.py:73–98`.

parse_and_repair_llm_json nhận nguyên số 42 hoặc danh sách chỉ có confidence_tier="SAI_ENUM" mà không báo lỗi schema. Khi sửa trailing comma, regex đổi cả từ True trong chuỗi tiêu đề thành true. Tìm nơi gọi cho thấy luồng generate hiện không dùng bộ parser này; các test sửa cú pháp vì vậy chưa chứng minh cổng runtime cho kiểu đầu ra, enum hoặc số lượng theo T083.

**Hướng sửa:** Tách sửa cú pháp khỏi xác thực schema, kiểm tra mô hình và số lượng trước chấp nhận; chỉ sửa token ngoài chuỗi, bảo toàn văn bản trích dẫn. Nối cổng kiểm tra vào đường thực thi và trả lỗi có cấu trúc sau số lần sửa được giới hạn. Nếu bỏ qua, JSON đọc được vẫn có thể không phải thẻ hợp lệ hoặc bị đổi nội dung.

### P08-09 — P1 — Mẫu sinh tự thêm tuyên bố định lượng và ý tưởng sai ngành

**Vị trí:** `sin_content_api/src/modules/ideation/generator.py:104–165, 170–196`.

Với brief serum và chỉ một phản hồi về da khô, generate tạo hook “Tiết kiệm 1.5 triệu mỗi tháng ... với Serum phục hồi” và “So sánh hộp cơm thường vs Serum phục hồi: Sau 6 tiếng ...”. Cả hai vẫn là EVIDENCE_BACKED/READY_FOR_REVIEW với điểm đặt sẵn. Mẫu nội dung không được lựa chọn từ bằng chứng, mục tiêu hoặc ngành; một ID được gắn luân phiên chưa hỗ trợ những tuyên bố được sinh.

**Hướng sửa:** Chỉ sinh phát biểu được bằng chứng hoặc dữ kiện sản phẩm cho phép hỗ trợ; kiểm tra tính phù hợp ngành và mức suy luận. Mẫu offline chưa kiểm chứng phải được nhận diện đúng, không gắn bằng chứng chắc chắn cho số liệu tự thêm. Nếu bỏ qua, chính generator tiếp tục tạo nội dung bịa mà verifier hiện không phát hiện.

### P08-10 — P1 — Không có bằng chứng vẫn xác nhận card mang nhãn EVIDENCE_BACKED

**Vị trí:** `sin_content_api/src/modules/ideation/verifier.py:53–72`; `ideation_service.py:196–198`.

Verify card không có ID/citations nhưng allow_hypotheses=true, confidence_tier=EVIDENCE_BACKED trả is_valid=true, suggested_status=NEEDS_EVIDENCE; card_preview vẫn giữ EVIDENCE_BACKED. Hàm chỉ đổi trạng thái đề nghị, không cưỡng chế nhãn HYPOTHESIS dù bình luận mã ghi là bắt buộc.

**Hướng sửa:** Từ chối tổ hợp nhãn/bằng chứng mâu thuẫn hoặc chuẩn hóa rõ card thành HYPOTHESIS trước trả kết quả. Nếu bỏ qua, client có thể hiểu thẻ đã có căn cứ dù verified_excerpts_count bằng 0, trái T082.

### P08-11 — P1 — Chủ đề cấm trong target_need không được kiểm tra

**Vị trí:** `sin_content_api/src/modules/ideation/verifier.py:31, 39–42`.

Brief cấm “kem trộn”; card có target_need="Nhu cầu dùng kem trộn bị cấm" vẫn is_valid=true và READY_FOR_REVIEW khi title/hook/angle không chứa từ đó. combined_text được kiểm tra chỉ ghép ba trường, bỏ target_need.

**Hướng sửa:** Áp dụng quy tắc thương hiệu cho toàn bộ nội dung card có ý nghĩa nghiệp vụ, gồm target_need; phân biệt trích dẫn nguồn để giải thích với đề xuất chủ đề bị cấm theo chính sách. Nếu bỏ qua, nhu cầu bị loại trừ vẫn được đưa vào ý tưởng đã xác minh.

## 17. Ghi chú đối soát P08

Không đếm lại lỗi nền P01 hoặc lỗi nguồn P03–P07; đây là các điểm kiểm tra/lưu/phê duyệt riêng tại P08 chưa bảo toàn ràng buộc trước đó. P08-01 nằm ở verifier, P08-09 nằm ở generator; cần sửa cả hai để tránh tạo sai và chấp nhận sai.

T084 hiện đạt trong luồng offline không gọi công cụ; không coi kết quả này là chứng minh an toàn cho tích hợp LLM có công cụ tương lai. T085 hiện đạt với trường hợp cảnh báo gần trùng đã có; không suy ra an toàn gửi lại hoặc nhiều yêu cầu đồng thời. Không đo tải hoặc xác minh production/PostgreSQL, ngân sách vendor hay khôi phục dữ liệu.

Chưa sửa mã, chưa đóng lỗi hoặc tạo checkpoint. Cần kiểm chứng lại tính có căn cứ của nội dung và quyền duyệt trước khi dùng đầu ra P08 cho P09. Antigravity đối soát nhãn PASS và đồng bộ trang hành trình theo phạm vi được phân công.

## 18. Chi tiết lỗi P09

### P09-01 — P1 — Chung một từ khóa đủ để xác minh cả tuyên bố sai

**Vị trí:** `sin_content_api/src/modules/scripts/claim_checker.py:47–74, 152–160`.

AllowedFact chỉ ghi “Giữ nóng 6 tiếng liên tục”, nhưng câu “Sau 6 tiếng sản phẩm chữa khỏi ung thư” vẫn VERIFIED và script được service APPROVE. Câu ghép “Giữ nóng 6 tiếng liên tục và chữa khỏi mọi bệnh” cũng qua. Nhánh chứa nhau hoặc trùng một core term xác nhận cả câu, không kiểm tra phần phát biểu thêm hoặc quan hệ giữa đại lượng và công dụng.

**Hướng sửa:** Tách các khẳng định và đối chiếu đầy đủ thuộc tính, điều kiện, đại lượng, công dụng với nguồn; không dùng một cụm thời gian chung làm bằng chứng cho toàn câu. Phần không được hỗ trợ phải BLOCKING. Nếu bỏ qua, nguồn kỹ thuật hợp lệ có thể bị dùng để chứng nhận một công dụng hoàn toàn khác.

### P09-02 — P1 — AllowedFact chưa được duyệt vẫn được sử dụng như sự thật đã duyệt

**Vị trí:** `sin_content_api/src/modules/scripts/claim_checker.py:86–89, 102–110, 152–160`.

Đặt AllowedFact thử ở verification_status=NEEDS_FACT_CHECK, script chứa câu khớp vẫn nhận claim VERIFIED và được APPROVED ở service. Query chỉ lọc brief_version_id, bỏ qua trạng thái nguồn fact.

**Hướng sửa:** Chỉ chấp nhận fact có trạng thái phê duyệt hợp lệ theo chính sách và nguồn còn hiệu lực; kiểm tra lại điều kiện này khi approve. Nếu bỏ qua, dữ kiện nháp hoặc chưa xác minh được biến thành nguồn đủ điều kiện duyệt nội dung.

### P09-03 — P1 — Bỏ sót phần trăm, ngôn ngữ khác và tuyên bố so sánh

**Vị trí:** `sin_content_api/src/modules/scripts/claim_checker.py:18–24, 122–146`.

Các câu “Hiệu quả 90%”, “100% khách hàng hài lòng”, “Saves 50 dollars and lasts 24 hours” và “Tốt hơn mọi sản phẩm khác” đều có claims=[] và được service APPROVE khi không có tài liệu hỗ trợ. Regex phần trăm dùng ranh giới từ sau dấu %, nên các cách viết bình thường có khoảng trắng/kết thúc câu không được nhận diện. Các mẫu còn lại chưa kiểm tra đầy đủ thống kê, so sánh và ngôn ngữ theo Gate P09.

**Hướng sửa:** Sửa nhận diện phần trăm và bổ sung kiểm tra các loại phát biểu được yêu cầu, bao gồm ngôn ngữ hỗ trợ; với loại chưa đánh giá được phải yêu cầu xác minh thay vì coi không có claim. Nếu bỏ qua, cổng chặn chỉ hiệu quả với một số mẫu câu hẹp dù báo cáo nói 100% tuyên bố quan trọng được kiểm tra.

### P09-04 — P1 — Bản SUPERSEDED hoặc bản đã duyệt bị REJECT vẫn có thể sửa đè

**Vị trí:** `sin_content_api/src/modules/scripts/script_service.py:203–206, 264–297, 315–316`.

Sau khi approve v1 rồi edit tạo v2, v1 thành SUPERSEDED. Edit tiếp chính ID v1 đi vào nhánh cập nhật trực tiếp, giữ version=1 nhưng đổi tiêu đề, trong khi approved_by_user_id còn nguyên. Luồng approve → reject → edit cũng ghi đè bản cũ. Chỉ trạng thái APPROVED hiện tại mới được bảo vệ, không phải mọi phiên bản đã từng được duyệt.

**Hướng sửa:** Bảo vệ bản đã từng duyệt bằng vòng đời bất biến; chỉ draft phù hợp mới được sửa tại chỗ. Yêu cầu sửa phải dựa trên phiên bản hiện hành và tạo bản mới, không mở lại snapshot cũ bằng đổi trạng thái. Nếu bỏ qua, lịch sử dùng để đối soát nội dung đã duyệt có thể bị thay đổi mà ID/version không đổi.

### P09-05 — P1 — Sai dung sai thời lượng vẫn READY_FOR_REVIEW và được duyệt

**Vị trí:** `sin_content_api/src/modules/scripts/script_service.py:69–88, 143–170`; `timing_calculator.py:42–58`.

Kịch bản mục tiêu 30 giây nhưng ba cảnh cộng thành 60 giây có duration_tolerance_passed=false, vẫn không bị chặn và được APPROVED ở service. TimingCalculator tính đúng cờ, nhưng create/approve không dùng cờ đó để thực thi tiêu chí T093.

**Hướng sửa:** Giữ bản sai thời lượng ở trạng thái cần chỉnh sửa và từ chối approve nếu chưa đạt dung sai, hoặc ghi nhận ngoại lệ tường minh theo chính sách nếu có. Nếu bỏ qua, trạng thái duyệt không bảo đảm bản thảo phù hợp thời lượng yêu cầu.

### P09-06 — P1 — Đường edit nhận kịch bản rỗng, hook rỗng và thời lượng âm

**Vị trí:** `sin_content_api/src/schemas/contracts.py:404–417`; `script_service.py:264–293, 165–170`.

Create bắt buộc ít nhất ba block, hai hook và thời lượng 15–180 giây, nhưng ScriptDraftEditRequest không có các ràng buộc tương ứng. Payload blocks=[], hook_variants=[], target_duration_seconds=-1 qua Pydantic, được lưu rồi APPROVED ở service. Sự vắng claims trên bản rỗng làm bước duyệt không có lý do để chặn.

**Hướng sửa:** Áp dụng cùng miền giá trị cho trường được sửa và xác thực lại toàn bộ bản thảo sau khi hợp nhất thay đổi; kiểm tra cấu trúc trước approve. Nếu bỏ qua, bản từng hợp lệ có thể trở thành bản rỗng hoặc sai schema nghiệp vụ mà vẫn có trạng thái đã duyệt.

### P09-07 — P1 — Không kiểm tra điều kiện ý tưởng, brief và giới hạn thương hiệu

**Vị trí:** `sin_content_api/src/modules/scripts/script_service.py:60–67, 79–84, 139–150`; `claim_checker.py:86–89`.

Đặt ý tưởng REJECTED và brief DRAFT; tạo script có lời thoại “Đây là nội dung kem trộn” trong khi brief cấm “kem trộn” vẫn được service tạo và approve. Service chỉ kiểm tra ý tưởng tồn tại/cùng workspace; claim checker không áp dụng topics_excluded. Không có kiểm tra điều kiện nguồn ý tưởng/brief trước duyệt.

**Hướng sửa:** Kiểm tra trạng thái ý tưởng/brief phù hợp với luồng tạo và duyệt; áp dụng brand safety lên nội dung script, không coi bước P08 trước đó đã đủ khi lời thoại có thể thay đổi. Nếu bỏ qua, script mới đưa lại chủ đề đã bị giới hạn hoặc dựa trên ý tưởng đã từ chối.

### P09-08 — P2 — Tham chiếu fact chưa khóa phiên bản tài liệu và SKU

**Vị trí:** `sin_content_api/src/models/entities.py:123–132`; `src/schemas/contracts.py:396–402`; `claim_checker.py:104–110`.

Claim lưu allowed_fact_id và source_citation dạng text, nhưng mô hình không có phiên bản phê duyệt tài liệu hoặc SKU để xác minh tiêu chí T091. Trong dữ liệu thử, cùng fact ID được đổi từ “6 tiếng” sang “24 tiếng” và đổi nguồn; script cũ vẫn APPROVED, ID claim trỏ tới fact hiện tại đã khác. Việc thay fact ở đây được thực hiện trên ORM RAM để kiểm tra mô hình tham chiếu, không chứng minh có endpoint cho phép người dùng sửa fact đó.

**Hướng sửa:** Gắn claim với phiên bản fact/tài liệu đã được phê duyệt, thông tin sản phẩm/SKU phù hợp và quy tắc khi nguồn bị thay thế. Có thể dùng snapshot bất biến có xuất xứ thay vì trỏ duy nhất tới bản ghi có thể thay đổi. Nếu bỏ qua, không thể chứng minh tài liệu/phiên bản sản phẩm nào đã hỗ trợ nội dung tại lúc duyệt.

### P09-09 — P1 — Tiêu đề script không được kiểm tra tuyên bố

**Vị trí:** `sin_content_api/src/modules/scripts/claim_checker.py:122–135`; `script_service.py:79–84, 144–149`.

Tạo title="Hiệu quả 90% chữa khỏi bệnh" với các cảnh bình thường, kết quả claims=[] và service APPROVE. Claim checker chỉ nhận narration, visual_cue và hook_variants, không nhận title. Ngay cả khi mở rộng regex, tiêu đề vẫn nằm ngoài phạm vi được quét.

**Hướng sửa:** Đưa các trường văn bản có thể trở thành nội dung xuất bản, gồm title, vào luồng nhận diện/đối chiếu tuyên bố; lưu vị trí phát biểu để người duyệt sửa đúng chỗ. Nếu bỏ qua, tuyên bố chưa được chứng minh có thể xuất hiện ở tiêu đề dù phần lời thoại đã kiểm định.

## 19. Ghi chú đối soát P09

Không đếm ba test API thất bại do 403 thành ba lỗi nghiệp vụ độc lập. Cần chạy lại suite tích hợp với danh tính và vai trò reviewer phù hợp sau khi nhóm phân quyền ổn định; không nới quyền để làm test xanh. Các tình huống service chứng minh lỗi trong logic khi được phép gọi, chưa chứng minh khai thác được qua mọi vai trò HTTP.

Không kiểm tra PostgreSQL, giao diện, tải đồng thời, phục hồi dữ liệu, LLM/provider thật hoặc quyền production. Các phát hiện P01–P08 trong báo cáo tổng hợp là lịch sử các lượt rà soát, chưa được kiểm tra lại sau các thay đổi phân quyền đang thực hiện.

Chưa sửa mã, đóng lỗi hoặc tạo checkpoint. Cần sửa cổng kiểm định tuyên bố, vòng đời phiên bản và xác thực bản thảo rồi nghiệm thu lại P09; Antigravity đối soát nhãn PASS và đồng bộ trang hành trình theo phân công.


## 20. Chi tiết rà soát P10

### P10-01 — P1 — Workbench vẫn dùng dữ liệu mẫu, chưa có luồng duyệt qua giao diện

**Vị trí:** `sin_creator_os/src/app/(main)/ideas/page.tsx:36–46, 232–249`; `src/services/idea-service.ts:5–9, 68–76`; `src/services/discover-service.ts:15–34`; `src/services/job-service.ts:4–36`; `src/types/idea.ts:3`.

Idea Board đọc trực tiếp mockIdeas; thao tác chỉ mở trang sinh ý tưởng hoặc kịch bản cố định script_01. Service đổi trạng thái chỉ sửa mảng RAM; kiểu IdeaStatus chưa có trạng thái review của API, version hoặc reviewer. Evidence Detail luôn đọc mockContentAnalysis bất kể contentId. JobService chỉ có tạo/thử lại trên mảng mẫu, chưa có hủy research run. Không có đường gọi review/history/metric_status trong các service và trang ý tưởng đã khảo sát. Đây là khoảng trống tích hợp của Gate tám trang, không phải kết luận đã thử đủ tám màn bằng trình duyệt.

**Hướng sửa:** Nối các màn bắt buộc với API và workspace/xác thực hiện tại; bổ sung approve/reject/request-evidence/reopen, expected_version, lịch sử và hủy run. Dữ liệu mẫu phải được nhận diện rõ, trạng thái thiếu/hết hạn phải hiển thị riêng. Chạy E2E và lưu ảnh đúng Gate. Nếu bỏ qua, người dùng không thực hiện được quy trình P10 dù test API báo đạt.

### P10-02 — P1 — Bỏ expected_version vẫn phê duyệt thành công

**Vị trí:** `sin_content_api/src/schemas/contracts.py:386–392`; `src/modules/ideation/ideation_service.py:245–265`.

HTTP có bearer reviewer độc lập hợp lệ gửi APPROVE chỉ kèm lý do, không gửi expected_version hay expected_status: nhận 200, APPROVED, version=2. Hai trường đều Optional và service chỉ kiểm tra khi được gửi. Một client giữ bản cũ có thể bỏ điều kiện thay vì nhận 409 theo T101.

**Hướng sửa:** Bắt buộc phiên bản mà reviewer đã đọc cho mọi thao tác review; từ chối thiếu/không hợp lệ ở biên API và cập nhật caller. Không chỉ bắt buộc expected_status vì nội dung có thể đổi trong cùng trạng thái. Nếu bỏ qua, duyệt không gắn với bản thực sự được xem.

### P10-03 — P1 — Kiểm tra phiên bản rồi ghi không ngăn hai phiên ghi đè nhau

**Vị trí:** `sin_content_api/src/modules/ideation/ideation_service.py:238–265, 289–294`; `src/models/entities.py:313`.

Hai SQLAlchemy session cùng giữ card v1 READY_FOR_REVIEW. Session A APPROVE với expected_version=1 thành APPROVED v2; session B REJECT cùng expected_version=1 vẫn thành REJECTED v2. Cả hai audit ghi new_version=2. Tái hiện bằng service trên SQLite RAM, giữ hai object đã đọc để mô phỏng các request chồng lấn; không phải thử tải đồng thời PostgreSQL. Phép kiểm tra Python và UPDATE tách nhau, ORM không có điều kiện khóa version trên lệnh ghi.

**Hướng sửa:** Dùng UPDATE có điều kiện id/workspace/version và kiểm tra số dòng cập nhật, hoặc cơ chế version của ORM; trạng thái và audit phải chung transaction. Request thua trả 409. Nếu bỏ qua, phê duyệt có thể mất và hai sự kiện cùng nhận một số phiên bản.

### P10-04 — P1 — Nhãn đang thịnh hành chỉ dựa vào tổng lượt xem của một snapshot

**Vị trí:** `sin_content_api/src/modules/sources/router.py:246–251, 282–290`; `tests/test_workbench.py` trong T102.

Một snapshot cách đây hai ngày có 250.000 views lập tức trả is_trending=true; không có snapshot thứ hai, cửa sổ tăng trưởng, baseline hay tín hiệu xu hướng. Test T102 còn khẳng định chính kết quả này nên không phát hiện lỗi. Số lượt xem tích lũy chứng minh độ lớn tại một thời điểm, chưa chứng minh nội dung đang tăng trưởng.

**Hướng sửa:** Tách nhãn nhiều lượt xem khỏi xu hướng; để is_trending chưa xác định khi chưa có căn cứ, hoặc dùng định nghĩa tín hiệu được duyệt với công thức và thời điểm rõ ràng. Nếu bỏ qua, UI nhận suy luận không được bằng chứng hỗ trợ dưới dạng dữ kiện.

### P10-05 — P1 — Snapshot trong tương lai được coi là hợp lệ

**Vị trí:** `sin_content_api/src/modules/sources/router.py:264–271, 282–290`.

Đặt observed_at sau hiện tại 10 ngày, view_count=250000: metric_status vẫn VALID và is_trending=true. age_days âm không rơi vào nhánh hết hạn; API không loại thời gian chưa xảy ra.

**Hướng sửa:** Kiểm tra mốc quan sát với dung sai đồng hồ có quy định; dữ liệu tương lai không được tham gia tính freshness/trend. Nếu bỏ qua, mốc sai hoặc bị nhập giả có thể kéo dài hiệu lực và tạo tín hiệu sai.

### P10-06 — P1 — Lưu trạng thái duyệt và audit bằng hai transaction riêng

**Vị trí:** `sin_content_api/src/modules/ideation/ideation_service.py:294–311`.

Gây lỗi có kiểm soát ở commit thứ hai: commit trạng thái đầu đã giữ APPROVED v2, nhưng không có AuditEvent tương ứng sau rollback. Đây là phép tiêm lỗi trong session RAM, không phải sự cố production đã quan sát. Code commit/refresh card trước khi thêm audit nên rollback sau đó không thể hoàn tác lần duyệt đầu.

**Hướng sửa:** Thêm audit vào cùng transaction với cập nhật trạng thái/phiên bản và chỉ commit một lần. Nếu bỏ qua, request báo lỗi nhưng nội dung đã được duyệt, lịch sử không giải thích được hành động và retry có thể gây thêm chuyển trạng thái.

### P10-07 — P2 — Lịch sử thẻ lấy cả sự kiện của thẻ khác nhắc ID trong lý do

**Vị trí:** `sin_content_api/src/modules/ideation/ideation_service.py:323–327`.

Reviewer REJECT thẻ B với lý do nhắc ID thẻ A. GET history của A qua HTTP trả sự kiện có details.idea_id=B. Bộ lọc LIKE trên toàn JSON khớp cả review_reason, không chỉ khóa idea_id. Vẫn có scope workspace; không suy ra rò dữ liệu khác tenant.

**Hướng sửa:** Lọc chính xác resource_id/idea_id bằng trường có cấu trúc, không tìm chuỗi trong toàn details. Nếu bỏ qua, người xem có thể hiểu nhầm quyết định duyệt/từ chối thuộc thẻ đang xem.

### P10-08 — P2 — Thiếu lượt xem làm mất cả chỉ số còn có và thời gian quan sát

**Vị trí:** `sin_content_api/src/modules/sources/router.py:253–263`.

Snapshot hai ngày trước có view_count=null nhưng like_count=123: API trả MISSING, like_count=null và last_observed_at=null. Nhánh kiểm view_count xóa đồng loạt các chỉ số còn hợp lệ; người dùng không thấy độ phủ từng metric hoặc thời điểm đã thu thập.

**Hướng sửa:** Giữ từng metric có thật và thời gian snapshot, thể hiện trường thiếu bằng null cùng trạng thái độ phủ tương ứng. Nếu bỏ qua, dữ liệu có thật bị trình bày như chưa từng được thu thập, sai yêu cầu metric coverage của P10.

## 21. Kiểm tra lại và bàn giao P10

- [ ] Hoàn thiện tám màn và hủy research run theo Gate; chạy E2E có ảnh, gồm vai trò/workspace và thiếu chỉ số khác số 0.
- [ ] Thử thiếu phiên bản, stale cùng trạng thái, hai phiên chồng lấn; chỉ một cập nhật thành công, phiên còn lại nhận 409.
- [ ] Thử lỗi ghi audit: không được lưu trạng thái duyệt thiếu audit.
- [ ] Kiểm lịch sử chính xác theo idea_id; thử metric một snapshot, thời gian tương lai và snapshot thiếu từng trường.

Không đếm lại P08-06 về approve chưa kiểm chứng bằng chứng. P10-02 là điều kiện phiên bản bị bỏ trống; P10-03 là tranh chấp dù đã gửi phiên bản, cần xử lý cả hai. Tài liệu gọi P11 là “Trend Velocity” trong báo cáo P10 không khớp kế hoạch chính thức: P11 là phản hồi chỉ đọc từ bài đã đăng; cần đối soát phạm vi trước khi làm tiếp.

Chưa chạy trình duyệt/Playwright, kiểm accessibility, PostgreSQL/RLS hoặc tải đồng thời, staging, production hay provider danh tính/nguồn thật. Chưa xác nhận số lỗi cũ còn tồn tại sau sửa RBAC. Không tạo checkpoint hoặc đổi nhãn nghiệm thu gốc. Antigravity đối soát PASS và cập nhật trang hành trình theo phân công.


## 22. Chi tiết rà soát P11

### P11-01 — P1 — Trả số liệu cố định dưới nhãn hiệu suất chính thức đã xác thực

**Vị trí:** `sin_content_api/src/modules/feedback/channel_service.py:53–67`; `tests/test_feedback_loop.py` trong T113.

**Vấn đề và bằng chứng:** Kết nối một ID kênh kiểm thử chưa có dữ liệu nào, API trả follower_count=45000, video_count=86, profile_views_7d=12800 và thông điệp chỉ số chính thức đã xác thực. Ba giá trị được viết cố định trong service; verified_at lấy từ thời điểm kết nối, không phải một lần quan sát chỉ số. T113 chỉ kiểm follower_count > 0 nên vẫn đạt với dữ liệu bịa đặt.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Chỉ trả chỉ số có quan sát thật hoặc bản nhập khách hàng được ghi rõ nguồn và thời điểm. Khi chưa có dữ liệu, trả metrics=null với lý do chưa khả dụng; loại bỏ các số cố định và nhãn đã xác thực. Nếu bỏ qua, phản hồi giả trở thành dữ liệu thật dùng ra quyết định.

### P11-02 — P1 — Người gọi tự khai scope OAuth và kết nối hết hạn vẫn có hiệu lực

**Vị trí:** `sin_content_api/src/schemas/contracts.py:522–527`; `src/modules/feedback/channel_service.py:24–53, 79–104`.

**Vấn đề và bằng chứng:** HTTP dùng bearer owner hợp lệ gửi channel_id tùy ý và oauth_scopes=["channel:metrics"]: API nhận CONNECTED, has_metrics_scope=true, không có bước xác minh quyền sở hữu hoặc grant từ provider. Sau khi đặt trạng thái bản ghi thành EXPIRED trong DB RAM, GET performance vẫn trả CONNECTED và metrics. RBAC xác nhận quyền thao tác trong workspace không chứng minh quyền OAuth với tài khoản bên ngoài.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Chỉ ghi scope/kênh từ kết quả ủy quyền đã được máy chủ xác minh hoặc nguồn nhập được định danh riêng. Kiểm tra trạng thái kết nối, hết hạn và thu hồi trước khi dùng; giữ tính năng chưa khả dụng nếu thiếu bằng chứng ủy quyền. Nếu bỏ qua, nhãn kênh sở hữu và trạng thái xác thực có thể do người gọi tự tạo.

### P11-03 — P1 — Chỉ số chưa biết bị đổi thành số 0 và vận tốc có vẻ hợp lệ

**Vị trí:** `sin_content_api/src/modules/feedback/velocity_engine.py:70–74, 82–85`; `src/modules/feedback/cohort_service.py:46–51, 61–63`; `src/schemas/contracts.py:495–511`.

**Vấn đề và bằng chứng:** Hai snapshot cách nhau một ngày có lượt xem null và 100: API biến from_views thành 0 rồi trả delta_views=100, velocity_views_per_day=100. rate_status=NOT_AVAILABLE chỉ báo tỷ lệ phần trăm, không ngăn vận tốc bịa từ đầu vào thiếu. Cohort có một bài nhưng toàn bộ lượt xem thiếu cũng trả total_views=0, average_velocity_views_per_day=0 thay vì chưa có dữ liệu. Schema MetricSnapshot quy định null khác số 0 đã quan sát.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Giữ null xuyên suốt phép tính; khi thiếu một đầu vào, delta/vận tốc/tỷ lệ phụ thuộc phải chưa khả dụng. Bổ sung độ phủ metric và số bài có quan sát cho tổng hợp; chỉ trả 0 nếu dữ liệu đủ và thực sự bằng 0. Nếu bỏ qua, thiếu dữ liệu bị diễn giải thành tăng trưởng hoặc hiệu suất bằng 0.

### P11-04 — P1 — Tính lại cùng cặp snapshot làm lệch trung bình hiệu suất

**Vị trí:** `sin_content_api/src/modules/feedback/velocity_engine.py:96–112`; `src/modules/feedback/cohort_service.py:55–63`; `src/models/entities.py:463–482`.

**Vấn đề và bằng chứng:** Hai bài có vận tốc 100 và 300 views/ngày cho trung bình 200. Gọi lại đúng phép tính của bài đầu, không thêm snapshot: trung bình giảm xuống 166,67 và bảng vận tốc có ba dòng. Mỗi request luôn thêm bản ghi; cohort lấy trung bình mọi bản ghi nên số lần nhấn hoặc retry trở thành trọng số thống kê.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Bảo đảm cùng nguồn/cặp quan sát/chỉ số/phiên bản công thức chỉ tạo một kết quả, và chọn cửa sổ có quy tắc cho mỗi bài khi tổng hợp. Nếu cần giữ lịch sử request thì không đưa các request trùng vào tập quan sát phân tích. Nếu bỏ qua, báo cáo thay đổi theo tần suất gọi API thay vì dữ liệu mới.

### P11-05 — P1 — Thông tin quảng cáo bị mất khi nhập và lọt vào nhóm tự nhiên

**Vị trí:** `sin_content_api/src/modules/ingestion/service.py:65–70, 101–110`; `src/models/entities.py:150–151`; `src/modules/feedback/cohort_service.py:24–29`.

**Vấn đề và bằng chứng:** Payload nhập ghi rõ is_paid=true, channel_id=kenh_paid và view_count=100000. Kiểm tra trực tiếp ingestion service cho thấy bản ghi lưu is_paid=false, channel_id=null; API cohort sau đó cộng 100.000 views vào ORGANIC, PAID bằng 0 nhưng vẫn cam kết đã tách quảng cáo. HTTP nhập bằng owner fixture nhận 403 nên ca này gọi riêng service, không khẳng định owner vượt guard nhập dữ liệu. Đây là lỗi tích hợp trường P11 với luồng nhập hiện có.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Giữ và kiểm tra phân loại trả phí cùng liên kết kênh qua các đường nhập được phép. Trạng thái chưa xác định phải được ghi riêng, không mặc định là tự nhiên; đối chiếu provenance trước khi đưa vào cohort. Nếu bỏ qua, số liệu quảng cáo được trình bày như hiệu suất tự nhiên dù hai nhóm trên response tách riêng.

### P11-06 — P1 — Nguồn synthetic hoặc đã purge vẫn được dùng cho phản hồi hiệu suất

**Vị trí:** `sin_content_api/src/modules/feedback/velocity_engine.py:29–48`; `src/modules/feedback/cohort_service.py:24–29, 48–51`.

**Vấn đề và bằng chứng:** Tạo nguồn kiểm thử synthetic=true, is_purged=true cùng hai snapshot 100 và 300. HTTP tính vận tốc trả VALID, 200 views/ngày; cohort cộng 300 views và vận tốc đó vào ORGANIC. Query chỉ xét workspace/source ID, không loại nguồn đã purge hoặc dữ liệu mẫu; response không cung cấp cờ synthetic để phân biệt. Hai cờ được đặt đồng thời trong ca thử, đọc mã xác nhận cả hai đều chưa được kiểm tra.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Chọn nguồn đủ điều kiện trước mọi phép tính và tổng hợp: dữ liệu thật, đúng quyền, còn được phép dùng, có liên kết bài đăng phù hợp. Dữ liệu mẫu phải tách khỏi phản hồi thật; xử lý hiệu lực kết quả dẫn xuất theo chính sách purge. Nếu bỏ qua, dữ liệu kiểm thử hoặc đã ngừng sử dụng vẫn ảnh hưởng quyết định nội dung.

### P11-07 — P1 — Chưa có luồng nối bài đã đăng với bản kịch bản và phản hồi học tập

**Vị trí:** `sin_content_api/src/modules/feedback/router.py:21–100`; `src/models/entities.py:440–482`; `src/main.py:109`; hợp đồng Feedback và Gate P11 trong kế hoạch gốc.

**Vấn đề và bằng chứng:** Đối chiếu OpenAPI thực chạy: feedback chỉ có bốn route tính vận tốc, cohort, đọc hiệu suất và khai báo kết nối. Không có /v1/published-links hoặc /v1/feedback/sync, cũng chưa có mô hình hoặc xử lý tương đương cho PublishedContentLink, PerformanceSnapshot, LearningSignal, ExperimentSuggestion. SourceRecord.channel_id không liên kết tới phiên bản script đã duyệt. Vì vậy không thực hiện được chuỗi gắn bài thực tế với script, nhận phản hồi có nguồn và giới hạn, rồi tháo liên kết theo Gate. Không chỉ dựa vào tên endpoint: đã tìm cả mã module và mô hình liên quan.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Hoàn thiện luồng tối thiểu theo hợp đồng: gắn bài thật với bản đã duyệt, nhận snapshot chỉ đọc hoặc import có nhãn, tạo tín hiệu/đề xuất truy nguyên được và tháo liên kết theo chính sách. Đánh giá Gate trên luồng đầy đủ trước khi mở pha sau. Nếu bỏ qua, bốn test toán học/kết nối không chứng minh vòng lặp phản hồi P11 đã tồn tại.

### P11-08 — P2 — Đổi ngầm khoảng thời gian làm sai vận tốc ở hai snapshot gần nhau

**Vị trí:** `sin_content_api/src/modules/feedback/velocity_engine.py:59–74, 121–125`.

**Vấn đề và bằng chứng:** Hai snapshot cách nhau một giây, tăng từ 100 lên 101 lượt xem: API trả delta_seconds=1 nhưng delta_days=0,0001 và velocity=10000 views/ngày. Theo khoảng thời gian thực, kết quả quy đổi là 86400 views/ngày. max(delta_days, 0.0001) kéo dài cửa sổ lên 8,64 giây dù thứ tự thời gian đã được kiểm tra lớn hơn 0.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Tính theo thời gian thực, hoặc từ chối/đánh dấu chưa đủ cửa sổ nếu chính sách không cho phép quan sát quá gần; không thay thời gian bằng một hằng số rồi báo VALID. Nếu bỏ qua, công thức công bố và khoảng quan sát không khớp kết quả.

### P11-09 — P2 — Bộ lọc cohort chỉ được ghi vào nhãn mà không lọc kết quả

**Vị trí:** `sin_content_api/src/modules/feedback/router.py:44–54`; `src/modules/feedback/cohort_service.py:74–81`.

**Vấn đề và bằng chứng:** Workspace có một bài tự nhiên 100 views và một bài trả phí 500 views. GET summary?cohort=ORGANIC trả filter_applied=ORGANIC nhưng paid_cohort vẫn có một bài, 500 views. filter_cohort không tham gia truy vấn hoặc tính toán, chỉ được chép vào response. Không có suy luận gộp trong ca này; lỗi là bộ lọc đã công bố không có tác dụng.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Thực thi bộ lọc và thể hiện nhóm bị loại rõ ràng trong hợp đồng, hoặc bỏ tham số cùng nhãn filter_applied nếu endpoint luôn trả cả hai nhóm. Nếu bỏ qua, client tin rằng response đã giới hạn theo nhóm được chọn.

## 23. Kiểm tra lại và bàn giao P11

- [ ] Không có quan sát kênh thì metrics chưa khả dụng, không có số mặc định; thông điệp và thời điểm xác minh phải khớp bằng chứng.
- [ ] Scope chỉ đến từ nguồn ủy quyền tin cậy; thử kênh sai chủ sở hữu, hết hạn và bị thu hồi.
- [ ] Null khác 0 ở snapshot, delta, vận tốc và tổng hợp; hiển thị độ phủ dữ liệu và công thức.
- [ ] Gọi lại cùng cặp snapshot không đổi cohort; chọn cửa sổ phân tích tương đương giữa các bài.
- [ ] Import giữ is_paid/channel_id; dữ liệu chưa rõ nguồn trả phí không thành ORGANIC; dữ liệu mẫu/purge không lọt vào phân tích thật.
- [ ] Có luồng bài đã đăng gắn đúng bản script đã duyệt, đồng bộ chỉ đọc/import có nhãn, tín hiệu/đề xuất có giới hạn và tháo liên kết.
- [ ] Khoảng thời gian thực khớp công thức; bộ lọc cohort thực thi đúng hợp đồng.

P11-01 là đầu ra bịa số liệu; P11-02 là bằng chứng kết nối không được xác minh, cần xử lý cả hai. Không đếm lại các lỗi quyền nền hoặc thiếu UI P10. P11-05 và P11-06 là lựa chọn/phân loại dữ liệu trong đường phân tích P11, không khẳng định các phát hiện cũ ở pha khác còn nguyên sau sửa RBAC.

Chưa chạy trình duyệt/E2E, PostgreSQL/RLS, tải/đồng thời, OAuth/provider thật, staging/production hoặc thử phục hồi migration. Không chạy lại quét secrets toàn repo trong lượt này. Chưa kiểm tra lại P01–P10; tổng hợp là sổ lịch sử phát hiện, không phải số lỗi còn tồn tại trên mã mới nhất.

Không tạo checkpoint; không xác nhận mở Gate P12. Antigravity đối soát nhãn hoàn tất trong báo cáo pha/trang hành trình và các phần chưa triển khai với bằng chứng mới. Việc cập nhật trang hành trình gốc thuộc phân công Antigravity và nằm ngoài vùng ghi Codex.


**Đối soát thay đổi song song:** Router feedback được bổ sung chặn workspace_id khác tenant trong lúc hoàn tất báo cáo. Đã đọc lại và chạy lại **4/4 test P11 đạt, mã thoát 0, 4,97 giây**; các service được ghi hash trong bằng chứng không đổi. Không có kết luận lỗi cross-tenant trong báo cáo này. [Nhật ký kiểm tra lại](../../08_kiem_thu/bang_chung/kiem_tra_lai_p11_sau_thay_doi_router_2026_10_21.txt).


## 24. Chi tiết rà soát P12

### P12-01 — P1 — Cache tác vụ trả artifact của workspace khác

**Vị trí:** `sin_content_api/src/modules/staging_reliability/downstream_executor.py:17, 34–45, 96–101`.

**Vấn đề và bằng chứng:** Tenant A chạy tác vụ với khóa K. Tenant B dùng bearer và workspace của B, gửi cùng K: HTTP 200, is_idempotent_replay=true và output_artifact_id trùng của A. Cache chỉ khóa bằng idempotency_key, được đọc trước ledger/workspace. Mã artifact chứa cả task_id của A. Ca này xác nhận lộ mã artifact và metadata tác vụ; chưa chứng minh đọc được nội dung artifact vì executor chưa lưu nội dung thật.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Khóa theo workspace và idempotency key, xác minh tài nguyên cùng fingerprint yêu cầu trước khi trả replay. Chuyển dữ liệu kết quả sang kho bền vững có scope. Nếu bỏ qua, khách thuê có thể nhận tham chiếu tác vụ của nhau; nhãn không có rò rỉ chéo tenant trong T120 không còn đúng.

### P12-02 — P1 — Mất cache RAM khiến tác vụ đã hoàn thành bị tạo và trừ phí lại

**Vị trí:** `sin_content_api/src/modules/staging_reliability/downstream_executor.py:34–58, 81–101`; `budget_guard.py:53–61, 135–140`.

**Vấn đề và bằng chứng:** Chạy tác vụ 2 units, xóa cache RAM để mô phỏng tiến trình mới nhưng giữ nguyên DB ledger, rồi gọi lại cùng payload/key. Hai lần đều 200, có hai artifact_id khác nhau và spent_units tăng lên 4. Ledger COMMITTED chỉ được trả IDEMPOTENT_HIT; executor vẫn chạy và commit_budget cộng phí tiếp. Tái hiện tuần tự, chưa thử nhiều worker thật.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Lưu kết quả cùng trạng thái hoàn tất trong DB, replay từ đó và bảo đảm commit trạng thái/chi phí chỉ diễn ra một lần. Cache chỉ tăng tốc tra cứu. Nếu bỏ qua, restart hoặc worker khác có thể tạo/trừ phí trùng dù test replay trong cùng tiến trình đạt.

### P12-03 — P1 — Ledger cũ cho phép vượt ngân sách bằng gọi lại hoặc đổi payload

**Vị trí:** `sin_content_api/src/modules/staging_reliability/budget_guard.py:45–64, 125–143`; `downstream_executor.py:48–62, 90–93`.

**Vấn đề và bằng chứng:** Ngân sách 1 unit, chạy tác vụ 5 units: lần đầu 402 nhưng gọi lại đúng key nhận 200 và spent_units=5. Một ca khác giữ chỗ 0,1 unit rồi chạy cùng key với estimated_units=10: vẫn 200 và spent_units=10. Mọi ledger cũ, kể cả REFUSED, đều IDEMPOTENT_HIT; executor chỉ chặn REFUSED_OVER_BUDGET và không đối chiếu payload hoặc mức giữ chỗ.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Kiểm trạng thái ledger, fingerprint bất biến và reservation hợp lệ trước thực thi; không cho REFUSED hoặc payload khác sử dụng lại quyền chạy. Kiểm chi phí tại điểm commit và trước từng thao tác tính phí theo hạn mức máy chủ. Nếu bỏ qua, chỉ cần hai request hợp lệ là vượt cap mà không cần giả mạo quyền.

### P12-04 — P1 — Hai phiên giữ chỗ vượt cap nhưng bảng ngân sách ghi thiếu

**Vị trí:** `sin_content_api/src/modules/staging_reliability/budget_guard.py:50–64, 89–103`; `src/models/entities.py:482–509`.

**Vấn đề và bằng chứng:** Hai session cùng đọc ngân sách 1 unit, mỗi phiên reserve 0,8 bằng key riêng. Cả hai trả RESERVED; tổng estimated_units của ledger RESERVED bằng 1,6 nhưng budget.reserved_units chỉ 0,8. Giữ hai ORM object đã đọc để mô phỏng request chồng lấn trên SQLite RAM. Đây là tái hiện cập nhật mất dữ liệu giữa hai phiên, không phải đo tải/locking PostgreSQL.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Giữ chỗ bằng cập nhật nguyên tử có điều kiện số dư, hoặc khóa transaction phù hợp với DB triển khai; ledger và số dư phải cùng giao dịch. Chỉ một request được nhận khi tổng vượt cap. Nếu bỏ qua, nhiều tác vụ cùng được cho phép tiêu cùng một ngân sách.

### P12-05 — P1 — Bài thử timeout chưa thực thi công việc hoặc side effect downstream

**Vị trí:** `sin_content_api/src/modules/staging_reliability/downstream_executor.py:68–93`; `src/modules/staging_reliability/router.py:44–62`; `src/main.py:111`; `tests/test_staging_evaluation.py` trong T121.

**Vấn đề và bằng chứng:** Vòng lặp tự raise TimeoutError trước khi tạo artifact, rồi lần cuối luôn tạo một chuỗi UUID và đặt success=true. Không có lời gọi provider, worker/research pipeline hoặc lưu artifact thực tế; actual_cost chỉ bằng estimated_units người gọi đưa vào. T121 yêu cầu timeout sau side effect nhưng test chỉ kiểm trình mô phỏng này. Tìm các caller cho thấy executor và BudgetGuard mới chỉ nối với route staging; router được include không điều kiện theo môi trường.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Giữ mô phỏng trong fixture được nhận diện rõ; kiểm executor và lớp tính phí thực với downstream giả lập có side effect bền vững rồi timeout sau side effect. Đối soát artifact/cost ở retry và restart, chứng minh guard trên luồng được phát hành; vô hiệu endpoint giả lập khi phát hành. Nếu bỏ qua, PASS không chứng minh độ bền của chức năng thật và COMPLETED chỉ là ID không có artifact phía sau.

### P12-06 — P1 — Backup cam kết đã tẩy secrets nhưng chỉ thay mật khẩu một cột

**Vị trí:** `sin_content_api/scripts/backup_staging_db.py:21–36, 61–64`; `docs/runbooks/backup_and_restore.md` mục secrets scrubbing.

**Vấn đề và bằng chứng:** Fixture SQLite có users.hashed_password và source_observations.raw_payload_json chứa access_token giả lập. Backup thay mật khẩu nhưng giữ nguyên token trong JSON, trong khi manifest ghi secrets_scrubbed=true, APPROVED_BACKUP. Script chỉ UPDATE users.hashed_password, còn lỗi thiếu bảng/cột bị bỏ qua. Không dùng hoặc phát hiện token thật của dự án trong phép thử này.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Định nghĩa dữ liệu được phép vào bản sao staging và xử lý các trường nhạy cảm trên toàn schema/payload trước khi công bố đã tẩy sạch; xác nhận bằng kiểm tra artifact. Không báo scrubbed khi chưa kiểm đủ. Nếu bỏ qua, người nhận bản backup tưởng đã làm sạch vẫn có thể nhận bí mật nằm ngoài một cột mật khẩu.

### P12-07 — P1 — Restore xóa database đích trước khi biết backup có hợp lệ

**Vị trí:** `sin_content_api/scripts/restore_staging_db.py:18–38, 40–43`; `docs/runbooks/backup_and_restore.md` lệnh restore.

**Vấn đề và bằng chứng:** Trên DB đích fixture có dữ liệu cần giữ, truyền một file không phải SQLite cùng đường manifest không tồn tại. Script bỏ kiểm manifest, xóa đích, chép file hỏng rồi mới PRAGMA; phát sinh DatabaseError, đích chỉ còn bytes của file hỏng. CLI không đọc đối số manifest thứ ba dù runbook hướng dẫn truyền đối số đó. Lượt thử đầu bị khóa file fixture do kết nối chưa đóng; sau khi đóng kết nối đúng, công cụ chạy lại xác nhận mất dữ liệu đích. Không thao tác DB dự án.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Bắt buộc manifest được phê duyệt và checksum, kiểm integrity/schema/count trên bản staging tạm trước khi thay đích; có bản giữ lại và thay thế nguyên tử. Sửa CLI truyền manifest đúng. Nếu bỏ qua, một đường dẫn backup sai hoặc bản hỏng có thể phá DB đang tốt mà không có rollback.

### P12-08 — P1 — Đánh giá prompt tự đếm nhãn ghi sẵn, không đo hệ thống hay thẩm định người

**Vị trí:** `sin_content_api/src/modules/staging_reliability/prompt_regression.py:14–84, 105–118, 140–155`; `tests/test_staging_evaluation.py` trong T124.

**Vấn đề và bằng chứng:** Ba brief chỉ có 10 ứng viên mỗi brief, nhãn RELEVANT/has_evidence/contains_excluded ghi sẵn trong mã. Thay hook đầu bằng đúng chủ đề cấm kèm 999999999 lượt xem không có nguồn, giữ nhãn: toàn bộ response vẫn y nguyên, PASSED và 90%. Không chạy model/prompt/ranking/verifier, không có evidence ID để resolve, không có hai reviewer/đối soát bất đồng hoặc tập >=30 ứng viên cho mỗi brief theo protocol.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Chạy pipeline được đánh giá trên corpus held-out có version, nguồn hợp lệ và ít nhất 30 ứng viên mỗi brief; lưu hai bộ nhãn độc lập và phán quyết bất đồng. Tính precision trên top 10 thực tế, resolve evidence và kiểm metric/brand exclusions từ đầu ra. Nếu bỏ qua, 90% chỉ phản ánh bảng nhãn do người viết mã đặt, không phải chất lượng sản phẩm.

### P12-09 — P1 — Kiểm toán phụ thuộc trả số vi phạm bằng 0 mà chưa kiểm tra

**Vị trí:** `sin_content_api/scripts/audit_licenses_and_deps.py:29–72, 99–110`; `tests/test_staging_evaluation.py` trong T125.

**Vấn đề và bằng chứng:** Fixture khai báo dependency giả lập có license GPL-3.0-only trong node_modules và requirements chứa MediaCrawler[extra]==1.0. run_audit vẫn PASS, banned_packages_detected=0, unapproved_licenses_detected=0, critical_vulnerabilities=0. Script chỉ so tên với ba gói cấm, không chuẩn hóa extras, không đọc license phụ thuộc/lockfile hay cơ sở dữ liệu lỗ hổng; hai trường cuối luôn bằng 0. Không suy ra dự án đang có CVE cụ thể hoặc kết luận pháp lý về một license từ ca giả lập này.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Dùng danh sách phụ thuộc thực đã khóa, chuẩn hóa tên và kiểm license/approval cùng nguồn advisory; ghi phiên bản và thời điểm cơ sở dữ liệu quét. Hạng mục chưa kiểm phải NOT_CHECKED, không trả số 0/PASS. Nếu bỏ qua, bản readiness sẽ khẳng định an toàn trên dữ liệu chưa hề được thu thập.

### P12-10 — P1 — Hồ sơ phát hành mở Gate P13 dù chưa có bằng chứng đạt Gate P12

**Vị trí:** `sin_content_api/docs/RELEASE_READINESS.md` mục I–III; `sin_creator_os/bao_cao_p12.md` phần kết luận; `src/main.py:101–111`; Gate P12 trong kế hoạch gốc.

**Vấn đề và bằng chứng:** RELEASE_READINESS khai báo P02–P12 enabled và SẴN SÀNG CHO CANARY, dựa vào sáu test trên. Lượt rà soát này tái hiện ngay trên route staging lỗi chéo tenant, vượt ngân sách và phí lặp; thí nghiệm prompt/license chỉ là kiểm nhãn/hằng số như các phát hiện bên trên. Hồ sơ chưa đưa bằng chứng clean CI toàn Gate, SLO/tải 25 job, monitoring/rollback thực thi hoặc kết quả xử lý các vấn đề P10/P11 đã được báo. Không coi lỗi lịch sử chưa kiểm lại là lỗi chắc chắn còn tồn tại; chính các ca P12 mới đã đủ làm thất bại điều kiện không có rủi ro cao.

**Hướng sửa và ảnh hưởng nếu bỏ qua:** Đánh dấu P12 chưa đạt, chốt danh sách năng lực thực sự bật và chỉ nghiệm thu sau kiểm tra lại bằng chứng hiện hành. Phần chưa kiểm phải để chưa xác nhận hoặc tắt năng lực tương ứng, gồm quyền nguồn/provider thật. Nếu bỏ qua, người duyệt canary có thể dựa vào hồ sơ đã khẳng định điều kiện chưa được chứng minh.

## 25. Kiểm tra lại và bàn giao P12

- [ ] Replay không lộ metadata chéo workspace; restart/nhiều worker không tạo artifact hoặc phí lặp.
- [ ] Ledger REFUSED không cấp quyền chạy; payload đổi phải bị từ chối; reservation/commit nguyên tử, không vượt cap khi chồng lấn.
- [ ] Thử timeout sau side effect thực sự bằng downstream giả lập bền vững, và xác nhận guard trên các pipeline phát hành.
- [ ] Bản sao không còn secrets trong các trường/payload đã quy định; lỗi scrub không được nhận manifest đã làm sạch.
- [ ] Manifest sai/thiếu hoặc backup hỏng không thay đổi DB đích; CLI dùng đúng manifest; kiểm phục hồi và rollback.
- [ ] Đánh giá chất lượng thực chạy pipeline với corpus/nhãn người đủ protocol, nguồn và metric có thể truy nguyên.
- [ ] Kiểm phụ thuộc/license/advisory có danh mục và phiên bản dữ liệu; mục chưa quét không được báo 0.
- [ ] Hồ sơ readiness ghi đúng năng lực bật, các Gate đã kiểm và bằng chứng CI/tải/giám sát/phục hồi, quyền provider.

P12-01 là thiếu scope cache; P12-02 là thiếu kết quả bền vững sau restart; P12-03 là kiểm sai trạng thái/fingerprint ledger; P12-04 là cập nhật số dư mất tính nguyên tử. Các ca khác nhau cần cùng được kiểm lại. P12-05/P12-08/P12-09 ghi nhận phép nghiệm thu chưa đo năng lực tuyên bố; không quy mọi vấn đề về việc thiếu thêm test.

Không kiểm lại toàn bộ P01–P11, không xác nhận số lỗi cũ còn tồn tại sau sửa RBAC. Chưa chạy toàn bộ suite/CI, đo coverage, trình duyệt/E2E, tải 25 job, PostgreSQL/RLS, provider/OAuth/model thật, advisory toàn repo, staging/production hoặc diễn tập phục hồi DB dự án. Không dùng các test nhỏ đạt để khẳng định không còn lỗ hổng HIGH/CRITICAL.

Đã lưu tài liệu đối soát và ghi chú trước kết luận cũ ở báo cáo pha/readiness; chưa tạo checkpoint hoặc mở Gate P13. Antigravity cập nhật trang hành trình gốc theo phân công và đối soát trạng thái phát hành.
