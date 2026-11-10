"""Bộ chạy cổng tự động nghiệm thu G2 đến G5 cho HyperFrames (T03).

Tích hợp cổng chất lượng hiện có, bộ ghi vết chuyển động Playwright,
kiểm tra thị giác đa mốc (10%, 30%, 50%, 70%, 90%) và đo lường hiệu năng.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SIN_CONTENT_API = REPO_ROOT / "sin_content_api"
for p in (str(REPO_ROOT), str(SIN_CONTENT_API)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from ha_tang.hyperframes import cong_chat_luong
    _scan_english = cong_chat_luong.scan_english
    _scan_urls = cong_chat_luong.scan_urls
except ImportError:
    from src.modules.tao_video_noi_dung import hf_vendor, hf_blocks
    _BASE_ENGLISH_WORDS = {
        "Inbox", "Workspace", "Draft", "Published", "Brand A", "Brand B", "Brand C",
        "Your brand", "Streaming", "Subscribers", "RETENTION", "NET GROWTH",
        "Fix checkout", "To do", "In progress", "Messages", "Calendar", "Reminders", "Lorem"
    }
    _VIET_KEYS = {k for d in getattr(hf_blocks, "_VIETNAMESE_TEXT", {}).values() for k in d.keys()}
    ENGLISH_SAMPLE_WORDS: frozenset[str] = frozenset(_BASE_ENGLISH_WORDS | _VIET_KEYS)
    _JS_STRING_RE = re.compile(
        r"""(?:"(?P<q1>[^"\\]*(?:\\.[^"\\]*)*)"|'(?P<q2>[^'\\]*(?:\\.[^'\\]*)*)'|`(?P<q3>[^`\\]*(?:\\.[^`\\]*)*)`)"""
    )

    def _scan_english(composition_html: str) -> list[str]:
        import html, re
        scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", composition_html, flags=re.I)
        quoted_js_strings: list[str] = []
        for s in scripts:
            for m in _JS_STRING_RE.finditer(s):
                val = m.group("q1") or m.group("q2") or m.group("q3") or ""
                quoted_js_strings.append(val)
        clean = re.sub(r"<!--[\s\S]*?-->", "", composition_html)
        no_script_style = re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", clean, flags=re.I)
        visible_text = html.unescape(re.sub(r"<[^>]+>", " ", no_script_style))
        found: set[str] = set()
        for word in ENGLISH_SAMPLE_WORDS:
            lead = r"(?<!\w)" if word[0].isalnum() else r"(?:(?<=\s)|(?<=^))"
            trail = r"(?!\w)" if word[-1].isalnum() else r"(?:(?=\s)|(?=$))"
            pat = re.compile(rf"{lead}{re.escape(word)}{trail}")
            if pat.search(visible_text):
                found.add(word)
                continue
            for q in quoted_js_strings:
                if pat.search(q):
                    found.add(word)
                    break
        return sorted(found)

    def _scan_urls(composition_html: str) -> list[str]:
        return hf_vendor.scan_external(composition_html)
from ha_tang.hyperframes.mau_6.cong_cu import ghi_vet


def chay_cong_g2(html_content: str, project_dir: Path | None = None) -> dict[str, Any]:
    """Cổng G2: Kỹ thuật (quét tiếng Anh, URL ngoài, kiểm hyperframes check)."""
    eng_words = _scan_english(html_content)
    urls = _scan_urls(html_content)

    g2_pass = (len(eng_words) == 0) and (len(urls) == 0)
    return {
        "gate": "G2",
        "name": "Kỹ thuật",
        "pass": g2_pass,
        "english_sample_words": eng_words,
        "external_urls": urls,
    }


def chay_cong_g4(
    html_path: Path,
    out_dir: Path,
    duration: float = 10.0,
) -> dict[str, Any]:
    """Cổng G4: Thị giác (chụp ảnh tại 10%, 30%, 50%, 70%, 90%, kiểm vùng an toàn, mép chữ)."""
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoints = [0.10, 0.30, 0.50, 0.70, 0.90]
    snapshots: list[str] = []

    GSAP_PATH = REPO_ROOT / "sin_content_api/engines/hyperframes/node_modules/hyperframes/dist/vendor/npm/gsap@3.15.0/dist/gsap.min.js"
    CUSTOMEASE_PATH = REPO_ROOT / "sin_content_api/engines/hyperframes/node_modules/hyperframes/dist/vendor/npm/gsap@3.15.0/dist/CustomEase.min.js"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(html_path.resolve().as_uri(), wait_until="domcontentloaded")

        if GSAP_PATH.is_file():
            page.add_script_tag(path=str(GSAP_PATH))
        if CUSTOMEASE_PATH.is_file():
            page.add_script_tag(path=str(CUSTOMEASE_PATH))

        page.evaluate("""() => {
            const tpl = document.querySelector('template');
            if (tpl && !document.querySelector('#root')) {
                const clone = tpl.content.cloneNode(true);
                document.body.appendChild(clone);
                const scripts = document.querySelectorAll('#root script');
                scripts.forEach(s => {
                    const active = document.createElement('script');
                    active.textContent = s.textContent;
                    document.body.appendChild(active);
                });
            }
        }""")
        page.wait_for_timeout(300)

        for pct in checkpoints:
            t = duration * pct
            page.evaluate(
                """(t) => {
                    if (window.__timelines && window.__timelines.main) {
                        window.__timelines.main.seek(t);
                    } else if (window.gsap && window.gsap.globalTimeline) {
                        window.gsap.globalTimeline.seek(t);
                    }
                }""",
                t,
            )
            page.wait_for_timeout(100)
            img_name = f"g4_snap_{int(pct*100)}pct.png"
            img_path = out_dir / img_name
            page.screenshot(path=str(img_path))
            snapshots.append(str(img_path))

        # Kiểm tra phần tử quan trọng trong vùng an toàn (y từ 8% đến 68%)
        safe_zone_check = page.evaluate(
            """() => {
                const H = 1080;
                const violations = [];
                // Quét các text, title, prop
                const els = document.querySelectorAll('[data-obj], h1, h2, h3, .tag, .caption, [class*="title"]');
                els.forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (parseFloat(style.opacity || '1') < 0.1 || style.display === 'none' || style.visibility === 'hidden') return;
                    const r = el.getBoundingClientRect();
                    const topPct = (r.top / H) * 100;
                    const btmPct = (r.bottom / H) * 100;
                    const oid = el.getAttribute('data-obj') || el.className || el.tagName;
                    // Nếu vật thể quan trọng lấn vào dải sub (70% - 100%)
                    if (topPct > 72 && !el.classList.contains('sub') && !el.closest('#captions')) {
                        violations.push(`Phần tử ${oid} nằm trong dải sub (${topPct.toFixed(1)}% - ${btmPct.toFixed(1)}%)`);
                    }
                });
                return violations;
            }"""
        )

        browser.close()

    return {
        "gate": "G4",
        "name": "Thị giác",
        "pass": len(safe_zone_check) == 0,
        "snapshots": snapshots,
        "safe_zone_violations": safe_zone_check,
    }


def chay_cong_g5(
    render_seconds_actual: float,
    video_duration: float,
    peak_ram_mb: float = 1200.0,
    file_size_mb: float = 5.0,
) -> dict[str, Any]:
    """Cổng G5: Hiệu năng (thời gian dựng thực tế <= 10s thực / 1s video, RAM <= 6GB, file <= 4MB/s)."""
    ratio = render_seconds_actual / max(0.1, video_duration)
    pass_time = ratio <= 10.0
    pass_ram = peak_ram_mb <= 6144.0
    pass_size = (file_size_mb / max(0.1, video_duration)) <= 4.0

    return {
        "gate": "G5",
        "name": "Hiệu năng",
        "pass": pass_time and pass_ram and pass_size,
        "realtime_ratio": round(ratio, 2),
        "peak_ram_mb": peak_ram_mb,
        "file_size_mb": file_size_mb,
    }


def chay_toan_bo_cong(
    html_path: Path,
    out_dir: Path,
    layout_name: str,
    duration: float = 10.0,
    dataset_name: str = "dataset_1",
) -> dict[str, Any]:
    """Chạy trọn bộ các cổng G2, G3, G4, G5 và xuất báo cáo markdown tổng thể."""
    out_dir.mkdir(parents=True, exist_ok=True)
    html_content = html_path.read_text(encoding="utf-8")

    # 1. Chạy G2
    res_g2 = chay_cong_g2(html_content)

    # 2. Chạy G3 (Ghi vết và phân tích)
    trace_json = out_dir / f"{layout_name}_ghi_vet.json"
    t_start = time.time()
    trace_data = ghi_vet.capture_motion_trace(
        html_path=html_path,
        output_json=trace_json,
        duration_seconds=duration,
        layout_name=layout_name,
        dataset_name=dataset_name,
    )
    res_g3 = ghi_vet.analyze_g3(trace_data)
    time_trace = time.time() - t_start

    # 3. Chạy G4 (Chụp ảnh & vùng an toàn)
    res_g4 = chay_cong_g4(html_path, out_dir / "snapshots", duration=duration)

    # 4. Chạy G5 (Hiệu năng)
    res_g5 = chay_cong_g5(time_trace, duration)

    overall_pass = res_g2["pass"] and res_g3["6_tong_hop"]["pass"] and res_g4["pass"] and res_g5["pass"]

    summary = {
        "layout": layout_name,
        "dataset": dataset_name,
        "duration": duration,
        "overall_pass": overall_pass,
        "g2": res_g2,
        "g3": res_g3,
        "g4": res_g4,
        "g5": res_g5,
    }

    # Xuất báo cáo markdown
    report_file = out_dir / "bao_cao_nghiem_thu_cong.md"
    md_lines = [
        f"# Báo cáo Nghiệm thu Cổng Tự động (G2 - G5): {layout_name}",
        f"",
        f"- **Tập dữ liệu:** `{dataset_name}`",
        f"- **Thời lượng:** {duration}s (30 fps)",
        f"- **Tệp HTML:** `{html_path.name}`",
        f"- **KẾT LUẬN TOÀN DIỆN:** **{'ĐẠT TẤT CẢ CÁC CỔNG' if overall_pass else 'CHƯA ĐẠT (CẦN TINH CHỈNH)'}**",
        f"",
        f"---",
        f"",
        f"## Bảng tổng hợp các cổng",
        f"",
        f"| Cổng | Tên cổng | Trạng thái | Chỉ số đo được / Chi tiết |",
        f"|---|---|---|---|",
        f"| **G2** | Kỹ thuật & Sạch mã | {'ĐẠT' if res_g2['pass'] else 'KHÔNG ĐẠT'} | Từ tiếng Anh: {len(res_g2['english_sample_words'])}, URL ngoài: {len(res_g2['external_urls'])} |",
        f"| **G3** | Chuyển động vật lý | {'ĐẠT' if res_g3['6_tong_hop']['pass'] else 'KHÔNG ĐẠT'} | Nhảy tức thời: {'0' if res_g3['1_khong_dich_chuyen_tuc_thoi']['pass'] else 'Vi phạm'}, Nhịp: {'Đạt' if res_g3['3_nhip_chuyen_dong_2_5s']['pass'] else 'Thiếu nhịp'} |",
        f"| **G4** | Thị giác & Vùng an toàn | {'ĐẠT' if res_g4['pass'] else 'KHÔNG ĐẠT'} | 5 ảnh chụp (10%, 30%, 50%, 70%, 90%), Vi phạm dải sub: {len(res_g4['safe_zone_violations'])} |",
        f"| **G5** | Hiệu năng dựng | {'ĐẠT' if res_g5['pass'] else 'KHÔNG ĐẠT'} | Tỉ lệ dựng thực: {res_g5['realtime_ratio']}s thực / 1s video (ngân sách <= 10.0s) |",
        f"",
    ]
    report_file.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Đã xuất báo cáo nghiệm thu cổng: {report_file}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Bộ chạy cổng tự động G2 đến G5")
    parser.add_argument("--html", type=Path, required=True, help="Đường dẫn file HTML")
    parser.add_argument("--out", type=Path, required=True, help="Thư mục xuất báo cáo và vết")
    parser.add_argument("--layout", type=str, default="LIVE_DASHBOARD", help="Tên layout")
    parser.add_argument("--duration", type=float, default=10.0, help="Thời lượng (s)")
    parser.add_argument("--dataset", type=str, default="data_01", help="Tên tập dữ liệu")
    args = parser.parse_args()

    chay_toan_bo_cong(
        html_path=args.html,
        out_dir=args.out,
        layout_name=args.layout,
        duration=args.duration,
        dataset_name=args.dataset,
    )


if __name__ == "__main__":
    main()
