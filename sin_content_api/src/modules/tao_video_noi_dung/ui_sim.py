"""Dựng giao diện giấy với chữ thật; chỉ đọc HTML cục bộ, không truy cập mạng."""
from __future__ import annotations

import base64
import html
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from src.media_process import run_media_command
from src.modules.media_studio.video_processor import VIETSUB_FONT_PATH, video_processor
from .planner import UiScene


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
    * {{box-sizing:border-box}} body {{margin:0;background:#112c40;color:#163344;font-family:Viet,sans-serif}}
    main {{margin:6vh 6vw;padding:4vh 4vw;background:#faf5e9;border-radius:28px;box-shadow:20px 24px 0 #081f30}}
    header {{border-bottom:3px solid #178777;padding-bottom:24px;margin-bottom:28px}}
    small {{color:#386b6a;letter-spacing:3px;font-size:22px}} h1 {{margin:12px 0 0;font-size:48px}}
    #messages {{display:flex;flex-direction:column;gap:24px;font-size:36px}}
    .message {{max-width:94%;padding:20px 28px;background:#fffdf7;border:2px solid #c4d9ce;border-radius:18px;
      box-shadow:8px 9px 0 #dce7db;animation:arrive .36s both;overflow-wrap:anywhere}}
    .message.customer {{align-self:flex-end;background:#e4eee6}}
    .message.ai {{border-left:9px solid #178777}}
    strong {{font-size:.65em;color:#22685f}} p {{margin:8px 0 0;white-space:pre-wrap;line-height:1.4}}
    footer {{margin-top:32px;padding:24px;background:#14675e;color:white;font-size:30px;border-radius:12px}}
    .DASHBOARD #messages {{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}}
    .DASHBOARD .message,.AI_PANEL .message {{max-width:100%;width:100%}}
    @keyframes arrive {{from {{opacity:0;transform:translateY(20px)}} to {{opacity:1;transform:translateY(0)}}}}
    </style><main class="{scene.layout}"><header><small>Baha · Giải pháp doanh nghiệp</small>
    <h1>{titles[scene.layout]}</h1></header><section id="messages">{cards}</section>{highlight}</main></html>'''


def render_ui_scene(scene: UiScene, style_snapshot: dict, duration_seconds: int, aspect_ratio: str, out_path: Path) -> dict:
    if aspect_ratio not in {"9:16", "16:9"} or not 1 <= duration_seconds <= 10:
        raise ValueError("UI_RENDER_DIMENSIONS_OR_DURATION_INVALID")
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
