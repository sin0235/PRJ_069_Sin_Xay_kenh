"""Cảnh viết trực tiếp cho HyperFrames: HTML, CSS và một timeline GSAP cho mỗi cảnh (không gọi lại trang setT cũ).

Mỗi hàm trả về (css, markup, js). `scaffold` gói thành một tệp cảnh con đúng hợp đồng HyperFrames: mọi thứ nằm trong <template>, gốc là #root,
timeline tạm dừng đăng ký ở window.__timelines[<id>], id có tiền tố, dùng fromTo. Ngôn ngữ chuyển động theo tài liệu của HyperFrames:
đến chậm đi gọn (expo.out, power4.out), chồng lấn khoảng 30 đến 50 phần trăm, không nảy, vị trí con trỏ tính từ phần tử thật.
Cảnh chưa có bản viết trực tiếp dùng bản bọc trang cũ (hf_project.legacy_scene)."""
from __future__ import annotations

import json
import math
from pathlib import Path

CAMERA_MOTION_JS = Path(__file__).with_name("dieu_khien_may_quay.js").read_text(encoding="utf-8")

# --------------------------------------------------------------------------------------------------------------------------------
# Khung chung
# --------------------------------------------------------------------------------------------------------------------------------
BASE_CSS = r'''
@font-face{font-family:"Viet";src:url('assets/fonts/be_vietnam_pro_semibold.ttf');font-weight:400 800}
@font-face{font-family:"BrandSans";src:url('assets/fonts/utm_helvetins.ttf')}
@@S@@{position:absolute;inset:0;font-family:"Viet",sans-serif;color:#F2EEE6;perspective:1900px;perspective-origin:50% 50%}
@@S@@ .cameraRig{position:absolute;inset:0;transform-style:preserve-3d;transform-origin:50% 50%;will-change:transform}
@@S@@ .cameraPlane{position:absolute;inset:0;transform-style:preserve-3d;backface-visibility:hidden}
@@S@@ .cam{position:absolute;inset:0}
@@S@@ .sheet{position:absolute;left:170px;top:70px;width:1576px;height:860px;border:2px solid rgba(217,178,106,.65);border-radius:24px;background:linear-gradient(145deg,rgba(27,41,64,.98),rgba(16,24,39,.98));
  box-shadow:0 24px 70px rgba(0,0,0,.5)}
@@S@@ .sheetBackground{position:absolute;left:170px;top:70px;width:1576px;height:860px;border:2px solid rgba(217,178,106,.65);border-radius:24px;background:linear-gradient(145deg,rgba(27,41,64,.98),rgba(16,24,39,.98));box-shadow:0 24px 70px rgba(0,0,0,.5)}
@@S@@ .sheetContent{background:transparent;border:0;box-shadow:none}
@@S@@ .fold,@@S@@ .tape,@@S@@ .pencil,@@S@@ .marker{display:none}
@@S@@ .title{position:absolute;left:80px;top:40px;font-size:46px;font-weight:700;white-space:nowrap}
@@S@@ .title .m{display:inline-block;overflow:hidden;vertical-align:top;padding-bottom:10px;margin-right:.28em}
@@S@@ .title .m>span{display:inline-block}
@@S@@ .unit{position:absolute;left:80px;top:100px;font-size:28px;color:#AAB7C8}
@@S@@ .sim{position:absolute;right:100px;top:44px;width:310px;height:52px;border-radius:12px;background:#1B2940;border:2px solid #D9B26A;color:#F6E2B0;font-size:28px;font-weight:600;display:flex;align-items:center;justify-content:center}
@@S@@ .tape{position:absolute;width:140px;height:34px;opacity:.78}
@@S@@ .pencil{position:absolute;left:68px;top:330px;width:34px;height:400px;background:#FABC11;box-shadow:6px 8px 0 rgba(8,31,48,.4)}
@@S@@ .pencil:before{content:"";position:absolute;left:0;top:-26px;width:34px;height:30px;border-radius:4px;background:#ED1B24}
@@S@@ .pencil:after{content:"";position:absolute;left:0;top:400px;border-left:17px solid transparent;border-right:17px solid transparent;border-top:52px solid #e9c9a0}
@@S@@ .marker{position:absolute;left:1814px;top:760px;width:44px;height:300px;border-radius:10px;background:#e9eef2;box-shadow:6px 8px 0 rgba(8,31,48,.4)}
@@S@@ .marker:before{content:"";position:absolute;left:0;top:150px;width:44px;height:150px;border-radius:10px;background:#FABC11}
@@S@@ .cursor{position:absolute;left:0;top:0;width:34px;height:44px;opacity:0;filter:drop-shadow(3px 4px 0 rgba(8,31,48,.35))}
@@S@@ .ring{position:absolute;left:0;top:0;width:60px;height:60px;margin:-30px 0 0 -30px;border-radius:50%;border:5px solid #0562AF;opacity:0}
'''

BASE_BODY = r'''
<div class="cameraRig" id="@@CID@@-rig" data-layout-allow-overflow>
<div class="cameraPlane back" id="@@CID@@-back"><div class="cam" id="@@CID@@-backCam">
  <div class="tape" style="left:156px;top:61px;background:#3fae9c"></div>
  <div class="tape" style="left:1646px;top:901px;background:#FABC11"></div>
  <div class="pencil" id="@@CID@@-pencil"></div><div class="marker" id="@@CID@@-marker"></div>
  <div class="sheetBackground"></div>
</div></div>
<div class="cameraPlane middle" id="@@CID@@-middle"><div class="cam" id="@@CID@@-cam">
  <div class="sheet sheetContent" id="@@CID@@-sheet">
    <div class="fold"></div>
    @@TITLE@@
    @@SIM@@
    @@BODY@@
  </div>
</div></div>
<div class="cameraPlane front" id="@@CID@@-front">
<div class="cam" id="@@CID@@-frontCam">
  <svg class="cursor" id="@@CID@@-cursor" viewBox="0 0 34 44"><path d="M2 2 L2 38 L11 30 L18 43 L25 40 L18 27 L31 27 Z" fill="#fff" stroke="#F2EEE6" stroke-width="3" stroke-linejoin="round"/></svg>
  <div class="ring" id="@@CID@@-ring"></div>
</div>
</div>
</div>
'''

JS_HELPERS = r'''
const R = document.querySelector('[data-composition-id="@@CID@@"]');
const q = (s) => R.querySelector(s), qa = (s) => Array.from(R.querySelectorAll(s));
const L = @@LEAD@@, D = @@DUR@@, EV = @@EV@@;
const CAMERA_CONFIG = @@CAMERA_CONFIG@@, cameraRig = q('#@@CID@@-rig'), cameraFocus = { x: 960, y: 540, from: D * .35, to: D * .55, points: [] };
const LAYERED_CAMERA = window.__bahaCamera.isLayered(CAMERA_CONFIG.kind, CAMERA_CONFIG.motion);
const cameraTargets = LAYERED_CAMERA ? [q('#@@CID@@-cam')] : [q('#@@CID@@-cam'), q('#@@CID@@-backCam'), q('#@@CID@@-frontCam')];
const T = (k) => EV[k] + L;
const tl = gsap.timeline({ paused: true });
const box = (el) => { const r = el.getBoundingClientRect(), b = R.getBoundingClientRect(), k = (b.width / 1920) || 1; return { x: (r.left - b.left) / k, y: (r.top - b.top) / k, w: r.width / k, h: r.height / k }; };
const geo = new Map();
const where = (el) => { if (!geo.has(el)) geo.set(el, box(el)); return geo.get(el); };
/* trang giấy trượt vào, rồi trôi rất nhẹ; trượt ra ở cuối cảnh (thoát ngắn hơn lúc vào) */
gsap.set(q('#@@CID@@-sheet'), { transformOrigin: '50% 50%' });
tl.fromTo(cameraTargets, { x: L > 0 ? 190 : 0, opacity: L > 0 ? 0 : 1 }, { x: 0, opacity: 1, duration: L > 0 ? .6 : .01, ease: 'power4.out' }, 0);
if (!LAYERED_CAMERA) tl.fromTo(cameraTargets, { scale: 1 }, { scale: 1.035, duration: D, ease: 'none' }, 0);
@@EXIT@@
/* tiêu đề: từng từ trồi lên từ mặt nạ, vào lệch nhau */
const words = qa('#@@CID@@-sheet .title .m>span');
if (words.length) tl.fromTo(words, { yPercent: 115, opacity: 0 }, { yPercent: 0, opacity: 1, duration: .75, ease: 'expo.out', stagger: .07 }, .18 + L);
const meta = qa('#@@CID@@-sheet .unit, #@@CID@@-sheet .sim');
if (meta.length) tl.fromTo(meta, { opacity: 0, y: -14 }, { opacity: 1, y: 0, duration: .5, ease: 'power3.out', stagger: .1 }, .5 + L);
/* con trỏ chuột giấy: tới phần tử thật trước mốc lời 0,45 giây rồi nhấn, gợn vòng xanh */
const cur = q('#@@CID@@-cursor'), ring = q('#@@CID@@-ring');
let curX = 1700, curY = 980, curShown = false, curPrev = 0;
function point(el, at, dx, dy) {
  const start = Math.max(curPrev + .12, at - .8);
  const tx = () => where(el).x + where(el).w * (dx === undefined ? .78 : dx), ty = () => where(el).y + where(el).h * (dy === undefined ? .78 : dy);
  if (!cameraFocus.points.length && cameraFocus.set) Object.assign(cameraFocus, { x: 960, y: 540 });
  cameraFocus.points.push({ x: tx(), y: ty(), at: Math.max(0, Math.min(D, at)) });
  if (!curShown) { curShown = true; tl.fromTo(cur, { opacity: 0, x: 1700, y: 980 }, { opacity: 1, duration: .25, ease: 'power2.out' }, start - .1); tl.set(cur, { x: curX, y: curY }, start - .1); }
  tl.to(cur, { x: tx, y: ty, duration: Math.max(.2, at - .08 - start), ease: 'power2.inOut' }, start);
  tl.to(cur, { scale: .86, duration: .07, ease: 'power2.in', transformOrigin: '0 0' }, at - .08);
  tl.to(cur, { scale: 1, duration: .16, ease: 'power3.out', transformOrigin: '0 0' }, at - .01);
  tl.set(ring, { x: tx, y: ty }, at - .01);
  tl.fromTo(ring, { scale: .3, opacity: .85 }, { scale: 1.7, opacity: 0, duration: .5, ease: 'power3.out', immediateRender: false }, at);
  curPrev = at;
}
/* bút dạ quang quét qua chữ; số khoanh bằng nét bút */
function sweep(el, at, dur) { tl.fromTo(el, { scaleX: 0, transformOrigin: '0% 50%' }, { scaleX: 1, duration: dur || .55, ease: 'power3.out' }, at); }
function draw(el, at, dur) { const len = el.getTotalLength ? el.getTotalLength() : 600; gsap.set(el, { strokeDasharray: len, strokeDashoffset: len }); tl.to(el, { strokeDashoffset: 0, duration: dur || .6, ease: 'power2.inOut' }, at); }
function count(el, from, to, at, dur, dec, suffix) { const o = { v: from }; tl.fromTo(o, { v: from }, { v: to, duration: dur || 1.2, ease: 'power2.out', onUpdate: () => { el.textContent = (dec ? o.v.toFixed(dec).replace('.', ',') : Math.round(o.v)) + (suffix || ''); } }, at); }
function punch(x, y, at, k) { if (!cameraFocus.set) Object.assign(cameraFocus, { from: Math.max(0, at - .9), to: Math.min(D, at + .7), set: true }); if (!cameraFocus.points.length) Object.assign(cameraFocus, { x, y }); if (!LAYERED_CAMERA) tl.to(cameraTargets, { scale: k || 1.07, transformOrigin: x + 'px ' + y + 'px', duration: .9, ease: 'power2.inOut' }, at); }
const cameraClock = { t: 0 };
tl.to(cameraClock, { t: D, duration: D, ease: 'none', onUpdate: () => {
  const c = window.__bahaCamera.transform(CAMERA_CONFIG.kind, CAMERA_CONFIG.motion, cameraClock.t, D, cameraFocus, 1920, 1080);
  const root = cameraRig.parentElement; root.style.perspective = c.perspective + 'px'; root.style.perspectiveOrigin = c.origin;
  cameraRig.style.transformOrigin = c.origin; cameraRig.style.transform = c.transform;
  ['back', 'middle', 'front'].forEach((name) => { const layer = q('#@@CID@@-' + name), pose = c.planes[name]; layer.style.transform = 'translateZ(' + pose.z.toFixed(2) + 'px)'; layer.style.filter = pose.blur_px > 0 ? 'blur(' + pose.blur_px.toFixed(2) + 'px)' : 'none'; });
} }, 0);
@@SCENE@@
cameraFocus.points.sort((a, b) => a.at - b.at);
if (cameraFocus.points.length > 1) Object.assign(cameraFocus, { from: cameraFocus.points[0].at, to: cameraFocus.points[cameraFocus.points.length - 1].at });
window.__timelines['@@CID@@'] = tl;
'''

EXIT_JS = r'''
 if (D > 3 && !LAYERED_CAMERA) tl.to(cameraTargets, { x: -210, opacity: 0.35, duration: .4, ease: 'power3.in' }, D - .42);
'''


def esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def title_html(text: str) -> str:
    return '<div class="title">' + "".join(f'<span class="m"><span>{esc(word)}</span></span>' for word in text.split()) + "</div>"


def scaffold(cid: str, scene: dict, css: str, body: str, js: str, lead: float, seconds: int, events: dict, simulated: bool = True, title: bool = True, exit_slide: bool = True) -> str:
    """Tệp cảnh con hoàn chỉnh."""
    sim = '<div class="sim">Dữ liệu mô phỏng</div>' if simulated else ""
    unit = f'<div class="unit">Đơn vị: {esc(scene["unit"])}</div>' if scene.get("unit") else ""
    page = BASE_BODY.replace("@@TITLE@@", (title_html(scene.get("title", "")) if title else "") + unit).replace("@@SIM@@", sim).replace("@@BODY@@", body)
    helpers = JS_HELPERS.replace("@@EXIT@@", EXIT_JS if exit_slide else "").replace("@@SCENE@@", js)
    helpers = helpers.replace("@@CAMERA_CONFIG@@", json.dumps({"kind": scene.get("kind", ""), "motion": scene.get("camera_motion", "AUTO")}))
    helpers = helpers.replace("@@LEAD@@", repr(round(lead, 3))).replace("@@DUR@@", str(seconds)).replace("@@EV@@", json.dumps({k: round(v, 3) for k, v in events.items()}))
    text = "<template>\n<style>\n" + BASE_CSS + css + "\n</style>\n<div id=\"root\" data-composition-id=\"@@CID@@\" data-width=\"1920\" data-height=\"1080\">" + page + "</div>\n<script>\n" + CAMERA_MOTION_JS + "\n" + helpers + "\n</script>\n</template>\n"
    return text.replace("@@S@@", '[data-composition-id="' + cid + '"]').replace("@@CID@@", cid)


# --------------------------------------------------------------------------------------------------------------------------------
# Các cảnh viết trực tiếp
# --------------------------------------------------------------------------------------------------------------------------------
def funnel(cid, scene, lead, seconds, ev):
    items = scene["items"]
    n, v0 = len(items), items[0]["value"]
    row_h = min(132, (640 - 16 * (n - 1)) / n)
    drops = [1 - items[i]["value"] / items[i - 1]["value"] for i in range(1, n)]
    bi = max(range(len(drops)), key=lambda i: drops[i])
    rows = ""
    for i, item in enumerate(items):
        wt = 220 + 780 * item["value"] / v0
        wb = 220 + 780 * items[i + 1]["value"] / v0 if i < n - 1 else wt * .82
        top = 250 + i * (row_h + 16) - 70
        a, b = (1000 - wt) / 2 / 10, (1000 - wb) / 2 / 10   # phần trăm chiều rộng khung 1000
        shade = ["#178777", "#0f5f57", "#1d4a6b", "#12324a", "#2c3e57"][i % 5]
        rows += (f'<div class="fr" id="{cid}-r{i}" style="top:{top:.0f}px;height:{row_h:.0f}px">'
                 f'<div class="fl">{esc(item["label"])}</div>'
                 f'<div class="fb" style="clip-path:polygon({a:.2f}% 0,{100 - a:.2f}% 0,{100 - b:.2f}% 100%,{b:.2f}% 100%);background:{shade}"><span class="fv" id="{cid}-v{i}">0</span><small>{esc(scene.get("unit", ""))}</small></div>'
                 f'<div class="fp" id="{cid}-p{i}">0%</div></div>')
    body = (rows + f'<div class="leakline" id="{cid}-line" style="top:{250 + (bi + 1) * (row_h + 16) - 8 - 70:.0f}px"></div>'
            f'<div class="leakbadge" id="{cid}-badge" style="top:{250 + (bi + 1) * (row_h + 16) - 8 - 70 - 36:.0f}px">Rơi {round(drops[bi] * 100)}%</div>')
    css = r'''
@@S@@ .fr{position:absolute;left:0;width:1496px}
@@S@@ .fl{position:absolute;left:80px;top:50%;margin-top:-22px;font-size:38px;font-weight:700;white-space:nowrap}
@@S@@ .fb{position:absolute;left:330px;width:1000px;height:100%;display:flex;align-items:center;justify-content:center;gap:14px;color:#fff;filter:drop-shadow(0 8px 0 rgba(11,42,63,.35))}
@@S@@ .fv{font-size:56px;font-weight:800}@@S@@ .fb small{font-size:28px;font-weight:600;margin-top:16px}
@@S@@ .fp{position:absolute;right:70px;top:50%;margin-top:-24px;font-size:42px;font-weight:800;color:#0f5f57}
@@S@@ .leakline{position:absolute;left:230px;width:1160px;height:0;border-top:7px dashed #d9694a;opacity:0}
@@S@@ .leakbadge{position:absolute;right:106px;width:300px;height:72px;border-radius:16px;background:#d9694a;color:#fff;font-size:42px;font-weight:800;display:flex;align-items:center;justify-content:center;opacity:0}
'''
    tpl = {"n": n, "bi": bi, "values": [it["value"] for it in items], "v0": v0}
    js = f'''
const F = {json.dumps(tpl)};
for (let i = 0; i < F.n; i++) {{
  const row = q('#{cid}-r' + i), at = T('stages') + i * .42;
  tl.fromTo(row, {{ opacity: 0, y: -46, scaleX: .72, transformOrigin: '50% 0%' }}, {{ opacity: 1, y: 0, scaleX: 1, duration: .85, ease: 'expo.out' }}, at);
  count(q('#{cid}-v' + i), 0, F.values[i], at + .15, 1.1, 0);
  const p = {{ v: 0 }};
  tl.fromTo(p, {{ v: 0 }}, {{ v: F.values[i] / F.v0 * 100, duration: 1.1, ease: 'power2.out', onUpdate: () => {{ q('#{cid}-p' + i).textContent = Math.round(p.v) + '%'; }} }}, at + .15);
}}
const lk = T('leak');
for (let i = 0; i < F.n; i++) if (i !== F.bi && i !== F.bi + 1) tl.to(q('#{cid}-r' + i), {{ opacity: .38, duration: .6, ease: 'power2.inOut' }}, lk);
tl.fromTo(q('#{cid}-line'), {{ opacity: 1, scaleX: 0, transformOrigin: '0% 50%' }}, {{ opacity: 1, scaleX: 1, duration: .7, ease: 'power3.inOut' }}, lk);
tl.fromTo(q('#{cid}-badge'), {{ opacity: 0, scale: .6, transformOrigin: '100% 100%' }}, {{ opacity: 1, scale: 1, duration: .55, ease: 'power4.out' }}, lk + .35);
point(q('#{cid}-badge'), lk + .55, .72, .7);
punch(1180, 560, lk + .1, 1.06);
'''
    return scaffold(cid, scene, css, body, js, lead, seconds, ev)


def checklist(cid, scene, lead, seconds, ev):
    steps = scene["steps"]
    n = len(steps)
    row_h = min(124, 560 / n)
    rows = ""
    for i, step in enumerate(steps):
        top = 20 + i * row_h
        rows += (f'<div class="cr" id="{cid}-r{i}" style="top:{top:.0f}px;height:{row_h:.0f}px"><div class="cb" id="{cid}-b{i}"><svg viewBox="0 0 60 60"><path id="{cid}-k{i}" d="M12 30 L26 44 L49 14" fill="none" stroke="#178777" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></svg></div>'
                 f'<div class="ct" id="{cid}-t{i}"><span class="hl" id="{cid}-h{i}"></span><span class="tx">{esc(step)}</span></div></div>')
    stamp = f'<div class="stamp" id="{cid}-stamp">{esc(scene["stamp"])}</div>' if scene.get("stamp") else ""
    body = f'<div class="cl"><div class="clip-bar">DANH SÁCH</div>{rows}</div>{stamp}'
    css = r'''
@@S@@ .cl{color:#1b2a41;position:absolute;left:330px;top:190px;width:900px;height:640px;border-radius:24px;background:#fffdf7;border:4px solid #cdbf9c;box-shadow:12px 14px 0 rgba(205,191,156,.55)}
@@S@@ .clip-bar{position:absolute;left:300px;top:-30px;width:300px;height:56px;border-radius:16px;background:#0f5f57;color:#fff;font-size:28px;font-weight:700;display:flex;align-items:center;justify-content:center}
@@S@@ .cr{position:absolute;left:40px;width:820px;border-bottom:3px dotted #e1d9c0}
@@S@@ .cb{position:absolute;left:10px;top:50%;margin-top:-30px;width:60px;height:60px;border-radius:12px;border:5px solid #b9ab86;background:#fffdf7}
@@S@@ .cb svg{position:absolute;inset:0;width:100%;height:100%}
@@S@@ .ct{position:absolute;left:100px;top:50%;margin-top:-30px;font-size:44px;font-weight:700;color:#6c8790;white-space:nowrap}
@@S@@ .hl{position:absolute;left:-8px;right:-8px;bottom:2px;height:26px;border-radius:8px;background:#FABC11;opacity:.7;transform:scaleX(0);transform-origin:0 50%;mix-blend-mode:multiply}
@@S@@ .tx{position:relative}
@@S@@ .stamp{position:absolute;left:1000px;top:690px;padding:12px 34px;border:9px solid #d9694a;border-radius:14px;color:#d9694a;font-size:54px;font-weight:800;opacity:0;background:rgba(255,253,247,.85)}
'''
    js = f'''
const N = {n};
tl.fromTo(q('.cl'), {{ opacity: 0, y: 40 }}, {{ opacity: 1, y: 0, duration: .8, ease: 'expo.out' }}, .25 + L);
tl.fromTo(qa('.cr'), {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: .6, ease: 'power3.out', stagger: .12 }}, .45 + L);
for (let i = 0; i < N; i++) {{
  const at = T('c' + i), k = q('#{cid}-k' + i);
  draw(k, at + .05, .4);
  tl.to(q('#{cid}-b' + i), {{ borderColor: '#178777', backgroundColor: '#dff1ec', duration: .25, ease: 'power2.out' }}, at);
  tl.to(q('#{cid}-t' + i), {{ color: '#163344', duration: .3, ease: 'power2.out' }}, at);
  sweep(q('#{cid}-h' + i), at + .1, .55);
  point(q('#{cid}-b' + i), at, .72, .72);
}}
if (q('#{cid}-stamp')) {{
  const at = T('stamp');
  tl.fromTo(q('#{cid}-stamp'), {{ opacity: 0, scale: 1.7, rotation: -2, transformOrigin: '50% 50%' }}, {{ opacity: 1, scale: 1, rotation: -8, duration: .38, ease: 'power4.out' }}, at);
  punch(1130, 760, at, 1.05);
  point(q('#{cid}-stamp'), at + .05, .85, .8);
}}
'''
    return scaffold(cid, scene, css, body, js, lead, seconds, ev)


def before_after(cid, scene, lead, seconds, ev):
    b, a = scene["docs"]
    def card(side, d, color):
        return (f'<div class="ba {side}" id="{cid}-{side}"><div class="bh" style="background:{color}">{esc(d["title"])}</div><div class="bl">{esc(d["label"])}</div>'
                f'<div class="bv" id="{cid}-{side}v">{esc(d["value"])}<i class="strike" id="{cid}-strike"></i></div></div>')
    body = card("before", b, "#8c7f5f") + card("after", a, "#178777") + f'<div class="pill" id="{cid}-pill">{esc(scene["diff_label"])}</div>'
    css = r'''
@@S@@ .ba{color:#1b2a41;position:absolute;top:180px;width:660px;height:520px;border-radius:20px;background:#fffdf7;border:4px solid #cdbf9c;box-shadow:12px 14px 0 rgba(205,191,156,.55);opacity:0;overflow:hidden}
@@S@@ .before{left:70px;background:#f3eedf}@@S@@ .after{left:850px;border-color:#3fae9c}
@@S@@ .bh{height:92px;color:#fff;font-size:44px;font-weight:800;display:flex;align-items:center;justify-content:center}
@@S@@ .bl{margin-top:34px;font-size:30px;color:#5b7a82;text-align:center}
@@S@@ .bv{position:relative;margin:56px auto 0;width:max-content;font-size:130px;font-weight:800;color:#6c6a5c;white-space:nowrap}
@@S@@ .after .bv{color:#0f5f57}
@@S@@ .strike{position:absolute;left:-14px;right:-14px;top:50%;height:12px;margin-top:-6px;border-radius:6px;background:#d9694a;transform:scaleX(0);transform-origin:0 50%;transform:rotate(-4deg) scaleX(0)}
@@S@@ .pill{position:absolute;left:518px;top:740px;width:540px;height:80px;border-radius:40px;background:#0f5f57;color:#fff;font-size:42px;font-weight:800;display:flex;align-items:center;justify-content:center;opacity:0}
'''
    js = f'''
tl.fromTo(q('#{cid}-before'), {{ opacity: 0, x: -90, rotation: -1.5 }}, {{ opacity: 1, x: 0, rotation: 0, duration: .85, ease: 'expo.out' }}, T('before'));
tl.fromTo(q('#{cid}-after'), {{ opacity: 0, x: 240, rotation: 1.5 }}, {{ opacity: 1, x: 0, rotation: 0, duration: .9, ease: 'expo.out' }}, T('after'));
tl.fromTo(q('#{cid}-strike'), {{ scaleX: 0, rotation: -4, transformOrigin: '0% 50%' }}, {{ scaleX: 1, rotation: -4, duration: .5, ease: 'power3.inOut' }}, T('after') + .35);
tl.fromTo(q('#{cid}-pill'), {{ opacity: 0, y: 24, scale: .86 }}, {{ opacity: 1, y: 0, scale: 1, duration: .55, ease: 'power4.out' }}, T('delta'));
point(q('#{cid}-afterv'), T('after') + .3, .8, .8);
point(q('#{cid}-pill'), T('delta') + .25, .82, .75);
punch(1180, 520, T('delta'), 1.05);
'''
    return scaffold(cid, scene, css, body, js, lead, seconds, ev)


def hub_spoke(cid, scene, lead, seconds, ev):
    steps = scene["steps"]
    n = len(steps)
    pts = []
    for i in range(n):
        an = -math.pi / 2 + 2 * math.pi * (i + .5) / n
        pts.append((790 + 590 * math.cos(an), 360 + 255 * math.sin(an)))   # tọa độ trong tờ giấy (gốc tại góc trái trên của tờ)
    nodes = "".join(f'<div class="hn" id="{cid}-n{i}" style="left:{x - 170:.0f}px;top:{y - 58:.0f}px">{esc(steps[i])}</div>' for i, (x, y) in enumerate(pts))
    lines = "".join(f'<line id="{cid}-l{i}" x1="{x:.0f}" y1="{y:.0f}" x2="790" y2="360" stroke="#178777" stroke-width="8" stroke-linecap="round"/>' for i, (x, y) in enumerate(pts))
    body = (f'<svg class="hsvg" viewBox="0 0 1576 860">{lines}</svg>{nodes}<div class="hring" id="{cid}-ring2"></div>'
            f'<div class="hub" id="{cid}-hub">{esc(scene.get("hub_label") or "Một nơi")}</div>')
    css = r'''
@@S@@ .hsvg{position:absolute;inset:0;width:1576px;height:860px}
@@S@@ .hn{color:#1b2a41;position:absolute;width:340px;height:116px;border-radius:20px;background:#fffdf7;border:5px dashed #d9694a;box-shadow:12px 14px 0 rgba(205,191,156,.55);display:flex;align-items:center;justify-content:center;font-size:38px;font-weight:700;opacity:0;text-align:center}
@@S@@ .hub{position:absolute;left:670px;top:240px;width:240px;height:240px;border-radius:50%;background:#178777;color:#fff;font-size:40px;font-weight:800;display:flex;align-items:center;justify-content:center;opacity:0;box-shadow:0 10px 0 rgba(11,42,63,.35);text-align:center}
@@S@@ .hring{position:absolute;left:670px;top:240px;width:240px;height:240px;border-radius:50%;border:6px solid #178777;opacity:0}
'''
    js = f'''
const NN = {n};
for (let i = 0; i < NN; i++) tl.fromTo(q('#{cid}-n' + i), {{ opacity: 0, y: 40, scale: .9 }}, {{ opacity: 1, y: 0, scale: 1, duration: .8, ease: 'expo.out' }}, T('nodes') + i * .24);
tl.fromTo(q('#{cid}-hub'), {{ opacity: 0, scale: .4 }}, {{ opacity: 1, scale: 1, duration: .8, ease: 'power4.out' }}, T('hub'));
tl.fromTo(q('#{cid}-ring2'), {{ opacity: .8, scale: 1 }}, {{ opacity: 0, scale: 1.9, duration: 1, ease: 'power3.out', immediateRender: false }}, T('hub') + .35);
for (let i = 0; i < NN; i++) {{
  const at = T('link') + i * .34, ln = q('#{cid}-l' + i);
  draw(ln, at, .6);
  tl.to(q('#{cid}-n' + i), {{ borderColor: '#178777', borderStyle: 'solid', backgroundColor: '#f1faf6', duration: .3, ease: 'power2.out' }}, at + .5);
}}
point(q('#{cid}-hub'), T('hub') + .5, .62, .72);
point(q('#{cid}-n' + (NN - 1)), T('link') + (NN - 1) * .34 + .4, .8, .8);
punch(960, 500, T('link'), 1.05);
'''
    return scaffold(cid, scene, css, body, js, lead, seconds, ev)


def timeline(cid, scene, lead, seconds, ev):
    steps, labels = scene["steps"], scene.get("labels") or [""] * len(scene["steps"])
    n = len(steps)
    xs = [190 + i * (1200 / (n - 1)) for i in range(n)]
    cards = "".join(
        f'<div class="tc" id="{cid}-c{i}" style="left:{x - 150:.0f}px;top:{(180 if i % 2 == 0 else 470):.0f}px"><b>{esc(labels[i])}</b><span>{esc(steps[i])}</span></div>'
        f'<div class="tm" id="{cid}-m{i}" style="left:{x - 30:.0f}px"></div>' for i, x in enumerate(xs))
    body = f'<div class="tbar"></div><div class="tfill" id="{cid}-fill"></div>{cards}'
    css = r'''
@@S@@ .tbar{position:absolute;left:100px;top:395px;width:1380px;height:30px;border-radius:15px;background:#e4dcc3}
@@S@@ .tfill{position:absolute;left:100px;top:395px;width:1380px;height:30px;border-radius:15px;background:#178777;transform:scaleX(0);transform-origin:0 50%}
@@S@@ .tm{position:absolute;top:380px;width:60px;height:60px;border-radius:50%;background:#fff;border:10px solid #0f5f57;opacity:0}
@@S@@ .tc{color:#1b2a41;position:absolute;width:300px;height:150px;border-radius:20px;background:#fffdf7;border:4px solid #cdbf9c;box-shadow:12px 14px 0 rgba(205,191,156,.55);display:flex;flex-direction:column;align-items:center;justify-content:center;opacity:0}
@@S@@ .tc b{font-size:32px;color:#d9694a;font-weight:800}@@S@@ .tc span{font-size:40px;font-weight:700;margin-top:8px}
'''
    js = f'''
const NM = {n};
gsap.set(q('#{cid}-fill'), {{ scaleX: 0 }});
for (let i = 0; i < NM; i++) {{
  const at = T('m' + i), up = i % 2 === 0;
  tl.to(q('#{cid}-fill'), {{ scaleX: .04 + (NM > 1 ? i / (NM - 1) * .92 : 0), duration: .7, ease: 'power3.inOut' }}, at - .45);
  tl.fromTo(q('#{cid}-m' + i), {{ opacity: 0, scale: 0 }}, {{ opacity: 1, scale: 1, duration: .45, ease: 'power4.out' }}, at);
  tl.fromTo(q('#{cid}-c' + i), {{ opacity: 0, y: up ? 36 : -36 }}, {{ opacity: 1, y: 0, duration: .75, ease: 'expo.out' }}, at + .05);
  point(q('#{cid}-c' + i), at + .1, .8, .85);
}}
punch(960, 420, T('m' + (NM - 1)), 1.05);
'''
    return scaffold(cid, scene, css, body, js, lead, seconds, ev)


def open_question(cid, scene, lead, seconds, ev):
    title, key = scene["title"], scene.get("caption") or ""
    words = ""
    for w in title.split():
        hot = bool(key) and w.strip("?,.!").lower() in key.lower().split()
        words += f'<span class="qm"><span class="q{" hot" if hot else ""}">{esc(w)}</span></span> '
    body = f'<div class="qc"><div class="qt">{words}</div><svg class="qs" viewBox="0 0 900 60"><path id="{cid}-sq" d="M10 34 C90 6 150 58 240 30 S400 8 480 34 S640 56 700 28 S840 14 890 32" fill="none" stroke="#d9694a" stroke-width="10" stroke-linecap="round"/></svg></div>'
    css = r'''
@@S@@ .qc{color:#1b2a41;position:absolute;left:260px;top:230px;width:1060px;height:400px;border-radius:26px;background:#fffdf7;border:4px solid #cdbf9c;box-shadow:14px 16px 0 rgba(205,191,156,.5);display:flex;align-items:center;justify-content:center}
@@S@@ .qt{width:900px;text-align:center;font-size:84px;font-weight:800;line-height:1.18}
@@S@@ .qm{display:inline-block;overflow:hidden;vertical-align:top;padding-bottom:12px}@@S@@ .qm>span{display:inline-block}
@@S@@ .hot{color:#d9694a}
@@S@@ .qs{position:absolute;left:100px;bottom:70px;width:900px;height:60px}
'''
    js = f'''
tl.fromTo(q('.qc'), {{ opacity: 0, scale: .94 }}, {{ opacity: 1, scale: 1, duration: .8, ease: 'expo.out' }}, .1 + L);
tl.fromTo(qa('.q'), {{ yPercent: 118, opacity: 0 }}, {{ yPercent: 0, opacity: 1, duration: .8, ease: 'expo.out', stagger: .09 }}, T('ask'));
draw(q('#{cid}-sq'), T('key') + .1, .8);
point(q('.hot') || q('.qt'), T('key') + .1, .7, .9);
punch(790, 430, T('key'), 1.05);
'''
    return scaffold(cid, scene, css, body, js, lead, seconds, ev, title=False, simulated=False)


def end_card(cid, scene, lead, seconds, ev):
    body = (f'<div class="ec" id="{cid}-card"><div class="crease" id="{cid}-crease"></div><img id="{cid}-logo" src="assets/brand/logo_doc_mau.png" alt="BAHA Group"/>'
            f'<div class="et">{esc(scene["title"])}</div><div class="shine" id="{cid}-shine"></div></div>'
            f'<div class="bars"><i style="background:#ED1B24"></i><i style="background:#FABC11"></i><i style="background:#0562AF"></i></div>'
            f'<div class="cta" id="{cid}-cta">{esc(scene["cta"])}</div>')
    css = r'''
@@S@@ .ec{color:#1b2a41;position:absolute;left:338px;top:110px;width:900px;height:580px;border-radius:18px;background:#fff;border:3px solid #cdbf9c;box-shadow:14px 16px 0 rgba(205,191,156,.55);overflow:hidden}
@@S@@ .ec img{position:absolute;left:158px;top:36px;width:580px;height:420px}
@@S@@ .et{position:absolute;left:0;right:0;bottom:30px;text-align:center;font-family:"BrandSans","Viet",sans-serif;font-size:36px;color:#163344}
@@S@@ .crease{position:absolute;left:0;right:0;top:50%;border-top:3px dashed #b9ab86;opacity:0}
@@S@@ .shine{position:absolute;top:-20%;left:-30%;width:22%;height:140%;background:linear-gradient(100deg,transparent,rgba(255,255,255,.75),transparent);transform:skewX(-18deg);opacity:0}
@@S@@ .bars{position:absolute;left:518px;top:722px;width:540px;height:8px;display:flex}@@S@@ .bars i{flex:1;transform:scaleX(0);transform-origin:0 50%}
@@S@@ .cta{position:absolute;left:388px;top:748px;width:800px;height:78px;border-radius:39px;background:#0562AF;color:#fff;font-family:"BrandSans","Viet",sans-serif;font-size:42px;display:flex;align-items:center;justify-content:center;opacity:0}
'''
    js = f'''
const f0 = T('fold');
tl.fromTo(q('#{cid}-card'), {{ scale: 1.3, opacity: .0, rotationX: 0, y: 30 }}, {{ scale: 1, opacity: 1, y: 0, duration: 1.0, ease: 'expo.out' }}, f0);
tl.fromTo(q('#{cid}-crease'), {{ opacity: 0 }}, {{ opacity: 1, duration: .25, ease: 'power2.out' }}, f0 + .1);
tl.to(q('#{cid}-crease'), {{ opacity: 0, duration: .4, ease: 'power2.in' }}, f0 + .55);
tl.fromTo(q('#{cid}-logo'), {{ opacity: 0, scale: .9, y: 18 }}, {{ opacity: 1, scale: 1, y: 0, duration: .9, ease: 'expo.out' }}, f0 + .35);
tl.fromTo(q('.et'), {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: .6, ease: 'power3.out' }}, f0 + .8);
tl.fromTo(q('#{cid}-shine'), {{ opacity: .9, x: 0 }}, {{ opacity: .9, x: 1300, duration: .9, ease: 'power2.inOut', immediateRender: false }}, f0 + 1.0);
tl.set(q('#{cid}-shine'), {{ opacity: 0 }}, f0 + 1.95);
tl.fromTo(qa('.bars i'), {{ scaleX: 0 }}, {{ scaleX: 1, duration: .5, ease: 'power3.out', stagger: .1 }}, T('cta') - .2);
tl.fromTo(q('#{cid}-cta'), {{ opacity: 0, y: 26 }}, {{ opacity: 1, y: 0, duration: .6, ease: 'power4.out' }}, T('cta'));
point(q('#{cid}-cta'), T('cta') + .45, .7, .72);
'''
    return scaffold(cid, scene, css, body, js, lead, seconds, ev, title=False, simulated=False, exit_slide=False)


NATIVE = {"FUNNEL": funnel, "CHECKLIST": checklist, "BEFORE_AFTER": before_after, "HUB_SPOKE": hub_spoke, "TIMELINE": timeline, "OPEN_QUESTION": open_question, "END_CARD": end_card}
