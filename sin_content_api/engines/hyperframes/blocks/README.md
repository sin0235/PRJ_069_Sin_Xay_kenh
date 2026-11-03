# Khối dựng sẵn của HyperFrames

Nguồn: kho khối chính thức của HyperFrames (`registry`, lấy bằng `hyperframes add`), giấy phép Apache-2.0 của HeyGen. Phiên bản công cụ cố định 0.8.222.

## Đang dùng trong pipeline (thư mục này)
`paper-collage-reveal.html`: chuyển cảnh mảnh giấy xé, cách quãng giữa các shot (`hf_project.collage_block`).

Các khối còn lại là nguồn của 9 loại cảnh mới (`hf_blocks.BLOCK_SCENES`, planner gọi là KINETIC_TITLE, MARK_PHRASE, WORD_SWAP, PILE_UP, STAT_RING, CHART_STORY, AI_RANK, DRAG_TASKS, CARD_SHIFT):

| Khối | Loại cảnh |
|---|---|
| `chart-story` | CHART_STORY, CHART_STORY |
| `conic-progress-ring` | STAT_RING |
| `headline-slam` | KINETIC_TITLE |
| `kinetic-center-build` | KINETIC_TITLE |
| `char-slam-explode` | KINETIC_TITLE |
| `ai-answer-rank` | AI_RANK |
| `cursor-drag-drop` | DRAG_TASKS |
| `focus-rack` | CARD_SHIFT |
| `kinetic-type-swap` | WORD_SWAP |
| `marker-highlight` | MARK_PHRASE, MARK_PHRASE, MARK_PHRASE |
| `overwhelm-surround` | PILE_UP |
| `shutter-slam` | KINETIC_TITLE |
| `text-match-cut` | KINETIC_TITLE |
| `titlecard-calm` | KINETIC_TITLE |
| `vox-annotate` | MARK_PHRASE |

Khi dựng, `hf_blocks.prepare_block` bỏ GSAP/font tải từ CDN (dùng GSAP cục bộ và font Be Vietnam Pro), đổi định danh theo từng lần dùng, ghi độ dài thật của shot (khối đọc độ dài từ `dataset.duration`, không từ thẻ host), Việt hóa chữ mẫu tiếng Anh, và khoác bảng màu thương hiệu qua biến CSS.

## Danh mục đã kiểm
`catalog.json` liệt kê 159 khối đã tải thử: 126 khối dựng và chụp được khung hình (`danh_sach_khoi_da_kiem.txt`), 32 là mảnh mã (snippet) không dựng độc lập, một số có lỗi chạy do thiếu font hoặc tài nguyên. Các khối chưa nối vào pipeline không được lưu trong kho này: lấy lại bằng `npx hyperframes add <tên>` trong một dự án HyperFrames.

Lưu ý khi nối thêm khối:
- Phần lớn khối chuyển cảnh (`torn-paper-rip`, `halftone-dissolve`, `iris-reveal`, `whip-pan-cut`...) nhận hai cảnh qua `<template data-slot>` nên không phải lớp phủ trong suốt như `paper-collage-reveal`; cần kiến trúc ghép khác.
- Trang mẫu có nội dung cố định (biểu đồ, `flowchart`, `lt-*`...) chứa chữ tiếng Anh và số mẫu, phải thay nội dung trước khi dùng; không để số liệu mẫu lên video.
- Thư viện GSAP đi kèm khối phải nạp cục bộ: `CustomEase` đã có ở `engines/vendor`; plugin khác cần thêm tương tự trước khi dùng khối.
- Chuyển cảnh giữa các shot (hf_project): mảnh giấy xé (khối `paper-collage-reveal`) xen kẽ với mở vòng, lia ngang và chớp sáng viết bằng GSAP trên cảnh vào.
