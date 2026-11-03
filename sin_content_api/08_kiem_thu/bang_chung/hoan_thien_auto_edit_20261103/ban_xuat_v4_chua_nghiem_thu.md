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

## Nối dựng lại vào pipeline

API Auto Edit hiện hữu nhận thêm manifest_asset_id tùy chọn. Loader kiểm manifest AUTO_EDIT/JSON, workspace, project, parent nguồn, giới hạn32MiB, đường dẫn, hash/size và source_sha256; biên bản thiếu words/plan/brief hoặc sai nguồn bị từ chối. Danh sách child job không trùng, khớp số brief và trong giới hạn hiện hữu. API enqueue cùng operation auto_edit_video ở phase render; worker đọc lại manifest có xác thực, lấy các child đã tạo, cho LLM chọn lại bố cục, rồi chạy render/QC/publish hiện hữu. Không gọi nhánh phân tích nguồn, ASR hoặc tạo cảnh mới. Idempotency tiếp tục dùng khóa request hiện hữu.

Kiểm thử: media_queue70/70 đạt trước bước siết danh sách child;5 ca loader sau siết đạt. Kiểm thử xuất rồi dựng lại từ manifest đạt1/1 trong84,92 giây; gài lỗi nếu ASR hoặc tạo ý tưởng cảnh bị gọi, xác nhận output mới vẫn có parent nguồn gốc và hash nguồn không đổi. API hiện hữu và trường hợp manifest không tồn tại đạt1/1, trả409 AUTO_EDIT_MANIFEST_NOT_REPLAYABLE. Không chạy video8GB hoặc render nặng sản xuất local. Chưa nối nút dựng lại trên UI, chưa nạp backend mới và chưa E2E thật nhánh này; v4 cũ chưa có đủ metadata nên không tự khôi phục bằng suy đoán.

## Giao diện dựng lại

Đã nối nút Dựng lại bố cục bên dưới vùng Clip đã dựng, dùng kiểu nút hiện hữu. Nút chỉ hiện khi manifest đủ trường phục vụ replay và nguồn UPLOAD gốc còn trong dự án; tác vụ đang chạy khóa thao tác. Gửi source_asset_id gốc và manifest_asset_id vào cùng API, tiếp tục poll job và cập nhật danh sách video. Không thêm audio/sub/JSON vào danh sách thành phẩm. Bản cũ thiếu dữ liệu vẫn xem được nhưng không có nút replay.

Parser frontend trước đây giới hạn3 Flow, không khớp backend2000. Đã sửa cùng mức2000; test4 cảnh đọc được và2001 cảnh bị từ chối. Hai test parser/render đạt;10 test media-studio-api đạt, gồm request dựng lại. tsc --noEmit --incremental false đạt, detector Impeccable trả[]; chưa xác minh nút bằng trình duyệt sau build. Chỉ giữ boolean/source ID phục vụ nút, không đưa toàn transcript vào state React.

Build FE trên Actions41646958791 đã completed/success cho commit915804f. Khi rà parser tiếp, phát hiện mode SPEAKER_PIP hợp lệ ở backend bị frontend từ chối và nhãn OVERLAY ghi cố định góc phải. Đã thêm mode đúng và nhãn Người nói trong khung nhỏ/Lớp phủ hoạt ảnh; test PIP trước sửa thất bại, sau sửa hai test parser/render đạt, TypeScript đạt. Cần build mới chứa phần sửa PIP trước khi cài runtime; chưa triển khai artifact cũ.

## Kiểm tra web thật và sửa phát/seek

Đã cài artifact41647325593 thành công vào runtime/web, giữ bản cũ. Qua Playwright CLI đăng nhập bằng JWT của tài khoản owner hiện hữu, không đổi mật khẩu/quyền; file state tạm chứa token đã xóa sau nạp. Trang /auto-edit hiện đúng dự án, chỉ video thành phẩm, biên bản v4 có cảnh cần rà soát; nút dựng lại không hiện vì biên bản cũ thiếu metadata.

Test phát thật trước sửa thất bại: video readyState4,1080x1920 nhưng currentTime0 dù paused=false; console báo blob URL ERR_FILE_NOT_FOUND lặp lại. Root cause: effect dọn URL phụ thuộc cả previewUrl và previewCaptionUrl, thu hồi URL video khi SRT tải xong. Tách hai effect theo từng URL. Đồng thời bỏ default của track captions vì MP4 đã burn karaoke, tránh bật hai lớp sub chồng nhau; track truy cập vẫn có thể bật thủ công. Không sửa MP4 để chữa lỗi trình phát.

Hai test parser/render và TypeScript sau sửa đạt. Artifact mới41653852043 (a97ef3a) completed/success, đã cài vào runtime/web; web PID16220 nghe cổng3000. API/worker không restart. Script khởi động báo cổng web chưa nghe quá sớm; kiểm lại cổng và trình duyệt đã sẵn sàng. Cảnh báo profile Flow đang bị giữ vẫn còn, không suy ra cần đăng nhập lại hoặc xóa lock.

Kiểm tra Playwright sau cài: phát currentTime0,014595; duration63,666667;1080x1920; readyState4; error=null. Seek37,008487 giây, readyState4, error=null. Track vi disabled, không bật phụ đề ngoài. Không có console error mới trong lượt kiểm tra. Screenshot desktop và viewport390x844 được lưu; document clientWidth=scrollWidth=390. Một số nút thao tác ở viewport hẹp còn sát/cắt ở mép vùng chứa, cần rà responsive; không nhận toàn bộ UI đạt. Chưa nghe audio toàn clip hoặc xem đủ mọi cue, chưa nghiệm thu95%.
