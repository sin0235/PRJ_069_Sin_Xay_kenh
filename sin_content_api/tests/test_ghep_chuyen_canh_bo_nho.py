import subprocess

from src.modules.media_studio import video_processor as module


def test_chuyen_canh_chi_mo_hai_doan_va_giu_du_khung_hinh(tmp_path, monkeypatch):
    processor = module.video_processor
    segments = []
    for index, color in enumerate(['red', 'blue', 'green', 'yellow']):
        path = tmp_path / f'doan_{index}.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        f'color=c={color}:s=108x192:r=30:d=1', '-c:v', 'libx264',
                        '-threads', '1', '-pix_fmt', 'yuv420p', str(path)], check=True)
        segments.append(path)
    original = module.run_media_command
    commands = []

    def track(command, **kwargs):
        commands.append(command)
        return original(command, **kwargs)

    monkeypatch.setattr(module, 'run_media_command', track)
    output = processor._ghep_chuyen_canh_tuan_tu(segments, tmp_path, 0.16, 30)
    assert all(command.count('-i') <= 2 for command in commands)
    frames = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                             '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', str(output)],
                            check=True, capture_output=True, text=True)
    assert int(frames.stdout.strip()) == 120
    # Đoạn cuối phải còn đúng màu vàng, không bị cắt bởi xfade.
    pixel = subprocess.run(['ffmpeg', '-v', 'error', '-sseof', '-0.05', '-i', str(output),
                            '-frames:v', '1', '-vf', 'scale=1:1', '-pix_fmt', 'rgb24',
                            '-f', 'rawvideo', '-'], check=True, capture_output=True).stdout
    assert pixel[0] > 200 and pixel[1] > 200 and pixel[2] < 50
