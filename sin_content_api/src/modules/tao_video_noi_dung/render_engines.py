"""Chọn engine dựng clip cảnh giấy: playwright (mặc định, đã chạy trên NAS), hyperframes hoặc remotion.

Cả ba dùng đúng một trang cảnh (`diagram_scene.html`, hàm thuần của thời gian) và cùng một hợp đồng đầu ra: MP4 H.264 30 khung hình mỗi giây,
yuv420p, không âm thanh, đúng độ dài. Chọn engine bằng `style_snapshot["render_engine"]` hoặc biến môi trường `CONTENT_VIDEO_RENDER_ENGINE`.
Engine Node (hyperframes, remotion) lỗi hoặc thiếu thì quay về playwright trừ khi `CONTENT_VIDEO_RENDER_FALLBACK=0`.
Cảnh chữ cũ (CHAT, AI_PANEL, DASHBOARD) và khung 9:16 luôn dùng playwright.
"""
from __future__ import annotations
from src.modules.tac_vu_tu_xa.client import offload, pipeline

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.media_process import run_media_command
from src.modules.media_studio.video_processor import video_processor
from .planner import DIAGRAM_LAYOUTS, PORTRAIT_DIAGRAM_LAYOUTS, UiScene
from .ui_sim import _diagram_html, diagram_payload, hyperframes_composition_html, render_ui_scene

logger = logging.getLogger(__name__)
ENGINES = ("playwright", "hyperframes", "remotion")
ENGINE_TIMEOUT_SECONDS = 900


class EngineUnavailable(RuntimeError):
    """Engine chưa được cài hoặc thiếu Node; khác với lỗi dựng giữa chừng."""


def engines_dir() -> Path:
    return Path(os.environ.get("PRJ069_ENGINES_DIR") or Path(__file__).resolve().parents[3] / "engines")


def selected_engine(style_snapshot: dict | None) -> str:
    style = style_snapshot or {}
    configured = style.get("render_engine") or os.environ.get("CONTENT_VIDEO_RENDER_ENGINE")
    name = str(configured or ("hyperframes" if "editorial motion" in str(style.get("style_name", "")).casefold() else "playwright")).lower()
    if name not in ENGINES:
        raise ValueError("RENDER_ENGINE_INVALID")
    return name


def _node() -> str:
    node = os.environ.get("PRJ069_NODE_BIN") or shutil.which("node")
    if not node:
        raise EngineUnavailable("NODE_NOT_FOUND")
    return node


def _chrome() -> str | None:
    """Chrome dùng chung cho engine Node: biến môi trường, hoặc Chromium của Playwright, hoặc Chrome hệ thống; None thì engine tự tìm."""
    for candidate in [os.environ.get("PRJ069_CHROME_BIN"), *sorted(Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/ms-playwright")).glob("chromium-*/chrome-linux*/chrome")),
                      r"C:\Program Files\Google\Chrome\Application\chrome.exe", "/usr/bin/chromium", "/usr/bin/google-chrome"]:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def _workers() -> str:
    return os.environ.get("PRJ069_ENGINE_WORKERS", "1")


def _run(command: list[str], cwd: Path, env: dict | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=ENGINE_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError("RENDER_ENGINE_FAILED: " + (result.stderr or result.stdout)[-600:])


def _normalize(source: Path, out_path: Path, duration_seconds: int) -> dict:
    """Đưa đầu ra của engine về cùng hợp đồng với luồng playwright để các bước sau không phân biệt engine."""
    encoded = source.with_name("normalized.mp4")
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-i", str(source), "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-r", "30", "-t", str(duration_seconds), "-movflags", "+faststart", str(encoded),
    ], check=True, capture_output=True, timeout=180)
    meta = video_processor.probe_video(encoded)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    encoded.replace(out_path)
    return meta


def render_hyperframes(scene: UiScene, duration_seconds: int, out_path: Path, narration: str = "", word_times: list[float] | None = None, aspect_ratio: str = "16:9", transparent_background: bool = False) -> dict:
    cli = engines_dir() / "hyperframes" / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    gsap = engines_dir() / "vendor" / "gsap.min.js"
    if not cli.is_file() or not gsap.is_file():
        raise EngineUnavailable("HYPERFRAMES_NOT_INSTALLED")
    node = _node()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hf_", dir=out_path.parent, ignore_cleanup_errors=True) as tmp:   # Windows: Chrome còn giữ tay cầm thư mục một lúc sau khi dựng xong
        project = Path(tmp) / "du_an"
        project.mkdir()
        from .planner import BLOCK_LAYOUTS
        if scene.layout in BLOCK_LAYOUTS:
            from .hf_project import build_project
            build_project(project, [{"scene": scene, "seconds": duration_seconds, "events": {},
                "narration": narration, "word_times": word_times}], None, None,
                transitions=False, aspect_ratio=aspect_ratio, transparent_background=transparent_background)
        else:
            (project / "index.html").write_text(hyperframes_composition_html(scene, narration, duration_seconds, word_times, gsap_src="gsap.min.js", aspect_ratio=aspect_ratio, transparent_background=transparent_background), encoding="utf-8")
        shutil.copy(gsap, project / "gsap.min.js")
        (project / "hyperframes.json").write_text(json.dumps({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}), encoding="utf-8")
        raw = Path(tmp) / ("raw.mov" if transparent_background else "raw.mp4")
        # Không telemetry, không lệnh cloud, auth hay publish: chỉ `render` cục bộ.
        env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
        chrome = _chrome()
        if chrome:
            env.setdefault("HYPERFRAMES_BROWSER_PATH", chrome)
            env.setdefault("PUPPETEER_EXECUTABLE_PATH", chrome)
        command = [node, str(cli), "render", "-q", "looks", "-w", _workers(), "-o", str(raw)]
        if transparent_background:
            command.extend(["--format=mov", "--prores-profile=4444"])
        _run(command, project, env)
        if transparent_background:
            meta = video_processor.probe_video(raw)
            if not meta.get("has_alpha"):
                raise RuntimeError("HYPERFRAMES_ALPHA_OUTPUT_MISSING")
            raw.replace(out_path)
            return meta
        return _normalize(raw, out_path, duration_seconds)


def _remotion_bundle(root: Path, node: str, cli: Path) -> Path:
    """Bundle một lần cho mọi cảnh (độ dài lấy từ props); tạo lại khi mã nguồn Remotion đổi."""
    digest = hashlib.sha256()
    for path in sorted([*(root / "src").rglob("*"), root / "package.json"]):
        if path.is_file():
            digest.update(path.read_bytes())
    cache = Path(os.environ.get("PRJ069_ENGINES_CACHE") or Path(tempfile.gettempdir()) / "prj069_engines") / f"remotion_{digest.hexdigest()[:16]}"
    if (cache / "index.html").is_file():
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    staging = cache.with_name(cache.name + ".dang_tao")
    shutil.rmtree(staging, ignore_errors=True)
    _run([node, str(cli), "bundle", "src/index.js", f"--out-dir={staging}"], root)
    staging.replace(cache)
    return cache


def render_remotion(scene: UiScene, duration_seconds: int, out_path: Path, narration: str = "", word_times: list[float] | None = None, aspect_ratio: str = "16:9") -> dict:
    root = engines_dir() / "remotion"
    cli = root / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    if not cli.is_file():
        raise EngineUnavailable("REMOTION_NOT_INSTALLED")
    node = _node()
    page_html = _diagram_html(diagram_payload(scene, narration, duration_seconds, word_times), aspect_ratio)
    bundle = _remotion_bundle(root, node, cli)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rm_", dir=out_path.parent, ignore_cleanup_errors=True) as tmp:
        props = Path(tmp) / "props.json"
        width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
        props.write_text(json.dumps({"html": page_html, "durationInFrames": duration_seconds * 30, "width": width, "height": height}, ensure_ascii=False), encoding="utf-8")
        raw = Path(tmp) / "raw.mp4"
        command = [node, str(cli), "render", str(bundle), "Scene", str(raw), f"--props={props}", "--codec=h264", "--muted", "--pixel-format=yuv420p",
                   f"--concurrency={_workers()}", "--log=error"]
        chrome = _chrome()
        if chrome:
            command.append(f"--browser-executable={chrome}")
        _run(command, root)
        return _normalize(raw, out_path, duration_seconds)


PORTRAIT_SIZE = (1080, 1920)
_LANDSCAPE_IN_PORTRAIT_HEIGHT = 608   # 1080 * 9 / 16, làm tròn chẵn
_REFLECTION_ALPHA = 0.34


def expand_landscape_to_portrait(src: Path, dst: Path) -> None:
    """Đặt clip 16:9 ở giữa khung 9:16, phần trên và dưới được mở rộng bằng bản phản chiếu mờ dần trên nền nhòe cùng hình."""
    width, height = PORTRAIT_SIZE
    inner = _LANDSCAPE_IN_PORTRAIT_HEIGHT
    top = (height - inner) // 2
    seconds = max(0.1, float(video_processor.probe_video(src).get("duration_seconds") or 6))
    level = f"0x{round(255 * _REFLECTION_ALPHA):02x}{round(255 * _REFLECTION_ALPHA):02x}{round(255 * _REFLECTION_ALPHA):02x}"

    def fade(first: str, second: str) -> str:   # mặt nạ độ mờ dựng sẵn một lần, nhanh hơn tính từng điểm ảnh
        return f"gradients=s={width}x{inner}:r=30:d={seconds:.3f}:c0={first}:c1={second}:x0=0:y0=0:x1=0:y1={inner}:speed=0.00001:n=2,format=gray"

    mirror = f"scale={width // 2}:{inner // 2},vflip,gblur=sigma=2.5,scale={width}:{inner},format=rgba"   # nhòe ở nửa độ phân giải cho nhanh
    graph = (
        "[0:v]split=4[a][b][c][d];"
        f"[a]scale={width // 4}:{height // 4}:force_original_aspect_ratio=increase,crop={width // 4}:{height // 4},gblur=sigma=7,scale={width}:{height},eq=brightness=-0.10:saturation=0.85[bg];"
        f"[b]scale={width}:{inner}:flags=lanczos[fg];"
        f"[c]{mirror}[cr];[1:v][cr]scale2ref=flags=bicubic[m1][cr2];[cr2][m1]alphamerge[below];"
        f"[d]{mirror}[dr];[2:v][dr]scale2ref=flags=bicubic[m2][dr2];[dr2][m2]alphamerge[above];"
        f"[bg][above]overlay=0:{top - inner}[t1];[t1][below]overlay=0:{top + inner}[t2];[t2][fg]overlay=0:{top},format=yuv420p[out]"
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_media_command([
            video_processor.ffmpeg_bin, "-y", "-v", "error", "-i", str(src),
            "-f", "lavfi", "-i", fade(level, "0x000000"),   # dưới clip: đậm sát mép rồi mờ dần
            "-f", "lavfi", "-i", fade("0x000000", level),   # trên clip: mờ dần rồi đậm sát mép
            "-filter_complex", graph, "-map", "[out]",
            "-an", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{seconds:.3f}", str(dst),
        ], check=True, capture_output=True, text=True, timeout=600)
    except subprocess.CalledProcessError as exc:
        tail = " ".join((exc.stderr or "").split())[-100:]
        raise RuntimeError(f"VIDEO_EXPAND_PORTRAIT_FAILED: {tail}") from exc


def _expand_with_fallback(src: Path, dst: Path) -> str:
    """Bản có phản chiếu; nếu ffmpeg trên máy không chạy được bộ lọc đó thì dùng hàm mở rộng nền nhòe đã có sẵn và đã chạy trên runner."""
    try:
        expand_landscape_to_portrait(src, dst)
        return "reflection"
    except Exception as exc:
        logger.warning("EXPAND_REFLECTION_FALLBACK: %s", str(exc)[:200])
        dst.unlink(missing_ok=True)
        video_processor.expand_16_9_to_9_16(input_video_path=src, output_video_path=dst, remove_watermark=False)
        return "blur"


def _landscape_scene_in_portrait(scene, style_snapshot, duration_seconds, out_path, narration, word_times) -> dict:
    """Sơ đồ chỉ có bản 16:9: dựng khung ngang rồi mở rộng thành khung dọc, để video 9:16 dùng được mọi loại sơ đồ."""
    with tempfile.TemporaryDirectory(prefix="ngang_", dir=out_path.parent, ignore_cleanup_errors=True) as tmp:
        landscape = Path(tmp) / "ngang.mp4"
        try:
            meta = render_scene(scene, {**style_snapshot, "aspect_ratio": "16:9"}, duration_seconds, "16:9", landscape,
                                narration=narration, word_times=word_times)
            mode = _expand_with_fallback(landscape, out_path)
        except Exception as exc:
            if str(exc).startswith(("VIDEO_", "REMOTE_", "FLOW_")):
                raise
            raise RuntimeError(f"VIDEO_LANDSCAPE_IN_PORTRAIT_FAILED: {type(exc).__name__}: {' '.join(str(exc).split())[:80]}") from exc
    return {**video_processor.probe_video(out_path), "render_engine": meta.get("render_engine"), "expanded_from": "16:9", "expand_mode": mode}


BACKENDS = {"hyperframes": render_hyperframes, "remotion": render_remotion}


@offload("render_scene", "RENDER_VISUAL", output="out_path")
def render_scene(scene: UiScene, style_snapshot: dict, duration_seconds: int, aspect_ratio: str, out_path: Path,
                 narration: str = "", word_times: list[float] | None = None, transparent_background: bool = False) -> dict:
    """Dựng clip cảnh bằng engine đã chọn; trả về meta của clip kèm `render_engine` là engine đã thật sự dùng."""
    if (aspect_ratio == "9:16" and scene.layout in DIAGRAM_LAYOUTS and scene.layout not in PORTRAIT_DIAGRAM_LAYOUTS
            and not transparent_background):
        return _landscape_scene_in_portrait(scene, style_snapshot, duration_seconds, out_path, narration, word_times)
    engine = selected_engine(style_snapshot)
    portrait_diagram = engine in ("hyperframes", "remotion") and aspect_ratio == "9:16" and scene.layout in PORTRAIT_DIAGRAM_LAYOUTS
    if engine != "playwright" and scene.layout in DIAGRAM_LAYOUTS and (aspect_ratio == "16:9" or portrait_diagram) and 1 <= duration_seconds <= 20:
        try:
            backend = BACKENDS[engine]
            meta = backend(scene, duration_seconds, out_path, narration, word_times, aspect_ratio, transparent_background) if engine == "hyperframes" else backend(scene, duration_seconds, out_path, narration, word_times, aspect_ratio=aspect_ratio)
            return {**meta, "render_engine": engine}
        except Exception as exc:   # mọi lỗi dựng của engine (kể cả ValueError, KeyError, hết giờ) đều lùi sang Playwright để vẫn ra clip
            if transparent_background or os.environ.get("CONTENT_VIDEO_RENDER_FALLBACK", "1") == "0":
                raise
            logger.warning("RENDER_ENGINE_FALLBACK: %s không dựng được (%s); dùng playwright", engine, str(exc)[:300])
    meta = render_ui_scene(scene, style_snapshot, duration_seconds, aspect_ratio, out_path, narration=narration, word_times=word_times)
    return {**meta, "render_engine": "playwright"}


def assembly_mode(style_snapshot: dict | None) -> str:
    """Cách ghép cả video: classic (từng cảnh thành MP4 rồi video_processor ghép) hoặc hyperframes (cả video là một dự án HyperFrames:
    cảnh viết bằng GSAP, chuyển cảnh, phụ đề động, giọng). Chọn bằng style_snapshot["assembly"] hoặc CONTENT_VIDEO_ASSEMBLY."""
    style = style_snapshot or {}
    default = "hyperframes" if "editorial motion" in str(style.get("style_name", "")).casefold() else "classic"
    name = str(style.get("assembly") or os.environ.get("CONTENT_VIDEO_ASSEMBLY") or default).lower()
    if name not in ("classic", "hyperframes"):
        raise ValueError("ASSEMBLY_MODE_INVALID")
    return name


@offload("placeholder", "RENDER_VISUAL", output="out_path")
def render_placeholder(out_path: Path, seconds: int, aspect_ratio: str = "16:9") -> dict:
    """Clip đen đúng độ dài, chỉ để giữ chỗ trong dây chuyền tài sản và QC khi cả video sẽ được dựng bằng HyperFrames (không tốn thời gian dựng cảnh)."""
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=30:d={seconds}",
        "-metadata", f"title=placeholder_{out_path.stem}",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-t", str(seconds), "-movflags", "+faststart", str(out_path),
    ], check=True, capture_output=True, timeout=120)
    return {**video_processor.probe_video(out_path), "render_engine": "hyperframes_assembly"}
