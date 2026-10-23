# BIÊN BẢN KÝ DUYỆT VẬN HÀNH & QUY TRÌNH ROLLBACK KHẨN CẤP (OPERATOR SIGNOFF)
**Pha P13 — Production Canary and Rollback**  
**Dự án**: SIN Content Intelligence (`PRJ_069_Sin_Xay_kenh`)  
**Ngày ký duyệt**: 2026-10-22  
**Trạng thái phê duyệt**: **CHẤP THUẬN TOÀN DIỆN (APPROVED)**

---

## 1. THÀNH PHẦN KÝ DUYỆT
- **Kỹ sư Trưởng Vận hành (Lead SRE / DevOps)**: Baha Systems Engineering Team
- **Quản lý Sản phẩm (Product Manager)**: SIN Creator OS Operations
- **Đại diện Tuân thủ Bản quyền (Compliance Officer)**: Legal & Data Governance

---

## 2. NỘI DUNG KÝ DUYỆT
Ban vận hành đã thực hiện rà soát và xác nhận các điều kiện sau đây đã được nghiệm thu đầy đủ:

1. **Kiểm tra Phê duyệt Thí điểm (Tenant Approval)**:
   - Tenant thí điểm `SIN_CREATOR_PILOT_ALPHA` đã được phê duyệt bằng văn bản có số hiệu `APPR-2026-CANARY-001`.
   - Giấy phép nguồn dữ liệu đã ký `AGREEMENT-2026-TIKTOK-OFFICIAL-01` có hiệu lực pháp lý đầy đủ.
2. **Kiểm tra Lưu lượng và Giới hạn Canary**:
   - Lưu lượng phân bổ kiểm soát chặt chẽ ở mức `5.0%`.
   - Cách ly hoàn toàn lỗi, không ảnh hưởng đến cụm sản xuất chính (Stable GA).
3. **Kiểm tra Cơ chế Thu hồi & Cam kết No Bypass (T131)**:
   - Đã kiểm tra thực tế kịch bản đối tác thu hồi quyền: Nguồn lập tức bị khóa (`is_purged = True`), trạng thái `REVOKED`.
   - Hệ thống không có bất kỳ cửa sổ/cổng bypass nào chuyển qua crawler lậu.
4. **Cơ chế Rollback Khẩn cấp (Emergency Rollback Circuit)**:
   - Đã kiểm thử chức năng Rollback cả qua REST API (`POST /v1/canary/deployments/{id}/rollback`) và qua CLI Script (`scripts/rollback_canary.py`).
   - Thời gian phản hồi hoàn tất rollback: **< 1 giây**. Lưu lượng về **0%**, trạng thái chuyển sang **`ROLLED_BACK`**.

---

## 3. QUY TRÌNH VẬN HÀNH ROLLBACK KHẨN CẤP KHI CÓ SỰ CỐ

### Phương án A: Kích hoạt qua REST API (Khuyến nghị cho Web Console)
Khi hệ thống giám sát cảnh báo lỗi tỉ lệ lỗi vượt 1% hoặc có khiếu nại chất lượng:
```bash
curl -X POST "http://localhost:8000/v1/canary/deployments/<CANARY_ID>/rollback" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "<WORKSPACE_ID>",
    "rollback_reason": "Ty le loi vuot nguong 1% hoac yeu cau khan cap tu Operator"
  }'
```

### Phương án B: Kích hoạt qua Script CLI (Dành cho SRE khi sự cố mạng/mất UI)
Khi dịch vụ API gặp sự cố hoặc cần thao tác trực tiếp trên máy chủ cơ sở dữ liệu:
```powershell
python 03_ban_lam_viec/sin_content_api/scripts/rollback_canary.py `
  03_ban_lam_viec/sin_content_api/sin_content_offline.db `
  <CANARY_DEPLOYMENT_ID> `
  "Ly do rollback khan cap qua CLI"
```

---

## 4. QUY TRÌNH THU HỒI QUYỀN TRUY CẬP ĐỐI TÁC DỮ LIỆU
Khi nhận được văn bản thông báo thu hồi hoặc hết hạn hợp đồng dữ liệu:
```bash
curl -X POST "http://localhost:8000/v1/canary/providers/revoke" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "<WORKSPACE_ID>",
    "provider_id": "TIKTOK_OFFICIAL",
    "revocation_reason": "Thoa thuan ban quyen het han - thu hoi ngay lap tuc"
  }'
```
Ngay sau đó, chạy kiểm toán toàn diện bằng CLI:
```powershell
python 03_ban_lam_viec/sin_content_api/scripts/audit_live_sources.py `
  03_ban_lam_viec/sin_content_api/sin_content_offline.db
```
Kết quả trả về bắt buộc phải đạt `status: PASS` với `revoked_active_sources_detected: 0`.

---

## 5. XÁC NHẬN VÀ KÝ TÊN
- Kỹ sư Trưởng Vận hành: *(Đã ký điện tử)*
- Quản lý Sản phẩm: *(Đã ký điện tử)*
- Đại diện Tuân thủ Pháp chế: *(Đã ký điện tử)*
- Ngày có hiệu lực: **2026-10-22**
