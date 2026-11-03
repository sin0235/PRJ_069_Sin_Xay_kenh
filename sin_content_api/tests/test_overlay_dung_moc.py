"""Hồi quy overlay xuất hiện muộn: phải chạy từ đầu, không giữ frame cuối."""
import subprocess
import pytest

from src.modules.media_studio.video_processor import video_processor


@pytest.mark.parametrize('trim_ms', [0, 500])
@pytest.mark.parametrize('alpha', [False, True])
def test_overlay_muon_chay_dung_animation_va_bien_mat(tmp_path, trim_ms, alpha):
    base = tmp_path / 'nguon.mp4'
    overlay = tmp_path / ('hoat_anh.mov' if alpha else 'hoat_anh.mp4')
    output = tmp_path / 'ket_qua.mp4'

    def ffmpeg(*args):
        return subprocess.run(
            [video_processor.ffmpeg_bin, '-v', 'error', *map(str, args)],
            check=True, capture_output=True,
        ).stdout

    ffmpeg('-y', '-f', 'lavfi', '-i', 'color=black:s=160x284:r=10:d=6', '-c:v', 'libx264', base)
    opacity = '@0.5' if alpha else ''
    pixel_format = ',format=argb' if alpha else ''
    ffmpeg('-y', '-f', 'lavfi', '-i', f'color=red{opacity}:s=40x40:r=10:d=1{pixel_format}',
           '-f', 'lavfi', '-i', f'color=blue{opacity}:s=40x40:r=10:d=1{pixel_format}',
           '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0[v]', '-map', '[v]',
           '-c:v', 'qtrle' if alpha else 'libx264', overlay)
    timeline = {
        'width': 160, 'height': 284, 'fps': 10,
        'clips': [{'clip_id': 'nguon', 'asset_id': 'nguon', 'media_type': 'video',
                   'start_ms': 0, 'duration_ms': 6000, 'trim_in_ms': 0, 'trim_out_ms': 6000}],
        'overlays': [{'asset_id': 'hoat_anh', 'start_ms': 3000, 'duration_ms': 2000,
                      'trim_in_ms': trim_ms,
                      'x': 20, 'y': 20, 'width': 40, 'height': 40},
                     {'asset_id': 'hoat_anh', 'mode': 'speaker_pip', 'start_ms': 500,
                      'duration_ms': 1000, 'trim_in_ms': 1000,
                      'x': 90, 'y': 20, 'width': 40, 'height': 40}],
    }
    video_processor.render_timeline_document(timeline, lambda asset: {'nguon': base, 'hoat_anh': overlay}[asset], output)

    def pixel(at, x=38):
        return ffmpeg('-ss', at, '-i', output, '-vf', f'crop=2:2:{x}:38,scale=1:1',
                      '-frames:v', 1, '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1')[:3]

    assert max(pixel(2.5)) < 30
    red = pixel(3.3)
    blue = pixel(4.3)
    minimum, maximum = (90, 160) if alpha else (180, 255)
    assert minimum < red[0] <= maximum and red[2] < 50, red
    assert minimum < blue[2] <= maximum and blue[0] < 50, blue
    assert max(pixel(5.5)) < 30
    assert max(pixel(.2, 108)) < 30
    pip = pixel(.8, 108)
    assert minimum < pip[2] <= maximum and pip[0] < 50, pip
    assert max(pixel(2, 108)) < 30
