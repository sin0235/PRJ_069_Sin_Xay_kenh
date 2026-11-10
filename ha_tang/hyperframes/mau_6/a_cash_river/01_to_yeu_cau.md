# Tờ yêu cầu: Cảnh A - CASH_RIVER (M1)

- **Tên layout:** `CASH_RIVER`
- **Mã khối:** `cash-river.html`
- **Thời lượng:** 10.0 giây (300 khung hình @ 30 fps)
- **Tập bài áp dụng:** Bài 08, 09, 10 và Kịch bản Khám sức khỏe doanh nghiệp BAHA (phần chi phí và thất thoát).
- **Ý chính một câu:** Dòng sông giấy origami thể hiện dòng tiền vào hội tụ từ các nhánh, chia sang các khoản chi, xoáy rò rỉ tại cống xả làm tụt mực nước quỹ dự trữ và con số thất thoát giáng xuống.

## 1. Danh sách vật thể chuyển động & giới hạn
- Đồng xu giấy vàng origami: 12 đồng xu (`data-obj="coin-1"` đến `coin-12"`, `data-kind="prop"`, `data-src="offscreen-left"`, `data-dst="sink-into:drain-hole"` hoặc `stay`).
- Cống rò rỉ & xoáy nước: (`data-obj="drain-hole"`, `data-kind="prop"`).
- Hồ chứa & mực nước: (`data-obj="lake-reservoir"`, `lake-water"`, `data-kind="prop"`).
- Nhãn rò rỉ: (`data-obj="leak-tag"`, `data-kind="text"`, `data-src="offscreen-bottom"`, `data-dst="stay"`).
- Con số kết quả: (`data-obj="stat-value"`, `data-kind="text"`, `data-src="offscreen-top"`, `data-dst="stay"`).
- Chip kết luận: (`data-obj="caption-chip"`, `data-kind="text"`, `data-src="offscreen-bottom"`, `data-dst="stay"`).
- Giới hạn: Tối đa 24 đồng xu tạo, 14 đồng xu đồng thời.

## 2. Cú máy chính
Lùi ra lộ sông (pull back), lia ngang theo dòng chảy (pan), đẩy vào miệng cống (push in), và đổi nét sang mặt hồ (rack focus).
