# BÁO CÁO KHẢO SÁT HIỆN TRẠNG, BASELINE VÀ ĐƯỜNG PHỤC HỒI (CỔNG G0)

- **Dự án:** PRJ_069_Sin_Xay_kenh — Hệ thống xây dựng & phát triển kênh TikTok SIN
- **Mã cổng:** G0 (Baseline & Rollback Verification)
- **Tiêu chuẩn quản trị:** BAHA_PROJECT_OS_STANDARD_TEMPLATE_V2
- **Thời điểm thực hiện:** 2026-10-23
- **Đơn vị thực hiện:** Antigravity (Kiến trúc sư trưởng & Điều phối chất lượng)
- **Tuân thủ quy tắc:** 100% Tiếng Việt có dấu, 100% SVG Vector (Tuyệt đối không dùng emoji/unicode icon).

---

## 1. Xác Định Kho Mã Nguồn & Ranh Giới Quản Lý (Repository Identification)

- **Thư mục dự án gốc (`C:\PRJ_069_Sin_Xay_kenh`):** Là container quản trị cấp cao theo chuẩn BAHA V2 (16 thư mục chuẩn), không trực tiếp chứa cấu hình Git.
- **Điểm nguồn chân lý duy nhất (Technical SSOT):** Thư mục `03_ban_lam_viec` được quản lý trực tiếp bằng Git repository:
  - **Remote URL:** `https://github.com/sin0235/PRJ_069_Sin_Xay_kenh.git`
  - **Nhánh làm việc:** `main`
  - **Commit nền gần nhất:** `55a97a5` ("Khoi tao ma nguon PRJ_069")
  - **Trạng thái tệp hiện hữu:** Sạch, không có nhánh trôi nổi; các thay đổi kiểm thử nằm trong vùng ghi được phép `03_ban_lam_viec`.
- **Ranh giới an toàn:** Tuyệt đối không `git init` tại thư mục gốc, không chép đè repository con, duy trì phân định rõ ràng giữa kho mã nguồn và các phân vùng dữ liệu gốc/bảo lưu.

---

## 2. Kiểm Kê Cơ Sở Dữ Liệu & Runtime Đang Chạy (DB & Process Inventory)

### 2.1. Tiến Trình Nền (Active Processes)
Khảo sát trực tiếp qua cổng mạng cục bộ:
- **FastAPI Backend:** Cổng `8000` (PID: 13444, lắng nghe `0.0.0.0:8000`), phản hồi HTTP 200 tại `/healthz`.
- **Next.js Frontend:** Cổng `3000` (PID: 7160, lắng nghe `:::3000`), phản hồi HTTP 200 tại `/video-studio` và `/ai-studio`.
- **9Router Gateway Daemon:** Cổng `20128` (PID: 16208, lắng nghe `0.0.0.0:20128`), phản hồi HTTP 200, phát hiện 828 mô hình AI sẵn sàng.

### 2.2. Kiểm Kê Cơ Sở Dữ Liệu Thực Tế
| Tên Tệp CSDL | Kích Thước | Số Bảng | Bản Ghi Cốt Lõi | Mục Đích Sử Dụng |
|---|---|---|---|---|
| `sin_content_api/sin_content_offline.db` | 978.944 bytes | 39 | `users`: 119<br>`workspaces`: 78<br>`owned_channels`: 1<br>`production_projects`: 1<br>`media_assets`: 41<br>`idea_cards`: 58<br>`script_draft_versions`: 27<br>`timeline_versions`: 2<br>`platform_llm_configurations`: 1<br>`allowed_facts`: 153<br>`audit_events`: 30 | CSDL Nghiệp Vụ Chính (SSOT Production SQLite WAL mode) |
| `sin_content_api/baha_auth_live.db` | 946.176 bytes | 19 | `memberships`: 244<br>`global_users`: 244<br>`role_assignments`: 245<br>`business_resources`: 125<br>`authz_audit_events`: 747 | CSDL Xác Thực & Phân Quyền BAHA-AUTHZ |
| `sin_content_api/sin_dieu_phoi_dung.db` | 81.920 bytes | 7 | `sessions`, `drafts`, `checkpoints`, `leases` | CSDL Lưu Phiên Điều Phối Dựng Video |
| `sin_content.db` (các bản 0-byte) | 0 bytes | 0 | Không có | Tệp placeholder, không chứa dữ liệu |

- **Kênh TikTok sở hữu (`owned_channels`):** Kênh `TikTok` (`channel_id: tiktok_tiktok`, `workspace_id: default_ws`, 96,4 triệu người theo dõi, trạng thái `CONNECTED` với mã thông báo và chỉ số sống).
- **Dự án video hiện có (`production_projects`):** Dự án `test baha` (`id: 27bda639-db53-4eb5-a5dd-8cdfc79693c2`, `workspace_id: default_ws`, trạng thái `DRAFT`).

---

## 3. Bản Đồ Mọi Đường Gọi Google Flow & Điểm Chặn Bắt Buộc (Flow Path Inventory)

Khảo sát toàn diện mã nguồn phát hiện 5 đường gọi sinh Flow:

| Điểm Gọi Trong Mã Nguồn | Vị Trí File / Tuyến Đường | Hiện Trạng Cơ Chế | Giải Pháp Chặn Cổng (Gate Enforcement) |
|---|---|---|---|
| **Đường 1: Tự động hoá Video Studio** | `sin_creator_os/src/app/(main)/video-studio/[projectId]/page.tsx:394` (`handleAutoProduce`) | Gọi trực tiếp Flow Music 30s + Flow Video 1 clip 10s, không voice, không chia cảnh | Chuyển toàn bộ sang gọi API Kế Hoạch (`/v1/media/projects/{id}/tao-video/ke-hoach`) qua Cổng Harness |
| **Đường 2: AI Studio Ảnh Sang Video & Nhạc** | `sin_creator_os/src/app/(main)/ai-studio/page.tsx` | Nút gửi tạo video từ ảnh trực tiếp tới backend router | Yêu cầu kiểm tra quyền, hạn ngạch và cấu hình style snapshot trước khi dispatch |
| **Đường 3: API Tạo Clip Media Studio** | `sin_content_api/src/modules/media_studio/router.py:869` (`/v1/media/video/generate`) | Nhận prompt thô từ client, chuyển tới `VideoOrchestrator` | Bọc qua `cong_harness.py`: Kiểm tra `BienNhanHarness` và `DanhGiaLLM`; từ chối prompt thô bypass |
| **Đường 4: Provider Adapter Flow** | `sin_content_api/src/modules/media_studio/video_provider.py` (`FlowVideoProvider`, `GoogleOfficialOmniProvider`) | Kết nối Playwright Edge `flow_bridge` | Chỉ nhận lệnh từ `cong_harness.py` có chữ ký hợp lệ và lease kiểm toán; cấm client gọi trực tiếp |
| **Đường 5: Đơn Sửa Cảnh Assisted UI** | `sin_content_api/src/modules/dieu_phoi_dung/sua_bang_flow.py` (`QuanLySuaCanh`) | Sinh mã biên nhận sửa cảnh và import asset | Bổ sung kiểm tra LLM preflight và style snapshot trước khi xuất packet sửa cảnh |

---

## 4. Kiểm Kê Tài Sản Thương Hiệu & Quy Chuẩn Phong Cách Kênh (Brand Assets Inventory)

- **Logo chính thức:**
  - `sin_creator_os/public/logo.png`: 822.362 bytes, định dạng PNG RGBA 1200x1382 chuẩn nhận diện thương hiệu BAHA.
  - `sin_creator_os/public/logo-square.png`: 195.671 bytes (512x512 có đệm trong suốt).
  - `sin_creator_os/public/icon.png` & `favicon.ico`: Đồng bộ nhận diện trên trình duyệt.
- **Bộ thông điệp chuẩn:**
  - **Slogan cốt lõi:** *"BAHA Group — Cung cấp giải pháp AI toàn diện."*
  - **Cấu trúc Outro:**
    - `O1`: Nhận diện thương hiệu thuần túy (Logo + Slogan, 5 giây).
    - `O2`: Kêu gọi theo dõi kiến thức công nghệ (Brand + Follow for Tech Knowledge).
    - `O3`: Giải pháp doanh nghiệp (Brand + Khám phá demo / Tư vấn giải pháp AI).
- **Phông chữ:** Arial và hệ phông Sans-serif tiêu chuẩn hỗ trợ 100% dấu tiếng Việt UTF-8.
- **Phong cách ban đầu đề xuất:** `baha_giai_thich_cong_nghe` (Chờ Founder phê duyệt mẫu tại G1).

---

## 5. Kết Quả Kiểm Thử Cơ Sở (Baseline Verification)

1. **Backend FastAPI (Pytest):**
   - Lệnh thực thi: `python -m pytest tests/test_video_prompt_compiler.py -q`
     - Kết quả: **2/2 tests PASSED** (0.85s).
   - Lệnh thực thi: `python -m pytest tests/test_harness_nang_cap_toan_dien.py -q` (sử dụng CSDL cách ly `SIN_DUNG_DB_PATH`)
     - Kết quả: **9/9 tests PASSED** (2.79s).
   - Lệnh thực thi: `python -m pytest tests/test_llm_edge_cases_and_guardrails.py tests/test_gate2_owner_db_and_secrets.py -q`
     - Kết quả: **20/20 tests PASSED** (9.80s).
   - *Ghi chú quan trọng về AppLocker:* Do chính sách bảo mật Windows Application Control chặn gọi trực tiếp file thực thi trong Scripts (`pytest.exe`), mọi lệnh kiểm thử phải chạy qua `python -m pytest`.
2. **Frontend Next.js (TypeScript Check):**
   - Lệnh thực thi: `pnpm exec tsc --noEmit` tại `03_ban_lam_viec/sin_creator_os`
   - Kết quả: **Exit code 0** (0 lỗi cú pháp, 0 lỗi kiểu dữ liệu).

---

## 6. Phương Án Phục Hồi & Điểm An Toàn (Rollback & Recovery Plan)

1. **Điểm phục hồi đã kiểm chứng:** `90_sao_luu/01_moc_khoi_phuc/CP22_OWNER_LLM_9ROUTER` lưu trữ toàn vẹn trạng thái hệ thống trước đợt thi công này.
2. **Nguyên tắc an toàn dữ liệu:**
   - Mọi migration CSDL phải có script hoàn tác (Down migration) và chạy thử nghiệm trên bản sao SQLite trước khi áp dụng.
   - Cơ chế Feature Flag cho phép tắt tức thời luồng tạo video mới nếu phát sinh sự cố, bảo toàn nguyên vẹn 100% dự án và media cũ.
   - Thao tác dọn dẹp kho thử nghiệm chỉ được xóa CSDL tạm, tuyệt đối không trỏ vào `sin_content_offline.db` hoặc `sin_dieu_phoi_dung.db`.

---

## 7. Kết Luận Cổng G0 (Go / No-Go Decision)

- **Trạng thái cổng G0:** **ĐẠT (PASSED)**.
- Toàn bộ 5 điều kiện tiên quyết (Repository, CSDL/Tiến trình thực, Baseline kiểm thử, Bản đồ Flow, Tài sản thương hiệu & Phục hồi) đã được đối soát và xác thực bằng chứng thực tế.
- **Quyết định:** Đủ điều kiện chuyển sang thực hiện **Cổng G1 (Dựng Prototype G1 & Kịch Bản Mẫu 60s/120s)**.
