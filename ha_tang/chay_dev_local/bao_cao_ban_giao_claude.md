# Bàn giao cho Claude: chuyển dev local và worker GitHub Actions

## Phạm vi và trạng thái

Founder yêu cầu tiếp tục kế hoạch chuyển môi trường dù goal nâng chất lượng Auto Edit đang tạm dừng. Không resume goal đó. Máy local không đủ RAM cho kiểm thử nặng; chạy pytest/build/render trên Actions. Không build NAS.

Checkout đang dùng: `C:\Users\Baha Group\Documents\PRJ_069_Sin_Xay_kenh_git_push_wt_auto_edit_ui`.
Repo: `sin0235/PRJ_069_Sin_Xay_kenh`, nhánh `dev/local-remote-video-tests`. Commit mã gần nhất trước báo cáo: `3342187`.
Main chỉ nhận đăng ký hai workflow tại `f9b636a`; chưa merge mã ứng dụng của nhánh dev.

## Đã chạy thật

- FE Windows standalone build trên Actions run `41569110732` đạt, tải artifact về `ha_tang/chay_dev_local/runtime/web`.
- FE, FastAPI, Caddy, Tunnel đang chạy native. Domain giữ nguyên `https://nhap-xaykenh-prj069.bahagroup.vn`, tunnel `af83f488-df7e-4ba2-b014-f2879d9aaa49`, origin `localhost:13069`. Không sửa DNS/ingress hoặc service tunnel khác.
- API local `127.0.0.1:8001`; FE `127.0.0.1:3000`; gateway `127.0.0.1:13069`. Kiểm tra lại PID/live process trước thao tác.
- Snapshot DB và cấu hình NAS đã lấy bằng đọc SSH, không restart NAS. Local giữ cùng auth và khóa mã hóa. `/v1/auth/me` owner session 200; anonymous 401. Chưa kiểm thử đăng nhập bằng mật khẩu trên browser.
- Actions run `41569431676` thành công: tải đoạn 12 giây/105.488.867 byte từ nguồn DJI gốc qua Tunnel rồi giải mã, peak RSS 252.674.048 byte.
- Cùng run đó render HyperFrames alpha 5 giây, 1080x1920/30fps/ProRes; output 63.575.376 byte trả local và đối soát hash; peak RSS 1.875.054.592 byte. Bằng chứng JSONL ở `sin_content_api/08_kiem_thu/bang_chung/chuyen_dev_local_20261103/ket_qua_worker.jsonl`.
- Bộ remote, streaming upload và child worker từng đạt 24 test local. Hai test Range resume thêm sau đó đạt trong bộ remote 13 test. Kiểm thử toàn nhóm trên Actions run `41574384623` cần đọc kết quả thật, không suy ra pass từ trạng thái đang chạy.

## Thiết kế đã triển khai

Module `sin_content_api/src/modules/tac_vu_tu_xa/`: store SQLite riêng local, OIDC kiểm tra repo ID/ref/workflow, token theo task, lease/fencing, upload output theo khối có hash và retry, download Range resume. Runner không nhận DB, cookie Flow hay khóa 9Router.

Decorator offload tại các engine ASR/TTS/HyperFrames/timeline/Flow normalize/QC. `run_media_command` chặn FFmpeg local khi remote mode bật; bước chưa được nối báo lỗi thay vì âm thầm chạy nặng. API không tự bật worker. Launcher và runbook tại `ha_tang/chay_dev_local/`.

Workflow worker dùng child process riêng, giám sát RSS cây tiến trình, giới hạn 6 GiB, kiểm tra disk reserve và timeout. Chỉ chạy thao tác trong registry cố định. Chưa có cache input giữa các stage nên nguồn lớn có thể tải lặp.

Dev dispatch dùng `gh` đăng nhập của máy khi `REMOTE_GITHUB_DISPATCH=gh` bật tường minh. Đây là thay đổi so với đề xuất PAT ban đầu; không trích hay lưu token CLI trong ứng dụng. Runner dùng OIDC. Không đưa `.env.dev`, `.env.tunnel_token`, `data/`, `runtime/` vào git.

## Chưa hoàn tất — thứ tự tiếp tục

1. Đọc kết quả run `41574384623`, sửa lỗi nếu có. Không chạy full suite/model local. Workflow CI `kiem_tra_chuyen_local.yaml` chạy trên push nhánh dev.
2. Rà soát offload cuối nhánh: `render_project` cần biến mọi path trong shot_media/SFX thành input được cấp quyền; vừa sửa path chuỗi của shot_media, chưa E2E AI_VIDEO. Kiểm tra serializer model timeline và các asset audio/overlay.
3. Kiểm thử nguồn DJI đủ 8.428.283.732 byte qua HTTP/Tunnel, không chỉ service hoặc đoạn nhỏ. Nguồn ở `C:\Users\Baha Group\Downloads\DJI_20261027202121_0203_D.MP4`. Không dùng mẫu đã edit làm input. Kiểm tra Range đầu/cuối rồi upload chunk resume và hash đầy đủ trên runner. Runner 14 GB SSD có thể không đủ nếu giữ nhiều bản; không bỏ preflight hoặc hạ chất lượng âm thầm.
4. Tối ưu truyền tệp: hiện mỗi task tải lại input vào scratch mới, không có cache xuyên task. Có thể giữ cache theo hash trong một phiên runner với giới hạn disk, nhưng phải kiểm scope và xác minh hash; không coi cache key là quyền đọc. Không đẩy nguyên tệp gốc lên git/artifact.
5. Kiểm tra profile Flow Windows và command cũ trước bật orchestrator. API/FE chạy không có nghĩa Flow đã hoạt động: worker desktop hiện dùng Xvfb/noVNC Linux. Cần đường đăng nhập native Windows phù hợp và kiểm tra profile thật. Không copy cookie/profile NAS lên Actions. Người dùng tự đăng nhập nếu cần.
6. Import video đã edit hiện hữu từ NAS vào media local với hash để link cũ phát được. DB đã copy nhưng media chưa copy đủ; chỉ đọc NAS, không sửa/xóa nguồn bất biến.
7. Hoàn thiện vòng đời dọn dữ liệu theo tham chiếu/TTL và hủy workflow khi parent hủy; hiện token/lease ngăn chốt output cũ và heartbeat lỗi dừng child, nhưng chưa có hủy workflow tức thì từ BE.
8. Rà soát độc lập toàn thay đổi, chạy smoke Auto Edit và AI_VIDEO bằng 9Router thật rồi mới 8 GB. Lưu video cuối trên web, phân biệt `/auto-edit` và `/video-studio`, chỉ liệt kê video đã edit. Goal chất lượng nội dung vẫn tạm dừng, không tự nhận 95%.

## Vận hành và rollback

Launcher: `ha_tang/chay_dev_local/khoi_dong_local.ps1`; chọn `-ThanhPhan api|web|gateway|tunnel|worker`. Không chạy all khi chưa kiểm Flow/command cũ và RAM. API runtime đang dùng có thể cần restart để nạp bản sửa gần nhất; kiểm queue đang chạy trước restart.

PID/log nằm cạnh launcher, đã ignore. Không dừng theo tên process toàn máy. Đối chiếu PID và command line thuộc checkout. Không tắt máy hoặc NAS.

Dữ liệu bí mật chỉ ở `.env.dev`, `.env.tunnel_token`, đã hạn chế ACL. Bản backup DB trước nhập NAS có hậu tố `.before_nas_snapshot`. Không chạy lại script snapshot khi API đang dùng DB.

Browser access host không khả dụng ở lượt trước; chưa nghiệm thu browser/UI. Chỉ HTTP 200 không chứng minh membership, phát video hoặc workflow đầu-cuối đạt.

Báo cáo này ghi rõ phần đã chạy và phần chưa xong, không phải biên bản nghiệm thu toàn bộ kế hoạch.

## Kiểm chứng sau bàn giao

Actions run `41574384623` đã hoàn tất với kết luận success. Kiểm thử chuyển môi trường được thực hiện trên runner GitHub; không chạy thêm tác vụ nặng local trong lượt này.
