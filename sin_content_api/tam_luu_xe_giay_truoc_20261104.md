# Bản lưu trước khi giảm mật độ xé giấy

- SHA-256 ban đầu của `src/modules/tao_video_noi_dung/hf_project.py`: `237E68A0B5A8D27D534E21B6FE9A860DC14C81A7560ED714249336673D9EFF8E`.
- Hoàn nguyên điều kiện hình cũ trong vòng lặp `build_project`: `if transitions and index % 2 == 1:`.
- Điều kiện cũ chèn SFX trong `runner.py`: `[clips[index].start_ms / 1000 for index in range(1, len(clips), 2)]`, chỉ khi HyperFrames bật và `CONTENT_VIDEO_HF_TRANSITIONS` khác `0`.

Đây là bản lưu logic tối thiểu để phục hồi nhịp cũ; mã nguồn chưa bị sửa tại thời điểm tạo bản lưu.
