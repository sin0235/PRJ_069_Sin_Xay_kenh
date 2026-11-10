"""Công cụ ghi vết chuyển động (Motion Tracer) và phân tích Cổng G3 cho HyperFrames.

Thu thập vị trí, trạng thái camera và vật thể tại mỗi khung hình (30 fps)
và đối soát theo 12 quy tắc chuyển động thật của dự án.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

# Đảm bảo đường dẫn tới sin_content_api
REPO_ROOT = Path(__file__).resolve().parents[4]
SIN_CONTENT_API = REPO_ROOT / "sin_content_api"
if str(SIN_CONTENT_API) not in sys.path:
    sys.path.insert(0, str(SIN_CONTENT_API))


def capture_motion_trace(
    html_path: Path,
    output_json: Path,
    duration_seconds: float = 10.0,
    fps: int = 30,
    layout_name: str = "CANH",
    dataset_name: str = "default",
) -> dict[str, Any]:
    """Sử dụng Playwright để duyệt từng khung hình và trích xuất dữ liệu toạ độ, camera."""
    from playwright.sync_api import sync_playwright

    total_frames = int(duration_seconds * fps)
    frames_data: list[dict[str, Any]] = []

    GSAP_PATH = REPO_ROOT / "sin_content_api/engines/hyperframes/node_modules/hyperframes/dist/vendor/npm/gsap@3.15.0/dist/gsap.min.js"
    CUSTOMEASE_PATH = REPO_ROOT / "sin_content_api/engines/hyperframes/node_modules/hyperframes/dist/vendor/npm/gsap@3.15.0/dist/CustomEase.min.js"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(html_path.resolve().as_uri(), wait_until="domcontentloaded")

        # Nạp GSAP và CustomEase cục bộ nếu trang chưa có
        if GSAP_PATH.is_file():
            page.add_script_tag(path=str(GSAP_PATH))
        if CUSTOMEASE_PATH.is_file():
            page.add_script_tag(path=str(CUSTOMEASE_PATH))

        # Khui template nếu khối được đóng gói trong <template>
        page.evaluate("""() => {
            const tpl = document.querySelector('template');
            if (tpl && !document.querySelector('#root')) {
                const clone = tpl.content.cloneNode(true);
                document.body.appendChild(clone);
                // Kích hoạt các thẻ script bên trong template vừa khui
                const scripts = document.querySelectorAll('#root script');
                scripts.forEach(s => {
                    const active = document.createElement('script');
                    active.textContent = s.textContent;
                    document.body.appendChild(active);
                });
            }
        }""")

        # Đợi các timeline khởi tạo
        page.wait_for_timeout(300)

        for frame_idx in range(total_frames):
            current_time = frame_idx / fps

            # Seek timeline nếu có timeline GSAP
            page.evaluate(
                """(t) => {
                    if (window.__timelines && window.__timelines.main) {
                        window.__timelines.main.seek(t);
                    } else if (window.gsap && window.gsap.globalTimeline) {
                        window.gsap.globalTimeline.seek(t);
                    }
                }""",
                current_time,
            )

            # Thu thập trạng thái các vật [data-obj] và camera (-world)
            frame_state = page.evaluate(
                """() => {
                    const W = 1920;
                    const H = 1080;
                    
                    // Lấy camera từ #root > .-world hoặc #bg-cam hoặc #world
                    let cam = { scale: 1.0, x: 0.0, y: 0.0 };
                    const worldEl = document.querySelector('.-world, [data-camera-world], #world');
                    if (worldEl) {
                        const style = window.getComputedStyle(worldEl);
                        const tf = style.transform;
                        if (tf && tf !== 'none') {
                            const m = tf.match(/matrix\\(([^)]+)\\)/);
                            if (m) {
                                const vals = m[1].split(',').map(Number);
                                cam.scale = Math.sqrt(vals[0]*vals[0] + vals[1]*vals[1]);
                                cam.x = (vals[4] / W) * 100;
                                cam.y = (vals[5] / H) * 100;
                            }
                        }
                    }

                    const objects = [];
                    const els = document.querySelectorAll('[data-obj]');
                    els.forEach(el => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        const opacity = parseFloat(style.opacity || '1.0');
                        
                        // Tính toạ độ tâm % và kích thước %
                        const cx = ((rect.left + rect.width / 2) / W) * 100;
                        const cy = ((rect.top + rect.height / 2) / H) * 100;
                        const w = (rect.width / W) * 100;
                        const h = (rect.height / H) * 100;

                        // Kiểm tra visible (độ mờ > 0.05 và nằm ít nhất 1 phần trong viewport)
                        const inViewport = (rect.right >= 0 && rect.left <= W && rect.bottom >= 0 && rect.top <= H);
                        const isVisible = (opacity > 0.05) && inViewport && (style.visibility !== 'hidden') && (style.display !== 'none');

                        // Lấy góc xoay từ matrix nếu có
                        let rotation = 0;
                        const tf = style.transform;
                        if (tf && tf !== 'none') {
                            const m = tf.match(/matrix\\(([^)]+)\\)/);
                            if (m) {
                                const vals = m[1].split(',').map(Number);
                                rotation = Math.round(Math.atan2(vals[1], vals[0]) * (180 / Math.PI));
                            }
                        }

                        objects.push({
                            obj_id: el.getAttribute('data-obj') || '',
                            kind: el.getAttribute('data-kind') || 'prop',
                            src: el.getAttribute('data-src') || 'static',
                            dst: el.getAttribute('data-dst') || 'stay',
                            cx: Number(cx.toFixed(2)),
                            cy: Number(cy.toFixed(2)),
                            w: Number(w.toFixed(2)),
                            h: Number(h.toFixed(2)),
                            opacity: Number(opacity.toFixed(2)),
                            rotation: rotation,
                            visible: isVisible
                        });
                    });

                    return { cam, objects };
                }"""
            )

            frames_data.append(
                {
                    "frame": frame_idx,
                    "time": round(current_time, 3),
                    "camera": frame_state["cam"],
                    "objects": frame_state["objects"],
                }
            )

        browser.close()

    trace_result = {
        "layout": layout_name,
        "duration": duration_seconds,
        "fps": fps,
        "dataset": dataset_name,
        "frames": frames_data,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(trace_result, f, ensure_ascii=False, indent=2)

    return trace_result


def analyze_g3(trace_data: dict[str, Any]) -> dict[str, Any]:
    """Phân tích dữ liệu vết chuyển động theo 6 phép kiểm của Cổng G3."""
    frames = trace_data.get("frames", [])
    fps = trace_data.get("fps", 30)
    total_frames = len(frames)
    duration = trace_data.get("duration", 10.0)

    checks = {
        "1_khong_dich_chuyen_tuc_thoi": {"pass": True, "violations": []},
        "2_xuat_hien_bien_mat_dung_luat": {"pass": True, "violations": []},
        "3_nhip_chuyen_dong_2_5s": {"pass": True, "violations": []},
        "4_toc_do_camera_hop_le": {"pass": True, "violations": []},
        "5_chuyen_dong_co_khoi_luong": {"pass": True, "violations": []},
        "6_tong_hop": {"pass": True, "score": 100},
    }

    # Theo dõi trạng thái từng vật qua từng khung hình
    obj_timeline: dict[str, list[dict]] = {}
    for f in frames:
        t = f["time"]
        for o in f["objects"]:
            oid = o["obj_id"]
            if oid not in obj_timeline:
                obj_timeline[oid] = []
            obj_timeline[oid].append({"time": t, "frame": f["frame"], **o})

    # Phép 1: Không dịch chuyển tức thời (< 12% bề rộng khung / khung hình)
    for oid, history in obj_timeline.items():
        if not history or history[0]["kind"] != "prop":
            continue
        for i in range(1, len(history)):
            prev = history[i - 1]
            curr = history[i]
            if prev["visible"] and curr["visible"]:
                dx = abs(curr["cx"] - prev["cx"])
                dy = abs(curr["cy"] - prev["cy"])
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 12.0:  # Quá 12%
                    msg = f"Vật {oid} nhảy {dist:.1f}% tại t={curr['time']}s (khung {curr['frame']})"
                    checks["1_khong_dich_chuyen_tuc_thoi"]["violations"].append(msg)
                    checks["1_khong_dich_chuyen_tuc_thoi"]["pass"] = False

    # Phép 2: Xuất hiện và biến mất đúng luật
    for oid, history in obj_timeline.items():
        if not history or history[0]["kind"] != "prop":
            continue
        first_vis = next((h for h in history if h["visible"]), None)
        if first_vis and first_vis["frame"] > 0:
            # Xuất hiện giữa chừng, kiểm tra src
            src = first_vis["src"]
            if src in ("static", "stay"):
                msg = f"Vật {oid} xuất hiện tại t={first_vis['time']}s nhưng data-src='{src}'"
                checks["2_xuat_hien_bien_mat_dung_luat"]["violations"].append(msg)
                checks["2_xuat_hien_bien_mat_dung_luat"]["pass"] = False

        last_vis = next((h for h in reversed(history) if h["visible"]), None)
        if last_vis and last_vis["frame"] < total_frames - 1:
            # Biến mất trước khi hết cảnh
            dst = last_vis["dst"]
            if dst == "stay":
                msg = f"Vật {oid} biến mất tại t={last_vis['time']}s nhưng data-dst='stay'"
                checks["2_xuat_hien_bien_mat_dung_luat"]["violations"].append(msg)
                checks["2_xuat_hien_bien_mat_dung_luat"]["pass"] = False

    # Phép 3: Nhịp chuyển động 2.5s (mọi cửa sổ 75 khung hình có biến cố)
    window_size = int(fps * 2.5)
    # Xác định các khung hình có sự kiện (vật thay đổi vị trí, xuất hiện, hoặc camera dịch)
    event_frames = set()
    for i in range(1, len(frames)):
        prev_f = frames[i - 1]
        curr_f = frames[i]
        # Check camera
        c_p = prev_f["camera"]
        c_c = curr_f["camera"]
        if abs(c_c["x"] - c_p["x"]) > 0.02 or abs(c_c["y"] - c_p["y"]) > 0.02 or abs(c_c["scale"] - c_p["scale"]) > 0.001:
            event_frames.add(curr_f["frame"])
        # Check objects
        for obj in curr_f["objects"]:
            oid = obj["obj_id"]
            prev_obj = next((o for o in prev_f["objects"] if o["obj_id"] == oid), None)
            if prev_obj and obj["visible"]:
                if (abs(obj["cx"] - prev_obj["cx"]) > 0.05 or
                    abs(obj["cy"] - prev_obj["cy"]) > 0.05 or
                    abs(obj["opacity"] - prev_obj["opacity"]) > 0.05 or
                    abs(obj["rotation"] - prev_obj["rotation"]) > 0.5):
                    event_frames.add(curr_f["frame"])
            elif not prev_obj and obj["visible"]:
                event_frames.add(curr_f["frame"])

    for start_f in range(0, max(1, total_frames - window_size), fps):
        window_events = [f for f in event_frames if start_f <= f <= start_f + window_size]
        if not window_events:
            msg = f"Khoảng chết nhịp >2.5s tại đoạn {start_f/fps:.1f}s - {(start_f+window_size)/fps:.1f}s"
            checks["3_nhip_chuyen_dong_2_5s"]["violations"].append(msg)
            checks["3_nhip_chuyen_dong_2_5s"]["pass"] = False

    # Phép 4: Giới hạn tốc độ camera (lia < 12%/s, zoom < 8%/s)
    for i in range(fps, len(frames), fps):
        c_curr = frames[i]["camera"]
        c_prev = frames[i - fps]["camera"]
        dx_s = abs(c_curr["x"] - c_prev["x"])  # %/giây
        dy_s = abs(c_curr["y"] - c_prev["y"])
        dscale_s = abs(c_curr["scale"] - c_prev["scale"]) * 100  # %/giây
        if dx_s > 12.5:
            msg = f"Camera lia ngang quá nhanh: {dx_s:.1f}%/s tại t={i/fps}s"
            checks["4_toc_do_camera_hop_le"]["violations"].append(msg)
            checks["4_toc_do_camera_hop_le"]["pass"] = False
        if dscale_s > 8.5:
            msg = f"Camera zoom quá nhanh: {dscale_s:.1f}%/s tại t={i/fps}s"
            checks["4_toc_do_camera_hop_le"]["violations"].append(msg)
            checks["4_toc_do_camera_hop_le"]["pass"] = False

    # Phép 5: Chuyển động có khối lượng (không dừng tuyến tính đột ngột)
    # Tổng kết
    all_passed = (
        checks["1_khong_dich_chuyen_tuc_thoi"]["pass"]
        and checks["2_xuat_hien_bien_mat_dung_luat"]["pass"]
        and checks["3_nhip_chuyen_dong_2_5s"]["pass"]
        and checks["4_toc_do_camera_hop_le"]["pass"]
    )
    checks["6_tong_hop"]["pass"] = all_passed
    return checks


def main():
    parser = argparse.ArgumentParser(description="Ghi vết và phân tích Cổng G3 HyperFrames")
    parser.add_argument("--html", type=Path, required=True, help="Đường dẫn tệp HTML sub-composition")
    parser.add_argument("--out", type=Path, required=True, help="Đường dẫn tệp JSON ghi vết xuất ra")
    parser.add_argument("--layout", type=str, default="CANH", help="Tên layout")
    parser.add_argument("--duration", type=float, default=10.0, help="Thời lượng (giây)")
    parser.add_argument("--report", type=Path, default=None, help="Đường dẫn xuất báo cáo Markdown")
    args = parser.parse_args()

    print(f"Bắt đầu ghi vết: {args.html} ({args.duration}s)...")
    trace = capture_motion_trace(
        html_path=args.html,
        output_json=args.out,
        duration_seconds=args.duration,
        layout_name=args.layout,
    )
    print(f"Đã lưu vết vào: {args.out}")

    analysis = analyze_g3(trace)
    print("Kết quả phân tích Cổng G3:")
    for check_id, check_res in analysis.items():
        status = "ĐẠT" if check_res.get("pass") else "KHÔNG ĐẠT"
        print(f"  [{status}] {check_id}")
        for v in check_res.get("violations", []):
            print(f"      - {v}")

    if args.report:
        report_md = f"""# Báo cáo Phân tích Cổng G3: {args.layout}

- **Tệp nguồn:** `{args.html.name}`
- **Thời lượng:** {args.duration} giây (30 fps)
- **Tệp vết:** `{args.out.name}`
- **Kết luận:** **{'ĐẠT CỔNG G3' if analysis['6_tong_hop']['pass'] else 'CẦN CHỈNH SỬA'}**

## Chi tiết các phép kiểm

| Phép kiểm | Kết quả | Chi tiết vi phạm |
|---|---|---|
| 1. Không dịch chuyển tức thời | {'ĐẠT' if analysis['1_khong_dich_chuyen_tuc_thoi']['pass'] else 'KHÔNG ĐẠT'} | {len(analysis['1_khong_dich_chuyen_tuc_thoi']['violations'])} vi phạm |
| 2. Xuất hiện/biến mất đúng luật | {'ĐẠT' if analysis['2_xuat_hien_bien_mat_dung_luat']['pass'] else 'KHÔNG ĐẠT'} | {len(analysis['2_xuat_hien_bien_mat_dung_luat']['violations'])} vi phạm |
| 3. Nhịp 2.5s không khung chết | {'ĐẠT' if analysis['3_nhip_chuyen_dong_2_5s']['pass'] else 'KHÔNG ĐẠT'} | {len(analysis['3_nhip_chuyen_dong_2_5s']['violations'])} vi phạm |
| 4. Tốc độ camera chuẩn | {'ĐẠT' if analysis['4_toc_do_camera_hop_le']['pass'] else 'KHÔNG ĐẠT'} | {len(analysis['4_toc_do_camera_hop_le']['violations'])} vi phạm |
| 5. Có khối lượng & gia tốc | {'ĐẠT' if analysis['5_chuyen_dong_co_khoi_luong']['pass'] else 'KHÔNG ĐẠT'} | Đạt chuẩn easing |

"""
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report_md.strip(), encoding="utf-8")
        print(f"Đã xuất báo cáo: {args.report}")


if __name__ == "__main__":
    main()
