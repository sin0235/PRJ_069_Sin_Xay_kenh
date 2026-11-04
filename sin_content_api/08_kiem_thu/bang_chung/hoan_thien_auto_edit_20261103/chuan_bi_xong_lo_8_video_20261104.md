# Bàn giao lô tám video trước bước duyệt

## Trạng thái

`AWAITING_APPROVAL` — chưa tạo cảnh, chưa gửi render, chưa nhận lời duyệt.

- Dự án mới: `61340dab-a666-4fa2-9bed-ac92520d125b`.
- Nguồn gốc: `f28532a9-3e88-536d-9e4a-d3d8d4acb0fc`, `UPLOAD`, không có parent, 8.428.283.732 byte; cùng SHA-256 nguồn DJI đã kiểm tra.
- Đã nhận dạng tiếng riêng cho cả tám nội dung qua 9Router, không dùng phần chồng cửa sổ làm lời lặp.
- Giữ đủ hook và kết luận: đặc biệt “Tăng giá rồi”, hook quảng cáo và “Có doanh thu mà không có tiền nhập hàng”.
- Đối chiếu lại câu đọc sửa của nội dung 7, giữ một bản trọn ý và bỏ lời nhắc đọc lại. Các đề xuất cắt không có bằng chứng lặp đã bị bỏ.
- Dự kiến mỗi clip dài 92,8–116,4 giây sau rút khoảng nghỉ/đọc lại. Đây là thời lượng trước render, không thay bằng chứng MP4.
- Có 74 cảnh: 48 HyperFrames, 26 Flow; Flow nguồn cố định 10 giây. Karaoke/style và checklist tích lũy giữ như đã chốt.

## Gói đã đóng băng

- `goi_duyet_8_video_20261104.json` và `.sha256` trong thư mục bằng chứng này.
- SHA-256: `6a21d1cd5f6531741addcc014d1d09d44a9cd9bce475753831f372f5f6aa14d4`.
- Bản runtime cùng nội dung: `ha_tang/chay_dev_local/runtime/goi_duyet_8_video_20261104.json`.
- Bảng đọc nhanh: `ha_tang/chay_dev_local/ban_duyet_lo_8_video_20261104.md`.
- Bộ chạy: `ha_tang/chay_dev_local/chay_lo_auto_edit_da_duyet.py`.

Chạy không cờ chỉ kiểm tra; đã chạy thực tế, trả `clips=8`, `visuals=74`, `flow=26`, `approved=false` và đúng SHA-256. Không có receipt duyệt hay job lô được tạo. Gói phiên bản 2 đã lọc mã màu và tên style tiếng Anh khỏi prompt Flow; bản trước lọc chỉ giữ trong runtime để đối soát, chưa từng gửi tạo cảnh.

## Sau khi người dùng nói duyệt

1. Nạp mã mới vào API/worker khi các lượt khác đã rảnh. Không dừng worker đang xử lý việc khác; giữ đúng hồ sơ Flow đã đăng nhập.
2. Kiểm tra nguồn, quyền dự án, hash gói và trạng thái Flow; phần nặng tiếp tục dùng GitHub Actions với concurrency 1.
3. Chạy bộ thực thi với `--duyet`. Receipt lưu ID từng cảnh và từng parent; không đổi khóa để tạo lại Flow khi trạng thái chưa rõ.
4. Gửi cửa sổ nguồn thô cần dựng thay vì tải lại cả 8 GB cho mỗi clip. Kiểm tra gói hình copy và dịch đồng bộ mốc hình/tiếng; không dùng MP4 đã edit làm nguồn.
5. Xuất từng nội dung thành một parent riêng. Video đã hoàn thành được đăng vào Auto Edit và giữ khi clip sau gián đoạn. Kết thúc cần đúng tám MP4, tải Range đầu/cuối được; hình ảnh để người dùng nghiệm thu.

## Hạn chế còn ghi rõ

- Còn một khoảng người nói 18,66 giây chưa có diễn họa trong nội dung 6; đã ghi trong bảng duyệt, không coi đó là kiểm định thẩm mỹ đạt.
- Mốc karaoke được căn từ ASR gốc và bản nhận dạng 9Router; các từ nghe mơ hồ vẫn cần rà khi nghiệm thu, không tự bịa lời.
- Đoạn mở đầu nội dung thứ 9 bị ngắt giữa câu không thuộc lô.
- Bản mẫu 42 giây trước đó vẫn là bản cũ; lô này dùng nguồn gốc và bản căn mới.
- Kiểm tra trước đóng gói: hồ sơ Google Flow báo `READY`, dự án mới có 0 job. Một lượt AI_VIDEO khác còn RUNNING và một remote task còn active, nên chưa restart worker trong bước chuẩn bị.

## Kiểm thử mã liên quan

Đã có kiểm thử đỏ/xanh cho cắt câu đọc lại và phụ đề cùng mốc, cửa sổ nguồn và offset hình/tiếng, tải tiếp khi gateway 502/503/504, giữ cảnh hợp lệ khi lượt sửa LLM cuối sai schema, và cổng duyệt không phát sinh tác vụ ở chế độ mặc định.

- Nhóm hồi quy gồm dựng dài, storyboard, cắt đọc lại, worker từ xa, cửa sổ nguồn và cổng duyệt: `152 passed, 1 warning in 104.11s`.
- Sau bổ sung bộ lọc prompt Flow cho Auto Edit: `test_storyboard_nhieu_nhip.py` có `17 passed in 2.40s`; ca mới đã thất bại trước sửa vì prompt còn mã màu.
- Chưa chạy tạo cảnh/render cả lô theo đúng mốc dừng người dùng yêu cầu. Chưa nghiệm thu hình ảnh.
