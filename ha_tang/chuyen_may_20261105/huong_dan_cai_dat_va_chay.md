# Chuyển máy và chạy lại PRJ_069 trên Windows

Ngày đối chiếu: 05/11/2026. Tài liệu dành cho máy Windows mới, khôi phục dữ liệu hiện hữu và tiếp tục môi trường phát triển dùng dịch vụ thật.

## 1. Chọn đúng bản bàn giao

Nguồn đang sử dụng khi đóng gói:

```text
C:\Users\Baha Group\Documents\PRJ_069_Sin_Xay_kenh_git_push_wt_auto_edit_ui
Nhánh: dev/local-remote-video-tests
HEAD: 951caf6bea2dece985399e6af51c439cd198370d
```

Nguồn có thay đổi chưa commit và mã mới chưa tracked; `ma_nguon` mới là bản mã đầy đủ tại thời điểm bàn giao. Không chỉ clone HEAD rồi bỏ qua bản chụp này. `C:\PRJ_069_Sin_Xay_kenh` là bản cũ tháng 10.

Gói NAS nằm trong `90_sao_luu/02_chuyen_may/chuyen_may_20261105_<thoi_diem>`. Chọn thư mục có biên bản và danh mục kiểm tra hoàn tất do người đóng gói cung cấp; đường dẫn chính xác được ghi trong chỉ mục gói.

| Thành phần gói | Nội dung cần dùng |
|---|---|
| `ma_nguon` | Mã hiện hành, gồm thay đổi chưa commit và mã mới |
| `du_lieu/data` | Bản sao SQLite nhất quán và dữ liệu vận hành được giữ |
| `du_lieu/media_assets` | Media ứng với các bản ghi tài sản |
| `cau_hinh_rieng` | Cấu hình riêng, khóa và token; chỉ người có quyền được đọc |
| `runtime` | Bản web standalone, công cụ và dữ liệu runtime được liệt kê |
| `git` | HEAD/nhánh/trạng thái, bản vá và cấu hình sparse checkout; lịch sử offline tùy mức có sẵn |
| `tu_lieu_ngoai` | Nội dung kịch bản bên ngoài và tư liệu được đóng gói |

Kiểm tra checksum theo danh mục gói trước khi giải nén. Không mở hoặc gửi nội dung tệp bí mật vào chat, email, Git hay artifact Actions.

## 2. Chế độ cần giữ nguyên

Đường chạy hiện hành gồm giao diện/API/Flow trên Windows, xử lý model và dựng video trên GitHub Actions. Đây là kiểm thử E2E dùng provider thật, tài khoản thật và dữ liệu hiện hữu.

Local đang dùng `APP_ENV=production`, `TESTING=0`, `DEV_AUTH_BYPASS=0`, `SYNTHETIC_DATA_ALLOWED=false`, `REMOTE_COMPUTE_MODE=github`. Các giá trị này giữ rào chắn xác thực. Runner Actions tự đặt `APP_ENV=test`, `TESTING=1` cho tác vụ nhận từ local.

Không dùng hướng dẫn E2E tháng 10 với DB `sin_content_e2e_test.db`, token dev hoặc cờ bỏ qua đăng nhập. Không tự đổi cờ bảo mật để làm trang đăng nhập hoạt động.

Chỉ cho một máy điều phối Flow/tunnel/lô video hoạt động. Trước khi chuyển quyền chạy, kiểm tra job đang làm và dừng đúng tiến trình dự án trên máy cũ; không bật hai bản worker với DB sao chép cùng một lô.

## 3. Công cụ trên máy mới

| Công cụ | Bản đã đối chiếu / cách dùng |
|---|---|
| Python | Máy cũ 3.11.9; workflow dùng 3.11 |
| Node.js | Workflow build dùng 22; máy cũ đang dùng 24.19.0 |
| npm | Máy cũ 11.17.0; dùng `package-lock.json` và `npm ci` khi cần cài source |
| Git và GitHub CLI | Máy cũ gh 2.102.0; tài khoản cần quyền repo và Actions |
| Microsoft Edge | Flow dùng channel `msedge`, cần đăng nhập Google lại |
| 9Router | Cổng 20128; khôi phục cấu hình/tài khoản theo ứng dụng |
| Cloudflared | Có trong PATH; dùng token của đúng tunnel dự án |
| Caddy | Launcher dùng `runtime/tools/caddy/caddy.exe` |
| FFmpeg và ffprobe | Có trong PATH nếu chạy công cụ media local |

Ưu tiên đường dẫn ngắn như `C:\PRJ069` để tránh giới hạn đường dẫn Windows. Máy cũ có 8 GB RAM nên build web và xử lý nặng chạy trên Actions.

Tạo môi trường Python từ thư mục mã mới:

```powershell
Set-Location C:\PRJ069
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r sin_content_api/requirements.txt
python -m pip install python-multipart soundfile numpy
```

Nếu chính sách PowerShell chặn activation, mở terminal được phép theo chính sách máy hoặc dùng trực tiếp `.venv\Scripts\python.exe`; launcher hiện tìm `python` trong PATH nên phải bảo đảm nó chọn môi trường vừa cài.

Danh sách trên là các gói local được đối chiếu, chưa được nghiệm thu trên Windows sạch. `requirements.txt` có các ràng buộc mở; `requirements.nas.lock` dành cho môi trường NAS/model, không mặc định là bản khóa Windows. Không sao chép `.venv` từ máy cũ.

TTS VieNeu không được cài trên máy local hiện tại. Workflow `kiem_thu_video_tu_xa.yaml` cài model và công cụ cần cho runner: FFmpeg/fonts, Chromium, `vieneu==3.8.3`, `onnxruntime==1.28.0`, HyperFrames `0.8.222`, Remotion `4.0.535`.

## 4. Khôi phục mã, dữ liệu và web

1. Chép nội dung `ma_nguon` vào `C:\PRJ069`, giữ tên thư mục và tệp ẩn được liệt kê trong gói.
2. Chép ba DB từ `du_lieu/data` vào `ha_tang/chay_dev_local/data`: `sin_content_production.db`, `baha_auth_production.db`, `sin_dieu_phoi_dung.db`.
3. Chép `du_lieu/media_assets` vào `ha_tang/chay_dev_local/data/media_assets`; giữ nguyên cấu trúc storage key.
4. Khôi phục dữ liệu lô và tiến độ runtime theo chỉ mục gói. Không đổi tên asset hoặc tạo DB rỗng thay DB thiếu.
5. Đặt `.env.dev` và `.env.tunnel_token` đúng tại `ha_tang/chay_dev_local/`, hạn chế quyền đọc cho tài khoản vận hành.
6. Khôi phục web vào `ha_tang/chay_dev_local/runtime/web`, công cụ vào `ha_tang/chay_dev_local/runtime/tools` theo chỉ mục.

Ba DB là snapshot riêng từng tệp, không phải giao dịch chung giữa ba DB. Khi đóng gói máy cũ đang hoạt động, đọc ghi chú thời điểm snapshot và kiểm tra tiến độ job trước khi tiếp tục.

Web standalone phải có `server.js`, `public`, `.next/static` và dependency đã đóng gói. Không cần build toàn bộ frontend để mở lại bản này. Không chép thư mục cache `.next` của cây source thay cho bản standalone.

```powershell
Test-Path ha_tang/chay_dev_local/runtime/web/server.js
Test-Path ha_tang/chay_dev_local/runtime/web/.next/static
Test-Path ha_tang/chay_dev_local/runtime/web/public
Test-Path ha_tang/chay_dev_local/runtime/tools/caddy/caddy.exe
```

Tệp `.git` của nguồn ban đầu là con trỏ worktree; không mang con trỏ đó sang máy mới rồi coi là repository độc lập. Repository gốc dùng partial clone `blob:none` và sparse checkout; nhiều tệp tracked/đối tượng chưa được tải. `ma_nguon` giữ các tệp thực sự hiện hữu của checkout, không hứa chứa toàn bộ kho hoặc toàn bộ lịch sử offline.

Để tiếp tục phát triển với Git, clone remote vào thư mục riêng rồi đối chiếu HEAD/trạng thái và phủ mã `ma_nguon` theo biên bản:

```powershell
git clone --branch dev/local-remote-video-tests https://github.com/sin0235/PRJ_069_Sin_Xay_kenh.git C:\PRJ069_git
git -C C:\PRJ069_git rev-parse HEAD
```

Nhánh remote có thể đã tiến thêm; dùng HEAD và bản vá trong gói để đối chiếu trước khi ghép thay đổi. Bản sao Git offline nếu có chỉ bảo đảm những object đã lưu và được xác minh trong biên bản. Khôi phục chạy bằng `ma_nguon` không phụ thuộc con trỏ `.git` cũ.

## 5. Sửa đường dẫn trước khi khởi động

Mở cấu hình riêng bằng trình soạn thảo local; chỉ sửa đường dẫn và thông số máy, giữ khóa mã hóa và định danh hệ thống.

| Mục | Đích cần đối chiếu |
|---|---|
| `DATABASE_URL` | `sqlite:///C:/PRJ069/ha_tang/chay_dev_local/data/sin_content_production.db` |
| `BAHA_AUTH_DATABASE_URL` | DB auth cùng thư mục |
| `SIN_DUNG_DB_PATH` | `.../data/sin_dieu_phoi_dung.db` |
| `MEDIA_ROOT_DIR` | `.../data/media_assets` |
| `WORKER_HEARTBEAT_PATH` | `.../data/runtime/worker.json` |
| `FLOW_PROFILE_ROOT` | Profile riêng của máy mới; máy cũ dùng `C:/Users/Baha Group/prj069_flow` |
| `REMOTE_GITHUB_REF` | Nhánh đã chứa mã remote tương thích bản bàn giao |
| `LOCAL_DEV_JOB_CUTOFF_UTC` | Giữ mốc hiện có khi tiếp tục lịch sử; không tự đặt lại để chạy toàn bộ job cũ |

Tìm tham chiếu đường dẫn cũ trong cấu hình, mã vận hành và manifest tư liệu, nhưng không xuất nội dung bí mật ra log. Kiểm tra thêm đường dẫn Python/Node/FFmpeg, tệp khóa, trình duyệt, ổ đĩa, profile và worktree.

`ha_tang/chay_dev_local/lo_video_noi_dung.py` đang có đường dẫn nội dung tuyệt đối tại dòng 35 đến `C:/Users/Baha Group/Documents/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/kich_ban/noi_dung_abstract_2026`. Khôi phục tư liệu `tu_lieu_ngoai` rồi cập nhật đường dẫn này trước khi dùng tiện ích lô.

`runtime/mo_dang_nhap_flow.py` tìm Edge ở hai vị trí Program Files chuẩn. `kiem_tra_cau_hinh.py` còn kiểm cookie ở `data/flow_profiles`, trong khi `FLOW_PROFILE_ROOT` hiện trỏ ra ngoài checkout; cảnh báo cookie từ tiện ích này chưa chứng minh profile đang dùng mất đăng nhập.

Giữ nguyên `BAHA_AUTH_JWT_SECRET`, issuer/audience và `LLM_ENCRYPTION_MASTER_KEY` đi cùng DB. Đổi khóa không có kế hoạch sẽ làm phiên hoặc cấu hình LLM mã hóa không đọc được.

## 6. Tài khoản, Flow và tunnel

```powershell
gh auth login
gh auth status
```

Dùng tài khoản có quyền `sin0235/PRJ_069_Sin_Xay_kenh` và dispatch workflow trên nhánh cấu hình. Không trích token GitHub CLI vào `.env`.

Cài/khôi phục 9Router theo ứng dụng, đăng nhập lại các provider cần dùng và xác minh cổng 20128. Trạng thái riêng máy cũ nằm tại `%APPDATA%\9router`; mã hóa/đăng nhập có thể phụ thuộc user nên cần xác thực lại. Launcher chỉ thử mở CLI `9router` đã cài; nó không tự cài hoặc phục hồi tài khoản. Không thay API key trong DB chỉ vì máy đổi.

Profile Edge/cookie có thể bị ràng buộc tài khoản Windows; bản sao không bảo đảm đăng nhập còn hiệu lực. Mở phiên Flow của đúng workspace qua giao diện hoặc tiện ích được khôi phục:

```powershell
python ha_tang/chay_dev_local/runtime/mo_dang_nhap_flow.py
```

Chỉ chạy lệnh trên nếu tệp có trong gói và đã cập nhật đường dẫn. Đăng nhập Google thủ công; không gửi profile hoặc cookie lên Actions.

Tunnel hiện có trỏ `localhost:13069`. Chuyển tunnel sang máy mới sau khi máy cũ nhường quyền; không đổi DNS hoặc dừng tunnel dự án khác. Token chỉ đặt trong `.env.tunnel_token` theo launcher.

## 7. Khởi động có kiểm soát

Trước tiên đọc trạng thái lô, job đang chạy và tiến độ trong bản bàn giao. Worker khi khởi động có thể nhận việc, tạo yêu cầu LLM/Flow và tiêu thụ tín dụng. Không dùng khởi động worker như một kiểm tra miễn phí.

Để kiểm tra API/web trước, chưa bật worker hoặc tunnel:

```powershell
& ./ha_tang/chay_dev_local/khoi_dong_local.ps1 -ThanhPhan api
& ./ha_tang/chay_dev_local/khoi_dong_local.ps1 -ThanhPhan web
& ./ha_tang/chay_dev_local/khoi_dong_local.ps1 -ThanhPhan gateway
```

API/worker có thể chạy migration hiện hữu khi khởi động; chỉ khởi động sau khi xác nhận DB là bản phục hồi đúng và đã giữ backup. Không chạy `chay_he_thong_offline.ps1` hoặc launcher cũ để thay đường chạy này.

Sau khi đã đối chiếu hàng đợi và cho máy mới tiếp quản:

```powershell
& ./ha_tang/chay_dev_local/chay_he_thong.ps1 -KhongMoTrinhDuyet
```

Lệnh này mở 9Router nếu cần, API, worker nội dung, web, gateway và tunnel; kiểm tra trạng thái rồi báo kết quả. `-SuaLLM` sửa cấu hình LLM trong DB; chỉ dùng khi đã xác nhận cần đổi host. `-CapNhatGiaoDien` dispatch build mới trên Actions; không cần cho lần khôi phục standalone.

Auto Edit có worker riêng `python ha_tang/chay_dev_local/chay_worker_auto_edit.py`; launcher `all` hiện không mở tiến trình này. Chỉ bật khi máy cũ đã dừng worker tương ứng và lô cần tiếp tục đã được đối chiếu. Không chạy lại tiện ích tạo lô chỉ để kiểm tra đăng nhập.

## 8. Kiểm tra nhẹ và địa chỉ sử dụng

| Thành phần | Địa chỉ |
|---|---|
| FastAPI | `http://127.0.0.1:8001` |
| Next standalone | `http://127.0.0.1:3000` |
| Caddy gateway | `http://127.0.0.1:13069` |
| Worker/điều khiển Flow | `http://127.0.0.1:8090` |
| Đăng nhập và thao tác | `https://nhap-xaykenh-prj069.bahagroup.vn` |

```powershell
Invoke-RestMethod http://127.0.0.1:8001/healthz
Invoke-RestMethod http://127.0.0.1:8001/readyz
(Invoke-WebRequest http://127.0.0.1:3000 -UseBasicParsing).StatusCode
(Invoke-WebRequest http://127.0.0.1:13069/healthz -UseBasicParsing).StatusCode
```

Các lệnh HTTP trên không tạo video. Nếu chưa bật worker, `/readyz` có thể báo worker chưa sẵn sàng; đọc lỗi thành phần thay vì tạo run mới. Kiểm tra trên domain: đăng nhập, mở lịch sử dự án, phát video đã có và thử seek. Không bấm tạo storyboard/video hoặc chạy kiểm thử remote trong bước smoke check.

Domain được giữ trong allowed origins/cookie secure. Localhost là địa chỉ kiểm tra hạ tầng; đăng nhập trên đó có thể bị chặn Origin theo cấu hình hiện hành.

Log/PID nằm tại `ha_tang/chay_dev_local`. Không phục hồi PID cũ như tiến trình hợp lệ. Dừng các thành phần do launcher quản lý bằng `chay_he_thong.ps1 -Dung`; lệnh này giữ 9Router và không quản lý worker Auto Edit riêng.

## 9. Cập nhật và quay lại

Khi cần build web mới, đẩy đúng mã đã đối chiếu lên nhánh rồi dùng workflow `build_web_local.yaml` hoặc `chay_he_thong.ps1 -CapNhatGiaoDien`. Workflow dùng Node 22, `npm ci`, `npm run build`; artifact `giao_dien_windows` chỉ giữ một ngày.

Giữ bản standalone cũ và DB backup trước cập nhật. Nếu thất bại, dừng đúng PID thuộc dự án, trả lại bản web/cấu hình đã lưu và đối chiếu DB/media trước khi mở worker. Không bật renderer local hoặc đổi sang dữ liệu giả để vượt lỗi remote.

Bản hướng dẫn được lập từ mã, launcher và cấu hình ngày 05/11/2026; chưa nghiệm thu cài đặt trên một máy Windows sạch. Danh mục/checksum và biên bản gói NAS là căn cứ xác nhận tệp thực sự đã bàn giao.
