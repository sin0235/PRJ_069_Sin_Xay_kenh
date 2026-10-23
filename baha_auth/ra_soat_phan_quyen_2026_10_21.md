# Rà soát triển khai phân quyền BAHA-AUTHZ-001 — 21/10/2026

Triển khai hiện có tạo dịch vụ `baha_auth` riêng với mô hình tổ chức, vai trò, bộ đánh giá quyền, duyệt và thẻ ủy quyền tác vụ nền. Tuy nhiên, dịch vụ nghiệp vụ vẫn dùng cơ chế quyền cũ; chưa đủ điều kiện nghiệm thu A00–A10 hoặc chuyển sang phát hành A11.

## Phạm vi và bằng chứng

- Đối chiếu tám tài liệu chuẩn RBAC tại `02_nguyen_ban_giai_nen/baha_group_anti_rbac_plan/`, trạng thái dự án, checkpoint và báo cáo triển khai.
- Đọc mã `baha_auth/src`, toàn bộ kiểm thử RBAC, điểm tích hợp trong `sin_content_api`, tìm kiếm trong `sin_content_workers`, và trang `/team` của giao diện. Kho Git chưa có đường cơ sở mã nguồn được theo dõi để đối chiếu một thay đổi riêng.
- Lệnh: `python 03_ban_lam_viec/baha_auth/ra_soat_phan_quyen_2026_10_21.py`.
- Môi trường kiểm thử: Python 3.11, SQLite chỉ trong RAM, dùng chung kết nối cho TestClient, bật khóa ngoại; ghi đè cấu hình trước khi nạp ứng dụng. Không ghi vào cơ sở dữ liệu dự án, không gọi nhà cung cấp hoặc môi trường thật.
- Kiểm thử sẵn có: **24 đạt, 2 cảnh báo, mã thoát pytest 0**. Các tình huống bổ sung tái hiện hành vi sai, không phải kiểm thử xác nhận an toàn.
- Nhật ký: `08_kiem_thu/bang_chung/kiem_thu_ra_soat_phan_quyen_2026_10_21.txt`.
- Kết quả tái hiện: `08_kiem_thu/bang_chung/tai_hien_loi_phan_quyen_2026_10_21.json`.
- Tải đánh giá: thao tác thông thường của nhiều thành viên thuộc nhiều nhóm/tenant. Những lỗi bên dưới đã xuất hiện với yêu cầu đơn lẻ; không cần tải cao.

## Bắt buộc sửa trước nghiệm thu

### 1. [P0] Giả danh người dùng bằng header

**Vị trí:** `src/api/deps.py:9–39`.

**Chức năng:** Xây dựng danh tính và quyền từ người dùng đang gọi API.

**Lỗi:** Chỉ cần gửi `X-Workspace-Id` và `X-User-Id` của Owner, không cần token/session đã xác thực, đã tạo được đơn vị tổ chức với HTTP 201 và có bản ghi trong RAM. Không có điều kiện giới hạn cơ chế này theo môi trường.

**Sửa:** Lấy định danh từ session/token được xác minh bằng nhà cung cấp danh tính tin cậy; workspace chỉ được chọn sau khi xác thực và kiểm tra membership. Nếu giữ giả lập thì phải tách cấu hình và cấm bật trên staging/production.

**Nếu bỏ qua:** Người biết định danh có thể hành động dưới quyền người khác. Lỗi này cũng hiện diện trong `sin_content_api/src/auth/tenancy.py` và đã được báo cáo ở rà soát P01/P02.

### 2. [P1] RBAC mới chưa bảo vệ luồng nghiệp vụ

**Vị trí:** `sin_content_api/src/auth/tenancy.py:83`, `sin_content_api/src/modules/briefs/router.py:85`, `sin_content_api/src/main.py`.

**Chức năng:** Dịch vụ nghiệp vụ xử lý brief, nghiên cứu và nội dung.

**Lỗi:** Mã vẫn dùng `require_role` và trọng số vai trò cũ; không gọi bộ đánh giá RBAC mới. Tìm kiếm `baha_auth`, `authz`, `require_action`, `evaluate_permission` không thấy điểm tích hợp trong API nghiệp vụ/worker/giao diện tại thời điểm khảo sát. Hai dịch vụ còn có mô hình Membership riêng.

**Sửa:** Thống nhất định danh tenant/membership và gắn kiểm tra action cùng tài nguyên vào các endpoint/job thật; kiểm thử thu hồi quyền qua chính API nghiệp vụ.

**Nếu bỏ qua:** Thu hồi quyền trong `baha_auth` không bảo đảm chặn thao tác nghiệp vụ; nhãn A05 bao phủ toàn bộ API không phản ánh triển khai.

### 3. [P1] Trưởng nhóm có thể cấp quyền toàn workspace

**Vị trí:** `src/services/role_service.py:42–79`, `src/api/deps.py:97–98`.

**Chức năng:** Gán vai trò cho thành viên.

**Lỗi:** Chỉ kiểm tra tên vai trò được cấp, không kiểm tra phạm vi đích là tập con của phạm vi người cấp. TEAM_LEAD của `team-1` cấp RESEARCHER với `scope_type=WORKSPACE` thành công HTTP 201.

**Sửa:** Giải quyết phạm vi phía máy chủ, đối chiếu cả người nhận, tài nguyên phạm vi và quyền người cấp trong cùng một phép kiểm tra; từ chối cấp vượt nhóm/phòng/tenant.

**Nếu bỏ qua:** Quản lý cấp thấp mở quyền đọc/ghi sang các đơn vị không thuộc thẩm quyền.

### 4. [P1] Owner vượt danh mục vai trò được cấp

**Vị trí:** `src/services/role_service.py:56–65`.

**Chức năng:** Áp dụng danh mục vai trò mà người cấp được phép phân công.

**Lỗi:** Ngoại lệ `WORKSPACE_OWNER` bỏ qua danh mục; API cấp `PLATFORM_OPS` thành công HTTP 201 và tự tạo vai trò nếu chưa tồn tại. Đây là vi phạm chính sách cấp vai trò; chưa chứng minh vai trò nền tảng này mở thêm quyền dữ liệu vì ma trận hiện không cấp quyền nghiệp vụ cho nó.

**Sửa:** Bỏ ngoại lệ, bắt buộc vai trò nằm trong danh mục được phê duyệt; không tự tạo role từ chuỗi tùy ý trong thao tác gán.

**Nếu bỏ qua:** Quy trình quản trị không còn giới hạn vai trò được phép phân công và có thể kích hoạt quyền ngoài ý muốn khi chính sách thay đổi.

### 5. [P1] Vai trò hết hạn vẫn có hiệu lực

**Vị trí:** `src/api/deps.py:52–65`, `src/services/role_service.py:43–47`.

**Chức năng:** Nạp các phân công vai trò còn hiệu lực.

**Lỗi:** Chỉ lọc `status=ACTIVE`, bỏ qua `valid_from`, `valid_until` và trạng thái Role. EXECUTIVE hết hạn một ngày vẫn tạo đơn vị tổ chức HTTP 201.

**Sửa:** Áp dụng khoảng hiệu lực và trạng thái tại tất cả đường đọc quyền, gồm cấp quyền và worker; kiểm tra trạng thái tài khoản/workspace theo chính sách.

**Nếu bỏ qua:** Quyền tạm thời không tự hết hạn như cam kết.

### 6. [P1] Quyền nhóm này lan sang nhóm khác

**Vị trí:** `src/policy/evaluator.py:95–128`.

**Chức năng:** So khớp action và phạm vi của từng phân công.

**Lỗi:** TEAM_LEAD được cấp tại `team-1`, đồng thời là thành viên thường của `team-2`, nhận ALLOW cho `ideas.read` tại `team-2`. Điều kiện dùng toàn bộ `actor.team_ids` thay vì giữ quyền gắn với scope của đúng assignment; phạm vi lấy từ ma trận chỉ được kiểm tra có giá trị rồi bỏ qua.

**Sửa:** So khớp từng cặp action/phạm vi độc lập, lấy giao giữa phạm vi chính sách và phân công; hỗ trợ rõ PROJECT và các phạm vi tài nguyên thật.

**Nếu bỏ qua:** Thành viên nhiều nhóm tích lũy quyền ngoài phạm vi được cấp, trái AUTH-022/033.

### 7. [P1] Dịch vụ tài nguyên bỏ kiểm tra quyền nội bộ

**Vị trí:** `src/services/tenant_service.py:62`, `:105`, `:121`, `:151`, `:183`.

**Chức năng:** Liệt kê, tìm kiếm, tổng hợp, tải và sửa tài nguyên.

**Lỗi:** Các hàm chỉ kiểm tra tenant hoặc lọc tenant. Actor không có role vẫn liệt kê được tài nguyên và sửa thành công dữ liệu của người khác trong cùng tenant; hàm tải trả đường URL dạng cố định không có chữ ký/hạn dùng.

**Sửa:** Thêm kiểm tra action và tài nguyên, lọc truy vấn theo phạm vi được phép. Dùng cơ chế ký URL thực sự ở lớp lưu trữ; chưa có bằng chứng URL hiện tại tải được file thật.

**Nếu bỏ qua:** Bộ test cách ly tenant vẫn xanh trong khi quyền sở hữu/nhóm bên trong tenant bị bỏ qua.

### 8. [P1] API đánh giá quyền tin thuộc tính tài nguyên từ client

**Vị trí:** `src/api/evaluate_router.py:19–34`.

**Chức năng:** Trả quyết định quyền cho tài nguyên cụ thể.

**Lỗi:** Không truy xuất tài nguyên; gán workspace theo actor và nhận owner/creator/org từ payload. Owner đánh giá `ideas.read` cho ID không tồn tại vẫn nhận ALLOW.

**Sửa:** Chỉ nhận định danh tài nguyên, tra cứu các thuộc tính đáng tin phía máy chủ; tài nguyên thiếu hoặc ngoài phạm vi phải DENY. Phân biệt kiểm tra khả năng chung với kiểm tra đối tượng cụ thể.

**Nếu bỏ qua:** Kết quả đánh giá không chứng minh được quyền trên tài nguyên thật và có thể bị giả mạo các điều kiện sở hữu/duyệt.

### 9. [P1] Worker nhận quyền tùy ý và không tái kiểm tra quyền hiện tại

**Vị trí:** `src/api/worker_router.py:15–28`, `:41–66`; `src/services/worker_service.py:70–86`.

**Chức năng:** Cấp và kiểm tra thẻ ủy quyền tác vụ nền.

**Lỗi:** Người có `publishing.schedule` tự gửi danh sách action tùy ý. Tái hiện cấp `fake.action`, thu hồi role người khởi tạo, rồi gọi `/workers/recheck` không xác thực: vẫn `allowed=true`. Không xác minh tài nguyên, phiên bản duyệt, quyền hiện tại hay policy version.

**Sửa:** Sinh thẻ từ quyền hiện tại và tài nguyên thật; xác thực worker, ràng buộc danh tính/job/tenant và kiểm tra lại toàn bộ điều kiện ngay trước tác động phụ.

**Nếu bỏ qua:** Thu hồi vai trò không vô hiệu hóa tác vụ đặc quyền; thẻ không còn là tập con quyền người khởi tạo. Chưa kiểm chứng có bài đăng hoặc cuộc gọi nhà cung cấp thật phát sinh.

### 10. [P1] Người gửi tự chọn chính sách và người duyệt không bị ràng buộc vào chặng

**Vị trí:** `src/api/approval_router.py:15–29`, `:95–110`; `src/services/approval_service.py:26–59`, `:85–104`.

**Chức năng:** Tạo và xử lý luồng duyệt nhiều cấp.

**Lỗi:** Thành viên RESEARCHER tự tạo policy, hash và danh sách chặng cho một tài nguyên mà không kiểm tra quyền trên đối tượng. EXECUTIVE ký được chặng chỉ định `PLATFORM_OPS` với HTTP 200; không kiểm tra thứ tự chặng hay tác giả tài nguyên thật, chỉ so người mở run.

**Sửa:** Chọn policy đã phê duyệt phía máy chủ, truy xuất phiên bản/hash/tác giả từ đối tượng thật; xác minh người duyệt, phạm vi và chặng đang chờ.

**Nếu bỏ qua:** Có thể bỏ chuỗi duyệt hoặc nhờ sai người ký; SoD hiện chỉ bảo vệ người khởi tạo run, chưa bảo vệ tác giả thực.

### 11. [P1] Duyệt cuối không hoàn tất run và gửi lại sinh quyết định trùng

**Vị trí:** `src/services/approval_service.py:104–130`, `src/database.py:27`.

**Chức năng:** Chuyển trạng thái khi ghi nhận quyết định.

**Lỗi:** Session đặt `autoflush=False`; truy vấn đếm chặng PENDING chạy trước khi thay đổi step được đẩy xuống DB. Lần duyệt cuối trả 200 nhưng step APPROVED, run vẫn PENDING. Gửi cùng quyết định lần hai trả 200, lưu hai quyết định; không kiểm tra trạng thái run/step hoặc khóa phiên bản.

**Sửa:** Thực hiện chuyển trạng thái có điều kiện trong một giao dịch, flush trước tổng hợp; chặn xử lý lại bước đã quyết định và thêm khóa chống xung đột/idempotency.

**Nếu bỏ qua:** Quy trình mắc ở trạng thái chờ hoặc có nhiều quyết định cho cùng chặng. Chưa chạy kiểm thử tranh chấp đồng thời trên PostgreSQL.

### 12. [P1] Khóa ngoại không bảo đảm cùng tenant; RLS chưa được triển khai

**Vị trí:** `src/models/entities.py:92–101`, `src/database.py:52–65`.

**Chức năng:** Cách ly dữ liệu tại tầng cơ sở dữ liệu.

**Lỗi:** Với SQLite đã bật khóa ngoại vẫn ghi được OrgAssignment có workspace A trỏ tới phòng của B. Khóa ngoại đơn lẻ chỉ kiểm tra ID tồn tại. Không thấy migration/policy RLS trong gói `baha_auth`; `get_db` đọc tenant context trước khi dependency actor thiết lập context, và các commit trong service mở giao dịch tiếp theo mà không thiết lập lại GUC.

**Sửa:** Bổ sung ràng buộc cùng tenant bằng khóa ghép và migration được kiểm thử; thiết lập context đáng tin theo từng giao dịch trước truy vấn, thực thi RLS bằng runtime role đúng quyền.

**Nếu bỏ qua:** Các quan hệ chéo tenant vẫn tồn tại và lớp phòng vệ DB chưa chứng minh được AUTH-015/016. Phần RLS là kết luận đọc mã; chưa chạy PostgreSQL.

### 13. [P1] Thao tác cấp/thu hồi quyền và duyệt không có nhật ký kiểm toán

**Vị trí:** `src/api/deps.py:98–109`, `src/services/role_service.py:81–85`, `src/services/approval_service.py:115–130`.

**Chức năng:** Ghi lại ai thực hiện thao tác nhạy cảm và quyết định chính sách nào được dùng.

**Lỗi:** Sau các thao tác tạo/gán/thu hồi và duyệt, có 0 event `roles.assign`/`brief.approve`; event duy nhất do chủ động gọi API `/evaluate`. Cơ chế require_action không ghi quyết định. Không có ràng buộc DB chống sửa/xóa event; chỉ thiếu endpoint sửa chưa chứng minh tính bất biến.

**Sửa:** Ghi event ở điểm thực thi, liên kết giao dịch và request/policy version; thêm bảo vệ ghi nối tiếp tại DB và kiểm thử chống sửa.

**Nếu bỏ qua:** Không truy vết hoặc chứng minh được ai thay quyền/duyệt và vì sao; chưa đáp ứng A09.

### 14. [P1] Action bị viết sai khiến cả Owner không đọc được tài nguyên

**Vị trí:** `src/services/tenant_service.py:43–46`.

**Chức năng:** Kiểm tra quyền đọc một tài nguyên.

**Lỗi:** Mã gọi `idea.read`, trong registry là `ideas.read`. Owner đọc tài nguyên thật cùng tenant nhận None; test AUTH-010 chỉ kiểm tra ca đọc chéo tenant nên không phát hiện lỗi này.

**Sửa:** Dùng action đúng và bổ sung cặp kiểm thử đọc hợp lệ/từ chối trên cùng hàm; kiểm tra tĩnh tất cả action được dùng trong mã với registry.

**Nếu bỏ qua:** Đường đọc hợp lệ bị chặn dù kiểm thử cách ly tenant vẫn đạt.

### 15. [P1] Kết luận PASS vượt quá bằng chứng nghiệm thu

**Vị trí:** `docs/implementation/rbac/IMPLEMENTATION_STATUS.md:16–30`, `docs/implementation/rbac/AUDIT.md:148–156`.

**Chức năng:** Xác định pha nào được phép tiếp tục.

**Lỗi:** A00–A10 ghi PASS dựa trên 24 bài, trong khi danh mục bắt buộc gồm cả RLS, ma trận toàn vai trò, đồng thời, trình duyệt và staging. AUTH-040/061/070/071 đang được gán vào các kịch bản khác tiêu chí chuẩn; AUTH-002 được đánh dấu hoàn tất trong khi cơ cấu tổ chức ở BLOCKERS còn chờ Founder. Kiểm định tính hợp lệ của gói kế hoạch không thay thế chạy baseline ứng dụng hoặc nghiệm thu hệ thống.

**Sửa:** Lập ánh xạ từng ID chuẩn → bài kiểm thử → kết quả → bằng chứng; ghi FAIL/BLOCKED hoặc chưa kiểm tra đúng thực tế, tách duyệt nghiệp vụ khỏi test kỹ thuật. Chỉ cho tiếp tục khi đủ điều kiện phụ thuộc.

**Nếu bỏ qua:** Pha phát hành có thể dựa trên bằng chứng không kiểm tra các ranh giới quan trọng. Báo cáo này không sửa tài liệu ngoài phạm vi Codex và không tạo checkpoint.

## Cần sửa

### 16. [P2] Trang quản trị là dữ liệu mẫu, chưa phản ánh máy chủ

**Vị trí:** `sin_creator_os/src/app/(main)/team/page.tsx:17`, `:122`, `:162`.

**Chức năng:** Hiển thị thành viên, quyền, duyệt và nhật ký.

**Lỗi:** Các danh sách và ma trận được khai báo cứng; không thấy gọi API RBAC. Vì thế thay quyền/thu hồi ở máy chủ không chứng minh được thay đổi trên màn hình, trái kết luận A08 đã đạt.

**Sửa:** Kết nối dữ liệu và năng lực từ phiên xác thực, xử lý đổi workspace/thu hồi quyền, rồi chạy kiểm thử trình duyệt theo A08.

**Nếu bỏ qua:** Người vận hành nhìn trạng thái mẫu và có thể hiểu nhầm quyền đã được áp dụng.

## Kết luận và bàn giao

**Chưa chấp nhận phát hành; cần xử lý các mục 1–15 và nghiệm thu lại.** Có 16 phát hiện: 1 P0, 14 P1, 1 P2. Ưu tiên xác thực và tích hợp quyền vào nghiệp vụ, rồi giới hạn phạm vi/cấp quyền, worker, duyệt, ràng buộc DB và audit; sau đó mới xác nhận giao diện và staging.

24/24 bài hiện có đạt chỉ chứng minh các trường hợp đã viết. Không chứng minh hoàn thành A00–A10. Các tình huống tái hiện chạy riêng với dữ liệu giả lập sau khi bộ test hoàn thành, không sửa hay làm yếu test gốc.

Chưa kiểm tra: PostgreSQL/RLS bằng tài khoản runtime, trình duyệt, tải và đồng thời, nhà cung cấp thật, ký URL thật, production, dry-run di trú/khôi phục và chữ ký phê duyệt Founder. Mã ứng dụng và dữ liệu dự án chưa được sửa; chỉ thêm công cụ rà soát, báo cáo, bằng chứng và ghi chú trạng thái. Antigravity đối soát lại trạng thái pha và cập nhật trang hành trình gốc theo trách nhiệm được phân công.
