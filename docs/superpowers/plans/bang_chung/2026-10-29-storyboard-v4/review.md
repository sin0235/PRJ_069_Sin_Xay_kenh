Rà soát độc lập: range `80a6d99..58cda68`, kèm cập nhật prompt/UI sau đó.

Điểm đã kiểm: tương thích serialization/prompt v3; UI_SIM có receipt/asset theo scope, escape HTML và không yêu cầu Flow; quy tắc chuyển động v4 không bắt số beat hoặc có người trong mọi cảnh.

Important: narration vẫn nhận tiếng Anh nguyên dạng và chuyển thẳng sang TTS. Đã có test tái hiện câu `AI will answer customer requests.` và thuật ngữ `chatbot`, `marketing`; đồng thời kiểm chữ UI vẫn giữ được tiếng Anh/số. Sửa tại hợp đồng v4 để áp cho cả tạo, sửa và đọc lại trước khi chạy; không thay tiếng nói sau khi duyệt. Kiểm tra dạng âm tiết chỉ chặn được trường hợp hình thức chưa phiên âm, còn từ đồng hình cần duyệt ngữ nghĩa.

Minor để lại: action_beats của UI_SIM không được renderer dùng; hoạt ảnh dựa vào mốc tin nhắn. Trường này có thể được lưu và hiện trên editor nếu LLM trả về dù không đổi hoạt ảnh.

Reviewer không kết luận về chất lượng Flow thật, gateway 503 hoặc 11 lỗi môi trường đã tái hiện ở commit gốc. Không có lỗi riêng được tìm thấy trong phần tăng diễn tiến hành động hoặc bỏ yêu cầu luôn có nhân vật.

Kết luận review ban đầu: có thể tích hợp sau khi xử lý Important. Chưa merge/push/deploy; trạng thái kiểm tra sau lượt sửa nằm cuối plan chính.
