# DANH SÁCH LỆNH KIỂM THỬ AN TOÀN (SAFE TEST SUITE RUNBOOK)
*Dự án:* PRJ_069_Sin_Xay_kenh  
*Mã Phase:* H00  
*Quy tắc bắt buộc:* Mọi lệnh kiểm thử offline dưới đây chạy độc lập, cấm gửi dữ liệu thật ra ngoài, cấm đòi hỏi API key sống của bên thứ ba, bảo đảm tính tất định 100%.

---

## 1. KIỂM TRA TYPECHECK & BUILD FRONTEND (sin_creator_os)

Lệnh 1: Kiểm tra lỗi kiểu TypeScript toàn bộ dự án
```powershell
cd C:\PRJ_069_Sin_Xay_kenh\03_ban_lam_viec\sin_creator_os
pnpm exec tsc --noEmit
```
*Kỳ vọng:* Exit code 0, 0 errors.

Lệnh 2: Biên dịch Production Next.js Turbopack
```powershell
cd C:\PRJ_069_Sin_Xay_kenh\03_ban_lam_viec\sin_creator_os
pnpm run build
```
*Kỳ vọng:* Exit code 0, 41/41 routes compiled successfully.

---

## 2. BỘ TEST BACKEND HIỆN HỮU TIỀN NHIỆM (sin_content_api)

Lệnh 3: Hồi quy toàn bộ Media Studio & Video Processor (38 tests)
```powershell
cd C:\PRJ_069_Sin_Xay_kenh\03_ban_lam_viec\sin_content_api
python -m pytest -q tests/test_media_studio_p1.py tests/test_media_studio_video.py
```
*Kỳ vọng:* Exit code 0, 38/38 tests PASSED (100% Green).

Lệnh 4: Hồi quy Flow Music & Audio QC (13 tests)
```powershell
cd C:\PRJ_069_Sin_Xay_kenh\03_ban_lam_viec\sin_content_api
python -m pytest -q tests/test_media_studio_music.py
```
*Kỳ vọng:* Exit code 0, 13/13 tests PASSED.

---

## 3. DANH SÁCH TEST HARNESS MỚI SẼ TRIỂN KHAI (THEO TỪNG TASK)

| Tên File Test Mới | Task Chịu Trách Nhiệm | Phạm Vi Kiểm Thử |
|---|---|---|
| `tests/test_harness_hop_dong.py` | Task T03 (Phase H03) | Khế ước schema, timebase rational V2, VFR PTS mapping, reject invalid data |
| `tests/test_harness_phien_dung.py` | Task T04 (Phase H04) | Phiên dựng, tool broker, CAS concurrency, idempotency, restart recovery |
| `tests/test_harness_hieu_tu_lieu.py` | Task T05 (Phase H05) | Hiểu tư liệu ASR, word timestamps, visual evidence, cache isolation |
| `tests/test_harness_thao_tac.py` | Task T06A (Phase H06A) | Dựng thời gian, split, trim, ripple, slip, 3 video layers, 4 audio layers |
| `tests/test_harness_am_thanh_phu_de.py` | Task T06B (Phase H06B) | Sync thoại/nhạc/SFX, J/L cuts, auto-ducking, phụ đề tiếng Việt, safe zone |
| `tests/test_harness_hau_ky_hinh.py` | Task T06C (Phase H06C) | Transform, keyframes, color LUT, masking, tracking ROI |
| `tests/test_harness_da_camera.py` | Task T06D (Phase H06D) | Retime, speed, freeze, reverse, 2 camera multicam sync |
| `tests/test_harness_dao_dien.py` | Task T07 (Phase H07) | Agent lập kế hoạch dựng, sửa theo phản hồi, giới hạn phiên |
| `tests/test_harness_sua_flow.py` | Task T08 (Phase H08) | Sửa cảnh qua Flow assisted receipt và Gemini API chính thức |
| `tests/test_harness_ban_giao.py` | Task T09 (Phase H09) | Bàn giao NLE, relink, native-bound roundtrip sửa tiếp |
| `tests/test_harness_bien_the.py` | Task T10 (Phase H10) | UI studio, brand kit, preset tỷ lệ khung hình, variants |
| `tests/test_harness_kiem_dinh.py` | Task T11 (Phase H11) | Kiểm định độc lập, full decode, EBU R128, injection guard, tamper detection |

*Lưu ý bảo mật:* Tuyệt đối không bật cờ `BAHA_HARNESS_LIVE=1` trong môi trường tự động kiểm thử offline.
