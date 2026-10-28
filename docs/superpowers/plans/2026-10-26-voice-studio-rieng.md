# Voice Clone & TTS riêng trong SIN Creator OS

## Mục tiêu

Tạo trang `/voice-studio` độc lập trong ứng dụng hiện tại, chia đúng hai tab `TTS` và `Clone giọng`. TTS nhận nội dung, giọng có sẵn hoặc giọng đã lưu, bảng phiên âm và cài đặt nâng cao. Tab Clone giọng lưu audio tham chiếu thành mục trong thư viện `Giọng của tôi` để dùng lại. Tác vụ không phụ thuộc project video hoặc storyboard.

## Phạm vi cần chạm

- Backend: API submit/trạng thái/danh sách job và thư viện voice; dùng `AIGenerationJob`, `MediaAsset`, TTS provider manager và worker lease đang có. Thêm entity voice profile theo workspace.
- Frontend: hai tab riêng; thư viện voice có thể chọn từ tab TTS; upload audio và playback dùng Media Studio API hiện tại.
- Kiểm tra: xác thực workspace, consent khi clone, idempotency, parser bảng phiên âm, tham số nâng cao có giới hạn, xử lý job qua worker độc quyền, WAV đầu ra.

## Không thuộc phạm vi

Không dựng ứng dụng khác, không phụ thuộc video run, không thêm provider/model hay tính năng biên tập âm thanh. Chỉ lưu audio tham chiếu và cấu hình clone; không tạo bản ghi model riêng.

## Tiêu chí nghiệm thu

- `/voice-studio` vào được từ sidebar và công cụ Voice Clone & TTS.
- Có thể gửi tác vụ TTS độc lập với preset hoặc voice đã lưu, theo dõi trạng thái và nghe/tải asset.
- Có đúng hai tab; tab Clone giọng tạo/lưu profile workspace, tab TTS có cài đặt nâng cao và bảng phiên âm Anh–Việt.
- Job dùng cùng lease với render video; không lộ nội dung đầu vào trong phản hồi trạng thái.
- Test logic submit/idempotency/worker và build frontend đạt; không tải model hay gọi inference thật trong kiểm thử.
