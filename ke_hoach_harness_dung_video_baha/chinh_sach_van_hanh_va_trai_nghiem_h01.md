# CHÍNH SÁCH VẬN HÀNH & ĐẶC TẢ TRẢI NGHIỆM HARNESS DỰNG VIDEO BAHA (PHASE H01)
*Thời gian ban hành:* 23/10/2026 11:30 (GMT+7)  
*Phiên bản chính sách:* `POLICY_V1_2026_10_23`  
*Mã Phase:* H01 — Task T01  
*Trạng thái Gate:* **APPROVED (DESIGN & GOVERNANCE FROZEN)**

---

## 1. MÔ TẢ 7 LUỒNG NGHIỆP VỤ BẮT BUỘC BẰNG VÍ DỤ CỤ THỂ DỰ ÁN SIN

### Luồng 1: Dựng từ Footage Thô (Raw Footage to Final Edit)
- **Ví dụ thực tế:** Dự án PRJ_BASE_01 "Review Trà Sữa Sin - Có Thoại".
- **Kịch bản thực thi:**
  1. Người dùng tải lên 1 video 4K 180s quay Sin thử các món trà sữa kèm 2 tệp âm thanh WAV (mic cài áo).
  2. Agent gọi công cụ phân tích tư liệu: chạy ASR lấy transcript tiếng Việt có dấu, word timestamp chính xác, chia các phân đoạn theo câu thoại.
  3. Lập kế hoạch dựng (Plan): Chọn 3 điểm sáng giá (Hook: Sin uống ngụm đầu tiên khen đậm vị; Thân bài: giải thích thành phần trà Oolong; Kết bài: CTA ghé quán).
  4. Tạo bản nháp (Draft): Cắt ghép 3 phân cảnh (tổng thời lượng 45s), gắn phụ đề tiếng Việt tự động vào Safe Zone TikTok, lồng nhạc nền có auto-ducking (-14 LUFS).
  5. Độc lập kiểm định (QC) -> Trình Editor duyệt -> Render MP4 thành phẩm.

### Luồng 2: Dựng từ Ảnh Tĩnh (Image to Video Montage)
- **Ví dụ thực tế:** Dự án PRJ_BASE_05 "Bộ Sưu Tập Thực Đơn Mùa Hè Sin".
- **Kịch bản thực thi:**
  1. Nạp 12 ảnh món nước phân giải cao và logo BAHA.
  2. Áp dụng chuyển động keyframe (Ken Burns effect: zoom in, pan nhẹ từ từ), thời lượng 2.5s mỗi ảnh.
  3. Xếp các lớp: V1 (ảnh món nước), V2 (overlay text tên món), V3 (logo quán góc trên an toàn).
  4. Lồng giọng đọc Voiceover AI đã duyệt và nhạc nền vui tươi.

### Luồng 3: Sửa Một Bản Dựng Theo Phản Hồi (Targeted Feedback Revision)
- **Ví dụ thực tế:** Editor ghi chú tại timecode `00:15.500`: *"Đổi nhạc nền từ giây 15 sang beat sôi động hơn, giữ nguyên toàn bộ lời thoại và hình ảnh đã cắt."*
- **Kịch bản thực thi:**
  1. Hệ thống tạo draft mới dựa trên revision hiện tại.
  2. Áp dụng lệnh thay thế audio track tại vị trí chỉ định; không chạm vào V1/V2 hay caption.
  3. Tính toán diff trước/sau, kiểm chứng không thay đổi bất kỳ frame nào ngoài vùng yêu cầu.

### Luồng 4: Sửa Nội Dung Một Cảnh Bằng Flow / API (Scene Generation & Repair)
- **Ví dụ thực tế:** Dự án PRJ_BASE_09 "Thay Thế Background Cảnh Mở Đầu".
- **Kịch bản thực thi:**
  1. Cảnh 0-5s Sin đứng trước quầy cũ cần đổi sang background ngoại trời mùa hè rực rỡ.
  2. Tạo đơn `DonSuaCanh`: Gửi đoạn 5s đầu làm source video, cung cấp ảnh tham chiếu bãi biển mùa hè, preserve list: giữ nguyên khuôn mặt Sin, trang phục và chuyển động cơ thể.
  3. Hỗ trợ 2 nhánh:
     - **Flow Assisted (UI):** Xuất gói dữ liệu cho operator thao tác trên Google Flow chính thức, tải file kết quả về gắn request ID.
     - **Gemini Omni REST API:** Gửi trực tiếp qua endpoint Interactions với previous_interaction_id khi đã có API key chính thức.
  4. Kiểm định kết quả: thời lượng bắt buộc khớp 5s (không tự trim/speed).

### Luồng 5: Hậu Kỳ Chuyên Sâu (Color, Masking, Tracking, Compositing)
- **Ví dụ thực tế:** Dự án PRJ_BASE_08 "Hướng Dẫn Pha Chế 2 Camera".
- **Kịch bản thực thi:**
  1. Áp dụng color LUT đồng bộ màu giữa Camera A (Sony Log) và Camera B (iPhone).
  2. Tạo mask hình tròn làm mờ thông tin cá nhân trên biên lai thanh toán (Tracking ROI qua từng frame).
  3. Các hiệu ứng phức tạp vượt ngoài khả năng tự động của engine sẽ chuyển sang trạng thái `NATIVE_EDIT_REQUIRED` để bàn giao editor thao tác trên DaVinci Resolve.

### Luồng 6: Nhân Bản Biến Thể Đầu Ra (Multi-Ratio / Multi-Variant Packaging)
- **Ví dụ thực tế:** Từ bản master 9:16 (TikTok), nhân bản sang 16:9 (YouTube) và 1:1 (Facebook Post).
- **Kịch bản thực thi:**
  1. Tự động áp dụng smart crop giữ Sin ở giữa khung hình.
  2. Bố cục lại phụ đề theo Safe Zone của từng nền tảng đích.
  3. Tuyệt đối không gọi lại các API sinh AI tốn tiền nếu chỉ thay đổi tỷ lệ khung hình hay đóng gói.

### Luồng 7: Bàn Giao NLE & Quay Lại Sửa Tiếp (Native Roundtrip & Handover)
- **Ví dụ thực tế:** Xuất gói dự án cho Editor hoàn thiện trên trạm dựng chuyên nghiệp.
- **Kịch bản thực thi:**
  1. Xuất gói bàn giao `GoiBanGiao` gồm: tệp media nguyên bản, file EDL / Final Cut XML / Resolve project, manifest mã băm.
  2. Editor mở dự án trên máy cá nhân, chỉnh color grading nâng cao.
  3. Nhập lại phiên bản native vào BAHA: Hệ thống đánh dấu revision `NATIVE_BOUND`. Khi Agent sửa caption sau đó, lệnh render sẽ sử dụng đúng native project đã sửa, không phá vỡ lớp color grading.

---

## 2. QUY CHUẨN XỬ LÝ 5 TRẠNG THÁI LỖI ĐẶC THÙ

| Trạng Thái Lỗi | Nguyên Nhân Gây Ra | Hành Vi Bắt Buộc Của Hệ Thống |
|---|---|---|
| **PROVIDER_ERROR (4xx/5xx/Timeout)** | Nhà cung cấp AI (Google Flow / Gemini / Lyria) gặp sự cố mạng hoặc quá tải. | Ghi nhận lỗi có phân loại, không resubmit mù; nếu timeout không rõ trạng thái bill thì chuyển sang `NEEDS_RECONCILIATION`, không trừ tiền 2 lần. |
| **STALE_REVISION_CONFLICT (OCC 409)** | Hai bên (editor hoặc agent) cùng ghi đè lên cùng một bản draft hoặc project. | Lập tức từ chối lệnh ghi (HTTP 409 Conflict), giữ nguyên trạng thái cũ, yêu cầu nạp lại snapshot mới nhất trước khi áp dụng thay đổi. |
| **MISSING_EVIDENCE** | Yêu cầu dựng hoặc cắt cúp nhưng không tìm thấy mốc timecode/word timestamp trong dữ liệu phân tích. | Chuyển sang trạng thái `UNKNOWN` / `REVIEW_REQUIRED`, yêu cầu người vận hành xác minh hoặc chạy phân tích bổ sung; tuyệt đối cấm bịa timecode. |
| **NATIVE_EDIT_REQUIRED** | Yêu cầu hiệu ứng (như 3D tracking, roto phức tạp) vượt ngoài năng lực của renderer BAHA. | Trả về mã lỗi `NATIVE_EDIT_REQUIRED`, giữ nguyên timeline, tạo task chỉ định rõ ràng cho Editor trên NLE chuyên nghiệp, không drop effect âm thầm. |
| **BUDGET_OVERRUN** | Chi phí ước tính hoặc thực tế vượt trần ngân sách cho phép của workspace. | Chặn đứng tác vụ ngay tại tầng `BudgetGuard` (HTTP 422), ghi nhận vào nhật ký kiểm toán `CostLedger`, phát sinh cảnh báo và dừng phiên. |

---

## 3. THIẾT LẬP THAM SỐ CHÍNH SÁCH BĂNG CHUYỀN (POLICY_V1)

1. **Giới hạn phiên làm việc của Agent:**
   - Số lượt hội thoại model tối đa (Max LLM Turns): **20 lượt**.
   - Số lần gọi công cụ tối đa (Max Tool Calls): **80 lần**.
   - Số vòng tự động sửa lỗi QC (Max Auto-Repair Cycles): **2 vòng**.
   - Thời gian xử lý chủ động tối đa cho 1 phiên: **30 phút**.
   - Dừng khẩn cấp: 3 bước liên tiếp cùng fingerprint lỗi hoặc không làm thay đổi bản nháp -> dừng ngay và báo cáo lý do.
2. **Quy chuẩn âm thanh & video phát sóng:**
   - Tỷ lệ khung hình chuẩn TikTok: **9:16 (1080 x 1920 px, 30.0 fps CFR)**.
   - Chuẩn âm lượng phát sóng EBU R128: **Integrated Loudness = -14.0 LUFS ± 1.0 LUFS**.
   - Ngưỡng đỉnh thực tế (True Peak Ceiling): **True Peak <= -1.5 dBTP**.
   - TikTok Safe Zone: Mép trên 150px, mép dưới 320px, mép phải 120px.
3. **Quy tắc bảo mật & dữ liệu đám mây:**
   - Dữ liệu gửi lên Cloud AI: Chỉ gửi phân cảnh cần thiết được người dùng chỉ định; cấm tải toàn bộ thư viện footage chưa có phép.
   - Nguyên tắc Bốn Mắt: Toàn bộ sản phẩm render sinh ra mang trạng thái `UNREVIEWED`; bắt buộc Founder hoặc Lead Editor duyệt trước khi xuất bản.
   - Tuyệt đối tuân thủ Rule 9 (NO EMOJI - SVG ONLY) và Rule 7 (NO SECRETS IN REPO).
