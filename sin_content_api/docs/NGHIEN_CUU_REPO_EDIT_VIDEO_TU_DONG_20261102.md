# Nghiên cứu repo tham khảo cho Auto Edit

Ngày đối chiếu: 2026-11-02

## Phạm vi hiện tại của dự án

Auto Edit đã có luồng riêng tại `/auto-edit`: nhận video gốc, nhận dạng lời nói, gửi transcript cho LLM chọn nội dung và take, tạo kế hoạch phụ đề/nhãn/diễn họa, sau đó dựng video bằng FFmpeg và renderer hoạt họa sẵn có. Kế hoạch lưu theo job để worker tiếp tục ở pha render. Lớp HyperFrames/Remotion đang được Claude Code phát triển; đánh giá này không đề xuất tạo thêm một trình dựng hoặc một lớp renderer song song.

Các điểm mã liên quan: `src/modules/dieu_phoi_dung/dung_video_dai.py`, `src/modules/media_studio/security.py`, `src/modules/media_studio/service.py`.

## Đối chiếu repo

| Repo chính thức | Giấy phép | Giá trị cho dự án | Quyết định tích hợp |
|---|---|---|---|
| [AIEV](https://github.com/notivn/AIEV) | MIT; media đi kèm có quyền riêng | Pipeline LLM điều phối HyperFrames và Remotion, karaoke, SFX, dashboard, khôi phục job. Trùng trực tiếp phần render và dashboard đang có. | Không chép engine/UI. Tham khảo khả năng tiếp tục job sau gián đoạn và cách tổ chức project theo video. |
| [Cutline](https://github.com/WebWithRathor/cutline) | Chưa xác minh được giấy phép từ repo công khai | LLM tạo creative brief và storyboard trước khi render; chọn thời điểm minh họa/B-roll. | Chỉ tham khảo ý tưởng storyboard. Không lấy mã hoặc phụ thuộc cho đến khi có giấy phép rõ ràng. Có nhiều repo cùng tên Cutline; repo trên là repo khớp mô tả bảng tham khảo. |
| [Open Video Edit / open-edits](https://github.com/kevinbadi/open-edits) | MIT cho mã; font, logo, GIF và media theo giấy phép riêng | Phân tích video tham chiếu thành nhịp cắt, bố cục, mật độ visual; đồng bộ diễn họa theo từ. | Tham khảo ngôn ngữ bố cục và cách đọc style. Không đưa renderer vẽ từng frame bằng Python vào pipeline đang dùng HyperFrames/Remotion. |
| [motion-script](https://github.com/marcoantoniovillalva-bot/motion-script) | MIT cho mã; font và tài nguyên ngoài có điều khoản riêng | LLM lập kế hoạch B-roll, zoom, caption và xuất lớp overlay riêng. | Ý tưởng lập kế hoạch visual theo transcript hữu ích; không nhập pipeline Remotion thứ hai hoặc tải tài nguyên ngoài tự động. |
| [ChatMonteur](https://github.com/ArtCog/chatmonteur) | MIT; dependency và media giữ giấy phép riêng | Có cổng chấm kế hoạch trước render và cổng kiểm video sau render: mật độ visual, caption lặp, khung đen, âm thanh, thời lượng. | Tham khảo để tăng QA của Auto Edit. Đây là khoảng trống đáng ưu tiên: hiện có full decode và phát hiện đoạn đen, nhưng chưa có bộ chấm toàn diện cho âm thanh và chất lượng storyboard. |
| [video-use](https://github.com/browser-use/video-use) | MIT; công cụ và tài nguyên cài thêm có giấy phép riêng | Quy trình agent xử lý transcript, bỏ từ đệm, cắt, màu, phụ đề và các loại animation overlay. | Tham khảo quy tắc biên tập; không đưa skill/agent phụ thuộc Claude vào runtime của dịch vụ. |
| [AutoBroll](https://github.com/andriidrok1/autobroll) | MIT; Gemini/Pexels và media ngoài có điều khoản riêng | Nhóm take lặp, sắp xếp theo mạch kể, cắt khoảng nghỉ, đặt B-roll theo lời và có MCP chỉnh timeline. | Ý tưởng nhóm take và neo visual vào lời đã có trong planner Auto Edit. Không nhập editor dạng timeline/MCP hoặc phụ thuộc Remotion khác. |
| [FireRed-OpenStoryline](https://github.com/FireRedTeam/FireRed-OpenStoryline) | Apache-2.0 | Lập kế hoạch bằng hội thoại, gọi công cụ theo từng bước, lưu style thành kỹ năng tái sử dụng và cho phép sửa một phần. | Tham khảo cấu trúc style có thể tái sử dụng; không thay job orchestrator bằng stack agent/MoviePy riêng. |
| [AIvideokit](https://github.com/rockwithsystems/AIvideokit) | MIT cho mã; nhạc/tài nguyên tùy chọn có giấy phép riêng | Từ điển hiệu ứng theo nhịp, ví dụ slam/flash, whip, punch-in, chuyển cutaway và SFX. | Dùng làm tài liệu thuật ngữ cho LLM/QA; không nhập scripts dựng và bộ phụ đề riêng. |
| [Vex Auto Visuals](https://github.com/AKMessi/vex) | PolyForm Noncommercial 1.0.0; không cho phép dùng thương mại/nội bộ kinh doanh nếu chưa có giấy phép khác | Tool loop để lập visual narrative và chọn renderer. | Không tích hợp hoặc sao chép mã vào PRJ_069. Chỉ dùng mô tả tính năng ở mức tham khảo. |

## Đối chiếu hai video mẫu

Các file `mau1.mp4` và `mau2.mp4` được mở chỉ để xem tham chiếu, không dùng làm footage đầu vào.

- `mau1`: có cảnh giao diện sản phẩm chiếm vùng trên, người nói ở vùng dưới; caption lớn có từ khóa xanh ngọc; chuyển giữa talking-head và cutaway.
- `mau2`: người nói toàn khung với caption karaoke trắng/vàng và thanh tiến độ theo mục; cảnh minh họa phẳng kiểu giấy màu kem, vàng và xanh đậm, có nhãn bước/checklist ở vùng an toàn.
- Mẫu dùng nhiều bố cục theo ý nghĩa câu nói: overlay nhỏ trên người nói, split-screen, thay toàn khung bằng diễn họa. Caption/nhãn/diễn họa cần chia vùng để tránh chồng chữ.

## Kết luận triển khai

Không có repo nào nên được nhúng nguyên khối vào hệ thống hiện tại. Những phần phù hợp đã được triển khai nội bộ trong pipeline: LLM chọn take và cut theo transcript; planner tạo nhãn và visual gắn từ; HyperFrames/Remotion render theo style hệ thống; FFmpeg ghép timeline và tạo caption karaoke. Việc đưa thêm AIEV, motion-script hoặc editor AutoBroll sẽ tạo renderer/job/UI trùng lặp.

Ưu tiên tiếp theo là mở rộng cổng QA của ChatMonteur theo dữ liệu đã có trong manifest: kiểm mật độ visual và khoảng talking-head trống dài, kiểm caption/nhãn chồng nhau hoặc lặp, kiểm audio silence/clipping/loudness và lưu báo cáo QC cho từng clip. Giữ nguyên quyền duyệt cuối của nhân viên trong Auto Edit.

## Giới hạn xác minh

- Cutline được nhận diện theo repo `WebWithRathor/cutline` vì nội dung khớp mô tả; trang repo không công bố giấy phép rõ ràng, cần chủ repo xác nhận trước khi dùng mã.
- MIT/Apache chỉ áp dụng cho mã được ghi nhận; font, nhạc, logo, ảnh, GIF, video stock, model và API có thể mang điều khoản khác.
- Tài liệu này là đánh giá khả năng tái sử dụng, chưa có mã nguồn bên thứ ba nào được vendored vào repo PRJ_069.
