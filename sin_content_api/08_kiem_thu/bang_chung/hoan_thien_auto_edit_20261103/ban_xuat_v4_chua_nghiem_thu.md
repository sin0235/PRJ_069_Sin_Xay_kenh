# Bản xuất Auto Edit v4, chưa nghiệm thu

Job666a7727-3e03-4812-ad88-8451cda61e0a đã SUCCEEDED qua pipeline sản phẩm. Asset169a64e3-baba-45f2-a2d7-dbdb8199be36, source_product AUTO_EDIT, parent là UPLOAD gốc f85636f3-f8a0-489b-8ea2-9070d59b13dd. Không dùng video đã edit làm đầu vào.

Link: https://nhap-xaykenh-prj069.bahagroup.vn/auto-edit?project_id=786676f6-e3c7-457d-9ccd-a22158507fdf&asset_id=169a64e3-baba-45f2-a2d7-dbdb8199be36

File auto_edit_f85636f3_01_4329db34.mp4,19.617.858 byte, SHA-2564df4f5bc848323935b8f96f6031ec99e996c50dfe94b98a00c30ad2237c179f0. Render chính1080x1920/30fps,63,666667 giây; brand_end và QC remote SUCCEEDED. Range đầu và cuối1024 byte qua domain có xác thực đều206, Content-Range khớp byte_size. Bằng chứng video_v4_tren_web.json. Chưa xác minh trình phát tương tác trên giao diện hoặc nghe toàn clip, chưa có chứng cứ LUFS cuối.

Quan sát ba khung360x640 từ MP4 thật:

-26 giây: người nói và karaoke lớn, nhưng overlay câu hỏi quá nhỏ và đang nhạt, khó đọc. Bản sửa kiểm font sau scale đã có cho lượt kế tiếp, chưa áp dụng bản này.
-32 giây: cảnh Flow giấy gấp đã phục hồi hiện toàn khung cùng karaoke, không thấy dấu logo ở góc trong khung này; còn ký tự giả trên đạo cụ.
-37 giây: checklist hiển thị chữ lớn, đang ở mục2/5, nhưng toàn khung có nhiều nền đen trống do bố cục CUTAWAY cho asset alpha; chưa đạt bố cục chuyên nghiệp. Cần sửa cách chọn bố cục và/hoặc composite alpha, giữ quyết định nội dung cho LLM.

Một cảnh Flow khác chưa được tạo do chờ xác nhận tài khoản sau khi Founder nghi ngờ sai hồ sơ. Kế hoạch còn khoảng dài thiếu minh họa. Đây là bản kiểm tra pipeline, không phải video đã đạt95% hoặc bằng chứng goal hoàn tất. Nguồn8GB chỉ chứng minh upload/hash, chưa xử lý toàn bộ.

## Sửa ghép alpha sau khi xem bản xuất

Renderer render_timeline_document bỏ qua pad_color trong timeline và luôn pad đen. Chuyển MOV alpha sang H.264 cũng không có bước ghép nền cho vùng trong suốt bên trong canvas. Test FFmpeg thật160x284, clip alpha đỏ50%, nền yêu cầu xanh: trước sửa pixel viền đen thay vì xanh. Sau sửa renderer xác thực màu hex6 ký tự, pad đúng màu và ghép alpha lên nền đục trước mã hóa; pixel viền xanh và tâm tím đúng kết quả trộn. Sáu test trong test_overlay_dung_moc.py đạt trong6,84 giây, gồm màu sai bị từ chối, alpha, overlay muộn/trim và PIP. Không chạy render fullHD local.

Bản sửa chỉ xử lý màu/composite, chưa cải thiện khoảng trống bố cục CUTAWAY hoặc quyết định nội dung. MP4 v4 ở link trên chưa được dựng lại, vẫn còn nền đen quan sát được. Cần runner có bản sửa cho lượt kế tiếp và kiểm lại video thật.

## Giữ dữ liệu nhẹ để phục vụ dựng lại

Cache kế hoạch bị dọn sau khi job hoàn tất. Manifest trước đây chỉ có timeline, lý do và lựa chọn diễn họa, chưa giữ transcript gốc theo word ID và toàn kế hoạch/brief. Bổ sung words, plan và visual_briefs vào manifest đã được kiểm soát workspace. Không giữ thêm bản sao video gốc hoặc audio. Kiểm thử tích hợp xuất clip hiện hữu xác nhận word ID, clip ID, hash nguồn, danh sách brief được lưu và hash nguồn không đổi:1/1 đạt trong30,98 giây,106 ca không chạy. Đây là metadata cho các lượt xuất mới, chưa bổ sung endpoint dựng lại và không khôi phục cache đã dọn của v4. Không dùng MP4 đã edit làm đầu vào thay thế.
