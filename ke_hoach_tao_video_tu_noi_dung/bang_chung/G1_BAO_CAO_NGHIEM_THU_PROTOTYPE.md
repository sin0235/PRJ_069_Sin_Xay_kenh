# BIÊN BẢN NGHIỆM THU NỘI BỘ PROTOTYPE, STORYBOARD & STYLE BOARD (CỔNG G1)

- **Dự án:** PRJ_069_Sin_Xay_kenh — Hệ thống xây dựng & phát triển kênh TikTok SIN
- **Mã cổng:** G1 (Prototype, Storyboard & Style Board Verification)
- **Tiêu chuẩn quản trị:** BAHA_PROJECT_OS_STANDARD_TEMPLATE_V2
- **Thời điểm thực hiện:** 2026-10-23
- **Đơn vị thực hiện:** Antigravity (Kiến trúc sư trưởng & Điều phối chất lượng)
- **Trạng thái cổng:** **STANDBY_FOUNDER_REVIEW (Sẵn Sàng Trình Founder Duyệt)**
- **Ràng buộc an toàn:** Tuyệt đối không tự suy đoán hoặc duyệt trước; chưa thi công backend nặng G2-G9 khi chưa có phê duyệt từ Founder.

---

## 1. Tổng Quan Kết Quả Triển Khai Prototype G1

Nhằm tuân thủ nghiêm ngặt **Nguyên Tắc Bất Biến số 4 (UX/UI & Kịch Bản Mẫu Trước &rarr; Chức Năng Sau)**, hệ thống đã hoàn tất xây dựng và kiểm chứng thực nghiệm 100% prototype của bộ tạo video hoàn chỉnh từ nội dung (phiên bản 2.0) trên cả hai môi trường:

1. **Môi trường Web trực tiếp trong ứng dụng:**
   - Điểm truy cập chuyên dụng: `http://localhost:3000/video-studio/prototype`
   - Điểm vào từ danh sách dự án: `http://localhost:3000/video-studio` (Banner điều hướng chuyên biệt)
   - Mã nguồn: 5 components chuyên sâu tại `03_ban_lam_viec/sin_creator_os/src/app/(main)/video-studio/[projectId]/_components/`:
     - `nhap_noi_dung.tsx`
     - `duyet_phan_canh.tsx`
     - `tien_do_san_xuat.tsx`
     - `duyet_thanh_pham.tsx`
     - `bang_phong_cach_kenh.tsx`
   - Kết quả biên dịch: TypeScript `pnpm exec tsc --noEmit` đạt **Exit code 0 (0 lỗi)**, máy chủ phản hồi **HTTP 200 OK**.
2. **Môi trường Ngoại Tuyến Độc Lập 1 Chạm:**
   - Tệp tệp trực quan: `03_ban_lam_viec/ke_hoach_tao_video_tu_noi_dung/prototype_g1_tao_video.html`
   - Lệnh mở nhanh tại gốc dự án: `00_MO_PROTOTYPE_G1.cmd`
   - Tiêu chuẩn hiển thị: 100% Tiếng Việt có dấu, 100% vector SVG (Tuyệt đối không dùng emoji/unicode icon).

---

## 2. Chi Tiết Các Màn Hình & Trải Nghiệm Người Dùng (UX Flow)

### 2.1. Màn Hình 1: Nhập Nội Dung, Thời Lượng & Khóa Kênh
- **Khóa phong cách bất biến:** Hiển thị rõ ràng Style Family `baha_giai_thich_cong_nghe_v1`, liên kết kênh `tiktok_tiktok`, mã băm snapshot `sha256:7f8e...`.
- **Lựa chọn thời lượng linh hoạt:** Hỗ trợ từ 30 đến 180 giây; nút chọn nhanh 60 giây (Demo) và 120 giây (Chuẩn bắt buộc BAHA). Tự động tính toán số khung hình tương ứng (60s = 1.800 frames, 120s = 3.600 frames ở 30 fps CFR).
- **Chế độ xử lý lời thoại:**
  - `BIEN_SOAN` (Khuyên dùng): LLM tối ưu hóa nhịp thoại vừa khít thời lượng và chia phân đoạn trực quan.
  - `GIU_NGUYEN_LOI`: Bảo toàn nguyên văn; dừng chờ nếu audio đo thực tế lệch chuẩn thời lượng.
- **Mẫu Brand Outro BAHA:** Lựa chọn `O1` (Nhận diện thuần túy), `O2` (Theo dõi kiến thức), hoặc `O3` (Giải pháp doanh nghiệp).

### 2.2. Màn Hình 2: Duyệt Storyboard, Kịch Bản & Prompt Từng Shot
- **Bảng chỉ số tổng quan:** Tổng frame đích, số lượng phân cảnh/shot, ước tính chi phí token AI, phiên bản CAS-Locked của kế hoạch.
- **Trình duyệt phân cảnh (Scene Browser):** Danh sách toàn bộ các cảnh kèm timecode bắt đầu/kết thúc và thẻ phân loại (`HOOK`, `DIAGRAM`, `SCREEN_RECORDING`, `AI_VIDEO`, `TEXT_MOTION`, `BRAND_OUTRO`).
- **Thanh tra chi tiết từng Shot (Inspector):**
  - Xem và chỉnh sửa lời thoại đọc (phụ đề & TTS).
  - Tiêu đề chữ hiển thị trên màn hình trong TikTok Safe Zone.
  - Prompt kỹ thuật biên dịch cho Flow/Adapter có đầy đủ ngữ cảnh liên tục, prompt phủ định (không sinh chữ giả, không méo hình).
  - Chỉ định rõ tư liệu nguồn (Đồ họa SVG, quay màn hình thật, Flow AI).

### 2.3. Màn Hình 3: Theo Dõi Sản Xuất DAG Bền Vững (Harness Simulator)
- **Chuỗi bước thực thi DAG tuần tự:**
  1. *Khóa phong cách kênh (Style Lock)*: Khóa snapshot hash nhận diện.
  2. *Thẩm định kịch bản (LLM Preflight)*: Thẩm định độ phủ luận điểm và schema prompt.
  3. *Sinh giọng đọc & Căn phụ đề (TTS & Alignment)*: Đo thời lượng audio thật từng câu.
  4. *Điều phối Flow & Tạo tư liệu (Flow Harness)*: Cấp biên nhận thực thi hợp lệ cho từng shot.
  5. *Lắp ráp & Ghép dựng Native (FFmpeg CPU)*: Ghép timeline đa track, phụ đề UTF-8, loudnorm -14 LUFS, outro BAHA.
  6. *Kiểm định chất lượng tự động (QC Gate)*: Đo EBU R128 và kiểm tra khung hình.
- **Công cụ kiểm thử trạng thái giả lập (G1 Simulator):**
  - Mô phỏng hoàn tất 100%.
  - Mô phỏng lệch thời lượng (`CHO_XU_LY_THOI_LUONG`).
  - Mô phỏng thiếu tư liệu quay màn hình (`CHO_TU_LIEU`).
  - Mô phỏng sự cố cổng LLM / Timeout (`CHO_LLM`).

### 2.4. Màn Hình 4: Xem Trước, QC & Gói Xuất Bản
- **Trình phát video 9:16 có lớp an toàn TikTok Safe Zone:**
  - Khung hình chuẩn dọc 1080x1920 px.
  - Lớp phủ Safe Zone trực quan: mép trên 150px, mép dưới 320px, mép phải 120px, mép trái 60px.
- **Báo cáo kiểm định QC tự động:** Âm lượng đạt **-14.1 LUFS (±1 LUFS)**, True Peak **-1.5 dBTP**, Full Decode **0 lỗi**.
- **Tính năng Sửa Cục Bộ 1 Cảnh (Scoped Re-render):**
  - Cho phép chọn sửa riêng một cảnh (ví dụ `c08`).
  - Chứng minh hệ thống chỉ tái biên dịch và sinh lại riêng cảnh đó; **100% hash tư liệu và audio của các cảnh khác được bảo toàn nguyên vẹn**.
- **Gói tải xuất bản đầy đủ (.ZIP):**
  - `video_thanh_pham_120s.mp4` (1080x1920, 30fps CFR, H.264 + AAC).
  - `phu_de_tieng_viet.srt` (UTF-8, căn chỉnh chuẩn xác).
  - `kich_ban_va_storyboard.json` (Kịch bản, phân cảnh và prompt từng shot).
  - `du_an_timeline.json` (Dự án có thể mở lại để chỉnh sửa trong Studio).
  - `bao_cao_kiem_dinh_qc.json` (Số đo âm lượng EBU R128 và an toàn khung hình).
  - `package_manifest.json` (Bảng kê mã băm SHA-256 xác thực tính toàn vẹn).

---

## 3. Đối Chiếu Hai Bộ Dữ Liệu Kịch Bản Mẫu (60 Giây & 120 Giây)

| Tiêu Chí | Kịch Bản Mẫu 60 Giây (Demo) | Kịch Bản Mẫu 120 Giây (Chuẩn Nghiệm Thu BAHA) |
|---|---|---|
| **Chủ Đề** | *"AI Agent khác Chatbot thông thường như thế nào?"* | *"RAG vs Fine-tuning: Chiến Lược Ứng Dụng Doanh Nghiệp"* |
| **Thời Lượng Đích** | 60.0 giây (1.800 frames ở 30 fps) | 120.0 giây (3.600 frames ở 30 fps) |
| **Quy Mô Phân Cảnh** | 5 cảnh / 5 shot | 12 cảnh / 12 shot |
| **Cấu Trúc Cảnh** | c01 Hook (3s)<br>c02 Khái niệm Chatbot (12s)<br>c03 Bản chất AI Agent (28s)<br>c04 Ứng dụng doanh nghiệp (12s)<br>c05 Brand Outro O1 (5s) | c01 Hook trực diện (3s)<br>c02 Bản chất RAG (10s)<br>c03 Bản chất Fine-tuning (10s)<br>c04 So sánh cập nhật dữ liệu (12s)<br>c05 Demo tra cứu tài liệu thật (12s)<br>c06 Kiểm soát ranh giới dữ liệu (12s)<br>c07 Kiến trúc phân quyền doanh nghiệp (12s)<br>c08 Minh họa bối cảnh ứng dụng thực tiễn (12s)<br>c09 Khi nào cần Fine-tuning? (12s)<br>c10 So sánh chi phí đầu tư (12s)<br>c11 Giải pháp kết hợp Hybrid (8s)<br>c12 Brand Outro O3 giải pháp doanh nghiệp (5s) |
| **Loại Tư Liệu Dùng** | TEXT_MOTION, DIAGRAM, SCREEN_RECORDING, BRAND_OUTRO | HOOK, DIAGRAM, SCREEN_RECORDING, AI_VIDEO, TEXT_MOTION, BRAND_OUTRO |
| **Quy Chuẩn Nhận Diện** | Đồng nhất 100% phong cách `baha_giai_thich_cong_nghe_v1` | Đồng nhất 100% phong cách `baha_giai_thich_cong_nghe_v1` |

---

## 4. Hồ Sơ Phong Cách Kênh Đã Khóa (Style Board Spec)

- **Định danh phong cách:** `baha_giai_thich_cong_nghe_v1`
- **Tài sản thương hiệu:** Logo chính thức `public/logo.png` (822 KB, 1200x1382 RGBA), clear space 24px, tuyệt đối không cho AI vẽ lại logo.
- **Bảng màu ngữ nghĩa:**
  - Primary: `#1e3a8a` (Xanh hải quân đậm)
  - Accent: `#2563eb` (Xanh công nghệ BAHA)
  - Background Dark: `#0f172a` (Xanh đen chuyên sâu)
  - Text Light: `#f8fafc` (Trắng sáng tương phản cao)
  - Emphasis: `#38bdf8` (Cyan nhấn mạnh từ khóa)
- **Giọng đọc & Phát âm:** Vi-VN Neural TTS, tốc độ 1.0x, chuẩn âm thanh -14 LUFS (±1 LUFS). Khóa từ điển thuật ngữ: RAG &rarr; R-A-G, MCP &rarr; M-C-P, API &rarr; A-P-I, LLM &rarr; L-L-M.
- **Phông chữ & Phụ đề:** Arial / System Sans-serif UTF-8 có dấu đầy đủ; phụ đề tối đa 2 dòng, tối đa 38 ký tự/dòng, tốc độ đọc &le; 20 ký tự/giây.

---

## 5. Hướng Dẫn Trải Nghiệm Dành Cho Founder

Founder và các kỹ sư có thể trực tiếp trải nghiệm prototype qua 2 phương thức:

1. **Xem trực tiếp trên trình duyệt web qua hệ thống Next.js:**
   - Mở liên kết: [http://localhost:3000/video-studio/prototype](http://localhost:3000/video-studio/prototype)
   - Hoặc truy cập [http://localhost:3000/video-studio](http://localhost:3000/video-studio) và bấm *"Mở Prototype 2.0"*.
2. **Xem bản độc lập 1 chạm (Offline Standalone):**
   - Chạy tệp `00_MO_PROTOTYPE_G1.cmd` tại thư mục gốc dự án.
   - Trình duyệt sẽ mở ngay `03_ban_lam_viec/ke_hoach_tao_video_tu_noi_dung/prototype_g1_tao_video.html`.

---

## 6. Trạng Thái Cổng & Đề Xuất Phê Duyệt

- **Trạng thái cổng G1:** **STANDBY_FOUNDER_REVIEW**.
- **Yêu cầu phê duyệt từ Founder:**
  - [ ] Phê duyệt bố cục trải nghiệm người dùng (UX) và 4 bước quy trình tạo video từ nội dung.
  - [ ] Phê duyệt phân cảnh Storyboard mẫu 60 giây và 120 giây (tổng 3.600 frames CFR).
  - [ ] Phê duyệt đề xuất Style Family nhận diện đầu tiên: `baha_giai_thich_cong_nghe_v1`.
- **Cảnh báo tuân thủ:** Mọi hoạt động thi công backend nặng (G2 - G9) tạm dừng chờ phê duyệt chính thức từ Founder.
