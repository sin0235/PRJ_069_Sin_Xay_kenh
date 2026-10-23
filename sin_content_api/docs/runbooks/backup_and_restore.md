# SỔ TAY VẬN HÀNH: QUY TRÌNH SAO LƯU & KHÔI PHỤC CSDL STAGING
## SIN Content Intelligence — PRJ_069
**Mục tiêu:** Đảm bảo khả năng phục hồi dữ liệu (Disaster Recovery) với RTO < 15 phút, RPO < 1 giờ.
**Nguyên tắc cốt lõi (T123):** Dữ liệu sao lưu phải được tẩy sạch thông tin xác thực/secrets (Secrets Scrubbing). Tuyệt đối không lưu trữ khóa mật mã trong artifacts sao lưu.

---

### I. QUY TRÌNH SAO LƯU DỮ LIỆU (BACKUP)

#### 1. Lệnh Thực Thi
Chạy script sao lưu an toàn:
```bash
python 03_ban_lam_viec/sin_content_api/scripts/backup_staging_db.py <duong_dan_db_nguon> <thu_muc_luu_backup>
```
*Ví dụ:*
```bash
python 03_ban_lam_viec/sin_content_api/scripts/backup_staging_db.py sin_content_offline.db backups
```

#### 2. Các Bước Thực Thi Tự Động Trong Script:
1. **Online Snapshot**: Kết nối SQLite và dùng Backup API để tạo bản sao lưu snapshot tại thời điểm t0, không khóa chặn các giao dịch đọc/ghi.
2. **Secrets Scrubbing (T123)**:
   - Tự động thay thế toàn bộ trường `hashed_password` thành `[SCRUBBED_IN_BACKUP]`.
   - Loại bỏ các access tokens, JWT secrets nhạy cảm.
3. **Audit Manifest & Checksum**:
   - Tính toán mã băm SHA256 cho file backup.
   - Thống kê số lượng bảng và số dòng của từng bảng.
   - Xuất file `backup_manifest_<timestamp>.json` chứa thông số kiểm toán.

---

### II. QUY TRÌNH KHÔI PHỤC DỮ LIỆU (RESTORE)

#### 1. Lệnh Thực Thi
```bash
python 03_ban_lam_viec/sin_content_api/scripts/restore_staging_db.py <file_backup.db> <db_dich.db> [file_manifest.json]
```

#### 2. Các Bước Kiểm Tra Tính Toàn Vẹn:
1. **Xác thực Checksum**: Nếu cung cấp file manifest, script sẽ kiểm tra SHA256 của file backup để đảm bảo không bị chỉnh sửa hay hỏng dữ liệu trong quá trình truyền tải.
2. **Khôi phục File**: Sao chép nguyên vẹn dữ liệu sang database đích.
3. **Kiểm tra Toàn vẹn SQLite**: Chạy lệnh `PRAGMA integrity_check` xác nhận cấu trúc B-tree không bị phân mảnh hay lỗi.
4. **Kiểm tra Readiness Probe**: Khởi động lại API và kiểm tra endpoint `/readyz` phản hồi HTTP 200 `status: "ready"`.

---

### III. SỰ CỐ & HÀNH ĐỘNG KHẮC PHỤC (TROUBLESHOOTING)
- **Lỗi Checksum mismatch**: Hủy bỏ tiến trình khôi phục, kiểm tra bản sao lưu gần nhất trước đó hoặc tải lại từ kho lưu trữ lạnh.
- **Lỗi database disk image is malformed**: Kiểm tra dung lượng đĩa cứng, chạy `sqlite3 <backup> ".recover"`.
