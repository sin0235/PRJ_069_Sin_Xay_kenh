# KẾ HOẠCH TÍCH HỢP HỆ THỐNG PHÂN QUYỀN & QUẢN TRỊ TỔ CHỨC (RBAC)

- **Mã kế hoạch:** BAHA-AUTHZ-001
- **Phiên bản nguồn:** 1.0
- **Ngày cơ sở:** 21/10/2026
- **Trạng thái:** Đã ghi nhận vào kế hoạch dự án; **CHƯA BẮT ĐẦU TRIỂN KHAI (NOT_STARTED)**.
- **Nguồn tham chiếu:** BAHA_GROUP_Anti_RBAC_Implementation_Plan_v1.zip tại thư mục gốc và 01_nguon_goc_bat_bien/.
- **Phân vùng đối soát nguyên bản:** 02_nguyen_ban_giai_nen/baha_group_anti_rbac_plan/.
- **Kết quả kiểm định gói (verify_plan.py):** ĐẠT 100% (13 phases, 58 permissions, 15 roles, 103 unique tests, 3 schemas, 3 synthetic tenants).
- **Phạm vi tài liệu này:** Tóm lược, phân tích và ánh xạ kiến trúc phân quyền chuẩn doanh nghiệp vào hệ sinh thái SIN Creator OS / Baha Group. Chưa thực hiện viết mã (chưa code).

---

## 1. Mục Tiêu Tích Hợp

Thiết lập khung quản trị phân quyền tập trung (Role-Based Access Control - RBAC), phân định ranh giới tổ chức (Organization Hierarchy), cách ly đa khách thuê (Multi-tenancy Isolation) và bảo vệ an toàn ranh giới dữ liệu cho toàn bộ hệ thống BAHA GROUP / SIN Creator OS.

Hệ thống bảo đảm:
1. **Phân cấp minh bạch**: Từ cấp Lãnh đạo/Chủ sở hữu (Owner/Executive), Quản lý bộ phận (Department Manager/Team Lead), Chuyên viên thực thi (Specialist/Editor), đến Đối tác phê duyệt bên ngoài (External Client/Partner Approver), Kiểm toán viên (Auditor), Khách (Guest) và Tác tử AI / Worker chạy ngầm (Delegated AI Principals).
2. **Nguyên tắc bảo vệ ranh giới**: Loại bỏ hoàn toàn nguy cơ rò rỉ dữ liệu chéo giữa các thương hiệu/kênh TikTok, cấm leo thang đặc quyền, cấm người tạo tự phê duyệt nội dung/ngân sách của mình, và kiểm soát chặt chẽ các tác vụ xuất dữ liệu hay tác vụ AI chi phí cao.

---

## 2. Ánh Xạ Vào Hệ Thống SIN Creator OS Hiện Tại

| Phân Hệ / Màn Hình | Hiện Trạng (CP01) | Định Hướng Ánh Xạ Phân Quyền (BAHA-AUTHZ-001) |
|---|---|---|
| **Multi-Tenancy & Workspace** | WorkspaceSwitcher chuyển đổi UI | Áp dụng Tenant Isolation & Row-Level Security (RLS). Mọi query API, cache và worker job phải ràng buộc chặt theo 	enant_id và workspace_id. |
| **Kênh TikTok & Đội Ngũ** (/channels, /team) | Quản lý kênh & danh sách thành viên | Áp dụng chính sách cấp phát quyền (ole_assignment_request), bảo vệ Chủ sở hữu cuối cùng (Last owner protection), cấm tự cấp quyền (No self-escalation). |
| **Khám Phá & Xu Hướng** (/discover, /trends) | Xem video viral, radar đối thủ | Phân quyền truy cập tài liệu nghiên cứu thị trường; giới hạn tải xuất hàng loạt dữ liệu nhạy cảm theo cấp bậc vai trò. |
| **Phòng Lab Ý Tưởng & Kịch Bản** (/ideas, /scripts) | Soạn thảo 5 block, AI Copilot | Phân tách quyền: Chuyên viên được tạo/chỉnh sửa bản nháp (DRAFT), nhưng chuyển sang phê duyệt (APPROVED) bắt buộc qua Team Lead/Content Manager. |
| **Trung Tâm AI** (/ai-studio) | 10 công cụ AI, voice clone, TTS | Thiết lập hạn ngạch ngân sách (Quota & Credit guard) theo vai trò; tác tử AI chạy ngầm kế thừa đúng quyền hạn hẹp của người ủy quyền. |
| **Dựng Phim & Media** (/video-studio, /media) | Canvas 9:16, Safe Zone, B-roll | Kiểm soát quyền truy cập kho tư liệu bản quyền; ngăn chặn tải xuống trái phép tài sản số trước ngày phát hành. |
| **Kế Hoạch & Xuất Bản** (/content, /publishing) | Pipeline Kanban, lịch phát sóng | **Quy tắc 4 mắt (Four-eyes principle)**: Cấm người tạo tự phê duyệt bài đăng của mình (No self-final-approval); cấm xuất bản lên TikTok khi chưa có chữ ký duyệt. |
| **Cấu Hình & API Vault** (/settings/integrations) | Quản lý khóa API, kết nối nền tảng | Thuộc nhóm đặc quyền Tối Cao (CRITICAL_SECURITY_CONFIG); chỉ Owner/Admin được ủy quyền mới có quyền cấu hình Vault, nghiêm cấm lộ secret trong log. |

---

## 3. Các Nguyên Tắc Bất Biến (Hard Invariants)

1. **Deny-by-default**: Mọi API endpoint, truy vấn cơ sở dữ liệu và tài nguyên đều bị chặn mặc định; chỉ mở khi có quyền hành động (ction_key) hợp lệ và phạm vi (scope) khớp.
2. **No Cross-Tenant Access**: Dữ liệu giữa các khách thuê/thương hiệu được cách ly tuyệt đối từ tầng database (RLS/Foreign key guard) đến tầng API.
3. **No Self-Privilege Escalation**: Không một vai trò nào được phép tự nâng quyền cho chính mình hoặc gán vai trò có thẩm quyền cao hơn quyền hạn của người gán.
4. **No Self-Final-Approval (Separation of Duties)**: Tách bạch trách nhiệm nghiêm ngặt trong quy trình duyệt nội dung, chiến dịch và duyệt chi ngân sách.
5. **AI Workers Recheck Permission**: Tác tử AI và Worker xử lý ngầm (render video, crawl, trích xuất) phải tái thẩm tra quyền tại thời điểm thực thi; lập tức dừng job nếu quyền của người ủy nhiệm bị thu hồi.
6. **Human Sign-Off Before Production**: Mọi thay đổi phân quyền môi trường Production phải có sự ký duyệt của Founder / Security Owner; không chạy migration quyền hạn tự động khi chưa duyệt A00.

---

## 4. Lộ Trình 13 Pha Triển Khai (A00 - A12) & Cổng Nghiệm Thu

| Pha | Tên Pha | Nội Dung Công Việc Chính | Cổng Nghiệm Thu Bắt Buộc (Exit Gate) | Mã Test Trọng Tâm |
|---|---|---|---|---|
| **A00** | Khảo sát kho mã nguồn & Mô hình đe dọa | Kiểm kê 100% route API, background job, bảng DB; thiết lập Threat Model và danh mục vai trò đề xuất | 100% private route được kiểm kê; Founder ký duyệt phạm vi | AUTH-001 -> 004 |
| **A01** | Ranh giới Khách thuê & CSDL (Tenant Boundary) | Thiết lập RLS (Row-Level Security) hoặc bộ lọc tenant bắt buộc trong ORM; đối soát dữ liệu | Không có bất kỳ rò rỉ đọc/ghi/tìm kiếm chéo tenant | AUTH-010 -> 019 |
| **A02** | Cấu trúc Tổ chức & Mối quan hệ phân cấp | Xây dựng API phòng ban/nhóm, cây phân cấp tổ chức, thuật toán ngăn chặn chu trình lặp (cycle) | Cây tổ chức hợp lệ, không chu trình, phạm vi báo cáo chuẩn | AUTH-020 -> 025 |
| **A03** | Động cơ Chính sách Phân quyền (Policy Engine) | Hiện thực hóa Authorizer cốt lõi, Resolve Scope, nạp Permission Registry và Role Matrix | 100% test case Deny/Allow trong ma trận đạt chuẩn | AUTH-030 -> 039 |
| **A04** | Cấp phát & Thu hồi Quyền thành viên | Triển khai API gán vai trò, lời mời tham gia, ủy quyền tạm thời và thu hồi quyền tức thì | Không có leo thang quyền; thu hồi có hiệu lực ngay lập tức | AUTH-040 -> 049 |
| **A05** | Thực thi Kiểm soát API, Truy vấn & Tài sản | Áp dụng Authorization Middleware lên 100% route riêng tư; bộ lọc query và chính sách tài sản số | 100% private route được bảo vệ nghiêm ngặt | AUTH-050 -> 059 |
| **A06** | Quy trình Phê duyệt & Tách bạch trách nhiệm | Máy trạng thái phê duyệt nội dung/chiến dịch; kiểm tra phiên bản; hòm thư duyệt (Review inbox) | Cấm tự duyệt; cấm xuất bản sai phiên bản đã duyệt | AUTH-060 -> 069 |
| **A07** | Tác tử AI, Worker nền & Xuất dữ liệu | Ủy quyền hẹp cho Job nền/AI; kiểm tra lại quyền tại runtime; tự động hủy khi thu hồi | Không có lỗi Confused Deputy; hủy job lập tức khi hết quyền | AUTH-070 -> 079 |
| **A08** | Giao diện Tổ chức, Phân quyền & Hòm thư duyệt | Giao diện quản lý vai trò, trang từ chối truy cập (403), hòm thư duyệt bài trên SIN Creator OS | Giao diện phản ánh 100% chuẩn xác thẩm quyền từ máy chủ | AUTH-080 -> 089 |
| **A09** | Nhật ký Kiểm toán & Hỗ trợ vận hành sự cố | Audit log bất biến, cảnh báo xâm nhập, cơ chế truy cập hỗ trợ an toàn và quy trình backup/restore | Log chống sửa đổi; không lộ bí mật; hỗ trợ an toàn | AUTH-090 -> 096 |
| **A10** | Đánh giá An ninh E2E & Chứng nhận Staging | Diễn tập Red Team, kiểm thử thâm nhập, đo lường độ trễ (SLO), kiểm thử hộp đen toàn diện | 0 lỗ hổng Critical / High; 100% test hồi quy đạt | AUTH-100 -> 109 |
| **A11** | Triển khai An toàn & Bàn giao Sản xuất | Chạy thử Canary, kiểm chứng kịch bản Rollback khẩn cấp; ký biên bản bàn giao vận hành | Founder ký phát hành chính thức sau khi dry-run đạt | AUTH-110 -> 115 |
| **A12** | Mở rộng Cấp Doanh Nghiệp (Tùy chọn) | Tích hợp SSO / SAML / SCIM hoặc mô hình ReBAC nâng cao nếu có nhu cầu phát sinh | Cần văn bản phê duyệt riêng; không tự động khởi chạy | Phê duyệt riêng |

---

## 5. Trạng Thái Dự Án Hiện Tại & Cam Kết "Chưa Code"

- **Điểm Checkpoint Hệ Thống:** Duy trì CP01_FRONTEND_FOUNDATION_CORE.
- **Cam kết kỹ thuật:** 
  - Toàn bộ gói BAHA-AUTHZ-001 được tiếp nhận tại phân vùng nguyên bản 02_nguyen_ban_giai_nen/baha_group_anti_rbac_plan/ và đồng bộ tài liệu sang 09_kiem_thu_quyen/.
  - Chưa can thiệp chỉnh sửa bất kỳ logic code ứng dụng nào trong 03_ban_lam_viec/sin_creator_os/ hay backend API.
  - Toàn bộ 13 pha A00 - A12 đều ở trạng thái **CHƯA BẮT ĐẦU (NOT_STARTED)**.
  - Khi có lệnh bắt đầu từ Founder, hệ thống sẽ tuần tự khởi chạy từ pha **A00** (Khảo sát hiện trạng & kiểm kê route) trước khi có bất kỳ thay đổi nào về cơ sở dữ liệu hay mã nguồn.
