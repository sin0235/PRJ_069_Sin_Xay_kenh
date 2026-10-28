# Kiểm kê A00 PRJ_069: nguồn dữ liệu và cấu hình NAS

**Trạng thái:** BLOCKED; đây là kết quả kiểm kê dữ liệu, chưa phải hồ sơ A00 hoàn chỉnh hoặc phê duyệt production.  
**Ngày:** 2026-10-28  
**Phạm vi:** chỉ đọc cấu hình NAS và SQLite trong vùng `03_ban_lam_viec`; không đọc giá trị tệp môi trường, không sửa DB, volume, container, tunnel hoặc Cloudflare.

## Cách kiểm tra

- Đọc `ha_tang/nas_kiem_thu_that/docker-compose.yml` và `khoi_tao_du_lieu.py`; chỉ xuất tên biến môi trường, trạng thái an toàn và tên tệp DB, không xuất giá trị secret.
- Mở SQLite qua URI `mode=ro`; chạy `PRAGMA integrity_check`, đếm bản ghi ở các bảng định danh/dữ liệu liên quan và kiểm tra giao nhau workspace/membership. Không đọc nội dung kịch bản, media hoặc email người dùng.
- Tìm đúng email Founder do Founder cung cấp bằng phép đếm khớp chính xác; chỉ ghi số lượng kết quả, không ghi lại email hoặc hàng DB.

## Cấu hình NAS đang lưu

- Compose `nas_kiem_thu_that` khai báo `APP_ENV=development`, `TESTING=0`, `DEV_AUTH_BYPASS=1`, `SYNTHETIC_DATA_ALLOWED=false`, `LLM_ENABLED=true`.
- API trỏ `DATABASE_URL` tới `sin_content_e2e_test.db` và `BAHA_AUTH_DATABASE_URL` tới `baha_auth_e2e_test.db` trong volume `/persist`. Tệp môi trường `9rt.env` được Compose nạp; không mở hoặc đọc giá trị của tệp này.
- `khoi_tao_du_lieu.py` sao lưu nguyên tử các bản `sin_content_e2e_test.db`, `baha_auth_e2e_test.db` và `sin_dieu_phoi_dung.db` vào volume, bổ sung schema test rồi chép media từ thư viện dùng chung. Marker khiến các lần chạy sau giữ nguyên volume.
- Vì vậy tên stack `nas_kiem_thu_that` không chứng minh dữ liệu trong volume là DB nghiệp vụ thật. Nội dung hiện thời của volume `du_lieu_that` chưa được đọc trực tiếp; có thể đã phát sinh ghi sau lúc khởi tạo. Không khởi động initializer/API để thử.
- Bổ sung kiểm tra trực tiếp DSM ngày 2026-10-28: log initializer ghi đã chép ba DB E2E và 118 tệp media vào volume lúc 18:07 ngày 2026-10-27; 27 tệp media được tham chiếu không có trong nguồn. Các lần chạy sau ghi volume đã khởi tạo và được giữ nguyên. Bằng chứng này xác nhận nguồn gốc ban đầu là E2E, nhưng chưa xác nhận trạng thái hiện tại bên trong volume hoặc các ghi mới sau thời điểm khởi tạo.
- Kiểm tra Edge hiện báo `ERR_NAME_NOT_RESOLVED` cho hostname đã chọn. DSM liệt kê project với ba container API, FE và khởi tạo dữ liệu; không khởi động container nào trong lượt này. Tệp xác thực/FE cục bộ khác hash với bản NAS hoặc chưa có trên NAS; chưa ghi đè bản SSOT.

## Kiểm tra DB nguồn chỉ đọc

| Tệp | Kích thước | Tính toàn vẹn | Kết quả chính |
|---|---:|---|---|
| `sin_content_offline.db` | 1.040.384 byte | `ok` | 119 users, 78 workspaces, 119 memberships, 65 brand briefs, 12 media assets |
| `baha_auth_live.db` | 819.200 byte | `ok` | 244 global users, 121 workspaces, 244 memberships, 245 role assignments, 125 business resources, 8 approval policies, 336 sự kiện audit |
| `sin_content_e2e_test.db` | 1.757.184 byte | `ok` | 119 users, 78 workspaces, 119 memberships, 65 brand briefs, 146 media assets |
| `baha_auth_e2e_test.db` | 2.215.936 byte | `ok` | 244 global users, 121 workspaces, 244 memberships, 245 role assignments, 125 business resources, 8 approval policies, 4.991 sự kiện audit |

- Cặp DB nguồn `sin_content_offline.db` và `baha_auth_live.db` chỉ có một workspace ID và một cặp membership `(workspace_id, user_id)` trùng nhau. Không thể xem đây là bộ dữ liệu đã đối soát đầy đủ.
- Workspace giao nhau là `default_ws`; DB Baha Auth ghi nhận hai membership ACTIVE, hai assignment `WORKSPACE_OWNER` ở scope workspace và không có approval policy ACTIVE cho workspace này.
- Có một hàng với ID mẫu `usr_sin_owner` trong Baha Auth live DB; không dựa vào ID này để cấp quyền. Email Founder không khớp hàng nào trong Baha Auth live DB hoặc DB content.
- DB content nguồn có 78 workspace, trong đó nhiều workspace mang tên dành cho kiểm thử (`P09 Script Workspace`, `Sin Source Test WS`, `Sin Planning Test WS`). Cấu hình `platform_llm_configurations` đọc chỉ có model `gpt-4o-mini` và base URL local `127.0.0.1:20128/v1`; chưa xác minh `9rt.env` có hiệu lực với singleton hiện có. Không thể coi nguồn này đã sẵn sàng cho LLM Luna 6.
- `sin_content_offline.db` có bốn vi phạm khóa ngoại: hai ở `media_assets`, một ở `source_records`, một ở `source_observations`. Không sửa hoặc tự gán các bản ghi này.
- Có tệp `sin_content.db` rỗng 0 byte trong thư mục API; không chọn tệp này làm nguồn dữ liệu.

## Quyết định và cổng còn thiếu

1. **Không chạy production hoặc mở hostname.** Cấu hình NAS hiện có auth bypass, trỏ vào DB E2E, chưa có tài khoản Founder trong DB live, thiếu approval policy cho `default_ws`, và cặp DB nghiệp vụ chưa khớp định danh.
2. **Không cấp quyền live.** Tài liệu RBAC yêu cầu hoàn thành A00, duyệt workspace/ma trận vai trò, dry-run, rollback và phát hành của Founder trước thay đổi quyền production.
3. Kiểm kê mã nguồn tĩnh cho thấy 110 khai báo endpoint API ở 17 module; giao diện build được 43 route; các worker chính nằm ở `media_studio/job_engine.py` và `voice_studio/worker.py`; chức năng tải media tập trung ở router media. Bằng chứng: `03_ban_lam_viec/sin_content_api/08_kiem_thu/bang_chung/kiem_ke_ma_nguon_api_giao_dien_20261028.md`. Chưa đối chiếu inventory này với trạng thái volume/container hoặc nghiệm thu từng luồng thật.
4. Để A00 đạt, còn cần kiểm tra chỉ đọc nội dung hiện tại của volume Docker đang dừng, chốt DB và workspace chuẩn, xử lý bốn vi phạm khóa ngoại theo quyết định của chủ dữ liệu, ký ma trận quyền và policy ngoại lệ tự duyệt Founder. Log DSM xác nhận volume ban đầu được seed từ E2E, nhưng không thay thế việc kiểm tra tệp hiện hành.
5. Mã xác thực Cloudflare Access, FE, tài liệu và bằng chứng đã được đồng bộ lên vùng SSOT NAS; 45 tệp được chép và SHA-256 khớp cho 46/46 mục tiêu. Bản khôi phục các tệp NAS cũ: `03_ban_lam_viec/bao_luu_phuc_hoi_xac_thuc_cloudflare_20261028_100520/`. Edge vẫn báo hostname chưa có DNS phân giải. Chưa thay Compose, DB, volume hoặc Cloudflare; chưa chạy container, tạo tài khoản hay gọi LLM thật.

## Bằng chứng kiểm thử mã cục bộ

- `python -m pytest 03_ban_lam_viec/baha_auth/tests/test_xac_minh_cloudflare_access.py 03_ban_lam_viec/baha_auth/tests/test_kiem_tra_phan_quyen_nhom_1.py 03_ban_lam_viec/baha_auth/tests/test_a02_a07_comprehensive.py 03_ban_lam_viec/baha_auth/tests/test_kiem_thu_duyet_tac_vu_nen.py -q`: 70 passed.
- `python -m pytest 03_ban_lam_viec/sin_content_api/tests/test_tenancy.py 03_ban_lam_viec/sin_content_api/tests/test_dev_auth_bypass.py 03_ban_lam_viec/sin_content_api/tests/test_gate2_owner_db_and_secrets.py -q`: 27 passed.
- `npm exec tsc -- --noEmit` trong `sin_creator_os`: mã thoát 0.
- `npm run build` trong `sin_creator_os`: mã thoát 0, 43 route; còn một cảnh báo cấu hình npm và một cảnh báo Starlette trong pytest.

Các kiểm thử trên dùng fixture/DB RAM; không xác nhận tài khoản, quyền, LLM, volume hoặc route Cloudflare live. A00 vẫn BLOCKED cho đến khi những mục trên có bằng chứng và chữ ký phê duyệt.
