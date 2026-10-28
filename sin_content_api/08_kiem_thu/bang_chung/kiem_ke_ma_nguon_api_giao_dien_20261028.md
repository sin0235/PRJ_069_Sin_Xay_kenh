# Kiểm kê mã nguồn API và giao diện PRJ_069

**Ngày:** 2026-10-28  
**Phạm vi:** quét tĩnh mã nguồn trong `03_ban_lam_viec`; không khởi động ứng dụng hoặc đọc dữ liệu nghiệp vụ.

## API

Đếm được 110 khai báo route `GET`, `POST`, `PUT`, `PATCH` hoặc `DELETE` trong 17 module router:

| Module | Route |
|---|---:|
| `auth` | 1 |
| `briefs` | 5 |
| `canary_rollback` | 5 |
| `feedback` | 11 |
| `ideation` | 6 |
| `ingestion` | 4 |
| `media_studio` | 22 |
| `platform_config` | 4 |
| `research` | 6 |
| `retrieval` | 4 |
| `scripts` | 6 |
| `sources` | 7 |
| `staging_reliability` | 4 |
| `tao_video_noi_dung` | 10 |
| `understanding` | 6 |
| `voice_studio` | 7 |
| `workspaces` | 2 |

## Tác vụ nền, tải dữ liệu và giao diện

- Các worker có tên tệp rõ ràng: `media_studio/job_engine.py`, `voice_studio/worker.py`. Pipeline video nội dung chạy qua `tao_video_noi_dung/runner.py` và `service.py`.
- Các tham chiếu download/streaming media tập trung ở `media_studio/router.py`; URL download cũng được tạo bởi dịch vụ media/voice.
- `npm run build` liệt kê 43 route Next.js; danh sách cụ thể được lưu trong `kiem_thu_build_giao_dien_cloudflare_20261028.txt`.

## Giới hạn

Đây là kiểm kê dựa trên khai báo mã nguồn; chưa xác minh toàn bộ quyền của từng endpoint, luồng tải, worker, dữ liệu volume hay trạng thái ứng dụng đang chạy. Không dùng tài liệu này thay cho nghiệm thu runtime.
