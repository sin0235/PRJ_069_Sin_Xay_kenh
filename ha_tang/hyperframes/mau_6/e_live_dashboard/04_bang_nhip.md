# Bảng nhịp: Cảnh E - LIVE_DASHBOARD (M4)

| Khoảng giây | Sự kiện chuyển động | Chi tiết chuyển động | Trạng thái camera | SFX | Biến sự kiện bám lời |
|---|---|---|---|---|---|
| **0.0 - 0.8** | Mở cảnh & Tiêu đề | Nền và bệ xuất hiện; tiêu đề trượt vào từng từ trễ 0.08s | `(scale: 1.06, x: +3%, y: 0)` | | Mở đầu |
| **0.6 - 3.0** | Cột biểu đồ mọc | Mỗi cột mọc 0.8s `back.out(1.3)` cách nhau 0.35s; đường xu hướng 1 vẽ dần 1.4s | Lướt thị sai `(1.00, -6%, 0)` (2.5%/s) | `luot_nhe` lúc 0.6s | "Chi phí vận hành ngày càng tăng" |
| **3.0 - 4.4** | Nhấn cột nổi bật | Máy đẩy êm vào cột nhấn; các cột khác mờ về 55%; chip `tag` bật lên | `(1.07, -8%, -2.5%)` | | "Doanh thu không tăng tương xứng" |
| **3.2 - 5.2** | Kim đồng hồ quét | Kim quét từ 0 đến `to_value` theo `elastic.out(1, 0.6)` qua ngưỡng 70% sang màu san hô | Giữ khung cận | `go_nhe`, `canh_bao` | "Điểm nghẽn lãng phí" |
| **4.6 - 5.6** | Thẻ KPI trượt vào | 2 thẻ KPI trượt vào từ ngoài phải với `power3.out`, nảy nhẹ 6px | | `bat_mo` lúc 4.6s | "Số liệu thực tế" |
| **5.8 - 8.0** | Chuỗi thứ hai & Giao nhau | Chuỗi 2 vẽ dần 1.6s; điểm giao nhau nhấp nháy 3 nhịp | Quét ngang `(1.03, +4%, 0)` | `luot_nhanh` lúc 5.8s | "Đối chiếu vận hành" |
| **8.0 - 9.4** | Lùi ra & Kết luận | Máy lùi ra toàn cảnh `(1.00, 0, 0)`; chip `caption` trượt từ dưới lên | `(1.00, 0, 0)` | `dong_dau` lúc 8.4s | "Tận dụng nguồn lực đang có" |
| **9.4 - 10.0** | Giữ khung & Thoát mờ | Vi chuyển động thở nhẹ, thoát mờ 0.25s cuối | Giữ tĩnh | | Thoát cảnh |
