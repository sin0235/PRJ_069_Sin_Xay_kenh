# Kế hoạch 6 mẫu video HyperFrames: giảm Flow, tăng chuyển động thật

> **ĐÍNH CHÍNH:** "6 mẫu" là **6 mẫu video trọn vẹn** (V1 đến V6, mỗi mẫu một khuôn video 100 giây), đặc tả ở `dac_ta_6_mau_video_20261109.md`. Sáu "mẫu A đến F" trong mục 4 và phụ lục 1 của tài liệu này thực chất là **sáu cảnh thành phần** (thư viện cảnh) dùng bên trong các mẫu video. Cách gán bài vào mẫu video nằm ở mục 3.1 của tài liệu đặc tả, thay cho phụ lục 1 ở đây. Các cổng cấp video (GV1 đến GV9) nằm ở tài liệu đặc tả; các cổng G0 đến G7 ở đây áp dụng cho từng cảnh thành phần.

Ngày lập: 09/11/2026. Trạng thái: bản đề xuất để Founder duyệt. Tài liệu này chỉ gồm kế hoạch, không có mã.
Các con số ngưỡng ở mục 7 là đề xuất ban đầu, được hiệu chỉnh sau lượt thử đầu tiên (mục 9, giai đoạn 0).

---

## 1. Mục tiêu và phạm vi

### 1.1 Vấn đề cần giải
1. Clip Flow luôn dài đúng 10 giây và tốn tín dụng. Hiện kế hoạch gợi ý khoảng 60% thời lượng video là Flow (`planner.py`, hàm gợi ý cấu trúc).
2. Clip Flow hay có hành động phi lý: vật thể tự bay, tự xuất hiện, tự biến mất. Lời nhắc hiện vừa đòi "2–4 lớp chuyển động" vừa đòi "không xuất hiện hoặc biến mất đột ngột", hai yêu cầu này kéo ngược nhau.
3. Cảnh sơ đồ (UI_SIM) dựng bằng mã còn tĩnh và giống nhau giữa các bài, thiếu cảm giác "vật thể thật đang chuyển động" và thiếu lia máy.

### 1.2 Mục tiêu đo được
| Chỉ số | Hiện tại | Mục tiêu |
|---|---|---|
| Tỉ lệ thời lượng dùng Flow trong một video 100 giây | khoảng 60% | không quá 20% (tối đa 2 clip Flow cho hook và cảnh kết) |
| Số clip Flow cần tạo cho một video | khoảng 6 | không quá 2 |
| Cảnh có chuyển động vật thể thật và lia máy | một phần | 100% cảnh dựng bằng 6 mẫu |
| Lỗi "vật thể xuất hiện hoặc biến mất đột ngột" | thường xuyên ở Flow | 0 lỗi ở cổng G3 |
| Điểm duyệt thị giác của Founder (thang 5) | chưa đo | trung bình từ 4,0 và không tiêu chí nào dưới 3 |

### 1.3 Ngoài phạm vi
- Không thay đổi sub (đã làm ở nhánh khác) và không thay đổi giọng đọc.
- Không bỏ hẳn Flow: hook mở đầu và cảnh kết vẫn có thể dùng Flow khi cần cảnh người thật, không gian thật.
- Chưa bàn tới việc dùng GPU rời hay dịch vụ dựng đám mây; kế hoạch chạy trên hạ tầng hiện có.

---

## 2. Hiện trạng và giới hạn kỹ thuật (đã kiểm trong dự án)

| Hạng mục | Thực tế | Hệ quả cho kế hoạch |
|---|---|---|
| Phiên bản HyperFrames | 0.8.222; kho khối có 159 mục trong `engines/hyperframes/blocks/catalog.json` | Có nhiều khối chữ, nền, lớp phủ dùng lại được |
| Chuyển cảnh | 8 kiểu GSAP: push, cover, scale, dissolve, radial, grid, blur, split. Chuyển cảnh shader đã khảo sát và chưa dùng được | Không hứa hiệu ứng shader; mọi chuyển cảnh thiết kế bằng 8 kiểu này hoặc bằng chuyển động vật thể |
| Camera | 4 kiểu cơ bản (push in, pull back, shake, rack focus) và 12 giá trị `camera_motion` cho cảnh sơ đồ (AUTO, DOLLY_ORBIT, TRACK_RACK, CRANE_PUSH, ARC_REVEAL, STATIC, ORBIT_ARC, CRANE_DIVE, PARALLAX_PASS, WHIP_PAN_SETTLE, DOLLY_RACK, DOLLY_ZOOM) | Đã có từ vựng camera; mẫu mới phải dùng đúng bộ từ vựng này để giữ tương thích |
| Phần cứng dựng | Khảo sát shader ghi nhận RAM 8 GB, không GPU rời, Chrome headless SwiftShader; khoảng 8,4 giây thực cho mỗi giây video | Một video 100 giây mất khoảng 14 phút; ngân sách dựng mục 9 tính theo con số này |
| Bảng màu và phong cách | "Origami Editorial Motion B2B v1": xanh navy, ngà, ngọc lam, vàng, đỏ san hô; font Be Vietnam Pro | Mọi mẫu dùng chung bảng màu này |
| Âm thanh hoạt hoạ | 9 tệp SFX có sẵn: bật mở, cảnh báo, chờ nhẹ, đóng dấu, gõ nhẹ, gõ phím, lật trang, lướt nhanh, lướt nhẹ | Mẫu mới tái sử dụng bộ này, bổ sung khi thiếu |
| Cổng chất lượng hiện có | `ha_tang/hyperframes/cong_chat_luong.py`: chạy `hyperframes check`, quét từ mẫu tiếng Anh, quét URL ngoài, chụp ảnh ở 60% thời lượng để kiểm chữ tràn | Giữ nguyên làm nền cho G2 và G4; bổ sung các cổng chuyển động (G3) |

Giới hạn quan trọng: HyperFrames dựng theo khung thời gian xác định (GSAP, không có động cơ vật lý thật). "Vật chuyển động thật" ở đây nghĩa là chuyển động được thiết kế theo quy tắc vật lý nhìn thấy được (khối lượng, quán tính, đường cong, va chạm có phản ứng), không phải mô phỏng vật lý. Đây là điều phải nói rõ với Founder để kỳ vọng đúng.

---

## 3. Nguyên tắc "chuyển động thật" (áp dụng cho cả 6 mẫu)

### 3.1 Mười hai quy tắc
1. **Mỗi vật có khối lượng.** Vật nặng bắt đầu chậm, dừng có nảy nhẹ; vật nhẹ (giấy) bay chậm, lắc nhẹ khi dừng. Không dùng chuyển động tuyến tính đều cho vật thể.
2. **Đường đi cong, không đi thẳng cứng.** Vật di chuyển theo cung hoặc đường dẫn, kèm xoay nhẹ theo hướng đi.
3. **Mọi vật xuất hiện phải có nguồn.** Vật vào khung từ ngoài khung, từ một vật khác (mở ra, bung ra), hoặc rơi xuống từ trên. Cấm hiện ra tại chỗ bằng mờ dần khi vật đó là vật thể (chỉ cho phép với chữ và lớp sáng).
4. **Mọi vật biến mất phải có đích.** Vật ra khỏi khung, gấp lại, chui vào vật khác hoặc bị vật khác che. Cấm biến mất đột ngột.
5. **Va chạm có phản ứng.** Khi vật A chạm vật B, B phải rung, lún hoặc bị đẩy ngay trong khung hình kế tiếp; có bóng tiếp xúc đổi theo.
6. **Mỗi cảnh một hành động chính và tối đa hai hành động phụ.** Mọi chuyển động phải phục vụ ý lời đọc; không thêm vật bay để "cho có chuyển động".
7. **Cảnh là một "thế giới" có chiều sâu.** Tối thiểu 3 lớp (nền, giữa, tiền cảnh) với tốc độ trôi khác nhau khi lia máy (thị sai), kèm một lớp làm mờ chiều sâu cho tiền cảnh hoặc hậu cảnh.
8. **Camera là một cú máy có chủ đích.** Mỗi cảnh chọn một cú máy chính từ bộ từ vựng mục 3.2; cú máy bắt đầu chậm, đạt tốc độ, rồi dừng êm; không rung giật trừ cảnh cảnh báo có chủ ý.
9. **Chuyển động bám lời đọc.** Mỗi sự kiện chính gắn với một mốc từ trong lời đọc của chính cảnh đó (kỹ thuật mốc từ đã có ở `diagram.on`); lệch cho phép được nêu ở mục 7.
10. **Luôn có vi chuyển động.** Vật đứng yên vẫn "thở": nổi lên xuống nhẹ, lá giấy rung nhẹ, hạt bụi trôi; tránh khung hình chết quá 1 giây.
11. **Bóng, texture và ánh sáng đồng nhất.** Mọi vật có bóng đổ cùng hướng sáng; một lớp hạt phim hoặc vân giấy rất nhẹ phủ chung để cả cảnh trông cùng một chất liệu origami.
12. **Nhịp 2 giây.** Cứ khoảng 2 giây phải có một sự kiện chuyển động mới (vật mới vào, đổi cú máy, đổi trọng tâm); không để một cảnh trôi dài chỉ có một cú máy chậm.

### 3.2 Từ vựng camera dùng chung
| Cú máy | Mô tả | Dùng khi | Tương ứng hệ thống hiện có |
|---|---|---|---|
| Đẩy vào (push in) | Tiến chậm vào chủ thể | Nhấn mạnh con số, điểm đau | push_in, CRANE_PUSH, DOLLY_ZOOM |
| Lùi ra (pull back) | Lùi lộ toàn cảnh | Mở cảnh, lộ quy mô | pull_back |
| Lia ngang (pan/track) | Trượt ngang theo dòng chảy hoặc băng chuyền | Quy trình, dòng tiền | TRACK_RACK, DOLLY_RACK |
| Nâng lên (crane up) | Máy nâng, lộ tầng trên | Xếp chồng, kho hàng | CRANE_PUSH, CRANE_DIVE |
| Vòng cung nhẹ (orbit) | Quay vòng ít độ quanh chủ thể | Trước và sau, so sánh | DOLLY_ORBIT, ORBIT_ARC, ARC_REVEAL |
| Lướt thị sai (parallax pass) | Máy trượt, các lớp trôi khác tốc độ | Bảng điều khiển, thành phố dữ liệu | PARALLAX_PASS |
| Đổi nét (rack focus) | Chuyển nét giữa hai vật | Chuyển trọng tâm giữa hai nhân vật | rack_focus |
| Quét nhanh rồi dừng (whip pan) | Quét ngang nhanh, dừng êm | Chuyển ý, vào cảnh mới | WHIP_PAN_SETTLE |

Giới hạn tốc độ camera (đề xuất, chốt lại ở giai đoạn 0): lia ngang tối đa 12% bề rộng khung mỗi giây; quét nhanh (whip pan) tối đa 40% mỗi giây và không quá 0,5 giây; phóng vào hoặc ra tối đa 8% mỗi giây; nâng hoặc hạ tối đa 10% bề cao khung mỗi giây. Vượt giới hạn là lỗi ở cổng G3.

---

## 4. Sáu cảnh thành phần (thư viện cảnh dùng trong các mẫu video)

Mọi mẫu có chung: khung 16:9 (mở rộng 9:16 ở giai đoạn sau), thời lượng cảnh tối đa 10 giây (một shot không quá 10 giây; cảnh dựng bằng mã hiện bị giới hạn 3–6 giây nên cần nâng giới hạn riêng cho 6 layout mới, xem hướng dẫn cho agent), bảng màu origami, bộ âm thanh mục 2, và nhận dữ liệu qua "hợp đồng biến" (mục 5). Mô tả dưới đây là thiết kế chuyển động mức tổng quan, chưa phải mã. Bảng nhịp chi tiết từng giây (đã khớp giới hạn 10 giây và giới hạn camera) nằm ở `huong_dan_agent_6_mau_hyperframes_20261109.md`, mục 6; nếu có khác biệt về giây hoặc con số thì lấy tài liệu hướng dẫn agent làm chuẩn.

### Mẫu A. Dòng tiền chảy (Cash River)
- **Dùng cho:** dòng tiền, thiếu tiền trả lương, vay vốn, giảm giá lỗ nặng. Bài 08, 09, 10.
- **Thế giới:** một con sông giấy cắt ngang cảnh chia nhiều nhánh; hồ chứa bên phải; cống bên trái.
- **Vật chuyển động thật:** đồng xu giấy trôi theo dòng, quay chậm trên mặt nước; túi tiền phồng lên và xẹp; cống rút xoáy kéo xu xoay vòng rồi biến mất xuống cống (có đích); mực nước hồ tụt hoặc dâng thật.
- **Chuỗi chuyển động (khoảng 10 giây):** 0–2 giây lùi ra lộ sông, xu trôi vào từ mép trái; 2–5 giây lia ngang theo dòng, xu chia nhánh; 5–8 giây đẩy vào cống, xoáy kéo xu; 8–10 giây đổi nét sang hồ cạn, con số lớn rơi xuống đặt lên mặt hồ.
- **Camera chính:** lia ngang theo dòng, kết bằng đẩy vào.
- **Chuyển cảnh vào, ra:** cover (tờ giấy gấp phủ) vào; blur nhẹ ra.
- **Âm thanh:** lướt nhẹ cho dòng chảy, đóng dấu khi con số đặt xuống.
- **Tài sản cần:** bộ SVG đồng xu giấy, túi tiền, cống, sông nhiều lớp.
- **Rủi ro:** làm xoáy nước thật cần nhiều phần tử chuyển động; giữ số xu tối đa 24 để dựng không quá nặng.

### Mẫu B. Đường ống quy trình (Pipeline Rail)
- **Dùng cho:** phễu bán hàng, báo giá rồi im lặng, gọi khách, giao hàng trễ. Bài 01, 02, 13.
- **Thế giới:** băng chuyền giấy chạy sâu vào trong khung (phối cảnh), các trạm kiểm dọc theo.
- **Vật chuyển động thật:** thẻ hồ sơ, thẻ khách hàng chạy trên băng chuyền, lên xuống nhẹ theo mối nối; thẻ bị kẹt ở trạm nghẽn làm các thẻ sau dồn lại rồi nén vào nhau; một thẻ rơi khỏi băng chuyền (khách mất) và rơi xuống theo quỹ đạo, nảy một lần.
- **Chuỗi chuyển động:** 0–2 giây thẻ vào từ xa, camera lùi; 2–5 giây dolly dọc băng chuyền, thẻ qua từng trạm; 5–8 giây trạm nghẽn, thẻ dồn, rung; 8–11 giây một thẻ rơi, đổi nét sang thẻ rơi, nhãn mất đơn hiện bên cạnh.
- **Camera chính:** dolly dọc băng chuyền, đổi nét ở cuối.
- **Chuyển cảnh:** push vào; scale ra.
- **Âm thanh:** gõ nhẹ khi thẻ qua trạm, cảnh báo khi nghẽn.
- **Tài sản:** thẻ giấy nhiều màu, trạm kiểm, băng chuyền module.
- **Rủi ro:** phối cảnh sai làm thẻ trượt; cần bảng tọa độ cố định cho làn băng chuyền.

### Mẫu C. Kho hàng xếp chồng (Stack Warehouse)
- **Dùng cho:** kho đầy hàng thiếu món cần, đội xe chạy liên tục lợi nhuận thấp. Bài 11, 12.
- **Thế giới:** nhà kho giấy nhiều tầng kệ; sân bãi có xe.
- **Vật chuyển động thật:** hộp giấy rơi từ trên xuống xếp chồng có nảy và nghiêng; chồng cao rung lắc rồi đổ một góc; xe nâng, xe tải giấy chạy đúng đường, quay đầu có lái; mũi tên quãng đường rỗng trải dần.
- **Chuỗi chuyển động:** 0–2 giây hộp rơi vào từ trên, xếp chồng; 2–6 giây nâng máy lên lộ tầng, chồng cao dần; 6–9 giây chồng nghiêng, một hộp cần tìm bị chôn, đổi nét; 9–11 giây xe chạy một vòng dài rỗng.
- **Camera chính:** nâng lên (crane up), kết bằng đổi nét.
- **Âm thanh:** gõ nhẹ khi hộp chạm, cảnh báo khi chồng nghiêng.
- **Rủi ro:** xếp chồng "vật lý" bằng thời gian cố định phải được vẽ tay từng hộp; giới hạn 20 hộp.

### Mẫu D. Trước và sau lật trang (Before After Flip)
- **Dùng cho:** khách mới và khách cũ, nhân viên quay lại Excel sau khi mua phần mềm. Bài 06, 18.
- **Thế giới:** một bàn làm việc nhìn từ trên xuống nghiêng nhẹ; trang giấy lớn ở giữa.
- **Vật chuyển động thật:** bàn "trước" bừa bộn (giấy tờ, bảng tính, ghi chú dán) với ghi chú rung nhẹ; trang giấy lật 3D theo gáy sách; bàn "sau" sắp gọn, giấy tờ bay về đúng chỗ theo đường cong và xếp vào ngăn.
- **Chuỗi chuyển động:** 0–3 giây trạng thái trước, máy vòng cung nhẹ; 3–5 giây lật trang (lật có độ cong thật, bóng đổi); 5–9 giây giấy tờ bay về xếp vào ngăn lần lượt; 9–10 giây đẩy vào nhãn kết quả.
- **Camera chính:** vòng cung nhẹ (orbit).
- **Âm thanh:** lật trang, lướt nhanh khi giấy bay về chỗ.
- **Rủi ro:** lật trang 3D bằng biến đổi CSS có thể lộ mặt sau; cần kiểm mặt sau trong G4.

### Mẫu E. Bảng điều khiển sống (Living Dashboard)
- **Dùng cho:** quảng cáo có lượt xem nhưng không ra đơn, doanh thu tăng lợi nhuận giảm, báo cáo nhiều sếp không biết khoẻ hay yếu. Bài 04, 07, 17.
- **Thế giới:** "thành phố dữ liệu" gồm các toà nhà dạng cột biểu đồ, tấm bảng KPI nổi, đồng hồ đo, đường xu hướng.
- **Vật chuyển động thật:** cột mọc lên có độ nảy; kim đồng hồ chạy có quán tính và rung khi tới ngưỡng; đường xu hướng vẽ dần có điểm sáng chạy dọc; thẻ KPI trượt vào từ ngoài khung và dừng có nảy.
- **Chuỗi chuyển động:** 0–3 giây lướt thị sai qua thành phố, cột mọc lần lượt; 3–6 giây đẩy vào cột nổi bật, kim đồng hồ tới vùng đỏ; 6–9 giây quét ngang sang cột thứ hai (doanh thu tăng, lợi nhuận giảm), hai đường giao nhau; 9–11 giây lùi ra, nhãn kết luận.
- **Camera chính:** lướt thị sai, đẩy vào.
- **Âm thanh:** gõ nhẹ khi cột chạm đáy, bật mở khi thẻ KPI vào.
- **Rủi ro:** quá nhiều phần tử làm dựng chậm; giới hạn 5 cột và 3 thẻ KPI mỗi cảnh.

### Mẫu F. Bàn cờ đội ngũ (Team Board)
- **Dùng cho:** giao việc, giám đốc nghỉ một ngày công ty rối loạn, gọi khách ngoài giờ. Bài 03, 14.
- **Thế giới:** mặt bàn giao việc với các cột trạng thái, nhân vật origami ngồi hai bên.
- **Vật chuyển động thật:** nhân vật origami nghiêng người, giơ tay, chuyền thẻ việc cho nhau theo đường cong; khi người ra quyết định vắng mặt, thẻ việc trượt xuống cuối cột và chất đống; cột trống tối dần.
- **Chuỗi chuyển động:** 0–3 giây nhân vật chuyền thẻ trôi chảy, máy đổi nét giữa hai người; 3–6 giây ghế giám đốc trống, thẻ dồn; 6–9 giây thẻ chồng lên, một thẻ đỏ nảy lên báo gấp; 9–11 giây lùi ra toàn bàn.
- **Camera chính:** đổi nét giữa hai nhân vật, kết bằng lùi ra.
- **Âm thanh:** gõ nhẹ khi chuyền thẻ, cảnh báo khi thẻ đỏ nảy.
- **Rủi ro:** hoạt hình nhân vật khó nhất; bắt đầu bằng 2 tư thế chính và nội suy.

### Hai khối dùng chung ngoài 6 mẫu
- **Hook mở đầu:** con số lớn rơi vào khung theo quỹ đạo, chữ trượt theo mốc từ; đã có khối `OPEN_NUMBER`, `OPEN_QUESTION`, `OPEN_HOOK` và nên được nâng cấp theo các quy tắc mục 3.
- **Cảnh kết:** dùng lại cảnh kết thương hiệu Baha đã có (logo, lời mời theo dõi).

---

## 5. Hợp đồng biến và cách nối vào hệ thống

Mỗi mẫu nhận dữ liệu qua một bộ biến cố định, không nhận mã tùy ý. Điều này giữ nguyên nguyên tắc của dự án: mọi chữ hiển thị là tiếng Việt, không lọt từ mẫu tiếng Anh.

| Nhóm biến | Ví dụ | Ghi chú |
|---|---|---|
| Văn bản | tiêu đề cảnh, nhãn, kết luận | Tối đa độ dài quy định theo mẫu; có dấu tiếng Việt |
| Số liệu | giá trị lớn, 2–5 điểm dữ liệu, đơn vị | Mẫu A, E dùng nhiều nhất |
| Sự kiện bám lời | mỗi sự kiện gắn một cụm nguyên văn có trong lời đọc của cảnh | Theo đúng thứ tự xuất hiện trong lời (quy tắc `EVENT_ORDER` hiện có) |
| Cú máy | một giá trị trong bộ từ vựng mục 3.2 | Mặc định theo mẫu, cho phép đổi trong danh sách được phép |
| Cường độ | nhẹ, vừa, mạnh | Chỉ đổi biên độ chuyển động, không đổi cấu trúc |

**Quy tắc chọn mẫu cho một bài:** người lập kịch bản (hoặc bộ lập kế hoạch) chọn mẫu theo bảng phụ lục 1; một video 100 giây có tối đa 2 cảnh dùng lại cùng một mẫu để tránh lặp.

**Quy tắc giảm Flow:** mỗi video chỉ giữ tối đa 2 clip Flow: một clip hook (cảnh khung rộng gây ấn tượng) và một clip kết khi cần cảnh người thật. Mọi cảnh giải thích dùng 6 mẫu. Với Flow còn lại, lời nhắc sửa theo hướng: một hành động liên tục, máy chậm, cấm vật tự bay, tự hiện, tự biến mất (việc này làm ở nhánh riêng, đã được Founder chọn là "sửa lời nhắc, đo thử trên vài clip").

---

## 6. Quy trình làm một mẫu (hướng dẫn chi tiết cho người thực hiện)

Mỗi mẫu đi qua 10 bước. Không bước nào được bỏ; kết quả mỗi bước là một tài liệu hoặc tệp nộp vào thư mục mẫu để người duyệt kiểm.

1. **Tờ yêu cầu (một trang).** Nêu ý chính cần truyền đạt, bài áp dụng, thời lượng, vật chuyển động chính, cú máy chính, giới hạn số phần tử. Người duyệt: Founder hoặc người được ủy quyền.
2. **Bảng ảnh tham chiếu và tâm trạng.** 6–10 ảnh hoặc clip tham chiếu cho chất liệu giấy, ánh sáng, chuyển động. Ghi rõ điều học từ mỗi ảnh (không sao chép).
3. **Kế hoạch lớp.** Liệt kê các lớp (nền, giữa, tiền cảnh, lớp phủ) và tốc độ thị sai của từng lớp; liệt kê mọi vật chuyển động với nguồn xuất hiện và đích biến mất (quy tắc 3, 4).
4. **Bảng nhịp (beat sheet) theo giây.** Một bảng gồm mốc thời gian, sự kiện, vật nào, cú máy, âm thanh, mốc từ lời đọc. Đây là tài liệu quan trọng nhất; duyệt ở cổng G1 trước khi dựng.
5. **Chuẩn bị tài sản.** Vẽ hoặc chuẩn hoá các hình vector cho vật thể (một phong cách origami thống nhất), đặt tên theo quy ước, kiểm font tiếng Việt, loại bỏ mọi nguồn tải từ ngoài.
6. **Dựng thế giới tĩnh.** Dựng đúng bố cục các lớp, chưa có chuyển động; chụp ảnh khung giữa để kiểm bố cục, chữ không tràn, tương phản.
7. **Thêm chuyển động theo bảng nhịp.** Làm từng sự kiện một, kiểm từng sự kiện trước khi thêm sự kiện kế tiếp; bắt đầu bằng cú máy, sau đó vật chính, sau đó vật phụ và vi chuyển động.
8. **Lớp hoàn thiện.** Bóng đổ, hạt phim nhẹ, vân giấy, ánh sáng, làm mờ chiều sâu; âm thanh từ bộ có sẵn.
9. **Thử với ba nội dung khác nhau.** Điền ba bộ dữ liệu thật (từ ba bài khác nhau) để chắc mẫu không gãy khi chữ dài ngắn khác nhau và khi số liệu khác nhau.
10. **Nộp cổng.** Chạy toàn bộ cổng G2 đến G6 (mục 7); chỉ khi đạt mới ghi vào danh mục mẫu và cho phép dùng trong sản xuất.

### 6.1 Việc nên làm và không nên làm
| Nên | Không nên |
|---|---|
| Mỗi cảnh một ý, một cú máy chính | Nhồi 4 hành động trong một cảnh |
| Vật vào khung từ ngoài khung hoặc từ vật khác | Cho vật hiện ra giữa khung bằng mờ dần |
| Dùng làm chậm khi dừng (easing) và nảy nhẹ cho vật nặng | Chuyển động tuyến tính đều cho mọi vật |
| Gắn sự kiện chính với mốc từ lời đọc | Canh thời gian bằng mắt rồi cố định |
| Giữ số phần tử chuyển động trong giới hạn từng mẫu | Thêm hạt, vật bay để làm "đẹp" |
| Kiểm cả khi chữ rất dài và rất ngắn | Chỉ thử với một câu mẫu |

### 6.2 Lỗi thường gặp và cách xử lý
| Lỗi | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Vật giật, nhảy vị trí | Hai chuyển động cùng điều khiển một thuộc tính | Mỗi thuộc tính chỉ một chuyển động tại một thời điểm |
| Vật hiện đột ngột | Quên nguồn vào hoặc thời gian bắt đầu sớm hơn nguồn | Dựng lại đường vào từ ngoài khung |
| Camera rung, trôi lệch | Cú máy vượt giới hạn tốc độ hoặc dừng đột ngột | Giảm biên độ, thêm đoạn dừng êm |
| Chữ che vật chính | Chồng lớp sai | Đẩy chữ về vùng an toàn, giảm cỡ |
| Dựng chậm, hết RAM | Quá nhiều phần tử hoặc bộ lọc nặng | Giảm số phần tử về giới hạn mẫu, bỏ bộ lọc nặng |
| Mặt sau trang lật lộ ra | Lật 3D không ẩn mặt sau | Thêm mặt sau thiết kế riêng hoặc giới hạn góc lật |

### 6.3 Quy ước tệp và phiên bản
- Mỗi mẫu một thư mục `mau_<chu_cai>_<ten_ngan>/` gồm: tờ yêu cầu, ảnh tham chiếu, bảng nhịp, tài sản, bản dựng, báo cáo cổng.
- Phiên bản theo dạng `v1.0`, tăng số phụ khi sửa nhỏ, tăng số chính khi đổi bố cục hoặc hợp đồng biến.
- Mọi bản duyệt phải ghi: ai duyệt, ngày, điểm từng tiêu chí, ghi chú sửa.

---

## 7. Các cổng nghiệm thu

Mỗi cổng có người chịu trách nhiệm, đầu vào, tiêu chí đạt và hành động khi không đạt. Không qua cổng thì không sang giai đoạn sau. Các ngưỡng số là đề xuất và được chốt lại sau lượt thử giai đoạn 0.

### G0. Cổng chuẩn bị
- **Đầu vào:** tờ yêu cầu, ảnh tham chiếu, danh sách tài sản.
- **Tiêu chí đạt:** (1) tờ yêu cầu đủ mục; (2) mọi tài sản là vector hoặc ảnh có giấy phép rõ ràng; (3) font hiển thị đúng toàn bộ dấu tiếng Việt kể cả chữ hoa (Đ, Ắ, Ễ, Ộ, Ứ); (4) không nguồn tải từ ngoài; (5) không từ mẫu tiếng Anh trong tài sản.
- **Không đạt:** trả lại người làm, không dựng.

### G1. Cổng thiết kế chuyển động
- **Đầu vào:** bảng nhịp theo giây, kế hoạch lớp, danh sách vật và nguồn vào, đích ra.
- **Tiêu chí đạt:** (1) mỗi vật có nguồn vào và đích ra; (2) mỗi cảnh một hành động chính, không quá hai phụ; (3) có một cú máy chính nằm trong bộ từ vựng; (4) khoảng cách giữa hai sự kiện liên tiếp không quá 2,5 giây; (5) mọi sự kiện chính có mốc từ lời đọc; (6) số phần tử không vượt giới hạn mẫu.
- **Người duyệt:** Founder hoặc người được ủy quyền; thời hạn phản hồi 2 ngày làm việc.

### G2. Cổng kỹ thuật (tự động)
- Dựa trên cổng chất lượng hiện có và mở rộng.
- **Tiêu chí đạt:** (1) lệnh kiểm của HyperFrames không báo lỗi cấu trúc hoặc chạy; (2) không từ mẫu tiếng Anh; (3) không URL ngoài; (4) độ dài đúng thời lượng quy định, sai số không quá 1 khung hình; (5) dựng hai lần cho ra cùng kết quả (tính xác định); (6) tệp ra đúng độ phân giải, tốc độ khung hình và có giải mã trọn vẹn.

### G3. Cổng chuyển động (tự động cộng soát bằng mắt)
Đây là cổng mới và quan trọng nhất vì giải quyết trực tiếp lỗi "vật bay, hiện, biến mất đột ngột".
- **Kiểm "không dịch chuyển tức thời":** trích khung theo bước 1/30 giây; không vật nào dịch quá 12% bề rộng khung giữa hai khung liền nhau, trừ whip pan có chủ ý ghi trong bảng nhịp.
- **Kiểm "vật xuất hiện, biến mất":** mỗi lần số vật trong khung tăng hoặc giảm phải khớp một sự kiện nguồn vào hoặc đích ra trong bảng nhịp; sai khác là lỗi.
- **Kiểm "nhịp 2 giây":** mọi cửa sổ 2,5 giây liên tiếp có ít nhất một sự kiện chuyển động mới.
- **Kiểm tốc độ camera:** không vượt giới hạn mục 3.2.
- **Kiểm "chuyển động có khối lượng":** gia tốc vật không bằng 0 đột ngột khi dừng, tức có đoạn giảm tốc; vật nặng có phản ứng khi va chạm.
- **Kiểm "bám lời":** mỗi sự kiện chính lệch lời đọc không quá 200 ms.
- **Soát bằng mắt:** người duyệt xem lại toàn bộ cảnh ở tốc độ 0,5 lần và đánh dấu mọi chỗ vật "tự di chuyển" vô lý.
- **Đạt khi:** 0 lỗi tự động loại "tức thời" và "xuất hiện, biến mất", và người duyệt không đánh dấu lỗi nặng.

### G4. Cổng thị giác
- **Ảnh chụp** ở các mốc 10%, 30%, 50%, 70% và 90% thời lượng, kèm ảnh ở mỗi điểm đổi cú máy.
- **Tiêu chí đạt:** (1) chữ không tràn mép và không bị che; (2) độ tương phản chữ nền đạt mức đọc rõ trên màn hình điện thoại; (3) nằm trong vùng an toàn; (4) bảng màu đúng thương hiệu; (5) không lộ mặt sau, không lộ cạnh vật; (6) dấu tiếng Việt rõ ở cỡ nhỏ nhất; (7) vùng đặt sub phía dưới không bị vật chính che.

### G5. Cổng hiệu năng
- **Tiêu chí đạt:** (1) dựng trong ngân sách: không quá 10 giây thực cho mỗi giây video trên máy hiện có; (2) đỉnh RAM không vượt 6 GB; (3) tệp ra không vượt 4 MB mỗi giây video ở chất lượng sản xuất; (4) không phụ thuộc GPU rời.

### G6. Cổng duyệt của Founder (chấm điểm)
Thang 1 đến 5 cho 8 tiêu chí; mẫu đạt khi trung bình từ 4,0 và không tiêu chí nào dưới 3.
| Tiêu chí | Câu hỏi |
|---|---|
| Chất liệu và nhất quán | Có cùng một thế giới origami không |
| Chuyển động tự nhiên | Vật chuyển động có "nặng", có quán tính không |
| Lia máy | Cú máy có chủ đích, mượt, không gây chóng mặt không |
| Nhịp | Cảnh có "thở", không trống và không dồn không |
| Bám lời | Hình trùng khớp ý lời đọc không |
| Dễ đọc | Chữ và số rõ trên điện thoại không |
| Độc đáo | Có cảm giác cao cấp, không "mẫu có sẵn" không |
| Sẵn sàng sản xuất | Có thể dùng cho nhiều bài khác nhau không |

### G7. Cổng đưa vào sản xuất
- **Tiêu chí đạt:** (1) mẫu đã chạy tốt với ba nội dung khác nhau ở bước 9; (2) hợp đồng biến được ghi chép; (3) danh mục mẫu cập nhật; (4) có hướng dẫn một trang cho người lập kịch bản biết khi nào dùng mẫu này; (5) có kế hoạch hồi quy: mỗi lần nâng cấp HyperFrames hoặc đổi bảng màu chạy lại G2 đến G5.
- **Sau khi vào sản xuất:** theo dõi 3 video đầu, thu thập lỗi, sửa trong bản vá nhỏ.

### Bảng tóm tắt cổng
| Cổng | Loại | Người chịu trách nhiệm | Đầu ra |
|---|---|---|---|
| G0 | Kiểm tài liệu | Người làm mẫu, người duyệt tài sản | Danh mục tài sản sạch |
| G1 | Duyệt thiết kế | Founder hoặc người được ủy quyền | Bảng nhịp được ký |
| G2 | Tự động | Công cụ, người làm đọc báo cáo | Báo cáo kỹ thuật |
| G3 | Tự động cộng soát mắt | Công cụ, người duyệt chuyển động | Báo cáo chuyển động |
| G4 | Tự động cộng soát mắt | Người duyệt thị giác | Bộ ảnh chụp có ghi chú |
| G5 | Đo đạc | Người phụ trách hạ tầng | Báo cáo hiệu năng |
| G6 | Chấm điểm | Founder | Phiếu chấm điểm |
| G7 | Tổng hợp | Chủ dự án | Mẫu được ghi vào danh mục |

---

## 8. Cách đo hiệu quả sau khi áp dụng
- **Tín dụng Flow trên mỗi video:** so sánh với lô 15 video hiện tại; mục tiêu giảm ít nhất 65%.
- **Thời gian dựng một video:** ghi giờ dựng từng cảnh; mục tiêu không tăng quá 20% dù nhiều chuyển động hơn.
- **Tỉ lệ cảnh qua G3 ngay lần đầu:** mục tiêu từ 70% ở mẫu thứ ba trở đi.
- **Điểm G6 trung bình toàn lô.**
- **Số lần phải tạo lại vì lỗi chuyển động:** mục tiêu giảm một nửa so với Flow.

---

## 9. Lộ trình, nguồn lực và rủi ro (ước lượng, cần hiệu chỉnh)

### 9.1 Các giai đoạn
| Giai đoạn | Việc | Ước lượng | Cổng kết thúc |
|---|---|---|---|
| 0. Thử nghiệm đầu cuối | Làm trọn một mẫu (đề xuất Mẫu E vì ít nhân vật) từ tờ yêu cầu đến G6, đo ngân sách dựng thật, chốt lại ngưỡng cổng | 1 tuần | G0 đến G6 cho Mẫu E |
| 1. Công cụ cổng | Xây các kiểm tra tự động của G3 và mở rộng G2, G4, G5 | 1 tuần, song song giai đoạn 0 | G3 chạy được trên mẫu thật |
| 2. Mẫu cơ bản | Mẫu A, B (chuyển động chủ yếu là vật thẻ và xu) | 2 tuần | G0 đến G6 |
| 3. Mẫu trung bình | Mẫu C, D (xếp chồng và lật trang) | 2 tuần | G0 đến G6 |
| 4. Mẫu khó | Mẫu F (nhân vật origami) | 2 tuần | G0 đến G6 |
| 5. Nối vào sản xuất | Nối hợp đồng biến vào bộ lập kế hoạch, quy tắc chọn mẫu, giảm Flow còn tối đa 2 clip | 1 tuần | G7 cho cả sáu mẫu |
| 6. Thí điểm lô | Làm 5 video thật bằng mẫu mới, đo theo mục 8 | 1 tuần | Báo cáo hiệu quả |

Tổng khoảng 8 đến 10 tuần với một người làm chính và một người duyệt. Đây là ước lượng thô, cần hiệu chỉnh sau giai đoạn 0.

### 9.2 Ngân sách dựng
Một video 100 giây khoảng 14 phút dựng ở chất lượng sản xuất (8,4 giây thực cho mỗi giây video). Mỗi mẫu cần thử ba nội dung và dựng nhiều vòng sửa: khoảng 10 vòng × 3 nội dung × 10 giây × 8,4 giây ≈ 42 phút dựng thuần cho mỗi mẫu, chưa kể thời gian người xem lại. Bản nháp chất lượng thấp dùng trong lúc sửa để tiết kiệm thời gian.

### 9.3 Rủi ro và cách giảm
| Rủi ro | Mức | Cách giảm |
|---|---|---|
| Không có động cơ vật lý, "vật lý thật" chỉ là mô phỏng bằng chuyển động thiết kế | Trung bình | Nói rõ kỳ vọng; thiết kế bảng nhịp thật kỹ; kiểm bằng G3 |
| Dựng chậm trên máy hiện có (CPU, 8 GB RAM) | Cao | Giới hạn số phần tử từng mẫu; bản nháp thấp; cân nhắc máy dựng khoẻ hơn nếu giai đoạn 0 chạy chậm hơn dự tính |
| Chuyển cảnh shader chưa dùng được | Thấp | Chỉ thiết kế bằng 8 kiểu GSAP và chuyển động vật thể |
| Chất lượng tài sản origami không đồng đều | Trung bình | Một người chịu trách nhiệm phong cách; bộ tài sản chung dùng cho cả 6 mẫu |
| Nhân vật origami (Mẫu F) khó và dễ trông "cứng" | Cao | Làm sau cùng; bắt đầu với 2 tư thế và nội suy; cho phép bỏ Mẫu F nếu G6 không đạt, dùng Mẫu B thay |
| Founder duyệt chậm làm kẹt cổng | Trung bình | Thời hạn phản hồi cố định; gom duyệt theo lô nhỏ |
| Lỗi cũ của Flow vẫn còn ở hook và cảnh kết | Trung bình | Sửa lời nhắc và đo thử ở nhánh riêng; Flow chỉ dùng cảnh khung rộng, không cảnh nhiều hành động |

### 9.4 Câu hỏi cần Founder quyết
1. Có đồng ý thứ tự làm bắt đầu bằng Mẫu E để thử nghiệm đầu cuối không.
2. Khung 9:16 làm cùng lúc hay sau khi 16:9 xong (đề xuất: sau).
3. Giữ tối đa 2 clip Flow hay đi xa hơn tới 0 clip Flow ở những bài không cần cảnh người thật.
4. Ai là người duyệt thay khi Founder bận, và thời hạn phản hồi chấp nhận được.
5. Có chấp nhận đổi máy dựng khoẻ hơn nếu đo thật cho thấy ngân sách mục 9.2 không đạt.

---

## Phụ lục 1. Gán 15 bài vào 6 mẫu (đề xuất ban đầu)
| Bài | Chủ đề | Mẫu chính | Lý do |
|---|---|---|---|
| 01 | Sản phẩm tốt nhưng thiếu khách mới | B | Phễu bán hàng, khách đi qua các bước |
| 02 | Báo giá xong khách im lặng, mất đơn | B | Thẻ báo giá kẹt ở một trạm |
| 03 | Gọi càng nhiều khách càng cúp máy | F | Đội gọi, chuyền việc, phản ứng khách |
| 04 | Quảng cáo có lượt xem nhưng không ra đơn | E | Cột lượt xem cao, cột đơn hàng thấp |
| 06 | Khách mới bỏ quên doanh thu từ khách cũ | D | Trước (bỏ quên) và sau (chăm sóc) |
| 07 | Doanh thu tăng nhưng lợi nhuận giảm | E | Hai đường giao nhau |
| 08 | Bán được hàng nhưng thiếu tiền trả lương | A | Dòng tiền cạn |
| 09 | Không vay được vốn | A | Hồ chứa không đầy để đạt điều kiện vay |
| 10 | Giảm giá bán nhiều có thể lỗ nặng | A | Lát cắt chi phí, tiền chảy ra |
| 11 | Kho đầy hàng nhưng thiếu món khách cần | C | Chồng hàng che món cần tìm |
| 12 | Đội xe chạy liên tục, lợi nhuận thấp | C | Xe chạy quãng đường rỗng |
| 13 | Giao hàng trễ, khách rời đi | B | Quy trình kẹt ở một trạm |
| 14 | Giám đốc nghỉ một ngày, công ty rối loạn | F | Thẻ việc dồn khi người ra quyết định vắng |
| 17 | Báo cáo nhiều nhưng sếp không biết khoẻ hay yếu | E | Thành phố dữ liệu nhiều thẻ KPI |
| 18 | Nhân viên quay lại Excel sau khi mua phần mềm | D | Bàn cũ và bàn mới |

Số bài mỗi mẫu: A 3, B 3, C 2, D 2, E 3, F 2.

## Phụ lục 2. Mẫu phiếu chấm G6 (điền tay)
| Tiêu chí | Điểm 1–5 | Ghi chú sửa |
|---|---|---|
| Chất liệu và nhất quán | | |
| Chuyển động tự nhiên | | |
| Lia máy | | |
| Nhịp | | |
| Bám lời | | |
| Dễ đọc | | |
| Độc đáo | | |
| Sẵn sàng sản xuất | | |
| Trung bình | | |
| Kết luận | Đạt / Sửa / Loại | |

## Phụ lục 3. Danh sách việc kiểm tay trước khi nộp cổng
- Mỗi vật có nguồn vào và đích ra, đã đối chiếu với bảng nhịp.
- Không vật nào "tự bay" khi xem ở tốc độ 0,5 lần.
- Chữ có dấu tiếng Việt rõ ở cỡ nhỏ nhất.
- Mặt sau của vật lật không lộ.
- Camera không vượt giới hạn tốc độ.
- Thử đủ ba nội dung, kể cả chữ dài nhất.
- Báo cáo G2 đến G5 đính kèm, phiếu G6 đã ký.
