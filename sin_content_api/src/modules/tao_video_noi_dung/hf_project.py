"""Dựng CẢ video bằng một dự án HyperFrames: cảnh con viết bằng GSAP (hf_scenes), cảnh chưa có bản riêng bọc trang cũ, chuyển cảnh chồng lấn,
phụ đề động theo mốc từng từ, giọng đọc, kiểm `hyperframes check` trước khi dựng.

Luồng: storyboard + mốc sự kiện của từng shot + giọng đã đệm + mốc từ toàn video  ->  thư mục dự án  ->  check  ->  render  ->  MP4.
Cần Node 22 và gói hyperframes đã cài trong engines/hyperframes (xem render_engines.py). Không dùng lệnh cloud, auth, publish; tắt telemetry."""
from __future__ import annotations

import html
import json
import math
import os
import re
import shutil
import subprocess
import threading
import warnings
import wave
from pathlib import Path

from . import hf_blocks
from . import hf_camera
from . import hf_captions
from . import hf_layers
from . import hf_scenes
from . import hf_transitions
from .brand import display_json
from .planner import BLOCK_LAYOUTS
from .render_engines import ENGINE_TIMEOUT_SECONDS, EngineUnavailable, _chrome, _node, engines_dir
from .ui_sim import _diagram_html, diagram_payload
from src.modules.media_studio.video_processor import VIETSUB_FONT_PATH

BRAND_DIR = Path(__file__).with_name("brand")

OVERLAP = 0.3   # giây chồng lấn giữa hai cảnh liền nhau: cảnh sau trượt vào khi cảnh trước đang trượt ra
COLLAGE_SECONDS = 1.2   # chuyển cảnh "mảnh giấy xé lột ra" của kho khối HyperFrames (paper-collage-reveal, Apache-2.0), dùng ở ranh giới cách quãng
COLLAGE_LEAD = 0.15     # giây mảnh giấy phủ trước khi cảnh mới bắt đầu
COLLAGE_SPACING = 6
MAX_COLLAGE_TRANSITIONS = 2
BLOCKS_DIR = Path(__file__).resolve().parents[3] / "engines" / "hyperframes" / "blocks"
VIDEO_SUFFIXES = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
_RENDER_LOCK = threading.Lock()


def collage_transition_indices(shot_count: int) -> list[int]:
    return list(range(COLLAGE_SPACING, shot_count, COLLAGE_SPACING))[:MAX_COLLAGE_TRANSITIONS]


def collage_block(cid: str) -> str:
    """Bản khối paper-collage-reveal cho MỘT lần dùng: bỏ GSAP tải từ CDN (dự án đã có GSAP cục bộ), bỏ thẻ nội dung mặc định
    để lộ cảnh nằm dưới, và đổi mọi định danh sang cid để nhiều lần dùng trong cùng video không đè nhau."""
    text = (BLOCKS_DIR / "paper-collage-reveal.html").read_text(encoding="utf-8")
    text = re.sub(r'<script src="https://cdn\.jsdelivr\.net/npm/gsap@[^"]+"></script>\s*', "", text)
    text = re.sub(r'<div class="pcr-content-default">.*?</div>\s*', "", text, count=1, flags=re.S)
    return text.replace("pcr-", f"{cid}-").replace("paper-collage-reveal", cid)


BOUNDARY_TRANSITIONS: tuple[str, ...] = ("dissolve", "grid", "flash", *hf_transitions.TRANSITION_KINDS)  # các dạng mở đầu là fade, wipe, cắt phủ


def boundary_transition(kind: str, target: str, shot_start: float) -> str:
    """Chuyển cảnh viết bằng GSAP trên chính cảnh vào (hàm thuần của thời gian nên dựng lại ra đúng khung hình cũ).
    iris: cảnh mới mở ra từ giữa khung bằng vòng tròn; whip: cảnh mới trượt vào từ phải, mờ theo chiều ngang rồi nét lại;
    flash: chớp sáng ngắn che chỗ cắt (lớp #flash dùng chung)."""
    t0 = max(0.0, shot_start - 0.15)
    if kind == "iris":
        return (f'tl.fromTo("{target}", {{ clipPath: "circle(0% at 50% 50%)" }}, {{ clipPath: "circle(75% at 50% 50%)", duration: 0.6, ease: "power2.out" }}, {t0:.3f});\n'
                f'tl.set("{target}", {{ clipPath: "none" }}, {t0 + 0.62:.3f});\n')
    if kind == "whip":
        return (f'tl.fromTo("{target}", {{ xPercent: 100, filter: "blur(14px)" }}, {{ xPercent: 0, filter: "blur(0px)", duration: 0.5, ease: "power3.out" }}, {t0:.3f});\n'
                f'tl.set("{target}", {{ filter: "none" }}, {t0 + 0.52:.3f});\n')
    return (f'tl.fromTo("#flash", {{ opacity: 0 }}, {{ opacity: 0.85, duration: 0.1, ease: "power1.in" }}, {max(0.0, shot_start - 0.12):.3f});\n'
            f'tl.to("#flash", {{ opacity: 0, duration: 0.32, ease: "power2.out" }}, {shot_start:.3f});\n')


def hyperframes_cli() -> Path:
    cli = engines_dir() / "hyperframes" / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    if not cli.is_file():
        raise EngineUnavailable("HYPERFRAMES_NOT_INSTALLED")
    return cli


def legacy_scene(
    cid: str,
    scene,
    narration: str,
    seconds: int,
    lead: float,
    word_times: list[float] | None,
    aspect_ratio: str = "16:9",
    transparent_background: bool = False,
) -> str:
    """Cảnh chưa có bản viết trực tiếp: nhúng trang cũ trong iframe, một timeline GSAP điều khiển setT."""
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    page = _diagram_html(
        diagram_payload(scene, narration, seconds, word_times),
        aspect_ratio,
        transparent_background=transparent_background,
    ).replace("performance.now()", "0")
    total = seconds + lead
    return (f'<template>\n<style>[data-composition-id="{cid}"]{{position:absolute;inset:0;overflow:hidden}}[data-composition-id="{cid}"] iframe{{position:absolute;left:0;top:0;width:{width}px;height:{height}px;border:0}}</style>\n'
            f'<div id="root" data-composition-id="{cid}" data-width="{width}" data-height="{height}"><iframe id="{cid}-f" srcdoc="{html.escape(page, quote=True)}"></iframe></div>\n'
            f'<script>\nconst tl = gsap.timeline({{ paused: true }}), drv = {{ t: 0 }}, f = document.getElementById("{cid}-f"), L = {lead}, D = {seconds};\n'
            f'tl.to(drv, {{ t: {total}, duration: {total}, ease: "none", onUpdate: () => {{ const w = f.contentWindow; if (w && w.setT) w.setT(Math.max(0, Math.min(D - .02, drv.t - L))); }} }}, 0);\n'
            f'window.__timelines["{cid}"] = tl;\n</script>\n</template>\n')


def caption_groups(words: list[dict], max_words: int = 5, pause_ms: int = 220) -> list[list[dict]]:
    groups, current = [], []
    for index, word in enumerate(words):
        current.append(word)
        gap = words[index + 1]["start_ms"] - word["end_ms"] if index + 1 < len(words) else 10 ** 6
        if len(current) >= max_words or word["text"].rstrip().endswith((".", "!", "?", "…")) or (gap >= pause_ms and len(current) >= 3):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def captions_scene(words: list[dict], total: float, aspect_ratio: str = "16:9") -> str:
    """Phụ đề đổi màu theo mốc từng từ (gọi hf_captions.caption_composition)."""
    return hf_captions.caption_composition("karaoke", words, total, aspect_ratio)[0]


def build_project(
    out: Path, shots: list[dict], voice_wav: Path | None, words: list[dict] | None,
    transitions: bool | None = None, music_path: Path | None = None, sfx_cues: list[dict] | None = None,
    aspect_ratio: str = "16:9", media_layers: list[dict] | None = None, link_media: bool = False,
    transparent_background: bool = False, caption_style: str | None = None,
    ambient_seed: str | None = None,
) -> dict:
    """shots có thể là cảnh UiScene hoặc video MP4 đã xác minh; Trả về thông tin project."""
    if aspect_ratio not in {"9:16", "16:9"}:
        raise ValueError("HYPERFRAMES_ASPECT_RATIO_INVALID")
    if caption_style is None:
        caption_style = os.getenv("CONTENT_VIDEO_HF_CAPTION_STYLE") or "karaoke"
    if caption_style not in hf_captions.CAPTION_STYLES:
        warnings.warn(f"Cảnh báo: caption_style '{caption_style}' không hợp lệ, lùi về 'karaoke'")
        caption_style = "karaoke"
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    out = Path(out)
    if transitions is None:   # mặc định bật; CONTENT_VIDEO_HF_TRANSITIONS=0 để tắt chuyển cảnh mảnh giấy
        transitions = os.getenv("CONTENT_VIDEO_HF_TRANSITIONS", "1") != "0"
    shutil.rmtree(out, ignore_errors=True)
    (out / "compositions").mkdir(parents=True)
    fonts, brand, vendor = out / "assets" / "fonts", out / "assets" / "brand", out / "assets" / "vendor"
    for folder in (fonts, brand, vendor):
        folder.mkdir(parents=True)
    shutil.copy(VIETSUB_FONT_PATH, fonts / "be_vietnam_pro_semibold.ttf")
    shutil.copy(BRAND_DIR / "utm_helvetins.ttf", fonts / "utm_helvetins.ttf")
    for name in ("logo_doc_mau.png", "logo_ngang_mau.png", "logo_doc_am_ban.png"):
        shutil.copy(BRAND_DIR / name, brand / name)
    shutil.copy(engines_dir() / "vendor" / "gsap.min.js", vendor / "gsap.min.js")
    custom_ease = engines_dir() / "vendor" / "CustomEase.min.js"
    if custom_ease.is_file():
        shutil.copy(custom_ease, vendor / "CustomEase.min.js")   # plugin mà vài khối HyperFrames cần
    if voice_wav:
        shutil.copy(voice_wav, out / "assets" / "voice.wav")
    audio_tracks = []
    if voice_wav:
        audio_tracks.append('<audio id="voice" src="assets/voice.wav" data-start="0" data-duration="__DURATION__" data-volume="1"></audio>')
    if music_path:
        music_path = Path(music_path)
        if not music_path.is_file():
            raise FileNotFoundError("MUSIC_ASSET_NOT_FOUND")
        music_name = f"music{music_path.suffix.lower()}"
        shutil.copy(music_path, out / "assets" / music_name)
        audio_tracks.append(f'<audio id="music" src="assets/{music_name}" data-start="0" data-duration="__DURATION__" data-volume="0.126"></audio>')
    hosts, start, native, legacy, videos, collages, main_js = "", 0.0, [], [], [], 0, ""
    used_blocks: set[str] = set()
    flashes = 0
    cadence = []
    staged_media: dict[str, str] = {}
    camera_enabled = os.getenv("CONTENT_VIDEO_HF_CAMERA", "1") != "0"
    camera_scenes = 0
    last_non_collage_kind: str | None = None
    transition_kinds: list[str] = []
    transition_indices = collage_transition_indices(len(shots)) if transitions else []
    non_collage_transition_count = 0

    def stage_media(source: Path, preferred_name: str) -> str:
        source = Path(source).resolve()
        if not source.is_file() or source.suffix.lower() not in VIDEO_SUFFIXES:
            raise ValueError("HYPERFRAMES_VIDEO_ASSET_INVALID")
        key = str(source)
        if key not in staged_media:
            media_name = f"{Path(preferred_name).stem}{source.suffix.lower()}"
            destination = out / "assets" / media_name
            if link_media:
                try:
                    os.link(source, destination)
                except OSError as exc:
                    raise RuntimeError("HYPERFRAMES_MEDIA_LINK_FAILED") from exc
            else:
                shutil.copy(source, destination)
            staged_media[key] = media_name
        return staged_media[key]
    for index, shot in enumerate(shots):
        cid = f"s{index + 1:02d}"
        try:
            seconds = float(shot["seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("HYPERFRAMES_SHOT_DURATION_INVALID") from exc
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("HYPERFRAMES_SHOT_DURATION_INVALID")
        lead = OVERLAP if index else 0.0
        try:
            shot_start = float(shot.get("start_seconds", start))
        except (TypeError, ValueError) as exc:
            raise ValueError("HYPERFRAMES_SHOT_START_INVALID") from exc
        if not math.isfinite(shot_start) or shot_start < 0:
            raise ValueError("HYPERFRAMES_SHOT_START_INVALID")
        scene = shot.get("scene")
        media_path = shot.get("media_path")
        if media_path:
            source = Path(media_path)
            media_start = float(shot.get("media_start_seconds", 0))
            fit = shot.get("fit", "cover")
            effect = shot.get("effect", "none")
            fade_in = float(shot.get("fade_in_seconds", 0))
            if (not math.isfinite(media_start) or media_start < 0 or fit not in {"cover", "contain"}
                    or not math.isfinite(fade_in) or fade_in < 0 or fade_in > seconds
                    or effect not in {"none", "punch_in"}):
                raise ValueError("HYPERFRAMES_VIDEO_ASSET_INVALID")
            media_name = stage_media(source, f"video_{index + 1:02d}")
            transform = "transform:scale(1.06);" if effect == "punch_in" else ""
            hosts += (f'<video id="{cid}-video" class="clip" src="assets/{media_name}" data-start="{shot_start:.3f}" '
                      f'data-duration="{seconds:.3f}" data-media-start="{media_start:.3f}" data-playback-rate="1" '
                      f'data-track-index="{index + 1}" muted playsinline style="position:absolute;left:0;top:0;width:100%;height:100%;object-fit:{fit};z-index:{index + 1};{transform}"></video>\n')
            if fade_in:
                main_js += f'tl.fromTo("#{cid}-video", {{ opacity: 0 }}, {{ opacity: 1, duration: {fade_in:.3f}, ease: "none" }}, {shot_start:.3f});\n'
            videos.append(media_name)
        else:
            if scene is None:
                raise ValueError("HYPERFRAMES_SHOT_SCENE_MISSING")
            dump = display_json(scene.diagram.model_dump(exclude={"on"}, exclude_none=True))
            dump["kind"] = scene.layout
            if aspect_ratio == "9:16" and scene.layout in BLOCK_LAYOUTS:
                dump["portrait"] = True
            if transparent_background:
                dump["transparent"] = True
            if getattr(scene, "block", None):
                used_blocks.add(scene.block)
            if shot.get("block"):
                used_blocks.add(shot["block"])
            if scene.layout in BLOCK_LAYOUTS or (hasattr(hf_blocks, "BLOCK_SCENES") and scene.layout in hf_blocks.BLOCK_SCENES):
                try:
                    used_blocks.add(hf_blocks.pick_variant(scene.layout, dump).block)
                except Exception:
                    pass
            builder = hf_scenes.NATIVE.get(scene.layout) if aspect_ratio == "16:9" or scene.layout in BLOCK_LAYOUTS else None
            host_extra, host_css = "", ""
            if builder:
                native.append(scene.layout)
                built = builder(cid, dump, lead, seconds + lead, shot["events"])
                text, host_extra, host_css = built if isinstance(built, tuple) else (built, "", "")
                if scene.layout in BLOCK_LAYOUTS:   # khối tự vào cảnh; thoát bằng mờ dần ở 0,25 giây cuối để nhường cảnh sau
                    main_js += f'tl.to("#{cid}", {{ opacity: 0, duration: 0.25, ease: "power1.in" }}, {max(0.0, shot_start + seconds - 0.25):.3f});\n'
            else:
                legacy.append(scene.layout)
                text = legacy_scene(
                    cid, scene, shot["narration"], seconds, lead, shot.get("word_times"), aspect_ratio,
                    transparent_background=transparent_background,
                )
            (out / "compositions" / f"{cid}.html").write_text(text, encoding="utf-8")
            host_start = max(0.0, shot_start - lead)
            hosts += (f'<div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="{host_start:.3f}" data-duration="{seconds + lead:.3f}" '
                      f'data-track-index="{index + 1}" data-track-kind="graphics" data-width="{width}" data-height="{height}"{host_extra} style="z-index:{index + 1};{host_css}"></div>\n')
            layout = getattr(scene, "layout", None) or (scene.get("layout") if isinstance(scene, dict) else None)
            layout_str = str(layout or "")
            is_exempt = layout_str == "END_CARD" or layout_str.startswith("OPEN_")
            if camera_enabled and not is_exempt:
                main_js += hf_camera.camera_motion_js("push_in", f"#{cid}", host_start, seconds + lead)
                camera_scenes += 1
        lt_spec = hf_layers.lower_third_for_shot(shot)
        if lt_spec:
            lt_cid = f"lt_{cid}"
            used_blocks.add(lt_spec.block)
            lt_comp, lt_host = hf_layers.overlay_host(lt_spec, lt_cid, aspect_ratio)
            (out / "compositions" / f"{lt_cid}.html").write_text(lt_comp, encoding="utf-8")
            hosts += lt_host + "\n"
        if transitions and index in transition_indices:   # chỉ xé giấy ở ranh giới 6/12, tối đa hai lần mỗi video
            tid, collages = f"tr{index:02d}", collages + 1
            used_blocks.add("paper-collage-reveal")
            (out / "compositions" / f"{tid}.html").write_text(collage_block(tid), encoding="utf-8")
            tstart = max(0.0, shot_start - COLLAGE_LEAD)
            spread = "outward" if collages % 2 else "scatter"
            hosts += (f'<div id="{tid}" data-composition-id="{tid}" data-composition-src="compositions/{tid}.html" data-start="{tstart:.3f}" data-duration="{COLLAGE_SECONDS}" '
                      f'data-track-index="{40 + index}" data-track-kind="graphics" data-width="{width}" data-height="{height}" data-variable-values=\'{{"panels":6,"tone":"mixed","spread":"{spread}"}}\' '
                      f'style="z-index:{40 + index};--surface:#fbf3df;--accent-2:#c8a468;opacity:0"></div>\n')
            main_js += f'tl.fromTo("#{tid}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12, ease: "none" }}, {tstart:.3f});\n'
        elif transitions and index:   # xé giấy ở 6/12; các ranh giới khác luân phiên hiệu ứng
            non_collage_idx = non_collage_transition_count
            kind = BOUNDARY_TRANSITIONS[non_collage_idx % len(BOUNDARY_TRANSITIONS)]
            if last_non_collage_kind and kind == last_non_collage_kind:
                non_collage_idx += 1
                kind = BOUNDARY_TRANSITIONS[non_collage_idx % len(BOUNDARY_TRANSITIONS)]
            non_collage_transition_count = non_collage_idx + 1
            last_non_collage_kind = kind
            transition_kinds.append(kind)
            cadence_kind = {"dissolve": "fade", "grid": "wipe", "flash": "cut"}.get(kind, "wipe")
            cadence.append({"boundary": index, "type": cadence_kind})
            target = f"#{cid}-video" if media_path else f"#{cid}"
            prev_shot = shots[index - 1]
            prev_cid = f"s{index:02d}"
            prev_target = f"{prev_cid}-video" if prev_shot.get("media_path") else prev_cid
            curr_target = f"{cid}-video" if media_path else cid
            if kind == "flash":
                main_js += boundary_transition("flash", target, shot_start)
                flashes += 1
            else:
                transition_seconds = min(OVERLAP, seconds)
                t_start = max(0.0, shot_start - transition_seconds)
                main_js += hf_transitions.transition_js(kind, prev_target, curr_target, t_start, transition_seconds)
        start = max(start, shot_start + seconds)

    for index, layer in enumerate(media_layers or []):
        try:
            layer_start = float(layer["start_seconds"])
            layer_duration = float(layer["duration_seconds"])
            media_start = float(layer.get("media_start_seconds", 0))
            x, y = int(layer["x"]), int(layer["y"])
            layer_width, layer_height = int(layer["width"]), int(layer["height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("HYPERFRAMES_MEDIA_LAYER_INVALID") from exc
        fit = layer.get("fit", "contain")
        if (not math.isfinite(layer_start) or layer_start < 0 or not math.isfinite(layer_duration)
                or layer_duration <= 0 or not math.isfinite(media_start) or media_start < 0
                or fit not in {"cover", "contain"} or x < 0 or y < 0 or layer_width <= 0 or layer_height <= 0
                or x + layer_width > width or y + layer_height > height):
            raise ValueError("HYPERFRAMES_MEDIA_LAYER_INVALID")
        layer_duration = min(layer_duration, max(0.0, start - layer_start))
        if layer_duration <= 0:
            continue
        media_name = stage_media(Path(layer["path"]), f"overlay_{index + 1:03d}")
        hosts += (f'<video id="overlay-{index + 1:03d}" class="clip" src="assets/{media_name}" data-start="{layer_start:.3f}" '
                  f'data-duration="{layer_duration:.3f}" data-media-start="{media_start:.3f}" data-playback-rate="1" '
                  f'data-track-index="{100 + index}" muted playsinline style="position:absolute;left:{x}px;top:{y}px;'
                  f'width:{layer_width}px;height:{layer_height}px;object-fit:{fit};z-index:{100 + index}"></video>\n')
        videos.append(media_name)
    total = start
    ambient_enabled = os.getenv("CONTENT_VIDEO_HF_AMBIENT", "0") == "1"   # mặc định TẮT: lớp sao/hạt quá mờ để thấy mà làm dựng chậm; đặt =1 để bật
    ambient_layers_count = 0
    if ambient_enabled:
        effective_seed = ambient_seed if ambient_seed is not None else f"{aspect_ratio}:{round(total)}"
        amb_specs = hf_layers.ambient_for_video(effective_seed, total, aspect_ratio)
        ambient_layers_count = len(amb_specs)
        for amb_idx, amb_spec in enumerate(amb_specs):
            amb_cid = f"amb_{amb_idx + 1:02d}"
            used_blocks.add(amb_spec.block)
            amb_comp, amb_host = hf_layers.overlay_host(amb_spec, amb_cid, aspect_ratio)
            (out / "compositions" / f"{amb_cid}.html").write_text(amb_comp, encoding="utf-8")
            hosts += amb_host + "\n"
    for index, cue in enumerate(sfx_cues or []):
        source = Path(cue["path"])
        start_s, volume = float(cue["start_seconds"]), float(cue["volume"])
        if not source.is_file() or not math.isfinite(start_s) or start_s < 0 or not math.isfinite(volume) or not 0 <= volume <= 1:
            raise ValueError("SFX_CUE_INVALID")
        try:
            with wave.open(str(source), "rb") as audio_file:
                duration_s = audio_file.getnframes() / audio_file.getframerate()
        except (wave.Error, ZeroDivisionError) as exc:
            raise ValueError("SFX_ASSET_INVALID") from exc
        if start_s >= total or duration_s <= 0:
            continue
        sound_name = f"sfx_{index + 1:03d}.wav"
        shutil.copy(source, out / "assets" / sound_name)
        audio_tracks.append(
            f'<audio id="sfx-{index + 1:03d}" src="assets/{sound_name}" data-start="{start_s:.3f}" '
            f'data-duration="{min(duration_s, total - start_s):.3f}" data-volume="{volume:.3f}"></audio>'
        )
    if words:
        caption_html, host_extra = hf_captions.caption_composition(caption_style, words, total, aspect_ratio)
        (out / "compositions" / "captions.html").write_text(caption_html, encoding="utf-8")
        hosts += (f'<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{total:.3f}" '
                  f'data-track-index="90" data-track-kind="captions" data-width="{width}" data-height="{height}"{host_extra} style="z-index:100"></div>\n')
    if flashes:
        hosts += '<div id="flash" style="position:absolute;inset:0;background:#fff8e6;opacity:0;z-index:70;pointer-events:none"></div>\n'
    audio = "\n".join(audio_tracks).replace("__DURATION__", f"{total:.3f}")
    root_background = "transparent" if transparent_background else "#0a1c2b"
    background_markup = "" if transparent_background else '<div id="bg"></div>'
    used_vendor_files: set[str] = {"gsap.min.js", "CustomEase.min.js"}
    for b in sorted(used_blocks):
        try:
            used_vendor_files.update(hf_blocks.vendor_files_for(b))
        except Exception:
            pass
    extra_vendor_files = [f for f in sorted(used_vendor_files) if f not in {"gsap.min.js", "CustomEase.min.js"}]
    for extra_file in extra_vendor_files:
        shutil.copy(engines_dir() / "vendor" / extra_file, vendor / extra_file)
    extra_scripts = "".join(f'<script src="assets/vendor/{f}"></script>\n' for f in extra_vendor_files)
    (out / "index.html").write_text(
        f'<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width={width}, height={height}">\n<script src="assets/vendor/gsap.min.js"></script>\n<script src="assets/vendor/CustomEase.min.js"></script>\n{extra_scripts}'
        f'<style>@font-face{{font-family:"Viet";src:url(assets/fonts/be_vietnam_pro_semibold.ttf);font-weight:100 900}}html,body{{margin:0;width:{width}px;height:{height}px;overflow:hidden;background:{root_background}}}#bg{{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,#12324a 0%,#0a1c2b 62%,#06131d 100%)}}</style>\n</head>\n<body>\n'
        f'<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="{width}" data-height="{height}" data-motion-blur="on">\n{background_markup}\n{hosts}{audio}</div>\n'
        '<script>\nwindow.__timelines = window.__timelines || {};\nconst tl = gsap.timeline({ paused: true });\n' + main_js + 'window.__timelines["main"] = tl;\n</script>\n</body>\n</html>\n', encoding="utf-8")
    (out / "hyperframes.json").write_text(json.dumps({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}), encoding="utf-8")
    (out / "package.json").write_text(json.dumps({"name": "video-baha", "private": True, "type": "module"}), encoding="utf-8")
    return {
        "total_seconds": total,
        "collage_transitions": collages,
        "collage_transition_indices": transition_indices[:collages],
        "transition_cadence": cadence,
        "native_scenes": native,
        "legacy_scenes": legacy,
        "video_scenes": videos,
        "ambient_layers": ambient_layers_count,
        "camera_scenes": camera_scenes,
        "transition_kinds": transition_kinds,
    }


def build_timeline_project(out: Path, timeline, asset_path_resolver, transition_seconds: float = 0.0) -> dict:
    def field(item, name, default=None):
        return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)

    width, height = int(field(timeline, "width", 1080)), int(field(timeline, "height", 1920))
    aspect_ratio = {(1080, 1920): "9:16", (1920, 1080): "16:9"}.get((width, height))
    if aspect_ratio is None:
        raise ValueError("HYPERFRAMES_TIMELINE_DIMENSIONS_INVALID")
    clips = field(timeline, "clips", [])
    if not clips:
        raise ValueError("HYPERFRAMES_TIMELINE_CLIPS_MISSING")
    try:
        transition_seconds = float(transition_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError("HYPERFRAMES_TRANSITION_INVALID") from exc
    if not math.isfinite(transition_seconds):
        raise ValueError("HYPERFRAMES_TRANSITION_INVALID")
    transition_ms = round(min(max(0.0, transition_seconds), 0.5) * 1000)
    cursor_ms = 0
    shots = []
    # FFmpeg ghép clip theo thứ tự; tính lại mốc để giữ độ dài sau xfade.
    for index, clip in enumerate(clips):
        media_type = field(clip, "media_type", "video")
        if getattr(media_type, "value", media_type) != "video":
            raise ValueError("HYPERFRAMES_TIMELINE_MEDIA_TYPE_UNSUPPORTED")
        asset_id = field(clip, "asset_id", "")
        duration_ms = int(field(clip, "duration_ms", 0))
        start_ms = int(field(clip, "start_ms", 0))
        trim_in_ms = int(field(clip, "trim_in_ms", 0))
        if not asset_id or duration_ms <= 0 or start_ms < 0 or trim_in_ms < 0:
            raise ValueError("HYPERFRAMES_TIMELINE_CLIP_INVALID")
        fit = field(clip, "fit", "cover")
        fit = getattr(fit, "value", fit)
        shots.append({
            "shot_id": field(clip, "clip_id", f"clip-{index + 1}"), "scene": None,
            "media_path": asset_path_resolver(asset_id), "media_start_seconds": trim_in_ms / 1000,
            "start_seconds": cursor_ms / 1000,
            "seconds": (duration_ms + (transition_ms if index + 1 < len(clips) else 0)) / 1000,
            "fade_in_seconds": transition_ms / 1000 if index else 0,
            "fit": fit, "effect": field(clip, "effect", "none"), "narration": "",
        })
        cursor_ms += duration_ms

    layers = []
    for overlay in field(timeline, "overlays", []):
        asset_id = field(overlay, "asset_id", "")
        start_ms, duration_ms = int(field(overlay, "start_ms", 0)), int(field(overlay, "duration_ms", 0))
        if not asset_id or start_ms < 0 or duration_ms <= 0:
            raise ValueError("HYPERFRAMES_TIMELINE_OVERLAY_INVALID")
        layers.append({
            "path": asset_path_resolver(asset_id), "start_seconds": start_ms / 1000,
            "duration_seconds": duration_ms / 1000,
            "media_start_seconds": int(field(overlay, "trim_in_ms", 0)) / 1000,
            "x": int(field(overlay, "x", 0)), "y": int(field(overlay, "y", 0)),
            "width": int(field(overlay, "width", 320)), "height": int(field(overlay, "height", 480)),
            "fit": "contain",
        })
    return build_project(out, shots, None, None, transitions=False, aspect_ratio=aspect_ratio,
                         media_layers=layers, link_media=True)


def _env() -> dict:
    env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
    chrome = _chrome()
    if chrome:
        env.setdefault("PUPPETEER_EXECUTABLE_PATH", chrome)
        env.setdefault("HYPERFRAMES_BROWSER_PATH", chrome)
    return env


def check_project(project: Path) -> dict:
    """Cổng chất lượng: hyperframes check --json. Trả về {'errors': n, 'warnings': n, 'text': ...}; không ném lỗi."""
    result = subprocess.run([_node(), str(hyperframes_cli()), "check", "--json"], cwd=project, env=_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=ENGINE_TIMEOUT_SECONDS)
    stdout_text = result.stdout or ""
    stderr_text = result.stderr or ""
    try:
        data = json.loads(stdout_text[stdout_text.index("{"):]) if "{" in stdout_text else {}
    except (ValueError, json.JSONDecodeError):
        data = {}
    return {"returncode": result.returncode, "data": data, "text": (stdout_text + stderr_text)[-4000:]}


def render_project(
    project: Path,
    output: Path,
    workers: str | None = None,
    quality: str = "looks",
    transparent_background: bool = False,
) -> None:
    # Concurrency render mặc định = 1 (quy tắc Rule 9 và Rule 20).
    workers = str(workers or os.getenv("CONTENT_VIDEO_HF_WORKERS") or "1")
    command = [_node(), str(hyperframes_cli()), "render", "-q", quality, "-w", workers, "-o", str(output)]
    if transparent_background or str(output).lower().endswith(".mov"):
        command.extend(["--format=mov", "--prores-profile=4444"])
    with _RENDER_LOCK:
        result = subprocess.run(command, cwd=project, env=_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=int(os.getenv("CONTENT_VIDEO_HF_RENDER_TIMEOUT_SECONDS") or 3 * 3600))   # video 100 s trên 2 vCPU có thể quá 60 phút; job runner tối đa 350 phút
    if result.returncode != 0:
        stdout_err = (result.stderr or result.stdout or "")[-800:]
        raise RuntimeError("RENDER_ENGINE_FAILED: " + stdout_err)
