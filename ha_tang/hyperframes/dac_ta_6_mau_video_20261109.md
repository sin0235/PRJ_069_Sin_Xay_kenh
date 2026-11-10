# Đặc tả 6 MẪU VIDEO (sản phẩm chính cần làm)

Ngày lập: 09/11/2026. Đây là tài liệu gốc về **sản phẩm cần giao**. Hai tài liệu cùng thư mục là phần phụ trợ:
- `huong_dan_agent_6_mau_hyperframes_20261109.md`: cách làm từng bước (thư viện cảnh, cổng, quy ước).
- `ke_hoach_6_mau_video_hyperframes_20261109.md`: kế hoạch tổng, rubric.

## 0. Sửa hiểu lầm: "mẫu video" khác "cảnh thành phần"

| Khái niệm | Là gì | Thời lượng | Số lượng | Vai trò |
|---|---|---|---|---|
| **Mẫu video** (V1 đến V6) | Một khuôn video trọn vẹn: hook, thân bài, kết; gồm 13 đến 14 cảnh nối nhau, có nhịp, màu, nhạc, kiểu sub và chữ ký chuyển động riêng. Điền một bài nội dung vào khuôn thì ra video hoàn chỉnh | 100 giây | **6** | **Sản phẩm cuối** |
| **Cảnh thành phần** (A đến F, cộng các loại cảnh có sẵn) | Một đoạn cảnh ngắn dựng bằng HyperFrames dùng bên trong mẫu video | 4 đến 10 giây | 6 cảnh mới + các cảnh có sẵn | **Nguyên liệu** của mẫu video |

Trong hai tài liệu trước, "mẫu A đến F" thực chất là **cảnh thành phần**, không phải mẫu video. Từ nay gọi đúng: "cảnh thành phần A đến F" (thư viện cảnh) và "mẫu video V1 đến V6".

Mẫu video không phải là một video mẫu đã quay sẵn. Nó là một khuôn có thể dùng lại cho nhiều bài: cùng cấu trúc phân cảnh, nhịp, phong cách, khác nội dung.

---

## 1. Quy tắc chung của mọi mẫu video

### 1.1 Thông số cố định
- Khung 16:9 (1920×1080), 30 khung hình mỗi giây. Bản 9:16 làm sau.
- Thời lượng 100 giây (khớp mặc định `--thoi-luong 100` của lô hiện tại). Cộng thêm cảnh kết thương hiệu Baha 3 giây do hệ thống tự gắn, không tính vào 100 giây.
- Lời đọc: tốc độ khoảng 3,8 âm tiết mỗi giây (`SPEECH_SYLLABLES_PER_SECOND` trong `planner.py`); mỗi cảnh cần từ 3,0 đến 4,2 âm tiết mỗi giây. Tổng lời đọc 100 giây khoảng 380 âm tiết.
- Bảng màu: "Origami Editorial Motion B2B v1" (navy, ngà, ngọc lam, vàng, san hô). Mỗi mẫu có một màu nhấn chủ đạo (mục 3).
- Giới hạn Flow: tối đa 2 clip Flow mỗi video (mỗi clip 10 giây), tức tối đa 20% thời lượng. Có mẫu chỉ dùng 1 clip.
- Chế độ không dùng Flow: hệ thống đã có chế độ sơ đồ thuần (`CONTENT_VIDEO_DIAGRAM_ONLY=1`, chỉ cho khung 16:9) trong đó mọi cảnh là sơ đồ dựng bằng mã. Mỗi mẫu video phải chạy được ở **cả hai chế độ**: có Flow (thay cảnh hook bằng clip Flow) và không Flow (thay bằng cảnh dựng bằng mã tương đương ở cột "Thay thế khi không Flow").

### 1.2 Quy tắc nhịp cho toàn video
1. Mỗi cảnh 3 đến 10 giây; không có cảnh nào dài hơn 10 giây (giới hạn shot).
2. Cứ 2,5 giây phải có một sự kiện chuyển động mới (khớp `DIAGRAM_SECONDS_PER_EVENT` trong `planner.py`).
3. Hook: trong 3 giây đầu phải có chuyển động nhìn thấy và một câu hỏi hoặc con số gây chú ý.
4. Hai cảnh liền nhau không dùng cùng một layout.
5. Mỗi layout dùng tối đa 2 lần; mỗi "họ" layout tối đa 3 lần (hai quy tắc kiểm hiện có của bộ lập kế hoạch).
6. Có ít nhất 5 loại layout khác nhau trong một video.
7. Cảnh mở đầu kiểu `OPEN_*` chỉ ở shot đầu; `END_CARD` hoặc `CTA_CLOSE` chỉ ở shot cuối cùng và chỉ dùng một trong hai.
8. Nhịp xen kẽ: cảnh nhanh (3 đến 6 giây, nhiều chữ, số) xen cảnh chậm (8 đến 10 giây, nhiều chuyển động vật thể và lia máy). Không có quá 2 cảnh nhanh liên tiếp.

### 1.3 Quy tắc liền mạch giữa các cảnh
1. Mỗi chuyển cảnh dùng một trong 8 kiểu có sẵn (push, cover, scale, dissolve, radial, grid, blur, split). Không dùng một kiểu ba lần liên tiếp.
2. **Khớp hướng:** hướng chuyển động cuối cảnh trước phải là hướng chuyển động đầu cảnh sau (ví dụ cảnh trước lia sang phải thì cảnh sau mở bằng vật vào từ trái hoặc tiếp tục sang phải; không đảo hướng đột ngột).
3. **Khớp sáng:** độ sáng trung bình hai khung ở chỗ nối chênh nhau không quá 25%.
4. Mỗi mẫu có một "chữ ký chuyển động" (mục 3) lặp lại ít nhất 3 lần trong video để tạo nhận diện.

### 1.4 Âm thanh
- Nhạc nền chọn từ thư viện nhạc nền hiện có (`thu_vien_nhac_nen.py`) theo tâm trạng của mẫu (mục 3); âm lượng nền thấp hơn giọng, tự hạ khi có lời (cơ chế duck có sẵn).
- Hiệu ứng âm thanh dùng 9 tệp có sẵn; không quá 1 hiệu ứng mỗi 1,2 giây.
- Chuẩn âm lượng theo EBU R128 của hệ thống; mục tiêu cuối cùng ghi theo cấu hình hiện có, không đổi.

### 1.5 Phụ đề
Mỗi mẫu dùng một cấu hình phụ đề riêng trong bốn mẫu sub chính thức (mục 3), để mỗi mẫu video có diện mạo chữ khác nhau. Sub đặt ở dải y từ 70% trở xuống; mọi vật chính phải ở y từ 8% đến 68%.

### 1.6 Các lớp kiểm của bộ lập kế hoạch mà khuôn phải qua được
`DIAGRAM_LAYOUT_REPEATED`, `DIAGRAM_FAMILY_REPEATED`, `DIAGRAM_OPENING_ONLY_FIRST_SHOT`, `DIAGRAM_END_CARD_ONLY_LAST_SHOT`, `DIAGRAM_BLOCK_LAYOUT_MISSING` (hạn ngạch tối thiểu số cảnh khối dựng sẵn), kiểm lời đọc 3,0 đến 4,2 âm tiết mỗi giây, mỗi shot một ý. Agent phải đọc các hàm này trong `planner.py` trước khi thiết kế khuôn.

---

## 2. Thư viện cảnh dùng cho các mẫu video

### 2.1 Cảnh có sẵn (không cần làm mới)
`OPEN_NUMBER`, `OPEN_QUESTION`, `OPEN_HOOK`, `KINETIC_TITLE`, `MARK_PHRASE`, `WORD_SWAP`, `PILE_UP`, `STAT_RING`, `CHART_STORY`, `KPI_CARDS`, `CHECKLIST`, `FUNNEL`, `PROCESS_RAIL`, `BEFORE_AFTER`, `CARD_SHIFT`, `CHAT_THREAD`, `NOTIFY_STACK`, `CTA_CLOSE`, `END_CARD`, và các loại cảnh sơ đồ khác trong `DIAGRAM_LAYOUTS`.

### 2.2 Cảnh mới cần làm (đặc tả ở `huong_dan_agent_6_mau_hyperframes_20261109.md`, mục 6)
| Mã | Layout | Dùng trong |
|---|---|---|
| E | `LIVE_DASHBOARD` | V1, V2, V3, V4, V5 |
| A | `CASH_RIVER` | V2, V3, V5 |
| B | `PIPELINE_RAIL` | V1, V3, V4, V5, V6 |
| C | `STACK_WAREHOUSE` | V3, V5 |
| D | `BOOK_FLIP` | V4, V6 |
| F | `TEAM_BOARD` | V4, V6 |

### 2.3 Giới hạn thời lượng cảnh cần nâng (đề xuất, Founder duyệt)
Mặc định cảnh dựng bằng mã chỉ 3 đến 6 giây (`UI_SHOT_MAX_SECONDS`). Các mẫu video dưới đây dùng cảnh 7 đến 10 giây cho: sáu cảnh mới, và các cảnh có sẵn `CHECKLIST`, `FUNNEL`, `PROCESS_RAIL`, `BEFORE_AFTER`, `CHART_STORY`. Cần thêm các layout này vào `UI_LAYOUT_MAX_SECONDS` với giá trị 10. Đây là thay đổi hành vi chung, cần duyệt và kiểm hồi quy.

---

## 3. Sáu mẫu video

Cách đọc: cột "Giây" là khoảng thời gian trong video 100 giây. "Cảnh" là layout; "Flow" là clip Flow 10 giây. "Chuyển động chính" mô tả điều người xem thấy. "Cú máy" theo từ vựng ở mục 3.2 của kế hoạch tổng. Chuyển cảnh vào chọn trong 8 kiểu, tránh lặp ba lần liên tiếp. Tổng thời lượng mỗi bảng bằng đúng 100 giây.

### V1. Điểm đau, nguyên nhân, cách gỡ (Pain, Cause, Fix)
- **Ý tưởng:** kể một nỗi đau quen thuộc, chỉ ra nó rò rỉ ở đâu, rồi đưa ra ba bước gỡ.
- **Bài áp dụng:** 01, 02, 13.
- **Màu nhấn:** san hô (vấn đề) chuyển dần sang ngọc lam (giải pháp). Nền navy.
- **Tâm trạng nhạc:** trầm, căng nhẹ ở nửa đầu, sáng dần ở nửa sau.
- **Sub:** `tu_dong`.
- **Chữ ký chuyển động:** một "điểm đỏ" nhấp nháy đánh dấu chỗ rò rỉ, xuất hiện ở cảnh 3, 7 và 9; sau cảnh 11 điểm này chuyển thành xanh ngọc.
| # | Giây | Vai trò | Cảnh | Chuyển động chính | Cú máy | Thay thế khi không Flow |
|---|---|---|---|---|---|---|
| 1 | 0 đến 10 | Hook | Flow | Tình huống đời thường một hành động liên tục | pull back | `PIPELINE_RAIL` (B) bản mở |
| 2 | 10 đến 15 | Câu chốt | `KINETIC_TITLE` | Chữ lớn hiện theo từng từ | push in | |
| 3 | 15 đến 25 | Nỗi đau xảy ra | `PIPELINE_RAIL` (B) | Thẻ chạy, kẹt ở trạm, thẻ rơi | dolly dọc băng chuyền | |
| 4 | 25 đến 31 | Quy mô | `STAT_RING` | Vòng tròn đầy tới tỉ lệ, số đếm | push in | |
| 5 | 31 đến 39 | Nguyên nhân gốc | `MARK_PHRASE` | Khoanh cụm then chốt | rack focus | |
| 6 | 39 đến 47 | Các nhánh nguyên nhân | `HUB_SPOKE` | Nhánh toả từ trung tâm | orbit nhẹ | |
| 7 | 47 đến 55 | Chỗ rò rỉ | `FUNNEL` | Hạt rơi qua phễu, rò ở một tầng | crane xuống | |
| 8 | 55 đến 61 | Cách gọi | `WORD_SWAP` | Từ đổi liên tục rồi dừng | static | |
| 9 | 61 đến 71 | Số liệu thật | `LIVE_DASHBOARD` (E) | Cột mọc, kim vào vùng đỏ | lướt thị sai | |
| 10 | 71 đến 77 | Chuyển ý | `KINETIC_TITLE` | Chữ đổi sang "cách gỡ" | whip pan rồi dừng | |
| 11 | 77 đến 85 | Ba bước gỡ | `CHECKLIST` | Ba mục được tích lần lượt | push in | |
| 12 | 85 đến 95 | Kết quả | Flow | Hình ảnh kết quả tốt, cùng bối cảnh với hook | pull back | `BEFORE_AFTER` |
| 13 | 95 đến 100 | Kêu gọi | `CTA_CLOSE` | Thẻ kết, lời mời | static | |

### V2. Con số tố cáo (Numbers Reveal)
- **Ý tưởng:** mỗi cảnh một con số hoặc biểu đồ làm lộ ra vấn đề, nhịp nhanh, nhiều dữ liệu.
- **Bài áp dụng:** 04, 07, 17.
- **Màu nhấn:** vàng kim trên nền navy; san hô cho con số xấu.
- **Tâm trạng nhạc:** nhịp đều, hơi điện tử, gọn.
- **Sub:** `bento_ba_tang`.
- **Chữ ký chuyển động:** "con số rơi": mỗi con số quan trọng rơi từ trên khung xuống, chạm mặt, nảy một lần, kèm âm đóng dấu (cảnh 1, 4, 10, 12).
- **Ít Flow nhất:** chỉ 1 clip.
| # | Giây | Vai trò | Cảnh | Chuyển động chính | Cú máy | Thay thế khi không Flow |
|---|---|---|---|---|---|---|
| 1 | 0 đến 5 | Hook số | `OPEN_NUMBER` | Con số lớn rơi, nảy | push in | |
| 2 | 5 đến 15 | Bức tranh dữ liệu | `LIVE_DASHBOARD` (E) | Cột mọc, đường xu hướng vẽ dần | lướt thị sai | |
| 3 | 15 đến 21 | Tỉ lệ | `STAT_RING` | Vòng tròn đầy | push in | |
| 4 | 21 đến 31 | Đời thực | Flow | Cảnh đời thực gắn với số liệu | pull back | `CASH_RIVER` (A) |
| 5 | 31 đến 37 | Điểm nhấn | `MARK_PHRASE` | Khoanh cụm then chốt | rack focus | |
| 6 | 37 đến 47 | Diễn biến | `CHART_STORY` | Biểu đồ tự kể | lia ngang | |
| 7 | 47 đến 53 | Câu hỏi | `KINETIC_TITLE` | "Vấn đề nằm ở đâu" | push in | |
| 8 | 53 đến 63 | Dòng tiền thật | `CASH_RIVER` (A) | Xu trôi, rò xuống cống | lia ngang rồi đẩy vào | |
| 9 | 63 đến 69 | Cách gọi | `WORD_SWAP` | Từ đổi rồi dừng | static | |
| 10 | 69 đến 79 | Hai đường giao nhau | `LIVE_DASHBOARD` (E) bộ dữ liệu 2 | Hai chuỗi giao nhau, vòng sáng | lướt thị sai | |
| 11 | 79 đến 85 | Chỉ số chính | `KPI_CARDS` | Thẻ KPI trượt vào | push in | |
| 12 | 85 đến 95 | Việc cần làm | `CHECKLIST` | Mục tích lần lượt | push in | |
| 13 | 95 đến 100 | Kêu gọi | `CTA_CLOSE` | Thẻ kết | static | |

### V3. Dòng chảy (Follow the Flow)
- **Ý tưởng:** camera "đi theo" một vật (đồng xu, kiện hàng, thẻ khách) xuyên suốt nhiều cảnh; vật này là sợi chỉ nối toàn video.
- **Bài áp dụng:** 08, 09, 12.
- **Màu nhấn:** ngọc lam; san hô ở chỗ vật bị kẹt hoặc rò.
- **Tâm trạng nhạc:** trôi, đều, cảm giác chuyển động liên tục.
- **Sub:** `da_sac_phan_tang`.
- **Chữ ký chuyển động:** "vật dẫn đường": cùng một vật xuất hiện cuối cảnh trước và đầu cảnh sau (khớp chuyển động), chuyển cảnh bằng chính vật đó (cảnh 3 sang 4, 4 sang 6, 6 sang 8).
- **Chỉ 1 clip Flow.**
| # | Giây | Vai trò | Cảnh | Chuyển động chính | Cú máy | Thay thế khi không Flow |
|---|---|---|---|---|---|---|
| 1 | 0 đến 10 | Hook | Flow | Giới thiệu vật dẫn đường | pull back | `CASH_RIVER` (A) bản mở |
| 2 | 10 đến 16 | Câu chốt | `KINETIC_TITLE` | Chữ hiện, vật dẫn đường lướt qua | push in | |
| 3 | 16 đến 26 | Dòng chảy vào | `CASH_RIVER` (A) | Vật trôi theo sông, chia nhánh | lia ngang | |
| 4 | 26 đến 36 | Qua quy trình | `PIPELINE_RAIL` (B) | Cùng vật chạy trên băng chuyền | dolly dọc | |
| 5 | 36 đến 42 | Quy mô | `STAT_RING` | Vòng tròn đầy | push in | |
| 6 | 42 đến 52 | Dồn lại | `STACK_WAREHOUSE` (C) | Vật xếp chồng, chồng nghiêng | crane lên | |
| 7 | 52 đến 58 | Cách gọi | `WORD_SWAP` | Từ đổi rồi dừng | static | |
| 8 | 58 đến 68 | Rò rỉ | `FUNNEL` | Vật rơi qua phễu, rò | crane xuống | |
| 9 | 68 đến 74 | Điểm nhấn | `MARK_PHRASE` | Khoanh cụm then chốt | rack focus | |
| 10 | 74 đến 84 | Số liệu | `LIVE_DASHBOARD` (E) | Cột mọc, kim vào vùng đỏ | lướt thị sai | |
| 11 | 84 đến 90 | Việc cần làm | `CHECKLIST` | Mục tích lần lượt | push in | |
| 12 | 90 đến 95 | Chốt ý | `KINETIC_TITLE` | Chữ chốt, vật dẫn đường về chỗ | pull back | |
| 13 | 95 đến 100 | Kêu gọi | `CTA_CLOSE` | Thẻ kết | static | |

### V4. Trước và sau (Transformation)
- **Ý tưởng:** nửa đầu hỗn loạn, tối, đục; nửa sau gọn, sáng, trong. Màu và ánh sáng thay đổi theo câu chuyện.
- **Bài áp dụng:** 06, 18.
- **Màu nhấn:** nửa đầu ngà ngả xám và san hô; nửa sau ngọc lam sáng và vàng.
- **Tâm trạng nhạc:** bắt đầu rối, chuyển sang rõ ràng, nhẹ nhõm.
- **Sub:** `hop_mau_dong_chinh`.
- **Chữ ký chuyển động:** "lật trang": hai lần lật trang 3D chia câu chuyện (cảnh 3 và cảnh 9); sau mỗi lần lật, màu cảnh sáng hơn một mức.
- **Chỉ 1 clip Flow.**
| # | Giây | Vai trò | Cảnh | Chuyển động chính | Cú máy | Thay thế khi không Flow |
|---|---|---|---|---|---|---|
| 1 | 0 đến 10 | Hook (trạng thái hỗn loạn) | Flow | Bàn làm việc bừa bộn | pull back | `PILE_UP` bản mở |
| 2 | 10 đến 16 | Câu chốt | `KINETIC_TITLE` | Chữ hiện | push in | |
| 3 | 16 đến 25 | Trước, lật trang | `BOOK_FLIP` (D) | Giấy lộn xộn, lật trang | orbit nhẹ | |
| 4 | 25 đến 31 | Việc dồn | `PILE_UP` | Việc dồn quanh một người | push in | |
| 5 | 31 đến 41 | Quy trình cũ | `PIPELINE_RAIL` (B) | Thẻ kẹt | dolly dọc | |
| 6 | 41 đến 47 | Thiệt hại | `STAT_RING` | Vòng tròn đầy | push in | |
| 7 | 47 đến 57 | Con người | `TEAM_BOARD` (F) | Chuyền việc, thẻ dồn | rack focus | |
| 8 | 57 đến 63 | Cách gọi | `WORD_SWAP` | Từ đổi rồi dừng | static | |
| 9 | 63 đến 72 | Sau, lật trang | `BEFORE_AFTER` | Trạng thái sau gọn gàng | orbit nhẹ | |
| 10 | 72 đến 82 | Kết quả đo được | `LIVE_DASHBOARD` (E) | Cột mọc lên cao | lướt thị sai | |
| 11 | 82 đến 88 | Điểm nhấn | `MARK_PHRASE` | Khoanh cụm then chốt | rack focus | |
| 12 | 88 đến 95 | Việc cần làm | `CHECKLIST` | Mục tích lần lượt | push in | |
| 13 | 95 đến 100 | Kêu gọi | `CTA_CLOSE` | Thẻ kết | static | |

### V5. Ba sai lầm (Three Mistakes)
- **Ý tưởng:** ba chương, mỗi chương một sai lầm có số thứ tự lớn 1, 2, 3, một cảnh minh hoạ chính và một câu chốt.
- **Bài áp dụng:** 10, 11.
- **Màu nhấn:** san hô cho sai lầm, vàng cho số thứ tự, ngọc lam cho cách làm đúng.
- **Tâm trạng nhạc:** nhịp rõ, mỗi chương có một điểm nhấn nhạc.
- **Sub:** `inline_pop_trai`.
- **Chữ ký chuyển động:** "thẻ số chương": số 1, 2, 3 vào bằng cú quét nhanh rồi dừng (whip pan), mỗi lần có một âm đóng dấu.
- **Chỉ 1 clip Flow.**
| # | Giây | Vai trò | Cảnh | Chuyển động chính | Cú máy | Thay thế khi không Flow |
|---|---|---|---|---|---|---|
| 1 | 0 đến 10 | Hook | Flow | Tình huống gây chú ý | pull back | `STACK_WAREHOUSE` (C) bản mở |
| 2 | 10 đến 15 | Giới thiệu "3 sai lầm" | `KINETIC_TITLE` | Chữ lớn | whip pan rồi dừng | |
| 3 | 15 đến 25 | Sai lầm 1 | `STACK_WAREHOUSE` (C) | Hộp xếp chồng, nghiêng | crane lên | |
| 4 | 25 đến 29 | Chốt 1 | `MARK_PHRASE` | Khoanh cụm then chốt | rack focus | |
| 5 | 29 đến 39 | Sai lầm 2 | `PIPELINE_RAIL` (B) | Thẻ kẹt ở trạm | dolly dọc | |
| 6 | 39 đến 43 | Chốt 2 | `WORD_SWAP` | Từ đổi rồi dừng | static | |
| 7 | 43 đến 53 | Sai lầm 3 | `CASH_RIVER` (A) | Xu rò xuống cống | lia ngang rồi đẩy vào | |
| 8 | 53 đến 57 | Chốt 3 | `STAT_RING` | Vòng tròn đầy | push in | |
| 9 | 57 đến 67 | Tổng kết số liệu | `LIVE_DASHBOARD` (E) | Cột mọc | lướt thị sai | |
| 10 | 67 đến 73 | Chuyển sang cách đúng | `KINETIC_TITLE` | Chữ đổi màu san hô sang ngọc lam | push in | |
| 11 | 73 đến 83 | Ba việc đúng | `CHECKLIST` | Mục tích lần lượt | push in | |
| 12 | 83 đến 89 | Chỉ số theo dõi | `KPI_CARDS` | Thẻ KPI trượt vào | push in | |
| 13 | 89 đến 95 | Chuyển trọng tâm | `CARD_SHIFT` | Tiêu điểm chuyển giữa hai thẻ | rack focus | |
| 14 | 95 đến 100 | Kêu gọi | `CTA_CLOSE` | Thẻ kết | static | |

### V6. Một ngày thật (A Real Day)
- **Ý tưởng:** kể một tình huống có nhân vật origami đi từ lúc bình thường đến lúc rối; người xem tự nhận ra mình.
- **Bài áp dụng:** 03, 14.
- **Màu nhấn:** vàng ấm và ngà; san hô khi rối; ngọc lam khi giải quyết.
- **Tâm trạng nhạc:** kể chuyện, ấm, có điểm lắng.
- **Sub:** `tu_dong`.
- **Chữ ký chuyển động:** "đổi nét theo người": rack focus chuyển tiêu điểm giữa các nhân vật ở cảnh 3, 7 và 10.
- **Hai clip Flow** (cảnh 1 và 5), vì cần cảnh nhân vật.
| # | Giây | Vai trò | Cảnh | Chuyển động chính | Cú máy | Thay thế khi không Flow |
|---|---|---|---|---|---|---|
| 1 | 0 đến 10 | Hook | Flow | Nhân vật bước vào văn phòng | pull back | `TEAM_BOARD` (F) bản mở |
| 2 | 10 đến 16 | Tên tình huống | `KINETIC_TITLE` | Chữ hiện | push in | |
| 3 | 16 đến 26 | Mọi thứ trôi chảy | `TEAM_BOARD` (F) | Chuyền việc, đổi nét | rack focus | |
| 4 | 26 đến 32 | Tin đến | `CHAT_THREAD` | Tin nhắn hiện từng cái | push in | |
| 5 | 32 đến 42 | Khoảnh khắc rối | Flow | Nhân vật bối rối | push in | `NOTIFY_STACK` rồi `PILE_UP` |
| 6 | 42 đến 48 | Việc dồn | `PILE_UP` | Việc dồn quanh một người | push in | |
| 7 | 48 đến 58 | Quy trình kẹt | `PIPELINE_RAIL` (B) | Thẻ kẹt, rơi | dolly dọc | |
| 8 | 58 đến 64 | Thông báo dồn | `NOTIFY_STACK` | Thông báo chồng lên | static | |
| 9 | 64 đến 72 | Điểm nhấn | `MARK_PHRASE` | Khoanh cụm then chốt | rack focus | |
| 10 | 72 đến 81 | Cách làm khác | `BOOK_FLIP` (D) | Trước và sau | orbit nhẹ | |
| 11 | 81 đến 87 | Kết quả | `STAT_RING` | Vòng tròn đầy | push in | |
| 12 | 87 đến 95 | Việc cần làm | `CHECKLIST` | Mục tích lần lượt | push in | |
| 13 | 95 đến 100 | Kêu gọi | `CTA_CLOSE` | Thẻ kết | static | |

### 3.1 Bảng tóm tắt
| Mẫu | Tên | Bài | Flow | Cảnh mới dùng | Sub | Màu nhấn |
|---|---|---|---|---|---|---|
| V1 | Điểm đau, nguyên nhân, cách gỡ | 01, 02, 13 | 2 clip | B, E | `tu_dong` | san hô sang ngọc lam |
| V2 | Con số tố cáo | 04, 07, 17 | 1 clip | E (2 lần), A | `bento_ba_tang` | vàng |
| V3 | Dòng chảy | 08, 09, 12 | 1 clip | A, B, C, E | `da_sac_phan_tang` | ngọc lam |
| V4 | Trước và sau | 06, 18 | 1 clip | D, B, F, E | `hop_mau_dong_chinh` | ngà xám sang ngọc lam sáng |
| V5 | Ba sai lầm | 10, 11 | 1 clip | C, B, A, E | `inline_pop_trai` | san hô, vàng, ngọc lam |
| V6 | Một ngày thật | 03, 14 | 2 clip | F, B, D | `tu_dong` | vàng ấm |
Cả 15 bài đều có mẫu: V1 3 bài, V2 3 bài, V3 3 bài, V4 2 bài, V5 2 bài, V6 2 bài.

---

## 4. Cách điền một bài vào một mẫu video

Bộ lập kế hoạch hiện đưa bài vào LLM để tạo storyboard. Khuôn video đóng vai trò **ràng buộc** cho LLM, không thay LLM viết lời.
1. **Đầu vào:** bài nội dung (md) và tên mẫu video.
2. **Phân đoạn lời đọc:** chia nội dung theo vai trò cảnh trong bảng (hook, nỗi đau, quy mô, ...). Mỗi cảnh nhận một đoạn lời có số âm tiết nằm trong 3,0 đến 4,2 âm tiết mỗi giây nhân với thời lượng cảnh.
3. **Điền dữ liệu cảnh:** mỗi cảnh điền các trường theo mục 5.2 của tài liệu hướng dẫn agent (ví dụ cảnh E cần `labels`, `series`, `to_value`).
4. **Chọn Flow hay sơ đồ thuần:** nếu chạy chế độ có Flow, thay cảnh được ghi "Flow" bằng clip Flow; nếu không, dùng cột "Thay thế khi không Flow".
5. **Kiểm tự động:** storyboard sinh ra phải qua toàn bộ kiểm ở mục 1.6 và các cổng video (mục 5).
6. **Đầu ra:** storyboard đủ 13 đến 14 shot, tổng 100 giây.

Điều khuôn **không** làm: không cố định lời; không ép mọi bài thành cùng một kịch bản; nếu một bài không hợp mẫu đã gán, cho phép đổi sang mẫu khác khi có lý do ghi rõ.

---

## 5. Cổng nghiệm thu cấp video (bổ sung cho các cổng cấp cảnh)

Các cổng cấp cảnh G0 đến G5 (tài liệu hướng dẫn agent, mục 7) áp dụng cho **từng cảnh mới**. Các cổng sau áp dụng cho **cả video**.

| Cổng | Kiểm gì | Tiêu chí đạt | Loại |
|---|---|---|---|
| GV1 | Khung kịch bản của mẫu | Bảng phân cảnh đủ 100 giây; qua kiểm mục 1.2 và 1.6; có chữ ký chuyển động lặp ít nhất 3 lần; Founder duyệt | Duyệt tài liệu |
| GV2 | Storyboard điền thật | Ba bài khác nhau điền vào mẫu đều qua kiểm của bộ lập kế hoạch; mỗi shot đủ trường; lời đọc đúng 3,0 đến 4,2 âm tiết mỗi giây | Tự động |
| GV3 | Nhịp toàn video | Mọi cửa sổ 2,5 giây có ít nhất một sự kiện; hook có chuyển động trong 3 giây đầu; không quá 2 cảnh nhanh liên tiếp; có ít nhất 5 loại layout; Flow không quá 20 giây | Tự động |
| GV4 | Liền mạch | Chuyển cảnh không lặp một kiểu ba lần; khớp hướng ở mọi chỗ nối; chênh sáng không quá 25%; không khung đen kéo dài (kiểm khung đen có sẵn); không nhảy cắt tức thời | Tự động cộng soát mắt |
| GV5 | Âm thanh | Nhạc nền không át giọng; hiệu ứng không dày hơn 1 cái mỗi 1,2 giây; âm lượng đạt chuẩn hiện có của hệ thống; không méo | Đo cộng nghe |
| GV6 | Sub | Đúng kiểu sub của mẫu; sub không che vật chính; sub bám lời | Tự động cộng soát mắt |
| GV7 | Dựng và hiệu năng | Dựng chất lượng sản xuất 100 giây không quá 17 phút (10 giây thực cho mỗi giây video); đỉnh RAM dưới 6 GB; tệp ra hợp lệ, giải mã đầy đủ | Đo đạc |
| GV8 | Duyệt Founder | Phiếu chấm cấp video (mục 6) trung bình từ 4,0, không tiêu chí dưới 3, chấm trên **ba video thật** làm từ ba bài khác nhau | Chấm điểm |
| GV9 | Vào sản xuất | GV1 đến GV8 đạt; mẫu có hướng dẫn một trang "khi nào dùng"; ghi vào danh mục mẫu; có kế hoạch hồi quy | Tổng hợp |

Cổng dừng: nếu một cổng không đạt sau 3 vòng sửa, dừng và báo (mục 0.4 của hướng dẫn agent).

---

## 6. Phiếu chấm cấp video (Founder)

Thang 1 đến 5, đạt khi trung bình từ 4,0 và không tiêu chí nào dưới 3.
| Tiêu chí | Câu hỏi |
|---|---|
| Móc hook | 10 giây đầu có giữ được người xem không |
| Câu chuyện | Có mạch từ vấn đề tới cách gỡ rõ ràng không |
| Nhịp toàn video | Cảnh nhanh chậm xen kẽ hợp lý, không lê thê, không dồn không |
| Chuyển động và lia máy | Vật chuyển động có quy luật, cú máy mượt, không vật bay vô lý |
| Liền mạch | Các cảnh nối nhau tự nhiên, có sợi chỉ chung |
| Nhận diện | Chữ ký chuyển động và màu nhấn riêng của mẫu rõ không |
| Chữ và sub | Dễ đọc, không che hình, bám lời |
| Sẵn sàng sản xuất | Có thể dùng cho bài khác cùng loại không |

---

## 7. Lộ trình làm (thay cho lộ trình trước)

Thứ tự bám theo phụ thuộc của cảnh mới. Pilot là V2 vì chỉ cần hai cảnh mới (E và A), cộng cảnh có sẵn.

| Giai đoạn | Việc | Phụ thuộc | Cổng kết thúc |
|---|---|---|---|
| 0 | T00 đến T03: đường cơ sở, bộ tài sản, công cụ ghi vết, bộ chạy cổng | | |
| 1 | Cảnh E `LIVE_DASHBOARD` rồi cảnh A `CASH_RIVER` (cổng cấp cảnh) | giai đoạn 0 | G0 đến G7 cấp cảnh |
| 2 | **Pilot V2** (đủ GV1 đến GV8) và báo cáo hiệu chỉnh | cảnh E, A | **DỪNG chờ Founder** |
| 3 | Cảnh B rồi **V1** | pilot được duyệt | GV1 đến GV9 |
| 4 | Cảnh C rồi **V3** | cảnh A, B, E | GV1 đến GV9 |
| 5 | Cảnh D, F rồi **V4**, **V6** | cảnh B, E | GV1 đến GV9 |
| 6 | **V5** (đủ cảnh) | cảnh A, B, C, E | GV1 đến GV9 |
| 7 | Nối vào bộ lập kế hoạch: chọn mẫu theo bài, giảm Flow, nâng giới hạn thời lượng | tuỳ mẫu | hồi quy |
| 8 | Thí điểm 5 video thật, báo cáo hiệu quả | giai đoạn 7 | báo cáo |

Ước lượng thô: 10 đến 12 tuần với một người làm chính và một người duyệt, cần hiệu chỉnh sau pilot.

---

## 8. Việc cần Founder quyết (mới)
1. **Xác nhận định nghĩa:** "6 mẫu video" là sáu khuôn video 100 giây như V1 đến V6 ở trên. Nếu bạn nghĩ tới sáu loại khác (ví dụ chia theo ngành, theo độ dài, theo nền tảng), cho biết để tôi sửa lại mục 3.
2. Có đồng ý sáu thể loại V1 đến V6 không (điểm đau, con số, dòng chảy, trước sau, ba sai lầm, một ngày thật), hay muốn đổi thể loại nào.
3. Có đồng ý nâng giới hạn thời lượng cảnh lên 10 giây cho các layout nêu ở mục 2.3.
4. Mỗi mẫu có kiểu sub riêng như mục 3.1 (dùng đủ bốn mẫu sub chính thức) hay dùng chung `tu_dong`.
5. Chạy chế độ có Flow (tối đa 1 đến 2 clip) hay chế độ sơ đồ thuần (không Flow) làm mặc định cho khung 16:9.
