# Kiểm tra lại số video từ tiếng toàn bộ nguồn 8 GB

## Kết luận về số lượng nội dung

**Có 8 mạch kịch bản hoàn chỉnh và 1 phần mở đầu kịch bản tiếp theo bị ngắt.** Số 10 trong bản rà soát đầu là tách dư, không dùng làm số lượng clip sẽ xuất.

1. Đơn nhiều nhưng tiền thực nhận còn bao nhiêu sau các chi phí.
2. Tăng giá nhưng tổng tiền lời lại giảm.
3. Đơn hàng giá rẻ, công xử lý mỗi đơn và giải pháp combo phù hợp nhu cầu.
4. Quảng cáo tạo đơn nhưng chưa chắc tạo lợi nhuận.
5. Doanh thu, lợi nhuận và quản trị dòng tiền đến hạn thanh toán.
6. Rời sàn tránh phí và niềm tin của khách ở từng kênh.
7. Giảm giá có thể mất nửa phần lãi; cần biết mình đánh đổi điều gì.
8. Sản phẩm bán chạy nhưng chưa chắc nuôi được cửa hàng; xem tiền đóng góp thay vì chỉ doanh thu/số đơn.

Cuối nguồn bắt đầu nội dung thứ 9: “Một đơn hàng hoàn ... có khi là mất lãi đến tận ba đơn”, rồi dừng ở “Nhưng đó là câu chuyện của...”. Giữ phần này riêng, không xuất thành video hoàn chỉnh và không ghép vào kết luận nội dung 8.

## Bằng chứng đã thực hiện

- WAV nguồn có SHA-256 `df4d41d9ba94450208d8d007d7cdd89803c4933abcb2c3a679f181d5ee4381e1`, 16 kHz, mono, PCM16, dài 926,827 giây.
- Gửi tiếng tới 9Router thật theo cửa sổ tối đa 120 giây, chồng lấn 5 giây; cắt WAV bằng thư viện chuẩn, không chạy ASR/render nặng local.
- Có 8 cửa sổ trả phiên âm, bao phủ 0–925 giây; cửa sổ cuối 920–926,827 giây trả HTTP 200 nhưng `EMPTY_TRANSCRIPTION`, được giữ cờ rà soát, không bịa lời. Lần gửi phần cuối dài 121,827 giây trước đó nhận HTTP 400; đã chia nhỏ, giữ kết quả các phần đã xong.
- Đọc đối chiếu phiên âm toàn nguồn và gọi LLM lại với tiếng vừa nhận dạng, quy tắc không tách ví dụ/giải pháp khỏi cùng kịch bản. Kết quả có 9 mục: 8 mục `hoan_chinh=true`, 1 mục `false`.
- Nhận xét cuối của LLM ghi nhầm số lượng so với chính danh sách trả về. Báo cáo dựa trên các mục đã kiểm và nội dung phiên âm, không lấy dòng nhận xét sai làm bằng chứng.

## Chỉnh lại bản chuẩn bị

- Gộp “đơn giá rẻ” và “combo” thành nội dung 3; gộp ví dụ “giảm giá mất nửa lãi” với phần ứng dụng phía sau thành nội dung 7.
- Bản chuẩn bị dự án mới `61340dab-a666-4fa2-9bed-ac92520d125b` đã đổi từ 10 nhóm sơ bộ sang 8 nội dung đầy đủ, giữ riêng phần thứ 9 bị ngắt.
- Mốc cắt chưa được coi là đã chốt: phát hiện LLM bỏ phần hook “Tăng giá rồi” và đẩy câu hook quảng cáo vào cuối nội dung trước trong một số word ID. Cần căn lại tiếng/word ID trước render; không dùng nguyên mốc dự thảo để dựng cả lô.
- Chưa gửi render toàn lô. Giữ style, karaoke và danh mục HyperFrames vừa nối trong lượt kế tiếp.
