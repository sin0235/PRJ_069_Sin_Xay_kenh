# ĐÁNH GIÁ QUYỀN TRUY CẬP, GIẤY PHÉP VÀ CHI PHÍ (RIGHTS & LICENSING REVIEW)
## DỰ ÁN: SIN CONTENT INTELLIGENCE (PRJ_069)
**Tài liệu tham chiếu chuẩn:** `docs/provider-audit/RIGHTS_REVIEW.md`  
**Phiên bản:** 1.0.0 | **Ngày ban hành:** 2026-10-21 | **Agent phụ trách:** Anti  
**Vị trí lưu trữ SSOT:** `03_ban_lam_viec/sin_creator_os/danh_gia_quyen_va_giay_phep.md`

---

## 1. NGUYÊN TẮC PHÁP LÝ & BẢN QUYỀN BẤT BIẾN
1. **Giấy phép SDK không đồng nghĩa với quyền dữ liệu nền tảng:** Một thư viện có giấy phép mã nguồn mở (như MIT, Apache-2.0) không trao quyền tự động cào, lưu trữ hoặc sử dụng dữ liệu người dùng của TikTok trái với Điều khoản dịch vụ (Terms of Service - ToS).
2. **Loại trừ tuyệt đối giấy phép phi thương mại:** Bất kỳ thư viện, đoạn mã hoặc mô hình mang giấy phép cấm thương mại (Non-Commercial / CC-BY-NC) đều không được phép tích hợp vào kho mã nguồn của dự án thương mại này.
3. **Quyền riêng tư và tối thiểu hóa dữ liệu (Data Minimization):** Không thu thập thông tin nhận dạng cá nhân (PII), thông tin nhạy cảm của người bình luận, hoặc dữ liệu vị trí địa lý chi tiết.
4. **Cơ chế phản hồi khi bị thu hồi quyền (Fail-Closed Revocation):** Khi tài khoản khách hàng hoặc đối tác bị hủy ủy quyền, hệ thống phải dừng ngay lập tức mọi lệnh truy vấn và thực hiện quy trình hủy dữ liệu theo yêu cầu.

---

## 2. RÀ SOÁT CÁC NGUỒN DỮ LIỆU ĐỀ XUẤT

### 2.1. Nguồn Dữ Liệu Khách Hàng Tự Cung Cấp (`customer_import`)
- **Mô tả:** Tập dữ liệu do chính khách hàng/kênh TikTok Sin xuất ra từ TikTok Creator Center / TikTok Studio hoặc tài liệu nội bộ (dưới định dạng CSV, JSON).
- **Quyền truy cập & Quyền thương mại:** **ĐƯỢC PHÉP 100% (APPROVED)**. Khách hàng là chủ sở hữu nội dung hoặc người đại diện hợp pháp, có toàn quyền ủy quyền cho hệ thống SIN phân tích để tối ưu kênh.
- **Yêu cầu tài khoản & Phạm vi quyền:** Khách hàng chủ động tải tệp lên hoặc kết nối kho lưu trữ nội bộ. Không cần cấp quyền API từ xa.
- **Chi phí:** **0 USD**. Không phát sinh cước phí gọi API nền tảng.
- **Giới hạn & Rủi ro:** Dữ liệu có tính chất tĩnh tại thời điểm xuất file (Snapshot); không thể tự động cập nhật số liệu mới nếu khách hàng không tải file cập nhật.
- **Xử lý khi lỗi:** Hệ thống kiểm tra cấu trúc schema của file (Validation), cách ly các bản ghi lỗi định dạng sang bảng phụ (Quarantine), giữ lại các bản ghi hợp lệ kèm chỉ dấu kiểm toán.
- **Đánh giá khả thi:** **LỰA CHỌN CỐT LÕI CHO OFFLINE MVP**.

---

### 2.2. TikTok Official API (`tiktok_official_api`)
- **Mô tả:** Giao diện lập trình ứng dụng chính thức của TikTok (TikTok for Developers: Display API, Commercial Content API, Business API).
- **Quyền truy cập & Quyền thương mại:** **HỢP PHÁP VỚI KÊNH SỞ HỮU (OWNED ACCOUNT)**. Tuân thủ nghiêm ngặt TikTok Developer Terms.
- **Yêu cầu tài khoản & Phạm vi quyền:**
  - Yêu cầu đăng ký tài khoản TikTok Developer, tạo Ứng dụng (App) và nộp hồ sơ xét duyệt (App Review).
  - Yêu cầu người dùng đăng nhập bằng TikTok Login Kit và cấp quyền (Scopes): `user.info.basic`, `video.list`, `video.insights`.
- **Năng lực thực tế:**
  - `SEARCH_CONTENT`: **UNSUPPORTED**. TikTok không cấp quyền tìm kiếm toàn mạng xã hội cho mục đích phân tích nội dung chung. TikTok Research API chỉ giới hạn cho các tổ chức học thuật/nghiên cứu phi lợi nhuận tại một số quốc gia được chọn.
  - `GET_POST`, `LIST_PROFILE_POSTS`, `REFRESH_METRICS`: **REQUIRES_AUTH** (Chỉ áp dụng cho tài khoản đã ủy quyền).
- **Chi phí:** Miễn phí trong hạn mức cơ bản (Rate limits do TikTok quy định).
- **Xử lý khi lỗi / Thu hồi quyền:** Khi Access Token hết hạn hoặc người dùng hủy ủy quyền trong ứng dụng TikTok, hệ thống ghi nhận mã lỗi `AUTH_FAILED` / `REQUIRES_REAUTH`, lập tức xóa token trong database và hiển thị thông báo an toàn trên giao diện.

---

### 2.3. Dịch Vụ Cào Dữ Liệu Apify TikTok Actor (`apify_tiktok_actor`)
- **Mô tả:** Sử dụng SDK `apify-client-python` để kích hoạt các Actor cào dữ liệu TikTok chạy trên đám mây của Apify.
- **Quyền truy cập & Quyền thương mại:** **CHƯA ĐƯỢC XÁC MINH (UNVERIFIED / BLOCKED)**.
  - SDK Python là mã nguồn mở (Apache-2.0), nhưng Actor chạy cào dữ liệu công khai tiềm ẩn rủi ro vi phạm Điều khoản dịch vụ của TikTok về việc cấm thu thập dữ liệu tự động.
- **Chi phí:** **CHƯA ĐƯỢC PHÊ DUYỆT**. Tính phí theo Compute Unit (CU) và dung lượng proxy xoay vòng (ước tính $3 - $5 / 1.000 video). Chưa có ngân sách được Project Owner phê chuẩn.
- **Xử lý khi lỗi:** Ngắt mạch tự động (Circuit Breaker) khi gặp mã lỗi 429 (Rate Limit) hoặc 403 (Cloudflare WAF). Tuyệt đối không tự động vượt rào chắn hoặc mua thêm proxy lậu.
- **Đánh giá:** Khóa ở trạng thái `UNVERIFIED` cho đến khi có văn bản phê duyệt từ cấp thẩm quyền.

---

### 2.4. Công Cụ Tự Host Douyin_TikTok_Download_API (`douyin_tiktok_download_api`)
- **Mô tả:** Repo mã nguồn mở của Evil0ctal hỗ trợ parse link và lấy dữ liệu video từ web endpoint của Douyin/TikTok.
- **Giấy phép:** Apache-2.0.
- **Quyền thương mại & Rủi ro:** **RỦI RO CAO (HIGH RISK)**. Tác giả ghi rõ mã nguồn mở không miễn trừ trách nhiệm tuân thủ pháp luật và điều khoản nền tảng. TikTok thường xuyên thay đổi cơ chế sinh token (`msToken`, `X-Bogus`), dẫn đến lỗi thường xuyên hoặc bị chặn IP server.
- **Quyết định:** Không sử dụng cho hệ thống sản xuất. Chỉ giữ làm tài liệu tham khảo kỹ thuật trong vùng nghiên cứu cách ly.

---

### 2.5. Thư Viện MediaCrawler (NanmiCoder)
- **Mô tả:** Bộ cào dữ liệu đa nền tảng (Douyin, TikTok, Xiaohongshu...).
- **Giấy phép:** `NON-COMMERCIAL LEARNING LICENSE 1.1`.
- **Đánh giá pháp lý:** **VI PHẠM BẢN QUYỀN NẾU DÙNG THƯƠNG MẠI**. Giấy phép cấm rõ ràng việc sử dụng mã nguồn này trong bất kỳ sản phẩm hoặc hoạt động thương mại nào nếu không có văn bản chấp thuận của tác giả.
- **Quyết định:** **CẤM TRIỆT ĐỂ (DISABLED_BY_POLICY)**. Không được nhập hay sử dụng bất kỳ tệp tin nào từ MediaCrawler.

---

### 2.6. Thư Viện Chuyển Giọng Nói Thành Văn Bản faster-whisper (`faster_whisper`)
- **Mô tả:** Thư viện chạy mô hình Whisper của OpenAI thông qua CTranslate2 để chuyển đổi audio thành text cục bộ trên GPU/CPU.
- **Giấy phép:** MIT (Mã nguồn) + Open Weights (Mô hình Whisper của OpenAI).
- **Quyền thương mại:** **HỢP PHÁP (APPROVED)** khi chạy trên thiết bị riêng của dự án.
- **Điều kiện sử dụng:** Chỉ được phép bóc băng các tệp âm thanh/video mà khách hàng sở hữu hoặc đã được cấp quyền sử dụng hợp pháp.
- **Chi phí:** 0 USD phí bản quyền; tiêu tốn tài nguyên GPU (cần quản lý mức sử dụng VRAM để không gây sập máy chủ).

---

## 3. RÀ SOÁT CÁC THÀNH PHẦN MÃ NGUỒN BÊN THỨ BA (THIRD-PARTY REPOS)

| Tên Gói / Thành Phần | Giấy Phép Mã Nguồn | Mục Đích Sử Dụng Trong Dự Án | Đánh Giá Tính Tương Thích & Rủi Ro | Quyết Định Pha P00 |
|---|---|---|---|---|
| `langgraph` | MIT | Điều phối luồng xử lý Agentic, lưu vết trạng thái và kiểm duyệt con người (HITL) | Tương thích hoàn toàn; thư viện ổn định, kiểm soát checkpoint tốt | **CHẤP THUẬN (APPROVED)** |
| `FlagEmbedding` | MIT | Tạo vector nhúng đa ngôn ngữ và xếp hạng lại (Reranking) | Giấy phép MIT; cần đánh giá thực nghiệm chất lượng tiếng Việt ở P06 | **CHẤP THUẬN CÓ ĐIỀU KIỆN (APPROVED_CONDITIONAL)** |
| `BERTopic` | MIT | Gom cụm chủ đề và nhu cầu khán giả | Phù hợp khi có tập dữ liệu lớn (>500 mẫu); tắt khi dữ liệu thưa thớt | **CHẤP THUẬN CÓ ĐIỀU KIỆN (APPROVED_CONDITIONAL)** |
| `gpt-researcher` | Apache-2.0 | Tham khảo kiến trúc tổng hợp tài liệu chuyên sâu | Cần viết lại adapter để bắt buộc trích dẫn nguồn có trong database | **CHẤP THUẬN CÓ ĐIỀU KIỆN (APPROVED_CONDITIONAL)** |
| `pgvector` | PostgreSQL License | Lưu trữ và tìm kiếm vector trong PostgreSQL | Giấy phép chuẩn PostgreSQL; hiệu năng cao, chi phí tối ưu | **CHẤP THUẬN (APPROVED)** |
| `langfuse` | MIT (Bản Core) | Theo dõi vết gọi LLM, giám sát chi phí và độ trễ | Cần lọc sạch dữ liệu PII/token trước khi đẩy log vào hệ thống | **CHẤP THUẬN (APPROVED)** |
| `promptfoo` | MIT | Đánh giá hồi quy prompt và kiểm thử red-teaming tự động | Thích hợp cho CI test offline; chạy không cần kết nối mạng | **CHẤP THUẬN (APPROVED)** |
| `crawlee-python` | Apache-2.0 | Thu thập dữ liệu web công khai (bài báo, tài liệu chuyên môn) | Giấy phép hợp lệ; chỉ cào các trang web có `robots.txt` cho phép | **CHẤP THUẬN CÓ ĐIỀU KIỆN (APPROVED_CONDITIONAL)** |

---

## 4. TỔNG HỢP ƯỚC TÍNH CHI PHÍ & TÍNH KHẢ THI VẬN HÀNH

1. **Giai đoạn Offline MVP (P01 - P10):**
   - Chi phí phần mềm bên ngoài: **0 USD**.
   - Dữ liệu sử dụng: Tập dữ liệu khách hàng tự cung cấp và các bộ fixture offline có nhãn `synthetic=true`.
   - Hạ tầng: Chạy trực tiếp trên máy chủ / máy trạm sẵn có của dự án.
2. **Giai đoạn Tích hợp Kênh & Thử Nghiệm Live (P11 - P13):**
   - Chi phí TikTok API: **0 USD** (hạn mức cơ bản của TikTok Developer).
   - Chi phí LLM Inference: Ước tính **$0.01 - $0.05 / 1 lượt sinh ý tưởng** (khi sử dụng các mô hình thương mại như Claude / GPT qua API). Được bảo vệ bởi Circuit Breaker với trần ngân sách thiết lập sẵn theo từng Research Run.
   - Chi phí cào ngoài (Apify): **0 USD** (chưa kích hoạt do đang ở trạng thái BLOCKED).

---

## 5. KẾT LUẬN & KIẾN NGHỊ
- Kho mã nguồn của dự án PRJ_069 hoàn toàn sạch về mặt bản quyền phần mềm: **ĐÃ LOẠI TRỪ 100% CÁC THƯ VIỆN CÓ GIẤY PHÉP BỊ CẤM (MediaCrawler)**.
- Mô hình dữ liệu được khóa chặt ở tiêu chuẩn an toàn cao nhất: Không tự cào lậu TikTok, lấy dữ liệu khách hàng tự cung cấp làm nền tảng cho việc sinh ý tưởng có căn cứ thực tế.
