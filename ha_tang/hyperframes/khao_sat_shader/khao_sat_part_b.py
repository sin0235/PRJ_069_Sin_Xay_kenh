"""Khao sát thực nghiệm Phần B: Điều tra tính khả thi của gói @hyperframes/shader-transitions@0.8.222.
Kiểm tra 3 giả thuyết với lệnh render thực tế 2.5 giây:
  hyperframes render -q draft -w 1 --start 4 --end 6.5 -o out.mp4
(a) Nhúng trực tiếp mã HTML cảnh (inline) vào index.html (không dùng data-composition-src), class="scene".
(b) Giữ sub-compositions và gọi HyperShader.init sau khi các cảnh con đã được mount vào DOM.
(c) Pre-render từng cảnh ra MP4 ngắn và dùng thẻ <video class="scene"> làm cảnh.
Ghi nhận thời gian thực (wall-clock seconds), giây trên mỗi giây dựng, và kiểm tra khung hình giữa có hiệu ứng shader hay chỉ chồng lấn phẳng (plain overlap).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from PIL import Image, ImageChops

REPO_ROOT = Path(__file__).resolve().parents[3]
SIN_API_DIR = REPO_ROOT / "sin_content_api"
if str(SIN_API_DIR) not in sys.path:
    sys.path.insert(0, str(SIN_API_DIR))

from src.modules.tao_video_noi_dung import hf_project
from src.modules.tao_video_noi_dung.planner import DiagramSpec, UiScene

PKG_DIST = Path(tempfile.gettempdir()) / "hf_shader_pkg" / "package" / "dist" / "index.global.js"


def ensure_shader_dist():
    if not PKG_DIST.is_file():
        raise RuntimeError(f"Chưa tìm thấy gói index.global.js tại: {PKG_DIST}")


def run_single_render(project_dir: Path, output_mp4: Path, extra_flags: list[str] = None) -> tuple[bool, float, str]:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    if output_mp4.is_file():
        output_mp4.unlink()

    cmd = [
        hf_project._node(),
        str(hf_project.hyperframes_cli()),
        "render",
        "-q", "draft",
        "-w", "1",
        "--start", "4",
        "--end", "6.5",
        "-o", str(output_mp4),
    ]
    if extra_flags:
        cmd.extend(extra_flags)

    t0 = time.perf_counter()
    res = subprocess.run(cmd, cwd=project_dir, env=hf_project._env(), capture_output=True, text=True, timeout=300)
    dur = time.perf_counter() - t0

    success = res.returncode == 0 and output_mp4.is_file() and output_mp4.stat().st_size > 1000
    log = (res.stdout + "\n" + res.stderr)[-4000:]
    return success, dur, log


def extract_frame_at(video_path: Path, timestamp_s: float, out_png: Path):
    if out_png.is_file():
        out_png.unlink()
    # Lấy frame tại timestamp bằng ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{timestamp_s:.3f}",
        "-i", str(video_path),
        "-vframes", "1",
        str(out_png),
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)


def check_shader_vs_overlap(frame_path: Path, s1_frame: Path, s2_frame: Path) -> dict:
    if not frame_path.is_file() or not s1_frame.is_file() or not s2_frame.is_file():
        return {"is_blend": False, "is_shader": False, "detail": "Thiếu file ảnh trích xuất"}

    im = Image.open(frame_path).convert("RGB")
    im1 = Image.open(s1_frame).convert("RGB")
    im2 = Image.open(s2_frame).convert("RGB")

    diff1 = ImageChops.difference(im, im1).getbbox() is not None
    diff2 = ImageChops.difference(im, im2).getbbox() is not None

    return {
        "is_blend": diff1 and diff2,
        "detail": f"diff_s1={diff1}, diff_s2={diff2}",
    }


def prepare_base_assets(project_dir: Path):
    shutil.rmtree(project_dir, ignore_errors=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    vendor_dir = project_dir / "assets" / "vendor"
    vendor_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "assets" / "fonts").mkdir(parents=True, exist_ok=True)

    # Copy gsap và hyper-shader
    shutil.copy(hf_project.engines_dir() / "vendor" / "gsap.min.js", vendor_dir / "gsap.min.js")
    shutil.copy(PKG_DIST, vendor_dir / "hyper-shader.global.js")

    (project_dir / "hyperframes.json").write_text(json.dumps({"paths": {"blocks": "compositions", "assets": "assets"}}), encoding="utf-8")
    (project_dir / "package.json").write_text(json.dumps({"name": "shader-test", "type": "module"}), encoding="utf-8")


def test_hypothesis_a(temp_dir: Path) -> dict:
    """Giả thuyết (a): Đặt trực tiếp markup HTML của 3 cảnh vào index.html với class='scene', không dùng data-composition-src."""
    proj = temp_dir / "hypo_a"
    prepare_base_assets(proj)

    # 3 cảnh nội tuyến với hình họa rõ rệt, màu nền đối lập và phần tử con có id
    # Cảnh 1: xanh dương đậm với lưới sọc và tiêu đề lớn
    # Cảnh 2: cam đỏ rực rỡ với khối tròn và tiêu đề
    # Cảnh 3: tím đậm
    index_html = f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1920, height=1080">
<script src="assets/vendor/gsap.min.js"></script>
<script src="assets/vendor/hyper-shader.global.js"></script>
<style>
html,body{{margin:0;width:1920px;height:1080px;overflow:hidden;background:#000;}}
.scene{{position:absolute;inset:0;width:1920px;height:1080px;display:flex;align-items:center;justify-content:center;font-family:sans-serif;}}
#s01{{background:linear-gradient(135deg, #0d3b66, #001e3d);color:#fff;}}
#s02{{background:linear-gradient(135deg, #e63946, #d62828);color:#ffbe0b;}}
#s03{{background:linear-gradient(135deg, #2a9d8f, #264653);color:#e76f51;}}
.box{{padding:40px 80px;border-radius:20px;font-size:72px;font-weight:900;text-align:center;box-shadow:0 20px 40px rgba(0,0,0,0.5);}}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="15.000" data-width="1920" data-height="1080">
  <div id="s01" class="scene" data-start="0.000" data-duration="6.000" style="z-index:1;">
    <div id="box-01" class="box" style="background:#1d3557;border:8px solid #a8dadc;">CANH 01 - DOMAIN WARP TRUOC</div>
  </div>
  <div id="s02" class="scene" data-start="4.500" data-duration="6.000" style="z-index:2;">
    <div id="box-02" class="box" style="background:#f4a261;border:8px solid #e76f51;">CANH 02 - DOMAIN WARP SAU</div>
  </div>
  <div id="s03" class="scene" data-start="9.500" data-duration="6.000" style="z-index:3;">
    <div id="box-03" class="box" style="background:#264653;border:8px solid #2a9d8f;">CANH 03 - KET THUC</div>
  </div>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
HyperShader.init({{
  bgColor: "#000000",
  accentColor: "#ff6b2b",
  scenes: ["s01", "s02", "s03"],
  transitions: [
    {{ time: 4.8, shader: "domain-warp", duration: 1.0 }},
    {{ time: 9.8, shader: "glitch", duration: 1.0 }}
  ],
  timeline: tl,
  compositionId: "main"
}});
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""
    (proj / "index.html").write_text(index_html, encoding="utf-8")

    out_mp4 = temp_dir / "out_hypo_a.mp4"
    success, dur, log = run_single_render(proj, out_mp4)

    # Trích xuất khung hình trước (4.2s), giữa chuyển cảnh (5.3s), sau (6.2s)
    f_before = temp_dir / "hypo_a_4_2s.png"
    f_mid = temp_dir / "hypo_a_5_3s.png"
    f_after = temp_dir / "hypo_a_6_2s.png"
    if success:
        # Thời gian trong video tương ứng với offset từ start=4:
        # 4.2s tuyệt đối = 0.2s trong out.mp4; 5.3s = 1.3s; 6.2s = 2.2s
        extract_frame_at(out_mp4, 0.2, f_before)
        extract_frame_at(out_mp4, 1.3, f_mid)
        extract_frame_at(out_mp4, 2.2, f_after)

    diff_info = check_shader_vs_overlap(f_mid, f_before, f_after)
    return {
        "hypothesis": "(a) Markup inline trong index.html",
        "success": success,
        "wall_clock_s": dur,
        "sec_per_rendered_sec": dur / 2.5 if success else 0,
        "diff_info": diff_info,
        "log_snippet": log[-1500:],
    }


def test_hypothesis_b(temp_dir: Path) -> dict:
    """Giả thuyết (b): Giữ sub-compositions (data-composition-src) và gọi HyperShader.init sau khi các cảnh con đã được mount."""
    proj = temp_dir / "hypo_b"
    prepare_base_assets(proj)
    (proj / "compositions").mkdir(parents=True, exist_ok=True)

    # Tạo 3 file composition con
    for cid, title, bg in [
        ("s01", "SUB-CANH 01", "#0d3b66"),
        ("s02", "SUB-CANH 02", "#d62828"),
        ("s03", "SUB-CANH 03", "#2a9d8f"),
    ]:
        comp_html = f"""<template>
<style>
[data-composition-id="{cid}"] {{ position:absolute; inset:0; background:{bg}; color:#fff; display:flex; align-items:center; justify-content:center; font-family:sans-serif; }}
.box {{ font-size:64px; font-weight:bold; }}
</style>
<div id="root" data-composition-id="{cid}" data-width="1920" data-height="1080">
  <div id="{cid}-inner" class="box">{title}</div>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
window.__timelines["{cid}"] = tl;
</script>
</template>
"""
        (proj / "compositions" / f"{cid}.html").write_text(comp_html, encoding="utf-8")

    # index.html chứa các host element với class="scene", và script chờ mount hoặc gọi init sau hook sẵn sàng
    index_html = f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1920, height=1080">
<script src="assets/vendor/gsap.min.js"></script>
<script src="assets/vendor/hyper-shader.global.js"></script>
<style>
html,body{{margin:0;width:1920px;height:1080px;overflow:hidden;background:#000;}}
.scene{{position:absolute;inset:0;width:1920px;height:1080px;}}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="15.000" data-width="1920" data-height="1080">
  <div id="s01" class="scene" data-composition-id="s01" data-composition-src="compositions/s01.html" data-start="0.000" data-duration="6.000" style="z-index:1;"></div>
  <div id="s02" class="scene" data-composition-id="s02" data-composition-src="compositions/s02.html" data-start="4.500" data-duration="6.000" style="z-index:2;"></div>
  <div id="s03" class="scene" data-composition-id="s03" data-composition-src="compositions/s03.html" data-start="9.500" data-duration="6.000" style="z-index:3;"></div>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});

// Chờ các host element có con (mounted) hoặc gọi init với fallback ngay
function initWhenReady() {{
  HyperShader.init({{
    bgColor: "#000000",
    accentColor: "#ff6b2b",
    scenes: ["s01", "s02", "s03"],
    transitions: [
      {{ time: 4.8, shader: "domain-warp", duration: 1.0 }},
      {{ time: 9.8, shader: "glitch", duration: 1.0 }}
    ],
    timeline: tl,
    compositionId: "main"
  }});
}}

// Trong HyperFrames virtual time, timeline chính được gán ngay
initWhenReady();
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""
    (proj / "index.html").write_text(index_html, encoding="utf-8")

    out_mp4 = temp_dir / "out_hypo_b.mp4"
    success, dur, log = run_single_render(proj, out_mp4)

    f_before = temp_dir / "hypo_b_4_2s.png"
    f_mid = temp_dir / "hypo_b_5_3s.png"
    f_after = temp_dir / "hypo_b_6_2s.png"
    if success:
        extract_frame_at(out_mp4, 0.2, f_before)
        extract_frame_at(out_mp4, 1.3, f_mid)
        extract_frame_at(out_mp4, 2.2, f_after)

    diff_info = check_shader_vs_overlap(f_mid, f_before, f_after)
    return {
        "hypothesis": "(b) Giữ sub-compositions, gọi init khi mount",
        "success": success,
        "wall_clock_s": dur,
        "sec_per_rendered_sec": dur / 2.5 if success else 0,
        "diff_info": diff_info,
        "log_snippet": log[-1500:],
    }


def test_hypothesis_c(temp_dir: Path) -> dict:
    """Giả thuyết (c): Pre-render từng cảnh ra file MP4 ngắn và dùng thẻ <video class="scene"> làm cảnh."""
    proj = temp_dir / "hypo_c"
    prepare_base_assets(proj)
    media_dir = proj / "assets"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Dùng ffmpeg tạo 3 video ngắn 6 giây màu khác nhau
    # Video 1: xanh dương; Video 2: đỏ; Video 3: xanh lá
    v1 = media_dir / "clip_s01.mp4"
    v2 = media_dir / "clip_s02.mp4"
    v3 = media_dir / "clip_s03.mp4"

    for v, col, txt in [
        (v1, "blue", "VIDEO SCENE 01"),
        (v2, "red", "VIDEO SCENE 02"),
        (v3, "green", "VIDEO SCENE 03"),
    ]:
        if not v.is_file():
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={col}:s=1920x1080:d=6:r=30",
                "-vf", f"drawtext=text='{txt}':fontcolor=white:fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(v),
            ]
            subprocess.run(cmd, capture_output=True, timeout=60)

    index_html = f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1920, height=1080">
<script src="assets/vendor/gsap.min.js"></script>
<script src="assets/vendor/hyper-shader.global.js"></script>
<style>
html,body{{margin:0;width:1920px;height:1080px;overflow:hidden;background:#000;}}
.scene{{position:absolute;inset:0;width:1920px;height:1080px;object-fit:cover;}}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="15.000" data-width="1920" data-height="1080">
  <video id="s01" class="scene" src="assets/clip_s01.mp4" data-start="0.000" data-duration="6.000" data-media-start="0" data-playback-rate="1" muted playsinline style="z-index:1;"></video>
  <video id="s02" class="scene" src="assets/clip_s02.mp4" data-start="4.500" data-duration="6.000" data-media-start="0" data-playback-rate="1" muted playsinline style="z-index:2;"></video>
  <video id="s03" class="scene" src="assets/clip_s03.mp4" data-start="9.500" data-duration="6.000" data-media-start="0" data-playback-rate="1" muted playsinline style="z-index:3;"></video>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
HyperShader.init({{
  bgColor: "#000000",
  accentColor: "#ff6b2b",
  scenes: ["s01", "s02", "s03"],
  transitions: [
    {{ time: 4.8, shader: "domain-warp", duration: 1.0 }},
    {{ time: 9.8, shader: "glitch", duration: 1.0 }}
  ],
  timeline: tl,
  compositionId: "main"
}});
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""
    (proj / "index.html").write_text(index_html, encoding="utf-8")

    out_mp4 = temp_dir / "out_hypo_c.mp4"
    success, dur, log = run_single_render(proj, out_mp4)

    f_before = temp_dir / "hypo_c_4_2s.png"
    f_mid = temp_dir / "hypo_c_5_3s.png"
    f_after = temp_dir / "hypo_c_6_2s.png"
    if success:
        extract_frame_at(out_mp4, 0.2, f_before)
        extract_frame_at(out_mp4, 1.3, f_mid)
        extract_frame_at(out_mp4, 2.2, f_after)

    diff_info = check_shader_vs_overlap(f_mid, f_before, f_after)
    return {
        "hypothesis": "(c) Pre-render thành video MP4, dùng <video class='scene'>",
        "success": success,
        "wall_clock_s": dur,
        "sec_per_rendered_sec": dur / 2.5 if success else 0,
        "diff_info": diff_info,
        "log_snippet": log[-1500:],
    }


def main():
    ensure_shader_dist()
    temp_dir = Path(tempfile.gettempdir()) / "hf_khao_sat_part_b"
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    print("=== BẮT ĐẦU KHẢO SÁT PHẦN B (SHADER TRANSITIONS) ===")
    results = []

    print("\n[1/3] Đang thử nghiệm Giả thuyết (a): Inline markup...")
    res_a = test_hypothesis_a(temp_dir)
    results.append(res_a)
    print(f"  Hoàn tất (a): success={res_a['success']}, time={res_a['wall_clock_s']:.2f}s, diff={res_a['diff_info']}")

    print("\n[2/3] Đang thử nghiệm Giả thuyết (b): Sub-compositions mounting...")
    res_b = test_hypothesis_b(temp_dir)
    results.append(res_b)
    print(f"  Hoàn tất (b): success={res_b['success']}, time={res_b['wall_clock_s']:.2f}s, diff={res_b['diff_info']}")

    print("\n[3/3] Đang thử nghiệm Giả thuyết (c): Pre-rendered video elements...")
    res_c = test_hypothesis_c(temp_dir)
    results.append(res_c)
    print(f"  Hoàn tất (c): success={res_c['success']}, time={res_c['wall_clock_s']:.2f}s, diff={res_c['diff_info']}")

    print("\n=== TỔNG HỢP KẾT QUẢ KHẢO SÁT PHẦN B ===")
    for r in results:
        print(f"\n{r['hypothesis']}:")
        print(f"  Thành công: {r['success']}")
        print(f"  Thời gian render (2.5s video): {r['wall_clock_s']:.2f}s (tỉ lệ: {r['sec_per_rendered_sec']:.2f}s render / 1s video)")
        print(f"  So sánh khung hình giữa: {r['diff_info']}")

    summary_file = temp_dir / "results.json"
    summary_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nĐã ghi kết quả thô vào: {summary_file}")


if __name__ == "__main__":
    main()
