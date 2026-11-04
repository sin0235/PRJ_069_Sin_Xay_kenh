# Chuẩn bị xử lý toàn bộ video gốc 8 GB

## Đầu vào và phạm vi

- Dự án Auto Edit: `685d269c-def5-4e35-9038-a75d2119dd80`.
- Nguồn gốc: `c15a3ad0-811a-4f96-861b-630549dab417`, 8.428.283.732 byte, dài 926,827 giây; đang lưu trên ổ C:.
- SHA-256 nguồn: `8b520dc243dfa602d09fee1f24c3d1f9ff89f56833b234eb6d317fc272a542df`.
- Đã có phiên âm toàn nguồn và kết quả đối chiếu tiếng 9Router. Chuẩn bị trên toàn bộ 2.597 từ, gồm cả các đoạn ngoài clip mẫu 42 giây.
- Lượt này chuẩn bị bản chia kịch bản và hàng đợi, chưa gửi cả lô tạo cảnh hoặc render.

## Quy tắc dựng đã chốt

1. LLM phân biệt kịch bản theo nội dung tiếng nói, gom các take quay lại cùng kịch bản và giữ take đầy đủ tốt nhất. Mọi từ phải được giải trình trong take hoặc phần hậu trường bị loại; không tự coi năm ứng viên cũ là kết quả cuối.
2. Giữ trọn mở đầu, ví dụ, lập luận, kết luận và CTA. Độ dài phụ thuộc nội dung; khoảng nghỉ chỉ hỗ trợ cắt vấp và khoảng lặng.
3. Checklist toàn khung dùng danh sách tích lũy: dòng sau hiện dưới dòng trước, các dòng đã hiện giữ lại. Thẻ overlay một mục chỉ được dùng OVERLAY. Chữ trên giấy sáng dùng mực đậm, giữ màu nhấn hiện có.
4. Diễn họa HyperFrames 3–6 giây mỗi nhịp khi phù hợp; Flow vẫn tạo nguồn 10 giây, timeline chỉ lấy phần cần thiết. LLM chọn công cụ và bố cục theo lời; giữ style giấy của hệ thống.
5. Phụ đề karaoke và style hiện có của hệ thống; không dùng video đã burn sub làm nguồn. Bản dựng mới dùng `diagram_revision=4` để phân biệt diễn họa cũ.

## Hàng đợi và tài nguyên

1. Rà soát toàn nguồn bằng LLM thật, lưu tất cả take, take được chọn, đoạn loại và các từ chưa được bao phủ. Mốc còn mơ hồ được giữ cờ rà soát.
2. Lưu bản kế hoạch bất biến theo nguồn và phiên bản; lập storyboard riêng cho từng kịch bản. Kế hoạch cũ chỉ là dữ liệu tham chiếu, không âm thầm bỏ qua các ứng viên đang có cờ rà soát.
3. Chuẩn bị cửa sổ nguồn thô cho từng nội dung bằng stream copy từ keyframe có phần đệm. Xác minh gói hình và lưu offset; dịch mốc hình/tiếng cùng offset trước khi gửi renderer. Đây là nguồn thô dẫn xuất, không phải MP4 thành phẩm được dùng lại.
4. Giao ASR, render, gỡ logo và ghép cuối cho GitHub Actions, tối đa một tác vụ nặng đồng thời. Host local giữ API, Flow và điều phối. Không gửi lại cả 8 GB cho từng clip.
5. Chuyển cảnh từng cặp để giới hạn số đầu vào đồng thời. Lưu checkpoint từng giai đoạn; tác vụ đã có kết quả được dùng lại đúng nguồn, tham số và phiên bản. Flow đã gửi nhưng chưa rõ kết quả phải đối soát trước khi tạo lại.
6. Đăng từng MP4 vào đúng dự án Auto Edit, giữ `UNREVIEWED` để người dùng nghiệm thu. Giao diện kết quả chỉ hiện video đã edit; các tệp âm thanh, phụ đề và manifest phục vụ nội bộ.

## Kết quả rà soát 9Router trên toàn bộ nguồn

LLM thật đã đề xuất 10 nhóm kịch bản sơ bộ và 11 take. Đây chưa phải số lượng clip chốt: cả 10 nhóm còn cờ phiên âm mơ hồ. Kế hoạch cũ có 5 ứng viên nên không đủ làm bản phân chia mặc định cho cả tệp.

| Nhóm sơ bộ | Nội dung | Mốc nguồn được đề xuất |
|---|---|---|
| 01 | Chi phí và tiền lời thực nhận mỗi đơn | 0,000–96,440 giây |
| 02 | Tăng giá và tổng lợi nhuận | 97,480–203,460 giây |
| 03 | Đơn hàng rẻ vẫn tốn công và chi phí | 205,350–238,990 giây |
| 04 | Combo theo nhu cầu và chi phí | 241,060–281,900 giây |
| 05 | Tăng quảng cáo khi thấy nhiều đơn | 282,520–415,390 giây |
| 06 | Dòng tiền và khoản sắp đến hạn | 417,090–516,950 giây |
| 07 | Chi phí trước khi rời sàn | 521,240–626,030 giây |
| 08 | Giảm giá làm mất lợi nhuận | 627,750–670,170 giây |
| 09 | Giảm giá cần đổi lấy điều gì | 704,110–750,610 giây |
| 10 | Quyết định nhập hàng và đóng góp của sản phẩm | 750,610–916,160 giây |

Kiểm tra bằng mã đối chiếu mọi chỉ số từ phát hiện còn một từ cuối chưa được LLM phân loại: chỉ số 2596, “của...”, 916,160–917,900 giây. Bản chuẩn bị giữ nguyên cảnh báo này, không tự coi nguồn đã được bao phủ hoàn toàn. Trước khi dựng cả lô cần đối chiếu âm thanh các nhóm mới, đặc biệt mở đầu nhóm 01, ranh giới nhóm 08–09 và nhóm 10 đang gom một đoạn dài. Phần cuối bị ngắt phải được phân loại rõ; không tự kéo vào clip hoặc bỏ âm thầm.

## Bằng chứng và việc cần chốt trước khi chạy lô

- Sửa checklist/độ tương phản: 126 kiểm thử đạt; ca chuyển cảnh bộ nhớ thấp đạt riêng.
- Bản mẫu mới nhất: asset `8eeb47ac-995c-50b6-b3c0-9c0f269e62ec`, 42,233 giây, có H.264/AAC. Bản mẫu này được render trước thay đổi checklist hiện tại.
- Lượt render nguồn ngắn `97ebcf5d-6ffc-44c1-98e9-bd938f304008` đã SUCCEEDED; nguồn stream copy 527.173.436 byte, offset 829.824 ms. HTTP Range đầu/cuối của thành phẩm đều 206.
- Ba lượt local bị chốt bảo vệ dừng do RAM khả dụng xuống dưới 350 MiB. Không tiếp tục render nặng toàn lô trên host này.
- Bản rà soát toàn nguồn và bản chuẩn bị lô được lưu ở runtime, sau đó sao kết quả kiểm tra vào `sin_content_api/08_kiem_thu/bang_chung/hoan_thien_auto_edit_20261103/`.
- Trước khi chạy lô cần dùng mã nguồn đã chốt trên runner và giữ worker điều phối ổn định. Chưa sửa tổng thể retry HTTP 502 và phục hồi parent job cũ; không dùng trạng thái cũ `SUBMITTING` làm bằng chứng đang chạy.

Chưa xóa nguồn trong giai đoạn chuẩn bị và nghiệm thu. Việc nghiệm thu hình ảnh do người dùng thực hiện; kiểm tra kỹ thuật tập trung vào MP4 có tiếng, đủ thời lượng và mở được trên web.
