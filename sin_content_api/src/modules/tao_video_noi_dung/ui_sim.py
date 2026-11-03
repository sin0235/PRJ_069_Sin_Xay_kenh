"""Dựng giao diện giấy với chữ thật; chỉ đọc HTML cục bộ, không truy cập mạng."""
from __future__ import annotations

import base64
import html
import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.media_process import run_media_command
from src.modules.media_studio.video_processor import VIETSUB_FONT_PATH, video_processor
from .planner import DIAGRAM_LAYOUTS, PORTRAIT_DIAGRAM_LAYOUTS, UiScene, resolve_diagram_times

DIAGRAM_TEMPLATE = Path(__file__).with_name("diagram_scene.html")
CAMERA_MOTION_JS = Path(__file__).with_name("dieu_khien_may_quay.js").read_text(encoding="utf-8")


def _scene_html(scene: UiScene, style_snapshot: dict) -> str:
    titles = {"CHAT": "Hỗ trợ khách hàng", "AI_PANEL": "Trợ lý tri thức", "DASHBOARD": "Bảng thông tin"}
    roles = {"customer": "Khách hàng", "ai": "Trợ lý AI", "staff": "Nhân viên", "system": "Hệ thống"}
    cards = "".join(
        f'<article class="message {message.role}" style="animation-delay:{message.at_s}s">'
        f'<strong>{roles[message.role]}</strong><p>{html.escape(message.text)}</p></article>'
        for message in scene.messages
    )
    highlight = f'<footer>{html.escape(scene.highlight)}</footer>' if scene.highlight else ""
    font = base64.b64encode(Path(VIETSUB_FONT_PATH).read_bytes()).decode("ascii")
    return f'''<!doctype html><html lang="vi"><meta charset="utf-8"><style>
    @font-face {{font-family:Viet;src:url(data:font/ttf;base64,{font})}}
    * {{box-sizing:border-box}} body {{margin:0;background:radial-gradient(ellipse at 75% 18%,#142b49,#0B0F17 62%);color:#F2EEE6;font-family:Viet,sans-serif}}
    main {{margin:6vh 6vw;padding:4vh 4vw;background:linear-gradient(145deg,rgba(27,41,64,.98),rgba(16,24,39,.98));border:2px solid rgba(217,178,106,.65);border-radius:28px;box-shadow:0 24px 70px rgba(0,0,0,.5)}}
    header {{border-bottom:2px solid #D9B26A;padding-bottom:24px;margin-bottom:28px}}
    small {{color:#F6E2B0;letter-spacing:3px;font-size:22px}} h1 {{margin:12px 0 0;font-size:48px}}
    #messages {{display:flex;flex-direction:column;gap:24px;font-size:36px}}
    .message {{max-width:94%;padding:20px 28px;background:linear-gradient(135deg,#1C2A40,#131E30);border:1px solid #344256;border-radius:18px;
      box-shadow:0 12px 30px rgba(0,0,0,.28);animation:arrive .36s both;overflow-wrap:anywhere}}
    .message.customer {{align-self:flex-end;background:linear-gradient(135deg,#103D70,#0B2F59);border-color:#5FA8FF}}
    .message.ai {{border-left:9px solid #0562AF}}
    strong {{font-size:.65em;color:#F6E2B0}} p {{margin:8px 0 0;white-space:pre-wrap;line-height:1.4}}
    footer {{margin-top:32px;padding:24px;background:linear-gradient(100deg,#0562AF,#083D70);border:1px solid #5FA8FF;color:#F2EEE6;font-size:30px;border-radius:12px}}
    .DASHBOARD #messages {{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}}
    .DASHBOARD .message,.AI_PANEL .message {{max-width:100%;width:100%}}
    @keyframes arrive {{from {{opacity:0;transform:translateY(20px)}} to {{opacity:1;transform:translateY(0)}}}}
    </style><main class="{scene.layout}"><header><small>Baha · Giải pháp doanh nghiệp</small>
    <h1>{titles[scene.layout]}</h1></header><section id="messages">{cards}</section>{highlight}</main></html>'''


def diagram_payload(scene: UiScene, narration: str, duration_seconds: int, word_times: list[float] | None = None) -> dict:
    """Dữ liệu đưa vào mẫu cảnh giấy: dữ liệu đã kiểm cộng thời điểm từng sự kiện, suy từ vị trí cụm từ neo trong lời đọc."""
    spec = scene.diagram
    payload = spec.model_dump(exclude={"on"}, exclude_none=True)
    payload.update(kind=scene.layout, camera_motion=scene.diagram.camera_motion or "AUTO", dur=duration_seconds,
                   t=resolve_diagram_times(scene, narration, duration_seconds, word_times))
    return payload


def _diagram_stage_markup(width: int, height: int) -> str:
    planes = "".join(
        f'<svg id="{name}" class="plane {plane}" viewBox="0 0 {width} {height}" width="{width}" height="{height}"></svg>'
        for name, plane in (("back", "back"), ("sv", "middle"), ("front", "front"))
    )
    return (f'<div id="stage"><div id="rig" data-layout-allow-overflow>{planes}</div>'
            f'<svg id="caption" viewBox="0 0 {width} {height}" width="{width}" height="{height}"><g id="cap"></g></svg></div>')


def _diagram_html(payload: dict, aspect_ratio: str = "16:9", transparent_background: bool = False) -> str:
    font = base64.b64encode(Path(VIETSUB_FONT_PATH).read_bytes()).decode("ascii")
    scene_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    template = DIAGRAM_TEMPLATE.read_text(encoding="utf-8")
    if aspect_ratio == "9:16":
        template = template.replace("#stage { width: 1920px; height: 1080px;", "#stage { width: 1080px; height: 1920px;")
        template = template.replace(_diagram_stage_markup(1920, 1080), _diagram_stage_markup(width, height))
        template = template.replace("var W = 1920, H = 1080,", f"var W = {width}, H = {height},")
        template = template.replace("var fitS = function () { var s = Math.min(innerWidth / 1920, (innerHeight - (document.body.classList.contains(\"sach\") ? 0 : 50)) / 1080);",
                                   "var fitS = function () { var s = Math.min(innerWidth / W, (innerHeight - (document.body.classList.contains(\"sach\") ? 0 : 50)) / H);")
    return (template
            .replace("/*FONT_FACE*/", f"@font-face {{font-family:Viet;font-weight:400 800;src:url(data:font/ttf;base64,{font})}}")
            .replace("/*CAMERA_MOTION*/", CAMERA_MOTION_JS)
            .replace("/*SCENE_JSON*/", f"window.PORTRAIT={json.dumps(aspect_ratio == '9:16')};window.TRANSPARENT_BG={json.dumps(transparent_background)};window.SCENE={scene_json};"))


def hyperframes_composition_html(scene: UiScene, narration: str, duration_seconds: int, word_times: list[float] | None = None, gsap_src: str = "https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js", aspect_ratio: str = "16:9", transparent_background: bool = False) -> str:
    """Gói diagram_scene thuần thời gian thành một composition cho renderer HyperFrames hiện có."""
    if scene.layout not in DIAGRAM_LAYOUTS:
        raise ValueError("HYPERFRAMES_ONLY_FOR_DIAGRAM_LAYOUTS")
    if aspect_ratio not in {"9:16", "16:9"} or aspect_ratio == "9:16" and scene.layout not in PORTRAIT_DIAGRAM_LAYOUTS:
        raise ValueError("HYPERFRAMES_DIAGRAM_ASPECT_RATIO_INVALID")
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    html = _diagram_html(diagram_payload(scene, narration, duration_seconds, word_times), aspect_ratio, transparent_background)
    html = html.replace("performance.now()", "0")
    stage = _diagram_stage_markup(width, height)
    if stage not in html or "<head>" not in html or "</body>" not in html:
        raise ValueError("HYPERFRAMES_TEMPLATE_CHANGED")
    wrapped = (f'<div id="root" data-composition-id="main" data-start="0" data-duration="{duration_seconds}" data-width="{width}" data-height="{height}">'
               f'{stage}</div>')
    driver = ('<script>(function () { var drv = { t: 0 }, tl = gsap.timeline({ paused: true });'
              ' tl.to(drv, { t: %d, duration: %d, ease: "none", onUpdate: function () { window.setT(drv.t); } }, 0);'
              ' window.__timelines = window.__timelines || {}; window.__timelines["main"] = tl; tl.seek(0); })();</script>\n</body>') % (duration_seconds, duration_seconds)
    return html.replace(stage, wrapped, 1).replace("<head>", '<head>\n<script src="%s"></script>' % gsap_src, 1).replace("</body>", driver, 1)


def render_ui_scene(scene: UiScene, style_snapshot: dict, duration_seconds: int, aspect_ratio: str, out_path: Path, narration: str = "", word_times: list[float] | None = None) -> dict:
    diagram = scene.layout in DIAGRAM_LAYOUTS
    if aspect_ratio not in {"9:16", "16:9"} or not 1 <= duration_seconds <= (20 if diagram else 10):
        raise ValueError("UI_RENDER_DIMENSIONS_OR_DURATION_INVALID")
    if diagram and aspect_ratio != "16:9" and not (aspect_ratio == "9:16" and scene.layout in PORTRAIT_DIAGRAM_LAYOUTS):
        raise ValueError("DIAGRAM_REQUIRES_16_9")
    page_html = _diagram_html(diagram_payload(scene, narration, duration_seconds, word_times), aspect_ratio) if diagram else None
    times = [message.at_s for message in scene.messages]
    if times != sorted(times) or any(t >= duration_seconds for t in times):
        raise ValueError("UI_MESSAGE_TIME_INVALID")
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ui_sim_", dir=out_path.parent) as tmp:
        scratch = Path(tmp)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                page.route("**/*", lambda route: route.abort())
                if diagram:
                    # Cảnh giấy là hàm thuần của t: đặt t rồi chụp, không có hoạt ảnh tự chạy.
                    page.set_content(page_html)
                    page.evaluate("document.fonts.load('700 54px Viet').then(() => window.setT(0))")
                    for frame in range(duration_seconds * 30):
                        page.evaluate("t => window.setT(t)", frame / 30)
                        page.screenshot(path=str(scratch / f"{frame:04}.png"))
                else:
                    page.set_content(_scene_html(scene, style_snapshot))
                    page.evaluate("document.fonts.ready")
                    # Tính bố cục với mọi tin nhắn để không cắt chữ khi nội dung xuất hiện dần.
                    for font_size in (36, 32, 28, 24):
                        page.locator("#messages").evaluate("(el, size) => el.style.fontSize = size + 'px'", font_size)
                        fits = page.evaluate("""() => document.querySelector('main').getBoundingClientRect().bottom < innerHeight - 40
                            && [...document.querySelectorAll('.message,footer')].every(e => e.scrollWidth <= e.clientWidth)""")
                        if fits:
                            break
                    if not fits:
                        raise ValueError("UI_SCENE_TEXT_OVERFLOW")
                    page.evaluate("window.motion = document.getAnimations(); window.motion.forEach(a => a.pause())")
                    for frame in range(duration_seconds * 30):
                        page.evaluate("t => window.motion.forEach(a => a.currentTime = t)", frame * 1000 / 30)
                        page.screenshot(path=str(scratch / f"{frame:04}.png"))
            finally:
                browser.close()
        encoded = scratch / "scene.mp4"
        run_media_command([
            video_processor.ffmpeg_bin, "-y", "-v", "error", "-framerate", "30", "-i", str(scratch / "%04d.png"),
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", "30",
            "-t", str(duration_seconds), "-movflags", "+faststart", str(encoded),
        ], check=True, capture_output=True, timeout=180)
        meta = video_processor.probe_video(encoded)
        encoded.replace(out_path)
    return meta
