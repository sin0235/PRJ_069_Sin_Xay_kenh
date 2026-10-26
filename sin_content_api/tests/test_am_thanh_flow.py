"""Kiểm định audio Flow thật qua FFmpeg khi các cảnh chênh lệch âm lượng."""

import subprocess

import pytest

from src.modules.media_studio.audio_processor import audio_processor
from src.modules.media_studio.video_processor import video_processor


@pytest.mark.parametrize("mix_existing", [False, True])
def test_native_audio_dap_ung_qc_sau_khi_ma_hoa_aac(tmp_path, mix_existing):
    """Chuẩn hóa một lượt bỏ lệch LUFS khi cảnh cuối to hơn các cảnh đầu."""
    source = tmp_path / "nguon.mp4"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=s=64x96:r=10:d=12",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
        "-af", "volume='if(lt(t,3),0.1,if(lt(t,6),1,if(lt(t,9),0.05,6)))':eval=frame",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "192k", str(source),
    ], check=True, capture_output=True)
    output = tmp_path / "ket_qua.mp4"
    cmd = [video_processor.ffmpeg_bin, "-y", "-i", str(source)]
    if mix_existing:
        cmd.extend(["-f", "lavfi", "-i", "sine=frequency=700:duration=12", "-map", "0:v", "-map", "1:a", "-c:a", "aac"])
    else:
        cmd.append("-an")
    subprocess.run(cmd + ["-c:v", "copy", str(output)], check=True, capture_output=True)

    assert video_processor._preserve_native_clip_audio(
        output, [(source, "video", index * 3, 3) for index in range(4)], tmp_path, mix_existing, 12,
    )

    qc = audio_processor.verify_audio_qc(output, expected_duration_sec=12)
    assert qc["passed"], qc
    assert qc["codec_name"] == "aac"
    assert qc["sample_rate_hz"] == 44100
    assert qc["channels"] == 2

    def video_hash(path):
        return subprocess.run([
            video_processor.ffmpeg_bin, "-i", str(path), "-map", "0:v:0", "-c:v", "copy",
            "-f", "hash", "-hash", "sha256", "-",
        ], check=True, capture_output=True).stdout

    assert video_hash(output) == video_hash(source)


@pytest.mark.parametrize("has_audio", [False, True])
def test_khong_tao_them_tieng_khi_nguon_im_lang(tmp_path, has_audio):
    """Nguồn không có track hoặc chỉ có mẫu im lặng vẫn giữ nguyên trạng thái."""
    output = tmp_path / "im_lang.mp4"
    cmd = [video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=s=64x96:r=10:d=1"]
    if has_audio:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-c:a", "aac", "-t", "1"])
    subprocess.run(cmd + ["-c:v", "libx264", "-preset", "ultrafast", str(output)], check=True, capture_output=True)
    before = output.read_bytes()

    assert video_processor._preserve_native_clip_audio(
        output, [(output, "video", 0, 1)], tmp_path, False, 1,
    ) is has_audio

    if has_audio:
        assert audio_processor.measure_loudness(output)["measured_i_lufs"] == float("-inf")
    else:
        assert output.read_bytes() == before
