# DANH SÁCH BLOCKER & QUẢN TRỊ RỦI RO (OPEN BLOCKERS & RISK REGISTER)
## DỰ ÁN: SIN CONTENT INTELLIGENCE (PRJ_069)
**Tài liệu tham chiếu chuẩn:** `docs/OPEN_BLOCKERS.md`  
**Phiên bản:** 1.0.0 | **Ngày ban hành:** 2026-10-21 | **Agent phụ trách:** Anti  
**Vị trí lưu trữ SSOT:** `03_ban_lam_viec/sin_creator_os/danh_sach_blocker_rui_ro.md`

---

## 1. NGUYÊN TẮC QUẢN LÝ ĐIỂM NGHẼN (FAIL-CLOSED BLOCKER POLICY)
1. Tuyệt đối không che giấu điểm nghẽn kỹ thuật, pháp lý hoặc chi phí.
2. Mọi tính năng chưa có quyền truy cập hoặc chưa được cấp phép **BẮT BUỘC** phải ghi nhận là `BLOCKED` hoặc `UNVERIFIED`.
3. Không bao giờ biến việc thiếu dữ liệu thành con số 0; không dùng dữ liệu giả định để tuyên bố tính năng đã hoàn thiện.
4. Pha tiếp theo chỉ được triển khai khi tất cả các cổng phụ thuộc (Dependency Gates) được nghiệm thu đạt chuẩn.

---

## 2. BẢNG DANH MỤC CÁC ĐIỂM NGHẼN ĐANG MỞ (ACTIVE OPEN BLOCKERS)

| Mã Điểm Nghẽn | Phân Loại | Mô Tả Chi Tiết Điểm Nghẽn | Ảnh Hưởng Đến Pha Nào | Giải Pháp Tạm Thời & Lối Thoát (Mitigation) | Điều Kiện Để Mở Khóa (Unblocking Criteria) | Trạng Thái |
|---|---|---|---|---|---|---|
| **BLK-001** | Quyền Dữ Liệu | Không có API tìm kiếm toàn mạng TikTok chính thức cho mục đích thương mại. TikTok chỉ cấp Research API cho nghiên cứu học thuật phi lợi nhuận. | P03-LIVE, P05, P07, P13 | Sử dụng mô hình **Offline MVP**: Khảo sát dựa trên dữ liệu khách hàng tự cung cấp (`customer_import`) và bộ dữ liệu mẫu nội bộ có bản quyền. | Khách hàng ký hợp đồng với đối tác dữ liệu được cấp phép hoặc sử dụng quy trình nghiên cứu trên tài khoản chính chủ. | **BLOCKED (GATED)** |
| **BLK-002** | Giấy Phép | `MediaCrawler` (NanmiCoder) mang giấy phép `NON-COMMERCIAL LEARNING LICENSE 1.1`, nghiêm cấm tích hợp vào sản phẩm thương mại. | P00, P03 | **CẤM TRIỆT ĐỂ**: Không đưa mã nguồn, module hay submodule MediaCrawler vào dự án. | Không tìm cách mở khóa; loại bỏ vĩnh viễn khỏi kiến trúc. | **RESOLVED BY BAN** |
| **BLK-003** | Pháp Lý & Ngân Sách | Dịch vụ cào Apify TikTok Actor là dịch vụ trả phí, chưa có đánh giá pháp lý về điều khoản TikTok ToS và chưa có hạn mức ngân sách được duyệt. | P03-LIVE, P04 | Đặt Apify Actor ở chế độ `UNVERIFIED` / `DISABLED_BY_POLICY`. Mọi bài test P03 chạy ở chế độ OFFLINE với synthetic fixtures. | Có văn bản phê duyệt ngân sách và ý kiến pháp lý chấp thuận sử dụng dịch vụ Apify cho dự án. | **BLOCKED (PENDING APPROVAL)** |
| **BLK-004** | Quyền Tài Khoản | Chưa có tài khoản TikTok Developer App được TikTok xét duyệt để sử dụng Login Kit / Display API cho kênh chính chủ. | P11 (Feedback Loop) | Triển khai giao diện nhập tay chỉ số (Manual Metric Entry) hoặc tải file báo cáo TikTok Analytics dạng CSV từ tài khoản khách hàng. | Hoàn tất đăng ký TikTok Developer, cấu hình OAuth Client ID/Secret và vượt qua kỳ thẩm định App Review của TikTok. | **BLOCKED (PENDING APP REVIEW)** |
| **BLK-005** | Kiến Trúc Hiện Trạng | Kho mã nguồn `03_ban_lam_viec/sin_creator_os/` hiện tại là 100% Mock UI phía client (Zustand store, hardcoded JSON). Hoàn toàn chưa có Backend, Database (Postgres/pgvector), Task Worker và Test Suite. | P01, P02, P03 | Xây dựng Backend FastAPI và Worker theo kiến trúc Modular Monolith trong Pha P01, kết nối với Frontend qua API schema chuẩn hóa. | Hoàn thành Pha P01: Triển khai backend, áp dụng migration database, vượt qua kiểm tra `/healthz` và cách ly workspace. | **IN PROGRESS (P01 SCOPE)** |
| **BLK-006** | Quản Trị Phiên Bản | Repository hiện tại đang ở nhánh `master` nhưng chưa có bất kỳ commit Git nào (`No commits yet`). Toàn bộ file đang ở trạng thái untracked. | P01 | Tạo commit baseline đầu tiên cho toàn bộ cây thư mục sau khi hoàn tất nghiệm thu tài liệu Pha P00. | Thực hiện `git add` và `git commit` khởi tạo baseline sau khi được duyệt Gate P00. | **OPEN (POST-P00 ACTION)** |

---

## 3. MA TRẬN PHÂN TÍCH RỦI RO KỸ THUẬT & VẬN HÀNH (RISK REGISTER)

| Mã Rủi Ro | Hạng Mục Rủi Ro | Mức Độ (Tác động x Khả năng) | Mô Tả Chi Tiết | Kế Hoạch Ứng Phó & Khắc Phục (Contingency Plan) |
|---|---|---|---|---|
| **RSK-001** | Tràn Bộ Nhớ GPU & Nghẽn Mạng NAS | CAO (4 x 4 = 16) | Việc chạy mô hình AI cục bộ (faster-whisper, embedding FlagEmbedding) hoặc xử lý video trên ổ đĩa mạng NAS có thể gây tràn VRAM GPU và nghẽn băng thông SMB. | Thiết lập hàng đợi Celery với tham số `concurrency=1` cho các tác vụ AI nặng. Lưu trữ cache mô hình trên ổ cứng local SSD của máy trạm thay vì lưu trên NAS. |
| **RSK-002** | Ảo Giác AI & Bịa Đặt Số Liệu (LLM Hallucination) | CAO (5 x 3 = 15) | LLM tự sáng tạo các đường dẫn URL video, bịa đặt số view/like, hoặc trích dẫn sai nguồn chứng minh khi sinh ý tưởng. | Triển khai tầng kiểm chứng độc lập (`IdeaVerifier`, `ClaimChecker`) ở Pha P08/P09. Mọi ID trích dẫn phải tồn tại thực trong database; nếu không khớp, hệ thống lập tức từ chối và báo lỗi. |
| **RSK-003** | Rò Rỉ Dữ Liệu Đa Khách Thuê (Tenant Data Leak) | CỰC CAO (5 x 2 = 10) | Người dùng thuộc Kênh A có thể xem được kịch bản, ý tưởng hoặc brief bí mật của Kênh B do lỗi lọc dữ liệu ở backend. | Bắt buộc kiểm tra quyền sở hữu `workspace_id` từ Session/Token phía server. Viết bộ kiểm thử bảo mật (Negative Security Tests) chạy tự động trong CI (Test T011, T120). |
| **RSK-004** | TikTok Thay Đổi Thuật Toán / Đổi Cấu Trúc Trang Web | TRUNG BÌNH (4 x 3 = 12) | Các bộ cào dữ liệu không chính thức (Douyin_TikTok_Download_API) bị hỏng khi TikTok cập nhật chữ ký `msToken` hoặc chặn IP. | Áp dụng triết lý Fail-Closed: Báo lỗi `PROVIDER_UNAVAILABLE`, không cố vượt cơ chế chống bot, dựa trên dữ liệu nhập khẩu hợp pháp làm nguồn cứu cánh an toàn. |
| **RSK-005** | Bùng Nổ Chi Phí Gọi API (API Cost Blowout) | TRUNG BÌNH (4 x 2 = 8) | Vòng lặp gợi ý ý tưởng hoặc tóm tắt tài liệu chạy mất kiểm soát làm vượt quá ngân sách LLM hàng tháng. | Tích hợp Circuit Breaker tài chính tại Pha P01/P08. Khóa cứng ngân sách tối đa trên từng Research Run; từ chối thực thi khi số dư dự trù không đủ. |

---

## 4. KẾT LUẬN & HÀNH ĐỘNG CHO PHA P00
- **Khẳng định:** Pha P00 ghi nhận đầy đủ, trung thực các điểm nghẽn và rủi ro; không che giấu bất kỳ hạn chế nào của hệ thống.
- **Quyết định chuyển tiếp:** Mọi tính năng liên quan đến dữ liệu trực tiếp (`LIVE_SOURCE`) được phong tỏa (Gated); Pha P01 và các pha tiếp theo chỉ được triển khai theo luồng **OFFLINE DETERMINISTIC STACK**.
