# Triển khai PRJ_069 v2 lên NAS (dự án mới, không dùng bản kiểm thử cũ)

Thư mục này là một dự án Container Manager độc lập tên `prj069_v2`. Không dùng lại project `prj069_nas_kiem_thu_that`, `prj069_flow_login` hay volume của chúng.

## 1. Những lỗi của bản cũ và cách bản mới xử lý

| Lỗi quan sát được | Nguyên nhân tìm thấy trong mã và cấu hình | Cách xử lý ở v2 |
|---|---|---|
| Lỗi xác thực | Đăng nhập tin vào ID người dùng cố định trong mã, có mật khẩu dự phòng cứng `BahaGroup@2026` và khóa JWT mặc định trong mã; production chỉ nhận header Cloudflare nên không đăng nhập được | Đăng nhập lấy ID từ Baha Auth DB; bỏ mật khẩu dự phòng; production trả 503 thay vì dùng khóa JWT mặc định khi thiếu cấu hình; dùng `AUTH_MODE=local_password` với hash trong `.env` |
| Không đọc được database | Volume được nạp từ DB E2E có 122 workspace và 245 người dùng thử; DB live không có Founder; initializer cũ từng ghi đè DB; hash mật khẩu bị Compose nuốt dấu `$` | Initializer chế độ `sach` tạo DB trống: 1 Founder, 1 workspace, 4 vai trò mẫu, 1 policy ACTIVE; chạy lại không ghi đè; hash đặt trong nháy đơn |
| API treo, health check timeout, job TTS bị ngắt | `--reload` và mount mã nguồn từ NAS (sửa file là API tự khởi động lại, giết job); chạy dev server Next.js; NAS quá tải | Bỏ `--reload`, bỏ mount mã; FE chạy bản build production; giới hạn RAM và log; health check dùng `/healthz` với `start_period` 180 giây |
| TTS lỗi | Image cũ thiếu `ffprobe`; model Hugging Face tải lại mỗi lần dựng container | Image dựng từ Dockerfile có FFmpeg; cache model nằm trong volume `/data/cache/vieneu` |
| Chưa nối Flow | API dùng volume hồ sơ khác container đăng nhập; mặc định gọi `msedge` không có trong image | Một volume `prj069_v2_flow_profiles` dùng chung; image API cài sẵn Chromium; `BROWSER_CHANNEL=chromium` |
| Script báo "đang chạy" khi API treo | `kiem_tra_trang_thai_nas.py` chỉ cần cổng TCP mở | Đã sửa: chỉ báo thành công khi `/healthz` trả 200 |

## 2. Việc làm một lần trên máy làm việc

1. Dừng project cũ `prj069_nas_kiem_thu_that` trong Container Manager (giải phóng cổng 3069 và 8069 và CPU). Chưa xóa volume cũ.
2. Tạo cấu hình bí mật:

   ```powershell
   cd Z:\01_du_an\PRJ_069_Sin_Xay_kenh\03_ban_lam_viec\ha_tang\nas_trien_khai_sach
   python tao_cau_hinh.py --nas-host 192.168.1.175
   ```

   Lệnh hỏi mật khẩu Founder (từ 12 ký tự), tạo `.env` và `secrets\9rt.env` (khóa LLM lấy từ `..\nas_kiem_thu_that\9rt.env`). Hai tệp này đã nằm trong `.gitignore`. Lệnh từ chối chạy nếu `.env` đã tồn tại.

## 3. Dựng image

Container Manager trên NAS đang quá tải khi build (Next.js build và cài Chromium rất nặng), nên nên build trên máy có Docker Desktop rồi nạp vào NAS. Trước hết xác nhận kiến trúc CPU của NAS trong DSM (Thông tin hệ thống): máy làm việc là x86_64, nếu NAS là ARM thì phải build trực tiếp trên NAS.

```powershell
docker compose build
docker save prj069-sin-api:v2 prj069-sin-fe:v2 -o prj069_v2_images.tar
```

Trong DSM: Container Manager, Image, Add, From File, chọn `prj069_v2_images.tar`. Nếu DSM vẫn tự build lại khi tạo project thì chấp nhận, hoặc build trực tiếp trên NAS lúc NAS rảnh.

## 4. Tạo project và chạy

1. Container Manager, Project, Create. Tên `prj069_v2`, đường dẫn `/volume1/09.ai_workspace/01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ha_tang/nas_trien_khai_sach`, dùng file Compose có sẵn.
2. Start. Thứ tự tự động: `khoi_tao` chạy một lần rồi thoát mã 0; `api` khởi động (lần đầu có thể mất 2 đến 3 phút); `web` chờ `api` healthy.
3. Kiểm tra từ máy làm việc:

   ```powershell
   python kiem_tra_sau_trien_khai.py --api http://192.168.1.175:8069 --web http://192.168.1.175:3069
   ```

   Script hỏi mật khẩu Founder và kiểm tra: health, môi trường production, bypass đã tắt, sai mật khẩu bị từ chối, đăng nhập, đọc Auth DB, ba API TTS, trang đăng nhập và proxy `/v1/*` của giao diện. Thoát mã 0 chỉ khi mọi bước đạt.
4. Mở `http://192.168.1.175:3069/auth/v1/login` và đăng nhập bằng `phuctoan235@gmail.com`.

## 5. Đăng nhập Google Flow (làm một lần, lặp lại khi phiên hết hạn)

Máy hiện không SSH vào NAS được, nên mở noVNC trực tiếp trong LAN. Vì noVNC mặc định không có mật khẩu, phải đặt mật khẩu trong `.env` trước:

```
FLOW_VNC_BIND=192.168.1.175
FLOW_VNC_PASSWORD=<mật khẩu riêng, không trùng mật khẩu Founder>
```

1. Tạm dừng mọi tác vụ Flow trên API (hồ sơ trình duyệt có khóa, một lúc chỉ một tiến trình dùng).
2. Tạo project phụ `prj069_v2_flow_login` từ `docker-compose.dang_nhap_flow.yml` cùng thư mục, Start.
3. Mở `http://192.168.1.175:6080/vnc.html?autoconnect=1&resize=scale`, nhập mật khẩu noVNC, đăng nhập Google trong Chromium, đóng Chromium để lưu phiên.
4. Dừng và xóa project phụ, rồi xóa hai dòng `FLOW_VNC_*` khỏi `.env` để cổng 6080 không còn mở ra LAN.

## 6. TTS lần đầu

VieNeu tải model từ Hugging Face ở lần chạy đầu (NAS phải ra được Internet), có thể mất vài phút; từ lần sau model nằm trong volume. Trong lúc có job đang chạy không khởi động lại API và không gửi nhiều job cùng lúc. Job đầu tiên là phép thử thật: nghe lại file WAV thay vì chỉ tin trạng thái SUCCEEDED.

## 7. Dữ liệu và sao lưu

- DB và media nằm trong volume `prj069_v2_du_lieu`; hồ sơ Flow trong `prj069_v2_flow_profiles`. Dựng lại container không làm mất dữ liệu; không dùng thao tác xóa volume.
- v2 bắt đầu sạch: media và DB của bản kiểm thử cũ không được chuyển sang. Cần giữ phần nào thì chép tay có đối soát; không xóa volume cũ `prj069_nas_kiem_thu_that_data` trước khi quyết định.
- Sao lưu định kỳ hai volume trên bằng Hyper Backup hoặc công cụ sao lưu volume Docker của NAS. Đường dẫn thật của volume phải xác nhận trên máy (thường dưới `/volume1/@docker/volumes/`).

## 8. Gỡ lỗi nhanh

| Triệu chứng | Kiểm tra |
|---|---|
| `khoi_tao` thoát mã khác 0 | Xem log container: thông báo ghi rõ biến thiếu hoặc không hợp lệ (hash, khóa, model phải là `cx/gpt-6-luna`, endpoint HTTPS `/v1`) |
| Đăng nhập báo 403 | Founder chưa có trong Auth DB: `khoi_tao` chưa chạy xong hoặc dùng volume khác |
| Đăng nhập báo 503 | Thiếu biến trong `.env` (FOUNDER_*, SIN_WORKSPACE_ID, BAHA_AUTH_JWT_*) |
| `api` unhealthy | Đợi hết `start_period`; xem log, rồi RAM/CPU container. Nếu CPU NAS còn cao, tắt các project cũ |
| Giao diện hiện Lỗi API 500 | Container `api` đã dừng hoặc chưa healthy; giao diện vẫn phục vụ được nên dễ nhầm |
| Flow báo cần đăng nhập | Phiên hết hạn hoặc hồ sơ bị khóa bởi project đăng nhập đang bật |

## 9. Chưa được kiểm chứng (đọc trước khi tin là xong)

- Chưa build image nào: Docker daemon trên máy làm việc đang tắt khi chuẩn bị; mới kiểm tra `docker compose config` hợp lệ.
- Chưa chạy trên NAS thật. Đã chạy API ở chế độ production trên máy làm việc với DB sạch do initializer tạo: 11/11 bước của `kiem_tra_sau_trien_khai.py` đạt (không qua Docker, không qua giao diện).
- Chưa kiểm tra: Next.js build trong image, hồ sơ Chromium dùng chung giữa image đăng nhập (Ubuntu) và image API (Debian), tải model VieNeu trên NAS, âm thanh TTS thật, phiên Google Flow thật.
- Bằng chứng: `03_ban_lam_viec/sin_content_api/08_kiem_thu/bang_chung/chuan_bi_nas_trien_khai_sach_20261028.md`.
