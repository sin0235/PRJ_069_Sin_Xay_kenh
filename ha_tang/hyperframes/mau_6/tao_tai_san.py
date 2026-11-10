"""Công cụ tự động sinh bộ tài sản origami vector dùng chung cho 6 mẫu video HyperFrames."""
from pathlib import Path
import xml.etree.ElementTree as ET

OUT_DIR = Path("C:/PRJ069/ha_tang/hyperframes/mau_6/tai_san")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Bảng màu chuẩn Origami Editorial Motion B2B v1
C_NAVY = "#0a1c2b"
C_SURFACE = "#12324a"
C_IVORY = "#f6efe0"
C_IVORY_SHADE = "#e6dcce"
C_IVORY_DARK = "#d6c9b8"
C_TURQUOISE = "#5cc8c0"
C_TURQUOISE_SHADE = "#46ada6"
C_CORAL = "#e8695a"
C_CORAL_SHADE = "#d15344"
C_GOLD = "#ffd54a"
C_GOLD_SHADE = "#e6be33"
C_MUTED = "#9fb4c4"

ASSETS = {}

# 1. Đồng xu giấy 64px
ASSETS["vat_dong_xu.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-32 -64 64 64" width="64" height="64" data-anchor="0,0">
  <!-- Dong xu origami mat phang gom cac tam giac gap -->
  <g id="coin-root">
    <polygon points="0,-64 24,-54 32,-32 0,-32" fill="{C_GOLD}" />
    <polygon points="32,-32 24,-10 0,0 0,-32" fill="{C_GOLD_SHADE}" />
    <polygon points="0,0 -24,-10 -32,-32 0,-32" fill="{C_GOLD_SHADE}" />
    <polygon points="-32,-32 -24,-54 0,-64 0,-32" fill="{C_GOLD}" />
    <!-- Nep gap trung tam va vien sang 8% -->
    <polygon points="-12,-44 12,-44 16,-32 12,-20 -12,-20 -16,-32" fill="#fff5d0" opacity="0.85" />
    <polygon points="-6,-38 6,-38 6,-26 -6,-26" fill="{C_GOLD_SHADE}" />
    <!-- Duong nep gap sac sao -->
    <line x1="0" y1="-64" x2="0" y2="0" stroke="rgba(255,255,255,0.4)" stroke-width="1" />
    <line x1="-32" y1="-32" x2="32" y2="-32" stroke="rgba(255,255,255,0.4)" stroke-width="1" />
  </g>
</svg>"""

# 2. Túi tiền origami
ASSETS["vat_tui_tien.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-40 -80 80 80" width="80" height="80" data-anchor="0,0">
  <g id="money-bag-root">
    <!-- Day va phan than duoi -->
    <polygon points="-36,0 36,0 40,-35 -40,-35" fill="{C_TURQUOISE_SHADE}" />
    <polygon points="-40,-35 0,-35 0,0 -36,0" fill="{C_TURQUOISE}" />
    <!-- Than giua voi nep gap origami -->
    <polygon points="-40,-35 0,-35 -15,-55 -32,-55" fill="{C_TURQUOISE}" />
    <polygon points="0,-35 40,-35 32,-55 15,-55" fill="{C_TURQUOISE_SHADE}" />
    <polygon points="-15,-55 15,-55 0,-35" fill="#75d6cf" />
    <!-- Mieng tui buoc day vang -->
    <polygon points="-18,-55 18,-55 14,-62 -14,-62" fill="{C_GOLD}" />
    <polygon points="-24,-62 24,-62 28,-78 0,-70" fill="{C_TURQUOISE}" />
    <polygon points="0,-70 28,-78 -28,-78" fill="{C_TURQUOISE_SHADE}" />
    <!-- Nep day buoc ruy bang -->
    <polygon points="0,-60 8,-50 2,-48" fill="{C_GOLD_SHADE}" />
    <line x1="-40" y1="-35" x2="40" y2="-35" stroke="rgba(255,255,255,0.3)" stroke-width="1" />
  </g>
</svg>"""

# 3. Hộp giấy nhỏ (3 cỡ)
ASSETS["vat_hop_giay_nho.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-30 -60 60 60" width="60" height="60" data-anchor="0,0">
  <g id="box-small">
    <!-- Mat truoc -->
    <polygon points="-25,0 25,0 25,-32 -25,-32" fill="{C_IVORY_SHADE}" />
    <!-- Mat tren -->
    <polygon points="-25,-32 0,-50 50,-50 25,-32" fill="{C_IVORY}" />
    <!-- Mat ben phai -->
    <polygon points="25,0 25,-32 50,-50 50,-18" fill="{C_IVORY_DARK}" />
    <!-- Bang keo dan origami vang -->
    <polygon points="-5,-32 5,-32 30,-50 20,-50" fill="{C_GOLD}" opacity="0.9" />
    <polygon points="-5,0 5,0 5,-32 -5,-32" fill="{C_GOLD_SHADE}" opacity="0.9" />
    <!-- Canh giay sang 8% -->
    <line x1="-25" y1="-32" x2="25" y2="-32" stroke="rgba(255,255,255,0.5)" stroke-width="1.2" />
    <line x1="25" y1="-32" x2="25" y2="0" stroke="rgba(255,255,255,0.3)" stroke-width="1" />
  </g>
</svg>"""

# 4. Hộp giấy vừa
ASSETS["vat_hop_giay_vua.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-40 -80 80 80" width="80" height="80" data-anchor="0,0">
  <g id="box-med">
    <polygon points="-35,0 35,0 35,-45 -35,-45" fill="{C_IVORY_SHADE}" />
    <polygon points="-35,-45 0,-70 70,-70 35,-45" fill="{C_IVORY}" />
    <polygon points="35,0 35,-45 70,-70 70,-25" fill="{C_IVORY_DARK}" />
    <polygon points="-8,-45 8,-45 43,-70 27,-70" fill="{C_GOLD}" opacity="0.9" />
    <polygon points="-8,0 8,0 8,-45 -8,-45" fill="{C_GOLD_SHADE}" opacity="0.9" />
    <line x1="-35" y1="-45" x2="35" y2="-45" stroke="rgba(255,255,255,0.5)" stroke-width="1.2" />
    <line x1="35" y1="-45" x2="35" y2="0" stroke="rgba(255,255,255,0.3)" stroke-width="1" />
  </g>
</svg>"""

# 5. Hộp giấy lớn
ASSETS["vat_hop_giay_lon.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -100 100 100" width="100" height="100" data-anchor="0,0">
  <g id="box-large">
    <polygon points="-45,0 45,0 45,-58 -45,-58" fill="{C_IVORY_SHADE}" />
    <polygon points="-45,-58 0,-90 90,-90 45,-58" fill="{C_IVORY}" />
    <polygon points="45,0 45,-58 90,-90 90,-32" fill="{C_IVORY_DARK}" />
    <polygon points="-10,-58 10,-58 55,-90 35,-90" fill="{C_GOLD}" opacity="0.9" />
    <polygon points="-10,0 10,0 10,-58 -10,-58" fill="{C_GOLD_SHADE}" opacity="0.9" />
    <line x1="-45" y1="-58" x2="45" y2="-58" stroke="rgba(255,255,255,0.5)" stroke-width="1.2" />
    <line x1="45" y1="-58" x2="45" y2="0" stroke="rgba(255,255,255,0.3)" stroke-width="1" />
  </g>
</svg>"""

# 6. Thẻ hồ sơ (bo góc, nếp gấp, 3 màu)
ASSETS["vat_the_ho_so.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-45 -65 90 65" width="90" height="65" data-anchor="0,0" data-anchor-handle="0,-60">
  <g id="profile-card">
    <!-- Phan than the giay gap -->
    <path d="M-40,0 L40,0 Q45,0 45,-5 L45,-55 Q45,-60 40,-60 L-40,-60 Q-45,-60 -45,-55 L-45,-5 Q-45,0 -40,0 Z" fill="{C_SURFACE}" />
    <!-- Nep giay gap cheo tai goc tren phai -->
    <polygon points="25,-60 45,-40 45,-60" fill="{C_TURQUOISE}" />
    <polygon points="25,-60 45,-40 25,-40" fill="{C_TURQUOISE_SHADE}" />
    <!-- Duong chi tieu the noi bo -->
    <rect x="-35" y="-50" width="30" height="6" rx="2" fill="{C_GOLD}" />
    <rect x="-35" y="-38" width="55" height="4" rx="1.5" fill="{C_IVORY}" opacity="0.8" />
    <rect x="-35" y="-28" width="45" height="4" rx="1.5" fill="{C_IVORY}" opacity="0.6" />
    <rect x="-35" y="-18" width="35" height="4" rx="1.5" fill="{C_IVORY}" opacity="0.4" />
    <!-- Vien canh giay -->
    <path d="M-45,-55 L-45,-5 Q-45,0 -40,0 L40,0" stroke="rgba(255,255,255,0.2)" stroke-width="1" fill="none" />
  </g>
</svg>"""

# 7. Thẻ KPI
ASSETS["vat_the_kpi.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -70 100 70" width="100" height="70" data-anchor="0,0">
  <g id="kpi-card">
    <path d="M-46,0 L46,0 Q50,0 50,-4 L50,-64 Q50,-68 46,-68 L-46,-68 Q-50,-68 -50,-64 L-50,-4 Q-50,0 -46,0 Z" fill="{C_SURFACE}" />
    <rect x="-42" y="-62" width="84" height="20" rx="3" fill="#184261" />
    <polygon points="-42,-62 0,-62 -20,-42 -42,-42" fill="#20537a" />
    <circle cx="34" cy="-52" r="5" fill="{C_TURQUOISE}" />
    <!-- Chi so KPI noi bat -->
    <rect x="-40" y="-34" width="48" height="18" rx="2" fill="{C_GOLD}" opacity="0.9" />
    <polygon points="18,-30 40,-30 29,-16" fill="{C_TURQUOISE}" />
    <line x1="-50" y1="-68" x2="50" y2="-68" stroke="rgba(255,255,255,0.3)" stroke-width="1.2" />
  </g>
</svg>"""

# 8. Cột biểu đồ (bệ và thân)
ASSETS["vat_cot_bieu_do.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-30 -120 60 120" width="60" height="120" data-anchor="0,0">
  <g id="chart-bar">
    <!-- Be do origami -->
    <polygon points="-28,0 28,0 22,-10 -22,-10" fill="{C_NAVY}" />
    <!-- Than cot 3D origami -->
    <polygon points="-18,-10 18,-10 18,-105 -18,-105" fill="{C_TURQUOISE}" />
    <polygon points="18,-10 28,-18 28,-113 18,-105" fill="{C_TURQUOISE_SHADE}" />
    <polygon points="-18,-105 18,-105 28,-113 -8,-113" fill="#7cedeb" />
    <line x1="-18" y1="-105" x2="18" y2="-105" stroke="rgba(255,255,255,0.6)" stroke-width="1.5" />
    <line x1="18" y1="-105" x2="18" y2="-10" stroke="rgba(255,255,255,0.3)" stroke-width="1" />
  </g>
</svg>"""

# 9. Đồng hồ đo và kim đo origami
ASSETS["vat_dong_ho_do.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -100 100 100" width="100" height="100" data-anchor="0,0" data-anchor-needle="0,-50">
  <g id="gauge-meter">
    <!-- Mat dong ho tron gap phang -->
    <circle cx="0" cy="-50" r="46" fill="{C_SURFACE}" />
    <!-- Vanh do origami 3 phan mau -->
    <path d="M-38,-50 A38 38 0 0 1 -12,-84" stroke="{C_TURQUOISE}" stroke-width="8" fill="none" />
    <path d="M-12,-84 A38 38 0 0 1 20,-82" stroke="{C_GOLD}" stroke-width="8" fill="none" />
    <path d="M20,-82 A38 38 0 0 1 38,-50" stroke="{C_CORAL}" stroke-width="8" fill="none" />
    <!-- Tam kim dong ho va kim origami -->
    <circle cx="0" cy="-50" r="8" fill="{C_IVORY}" />
    <polygon id="needle" points="-3,-50 0,-85 3,-50" fill="{C_CORAL}" />
    <circle cx="0" cy="-50" r="3" fill="{C_NAVY}" />
  </g>
</svg>"""

# 10. Băng chuyền origami (module nối tiếp được)
ASSETS["vat_bang_chuyen.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-60 -40 120 40" width="120" height="40" data-anchor="0,0">
  <g id="conveyor-rail">
    <!-- Chan be -->
    <polygon points="-50,0 -40,0 -40,-15 -50,-15" fill="{C_NAVY}" />
    <polygon points="40,0 50,0 50,-15 40,-15" fill="{C_NAVY}" />
    <!-- Mat bang chuyen -->
    <polygon points="-60,-15 60,-15 52,-32 -52,-32" fill="{C_SURFACE}" />
    <polygon points="-60,-15 60,-15 60,-22 -60,-22" fill="#184364" />
    <!-- Vach phan doan bang chuyen co the noi lap lai -->
    <line x1="-30" y1="-15" x2="-26" y2="-32" stroke="rgba(255,255,255,0.25)" stroke-width="1.5" />
    <line x1="0" y1="-15" x2="4" y2="-32" stroke="rgba(255,255,255,0.25)" stroke-width="1.5" />
    <line x1="30" y1="-15" x2="34" y2="-32" stroke="rgba(255,255,255,0.25)" stroke-width="1.5" />
    <!-- Vien sang canh mep tren -->
    <line x1="-52" y1="-32" x2="52" y2="-32" stroke="rgba(255,255,255,0.5)" stroke-width="1.2" />
  </g>
</svg>"""

# 11. Trạm kiểm soát origami
ASSETS["vat_tram_kiem.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-35 -90 70 90" width="70" height="90" data-anchor="0,0">
  <g id="check-station">
    <!-- Cot tram -->
    <polygon points="-8,0 8,0 8,-70 -8,-70" fill="{C_SURFACE}" />
    <polygon points="8,0 14,-5 14,-75 8,-70" fill="#0d283c" />
    <!-- Khung cam bien origami tren dinh -->
    <polygon points="-30,-70 30,-70 24,-88 -24,-88" fill="{C_TURQUOISE}" />
    <polygon points="30,-70 24,-88 34,-92 40,-74" fill="{C_TURQUOISE_SHADE}" />
    <!-- Mat quet / den tin hieu -->
    <circle cx="0" cy="-79" r="5" fill="{C_GOLD}" />
    <line x1="-30" y1="-70" x2="30" y2="-70" stroke="rgba(255,255,255,0.5)" stroke-width="1.2" />
  </g>
</svg>"""

# 12. Kệ kho hàng origami
ASSETS["vat_ke_kho.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-50 -120 100 120" width="100" height="120" data-anchor="0,0">
  <g id="warehouse-rack">
    <!-- Cot thang dung trai va phai -->
    <polygon points="-48,0 -40,0 -40,-115 -48,-115" fill="{C_SURFACE}" />
    <polygon points="40,0 48,0 48,-115 40,-115" fill="{C_SURFACE}" />
    <!-- Tang do 1, 2, 3 -->
    <polygon points="-48,-35 48,-35 44,-42 -44,-42" fill="{C_MUTED}" />
    <polygon points="-48,-75 48,-75 44,-82 -44,-82" fill="{C_MUTED}" />
    <polygon points="-48,-115 48,-115 44,-122 -44,-122" fill="{C_MUTED}" />
    <!-- Thanh giang cheo chu X origami -->
    <line x1="-40" y1="-35" x2="40" y2="-75" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" />
    <line x1="40" y1="-35" x2="-40" y2="-75" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" />
    <line x1="-40" y1="-75" x2="40" y2="-115" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" />
    <line x1="40" y1="-75" x2="-40" y2="-115" stroke="rgba(255,255,255,0.2)" stroke-width="1.5" />
  </g>
</svg>"""

# 13. Xe nâng origami
ASSETS["vat_xe_nang.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-55 -75 110 75" width="110" height="75" data-anchor="0,0" data-anchor-fork="45,-15">
  <g id="forklift">
    <!-- Banh xe giay phang -->
    <circle cx="-30" cy="-10" r="10" fill="{C_NAVY}" />
    <circle cx="-30" cy="-10" r="5" fill="{C_GOLD}" />
    <circle cx="20" cy="-10" r="10" fill="{C_NAVY}" />
    <circle cx="20" cy="-10" r="5" fill="{C_GOLD}" />
    <!-- Than xe origami mau vang -->
    <polygon points="-45,-12 30,-12 25,-42 -20,-42 -45,-30" fill="{C_GOLD}" />
    <polygon points="-20,-42 25,-42 18,-68 -10,-68" fill="{C_GOLD_SHADE}" />
    <!-- Cabin va cua so -->
    <polygon points="-8,-45 15,-45 10,-65 -5,-65" fill="{C_SURFACE}" />
    <!-- Khung nang va cang nang phia truoc -->
    <polygon points="32,-5 38,-5 38,-70 32,-70" fill="{C_MUTED}" />
    <polygon points="34,-12 55,-12 55,-16 38,-16" fill="{C_MUTED}" />
    <line x1="-45" y1="-30" x2="25" y2="-42" stroke="rgba(255,255,255,0.4)" stroke-width="1.2" />
  </g>
</svg>"""

# 14. Bàn làm việc origami
ASSETS["vat_ban_lam_viec.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-60 -65 120 65" width="120" height="65" data-anchor="0,0">
  <g id="work-desk">
    <!-- Chan ban -->
    <polygon points="-52,0 -46,0 -46,-45 -52,-45" fill="{C_SURFACE}" />
    <polygon points="46,0 52,0 52,-45 46,-45" fill="{C_SURFACE}" />
    <!-- Mat ban origami 3D -->
    <polygon points="-60,-45 60,-45 48,-62 -48,-62" fill="{C_IVORY_SHADE}" />
    <polygon points="-60,-45 60,-45 60,-50 -60,-50" fill="{C_IVORY_DARK}" />
    <!-- Mep ban sang nhe -->
    <line x1="-48" y1="-62" x2="48" y2="-62" stroke="rgba(255,255,255,0.6)" stroke-width="1.2" />
  </g>
</svg>"""

# 15. Trang giấy hai mặt origami
ASSETS["vat_trang_giay.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-40 -60 80 60" width="80" height="60" data-anchor="0,0">
  <g id="flip-page">
    <!-- Mat truoc trang giay -->
    <polygon points="-35,0 35,0 35,-55 -35,-55" fill="{C_IVORY}" />
    <!-- Nep gap goc tren phai -->
    <polygon points="20,-55 35,-40 20,-40" fill="{C_IVORY_SHADE}" />
    <!-- Cac dong chu mo phong bang line mau muted -->
    <line x1="-28" y1="-45" x2="12" y2="-45" stroke="{C_SURFACE}" stroke-width="2.5" opacity="0.6" />
    <line x1="-28" y1="-35" x2="28" y2="-35" stroke="{C_SURFACE}" stroke-width="2" opacity="0.4" />
    <line x1="-28" y1="-27" x2="24" y2="-27" stroke="{C_SURFACE}" stroke-width="2" opacity="0.4" />
    <line x1="-28" y1="-19" x2="20" y2="-19" stroke="{C_SURFACE}" stroke-width="2" opacity="0.4" />
    <!-- Canh giay sang -->
    <line x1="-35" y1="-55" x2="20" y2="-55" stroke="rgba(255,255,255,0.7)" stroke-width="1.2" />
    <line x1="-35" y1="-55" x2="-35" y2="0" stroke="rgba(255,255,255,0.4)" stroke-width="1" />
  </g>
</svg>"""

# 16. Ghi chú dán origami có góc gấp
ASSETS["vat_ghi_chu_dan.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-25 -50 50 50" width="50" height="50" data-anchor="0,0">
  <g id="sticky-note">
    <!-- Giay note mau vang -->
    <polygon points="-22,0 22,0 22,-40 10,-48 -22,-48" fill="{C_GOLD}" />
    <!-- Goc gap cuon origami -->
    <polygon points="10,-48 22,-40 10,-40" fill="{C_GOLD_SHADE}" />
    <line x1="-16" y1="-34" x2="14" y2="-34" stroke="{C_NAVY}" stroke-width="2" opacity="0.5" />
    <line x1="-16" y1="-24" x2="10" y2="-24" stroke="{C_NAVY}" stroke-width="2" opacity="0.5" />
    <line x1="-16" y1="-14" x2="4" y2="-14" stroke="{C_NAVY}" stroke-width="2" opacity="0.5" />
  </g>
</svg>"""

# 17. Ngăn tủ / khay sắp xếp origami
ASSETS["vat_ngan_tu.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-45 -55 90 55" width="90" height="55" data-anchor="0,0">
  <g id="drawer-tray">
    <polygon points="-40,0 40,0 45,-45 -45,-45" fill="{C_SURFACE}" />
    <polygon points="-45,-45 45,-45 38,-52 -38,-52" fill="#1b4666" />
    <!-- Tay cam ngan tu -->
    <polygon points="-12,-20 12,-20 10,-26 -10,-26" fill="{C_GOLD}" />
    <line x1="-45" y1="-45" x2="45" y2="-45" stroke="rgba(255,255,255,0.4)" stroke-width="1.2" />
  </g>
</svg>"""

# 18. Ghế origami
ASSETS["vat_ghe.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-25 -65 50 65" width="50" height="65" data-anchor="0,0">
  <g id="chair">
    <!-- Chan ghe -->
    <line x1="-18" y1="0" x2="-14" y2="-28" stroke="{C_MUTED}" stroke-width="3" />
    <line x1="18" y1="0" x2="14" y2="-28" stroke="{C_MUTED}" stroke-width="3" />
    <!-- Dem ngoi -->
    <polygon points="-22,-28 22,-28 18,-35 -18,-35" fill="{C_SURFACE}" />
    <!-- Tua lung origami -->
    <polygon points="-18,-35 18,-35 16,-62 -16,-62" fill="{C_NAVY}" />
    <polygon points="-16,-62 0,-62 0,-35 -18,-35" fill="#132c42" />
    <line x1="-16" y1="-62" x2="16" y2="-62" stroke="rgba(255,255,255,0.4)" stroke-width="1" />
  </g>
</svg>"""

# 19. Nhân vật origami ngồi nhìn thẳng
ASSETS["vat_nhan_vat_thang.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-30 -85 60 85" width="60" height="85" data-anchor="0,0" data-anchor-hand="0,-35">
  <g id="char-front">
    <!-- Than duoi ngoi -->
    <polygon points="-18,0 18,0 15,-28 -15,-28" fill="{C_NAVY}" />
    <!-- Ao origami voi 2 nếp gap trai phai -->
    <polygon points="-15,-28 0,-28 0,-58 -22,-52" fill="{C_TURQUOISE}" />
    <polygon points="0,-28 15,-28 22,-52 0,-58" fill="{C_TURQUOISE_SHADE}" />
    <!-- Co ao vang -->
    <polygon points="-6,-58 6,-58 0,-48" fill="{C_GOLD}" />
    <!-- Dau hinh da giac origami -->
    <polygon points="-14,-62 0,-56 14,-62 12,-80 0,-84 -12,-80" fill="{C_IVORY}" />
    <polygon points="-14,-62 0,-56 0,-84 -12,-80" fill="{C_IVORY_SHADE}" />
    <!-- Duong nep giay song mui va go ma -->
    <line x1="0" y1="-84" x2="0" y2="-56" stroke="rgba(255,255,255,0.6)" stroke-width="1" />
    <line x1="0" y1="-58" x2="0" y2="-28" stroke="rgba(255,255,255,0.4)" stroke-width="1" />
  </g>
</svg>"""

# 20. Nhân vật origami ngồi nhìn nghiêng
ASSETS["vat_nhan_vat_nghieng.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-30 -85 60 85" width="60" height="85" data-anchor="0,0" data-anchor-hand="18,-35">
  <g id="char-tilt">
    <polygon points="-15,0 12,0 18,-28 -10,-28" fill="{C_NAVY}" />
    <polygon points="-10,-28 18,-28 24,-52 -6,-58" fill="{C_TURQUOISE}" />
    <polygon points="-6,-58 4,-58 10,-42" fill="{C_TURQUOISE_SHADE}" />
    <!-- Tay gio ve phia truoc (truyen viec) -->
    <polygon points="12,-42 28,-36 24,-32 10,-38" fill="{C_IVORY}" />
    <!-- Dau nghieng -->
    <polygon points="-10,-60 16,-54 22,-72 8,-84 -8,-76" fill="{C_IVORY}" />
    <polygon points="-10,-60 8,-84 -8,-76" fill="{C_IVORY_SHADE}" />
    <line x1="8" y1="-84" x2="16" y2="-54" stroke="rgba(255,255,255,0.6)" stroke-width="1" />
  </g>
</svg>"""

# 21. Nhân vật origami đứng / rời đi
ASSETS["vat_nhan_vat_roi_di.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-30 -100 60 100" width="60" height="100" data-anchor="0,0">
  <g id="char-leaving">
    <!-- Chan buoc di -->
    <polygon points="-12,0 -4,0 -2,-45 -10,-45" fill="{C_NAVY}" />
    <polygon points="4,0 14,-8 8,-45 0,-45" fill="#081520" />
    <!-- Than nguoi xoay lung / nghiem buoc -->
    <polygon points="-14,-45 10,-45 16,-75 -8,-75" fill="{C_MUTED}" />
    <polygon points="-8,-75 16,-75 4,-75" fill="#889dae" />
    <!-- Dau buoc quay lung -->
    <polygon points="-10,-78 12,-78 10,-96 -8,-96" fill="{C_IVORY_SHADE}" />
    <polygon points="-10,-78 0,-78 0,-96 -8,-96" fill="{C_IVORY_DARK}" />
  </g>
</svg>"""

# 22. Đèn báo (xanh, đỏ)
ASSETS["vat_den_bao.svg"] = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 -40 40 40" width="40" height="40" data-anchor="0,0">
  <g id="indicator-light">
    <!-- De den origami -->
    <polygon points="-16,0 16,0 12,-12 -12,-12" fill="{C_SURFACE}" />
    <!-- Vong bao xanh -->
    <circle cx="-6" cy="-22" r="7" fill="{C_TURQUOISE}" />
    <circle cx="-6" cy="-22" r="3" fill="#a4eee8" />
    <!-- Vong bao do -->
    <circle cx="6" cy="-22" r="7" fill="{C_CORAL}" />
    <circle cx="6" cy="-22" r="3" fill="#f8aba2" />
    <line x1="-12" y1="-12" x2="12" y2="-12" stroke="rgba(255,255,255,0.4)" stroke-width="1" />
  </g>
</svg>"""

# Lưu từng tệp
for name, content in ASSETS.items():
    file_path = OUT_DIR / name
    file_path.write_text(content.strip(), encoding="utf-8")
    print(f"Đã lưu: {name}")

# Tạo ảnh tổng hợp tong_hop.svg xếp tất cả các vật cạnh nhau
TONG_HOP_WIDTH = 1200
TONG_HOP_HEIGHT = 700

items_list = list(ASSETS.items())
# Chia thanh 4 hang x 6 cot
cols = 6
rows = 4
cell_w = TONG_HOP_WIDTH / cols
cell_h = (TONG_HOP_HEIGHT - 60) / rows

svg_items = []
for idx, (name, content) in enumerate(items_list):
    r = idx // cols
    c = idx % cols
    cx = c * cell_w + cell_w / 2
    cy = 60 + r * cell_h + cell_h - 20
    # Clean inner g from content
    root = ET.fromstring(content)
    inner_str = "".join(ET.tostring(child, encoding="unicode") for child in root)
    label = name.replace("vat_", "").replace(".svg", "")
    svg_items.append(f"""
    <g transform="translate({cx}, {cy})">
      <line x1="-{cell_w*0.4}" y1="0" x2="{cell_w*0.4}" y2="0" stroke="rgba(255,255,255,0.15)" stroke-dasharray="3,3" />
      {inner_str}
      <text x="0" y="16" text-anchor="middle" fill="{C_IVORY}" font-family="'Viet', sans-serif" font-size="11">{label}</text>
    </g>""")

tong_hop_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TONG_HOP_WIDTH} {TONG_HOP_HEIGHT}" width="{TONG_HOP_WIDTH}" height="{TONG_HOP_HEIGHT}">
  <rect width="{TONG_HOP_WIDTH}" height="{TONG_HOP_HEIGHT}" fill="{C_NAVY}" />
  <text x="30" y="38" fill="{C_GOLD}" font-family="'Viet', sans-serif" font-size="20" font-weight="bold">BỘ TÀI SẢN ORIGAMI DÙNG CHUNG (T01) - 6 MẪU VIDEO HYPERFRAMES</text>
  <text x="950" y="38" fill="{C_MUTED}" font-family="'Viet', sans-serif" font-size="13">Baha Origami Editorial Motion B2B</text>
  <line x1="30" y1="48" x2="{TONG_HOP_WIDTH-30}" y2="48" stroke="rgba(255,255,255,0.2)" stroke-width="1" />
  {"".join(svg_items)}
</svg>"""

(OUT_DIR / "tong_hop.svg").write_text(tong_hop_content.strip(), encoding="utf-8")
print("Đã tạo: tong_hop.svg")

# Tạo DANH_MUC.md
danh_muc_content = """# Danh mục tài sản Origami dùng chung (T01)

Ngày cập nhật: 09/11/2026
Phong cách: "Origami Editorial Motion B2B v1"
Quy chuẩn:
- 100% Vector SVG, không ảnh điểm (no bitmap/raster), không font ngoài nhúng, không CDN/URL ngoài.
- Nếp gấp nhìn thấy được, cạnh giấy sáng hơn 8%, không viền đen bao quanh.
- Bóng đổ được tạo bằng CSS / GSAP khi dựng composition, không nung bóng (baked shadow) vào SVG.
- Gốc toạ độ `(0,0)` đặt tại chính giữa đáy của vật (bottom-center) với thuộc tính `data-anchor="0,0"` để vật tiếp xúc sàn và các lớp khác chuẩn xác.

| Tên tệp | Tên vật | Kích thước chuẩn | Điểm neo | Dùng cho layout | Giấy phép |
|---|---|---|---|---|---|
| `vat_dong_xu.svg` | Đồng xu giấy origami | 64×64 px | `(0,0)` đáy giữa | A, V2, V3, V5 | Tự vẽ (PRJ069) |
| `vat_tui_tien.svg` | Túi tiền origami | 80×80 px | `(0,0)` đáy giữa | A, V2, V3 | Tự vẽ (PRJ069) |
| `vat_hop_giay_nho.svg` | Hộp giấy nhỏ | 60×60 px | `(0,0)` đáy giữa | C, V3, V5 | Tự vẽ (PRJ069) |
| `vat_hop_giay_vua.svg` | Hộp giấy vừa | 80×80 px | `(0,0)` đáy giữa | C, V3, V5 | Tự vẽ (PRJ069) |
| `vat_hop_giay_lon.svg` | Hộp giấy lớn | 100×100 px | `(0,0)` đáy giữa | C, V3, V5 | Tự vẽ (PRJ069) |
| `vat_the_ho_so.svg` | Thẻ hồ sơ khách hàng | 90×65 px | `(0,0)` đáy, `(0,-60)` tay | B, V1, V3, V4, V5, V6 | Tự vẽ (PRJ069) |
| `vat_the_kpi.svg` | Thẻ KPI dữ liệu | 100×70 px | `(0,0)` đáy giữa | E, V1, V2, V3, V4, V5 | Tự vẽ (PRJ069) |
| `vat_cot_bieu_do.svg` | Cột biểu đồ 3D origami | 60×120 px | `(0,0)` đáy giữa | E, V1, V2, V4 | Tự vẽ (PRJ069) |
| `vat_dong_ho_do.svg` | Đồng hồ đo và kim origami | 100×100 px | `(0,0)` đáy, `(0,-50)` tâm kim | E, V1, V2, V3 | Tự vẽ (PRJ069) |
| `vat_bang_chuyen.svg` | Băng chuyền module | 120×40 px | `(0,0)` đáy giữa | B, V1, V3, V4, V5, V6 | Tự vẽ (PRJ069) |
| `vat_tram_kiem.svg` | Trạm kiểm soát quy trình | 70×90 px | `(0,0)` đáy giữa | B, V1, V3, V5 | Tự vẽ (PRJ069) |
| `vat_ke_kho.svg` | Kệ kho hàng module | 100×120 px | `(0,0)` đáy giữa | C, V3, V5 | Tự vẽ (PRJ069) |
| `vat_xe_nang.svg` | Xe nâng pallet origami | 110×75 px | `(0,0)` đáy, `(45,-15)` càng | C, V3, V5 | Tự vẽ (PRJ069) |
| `vat_ban_lam_viec.svg` | Bàn làm việc phối cảnh | 120×65 px | `(0,0)` đáy giữa | D, F, V4, V6 | Tự vẽ (PRJ069) |
| `vat_trang_giay.svg` | Trang giấy lật hai mặt | 80×60 px | `(0,0)` đáy giữa | D, V4, V6 | Tự vẽ (PRJ069) |
| `vat_ghi_chu_dan.svg` | Ghi chú dán góc gấp | 50×50 px | `(0,0)` đáy giữa | D, F, V4, V6 | Tự vẽ (PRJ069) |
| `vat_ngan_tu.svg` | Khay sắp xếp / ngăn tủ | 90×55 px | `(0,0)` đáy giữa | D, V4, V6 | Tự vẽ (PRJ069) |
| `vat_ghe.svg` | Ghế ngồi origami | 50×65 px | `(0,0)` đáy giữa | F, V4, V6 | Tự vẽ (PRJ069) |
| `vat_nhan_vat_thang.svg` | Nhân vật ngồi thẳng | 60×85 px | `(0,0)` đáy, `(0,-35)` tay | F, V4, V6 | Tự vẽ (PRJ069) |
| `vat_nhan_vat_nghieng.svg` | Nhân vật ngồi chuyền việc | 60×85 px | `(0,0)` đáy, `(18,-35)` tay | F, V4, V6 | Tự vẽ (PRJ069) |
| `vat_nhan_vat_roi_di.svg` | Nhân vật đứng rời đi | 60×100 px | `(0,0)` đáy giữa | F, V4, V6 | Tự vẽ (PRJ069) |
| `vat_den_bao.svg` | Đèn báo tín hiệu đỏ/xanh | 40×40 px | `(0,0)` đáy giữa | B, F, V1, V5, V6 | Tự vẽ (PRJ069) |
"""
(OUT_DIR / "DANH_MUC.md").write_text(danh_muc_content.strip(), encoding="utf-8")
print("Đã tạo: DANH_MUC.md")

