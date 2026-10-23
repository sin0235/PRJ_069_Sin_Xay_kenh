# Nhật ký điều phối — kế hoạch: ke_hoach_sua_phan_quyen_2026_10_21.md

Người dùng yêu cầu các agent Luna 6 max sửa các lỗi trong báo cáo phân quyền. Đã mở ba agent `gpt-6-luna`, `reasoning_effort=max`, không kế thừa toàn bộ hội thoại.

| Nhóm | Vùng sở hữu | Phụ thuộc | Đối soát |
|---|---|---|---|
| 1 — lõi phân quyền | identity/deps/config/database/models/policy/role/tenant/org/audit | Cung cấp actor, resource, evaluator, xác minh bearer và audit cho nhóm 2/3 | Không chỉnh service/router duyệt/worker, không chỉnh API nghiệp vụ |
| 2 — duyệt và worker | approval/worker service/router, schemas; test riêng | Dùng actor/evaluator/audit của nhóm 1; đề nghị model thay đổi qua nhóm 1 | Không chỉnh DB/model chung hoặc nghiệp vụ |
| 3 — tích hợp nghiệp vụ | sin_content_api, sin_content_workers, sin_creator_os liên quan phân quyền | Dùng contract identity/policy đã phối hợp với nhóm 1 | Không sửa baha_auth; tránh trùng namespace src.* |
| Điều phối | Kế hoạch, nhật ký, bằng chứng tổng hợp và trạng thái | Chờ từng nhóm, kiểm tra tích hợp và rà soát độc lập | Không tự nhận staging/production đạt |

- Nhóm 1: đang thực hiện; được giao thêm conftest và test cũ tenant/comprehensive.
- Nhóm 2: đang thực hiện; tạo test riêng, cập nhật test approvals/worker cũ phải phối hợp.
- Nhóm 3: đang thực hiện; cần xác minh mọi điểm ghi nghiệp vụ có kiểm tra quyền trên tài nguyên.
- Kiểm tra độc lập: chưa bắt đầu; chờ báo cáo và gói thay đổi từng nhóm.

Quyết định: làm tại SSOT được người dùng quy định `03_ban_lam_viec/`, phân chia vùng sửa từng agent; không sao chép mã sang thư mục ngoài quản lý. Kho chưa có đường cơ sở tracked cho các tệp ứng dụng nên không lấy HEAD làm bằng chứng diff ứng dụng. Không commit dữ liệu/untracked của tác vụ khác hoặc xóa thư mục theo workflow chung.

Phát hiện bổ sung khi đọc runbook cũ: tài liệu ngoài vùng ghi có hướng dẫn tắt cách ly và drop_all khi rollback. Không thực thi; sẽ đưa hướng dẫn an toàn thay thế trong vùng làm việc và bàn giao Antigravity đối soát tài liệu gốc.

Quyết định: worker dùng một principal được cấu hình subject/audience riêng cho pool hiện tại, không thêm mô hình nhiều executor khi chưa có yêu cầu. Mỗi lần kiểm tra vẫn phải có thẻ công việc chuẩn và đối chiếu initiator, action, tài nguyên, phiên bản/hash, chính sách, trạng thái và thời hạn; biết job ID không đủ quyền. Giới hạn: nếu triển khai nhiều principal độc lập cần bổ sung ràng buộc executor ở thẻ và kiểm thử cách ly tương ứng.

Cập nhật giữa đợt sửa:
- Nhóm 1 báo 30 bài kiểm thử lõi/tenant đạt; đang bổ sung migration, bảo vệ audit và chốt giao diện. Đã sửa ca trộn grantability/phạm vi giữa hai role, invite đúng team và parent org cùng phạm vi. Chưa chạy tổng hợp độc lập.
- Nhóm 2 đã triển khai schema strict và service duyệt/worker; đang khớp binding worker response và cập nhật bộ API test cũ. Có lỗi quan hệ ORM mơ hồ sau thêm FK được chuyển nhóm 1 xử lý.
- Nhóm 3 báo 12 bài worker đạt; tiếp tục bổ sung binding payload và test tích hợp API. Chưa coi bộ legacy API cũ đã đạt.
- Giao diện `/team` đã chuyển dữ liệu mẫu thành trạng thái chưa kết nối, không hiển thị giả dữ liệu doanh nghiệp. Chưa kiểm tra trình duyệt.
- Phát hiện source `sin_content_api/src/auth/tenancy.py` thay đổi ngoài bản secure đã kiểm tra, quay về offline fallback. Chưa xác định tác nhân; các agent khác trong nhóm xác nhận không sửa vùng này. Agent sở hữu đang khôi phục và lưu hash. Đã tạo `00_bat_dau/COMMAND_CONTROL_CARD.md` để phối hợp tránh sửa chồng.
- Chốt bổ sung về worker: model đã có `worker_subject` trước khi quyết định tối giản được truyền đến; giữ field, chỉ điền từ cấu hình server và so subject lúc recheck. Vẫn chỉ hỗ trợ một principal pool. Mỗi kết quả ALLOW phải có binding workspace/resource/version/hash/policy để bên thực thi đối chiếu payload, không chỉ bool.
- Bộ xác minh chỉ xác minh token do bên ngoài cấp; chưa có provider thực tế. Thiếu issuer/audience/key hoặc kho quyền phải từ chối. Chưa kiểm chứng PostgreSQL/RLS, staged rollout hoặc production.

Kiểm tra tổng hợp độc lập lượt 1: `python 03_ban_lam_viec/baha_auth/kiem_tra_tong_hop_phan_quyen.py` mã thoát 0; 78 bài auth + 9 bài API + 14 bài worker = 101 đạt. Không có lỗi cú pháp; 105 tệp được khảo sát không đổi mã băm trong lúc chạy. Bằng chứng: `08_kiem_thu/bang_chung/ket_qua_tong_hop_sua_phan_quyen_2026_10_21.json` và các log `kiem_thu_tong_hop_phan_quyen_*`.

Rà soát nhóm 2 độc lập nêu 2 P1 trong `ra_soat_doc_lap_nhom_2.md`; đã giao lại agent gốc sửa vòng 1.

Quyết định: worker phải có tenant được ký trong token dịch vụ (`workspace_id`), đặt tenant context trước truy vấn grant, không dùng truy vấn toàn tenant hay hàm nâng quyền để tìm workspace. Token hiện tại được cấu hình theo mỗi tiến trình worker; hỗ trợ nhiều tenant trong một pool cần thiết kế quản lý token tương ứng sau. Thiếu claim phải từ chối. Cái giá: token worker cũ không có claim tenant sẽ cần cấp lại.

Quyết định: coi owner và creator của tài nguyên đều thuộc bên có xung đột lợi ích khi duyệt, nhất quán scope OWN đang cấp quyền dữ liệu cá nhân theo cả hai trường. Từ chối cả hai tự duyệt, giữ kiểm thử người độc lập được duyệt. Cái giá: một quản lý được ghi owner nhưng không phải tác giả sẽ cần người duyệt độc lập; cần xác nhận ngữ nghĩa ownership trước phát hành thật.

Quyết định: tạo bản nháp brief sử dụng quyền soạn `brief.edit` hiện có; không thêm quyền/ngầm cấp ma trận mới. Các action thiếu thật sự `workspace.create`, `evidence.import`, `evidence.purge` vẫn từ chối và ghi rõ endpoint chưa mở.

## Đóng đợt sửa

- Nhóm 1: hoàn thành bản sửa trong phạm vi, report `bao_cao_sua_nhom_1.md`.
- Nhóm 2: hoàn thành và sửa vòng 1, full auth 86 bài đạt; report `bao_cao_sua_nhom_2.md`. Claim workspace worker và kiểm tra owner/creator đã được đối chiếu source độc lập.
- Nhóm 3: hoàn thành tích hợp; bổ sung kiểm thử P09 thiếu resource và sửa dò brief ID. API tích hợp cuối 11 bài đạt, worker 14 bài đạt.
- Rà soát tổng hợp: các P2 PROJECT được đóng bằng làm rõ phạm vi, brief được sửa code/test; không còn phát hiện đang mở trong phạm vi đã đọc. Không dùng kết luận này thay xác minh PostgreSQL/staging.
- Kiểm chứng điều phối cuối: 111 bài đạt, runner mã thoát 0, cú pháp 0 lỗi, 105 tệp hash ổn định. Không mở rộng chạy bộ legacy nghiệp vụ chưa chuyển sang auth mới; giới hạn này được ghi báo cáo.
- Bàn giao `bao_cao_khac_phuc_phan_quyen_2026_10_21.md`; CURRENT_STATE ưu tiên báo cáo mới. Không tạo checkpoint, không phát hành hoặc đổi quyền sống.
