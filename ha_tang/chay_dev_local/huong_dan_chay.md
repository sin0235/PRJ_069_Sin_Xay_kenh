# Chạy môi trường phát triển trên máy local

FE Next.js, API FastAPI, gateway và phiên Flow ở local. GitHub Actions thực hiện kiểm thử ASR, TTS, hoạt họa, render và QC. Môi trường giữ các cổng trên loopback, dùng xác thực và DB hiện hữu; không bật bỏ qua phân quyền.

## Địa chỉ và tiến trình

| Thành phần | Địa chỉ |
|---|---|
| Giao diện và API công khai | https://nhap-xaykenh-prj069.bahagroup.vn |
| Gateway Caddy | http://127.0.0.1:13069 |
| Next.js | http://127.0.0.1:3000 |
| FastAPI | http://127.0.0.1:8001 |
| Điều khiển phiên Flow | http://127.0.0.1:8090 |

Tunnel đã có của dự án trỏ tới `localhost:13069`; không đổi DNS hoặc service Cloudflared của dự án khác.

## Khởi động lại

Từ checkout local, chạy:

```powershell
& ./ha_tang/chay_dev_local/khoi_dong_local.ps1
```

Có thể chọn một thành phần bằng `-ThanhPhan api`, `web`, `gateway`, `tunnel` hoặc `worker`. Script kiểm tra PID, không bật trùng tiến trình và không dừng tiến trình khác đang dùng PID cũ. Log và PID nằm cạnh script, được ignore.

API không khởi động model hoặc worker nặng. Tiến trình `worker` chỉ điều phối, dùng remote mode và mốc `LOCAL_DEV_JOB_CUTOFF_UTC` để giữ các job nhập từ NAS ở lịch sử. Tác vụ model/FFmpeg chưa được nối từ xa sẽ báo lỗi thay vì chạy nặng trên local.

## Build FE trên Actions

```powershell
gh workflow run build_web_local.yaml --repo sin0235/PRJ_069_Sin_Xay_kenh --ref dev/local-remote-video-tests
gh run list --repo sin0235/PRJ_069_Sin_Xay_kenh --workflow build_web_local.yaml
```

Sau khi workflow đạt, tải artifact `giao_dien_windows` vào một thư mục phát hành mới. Chỉ thay `runtime/web` khi đã kiểm tra `server.js`, thư mục `.next/static` và `public`; giữ bản phát hành cũ để quay lại. Artifact chỉ giữ một ngày; không dùng nó để lưu video.

## Kiểm thử kết nối từ xa

```powershell
python ha_tang/chay_dev_local/kiem_thu_worker_tu_xa.py --source ha_tang/chay_dev_local/runtime/nguon_dji_12s.mp4
python ha_tang/chay_dev_local/kiem_thu_worker_tu_xa.py --diagram
```

Lệnh đầu giải mã video thật trên Actions; lệnh sau dựng lại một yêu cầu diễn họa đã được LLM lập trong DB, giữ style và engine hiện hữu. Đây là kiểm thử hạ tầng, không phải nghiệm thu chất lượng toàn bộ Auto Edit.

BE gọi workflow qua GitHub CLI khi `REMOTE_GITHUB_DISPATCH=gh` được bật tường minh cho môi trường dev; không trích hoặc lưu token của CLI trong ứng dụng. Runner dùng OIDC kiểm tra repo ID, workflow và nhánh, rồi nhận token ngắn hạn giới hạn theo task.

## Dữ liệu và khôi phục

- `.env.dev`, `.env.tunnel_token` và `data/` chỉ ở local, được ignore. Không tải chúng lên Actions hoặc đưa vào artifact.
- `sao_chep_du_lieu_nas.py` chỉ đọc snapshot DB/cấu hình qua SSH. Không chạy lại khi API/worker local đang sử dụng các DB đích.
- `runtime/` chứa bản FE đã build, công cụ được đối chiếu checksum và tệp kiểm thử. Source DJI trong Downloads được giữ nguyên.
- Chưa cần thêm Appwrite vào đường chạy chính. Chọn native vì máy 8 GB RAM và Docker chưa chạy; chưa tạo thêm một stack Compose cần build trên máy này.
- Đăng nhập Google trên NAS không chuyển nguyên trạng sang Windows. Phiên Flow local cần được xác minh riêng trước kiểm thử sinh clip mới; không đưa browser profile lên Actions.
- Khi rollback, dừng đúng PID thuộc thư mục này, phục hồi bản FE/cấu hình đã lưu và khởi động lại. Giữ DB/media; không bật renderer local để thay worker từ xa.
