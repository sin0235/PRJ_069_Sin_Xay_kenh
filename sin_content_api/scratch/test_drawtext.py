import subprocess
import pathlib

tmp_dir = pathlib.Path("scratch/test_drawtext")
tmp_dir.mkdir(parents=True, exist_ok=True)
in_vid = tmp_dir / "in.mp4"
out_vid = tmp_dir / "out.mp4"
txt_file = tmp_dir / "cap.txt"
txt_file.write_text("TEST TIẾNG VIỆT CÓ DẤU HOÀN TOÀN!", encoding="utf-8")

# 1. create test video
subprocess.run([
    "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=1",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(in_vid)
], check=True, capture_output=True)

# 2. test drawtext
escaped_txt = str(txt_file.resolve()).replace("\\", "/").replace(":", "\\:")
font_path = "C:/Windows/Fonts/arial.ttf".replace(":", "\\:").replace("\\", "/")

# Test 6: Running inside cwd=tmp_dir with relative paths
vf6 = "drawtext=fontfile='/Windows/Fonts/arial.ttf':textfile='cap.txt':fontsize=36:fontcolor=white:box=1:boxcolor=black@0.7:boxborderw=8:x=(w-text_w)/2:y=h-480:enable='between(t,0.000,1.000)'"
res6 = subprocess.run(
    ["ffmpeg", "-y", "-i", "in.mp4", "-vf", vf6, "-c:v", "libx264", "-pix_fmt", "yuv420p", "out6.mp4"],
    cwd=str(tmp_dir),
    capture_output=True,
    text=True
)
print("Test 6 (cwd=tmp_dir, fontfile=/Windows/Fonts/arial.ttf, textfile=cap.txt):", res6.returncode)
if res6.returncode == 0:
    print("SUCCESS! out6.mp4 size:", (tmp_dir / "out6.mp4").stat().st_size)
else:
    print("Stderr 6:", res6.stderr)



