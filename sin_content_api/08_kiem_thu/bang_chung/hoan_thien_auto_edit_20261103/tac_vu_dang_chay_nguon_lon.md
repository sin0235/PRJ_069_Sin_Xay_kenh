# Tác vụ đang chạy từ nguồn lớn

Đây là bản ghi tiếp quản, không phải biên bản đạt nghiệm thu.

- Actions run: `41659870643`, commit `0b58a38`.
- Render cảnh KINETIC_TITLE do LLM thật chọn: task `d1eb47b3-59b7-47a9-90e6-d4256b30dd43` đã SUCCEEDED; đã nhận MOV và xem ba khung, chi tiết trong tich_hop_canh_khoi_auto_edit.md.
- Tách tiếng từ asset UPLOAD gốc 8.428.283.732 byte `c15a3ad0-811a-4f96-861b-630549dab417`: task `c3449679-f78f-4fb2-9a4b-eec392588268`, lần kiểm tra gần nhất QUEUED sau task render. Không lấy MP4 đã edit làm nguồn.
- Tiến trình local điều phối render exec session `26014` đã kết thúc exit 0; điều phối tách tiếng rồi nhận dạng có exec session `54699`. Cần kiểm tra handle và hàng đợi thực tế khi tiếp quản, không khởi động lại chỉ vì chưa có output.
- Script runtime `nhan_dang_nguon_8gb.py` dùng offload extract_audio rồi transcribe_words. Chỉ gọi nhận dạng sau khi WAV thực tế được tải về và kiểm tra mono 16 kHz. Nếu có transcript hoàn thành sẽ không tự ghi đè hoặc chạy lại. Script render cảnh khối là `render_canh_khoi_llm_that.py`.
- File dự kiến nằm trong runtime local: `nguon_8gb_tieng_goc.wav`, `nguon_8gb_tu.json`, `canh_khoi_llm_that.mov`. Tên file dự kiến không chứng minh task đã thành công.
- Local chỉ hash đầu vào theo khối, chờ và lưu kết quả. Quan sát hai tiến trình điều phối khoảng 81–84 MB RSS; chưa có số peak của toàn lượt. Runner chỉ claim một tác vụ nặng mỗi lần và kiểm tra dung lượng trước khi tải đầu vào.
- Chưa xác minh render cảnh khối mới, chưa có transcript toàn nguồn, chưa LLM chia kịch bản toàn nguồn hoặc xuất video hoàn chỉnh từ nguồn 8 GB.
- Flow chưa gọi thêm: đang chờ Founder chọn tài khoản. Email hồ sơ Edge chính là `phuctoan235@gmail.com`; tài khoản Google đã quan sát trong Flow hệ thống là `tranthaomy235@gmail.com`. Email hồ sơ Edge không tự chứng minh tài khoản Google bên trong trang Flow.

## Cập nhật kết thúc tác vụ tách tiếng

Task `c3449679-f78f-4fb2-9a4b-eec392588268` đã FAILED với `REMOTE_DISK_BUDGET_EXCEEDED`; session local `54699` kết thúc exit 1. Không còn là tác vụ đang chờ. Preflight runner yêu cầu dung lượng tổng đầu vào cộng 3 GiB; không đủ nên dừng trước tải file. Chưa có WAV hoặc transcript toàn nguồn.

Đã thêm bước giải phóng ba toolchain không dùng (.NET, Android, GHC) trên VM GitHub-hosted trước cài dependencies; có điều kiện RUNNER_ENVIRONMENT=github-hosted và ghi df trước/sau. Không tác động local, NAS, tool cache Python/Node hoặc workspace dự án. YAML parse và kiểm thứ tự bước đạt; cần một run mới để biết dung lượng thu hồi thực tế và thử lại nguồn lớn. Không hạ mức dự phòng dung lượng để ép task chạy.
