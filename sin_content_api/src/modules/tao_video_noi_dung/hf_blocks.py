"""Kho khối dựng sẵn của HyperFrames (registry chính thức, Apache-2.0, HeyGen) nối vào cảnh dựng bằng mã.

Mỗi khối là một sub-composition có biến (`data-composition-variables`) và đọc giá trị qua `window.__hyperframes.getVariables()`.
Ở đây khối được: (1) bỏ phần tải GSAP và font từ CDN (dự án dùng GSAP cục bộ và font Be Vietnam Pro có dấu tiếng Việt),
(2) đổi định danh theo từng lần dùng để nhiều lần dùng trong một video không đè nhau, (3) khoác bảng màu thương hiệu qua biến CSS.

Hai cách dùng:
- Cảnh kể chuyện: `BLOCK_SCENES[layout]` gồm vài biến thể khối; `scene_composition()` chọn một biến thể ổn định theo nội dung
  rồi điền biến từ `diagram`. Cùng layout ở hai video khác nhau cho vẻ ngoài khác nhau mà cùng nội dung vẫn ra cùng kết quả.
- Lớp phủ và chuyển cảnh: `overlay()` cho nền động, hạt phim, rò sáng... đặt chồng lên cảnh.
Danh sách khối đã kiểm bằng ảnh chụp nằm trong blocks/catalog.json (xem tools_catalog)."""
from __future__ import annotations

import html
import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import hf_vendor
from .hf_manifest import (
    BlockManifest,
    load_manifests,
    render_literals,
    render_variables,
)

BLOCKS_DIR = Path(__file__).resolve().parents[3] / "engines" / "hyperframes" / "blocks"
CATALOG_FILE = BLOCKS_DIR / "catalog.json"

# Biến CSS mà các khối đọc (--fg, --bg, --brand, --accent...). Bảng màu khớp "Origami Editorial Motion B2B v1": navy, ngà, ngọc lam, vàng, đỏ san hô.
THEME_STYLE = ("--bg:#0a1c2b;--fg:#f6efe0;--color:#f6efe0;--surface:#12324a;--border:rgba(255,255,255,.16);--brand:#ffd54a;--accent:#5cc8c0;"
               "--accent-2:#e8695a;--muted:#9fb4c4;--font-display:'Viet',sans-serif;--font-body:'Viet',sans-serif;--font-mono:'Viet',monospace")
TRANSPARENT_THEME_STYLE = (
    THEME_STYLE.replace("--bg:#0a1c2b;", "--bg:transparent;").replace("--surface:#12324a;", "--surface:transparent;")
)

_TRANSPARENT_BLOCK_CSS = """
html, body, #root, #aar-root, [class*="-clip"], .tmx-shell, .tmx-shell[data-bg="navy"], .fr-clip, .nty-body, .va-note {
  background: transparent !important;
  box-shadow: none !important;
}
#root {
  overflow: visible !important;
}
#root > :not(style):not(script) {
  transform: translateY(-34cqh) !important;
}
#root > :not(.hf-fx-rig):not(style):not(script) {
  filter: drop-shadow(0 3px 10px rgba(0, 0, 0, 0.92)) drop-shadow(0 8px 20px rgba(0, 0, 0, 0.68));
}
.nty-nav, .nty-check, .nty-fmt,
.cht-sbtime, .cht-sbicons, .cht-back, .cht-badge, .cht-av, .cht-name, .cht-chev, .cht-video, .cht-Input, .cht-plus, .cht-mic {
  display: none !important;
}
.nty-title {
  color: #ffd54a !important;
  text-shadow: 0 0 24px rgba(255, 213, 74, 0.45) !important;
}
.nty-line {
  color: #f6efe0 !important;
}
.nty-body {
  top: 40cqh !important;
}
.va-note {
  color: #ffd54a !important;
  font-weight: 700 !important;
  font-size: min(3.1cqw, 4.8cqh) !important;
  background: rgba(10, 28, 43, 0.24) !important;
  padding: 6px 16px !important;
  border-radius: 999px !important;
  border: 1.5px solid rgba(255, 213, 74, 0.65) !important;
}
.mh-text, .va-text, .kts-sentence, .pwr-stage, .ls-line, .ptd-line, .hs-headline, .cse-headline, .ss-word {
  text-shadow: 0 3px 14px rgba(0, 0, 0, 0.92), 0 0 26px rgba(255, 213, 74, 0.32) !important;
}
.hf-fx-rig {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: visible;
}
.hf-fx-backdrop {
  position: absolute;
  left: 2cqw;
  right: 2cqw;
  top: 34cqh;
  height: 32cqh;
  border-radius: 36px;
  background: radial-gradient(ellipse 85% 75% at 50% 50%, rgba(10, 28, 43, 0.95) 0%, rgba(10, 28, 43, 0.45) 65%, rgba(10, 28, 43, 0.0) 100%);
  opacity: 0;
}
.hf-fx-card {
  position: absolute;
  left: 4cqw;
  right: 4cqw;
  top: 36cqh;
  height: 28cqh;
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(10, 28, 43, 0.96) 0%, rgba(18, 50, 74, 0.88) 50%, rgba(10, 28, 43, 0.96) 100%);
  overflow: hidden;
  opacity: 0;
  transform-origin: 50% 50%;
}
/* 8 KIEU KHUNG VA KHONG KHUNG KHAC BIET HOAN TOAN (STYLE 0 -> 7) */
.hf-fx-rig[data-fx-style="0"] .hf-fx-card {
  border-radius: 50%;
  left: 6cqw;
  right: 6cqw;
  background: radial-gradient(ellipse 80% 70% at 50% 50%, rgba(16, 62, 84, 0.95) 0%, rgba(10, 28, 43, 0.45) 62%, transparent 100%);
}
.hf-fx-rig[data-fx-style="0"] .hf-fx-frame { display: none !important; }

.hf-fx-rig[data-fx-style="1"] .hf-fx-card {
  border-radius: 96px 20px 96px 20px;
  left: 5cqw;
  right: 5cqw;
  background: linear-gradient(102deg, rgba(48, 22, 38, 0.94) 0%, rgba(14, 38, 58, 0.92) 55%, rgba(42, 30, 14, 0.88) 100%);
}
.hf-fx-rig[data-fx-style="1"] .hf-fx-frame { display: none !important; }

.hf-fx-rig[data-fx-style="2"] .hf-fx-card {
  border-radius: 0;
  left: 6.5cqw;
  right: 6.5cqw;
  background: linear-gradient(90deg, rgba(255, 213, 74, 0.35) 0%, rgba(10, 28, 43, 0.88) 15%, rgba(10, 28, 43, 0.88) 85%, rgba(92, 200, 192, 0.35) 100%);
}
.hf-fx-rig[data-fx-style="2"] .hf-fx-frame { display: none !important; }

.hf-fx-rig[data-fx-style="3"] .hf-fx-card {
  border-radius: 999px;
  left: 5cqw;
  right: 5cqw;
  top: 37.5cqh;
  height: 25cqh;
  background: linear-gradient(135deg, rgba(12, 36, 56, 0.96) 0%, rgba(22, 64, 82, 0.90) 100%);
}
.hf-fx-rig[data-fx-style="3"] .hf-fx-frame {
  border-radius: 999px;
  left: 5cqw;
  right: 5cqw;
  top: 37.5cqh;
  height: 25cqh;
  border: 2.5px dashed rgba(92, 200, 192, 0.72);
}

.hf-fx-rig[data-fx-style="4"] .hf-fx-card {
  border-radius: 40px;
  left: 8cqw;
  right: 8cqw;
  background: radial-gradient(circle at 50% 50%, rgba(10, 28, 43, 0.92) 0%, rgba(10, 28, 43, 0.30) 72%, transparent 100%);
}
.hf-fx-rig[data-fx-style="4"] .hf-fx-frame { display: none !important; }

.hf-fx-rig[data-fx-style="5"] .hf-fx-card {
  clip-path: polygon(3% 8%, 98% 0%, 96% 92%, 1% 100%);
  border-radius: 0;
  background: linear-gradient(125deg, rgba(44, 20, 28, 0.94) 0%, rgba(12, 34, 52, 0.92) 60%, rgba(48, 36, 12, 0.92) 100%);
}
.hf-fx-rig[data-fx-style="5"] .hf-fx-frame { display: none !important; }

.hf-fx-rig[data-fx-style="6"] .hf-fx-card {
  border-radius: 60%;
  left: 5cqw;
  right: 5cqw;
  background: radial-gradient(ellipse 85% 65% at 50% 50%, rgba(20, 42, 62, 0.94) 0%, rgba(10, 24, 38, 0.35) 68%, transparent 100%);
}
.hf-fx-rig[data-fx-style="6"] .hf-fx-frame { display: none !important; }

.hf-fx-rig[data-fx-style="7"] .hf-fx-card {
  clip-path: polygon(38px 0, calc(100% - 38px) 0, 100% 38px, 100% calc(100% - 38px), calc(100% - 38px) 100%, 38px 100%, 0 calc(100% - 38px), 0 38px);
  border-radius: 0;
}
.hf-fx-rig[data-fx-style="7"] .hf-fx-frame {
  clip-path: polygon(38px 0, calc(100% - 38px) 0, 100% 38px, 100% calc(100% - 38px), calc(100% - 38px) 100%, 38px 100%, 0 calc(100% - 38px), 0 38px);
  border-radius: 0;
  border: 2px solid rgba(92, 200, 192, 0.62);
}

/* 8 MẪU CÔNG NGHỆ CAO CẤP (HIGH-TECH STYLES 8 -> 15) */
/* Style 8: Cyber HUD Reticle (Kính Ngắm Sci-Fi HUD Tọa Độ Số) */
.hf-fx-rig[data-fx-style="8"] .hf-fx-card {
  clip-path: polygon(24px 0, calc(100% - 24px) 0, 100% 24px, 100% calc(100% - 24px), calc(100% - 24px) 100%, 24px 100%, 0 calc(100% - 24px), 0 24px);
  background: linear-gradient(135deg, rgba(6, 18, 34, 0.95) 0%, rgba(12, 32, 54, 0.88) 50%, rgba(6, 18, 34, 0.95) 100%);
  border-radius: 0;
}
.hf-fx-rig[data-fx-style="8"] .hf-fx-frame {
  clip-path: polygon(24px 0, calc(100% - 24px) 0, 100% 24px, 100% calc(100% - 24px), calc(100% - 24px) 100%, 24px 100%, 0 calc(100% - 24px), 0 24px);
  border-radius: 0;
  border: 1.5px solid rgba(0, 242, 254, 0.65);
  box-shadow: 0 0 24px rgba(0, 242, 254, 0.35), inset 0 0 16px rgba(0, 242, 254, 0.2);
}

/* Style 9: Neon Circuit Board Trace (Bo Mạch Silicon Neon) */
.hf-fx-rig[data-fx-style="9"] .hf-fx-card {
  border-radius: 18px;
  background: radial-gradient(circle at 80% 20%, rgba(16, 48, 64, 0.94) 0%, rgba(6, 20, 28, 0.94) 70%, rgba(3, 12, 18, 0.96) 100%);
}
.hf-fx-rig[data-fx-style="9"] .hf-fx-frame {
  border-radius: 18px;
  border: 1.5px solid rgba(56, 189, 248, 0.55);
  box-shadow: 0 0 20px rgba(56, 189, 248, 0.25);
}

/* Style 10: Hacker Dev Terminal (Cửa Sổ Dòng Lệnh Matrix Unix) */
.hf-fx-rig[data-fx-style="10"] .hf-fx-card {
  border-radius: 14px;
  background: rgba(13, 17, 23, 0.96);
  border-top: 28px solid rgba(22, 27, 34, 0.98);
}
.hf-fx-rig[data-fx-style="10"] .hf-fx-frame {
  border-radius: 14px;
  border: 1.5px solid rgba(48, 54, 61, 0.95);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.85);
}

/* Style 11: Quantum Hexagon Hologram (Lưới Tổ Ong Lượng Tử) */
.hf-fx-rig[data-fx-style="11"] .hf-fx-card {
  clip-path: polygon(50px 0, calc(100% - 50px) 0, 100% 50%, calc(100% - 50px) 100%, 50px 100%, 0 50%);
  border-radius: 0;
  background: radial-gradient(ellipse at 50% 50%, rgba(10, 36, 48, 0.95) 0%, rgba(4, 18, 28, 0.92) 80%, rgba(2, 8, 14, 0.96) 100%);
}
.hf-fx-rig[data-fx-style="11"] .hf-fx-frame {
  clip-path: polygon(50px 0, calc(100% - 50px) 0, 100% 50%, calc(100% - 50px) 100%, 50px 100%, 0 50%);
  border-radius: 0;
  border: 1.5px solid rgba(52, 211, 153, 0.65);
  box-shadow: 0 0 26px rgba(52, 211, 153, 0.35);
}

/* Style 12: Fintech Telemetry Wave (Dao Động Xung Radar Tài Chính) */
.hf-fx-rig[data-fx-style="12"] .hf-fx-card {
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(14, 28, 44, 0.95) 0%, rgba(8, 16, 26, 0.92) 65%, rgba(4, 30, 24, 0.92) 100%);
}
.hf-fx-rig[data-fx-style="12"] .hf-fx-frame {
  border-radius: 20px;
  border: 1.5px solid rgba(255, 213, 74, 0.55);
  box-shadow: 0 0 24px rgba(255, 213, 74, 0.22);
}

/* Style 13: Prism Glassmorphism Laser (Kính Lăng Kính Tán Sắc Đa Tầng) */
.hf-fx-rig[data-fx-style="13"] .hf-fx-card {
  border-radius: 36px;
  background: linear-gradient(135deg, rgba(20, 30, 55, 0.82) 0%, rgba(35, 25, 55, 0.78) 50%, rgba(15, 35, 55, 0.82) 100%);
  backdrop-filter: blur(24px);
}
.hf-fx-rig[data-fx-style="13"] .hf-fx-frame {
  border-radius: 36px;
  border: 2px solid rgba(56, 189, 248, 0.75);
  box-shadow: 0 0 35px rgba(56, 189, 248, 0.35), inset 0 0 16px rgba(244, 63, 94, 0.25);
}

/* Style 14: Neural Synapse AI Network (Mạng Nơ-ron Trí Tuệ Nhân Tạo) */
.hf-fx-rig[data-fx-style="14"] .hf-fx-card {
  border-radius: 48px 12px 48px 12px;
  background: radial-gradient(ellipse 90% 80% at 50% 50%, rgba(22, 18, 48, 0.94) 0%, rgba(8, 14, 32, 0.92) 65%, rgba(4, 8, 20, 0.96) 100%);
}
.hf-fx-rig[data-fx-style="14"] .hf-fx-frame {
  border-radius: 48px 12px 48px 12px;
  border: 1.5px solid rgba(192, 132, 252, 0.65);
  box-shadow: 0 0 28px rgba(192, 132, 252, 0.35);
}

/* Style 15: Cyberpunk 2077 Hazard Chamfer (Vát Góc Công Nghiệp Sắc Bén) */
.hf-fx-rig[data-fx-style="15"] .hf-fx-card {
  clip-path: polygon(60px 0, 100% 0, 100% calc(100% - 60px), calc(100% - 60px) 100%, 0 100%, 0 60px);
  border-radius: 0;
  background: linear-gradient(145deg, rgba(28, 28, 34, 0.96) 0%, rgba(14, 14, 18, 0.94) 50%, rgba(36, 32, 16, 0.96) 100%);
}
.hf-fx-rig[data-fx-style="15"] .hf-fx-frame {
  clip-path: polygon(60px 0, 100% 0, 100% calc(100% - 60px), calc(100% - 60px) 100%, 0 100%, 0 60px);
  border-radius: 0;
  border: 2px solid rgba(255, 213, 74, 0.75);
  box-shadow: 0 0 30px rgba(255, 213, 74, 0.35);
}

.hf-fx-frame {
  position: absolute;
  left: 4cqw;
  right: 4cqw;
  top: 36cqh;
  height: 28cqh;
  border-radius: 28px;
  border: 2px solid rgba(255, 213, 74, 0.52);
  box-shadow: 0 0 28px rgba(92, 200, 192, 0.22), inset 0 0 20px rgba(255, 213, 74, 0.14);
  overflow: hidden;
  opacity: 0;
  transform-origin: 50% 50%;
}
.hf-fx-sweep {
  position: absolute;
  top: -30%;
  left: -45%;
  width: 42%;
  height: 160%;
  background: linear-gradient(105deg, transparent 10%, rgba(255, 213, 74, 0.35) 45%, rgba(255, 255, 255, 0.72) 50%, rgba(92, 200, 192, 0.35) 55%, transparent 90%);
  transform: skewX(-20deg);
  opacity: 0;
}
.hf-fx-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}
.hf-fx-bar-wrap {
  position: absolute;
  left: 18cqw;
  right: 18cqw;
  top: 62cqh;
  height: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.hf-fx-bar {
  width: 100%;
  height: 4px;
  border-radius: 4px;
  background: linear-gradient(90deg, transparent 0%, #5cc8c0 22%, #ffd54a 50%, #e8695a 78%, transparent 100%);
  box-shadow: 0 0 16px rgba(255, 213, 74, 0.8);
  transform-origin: 50% 50%;
}
.hf-fx-dot {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #ffd54a;
  box-shadow: 0 0 18px #ffd54a, 0 0 6px #ffffff;
}
[class*="-clip"], .clip {
  z-index: 2 !important;
}
/* SAN KHAU CHU CHAY THEO GIONG NOI (VOICE-SYNCED TOP OVERLAY STAGE) */
#root:has(.hf-vs-stage) > :not(.hf-fx-rig):not(.hf-vs-stage):not(style):not(script) {
  opacity: 0 !important;
  pointer-events: none !important;
}
.hf-vs-stage {
  position: absolute;
  left: 6.5cqw;
  right: 6.5cqw;
  top: 37cqh;
  height: 25cqh;
  z-index: 5 !important;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  pointer-events: none;
  text-align: center;
}
.hf-vs-tag {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 7px 22px;
  border-radius: 999px;
  font-family: "Be Vietnam Pro", system-ui, sans-serif;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #ffd54a;
  background: rgba(10, 28, 43, 0.26);
  border: 1.5px solid rgba(255, 213, 74, 0.68);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.65);
}
.hf-vs-lines {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
}
.hf-vs-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: center;
  column-gap: 15px;
  row-gap: 6px;
  line-height: 1.22;
}
.hf-vs-word {
  display: inline-block;
  font-family: "Be Vietnam Pro", system-ui, sans-serif;
  font-size: 58px;
  font-weight: 800;
  color: #cbd5e1;
  opacity: 0.34;
  transform-origin: 50% 65%;
  text-shadow: 0 4px 14px rgba(0, 0, 0, 0.95), 0 1px 4px rgba(0, 0, 0, 0.95);
  will-change: transform, opacity, color;
}
.hf-vs-word[data-size="lg"] {
  font-size: 66px;
}
.hf-vs-word[data-size="sm"] {
  font-size: 50px;
}
"""


def _build_style_specific_svg(cid: str, style_idx: int) -> str:
    """Sinh đồ họa vector SVG đặc trưng riêng biệt cho từng kiểu (0..7) — tuyệt đối không lặp lại 1 khung."""
    if style_idx == 0:
        # Style 0: Frameless Aurora Mist + Sóng lượn đôi SVG phát sáng dưới chân chữ
        return (
            f'<g class="hf-fx-corners" id="{cid}-corners" opacity="0">'
            f'<path d="M120,1155 Q330,1120 540,1155 T960,1155" fill="none" stroke="#ffd54a" stroke-width="5.5" stroke-linecap="round"/>'
            f'<path d="M180,1178 Q360,1205 540,1178 T900,1178" fill="none" stroke="#5cc8c0" stroke-width="3.5" stroke-dasharray="14 10" stroke-linecap="round"/>'
            f'</g>'
        )
    if style_idx == 1:
        # Style 1: Brush Stroke Ink Ribbon + Vệt cọ nghệ thuật & giọt mực vector
        return (
            f'<g class="hf-fx-corners" id="{cid}-corners" opacity="0">'
            f'<path d="M95,750 C310,728 770,768 985,742" fill="none" stroke="#e8695a" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M115,1165 C350,1188 730,1142 965,1170" fill="none" stroke="#ffd54a" stroke-width="8" stroke-linecap="round"/>'
            f'<circle cx="82" cy="752" r="7" fill="#e8695a"/><circle cx="1002" cy="740" r="5" fill="#ffd54a"/>'
            f'<circle cx="96" cy="1168" r="6" fill="#ffd54a"/><circle cx="984" cy="1172" r="8" fill="#5cc8c0"/>'
            f'</g>'
        )
    if style_idx == 2:
        # Style 2: Split Vertical Laser Pillars (2 trụ laser dọc hai bên |   |, mở hoàn toàn trên/dưới)
        return (
            f'<g class="hf-fx-corners" id="{cid}-corners" opacity="0">'
            f'<line x1="72" y1="720" x2="72" y2="1200" stroke="#ffd54a" stroke-width="7" stroke-linecap="round"/>'
            f'<line x1="90" y1="765" x2="90" y2="1155" stroke="#5cc8c0" stroke-width="3" stroke-dasharray="10 12" stroke-linecap="round"/>'
            f'<line x1="1008" y1="720" x2="1008" y2="1200" stroke="#5cc8c0" stroke-width="7" stroke-linecap="round"/>'
            f'<line x1="990" y1="765" x2="990" y2="1155" stroke="#ffd54a" stroke-width="3" stroke-dasharray="10 12" stroke-linecap="round"/>'
            f'<polygon points="72,698 84,714 72,730 60,714" fill="#ffd54a"/>'
            f'<polygon points="1008,698 1020,714 1008,730 996,714" fill="#5cc8c0"/>'
            f'<polygon points="72,1190 84,1206 72,1222 60,1206" fill="#5cc8c0"/>'
            f'<polygon points="1008,1190 1020,1206 1008,1222 996,1206" fill="#ffd54a"/>'
            f'</g>'
        )
    if style_idx == 3:
        # Style 3: Stadium Pill Halo & Vòng quỹ đạo elip nghiêng
        return (
            f'<g class="hf-fx-corners" id="{cid}-corners" opacity="0">'
            f'<ellipse cx="540" cy="960" rx="486" ry="225" transform="rotate(-3.5 540 960)" fill="none" stroke="#ffd54a" stroke-width="3.5" stroke-dasharray="28 16"/>'
            f'<ellipse cx="540" cy="960" rx="468" ry="202" transform="rotate(2.5 540 960)" fill="none" stroke="#5cc8c0" stroke-width="2.5" stroke-dasharray="12 20"/>'
            f'</g>'
        )
    if style_idx == 4:
        # Style 4: Frameless Viewfinder Reticle Crosshairs (+) & Thước đo vạch chia độ
        ticks = "".join(
            f'<line x1="{180 + i * 36}" y1="1172" x2="{180 + i * 36}" y2="{1194 if i % 5 == 0 else 1184}" '
            f'stroke="{"#ffd54a" if i % 5 == 0 else "#5cc8c0"}" stroke-width="{"3.5" if i % 5 == 0 else "2"}"/>'
            for i in range(21)
        )
        return (
            f'<g class="hf-fx-corners" id="{cid}-corners" opacity="0">'
            f'<path d="M88,735 H138 M113,710 V760" stroke="#ffd54a" stroke-width="4.5" stroke-linecap="round"/>'
            f'<circle cx="113" cy="735" r="14" fill="none" stroke="#ffd54a" stroke-width="2.5"/>'
            f'<path d="M942,735 H992 M967,710 V760" stroke="#5cc8c0" stroke-width="4.5" stroke-linecap="round"/>'
            f'<circle cx="967" cy="735" r="14" fill="none" stroke="#5cc8c0" stroke-width="2.5"/>'
            f'<path d="M88,1175 H138 M113,1150 V1200" stroke="#5cc8c0" stroke-width="4.5" stroke-linecap="round"/>'
            f'<path d="M942,1175 H992 M967,1150 V1200" stroke="#ffd54a" stroke-width="4.5" stroke-linecap="round"/>'
            f'{ticks}'
            f'</g>'
        )
    if style_idx == 5:
        # Style 5: Pop-Art Radial Starburst Impact (Tia chớp & đa giác năng lượng không viền hộp)
        return (
            f'<g class="hf-fx-corners" id="{cid}-corners" opacity="0">'
            f'<polygon points="95,720 135,705 118,742 152,735 102,778 112,745 82,752" fill="#ffd54a"/>'
            f'<polygon points="985,720 945,705 962,742 928,735 978,778 968,745 998,752" fill="#e8695a"/>'
            f'<path d="M130,1172 L320,1152 L540,1178 L760,1150 L950,1170" fill="none" stroke="#ffd54a" stroke-width="5" stroke-linejoin="round"/>'
            f'</g>'
        )
    if style_idx == 6:
        # Style 6: Editorial Quote Watermark & Gạch chân đôi vẽ tay (Frameless)
        return (
            f'<g class="hf-fx-corners" id="{cid}-corners" opacity="0">'
            f'<path d="M110,795 C110,745 145,715 185,715 L185,742 C158,742 142,760 142,782 L175,782 L175,832 L110,832 Z" fill="#ffd54a" opacity="0.42"/>'
            f'<path d="M195,795 C195,745 230,715 270,715 L270,742 C243,742 227,760 227,782 L260,782 L260,832 L195,832 Z" fill="#ffd54a" opacity="0.42"/>'
            f'<path d="M140,1158 C380,1135 690,1178 940,1150" fill="none" stroke="#ffd54a" stroke-width="6.5" stroke-linecap="round"/>'
            f'<path d="M210,1180 C430,1165 650,1192 870,1172" fill="none" stroke="#e8695a" stroke-width="4" stroke-linecap="round"/>'
            f'</g>'
        )
    # Style 7: Cyber Chamfer Hex-Cut & Cột sóng âm Equalizer hai bên
    eq_bars = []
    for i, h in enumerate((48, 86, 124, 72, 104)):
        y_top = 960 - h // 2
        eq_bars.append(f'<rect x="{58 + i * 12}" y="{y_top}" width="6" height="{h}" rx="3" fill="{"#ffd54a" if i % 2 == 0 else "#5cc8c0"}"/>')
        eq_bars.append(f'<rect x="{1016 - i * 12}" y="{y_top}" width="6" height="{h}" rx="3" fill="{"#5cc8c0" if i % 2 == 0 else "#ffd54a"}"/>')
    return (
        f'<g class="hf-fx-corners" id="{cid}-corners" opacity="0">'
        f'<path d="M52,750 L92,710 L175,710" fill="none" stroke="#ffd54a" stroke-width="6" stroke-linecap="round"/>'
        f'<path d="M1028,750 L988,710 L905,710" fill="none" stroke="#5cc8c0" stroke-width="6" stroke-linecap="round"/>'
        f'<path d="M52,1170 L92,1210 L175,1210" fill="none" stroke="#5cc8c0" stroke-width="6" stroke-linecap="round"/>'
        f'<path d="M1028,1170 L988,1210 L905,1210" fill="none" stroke="#ffd54a" stroke-width="6" stroke-linecap="round"/>'
        f'{"".join(eq_bars)}'
        f'</g>'
    )


_VS_COLOR_PALETTE: dict[str, tuple[str, str]] = {
    "GOLD": ("#ffd54a", "0 0 26px rgba(255,213,74,0.85), 0 4px 14px rgba(0,0,0,0.95)"),
    "CORAL": ("#ff5a5f", "0 0 26px rgba(255,90,95,0.85), 0 4px 14px rgba(0,0,0,0.95)"),
    "EMERALD": ("#34d399", "0 0 26px rgba(52,211,153,0.85), 0 4px 14px rgba(0,0,0,0.95)"),
    "CYAN": ("#38bdf8", "0 0 26px rgba(56,189,248,0.85), 0 4px 14px rgba(0,0,0,0.95)"),
    "WHITE": ("#ffffff", "0 0 22px rgba(255,213,74,0.65), 0 4px 14px rgba(0,0,0,0.95)"),
}


def _build_voice_synced_stage(cid: str, word_times: list[dict], tag_text: str = "", style_idx: int = 0) -> tuple[str, str]:
    """Sinh sân khấu chữ chạy khớp từng âm tiết phát âm thật (Voice-Synced Word-by-Word Kinetic Stage)."""
    if not word_times:
        return "", ""

    n_words = len(word_times)
    size_attr = "lg" if n_words <= 6 else ("sm" if n_words >= 12 else "md")
    # Chia thành 1..3 dòng cân đối
    if n_words <= 4:
        line_groups = [list(enumerate(word_times))]
    elif n_words <= 9:
        mid = (n_words + 1) // 2
        line_groups = [list(enumerate(word_times[:mid])), list(enumerate(word_times[mid:], start=mid))]
    else:
        c1 = (n_words + 2) // 3
        c2 = (2 * n_words + 2) // 3
        line_groups = [
            list(enumerate(word_times[:c1])),
            list(enumerate(word_times[c1:c2], start=c1)),
            list(enumerate(word_times[c2:], start=c2)),
        ]

    lines_html = []
    for grp in line_groups:
        spans = []
        for idx, w in grp:
            w_txt = html.escape(str(w.get("text") or "").strip())
            if not w_txt:
                continue
            spans.append(
                f'<span class="hf-vs-word" id="{cid}-vsw-{idx}" data-size="{size_attr}">{w_txt}</span>'
            )
        if spans:
            lines_html.append(f'<div class="hf-vs-line">{"".join(spans)}</div>')

    tag_html = ""
    if tag_text:
        svg_badge = (
            '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffd54a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
            '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>'
        )
        tag_html = f'<div class="hf-vs-tag" id="{cid}-vs-tag">{svg_badge}<span>{html.escape(tag_text.upper())}</span></div>'

    stage_html = (
        f'<div class="hf-vs-stage" id="{cid}-vs-stage" data-style="{style_idx}">'
        f'{tag_html}'
        f'<div class="hf-vs-lines">{"".join(lines_html)}</div>'
        f'</div>'
    )

    js_lines = [
        f'    var vsStage = root.querySelector("#{cid}-vs-stage");',
        f'    var vsTag = root.querySelector("#{cid}-vs-tag");',
        '    if (vsTag) {',
        '      gsap.set(vsTag, { opacity: 0, y: -14, scale: 0.88 });',
        '      tl.fromTo(vsTag, { opacity: 0, y: -14, scale: 0.88 }, { opacity: 1, y: 0, scale: 1, duration: 0.32, ease: "back.out(1.8)" }, 0.04);',
        '      tl.to(vsTag, { opacity: 0, y: -10, duration: 0.24 }, tOut);',
        '    }',
    ]

    palette_Cycle = ("GOLD", "CYAN", "EMERALD", "CORAL")
    for idx, w in enumerate(word_times):
        s_s = max(0.0, float(w.get("start_ms", 0)) / 1000.0)
        e_s = max(s_s + 0.12, float(w.get("end_ms", int(s_s * 1000) + 260)) / 1000.0)
        w_dur = max(0.10, e_s - s_s)
        pop_in = min(0.11, w_dur * 0.45)
        col_key = str(w.get("color") or "").upper()
        is_kw = bool(w.get("highlight") or col_key in _VS_COLOR_PALETTE)
        if col_key not in _VS_COLOR_PALETTE:
            col_key = palette_Cycle[(idx + style_idx) % len(palette_Cycle)] if is_kw else "GOLD"
        active_hex, active_glow = _VS_COLOR_PALETTE[col_key]
        settled_hex = active_hex if is_kw else "#f8fafc"
        settled_scale = 1.04 if is_kw else 1.0

        js_lines.append(f'    var w{idx} = root.querySelector("#{cid}-vsw-{idx}");')
        js_lines.append(f'    if (w{idx}) {{')
        js_lines.append(f'      gsap.set(w{idx}, {{ opacity: 0.34, scale: 0.92, y: 6, color: "#cbd5e1" }});')
        js_lines.append(
            f'      tl.to(w{idx}, {{ opacity: 1, scale: 1.16, y: -5, color: "{active_hex}", '
            f'textShadow: "{active_glow}", duration: {pop_in:.3f}, ease: "back.out(2.4)" }}, {s_s:.3f});'
        )
        js_lines.append(
            f'      tl.to(w{idx}, {{ opacity: 0.98, scale: {settled_scale:.2f}, y: 0, color: "{settled_hex}", '
            f'textShadow: "0 4px 14px rgba(0,0,0,0.95)", duration: 0.12, ease: "sine.out" }}, {e_s:.3f});'
        )
        js_lines.append(f'      tl.to(w{idx}, {{ opacity: 0, scale: 0.90, y: -8, duration: 0.24 }}, tOut);')
        js_lines.append('    }')

    return stage_html, "\n".join(js_lines)


def _build_overlay_fx_rig(
    cid: str,
    duration: float,
    seed_key: str = "",
    fx_style: int | None = None,
    word_times: list[dict] | None = None,
    tag_text: str = "",
) -> tuple[str, str]:
    """Sinh lớp HTML/SVG hiệu ứng động đa phong cách (8 kiểu 0..7) + sân khấu chữ khớp giọng nói.
    Độ mờ nền (alpha) dao động ngẫu nhiên ổn định trong khoảng 0.0 -> 0.30 theo từng cảnh."""
    seed = zlib.crc32((seed_key or cid).encode("utf-8"))
    style_idx = int(fx_style) % 8 if fx_style is not None else ((seed >> 3) % 8)

    # Chọn các mốc alpha ngẫu nhiên trong khoảng 0.0 -> 0.30
    alpha_p1 = round(0.12 + ((seed & 0xFF) / 255.0) * 0.16, 3)          # 0.12 -> 0.28
    alpha_mid = round(0.03 + (((seed >> 8) & 0xFF) / 255.0) * 0.10, 3)   # 0.03 -> 0.13
    alpha_p2 = round(0.15 + (((seed >> 16) & 0xFF) / 255.0) * 0.15, 3)   # 0.15 -> 0.30

    # 12 tia nhấn (Impact Burst Rays) ở hai bên trái/phải vùng chữ
    rays_svg = []
    ray_coords = [
        (110, 960, 42, 910, "#ffd54a"), (95, 995, 28, 995, "#5cc8c0"), (110, 1030, 45, 1080, "#e8695a"),
        (150, 880, 95, 825, "#ffd54a"), (150, 1090, 95, 1145, "#5cc8c0"), (190, 845, 155, 785, "#f6efe0"),
        (970, 960, 1038, 910, "#ffd54a"), (985, 995, 1052, 995, "#5cc8c0"), (970, 1030, 1035, 1080, "#e8695a"),
        (930, 880, 985, 825, "#ffd54a"), (930, 1090, 985, 1145, "#5cc8c0"), (890, 845, 925, 785, "#f6efe0"),
    ]
    for idx, (x1, y1, x2, y2, col) in enumerate(ray_coords):
        rays_svg.append(
            f'<line class="hf-fx-ray" id="{cid}-ray-{idx}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{col}" stroke-width="5.5" stroke-linecap="round" stroke-dasharray="120" stroke-dashoffset="120" opacity="0"/>'
        )

    # 6 ngôi sao 4 cánh lấp lánh (Sparkle Stars SVG)
    stars_svg = []
    star_coords = [
        (135, 760, 1.15, "#ffd54a"), (945, 770, 1.1, "#5cc8c0"),
        (85, 1120, 0.95, "#ffd54a"), (995, 1110, 1.05, "#e8695a"),
        (260, 725, 0.85, "#f6efe0"), (820, 1175, 0.9, "#ffd54a"),
    ]
    for idx, (cx, cy, sc, col) in enumerate(star_coords):
        stars_svg.append(
            f'<g class="hf-fx-star" id="{cid}-star-{idx}" transform="translate({cx},{cy}) scale(0)">'
            f'<path d="M0,-22 C3,-6 6,-3 22,0 C6,3 3,6 0,22 C-3,6 -6,3 -22,0 C-6,-3 -3,-6 0,-22 Z" fill="{col}"/>'
            f'</g>'
        )

    # Đồ họa vector riêng biệt theo từng style (0..7)
    corners_svg = _build_style_specific_svg(cid, style_idx)

    # 12 hạt năng lượng bay lơ lửng (Floating Bokeh Particles)
    particles_svg = []
    p_colors = ("#ffd54a", "#5cc8c0", "#e8695a", "#f6efe0")
    for idx in range(12):
        px = 90 + ((seed >> (idx * 2)) * 73 + idx * 81) % 900
        py = 730 + ((seed >> (idx + 3)) * 59 + idx * 47) % 460
        pr = 4 + (idx % 4) * 2.2
        pcol = p_colors[idx % len(pcol)] if (pcol := p_colors) else "#ffd54a"
        particles_svg.append(
            f'<circle class="hf-fx-orb" id="{cid}-orb-{idx}" cx="{px}" cy="{py}" r="{pr:.1f}" fill="{pcol}" opacity="0"/>'
        )

    vs_html, vs_js = _build_voice_synced_stage(cid, word_times or [], tag_text=tag_text, style_idx=style_idx)

    fx_html = (
        f'<div class="hf-fx-rig" id="{cid}-fx-rig" data-fx-style="{style_idx}">'
        f'<div class="hf-fx-backdrop" id="{cid}-fx-bg"></div>'
        f'<div class="hf-fx-card" id="{cid}-fx-card"></div>'
        f'<div class="hf-fx-frame" id="{cid}-fx-frame"><div class="hf-fx-sweep" id="{cid}-fx-sweep"></div></div>'
        f'<div class="hf-fx-bar-wrap"><div class="hf-fx-bar" id="{cid}-fx-bar"></div><div class="hf-fx-dot" id="{cid}-fx-dot"></div></div>'
        f'<svg class="hf-fx-svg" viewBox="0 0 1080 1920" preserveAspectRatio="none">'
        f'{corners_svg}{"".join(rays_svg)}{"".join(stars_svg)}{"".join(particles_svg)}'
        f'</svg>'
        f'</div>'
        f'{vs_html}'
    )

    dur = max(1.8, float(duration or 3.5))
    t_in = min(0.35, dur * 0.14)
    t_mid = dur * 0.48
    t_p2 = dur * 0.76
    t_out = max(t_p2 + 0.15, dur - 0.26)

    fx_js = f"""
;(function() {{
  function attachFx() {{
    var tl = window.__timelines && window.__timelines["{cid}"];
    var root = document.getElementById("root");
    if (!tl || !root) return;
    var tOut = {t_out:.3f};
    var bg = root.querySelector("#{cid}-fx-bg");
    var card = root.querySelector("#{cid}-fx-card");
    var frame = root.querySelector("#{cid}-fx-frame");
    var sweep = root.querySelector("#{cid}-fx-sweep");
    var bar = root.querySelector("#{cid}-fx-bar");
    var dot = root.querySelector("#{cid}-fx-dot");
    var corners = root.querySelector("#{cid}-corners");
    var rays = root.querySelectorAll(".hf-fx-ray");
    var stars = root.querySelectorAll(".hf-fx-star");
    var orbs = root.querySelectorAll(".hf-fx-orb");

    // 1. Alpha nền kính dao động ngẫu nhiên từ 0.0 -> {alpha_p1} -> {alpha_mid} -> {alpha_p2} -> 0.0 (trong ngưỡng thấp 0 -> 0.3)
    gsap.set([bg, card], {{ opacity: 0 }});
    gsap.set(card, {{ scale: 0.92 }});
    tl.fromTo(bg, {{ opacity: 0 }}, {{ opacity: {round(alpha_p1 * 0.25, 3)}, duration: {t_in:.3f}, ease: "sine.out" }}, 0);
    tl.to(bg, {{ opacity: {round(alpha_mid * 0.25, 3)}, duration: {max(0.2, t_mid - t_in):.3f}, ease: "sine.inOut" }}, {t_in:.3f});
    tl.to(bg, {{ opacity: {round(alpha_p2 * 0.25, 3)}, duration: {max(0.2, t_p2 - t_mid):.3f}, ease: "sine.inOut" }}, {t_mid:.3f});
    tl.to(bg, {{ opacity: 0, duration: {max(0.18, dur - t_out):.3f}, ease: "power2.in" }}, tOut);

    tl.fromTo(card, {{ opacity: 0, scale: 0.92 }}, {{ opacity: {alpha_p1}, scale: 1, duration: 0.42, ease: "back.out(1.5)" }}, 0.04);
    tl.to(card, {{ opacity: {alpha_mid}, scale: 0.985, duration: {max(0.2, t_mid - 0.46):.3f}, ease: "sine.inOut" }}, 0.46);
    tl.to(card, {{ opacity: {alpha_p2}, scale: 1.01, duration: {max(0.2, t_p2 - t_mid):.3f}, ease: "sine.inOut" }}, {t_mid:.3f});
    tl.to(card, {{ opacity: 0, scale: 0.96, duration: 0.24, ease: "power2.in" }}, tOut);

    if (frame) {{
      gsap.set(frame, {{ opacity: 0, scale: 0.92 }});
      tl.fromTo(frame, {{ opacity: 0, scale: 0.92 }}, {{ opacity: 0.88, scale: 1, duration: 0.42, ease: "back.out(1.5)" }}, 0.04);
      tl.to(frame, {{ opacity: 0, scale: 0.96, duration: 0.24, ease: "power2.in" }}, tOut);
    }}

    // 2. Đồ họa vector theo style (0..7) + Thanh năng lượng + Hạt quét Scanner
    if (corners) {{
      gsap.set(corners, {{ opacity: 0, scale: 0.88, svgOrigin: "540 970" }});
      tl.fromTo(corners, {{ opacity: 0, scale: 0.88 }}, {{ opacity: 0.94, scale: 1, duration: 0.46, ease: "expo.out" }}, 0.06);
      tl.to(corners, {{ opacity: 0, scale: 1.04, duration: 0.24 }}, tOut);
    }}
    if (bar && dot) {{
      gsap.set(bar, {{ scaleX: 0, opacity: 0 }});
      gsap.set(dot, {{ x: -260, opacity: 0, scale: 0 }});
      tl.fromTo(bar, {{ scaleX: 0, opacity: 0 }}, {{ scaleX: 1, opacity: 0.95, duration: 0.50, ease: "expo.out" }}, 0.10);
      tl.fromTo(dot, {{ x: -260, opacity: 0, scale: 0.4 }}, {{ x: 260, opacity: 1, scale: 1.15, duration: {max(0.8, dur - 0.35):.3f}, ease: "none" }}, 0.10);
      tl.to([bar, dot], {{ opacity: 0, duration: 0.22 }}, tOut);
    }}

    // 3. Dải quét ánh kim (Shimmer Sweep)
    if (sweep) {{
      gsap.set(sweep, {{ xPercent: -140, opacity: 0 }});
      tl.fromTo(sweep, {{ xPercent: -140, opacity: 0.95 }}, {{ xPercent: 340, opacity: 0.95, duration: 1.05, ease: "power2.inOut" }}, 0.28);
    }}

    // 4. Tia nổ tâm điểm (Impact Burst Rays)
    rays.forEach(function(ray, i) {{
      var at = 0.12 + (i % 6) * 0.045;
      gsap.set(ray, {{ strokeDashoffset: 120, opacity: 0 }});
      tl.fromTo(ray, {{ strokeDashoffset: 120, opacity: 1 }}, {{ strokeDashoffset: 0, opacity: 1, duration: 0.36, ease: "power3.out" }}, at);
      tl.to(ray, {{ strokeDashoffset: -120, opacity: 0, duration: 0.32, ease: "power2.in" }}, at + 0.34);
    }});

    // 5. Sao 4 cánh lấp lánh (Sparkle Stars)
    stars.forEach(function(st, i) {{
      var at = 0.16 + i * 0.10;
      gsap.set(st, {{ scale: 0, rotation: -45, opacity: 0, transformOrigin: "0px 0px" }});
      tl.fromTo(st, {{ scale: 0, rotation: -45, opacity: 0 }}, {{ scale: 1.25, rotation: 15, opacity: 0.95, duration: 0.38, ease: "back.out(2.2)" }}, at);
      tl.to(st, {{ scale: 0.75, rotation: 45, opacity: 0.55, duration: 0.45, yoyo: true, repeat: 1, ease: "sine.inOut" }}, at + 0.38);
      tl.to(st, {{ scale: 0, opacity: 0, duration: 0.22 }}, tOut);
    }});

    // 6. Hạt năng lượng Bokeh bay lơ lửng
    orbs.forEach(function(orb, i) {{
      var at = 0.06 + (i % 5) * 0.07;
      var dy = -55 - (i % 4) * 22;
      var dx = (i % 2 === 0 ? 1 : -1) * (18 + (i % 3) * 12);
      gsap.set(orb, {{ opacity: 0, x: 0, y: 20, scale: 0.4 }});
      tl.fromTo(orb, {{ opacity: 0, x: 0, y: 20, scale: 0.4 }}, {{ opacity: 0.78, x: dx, y: dy, scale: 1.15, duration: {max(0.9, dur * 0.72):.3f}, ease: "sine.out" }}, at);
      tl.to(orb, {{ opacity: 0, scale: 0.2, duration: 0.24 }}, tOut);
    }});

    // 7. Chữ chạy khớp từng âm tiết phát âm thật (Voice-Synced Words)
{vs_js}

    tl.seek(0);
  }}
  attachFx();
  if (document.fonts && document.fonts.ready) {{
    document.fonts.ready.then(attachFx);
  }}
}})();
"""
    return fx_html, fx_js


# Chữ mẫu tiếng Anh có sẵn trong mã khối -> tiếng Việt (khối không có biến cho các chữ này).
_VIETNAMESE_TEXT: dict[str, dict[str, str]] = {
    "overwhelm-surround": {
        "Inbox": "Hộp thư", "Due": "Hạn chót", "@you": "@bạn", "ASAP": "GẤP", "Review": "Duyệt", "Call": "Gọi lại", "3 pings": "3 tin", "Sync": "Đồng bộ",
        "Today": "Hôm nay", "Reply": "Trả lời", "8 tabs": "8 tab", "Update": "Cập nhật", "Now": "Ngay", "Draft": "Soạn", "4 alerts": "4 cảnh báo",
        "Fix": "Sửa", "Follow up": "Theo dõi", "Queue": "Hàng chờ", "2 min": "2 phút", "Waiting": "Đang chờ",
    },
    "notification-pileup": {
        "Messages": "Tin nhắn", "Can you take a quick look?": "Anh xem giúp em một chút?", "Calendar": "Lịch", "Stand-up moved to 10:30": "Họp giao ban dời sang 10:30",
        "Mail": "Thư", "Five new replies in your thread": "Năm phản hồi mới trong chuỗi", "Updates": "Cập nhật", "A new version is ready": "Có bản mới cần duyệt",
        "Tasks": "Công việc", "Deadline changed to today": "Hạn nộp đổi sang hôm nay", "Drive": "Kho tệp", "Someone requested access": "Có người xin quyền truy cập",
        "Security": "Bảo mật", "New sign-in needs review": "Đăng nhập mới cần duyệt", "Social": "Mạng xã hội", "You have twelve new mentions": "Mười hai lượt nhắc mới",
        "Notes": "Ghi chú", "Shared checklist was updated": "Danh sách chung vừa đổi", "Reminders": "Nhắc việc", "Follow up before end of day": "Theo dõi trước cuối ngày",
    },
}


def block_path(name: str) -> Path:
    path = BLOCKS_DIR / f"{name}.html"
    if not path.is_file():
        raise FileNotFoundError(f"HYPERFRAMES_BLOCK_MISSING:{name}")
    return path


def prepare_block(
    name: str,
    cid: str,
    duration: float | None = None,
    literals: dict[str, str] | None = None,
    transparent_background: bool = False,
    seed_key: str = "",
    fx_style: int | None = None,
    word_times: list[dict] | None = None,
    tag_text: str = "",
) -> str:
    """Mã khối cho MỘT lần dùng: bỏ CDN, đổi định danh `name` thành `cid`. Khối đọc độ dài D từ `data-duration` của chính nó
    (không lấy từ thẻ host) nên phải ghi D thật vào đó, nếu không khối thoát cảnh theo độ dài mặc định."""
    text = block_path(name).read_text(encoding="utf-8")
    text, _ = hf_vendor.localize(text)
    remaining_urls = hf_vendor.scan_external(text)
    if remaining_urls:
        raise ValueError(f"HYPERFRAMES_BLOCK_EXTERNAL_URL:{name}:{remaining_urls[0]}")
    if duration is not None:
        text = re.sub(r'(data-(?:composition-)?duration=")[\d.]+(")', lambda m: f"{m.group(1)}{duration:.3f}{m.group(2)}", text)
        # Khi chạy, runtime không để lại data-duration trên #root nên khối rơi về giá trị mặc định trong mã: `dataset.duration || "3.5"`.
        text = re.sub(r'(dataset\.duration\s*\|\|\s*")[\d.]+(")', lambda m: f"{m.group(1)}{duration:.3f}{m.group(2)}", text)
    for english, vietnamese in _VIETNAMESE_TEXT.get(name, {}).items():
        text = text.replace(f'"{english}"', f'"{vietnamese}"')
    for old, new in (literals or {}).items():   # chữ cố định trong mã khối mà khối không có biến: thay bằng nội dung của cảnh
        if old not in text:
            raise ValueError(f"HYPERFRAMES_BLOCK_LITERAL_MISSING:{name}:{old[:30]}")
        text = text.replace(old, new)   # new do hàm dựng literals tự escape phần nội dung
    if transparent_background and "</style>" in text:
        text = text.replace("</style>", _TRANSPARENT_BLOCK_CSS + "\n</style>", 1)
    text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9_])", cid, text)
    if transparent_background:
        fx_html, fx_js = _build_overlay_fx_rig(
            cid,
            duration or 3.5,
            seed_key=seed_key or f"{cid}:{name}",
            fx_style=fx_style,
            word_times=word_times,
            tag_text=tag_text,
        )
        if "</style>" in text:
            text = text.replace("</style>", "</style>\n" + fx_html, 1)
        if "</script>" in text:
            last_script_idx = text.rfind("</script>")
            text = text[:last_script_idx] + "\n" + fx_js + "\n" + text[last_script_idx:]
    return text


def vendor_files_for(name: str) -> tuple[str, ...]:
    """Các tệp vendor cục bộ mà khối cần (từ báo cáo localize trên tệp gốc)."""
    text = block_path(name).read_text(encoding="utf-8")
    _, report = hf_vendor.localize(text)
    return report.files


def host_attrs(variables: dict | None = None) -> str:
    """Thuộc tính thêm cho thẻ host: giá trị biến của khối (JSON trong dấu nháy đơn)."""
    if not variables:
        return ""
    return " data-variable-values='" + json.dumps(variables, ensure_ascii=False).replace("&", "&amp;").replace("'", "&#39;") + "'"


def load_catalog() -> dict:
    try:
        return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"blocks": {}}


@dataclass(frozen=True)
class Variant:
    block: str
    variables: Callable[[dict], dict]
    max_chars: int = 999   # khối cỡ chữ cố định chỉ hợp tiêu đề ngắn
    literals: Callable[[dict], dict] | None = None   # chữ cố định trong mã khối cần thay theo nội dung cảnh
    manifest: BlockManifest | None = None


# Đọc toàn bộ manifest từ blocks/manifest/*.json
_LOADED_MANIFESTS = load_manifests()


def _build_block_scenes() -> dict[str, list[Variant]]:
    scenes: dict[str, list[Variant]] = {}
    for layout, m_list in _LOADED_MANIFESTS.items():
        variants: list[Variant] = []
        for m in m_list:
            v_vars = (lambda mf: lambda d: render_variables(mf, d))(m)
            v_lits = (lambda mf: (lambda d: render_literals(mf, d)) if mf.literals else None)(m)
            variants.append(Variant(
                block=m.block,
                variables=v_vars,
                max_chars=m.max_chars,
                literals=v_lits,
                manifest=m,
            ))
        scenes[layout] = variants
    return scenes


BLOCK_SCENES: dict[str, list[Variant]] = _build_block_scenes()

# Hệ số phóng cảnh khối ở khung 9:16 (dựng từ manifest)
PORTRAIT_SCALE: dict[str, float] = {
    layout: m_list[0].portrait_scale.get("base", 1.0)
    for layout, m_list in _LOADED_MANIFESTS.items()
    if m_list and m_list[0].portrait_scale.get("base", 1.0) != 1.0
}
SQUARE_BLOCKS: tuple[str, ...] = tuple(
    layout for layout, m_list in _LOADED_MANIFESTS.items()
    if any(m.square for m in m_list)
)


def portrait_scale(layout: str, data: dict) -> float:
    """Hệ số phóng ở khung 9:16. Khối chữ một dòng đã tự co theo chiều rộng nên câu dài phóng thêm sẽ tràn mép: câu càng dài phóng càng ít."""
    manifests = _LOADED_MANIFESTS.get(layout, [])
    rules = manifests[0].portrait_scale if manifests else {}
    base = PORTRAIT_SCALE.get(layout, 1.0)
    if layout in ("MARK_PHRASE", "WORD_SWAP"):
        size = len(str(data.get("title") or "")) + (
            (sum(len(s) for s in data.get("steps") or []) // max(1, len(data.get("steps") or [1]))
             + len(str(data.get("caption") or "")))
            if layout == "WORD_SWAP" else 0
        )
        if size <= 22:
            return rules.get("lte_22", base)
        elif size <= 30:
            return rules.get("lte_30", 1.15)
        else:
            return rules.get("default", 1.0)
    return base


def pick_variant(layout: str, data: dict) -> Variant:
    title_len = len(str(data.get("title") or ""))
    variants = [v for v in BLOCK_SCENES[layout] if title_len <= v.max_chars] or BLOCK_SCENES[layout][-1:]
    if layout == "KINETIC_TITLE":
        dynamic = [v for v in variants if v.block not in {"titlecard-calm", "kinetic-center-build"}]
        if dynamic:
            variants = dynamic
    key = json.dumps([layout, data.get("title"), data.get("tag")], ensure_ascii=False, sort_keys=True)
    return variants[zlib.crc32(key.encode("utf-8")) % len(variants)]


def scene_composition(
    layout: str,
    cid: str,
    data: dict,
    duration: float | None = None,
    transparent_background: bool = False,
) -> tuple[str, str, str]:
    """(mã composition, thuộc tính host, style host) cho một cảnh khối; style host mang bảng màu thương hiệu."""
    if layout == "MARK_PHRASE" and not data.get("caption") and data.get("tag"):
        data = {**data, "caption": str(data["tag"]).upper()}
    variant = pick_variant(layout, data)
    transparent = bool(transparent_background or data.get("transparent"))
    has_vs = bool(data.get("word_times"))
    scale = 1.0 if has_vs else (portrait_scale(layout, data) if data.get("portrait") else 1.0)
    base_theme = TRANSPARENT_THEME_STYLE if transparent else THEME_STYLE
    style = base_theme + (f";transform:scale({scale});transform-origin:50% 50%" if scale != 1.0 else "")
    if layout in SQUARE_BLOCKS and not has_vs:   # khối vuông 1080x1080 đặt giữa khung
        style += ";transform:translate(0,420px)" if data.get("portrait") else ";transform:translate(420px,0)"
    literals = variant.literals(data) if variant.literals else None
    seed_key = json.dumps([layout, data.get("title"), data.get("tag"), data.get("caption")], ensure_ascii=False, sort_keys=True)
    return (
        prepare_block(
            variant.block,
            cid,
            duration,
            literals,
            transparent_background=transparent,
            seed_key=seed_key,
            fx_style=data.get("fx_style"),
            word_times=data.get("word_times"),
            tag_text=str(data.get("tag") or data.get("caption") or ""),
        ),
        host_attrs(variant.variables(data)),
        style,
    )


def _drag_literals(data: dict) -> dict[str, str]:
    """Hàm tương thích ngược phỏng sinh literals cho DRAG_TASKS qua manifest."""
    manifests = _LOADED_MANIFESTS.get("DRAG_TASKS", [])
    return render_literals(manifests[0], data) if manifests else {}


def _shift_literals(data: dict) -> dict[str, str]:
    """Hàm tương thích ngược phỏng sinh literals cho CARD_SHIFT qua manifest."""
    manifests = _LOADED_MANIFESTS.get("CARD_SHIFT", [])
    return render_literals(manifests[0], data) if manifests else {}
