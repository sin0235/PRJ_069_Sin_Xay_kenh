# MA TRẬN TÍCH HỢP PHÂN QUYỀN RBAC & GIAO DIỆN FRONTEND
## Hệ Thống Trí Tuệ Nội Dung SIN x BAHA Creator Studio (PRJ_069)

- **Mã kế hoạch:** RBAC-FE-INTEGRATION-001
- **Phiên bản:** 1.0.0
- **Ngày lập:** 22/10/2026
- **Trạng thái:** TÀI LIỆU ÁNH XẠ KIẾN TRÚC & PHÂN QUYỀN — **CHƯA CODE (SPECIFICATION ONLY)**
- **Tiêu chuẩn tham chiếu:** 
  - Gói phân quyền doanh nghiệp: `BAHA-AUTHZ-001` (58 Action Keys x 15 Tổ Chức Vai Trò)
  - Phân hệ trí tuệ nội dung: `SIN-CONTENT-INTELLIGENCE-001` (P00 - P14)
  - Giao diện người dùng: `BAHA Creator Studio` (`03_ban_lam_viec/sin_creator_os/`)

---

## 1. Ma Trận Ánh Xạ API Endpoints x RBAC Action Keys x Vai Trò

Dưới đây là ma trận phân quyền chi tiết cho toàn bộ các endpoints của phân hệ Trí tuệ Nội dung, đảm bảo nguyên tắc Chặn Mặc Định (Deny-by-default):

| Nhóm Chức Năng | API Endpoint | Phương Thức | Quyền Hành Động (Action Key) | Cấp Độ Rủi Ro (Tier) | Vai Trò Tối Thiểu Được Phép | Quy Tắc Phê Duyệt Đặc Biệt |
|---|---|---|---|---|---|---|
| **Brief Thương Hiệu** | `/v1/briefs` | POST | `brief.create` | STANDARD | `marketing_lead`, `brand_manager` | Tạo bản nháp (DRAFT) |
| | `/v1/briefs/{id}` | GET | `brief.read` | READ_ONLY | `viewer`, `creator`, `editor` | Cách ly theo workspace |
| | `/v1/briefs/{id}/approve` | POST | `brief.approve` | SENSITIVE | `marketing_director`, `brand_owner` | **Cấm người tạo tự duyệt** (Four-eyes) |
| **Nguồn Dữ Liệu** | `/v1/sources` | GET | `sources.read` | READ_ONLY | `researcher`, `creator`, `lead` | Chỉ đọc nguồn đã kết nối |
| | `/v1/sources/connect` | POST | `sources.manage` | SENSITIVE | `workspace_admin`, `owner` | Chỉ Admin được kết nối nguồn |
| | `/v1/sources/sync` | POST | `sources.sync` | STANDARD | `researcher`, `lead` | Kiểm tra hạn mức tác vụ |
| | `/v1/sources/evidence/{id}` | GET | `evidence.read` | READ_ONLY | `researcher`, `creator`, `editor` | Trích dẫn nguồn xác thực |
| **Nghiên Cứu & Khám Phá** | `/v1/research-runs` | POST | `research.run` | SENSITIVE | `researcher`, `content_lead` | **Pre-flight Budget Guard** |
| | `/v1/research-runs/{id}` | GET | `research.read` | READ_ONLY | `creator`, `editor`, `lead` | Lịch sử tác vụ |
| | `/v1/research-runs/{id}/cancel` | POST | `research.manage` | STANDARD | `researcher`, `lead`, `admin` | Hủy và hoàn lại ngân sách giữ chỗ |
| **Phòng Lab Ý Tưởng** | `/v1/ideation/generate` | POST | `idea.create` | STANDARD | `creator`, `copywriter`, `lead` | Sinh thẻ ý tưởng có căn cứ |
| | `/v1/ideation/cards` | GET | `idea.read` | READ_ONLY | Mọi vai trò trong workspace | Danh sách thẻ ý tưởng |
| | `/v1/ideation/cards/{id}/review` | POST | `idea.review` | SENSITIVE | `content_lead`, `reviewer`, `owner` | **Bắt buộc expected_version, cấm tự duyệt** |
| | `/v1/ideation/cards/{id}` | DELETE | `idea.delete` | SENSITIVE | `content_lead`, `workspace_admin` | Đánh dấu xóa mềm (soft-delete) |
| **Soạn Thảo Kịch Bản** | `/v1/scripts` | POST | `script.create` | STANDARD | `scriptwriter`, `creator`, `lead` | Bản nháp ban đầu (DRAFT) |
| | `/v1/scripts/{id}` | GET | `script.read` | READ_ONLY | Mọi vai trò trong workspace | Xem kịch bản |
| | `/v1/scripts/{id}` | PUT | `script.edit` | STANDARD | `scriptwriter`, `creator`, `lead` | Sửa bản DRAFT; nếu sửa bản APPROVED tự sinh version mới |
| | `/v1/scripts/{id}/approve` | POST | `script.approve_final` | CRITICAL | `content_director`, `client_approver` | **Chặn nếu có tuyên bố vi phạm AllowedFact** |
| **Phản Hồi & Kênh** | `/v1/feedback/channels/connect` | POST | `channel.connect` | CRITICAL | `workspace_admin`, `owner` | Xác thực OAuth từ máy chủ |
| | `/v1/feedback/channels/{id}/perf` | GET | `channel.read` | READ_ONLY | `analytics_viewer`, `lead`, `owner` | Chỉ đọc số liệu quan sát thật |
| | `/v1/feedback/velocity/calculate` | POST | `analytics.read` | STANDARD | `researcher`, `creator`, `lead` | Tính vận tốc >= 2 snapshots |
| | `/v1/feedback/published-links` | POST | `published_link.manage` | STANDARD | `content_distributor`, `lead` | Nối video đã đăng với kịch bản |
| **Ngân Sách & Vận Hành** | `/v1/staging/budget/reserve` | POST | `ai_budget.update` | SENSITIVE | `system_worker`, `admin` | Kiểm tra số dư nguyên tử |
| | `/v1/staging/billing/reconcile` | POST | `billing.manage` | CRITICAL | `finance_admin`, `owner` | Đối soát chi phí nhà cung cấp |

---

## 2. Ánh Xạ 16 Màn Hình Frontend BAHA Creator Studio

Hệ thống giao diện người dùng hiển thị trực quan các chức năng theo đúng thẩm quyền được phân cấp:

| STT | Đường Dẫn (Route) | Tên Màn Hình | Vai Trò Chính Sử Dụng | Yêu Cầu Tích Hợp RBAC & Trí Tuệ Nội Dung |
|---|---|---|---|---|
| 1 | `/dashboard` | Tổng Quan Creator | Mọi thành viên | Hiển thị 6 KPI tổng hợp, gợi ý ý tưởng thịnh hành (chỉ hiển thị khi có chứng cứ thực tế). |
| 2 | `/discover` | Khám Phá Xu Hướng | `researcher`, `creator` | Lưới 4 cột video viral; bộ lọc đa tầng; hiển thị nguồn, phương thức lấy mẫu và nhãn bằng chứng. |
| 3 | `/discover/[contentId]` | Bóc Tách Chi Tiết | `researcher`, `creator` | Timeline retention giữ chân người xem; 10 chỉ số phân tích NLP; công thức biến đổi nội dung. |
| 4 | `/ideas` | Bảng Ý Tưởng (Lab) | `creator`, `lead` | Kanban/List ý tưởng; nhãn rõ ràng `EVIDENCE_BACKED` vs `HYPOTHESIS`; điểm số 5 chiều. |
| 5 | `/ideas/generate` | Phòng Tạo Ý Tưởng | `creator`, `lead` | 3 cột: Cấu hình yêu cầu -> Danh sách ý tưởng sinh ra -> Bằng chứng trích dẫn chứng minh. |
| 6 | `/scripts/[id]` | Script Studio | `scriptwriter`, `lead` | 3 cột: Bối cảnh chiến lược -> Soạn thảo 5 block (Hook/Setup/Value/Proof/CTA) -> Fact-checking AllowedFact. |
| 7 | `/ai-studio` | Trung Tâm AI | `creator`, `editor` | 10 công cụ AI; hiển thị số dư credit thời gian thực; chặn gọi model khi vượt ngân sách (P12). |
| 8 | `/video-studio/[id]` | Phòng Dựng Video | `video_editor` | Khung hình dọc 9:16; đường ranh Safe Zone TikTok (Top 150px, Bottom 320px, Right 120px); inspector layer. |
| 9 | `/content` | Kế Hoạch Nội Dung | `lead`, `manager` | Kanban quy trình 6 bước kéo thả: Idea -> Script -> Production -> Review -> Scheduled -> Published. |
| 10 | `/calendar` | Lịch Xuất Bản | Mọi thành viên | Lịch phát sóng đa kênh; modal xem trước nhanh; trạng thái duyệt xuất bản. |
| 11 | `/media` | Kho Tài Nguyên Số | `editor`, `creator` | B-roll video, nhạc nền xu hướng, voice AI; kiểm soát bản quyền tài nguyên số. |
| 12 | `/publishing` | Soạn Bài & Xuất Bản | `distributor`, `lead` | Mô phỏng điện thoại (Mockup 9:16); đặt lịch xuất bản; chỉ cho phép đăng bài đã APPROVED. |
| 13 | `/analytics` | Phân Tích Chuyên Sâu | `lead`, `director` | Biểu đồ tỷ lệ xem hết; tách biệt tuyệt đối giữa nhóm Tự nhiên (Organic) và Quảng cáo (Paid). |
| 14 | `/competitors` | Radar Đối Thủ | `researcher`, `lead` | Theo dõi tài khoản đối thủ; snapshot lượt xem định kỳ; phân tích khoảng trống nội dung. |
| 15 | `/channels` | Quản Lý Kênh TikTok | `workspace_admin` | Kết nối tài khoản chính thức qua OAuth; hiển thị trạng thái scope `channel:metrics` trung thực. |
| 16 | `/settings/team` | Quản Trị Đội Ngũ | `owner`, `admin` | Phân quyền 15 vai trò tổ chức; mời thành viên; áp dụng chính sách bảo vệ chủ sở hữu cuối cùng. |

---

## 3. Quy Tắc Tách Bạch Trách Nhiệm & Kiểm Soát Bốn Mắt (Separation of Duties)

Để đảm bảo tính toàn vẹn và chất lượng nội dung trước khi xuất bản, hệ thống áp dụng các rào chắn cứng (Hard Guardrails):

1. **Cấm Tự Phê Duyệt Nội Dung (No Self-Approval):**
   - Người tạo kịch bản (`creator_id`) không được phép đồng thời là người bấm nút phê duyệt (`approved_by_user_id`).
   - Nếu `current_user.id == card.created_by_user_id`, backend lập tức từ chối thao tác phê duyệt với mã lỗi HTTP 403 `CANNOT_APPROVE_OWN_CREATION`.

2. **Cấm Sửa Đổi Trực Tiếp Kịch Bản Đã Duyệt (Immutable Versioning):**
   - Khi kịch bản đã ở trạng thái `APPROVED`, bất kỳ thao tác chỉnh sửa lời thoại hoặc phân cảnh nào sẽ tự động chuyển bản ghi cũ sang trạng thái `SUPERSEDED` và sinh ra một bản nháp mới (`version = version + 1`, `DRAFT`).
   - Bản nháp mới bắt buộc phải trải qua toàn bộ quy trình kiểm định sự thật (`ClaimChecker`) và kiểm duyệt lại từ đầu.

3. **Chặn Phê Duyệt Khi Còn Tuyên Bố Chưa Xác Thực (Blocking Unverified Claims):**
   - Bất kỳ kịch bản nào có chứa tuyên bố định lượng (ví dụ: "giảm 50%", "bảo hành trọn đời", "inox 304 chuẩn y tế") mà không khớp 100% với danh mục sự thật thương hiệu (`AllowedFact`) sẽ bị hệ thống gắn nhãn `BLOCKING_CLAIM`.
   - Cấm chuyển trạng thái sang `APPROVED`, trả về mã lỗi HTTP 422 `CANNOT_APPROVE_UNVERIFIED_CLAIMS`.

4. **Ủy Quyền Hẹp Cho Tác Tử AI & Worker Xử Lý Ngầm:**
   - Khi một tác vụ nền (như quét số liệu hoặc sinh kịch bản tự động) được kích hoạt, worker chỉ được cấp phát một mã thông báo ủy nhiệm tạm thời (Delegated Scoped Token) kế thừa đúng phạm vi hẹp của người kích hoạt.
   - Nếu tài khoản người dùng bị khóa hoặc bị thu hồi quyền trong lúc job đang chạy, worker phải lập tức tự hủy tác vụ và ghi log kiểm toán.

---

## 4. Cam Kết Hiện Tại: Chỉ Quy Hoạch Kế Hoạch, Chưa Code

Tài liệu này xác lập ma trận ánh xạ phân quyền và giao diện chuẩn mực, làm căn cứ đối soát cho đợt triển khai mã nguồn tiếp theo. Toàn bộ mã nguồn hệ thống hiện tại chưa bị thay đổi.
