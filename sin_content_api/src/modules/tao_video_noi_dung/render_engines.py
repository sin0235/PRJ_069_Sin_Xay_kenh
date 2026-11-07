"""Chọn engine cảnh và giữ đường HTML/HyperFrames tương thích.

Remotion native là opt-in cho CHECKLIST, KPI_CARDS và BEFORE_AFTER; cảnh khác tiếp tục dùng composition Scene.
"""
from __future__ import annotations
from src.modules.tac_vu_tu_xa.client import offload, pipeline

import hashlib
import json
import logging
import math
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
NATIVE_REMOTION_LAYOUTS = frozenset(("CHECKLIST", "KPI_CARDS", "BEFORE_AFTER"))
NATIVE_REMOTION_FPS = 30
NATIVE_REMOTION_THEME = {"background": "#0B0F17", "surface": "#1C2A40", "ink": "#F2EEE6", "accent": "#D9B26A"}
NATIVE_REMOTION_ASSETS = {"font": "phong_chu/be_vietnam_pro_dam.ttf", "logo": "thuong_hieu/logo_ngang_mau.png"}
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


def native_event_frame(seconds: float, duration_in_frames: int) -> int:
    if not math.isfinite(seconds) or duration_in_frames < 1:
        raise ValueError("REMOTION_NATIVE_TIMING_INVALID")
    return min(duration_in_frames - 1, max(0, math.floor(seconds * NATIVE_REMOTION_FPS + 0.5)))


def native_remotion_props(scene: UiScene, duration_seconds: float, aspect_ratio: str, narration: str = "", word_times: list[float] | None = None) -> dict:
    if scene.layout not in NATIVE_REMOTION_LAYOUTS:
        raise ValueError("REMOTION_NATIVE_LAYOUT_UNSUPPORTED")
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("REMOTION_NATIVE_DURATION_INVALID")
    if aspect_ratio not in ("9:16", "16:9"):
        raise ValueError("REMOTION_NATIVE_ASPECT_RATIO_INVALID")
    if word_times is not None and (
        len(word_times) != len(narration.split())
        or any(isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time) for time in word_times)
        or any(current < previous for previous, current in zip(word_times, word_times[1:]))
    ):
        raise ValueError("REMOTION_NATIVE_WORD_TIMES_INVALID")
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    return {"schemaVersion": 1, "diagram": diagram_payload(scene, narration, duration_seconds, word_times),
            "fps": NATIVE_REMOTION_FPS,
            "durationInFrames": max(1, math.floor(duration_seconds * NATIVE_REMOTION_FPS + 0.5)),
            "width": width, "height": height, "theme": dict(NATIVE_REMOTION_THEME), "assets": dict(NATIVE_REMOTION_ASSETS)}


def native_remotion_enabled(scene: UiScene, style_snapshot: dict | None) -> bool:
    style = style_snapshot or {}
    return selected_engine(style) == "remotion" and style.get("remotion_native") is True and scene.layout in NATIVE_REMOTION_LAYOUTS


def renderer_revision(root: Path | None = None) -> str:
    root = root or engines_dir() / "remotion"
    paths = [*(root / "src").rglob("*"), root / "package.json", root / "package-lock.json"]
    if (root / "public").is_dir():
        paths.extend((root / "public").rglob("*"))
    digest = hashlib.sha256()
    for path in sorted(path for path in paths if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8")); digest.update(b"\0"); digest.update(path.read_bytes())
    return digest.hexdigest()


def native_remotion_fingerprint(scene: UiScene, duration_seconds: float, aspect_ratio: str, narration: str = "", word_times: list[float] | None = None) -> str:
    props = native_remotion_props(scene, duration_seconds, aspect_ratio, narration, word_times)
    raw = json.dumps({"renderer_revision": renderer_revision(), "props": props,
                      "timing_source": "word_times" if word_times is not None else "estimated"},
                     ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=ENGINE_TIMEOUT_SECONDS)
    if result.returncode != 0:
        raise RuntimeError("RENDER_ENGINE_FAILED: " + (result.stderr or result.stdout)[-600:])


def _normalize(source: Path, out_path: Path, duration_seconds: int) -> dict:
    """Đưa đầu ra của engine về cùng hợp đồng với luồng playwright để các bước sau không phân biệt engine."""
    encoded = source.with_name("normalized.mp4")
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-i", str(source), "-an",
        "-vf", "scale=in_range=auto:out_range=tv,format=yuv420p", "-color_range", "tv",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
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


def _remotion_bundle(root: Path, node: str, cli: Path, revision: str | None = None) -> Path:
    """Cache theo mã, lockfile và tài nguyên public; bundle được công bố nguyên tử."""
    revision = revision or renderer_revision(root)
    cache = Path(os.environ.get("PRJ069_ENGINES_CACHE") or Path(tempfile.gettempdir()) / "prj069_engines") / f"remotion_{revision[:16]}"
    if (cache / "index.html").is_file():
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=cache.name + ".dang_tao_", dir=cache.parent))
    staging.rmdir()
    try:
        _run([node, str(cli), "bundle", "src/index.js", f"--out-dir={staging}"], root)
        if (cache / "index.html").is_file():
            return cache
        try:
            staging.replace(cache)
        except OSError:
            if not (cache / "index.html").is_file():
                raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return cache


def render_remotion(scene: UiScene, duration_seconds: int, out_path: Path, narration: str = "", word_times: list[float] | None = None, aspect_ratio: str = "16:9", *, native: bool = False) -> dict:
    out_path = Path(out_path).resolve()
    root = engines_dir() / "remotion"
    cli = root / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    if not cli.is_file():
        raise EngineUnavailable("REMOTION_NOT_INSTALLED")
    node = _node()
    if native:
        props = native_remotion_props(scene, duration_seconds, aspect_ratio, narration, word_times)
        public = root / "public"
        if any(not (public / asset).is_file() for asset in NATIVE_REMOTION_ASSETS.values()):
            raise ValueError("REMOTION_NATIVE_ASSET_MISSING")
        variant, composition = "native", "CanhTrucTiep"
    else:
        props = {"html": _diagram_html(diagram_payload(scene, narration, duration_seconds, word_times), aspect_ratio),
                 "durationInFrames": duration_seconds * NATIVE_REMOTION_FPS}
        variant, composition = "legacy_html", "Scene"
    revision = renderer_revision(root)
    bundle = _remotion_bundle(root, node, cli, revision)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rm_", dir=out_path.parent, ignore_cleanup_errors=True) as tmp:
        props_path = Path(tmp) / "props.json"
        if not native:
            width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
            props.update(width=width, height=height)
        props_path.write_text(json.dumps(props, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        raw = Path(tmp) / "raw.mp4"
        command = [node, str(cli), "render", str(bundle), composition, str(raw), f"--props={props_path}", "--codec=h264", "--muted", "--pixel-format=yuv420p",
                   f"--concurrency={_workers()}", "--log=error"]
        chrome = _chrome()
        if chrome:
            command.append(f"--browser-executable={chrome}")
        _run(command, root)
        duration = props["durationInFrames"] / NATIVE_REMOTION_FPS if native else duration_seconds
        meta = _normalize(raw, out_path, duration)
        result = {**meta, "render_variant": variant}
        if native:
            fingerprint = json.dumps({"renderer_revision": revision, "props": props,
                                      "timing_source": "word_times" if word_times is not None else "estimated"},
                                     ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            result.update(renderer_revision=revision, render_fingerprint=hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
                          timing_source="word_times" if word_times is not None else "estimated")
        return result


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
    return {**video_processor.probe_video(out_path), **{key: meta[key] for key in ("render_engine", "render_variant", "renderer_revision", "render_fingerprint", "timing_source") if key in meta},
            "expanded_from": "16:9", "expand_mode": mode}


BACKENDS = {"hyperframes": render_hyperframes, "remotion": render_remotion}


@offload("render_scene", "RENDER_VISUAL", output="out_path")
def render_scene(scene: UiScene, style_snapshot: dict, duration_seconds: int, aspect_ratio: str, out_path: Path,
                 narration: str = "", word_times: list[float] | None = None, transparent_background: bool = False) -> dict:
    """Dựng clip cảnh bằng engine đã chọn; trả về meta của clip kèm `render_engine` là engine đã thật sự dùng."""
    out_path = Path(out_path).resolve()
    if (aspect_ratio == "9:16" and scene.layout in DIAGRAM_LAYOUTS and scene.layout not in PORTRAIT_DIAGRAM_LAYOUTS
            and not transparent_background):
        return _landscape_scene_in_portrait(scene, style_snapshot, duration_seconds, out_path, narration, word_times)
    engine = selected_engine(style_snapshot)
    native = native_remotion_enabled(scene, style_snapshot)
    if engine == "remotion" and transparent_background:
        raise ValueError("REMOTION_ALPHA_UNSUPPORTED")
    if (engine == "remotion" and (style_snapshot or {}).get("remotion_native") is True and not native
            and os.environ.get("CONTENT_VIDEO_RENDER_FALLBACK", "1") == "0"):
        raise EngineUnavailable("REMOTION_NATIVE_LAYOUT_UNSUPPORTED")
    if native:
        native_remotion_props(scene, duration_seconds, aspect_ratio, narration, word_times)
    portrait_diagram = engine in ("hyperframes", "remotion") and aspect_ratio == "9:16" and scene.layout in PORTRAIT_DIAGRAM_LAYOUTS
    fallback_reason = None
    if engine != "playwright" and scene.layout in DIAGRAM_LAYOUTS and (aspect_ratio == "16:9" or portrait_diagram) and 1 <= duration_seconds <= 20:
        try:
            backend = BACKENDS[engine]
            if engine == "hyperframes":
                meta = backend(scene, duration_seconds, out_path, narration, word_times, aspect_ratio, transparent_background)
            elif native:
                meta = backend(scene, duration_seconds, out_path, narration, word_times, aspect_ratio=aspect_ratio, native=True)
            else:
                meta = backend(scene, duration_seconds, out_path, narration, word_times, aspect_ratio=aspect_ratio)
            result = {**meta, "render_engine": engine}
            if engine == "remotion":
                result.setdefault("render_variant", "native" if native else "legacy_html")
            return result
        except (EngineUnavailable, RuntimeError, subprocess.SubprocessError, OSError) as exc:
            if transparent_background or os.environ.get("CONTENT_VIDEO_RENDER_FALLBACK", "1") == "0":
                raise
            fallback_reason = f"{type(exc).__name__}: {exc}"
            logger.warning("RENDER_ENGINE_FALLBACK: %s không dựng được (%s); dùng playwright", engine, str(exc)[:300])
    elif engine == "remotion":
        fallback_reason = "REMOTION_LAYOUT_OR_DURATION_UNSUPPORTED"
        if os.environ.get("CONTENT_VIDEO_RENDER_FALLBACK", "1") == "0":
            raise EngineUnavailable(fallback_reason)
    meta = render_ui_scene(scene, style_snapshot, duration_seconds, aspect_ratio, out_path, narration=narration, word_times=word_times)
    return {**meta, "render_engine": "playwright", **({"render_variant": "fallback", "render_fallback_reason": fallback_reason} if engine == "remotion" else {})}


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
    out_path = Path(out_path).resolve()
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_media_command([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=30:d={seconds}",
        "-metadata", f"title=placeholder_{out_path.stem}",
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-t", str(seconds), "-movflags", "+faststart", str(out_path),
    ], check=True, capture_output=True, timeout=120)
    return {**video_processor.probe_video(out_path), "render_engine": "hyperframes_assembly"}
