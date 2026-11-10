# Tờ yêu cầu: Cảnh E - LIVE_DASHBOARD (M1)

- **Tên layout:** `LIVE_DASHBOARD`
- **Mã khối:** `live-dashboard.html`
- **Thời lượng:** 10.0 giây (300 khung hình @ 30 fps)
- **Tập bài áp dụng:** Bài 04, 07, 17 và Kịch bản Khám sức khỏe doanh nghiệp BAHA.
- **Ý chính một câu:** Bảng điều khiển dữ liệu 3D origami hiển thị các cột biểu đồ mọc lên, đường xu hướng trực quan, kim đồng hồ quét vượt ngưỡng và thẻ KPI thực tế.

## 1. Danh sách vật thể chuyển động & giới hạn
- Cột biểu đồ: 3 đến 5 cột (`data-obj="bar-1"` đến `bar-5"`, `data-kind="prop"`, `data-src="static"`, `data-dst="stay"`).
- Thẻ KPI: 2 thẻ nổi (`data-obj="kpi-1"`, `kpi-2"`, `data-kind="prop"`, `data-src="offscreen-right"`, `data-dst="stay"`).
- Đồng hồ đo & kim: 1 cụm (`data-obj="gauge-meter"`, `gauge-needle"`, `data-kind="prop"`).
- Đường xu hướng: 2 đường nét vẽ (`data-obj="trend-line-1"`, `trend-line-2"`, `data-kind="fx"`).
- Chip kết luận: 1 chip (`data-obj="caption-chip"`, `data-kind="text"`, `data-src="offscreen-bottom"`, `data-dst="stay"`).
- Giới hạn phần tử chuyển động đồng thời: <= 12 phần tử.

## 2. Cú máy chính
Lướt thị sai (parallax pass) kết hợp đẩy vào (push in) êm và lùi toàn cảnh (pull back).

## 3. Trường dữ liệu DiagramSpec
- `title` (string <= 60 chars)
- `labels` (array of 3-5 strings, each <= 10 chars)
- `series` (1-2 series, values list matching labels)
- `unit` (string <= 16 chars)
- `to_value` (number 0-100)
- `tag` (string <= 24 chars)
- `caption` (string <= 40 chars)
