# Kết quả đối chiếu bổ sung trước chuyển máy

- Đã đối chiếu 1.004 tệp tracked hiện hữu: mã khớp; bổ sung đủ 5 log tracked từng bị bộ lọc bỏ qua.
- Bổ sung 37 tệp chưa tracked trong `bang_chung/tep_chua_track_bo_sung.zip`; ảnh kiểm thử trong `bang_chung/output_kiem_thu.zip`.
- Bản dự phòng hồ sơ Flow nằm tại `cau_hinh_rieng/flow_profile.zip`, đã bỏ cache và khóa tiến trình. Vẫn cần xác minh hoặc đăng nhập lại trên máy mới.
- Hai cấu hình riêng `.env.dev` và `.env.tunnel_token` khớp máy nguồn. Web, tools và runtime bổ sung không thiếu tệp theo danh sách archive.
- Database nội dung đã thay đổi sau lần sao lưu đầu. Khi phục hồi, chép ba DB từ `du_lieu/data`, sau đó phủ `sin_content_production.db` từ `du_lieu/database_cap_nhat_sau_doi_chieu`. Các bản mới đều đã kiểm tra toàn vẹn và SHA-256. Hai DB còn lại không thay đổi.
- Sau khi giải nén `runtime/bo_sung.zip`, giải nén thêm `runtime/cap_nhat_sau_doi_chieu.zip` vào cùng thư mục runtime nếu có tệp trong gói.
- Bằng chứng đối chiếu: `bang_chung/doi_chieu_lai_hoan_tat.json`, `database_doi_chieu_lai.json` và danh mục SHA-256.

199 media lịch sử vẫn thiếu từ trước tại nguồn; xem danh sách đã bàn giao. Cache model và browser có thể tải lại; đăng nhập GitHub/Flow/9Router cần xác minh trên máy mới. Chưa thử phục hồi trên Windows sạch.
