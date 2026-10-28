# Bảng phong cách đề xuất cho Vietsub

**Trạng thái:** Bản đặc tả để Founder chọn hướng; chưa phải style đã duyệt hoặc asset production.  
**Phạm vi:** Caption tiếng Việt cho narration tiếng Việt trong video dọc. Chưa bao gồm dịch lời nói ngoại ngữ.

## Hướng đề xuất

Thử hai cách trình bày trên cùng một nội dung và ba nền đại diện. Khuyến nghị đưa phương án B vào vòng xem trước đầu tiên vì video có nền thay đổi liên tục; phương án A giữ lại để so sánh độ nhẹ mắt. Chưa chốt màu thương hiệu, font, fallback hay kích thước cuối trước khi Founder duyệt và font thật được render kiểm tra.

### Thông số chung cho cả hai phương án

- Khung mẫu: 1080 × 1920, 30 fps.
- Vùng an toàn: trên 150 px, dưới 320 px, phải 120 px; lề trái đề xuất 60 px.
- Tối đa hai dòng, 38 ký tự mỗi dòng, tối đa 20 ký tự/giây, cue 0,7–6 giây.
- Căn giữa theo khung; đặt bounding box thấp vừa phải nhưng không xuống dưới ranh giới an toàn. Tọa độ cuối cần đo bằng font thực và kiểm tra trên video có UI TikTok.
- Font candidate để thử: Be Vietnam Pro SemiBold 600 vì có hỗ trợ tiếng Việt và giấy phép SIL OFL 1.1 theo Google Fonts. Tệp font, hash, quyền nhúng và fallback chưa được chốt.
- Câu mẫu dùng giống nhau cho A/B: `Đừng để AI đoán lời đọc.` / `Giữ đúng dấu: ă â ê ô ơ ư đ, RAG, API.`

## Phương án A: chữ sáng, không hộp nền

| Thuộc tính | Đề xuất thử |
|---|---|
| Chữ | Trắng ngà, weight 600, cỡ thử 48–54 px. |
| Nền | Không có hộp; viền tối mảnh hoặc bóng nhẹ để tách khỏi nền. |
| Bố cục | Hai dòng căn giữa, chiều rộng tối đa khoảng 84% khung. |
| Ưu điểm cần kiểm | Ít che hình, cảm giác gọn và gần phong cách biên tập. |
| Rủi ro cần kiểm | Khó đọc trên vùng sáng, chi tiết dày hoặc chuyển động mạnh. |

Mẫu trình bày: chữ trắng ngà, viền tối mảnh, đặt giữa vùng an toàn phía dưới.

## Phương án B: chữ sáng trên nền tối bán trong suốt

| Thuộc tính | Đề xuất thử |
|---|---|
| Chữ | Trắng ngà, weight 600, cỡ thử 48–54 px. |
| Nền | Hộp chữ đen bán trong suốt khoảng 68–72%, padding cân đối; chưa bo góc hoặc thêm hiệu ứng nếu renderer không hỗ trợ ổn định. |
| Nhấn | Chỉ dùng một token màu trong palette công ty sau khi Founder duyệt; bản chưa duyệt dùng trắng/đen trung tính. |
| Bố cục | Hai dòng căn giữa; hộp không vượt vùng an toàn và không chiếm quá nhiều diện tích hình. |
| Ưu điểm cần kiểm | Tương phản ổn định hơn trên ba loại nền. |
| Rủi ro cần kiểm | Hộp có thể che hình hoặc tạo cảm giác nặng nếu padding/độ đục quá lớn. |

Mẫu trình bày: cùng câu mẫu với phương án A, đặt trên hộp tối bán trong suốt; không đổi cỡ chữ hoặc vị trí để so sánh công bằng.

## Ba nền phải dùng để so sánh

1. Cảnh tối có vùng nền tương đối phẳng.
2. Cảnh sáng có vùng màu gần trắng phía sau caption.
3. Cảnh chuyển động nhiều chi tiết, có thay đổi sáng/tối trong lúc cue hiển thị.

Mỗi nền dùng cùng câu mẫu, độ dài, thời điểm và kích thước xuất. Đánh giá khả năng đọc, phần hình bị che, dấu tiếng Việt, tên riêng/thuật ngữ, bounding box và TikTok Safe Zone. Không dùng nền giả làm bằng chứng nghiệm thu video cuối.

## Đề xuất chọn hướng

Đưa A và B ra Founder xem cùng nhau; chọn B làm ứng viên pilot nếu độ tương phản trên cả ba nền đạt và phần hộp không che chủ thể. Nếu B quá nặng, chọn A chỉ sau khi kiểm tra thực tế trên nền sáng. Đây là khuyến nghị thiết kế, không phải quyết định thương hiệu.

## Cần thêm trước khi duyệt cuối

- Bản xem trước trực quan A/B trên ba khung video thật có quyền sử dụng.
- Font asset thực tế, SHA-256, weight, license, glyph tiếng Việt và điều kiện nhúng.
- Mã màu/palette được Founder duyệt; kích thước và bounding box đo bằng font thật.
- Ảnh kiểm tra ít nhất 12 frame sau khi có lease render; tài liệu này chưa có ảnh render và không được coi là nghiệm thu.

Nguồn font: [Be Vietnam Pro trên Google Fonts](https://fonts.google.com/specimen/Be+Vietnam+Pro), [metadata và giấy phép trong kho Google Fonts](https://github.com/google/fonts/tree/main/ofl/bevietnampro).
