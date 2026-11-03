# Nối cảnh khối HyperFrames vào Auto Edit

## Phạm vi đã kiểm tra

Thư viện hiện có 38 `DIAGRAM_LAYOUTS`, trong đó sáu `BLOCK_LAYOUTS`: KINETIC_TITLE, MARK_PHRASE, WORD_SWAP, PILE_UP, STAT_RING và CHART_STORY. Auto Edit lấy schema UiScene dùng chung; không tạo engine hoặc bộ cảnh riêng.

Lỗi ở `tao_y_tuong_dien_hoa_flow.diagram_window`: gọi min/max trên danh sách sự kiện rỗng. Các cảnh khối có `diagram.on={}` theo hợp đồng, nên đều bị loại khỏi kết quả. Bản sửa dùng toàn bộ khoảng từ mà LLM đã chọn cho các cảnh khối, giữ giới hạn thời lượng tối đa sáu giây và kiểm tra schema chung. Các sơ đồ có sự kiện vẫn dùng mốc sự kiện như trước.

## Kiểm thử

- Sáu test tham số cho sáu layout đều thất bại trước sửa và đạt sau sửa.
- Bộ rộng: 127 test đạt, một fixture hết câu trả lời giả vì planner hiện thử bốn lượt nhưng fixture chỉ cấp ba. Cập nhật đúng fixture thành bốn và thêm kiểm tra số lượt; không giảm validation hoặc bỏ test lỗi.
- Chạy lại nhóm cảnh khối, fixture vừa sửa, storyboard nhiều nhịp và checklist: 22 test đạt trong 4,62 giây. Các test này không phải E2E với LLM thật.
- Commit thực thi: `4598ded`.

## LLM thật

Gọi LLMClient cấu hình 9Router thật qua planner Auto Edit. Đầu vào là transcript/plan chẩn đoán lưu từ nguồn quay gốc tại cache `6323d72c-4491-4ed7-9338-fe30973a9ae8`; đây không phải transcript v4 được phục hồi. Không gửi yêu cầu tạo cảnh Flow, không dùng video đã edit làm nguồn. Tạm khai báo Flow không khả dụng cho phép thử độc lập trong khi chờ xác nhận tài khoản.

Kết quả tại `planner_canh_khoi_that.json`: ba visual hợp lệ gồm KINETIC_TITLE, CHECKLIST, KINETIC_TITLE. Hai cảnh khối không có diagram.on vẫn được giữ và có target_start_word_id/target_end_word_id. Kế hoạch còn cần rà soát; cờ và lý do review bao gồm dữ liệu kế thừa từ cache đầu vào. Không diễn giải cờ này thành chỉ số chất lượng của riêng lượt LLM mới.

Chưa render E2E ba cảnh vừa chọn hoặc ghép thành video nghiệm thu. Phép thử chỉ chứng minh LLM thật chọn được cảnh khối và validator Auto Edit tiếp nhận chúng.

## Đường render cảnh khối đầy đủ

Rà tiếp thấy `render_hyperframes` trước đây luôn gọi `hyperframes_composition_html` từ ui_sim. Với sáu BLOCK_LAYOUTS, diagram_scene chỉ có `sceneBlockCard`, ghi rõ là bản dự phòng, chưa dùng animation hf_blocks. Do đó việc planner nhận layout mới chưa đủ chứng minh renderer dùng cảnh mới.

Đã sửa renderer dùng `hf_project.build_project` cho đúng BLOCK_LAYOUTS, không bật chuyển cảnh giữa các shot vì đây là một cảnh rời. Các layout khác giữ đường render hiện hữu. Bổ sung tùy chọn nền trong suốt vào build_project để giữ yêu cầu xuất MOV alpha; mặc định nền đục của caller AI Video không thay đổi. Đây là nền của project, không phải thuật toán tách nền các vật thể hoặc bỏ mọi nền riêng bên trong từng khối.

Test đường render thất bại trước sửa vì không gọi build_project, đạt sau sửa. Chạy nhóm Auto Edit cảnh khối, thư viện HyperFrames và checklist: 42 test đạt trong 4,46 giây. Có test tạo project thật ở cả nền đục và nền trong suốt, xác nhận native_scenes có KINETIC_TITLE và legacy_scenes rỗng. CLI render được giả lập trong test định tuyến; chưa có MOV thật của đường định tuyến mới này.
