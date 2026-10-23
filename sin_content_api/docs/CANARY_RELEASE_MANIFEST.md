# KẾ HOẠCH PHÁT HÀNH CANARY VÀ GIẢI PHÁP ROLLBACK KHẨN CẤP (CANARY RELEASE MANIFEST)
**Pha P13 — Production Canary and Rollback**  
**Dự án**: SIN Content Intelligence (`PRJ_069_Sin_Xay_kenh`)  
**Ngày ban hành**: 2026-10-22  
**Mã kiểm thử nghiệm thu**: T130, T131  
**Exit Gate**: `authorized_canary_quality_verified_and_rollback_tested`

---

## 1. MỤC TIÊU VÀ PHẠM VI ÁP DỤNG
Tài liệu này xác lập cấu hình triển khai thử nghiệm thực tế có kiểm soát (Canary Deployment) cho một nhóm khách hàng thí điểm được phê duyệt văn bản, đảm bảo an toàn tuyệt đối cho hệ thống sản xuất.

- **Môi trường**: Production Canary Isolated Ring.
- **Tỷ lệ phân bổ lưu lượng (Traffic Split)**: Ban đầu 5% (tối đa 10% trong giai đoạn thí điểm).
- **Điều kiện tiên quyết**:
  - Bắt buộc có mã phê duyệt của người vận hành/khách hàng (`human_approval_id`).
  - Bắt buộc có căn cứ thỏa thuận bản quyền dữ liệu hợp pháp đã ký (`signed_rights_reference`).
  - Sẵn sàng kích hoạt cơ chế rollback tức thì (`is_rollback_ready = True`).

---

## 2. KIẾN TRÚC CANARY VÀ NGUYÊN TẮC BẢO MẬT

```
+---------------------------------------------------------------------------------+
|                        INCOMING TENANT REQUESTS                                 |
+---------------------------------------------------------------------------------+
                                      |
                       +--------------+--------------+
                       |  Canary Router / Gateway    |
                       +--------------+--------------+
                                      |
               +----------------------+----------------------+
               | (95% Standard Traffic)                      | (5% Canary Traffic)
               v                                             v
      +------------------+                          +------------------+
      | Production Ring  |                          |   Canary Ring    |
      |   (Stable GA)    |                          | (Approved Tenant)|
      +------------------+                          +------------------+
                                                             |
                                            +----------------+----------------+
                                            | Real Source IDs Tracking        |
                                            | Complete Data Lineage           |
                                            | Quota Cost Accounting           |
                                            | Human Quality Review Output     |
                                            +---------------------------------+
                                                             |
                                            +----------------+----------------+
                                            | EMERGENCY ROLLBACK CIRCUIT      |
                                            | - Zero traffic within seconds   |
                                            | - Status -> ROLLED_BACK         |
                                            | - Immediate Source Isolation    |
                                            +---------------------------------+
```

---

## 3. CẤU HÌNH CANARY DEPLOYMENT CHI TIẾT (T130)

| Tham số Cấu hình | Giá trị Tiêu chuẩn | Mô tả & Ràng buộc |
| :--- | :--- | :--- |
| `tenant_name` | `SIN_CREATOR_PILOT_ALPHA` | Tên tenant thí điểm được cấp phép |
| `traffic_percentage` | `5.0%` | Lưu lượng thử nghiệm phân bổ cho canary |
| `human_approval_id` | `APPR-2026-CANARY-001` | Mã số phê duyệt ký số của Quản lý Vận hành |
| `signed_rights_reference` | `AGREEMENT-2026-TIKTOK-OFFICIAL-01` | Mã số giấy phép bản quyền nguồn dữ liệu |
| `status` | `CANARY_ACTIVE` | Trạng thái triển khai ban đầu |
| `is_rollback_ready` | `True` | Điều kiện bắt buộc để cho phép kích hoạt canary |

---

## 4. QUẢN LÝ DỮ LIỆU VÀ TRUY XUẤT NGUỒN GỐC (DATA LINEAGE & REVIEW OUTPUT)
Theo tiêu chuẩn **T130**, mọi phiên nghiên cứu (`CanaryResearchRun`) phải ghi nhận đầy đủ:
1. **Real Source IDs**: Danh sách ID bài viết nguồn thực tế được cấp phép bản quyền đầy đủ (`real_source_ids_json`), tuyệt đối cấm dùng nguồn cào lậu / MediaCrawler.
2. **Data Lineage**: Cấu trúc nguồn gốc dữ liệu minh bạch (`brief_version_id`, `provider_ids`, `model_route`, `timestamp`).
3. **Quota Cost Accounting**: Ghi nhận chi phí hạn mức thực tế tiêu thụ (`quota_cost_units`).
4. **Human Review Output**: Bản đánh giá chất lượng đầu ra phục vụ rà soát chất lượng trước khi cho phép nhân rộng.
5. **Rollback Readiness**: Mọi phiên nghiên cứu đều có cờ `is_rollback_ready = True` sẵn sàng hoàn tác nếu phát hiện sai lệch.

---

## 5. CƠ CHẾ THU HỒI QUYỀN TRUY CẬP NHÀ CUNG CẤP (T131)
Khi nhà cung cấp dữ liệu đối tác (ví dụ TikTok Official, YouTube Official) gửi yêu cầu thu hồi bản quyền hoặc hết hạn giấy phép:
- **Hành động tức thời**: Kích hoạt API `/v1/canary/providers/revoke` với `provider_id`.
- **Trạng thái Grant**: Chuyển ngay sang `REVOKED`.
- **Cô lập Nguồn**: Tất cả bài viết nguồn thuộc `provider_id` đó được đánh dấu `is_purged = True`, `purged_at = utc_now`.
- **Cam kết No Alternate Bypass**: Cấm tuyệt đối việc tự động chuyển sang crawler lậu hoặc nguồn thay thế không có bản quyền.
- **Thông báo an toàn**: Giao diện và API phản hồi thông báo rõ ràng cho Operator: *"Quyền truy cập nhà cung cấp đã thu hồi an toàn. Cấm tuyệt đối nguồn thay thế (no alternate bypass). Nguồn dữ liệu đã được cô lập/xóa."*

---

## 6. KẾT LUẬN
Bản kế hoạch này là cơ sở pháp lý và kỹ thuật bắt buộc để vận hành Canary trong môi trường sản xuất có kiểm soát của SIN Content Intelligence.
