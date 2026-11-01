# Khối dựng sẵn của HyperFrames đang dùng

Nguồn: kho khối chính thức của HyperFrames (`registry`, lấy bằng `hyperframes add`), giấy phép Apache-2.0 của HeyGen; giữ nguyên tệp gốc, chỉ chỉnh khi dựng (xem `hf_project.collage_block`).

| Khối | Dùng để | Chỉnh khi dùng |
|---|---|---|
| `paper-collage-reveal.html` | Chuyển cảnh: mảnh giấy xé phủ khung rồi lột ra để lộ cảnh mới, cách quãng giữa các shot | Bỏ GSAP tải từ CDN (dùng bản cục bộ), bỏ thẻ nội dung mặc định để lộ cảnh nằm dưới, đổi định danh theo từng lần dùng |
