# Nguồn bộ hiệu ứng âm thanh

Bộ thư viện có 32 hiệu ứng WAV: 20 hiệu ứng nội bộ BAHA hoặc tổng hợp cho dự án, và 12 hiệu ứng giao diện từ Kenney Interface Sounds.

Ứng dụng chỉ phát hiệu ứng khi storyboard mô tả hành động tương ứng. Âm lượng từng hiệu ứng được hạ riêng trong `sfx.py` để không lấn lời đọc và nhạc nền.

## Gói giao diện Kenney

- Nguồn: Kenney, [Interface Sounds](https://kenney.nl/assets/interface-sounds), phiên bản 1.0.
- Giấy phép nguồn: Creative Commons CC0 1.0; dùng được cho dự án thương mại, không bắt buộc ghi công. [Điều khoản CC0](https://creativecommons.org/publicdomain/zero/1.0/).
- Ngày lấy: 2026-11-02. Mã băm SHA-256 gói gốc: `f2193d072726d6758a5f7871b2dcc54dcce0d5c35c6f0a62f92549b327c81232`.
- Mười hai tệp OGG được chuyển sang WAV PCM 16-bit, stereo, 44,1 kHz để dùng chung định dạng với thư viện hiện tại.

| Tệp dùng trong dự án | Tệp gốc trong gói |
|---|---|
| `nhap_nut_nhe.wav` | `Audio/click_001.ogg` |
| `nhap_nut_manh.wav` | `Audio/click_003.ogg` |
| `ui_mo.wav` | `Audio/open_001.ogg` |
| `ui_dong.wav` | `Audio/close_001.ogg` |
| `ui_tha.wav` | `Audio/drop_001.ogg` |
| `ui_cuon.wav` | `Audio/scroll_001.ogg` |
| `ui_phong_to.wav` | `Audio/maximize_001.ogg` |
| `ui_thu_nho.wav` | `Audio/minimize_001.ogg` |
| `ui_loi.wav` | `Audio/error_001.ogg` |
| `ui_xac_nhan.wav` | `Audio/confirmation_002.ogg` |
| `ui_chon.wav` | `Audio/select_001.ogg` |
| `ui_vet_but.wav` | `Audio/scratch_001.ogg` |
