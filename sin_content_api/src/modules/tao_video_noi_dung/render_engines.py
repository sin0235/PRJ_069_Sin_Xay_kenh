"""Chọn engine dựng clip cảnh giấy: playwright (mặc định, đã chạy trên NAS), hyperframes hoặc remotion.

Cả ba dùng đúng một trang cảnh (`diagram_scene.html`, hàm thuần của thời gian) và cùng một hợp đồng đầu ra: MP4 H.264 30 khung hình mỗi giây,
yuv420p, không âm thanh, đúng độ dài. Chọn engine bằng `style_snapshot["render_engine"]` hoặc biến môi trường `CONTENT_VIDEO_RENDER_ENGINE`.
Engine Node (hyperframes, remotion) lỗi hoặc thiếu thì quay về playwright trừ khi `CONTENT_VIDEO_RENDER_FALLBACK=0`.
Cảnh chữ cũ (CHAT, AI_PANEL, DASHBOARD) và khung 9:16 luôn dùng playwright.
"""
from __future__ import annotations

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
    name = str(configured or ("hyperframes" if "baha editorial motion" in str(style.get("style_name", "")).casefold() else "playwright")).lower()
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
        (project / "index.html").write_text(hyperframes_composition_html(scene, narration, duration_seconds, word_times, gsap_src="gsap.min.js", aspect_ratio=aspect_ratio, transparent_background=transparent_background), encoding="utf-8")
        shutil.copy(gsap, project / "gsap.min.js")
        (project / "hyperframes.json").write_text(json.dumps({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}), encoding="utf-8")
        raw = Path(tmp) / ("raw.mov" if transparent_background else "raw.mp4")
        # Không telemetry, không lệnh cloud, auth hay publish: chỉ `render` cục bộ.
        env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
        chrome = _chrome()
        if chrome:
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


def render_remotion(scene: UiScene, duration_seconds: int, out_path: Path, narration: str = "", word_times: list[float] | None = None) -> dict:
    root = engines_dir() / "remotion"
    cli = root / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    if not cli.is_file():
        raise EngineUnavailable("REMOTION_NOT_INSTALLED")
    node = _node()
    page_html = _diagram_html(diagram_payload(scene, narration, duration_seconds, word_times))
    bundle = _remotion_bundle(root, node, cli)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rm_", dir=out_path.parent, ignore_cleanup_errors=True) as tmp:
        props = Path(tmp) / "props.json"
        props.write_text(json.dumps({"html": page_html, "durationInFrames": duration_seconds * 30}, ensure_ascii=False), encoding="utf-8")
        raw = Path(tmp) / "raw.mp4"
        command = [node, str(cli), "render", str(bundle), "Scene", str(raw), f"--props={props}", "--codec=h264", "--muted", "--pixel-format=yuv420p",
                   f"--concurrency={_workers()}", "--log=error"]
        chrome = _chrome()
        if chrome:
            command.append(f"--browser-executable={chrome}")
        _run(command, root)
        return _normalize(raw, out_path, duration_seconds)


BACKENDS = {"hyperframes": render_hyperframes, "remotion": render_remotion}


def render_scene(scene: UiScene, style_snapshot: dict, duration_seconds: int, aspect_ratio: str, out_path: Path,
                 narration: str = "", word_times: list[float] | None = None, transparent_background: bool = False) -> dict:
    """Dựng clip cảnh bằng engine đã chọn; trả về meta của clip kèm `render_engine` là engine đã thật sự dùng."""
    engine = selected_engine(style_snapshot)
    portrait_diagram = engine == "hyperframes" and aspect_ratio == "9:16" and scene.layout in PORTRAIT_DIAGRAM_LAYOUTS
    if engine != "playwright" and scene.layout in DIAGRAM_LAYOUTS and (aspect_ratio == "16:9" or portrait_diagram) and 1 <= duration_seconds <= 20:
        try:
            backend = BACKENDS[engine]
            meta = backend(scene, duration_seconds, out_path, narration, word_times, aspect_ratio, transparent_background) if engine == "hyperframes" else backend(scene, duration_seconds, out_path, narration, word_times)
            return {**meta, "render_engine": engine}
        except (EngineUnavailable, RuntimeError, subprocess.SubprocessError, OSError) as exc:
            if transparent_background or os.environ.get("CONTENT_VIDEO_RENDER_FALLBACK", "1") == "0":
                raise
            logger.warning("RENDER_ENGINE_FALLBACK: %s không dựng được (%s); dùng playwright", engine, str(exc)[:300])
    meta = render_ui_scene(scene, style_snapshot, duration_seconds, aspect_ratio, out_path, narration=narration, word_times=word_times)
    return {**meta, "render_engine": "playwright"}


def assembly_mode(style_snapshot: dict | None) -> str:
    """Cách ghép cả video: classic (từng cảnh thành MP4 rồi video_processor ghép) hoặc hyperframes (cả video là một dự án HyperFrames:
    cảnh viết bằng GSAP, chuyển cảnh, phụ đề động, giọng). Chọn bằng style_snapshot["assembly"] hoặc CONTENT_VIDEO_ASSEMBLY."""
    name = str((style_snapshot or {}).get("assembly") or os.environ.get("CONTENT_VIDEO_ASSEMBLY") or "classic").lower()
    if name not in ("classic", "hyperframes"):
        raise ValueError("ASSEMBLY_MODE_INVALID")
    return name


def render_placeholder(out_path: Path, seconds: int, aspect_ratio: str = "16:9") -> dict:
    """Clip đen đúng độ dài, chỉ để giữ chỗ trong dây chuyền tài sản và QC khi cả video sẽ được dựng bằng HyperFrames (không tốn thời gian dựng cảnh)."""
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=30:d={seconds}",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-t", str(seconds), "-movflags", "+faststart", str(out_path),
    ], check=True, capture_output=True, timeout=120)
    return {**video_processor.probe_video(out_path), "render_engine": "hyperframes_assembly"}
