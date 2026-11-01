"""Dựng CẢ video bằng một dự án HyperFrames: cảnh con viết bằng GSAP (hf_scenes), cảnh chưa có bản riêng bọc trang cũ, chuyển cảnh chồng lấn,
phụ đề động theo mốc từng từ, giọng đọc, kiểm `hyperframes check` trước khi dựng.

Luồng: storyboard + mốc sự kiện của từng shot + giọng đã đệm + mốc từ toàn video  ->  thư mục dự án  ->  check  ->  render  ->  MP4.
Cần Node 22 và gói hyperframes đã cài trong engines/hyperframes (xem render_engines.py). Không dùng lệnh cloud, auth, publish; tắt telemetry."""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import hf_scenes
from .brand import display_json
from .render_engines import ENGINE_TIMEOUT_SECONDS, EngineUnavailable, _chrome, _node, engines_dir
from .ui_sim import BRAND_DIR, _diagram_html, diagram_payload
from src.modules.media_studio.video_processor import VIETSUB_FONT_PATH

OVERLAP = 0.3   # giây chồng lấn giữa hai cảnh liền nhau: cảnh sau trượt vào khi cảnh trước đang trượt ra
COLLAGE_SECONDS = 1.2   # chuyển cảnh "mảnh giấy xé lột ra" của kho khối HyperFrames (paper-collage-reveal, Apache-2.0), dùng ở ranh giới cách quãng
COLLAGE_LEAD = 0.15     # giây mảnh giấy phủ trước khi cảnh mới bắt đầu
BLOCKS_DIR = Path(__file__).resolve().parents[3] / "engines" / "hyperframes" / "blocks"


def collage_block(cid: str) -> str:
    """Bản khối paper-collage-reveal cho MỘT lần dùng: bỏ GSAP tải từ CDN (dự án đã có GSAP cục bộ), bỏ thẻ nội dung mặc định
    để lộ cảnh nằm dưới, và đổi mọi định danh sang cid để nhiều lần dùng trong cùng video không đè nhau."""
    text = (BLOCKS_DIR / "paper-collage-reveal.html").read_text(encoding="utf-8")
    text = re.sub(r'<script src="https://cdn\.jsdelivr\.net/npm/gsap@[^"]+"></script>\s*', "", text)
    text = re.sub(r'<div class="pcr-content-default">.*?</div>\s*', "", text, count=1, flags=re.S)
    return text.replace("pcr-", f"{cid}-").replace("paper-collage-reveal", cid)


def hyperframes_cli() -> Path:
    cli = engines_dir() / "hyperframes" / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    if not cli.is_file():
        raise EngineUnavailable("HYPERFRAMES_NOT_INSTALLED")
    return cli


def legacy_scene(cid: str, scene, narration: str, seconds: int, lead: float, word_times: list[float] | None) -> str:
    """Cảnh chưa có bản viết trực tiếp: nhúng trang cũ trong iframe, một timeline GSAP điều khiển setT."""
    page = _diagram_html(diagram_payload(scene, narration, seconds, word_times)).replace("performance.now()", "0")
    total = seconds + lead
    return (f'<template>\n<style>[data-composition-id="{cid}"]{{position:absolute;inset:0;overflow:hidden}}[data-composition-id="{cid}"] iframe{{position:absolute;left:0;top:0;width:1920px;height:1080px;border:0}}</style>\n'
            f'<div id="root" data-composition-id="{cid}" data-width="1920" data-height="1080"><iframe id="{cid}-f" srcdoc="{html.escape(page, quote=True)}"></iframe></div>\n'
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


def captions_scene(words: list[dict], total: float) -> str:
    """Phụ đề động: mỗi nhóm 3 đến 5 từ, từ đang đọc đổi sang vàng đúng mốc, nhóm thoát gọn và bị ẩn hẳn sau khi thoát (theo captions.md)."""
    groups = caption_groups(words)
    markup, code = "", ""
    for g, group in enumerate(groups):
        start, end = max(.1, group[0]["start_ms"] / 1000 - .05), group[-1]["end_ms"] / 1000 + .1
        if g:   # chỉ một nhóm hiện cùng lúc: nhóm trước thoát trước khi nhóm sau vào
            start = max(start, groups[g - 1][-1]["end_ms"] / 1000 + .02)
        if g + 1 < len(groups):
            end = min(end, max(start + .3, groups[g + 1][0]["start_ms"] / 1000 - .08))
        spans = "".join(f'<span class="w" id="cap-{g}-{i}">{html.escape(w["text"])}</span> ' for i, w in enumerate(group))
        markup += f'<div class="g" id="cap-g{g}">{spans}</div>\n'
        code += f'tl.set("#cap-g{g}", {{ opacity: 0, visibility: "hidden" }}, 0);\ntl.set("#cap-g{g}", {{ visibility: "visible" }}, {start:.3f});\n'
        code += f'tl.fromTo("#cap-g{g}", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: .16, ease: "power3.out" }}, {start:.3f});\n'
        for i, w in enumerate(group):
            code += f'tl.to("#cap-{g}-{i}", {{ color: "#FFD54A", duration: .06, ease: "none" }}, {w["start_ms"] / 1000:.3f});\n'
        code += f'tl.to("#cap-g{g}", {{ opacity: 0, duration: .12, ease: "power2.in" }}, {end - .12:.3f});\ntl.set("#cap-g{g}", {{ opacity: 0, visibility: "hidden" }}, {end:.3f});\n'
    return (f'<template>\n<style>@font-face{{font-family:"Viet";src:url(\'assets/fonts/be_vietnam_pro_semibold.ttf\');font-weight:400 800}}\n'
            '[data-composition-id="captions"]{position:absolute;inset:0;font-family:"Viet",sans-serif}\n'
            '[data-composition-id="captions"] .g{position:absolute;left:0;right:0;bottom:38px;text-align:center;font-size:54px;font-weight:700;color:#fff;white-space:nowrap;opacity:0;visibility:hidden;'
            '-webkit-text-stroke:9px #06131d;paint-order:stroke fill;overflow:visible}</style>\n'
            f'<div id="root" data-composition-id="captions" data-width="1920" data-height="1080">\n{markup}</div>\n'
            f'<script>\nconst tl = gsap.timeline({{ paused: true }});\n{code}window.__timelines["captions"] = tl;\n</script>\n</template>\n')


def build_project(out: Path, shots: list[dict], voice_wav: Path | None, words: list[dict] | None, transitions: bool | None = None) -> dict:
    """shots: [{shot_id, scene (UiScene), narration, seconds, events (giây trong clip), word_times}]. Trả về thông tin dự án."""
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
    if voice_wav:
        shutil.copy(voice_wav, out / "assets" / "voice.wav")
    hosts, start, native, collages, main_js = "", 0.0, [], 0, ""
    for index, shot in enumerate(shots):
        cid = f"s{index + 1:02d}"
        seconds, lead = shot["seconds"], (OVERLAP if index else 0.0)
        scene = shot["scene"]
        dump = scene.diagram.model_dump(exclude={"on"}, exclude_none=True)
        dump = display_json(scene.diagram.model_dump(exclude={"on"}, exclude_none=True))
        builder = hf_scenes.NATIVE.get(scene.layout)
        if builder:
            native.append(scene.layout)
            text = builder(cid, dump, lead, seconds + lead, shot["events"])
        else:
            text = legacy_scene(cid, scene, shot["narration"], seconds, lead, shot.get("word_times"))
        (out / "compositions" / f"{cid}.html").write_text(text, encoding="utf-8")
        host_start = max(0.0, start - lead)
        hosts += (f'<div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="{host_start:.3f}" data-duration="{seconds + lead:.3f}" '
                  f'data-track-index="{index + 1}" data-track-kind="graphics" data-width="1920" data-height="1080" style="z-index:{index + 1}"></div>\n')
        if transitions and index % 2 == 1:   # cách quãng: mảnh giấy xé phủ cuối cảnh trước rồi lột ra để lộ cảnh mới
            tid, collages = f"tr{index:02d}", collages + 1
            (out / "compositions" / f"{tid}.html").write_text(collage_block(tid), encoding="utf-8")
            tstart = max(0.0, start - COLLAGE_LEAD)
            spread = "outward" if collages % 2 else "scatter"
            hosts += (f'<div id="{tid}" data-composition-id="{tid}" data-composition-src="compositions/{tid}.html" data-start="{tstart:.3f}" data-duration="{COLLAGE_SECONDS}" '
                      f'data-track-index="{40 + index}" data-track-kind="graphics" data-width="1920" data-height="1080" data-variable-values=\'{{"panels":6,"tone":"mixed","spread":"{spread}"}}\' '
                      f'style="z-index:{40 + index};--surface:#fbf3df;--accent-2:#c8a468;opacity:0"></div>\n')
            main_js += f'tl.fromTo("#{tid}", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12, ease: "none" }}, {tstart:.3f});\n'
        start += seconds
    total = start
    if words:
        (out / "compositions" / "captions.html").write_text(captions_scene(words, total), encoding="utf-8")
        hosts += (f'<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{total:.3f}" '
                  f'data-track-index="90" data-track-kind="captions" data-width="1920" data-height="1080" style="z-index:100"></div>\n')
    audio = f'<audio id="voice" src="assets/voice.wav" data-start="0" data-duration="{total:.3f}" data-volume="1"></audio>\n' if voice_wav else ""
    (out / "index.html").write_text(
        '<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=1920, height=1080">\n<script src="assets/vendor/gsap.min.js"></script>\n'
        '<style>html,body{margin:0;width:1920px;height:1080px;overflow:hidden;background:#0a1c2b}#bg{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,#12324a 0%,#0a1c2b 62%,#06131d 100%)}</style>\n</head>\n<body>\n'
        f'<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="1920" data-height="1080" data-motion-blur="on">\n<div id="bg"></div>\n{hosts}{audio}</div>\n'
        '<script>\nwindow.__timelines = window.__timelines || {};\nconst tl = gsap.timeline({ paused: true });\n' + main_js + 'window.__timelines["main"] = tl;\n</script>\n</body>\n</html>\n', encoding="utf-8")
    (out / "hyperframes.json").write_text(json.dumps({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"}}), encoding="utf-8")
    (out / "package.json").write_text(json.dumps({"name": "video-baha", "private": True, "type": "module"}), encoding="utf-8")
    return {"total_seconds": total, "collage_transitions": collages, "native_scenes": native, "legacy_scenes": [s["scene"].layout for s in shots if s["scene"].layout not in hf_scenes.NATIVE]}


def _env() -> dict:
    env = {**os.environ, "HYPERFRAMES_NO_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
    chrome = _chrome()
    if chrome:
        env.setdefault("PUPPETEER_EXECUTABLE_PATH", chrome)
    return env


def check_project(project: Path) -> dict:
    """Cổng chất lượng: hyperframes check --json. Trả về {'errors': n, 'warnings': n, 'text': ...}; không ném lỗi."""
    result = subprocess.run([_node(), str(hyperframes_cli()), "check", "--json"], cwd=project, env=_env(), capture_output=True, text=True, timeout=ENGINE_TIMEOUT_SECONDS)
    try:
        data = json.loads(result.stdout[result.stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        data = {}
    return {"returncode": result.returncode, "data": data, "text": (result.stdout + result.stderr)[-4000:]}


def render_project(project: Path, output: Path, workers: str = "2", quality: str = "looks") -> None:
    command = [_node(), str(hyperframes_cli()), "render", "-q", quality, "-w", workers, "-o", str(output)]
    result = subprocess.run(command, cwd=project, env=_env(), capture_output=True, text=True, timeout=ENGINE_TIMEOUT_SECONDS * 4)
    if result.returncode != 0:
        raise RuntimeError("RENDER_ENGINE_FAILED: " + (result.stderr or result.stdout)[-800:])
