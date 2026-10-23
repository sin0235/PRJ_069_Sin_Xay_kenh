# Báo cáo điều phối G0/G1 và nguyên mẫu bộ tạo video

Ngày: 23/10/2026
Trạng thái: khảo sát tĩnh đã tổng hợp; nguyên mẫu luồng đã tạo; chưa nghiệm thu G0/G1 và chưa phát lease runtime.

## Kết quả các agent song song

| Agent | Phạm vi | Kết quả |
|---|---|---|
| `audit_duong_flow` | Bản đồ entrypoint tạo video/Flow và ranh giới auth | `bang_chung/bao_cao_audit_duong_flow.md` |
| `audit_harness` | Đối chiếu Harness hiện hữu với hợp đồng content-to-video | `bang_chung/bao_cao_audit_harness.md` |
| `kiem_ke_style` | Tài sản thật, trạng thái quyền/duyệt và token cần Founder chọn | `bang_chung/bao_cao_khao_sat_phong_cach.md` |

Cả ba agent chỉ đọc source/tài liệu và ghi báo cáo tách biệt. Không chạy API, LLM, provider, Flow hay kiểm thử; không đọc DB/WAL/secret; không sửa runtime.

## Kết luận hợp nhất

1. `POST /v1/media/video/generate` nhận prompt và có đường gọi Flow trực tiếp. API có Bearer/RBAC và kiểm tra workspace/project khi project được truyền, nhưng project là tùy chọn. Đường hiện tại không bắt buộc Harness, LLM, profile phong cách đã duyệt hay receipt server-side trước tác động.
2. Điều Phối Dựng có thể tái sử dụng cho timeline, draft/revision/CAS, lease, checkpoint và thao tác hậu kỳ. Nó chưa phải bộ điều phối từ content và chưa kiểm soát việc sinh shot. Nhánh Flow trong AI Jobs cũng cần được rào và kiểm tra scope trước khi mở rộng schema.
3. Có logo và màu giao diện hiện hữu, nhưng chưa có bằng chứng quyền/phiên bản video; font có hỗ trợ tiếng Việt, voice, nhạc, outro và profile theo kênh chưa được xác nhận. `baha_giai_thich_cong_nghe` vẫn là đề xuất, chưa phải style binding sản xuất.
4. Git root là `03_ban_lam_viec`. Working tree đang có nhiều file runtime và WAL/SHM đã thay đổi; đây là trạng thái sẵn có khi rà soát, không được reset hoặc ghi đè. G0 cần chụp inventory/hash và xác định process/DB/storage trước khi can thiệp tiếp.

## Nguyên mẫu

`nguyen_mau_tao_video_noi_dung.html` là file HTML độc lập trong thư mục kế hoạch. Nó minh họa brief, đổi thời lượng 60/120 giây, cảnh có timing cộng đúng mục tiêu, phần xem lời đọc/prompt dự kiến, chốt phong cách, kiểm tra Harness, preview/QC và gói bàn giao. Nút tạo video đang khóa; luồng xem trước ghi rõ là mô phỏng và không gọi API/Flow. Token UI BAHA chỉ làm vỏ tham chiếu; phong cách video vẫn hiển thị chờ Founder duyệt.

Đã kiểm tra inline JavaScript parse được; tổng thời lượng cảnh là 60 và 120 giây tương ứng; có prompt preview; không có fetch/XHR/WebSocket. Đây là kiểm tra tĩnh, chưa phải kiểm thử trình duyệt hay tích hợp giao diện sản phẩm.

## Còn thiếu trước khi cấp lease

- Hoàn tất G0 thực tế: xác nhận DB/runtime/storage/process, kiểm thử luồng cũ với tài khoản đúng quyền, baseline build/tests và bản sao phục hồi được kiểm chứng; lưu bằng chứng theo vùng ghi dự án.
- Founder duyệt prototype/storyboard 120 giây và style board: logo/quyền, palette, font có dấu tiếng Việt/license, voice hoặc `NOT_APPLICABLE`, nhạc, outro/CTA và reference frames.
- Integrator đóng băng một hợp đồng runtime duy nhất, owner/lane/hash/lease và mapping mọi entrypoint legacy trước khi phân việc code chung.
- Tất cả endpoint tạo/sửa shot phải qua cùng Harness + LLM + style snapshot + receipt server-side trước side effect; lỗi/mất cấu hình phải dừng trước Flow.

Không nâng checkpoint. Báo cáo này không xác nhận G0, G1, M-P7, video 120 giây thật hoặc nghiệm thu production.

## Ảnh chụp process/port trong lượt điều phối

Lệnh read-only `Get-Process` thấy các process `python`, `node`, `chrome` và `msedge` đang chạy; phép lọc listener không thấy cổng 8000, 8001, 3000 hoặc 20128. Không đọc command line nên chưa ánh xạ được process tới dự án hay DB cụ thể. WAL/SHM vẫn có thay đổi trong working tree. Vì vậy không kết luận API đang tắt, DB đã đóng an toàn hay có thể chạy baseline; cần người tích hợp xác định process/DB/runtime từ môi trường vận hành trước khi test hoặc backup.

## Rà soát nguyên mẫu G1 độc lập

Agent `kiem_ke_style` đối chiếu checklist G1, NO EMOJI và accessibility trong `bang_chung/bao_cao_ra_soat_nguyen_mau_g1.md`. Kết luận: phù hợp làm bản khung để xem luồng, nhưng chưa đủ đóng G1. Còn thiếu style board/binding, ba storyboard chủ đề, thao tác sửa cảnh và duyệt, chi phí/quota, gói tải, trạng thái lỗi/hủy/tiếp tục/xung đột revision, và bằng chứng duyệt Founder. Rà soát accessibility tĩnh đề nghị dùng nav semantic, live region cho nội dung cập nhật, tăng tương phản hai màu chữ nhỏ; chưa kiểm tra trình duyệt/thiết bị. Không phát hiện emoji hoặc biểu tượng Unicode.
