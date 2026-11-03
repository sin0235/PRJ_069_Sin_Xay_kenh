# Đối chiếu mẫu Auto Edit và bản E2E

Ngày kiểm tra: 03/11/2026. Đây là quan sát hình ảnh từ montage và chuỗi khung 5 fps; chưa nghe toàn bộ audio hoặc xem liên tục toàn bộ hai mẫu. Không dùng tài liệu này để nhận nghiệm thu M0 đã hoàn tất.

## Tư liệu

- Mẫu 1: `Z:/01_du_an/PRJ_069_Sin_Xay_kenh/mau1.mp4`, 123,74 giây, 1080×1920, 30 fps, có audio.
- Mẫu 2: `Z:/01_du_an/PRJ_069_Sin_Xay_kenh/mau2.mp4`, 63,09 giây, 1080×1920, 30 fps, có audio.
- Bằng chứng: `sin_content_api/08_kiem_thu/bang_chung/hoan_thien_auto_edit_20261103/`. Montage tổng thể lấy 1 khung/8 giây cho mẫu 1 và 1 khung/4 giây cho mẫu 2; mốc trong montage là vùng khảo sát, không phải điểm cắt chính xác.

## Quan sát có bằng chứng

| Mẫu/vùng | Quan sát | Áp dụng vào Auto Edit |
|---|---|---|
| Mẫu 1, mở đầu trong montage | Chữ hook lớn hai màu, người nói chiếm phần chính | Hook ít chữ, rõ, giữ người nói; không dùng thanh đen nhỏ |
| Mẫu 1, 7–9 giây, chuỗi 5 fps | Người nói liên tục, sub thay theo cụm; không phải mọi câu đều có B-roll | Không bơm hiệu ứng ở mọi từ chỉ để tăng số lượng |
| Mẫu 1, 10–12 giây, chuỗi 5 fps | Đồ họa thay toàn khung; các thẻ/điện thoại/chỉ số xuất hiện thêm theo trình tự; sub nằm riêng ở dưới | Thông tin cần đọc dùng không gian đủ lớn và vào theo nhịp, thay vì thu cả canvas vào góc |
| Mẫu 1, các vùng giữa trong montage | Có cảnh màn hình thực, cảnh người nói và hình bổ trợ phía trên người nói | LLM được chọn full-frame hoặc bố cục song song theo nội dung |
| Mẫu 1, vùng kết trong montage | CTA/chữ khóa lớn và nền minh họa phía sau người nói | Kết có hành động rõ, không lấy nhãn hộp chung cho mọi clip |
| Mẫu 2, 15–17 giây, chuỗi 5 fps | Nhãn mục phía trên, số thứ tự lớn; karaoke nhấn màu từng từ/cụm; có thanh tiến trình chương | Nhãn chỉ ghi ý chính ngắn; caption và nhãn là hai lớp độc lập |
| Mẫu 2, 17–19 giây, chuỗi 5 fps | Chuyển từ người nói sang giao diện lớn: thẻ website hiện trước, nhãn sự kiện màu vàng hiện sau; nền đậm tăng tương phản | Animation có quan hệ nội dung, đối tượng lần lượt xuất hiện; không fade cả bảng thành mờ trong thời gian đọc |
| Mẫu 2, các vùng giữa/cuối trong montage | Quy trình máy chủ/Meta, hai nhóm khách hàng, landing page, checklist mục tiêu | Ưu tiên sơ đồ được neo lời bằng HyperFrames; Flow dành cho cảnh vật/nhân vật giấy cần chuyển động tự do |

Các quan sát trên mô tả cách dựng, không sao chép brand/màu/văn bản của mẫu. Auto Edit vẫn theo giấy gấp BAHA, có thể 2D/3D.

## Khác biệt của bản 66 giây hiện tại

1. Checklist bị thu vào góc, nền/đường viền nhạt và nội dung nhỏ. Ảnh Founder gửi xác nhận không đọc rõ.
2. Renderer scale overlay nhưng không dời PTS tới thời điểm chèn. Cảnh vài giây bị chạy hết trước khi xuất hiện muộn trên timeline, sau đó giữ frame cuối. Frame cuối của HyperFrames có fade nên nhìn mờ và không động.
3. Các cảnh Flow cũ là kính/kim loại, lệch chất liệu giấy yêu cầu. Planner mới đã sửa style nhưng bản video đó chưa được tạo lại theo snapshot mới.
4. Script E2E chia nhịp thủ công; chưa chứng minh LLM/pipeline sản phẩm lập đầy đủ nhịp cho cùng clip.

## Kiểm chứng đã thực hiện cho lỗi timestamp

Test: `sin_content_api/tests/test_overlay_dung_moc.py`.

- Nguồn 6 giây, 160×284, 10 fps; overlay 2 giây gồm đỏ rồi xanh, xuất hiện ở giây 3.
- Trước sửa: tại 3,3 giây đọc pixel xanh `00 00 ff`, trái kỳ vọng đỏ. Đây là bằng chứng lỗi thời gian thay vì thiếu animation trong asset.
- Sau sửa: 2 case đạt (trim nguồn 0 và 500 ms); trước cue đen, đầu cue đỏ, sau đó xanh, hết cue trở lại đen.
- Sửa tại `VideoProcessor.render_timeline_document`: trim nguồn, dịch PTS tới start, ngừng lặp frame cuối khi EOF và dùng cửa sổ kết thúc loại trừ.
- Chỉ chạy fixture nhỏ khoảng 3 giây thời gian xử lý; không render full HD hoặc tải model local.

## Việc tiếp theo theo kế hoạch

- Xem/nghe phần còn lại và chốt storyboard nguồn bằng LLM: M0 còn mở.
- Kiểm PIP trim, nhiều overlay và alpha trên runner; xuất đoạn proof có checklist xuất hiện muộn.
- Xử lý bounds và kích thước chữ checklist trong không gian hiển thị, xem ở 360×640. Không chỉ tăng cỡ enum `small` thành `large` mà giữ cả khoảng trống canvas.
- M1 chỉ đạt khi đoạn proof thật đọc rõ và chuyển động đúng cue; test timestamp đạt chưa đủ.
