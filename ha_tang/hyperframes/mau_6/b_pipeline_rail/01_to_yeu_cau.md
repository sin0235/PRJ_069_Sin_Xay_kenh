# Tờ yêu cầu: Cảnh B - PIPELINE_RAIL (M1)

- **Tên layout:** `PIPELINE_RAIL`
- **Mã khối:** `pipeline-rail.html`
- **Thời lượng:** 10.0 giây (300 khung hình @ 30 fps)
- **Tập bài áp dụng:** Bài 01, 02, 13 và Kịch bản Khám sức khỏe doanh nghiệp BAHA (quy trình chăm sóc khách hàng, mất đơn).
- **Ý chính một câu:** Băng chuyền module origami đưa các thẻ hồ sơ khách hàng chạy qua các trạm xử lý, tắc nghẽn tại một trạm kiểm soát làm dồn thẻ và đẩy một thẻ rơi khỏi băng chuyền kèm con số đơn mất.

## 1. Danh sách vật thể chuyển động & giới hạn
- Băng chuyền: module ngang (`data-obj="conveyor-track"`, `data-kind="prop"`, `data-src="static"`, `data-dst="stay"`).
- Trạm kiểm soát: 5 trạm (`station-0` đến `station-4`, `data-kind="prop"`).
- Thẻ hồ sơ khách hàng: 6 thẻ (`card-1` đến `card-6`, `data-kind="prop"`, thẻ 6 rơi ra mép `data-dst="offscreen-bottom"`).
- Nhãn nghẽn & bộ đếm đơn mất: (`jam-tag`, `counter-box`, `data-kind="text"`).
- Chip kết luận: (`caption-chip`, `data-kind="text"`).
- Giới hạn: Tối đa 8 thẻ, 5 trạm.

## 2. Cú máy chính
Dolly ngang dọc theo băng chuyền (tối đa 10.7%/giây), đẩy vào trạm nghẽn (push in), và hạ góc máy theo dõi thẻ rơi.
