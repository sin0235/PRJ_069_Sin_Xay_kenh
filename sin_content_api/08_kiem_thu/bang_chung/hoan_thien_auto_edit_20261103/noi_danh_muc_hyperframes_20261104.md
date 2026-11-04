# Nối danh mục HyperFrames mới vào Auto Edit

## Kết quả

- Kiểm tra các commit mới `33e6ae5`, `9c25e6c`, `ec39ebd`, `d6eaf55`: bốn layout mới, biến thể tiêu đề, chuyển cảnh/camera/lớp nền/lower third và danh mục quét khối.
- Danh mục thô có 159 mục; 126 mục được đánh dấu dùng được trong kết quả quét đã có. Đây không phải bằng chứng render lại 159 mục trong lượt này.
- Có 13 layout đã ánh xạ schema và renderer, gồm bốn layout mới `CHAT_THREAD`, `NOTE_TYPING`, `CTA_CLOSE`, `NOTIFY_STACK`. Các biến thể tiêu đề được manifest chọn tất định theo nội dung.
- Auto Edit trước đó chỉ mô tả sáu layout cũ trong prompt. Đã thay bằng trường `cac_khoi_hyperframes` lấy trực tiếp `hf_prompt.LAYOUT_PROMPTS`; bổ sung quy tắc CTA ở cuối và phân biệt danh sách tích lũy với thay từ.
- Không sửa chồng các thay đổi đang làm của agent khác trong runner, service hoặc luồng tạo video AI.

## Kiểm chứng

- Trước sửa: bốn ca layout mới cùng lỗi `KeyError: cac_khoi_hyperframes`.
- Sau sửa: `python -m pytest tests/test_storyboard_nhieu_nhip.py tests/test_khoi_hyperframes.py tests/test_hf_catalog.py -q --disable-warnings --tb=short`: **86 passed, 1 warning in 130.53s**.
- Gọi 9Router thật với planner vừa sửa, xác minh request có đủ danh mục 13 layout. Kết quả ba cảnh hợp lệ: `KINETIC_TITLE`, `CHECKLIST`, `VERSUS_LIST`. Chỉ chẩn đoán storyboard, chưa gửi Flow hoặc render cảnh. Bằng chứng: `kiem_tra_llm_hyperframes_moi_20261104.json`.

## Dự án mới và video nguồn

- Dự án: `61340dab-a666-4fa2-9bed-ac92520d125b`, loại `AUTO_EDIT`.
- Nguồn: `f28532a9-3e88-536d-9e4a-d3d8d4acb0fc`, loại `UPLOAD`, không có parent, 8.428.283.732 byte.
- Tạo hard link riêng trong kho local, không sao chép thêm 8 GB; xác minh cùng tệp, cùng SHA-256 nguồn và số liên kết là 2. Dự án cũ vẫn giữ nguyên tư liệu và kết quả.
- Kiểm tra API danh sách tư liệu của dự án mới có nguồn đúng loại. URL được lưu trong `du_an_8gb_hyperframes_moi_20261104.json`.
- Bản chuẩn bị lô của dự án mới: `lo_du_an_moi_8gb_20261104.json`. Sau đối chiếu tiếng toàn nguồn đã sửa 10 nhóm sơ bộ thành 8 nội dung đầy đủ và 1 phần cuối bị ngắt. Cần căn lại mốc hook/câu kết trước khi dựng toàn lô; xem `dem_lai_kich_ban_tu_tieng_8gb_20261104.md`.

## Giới hạn

Chưa render toàn lô hoặc render lại toàn bộ khối mới. Không restart worker đang phục vụ lượt khác; mã mới cần được nạp vào worker khi điều phối lượt mới, trước khi chạy cả lô. Giữ phần nặng trên GitHub Actions, không chạy render nặng ở máy local.
