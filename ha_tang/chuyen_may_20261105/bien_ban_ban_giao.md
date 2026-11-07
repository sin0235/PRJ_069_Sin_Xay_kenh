# Bàn giao chuyển máy ngày 05 tháng 11 năm 2026

Bộ sao lưu nằm tại `\\192.168.1.175\09.ai_workspace\01_du_an\PRJ_069_Sin_Xay_kenh\90_sao_luu\02_chuyen_may\chuyen_may_20261105_131258`.

Đọc `huong_dan_cai_dat_va_chay.md` trong thư mục gói trước khi khôi phục. Mã nguồn lấy từ worktree đang chạy, nhánh `dev/local-remote-video-tests`, commit `951caf6bea2dece985399e6af51c439cd198370d`, kèm các thay đổi chưa commit và âm thanh mới chưa được Git quản lý.

- `ma_nguon`: bản mã hiện hữu, không kèm con trỏ `.git` tuyệt đối của máy cũ.
- `du_lieu/data`: ba database được chụp bằng SQLite backup API; integrity_check đạt, SHA-256 bản trên NAS khớp. Dữ liệu lô và trạng thái vận hành được giữ cùng bộ.
- `du_lieu/media_assets`: media của máy đang chạy; xem kết quả Robocopy trong `bang_chung/media_robocopy.log`.
- `runtime`: các ZIP web standalone, công cụ, Python Windows 3.11 và tệp vận hành bổ sung; đã kiểm tra CRC.
- `cau_hinh_rieng`: cấu hình riêng và trạng thái 9Router, gồm snapshot SQLite. Giữ khóa JWT và mã hóa LLM đi cùng database; xác minh lại đăng nhập trên máy mới.
- `git`: commit, nhánh, trạng thái, bản vá chưa commit và danh sách gói Python. Kho hiện tại là partial clone/sparse checkout, không bảo đảm lịch sử Git đầy đủ khi offline.
- `tu_lieu_ngoai`: 20 nội dung kịch bản bên ngoài checkout.
- `bang_chung/danh_muc_sha256.json`: checksum mã nguồn, cấu hình, Git metadata và runtime.

## Phần cần chú ý khi tiếp quản

Database chứa 667 bản ghi media; 199 tệp lịch sử không tồn tại trong thư mục media nguồn ngay trước sao lưu và chưa tìm được tại các vị trí dự phòng đã kiểm tra. Danh sách cụ thể nằm trong `bang_chung/media_db_inventory.json`; đây là thiếu hụt hiện hữu, không phải tệp bị xóa trong quá trình chuyển máy.

Máy mới phải sửa các đường dẫn tuyệt đối trong `.env.dev`, xác thực lại GitHub CLI, các provider 9Router và Google Flow. Bộ sao lưu không bảo đảm chuyển được cookie Windows sang tài khoản mới. Chỉ chuyển quyền worker/tunnel sau khi máy cũ nhường quyền để tránh gửi trùng tác vụ.

Chưa nghiệm thu trên một máy Windows mới. Các database là snapshot riêng từng tệp, không phải giao dịch chung của cả ba database. Việc sao lưu không triển khai lại hoặc thay thế runtime NAS hiện hành.
