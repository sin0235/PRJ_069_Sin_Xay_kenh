# Đối soát dữ liệu dựng lại v4

## Kết quả

Không dùng cache chẩn đoán cũ để bổ sung transcript hoặc word ID cho biên bản v4. Chưa sửa biên bản và chưa gửi lại yêu cầu Flow.

- Job cha: `666a7727-3e03-4812-ad88-8451cda61e0a`.
- Biên bản: `9df61132-8b4d-4ea6-9236-39487741e155`.
- Phụ đề trong biên bản có 211 từ; cache chẩn đoán có 212 từ. Ngoài khác dấu câu, cache thêm một từ và khác nội dung tại một mốc. Không thể coi hai transcript là cùng một bản.
- Phép đảo thời gian phụ đề gặp đúng biên khoảng bị cắt. Thời gian nguồn đã bị gộp ở biên đó không thể khôi phục chính xác chỉ từ thời gian đầu ra.

## Đối chiếu trực tiếp request của các cảnh

Đọc `AIGenerationJob.request_payload_json.parameters` trong cơ sở dữ liệu, chỉ xuất tên trường và mốc từ, không xuất thông tin đăng nhập.

| Cảnh | Trạng thái | Dữ liệu neo có trong request |
|---|---|---|
| `611bf8fe-8c30-4380-b5df-0f00605b291a` | SUCCEEDED | `stt_part1_01_0080` đến `stt_part1_01_0096`, 15 mốc narration |
| `e8696e28-7c0b-45db-8453-2e8f831731bb` | SUCCEEDED | Chỉ có target_clip_id, không có neo từ |
| `3dbeb4f7-c9cd-4d88-9d02-96da45daa5de` | SUCCEEDED | `stt_part1_01_0111` đến `stt_part1_01_0127`, 16 mốc narration |
| `e995422e-b0d8-41ff-a471-40f38e450d16` | FAILED | Chỉ có target_clip_id, không có neo từ |

Hai request HyperFrames cũng không chứa toàn bộ transcript hoặc toàn bộ visual brief ban đầu. Không đủ bằng chứng để tái tạo đầy đủ kế hoạch cũ bằng cách đánh lại số thứ tự từ phụ đề.

## Bước tiếp theo

Lượt dựng cải thiện phải dùng transcript từ video quay gốc và ghi đầy đủ words, plan, visual_briefs ngay khi lập kế hoạch. Có thể tái sử dụng cảnh đã có khi xác thực nội dung và thời gian phù hợp; không dùng MP4 đã edit làm đầu vào. Trước khi tạo thêm Flow cần xác nhận tài khoản vì Founder vừa báo có thể mở nhầm hồ sơ. Hồ sơ đã quan sát đăng nhập `tranthaomy235@gmail.com`; chưa được xác nhận là tài khoản cần dùng.

Chưa nghiệm thu chất lượng v4, chưa chạy xử lý toàn bộ nguồn 8 GB.

## Kiểm tra ghép alpha bằng cảnh thật

- Chạy `python -m pytest tests/test_overlay_dung_moc.py -q` tại `sin_content_api`: 6 test đạt trong 8,07 giây.
- Lấy 0,5 giây ở mốc 2 giây từ cảnh checklist HyperFrames `9bed1256-462b-4a84-899d-70f4785f89ed`, thu nhỏ 360×640 trước khi ghép. Đây là fixture nhẹ, không dựng lại video nguồn trên local.
- Gọi renderer với `pad_color=0B1F2A`, xuất `checklist_nen_giay_360.mp4` và ảnh `checklist_nen_giay_360.png` trong cùng thư mục bằng chứng.
- Quan sát ảnh: nền đã chuyển sang màu được chọn, không còn đen mặc định. Tuy nhiên cảnh thật vẫn không đạt: thẻ và chữ tối, có chữ lớn phía sau nhãn, phần lớn khung trống. Sửa nền ghép riêng lẻ chưa giải quyết chất lượng nội dung hoạt họa.
- Việc tiếp theo thuộc scene/layout: kiểm tra opacity, các lớp chữ và vùng nội dung thực của checklist, rồi dựng proof animation trước khi xuất lại toàn clip. Không dùng kết quả 6 test để tuyên bố checklist đã đẹp hoặc video đạt nghiệm thu.

## Đối chiếu template hiện tại với cảnh đã xuất

Đọc đúng `ui_scene`, `narration`, `narration_word_times` và thời lượng từ request checklist ở trên. Tạo HTML bằng `_diagram_html(diagram_payload(...), '9:16', True)`, mở qua Playwright CLI và gọi `setT(2.5)` sau khi font sẵn sàng. Chụp với nền trong suốt ở tỷ lệ 360×640: `checklist_template_hien_tai_360.png`.

Quan sát: template hiện tại cho thẻ giấy sáng, nhãn “giá vốn” rõ và chỉ một mục đang hiện, gạch vàng cùng dấu kiểm. Khác ảnh trích từ MOV cũ. Không sửa template chỉ dựa vào MOV cũ. Mốc 2,0 giây trước đó có thể nằm trong pha vào của một mục; ảnh tĩnh riêng lẻ không chứng minh opacity sai trong cả cảnh.

Chạy `python -m pytest tests/test_checklist_doc_ro.py -q`: 3 test đạt trong 1,02 giây. Đây là kiểm tra template, font và hợp đồng planner; chưa phải kiểm tra MOV mới qua HyperFrames hoặc video E2E. Canvas alpha vẫn có nhiều vùng trống bên dưới thẻ; cần xem bố cục chèn thực tế do LLM chọn trước khi nghiệm thu.

## Render HyperFrames thật và lỗi camera được tái hiện

- Actions run `41656504477`, task `6dd7aa09-393a-4f81-b503-d7fff8b95d5f`: trả MOV 5 giây, 1080×1920, 30 fps, ProRes `yuva444p12le`, có alpha. Chi tiết tại `checklist_hyperframes_moi.json`.
- Ba khung 0,8 / 2,5 / 4,3 giây: `checklist_moi_dau.png`, `checklist_moi_giua.png`, `checklist_moi_cuoi.png`. Nhãn thay từ giá bán sang giá vốn và đóng gói. Thẻ sáng nhưng khung cuối bị camera đẩy ra mép trái.
- Thêm test `test_the_checklist_alpha_khong_bi_camera_day_ra_khoi_canvas`: thất bại trước sửa, cho thấy cả cam và rig có transform dịch/phóng. Sửa riêng checklist alpha dọc để giữ cam/rig ổn định; hàm sceneChecklist vẫn tạo animation vào thẻ, nét kiểm và gạch nhấn.
- Sau sửa: `python -m pytest tests/test_checklist_doc_ro.py tests/test_khoi_hyperframes.py -q`: 33 test đạt trong 2,48 giây. Chưa render MOV bằng bản sửa camera này; MOV và ba ảnh ở trên là bằng chứng lỗi trước sửa.
- Đo âm lượng v4 trên Actions, `am_luong_v4.json`: integrated -14,67 LUFS, true peak -2,65 dBTP, LRA 3,9 LU. Đạt ngưỡng đo đã đặt; chưa thay cho việc nghe kiểm toàn clip.
