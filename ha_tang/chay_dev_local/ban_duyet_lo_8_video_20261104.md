# Bản chuẩn bị 8 video để duyệt chạy cả lô

Dự án mới: https://nhap-xaykenh-prj069.bahagroup.vn/auto-edit?project_id=61340dab-a666-4fa2-9bed-ac92520d125b

**Trạng thái: chờ người dùng duyệt; chưa tạo cảnh Flow/HyperFrames hoặc render cả lô.**

| Video | Nội dung | Nguồn (giây) | Dự kiến sau cắt nghỉ/đọc lại | HyperFrames | Flow |
|---|---|---|---|---|---|
| kb_01 | Đơn nhiều nhưng tiền thực nhận đâu? | 0.00–96.54 | 92.8 giây | 8 | 3 |
| kb_02 | Tăng giá rồi, sao tiền lời lại giảm? | 97.40–203.56 | 94.5 giây | 9 | 0 |
| kb_03 | Đơn càng rẻ, tiền lời càng dễ biến mất | 205.27–311.07 | 97.7 giây | 5 | 3 |
| kb_04 | Có đơn quảng cáo không có nghĩa có lời | 311.47–411.87 | 98.2 giây | 3 | 6 |
| kb_05 | Có doanh thu mà không có tiền nhập hàng | 413.43–517.05 | 98.3 giây | 7 | 5 |
| kb_06 | Rời sàn tránh phí, khách có theo không? | 521.16–626.13 | 102.8 giây | 5 | 3 |
| kb_07 | Giảm mười nghìn có khi mất nửa lãi | 627.67–754.09 | 93.1 giây | 6 | 2 |
| kb_08 | Món bán chạy nhất có khi lại đang kéo shop lỗ | 755.45–885.00 | 116.4 giây | 5 | 4 |

Tổng 74 cảnh dự kiến; 26 lượt tạo nguồn Flow 10 giây. LLM đã lập kế hoạch, chưa phát sinh tạo cảnh.

Giữ karaoke và style giấy hiện tại. Checklist toàn khung tích lũy từ trên xuống; overlay giữ alpha khi phù hợp. LLM chọn bố cục cuối theo cảnh thật sau khi tạo.

Đoạn thứ 9 bị ngắt giữa câu không nằm trong lô. Mỗi video xuất thành một tác vụ riêng để giữ kết quả đã xong nếu lượt sau gián đoạn.

## Các đoạn nói lại được đánh dấu

- kb_06: 602.43–603.29 giây: Lặp cụm “cái chi phí”.
- kb_07: 644.93–652.41 giây: Lời nhắc đọc lại; giữ bản trước đó đủ ý, gồm giá vốn, chi phí, số còn lại và câu khách hỏi.
- kb_07: 672.77–688.21 giây: Bỏ bản đọc vấp và phần nhắc lại; giữ phiên bản sau trọn ý, mượt hơn.
- kb_08: 813.12–814.06 giây: Cụm hậu trường “Nhắc lại nhé”.
- kb_08: 814.12–815.44 giây: Lặp lại ý món tạo cảm giác bận rộn.
- kb_08: 829.54–832.70 giây: Lặp lại ý tâm lý dễ hiểu.

## Ghi chú cần giữ khi nghiệm thu

- kb_01: w000025–w000026: Cụm “chứa chừa” nghe không chắc; cần nghe lại.
- kb_02: Cụm w000357–w000362 nghe không chắc; không cắt.
- kb_04: Cụm “mét ví dụ thế” nghe không chắc; cần nghe lại.
- kb_06: Cụm w001815–w001816 và w001834–w001838 nghe không chắc; không cắt.
- kb_06: còn khoảng hình người nói dài 18.7 giây; chưa phải nghiệm thu hình ảnh.

## Chạy sau duyệt

Mặc định công cụ chỉ kiểm tra. Chỉ dùng --duyet sau khi người dùng đã nói duyệt chạy cả lô.

    python ha_tang/chay_dev_local/chay_lo_auto_edit_da_duyet.py
    python ha_tang/chay_dev_local/chay_lo_auto_edit_da_duyet.py --duyet

Trước khi chạy cần nạp mã mới vào API/worker khi các lượt khác đã rảnh; giữ nguyên hồ sơ Flow và không dừng tác vụ đang hoạt động. Không render nặng local.

SHA-256 gói duyệt: 6a21d1cd5f6531741addcc014d1d09d44a9cd9bce475753831f372f5f6aa14d4
