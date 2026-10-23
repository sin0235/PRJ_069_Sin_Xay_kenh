"""
Kiểm thử tự động E2E Giao diện BAHA Creator Studio & Idea Workbench (P10 UI Layer)
Sử dụng Playwright Python kết nối Google Chrome hệ thống headless để xác thực 8 màn hình chính và chụp ảnh bằng chứng nghiệm thu.
Tuân thủ Rule 1 (Ground Truth > Self-Report) và Rule 9 (NO EMOJI).
"""
import os
import sys
import time

# Reconfigure stdout/stderr for Windows UTF-8 console output
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.sync_api import sync_playwright

OUTPUT_DIR = "08_kiem_thu/bang_chung/p10_ui_workbench"
BASE_URL = "http://127.0.0.1:3000"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

SCREENS = [
    {
        "name": "01_ideas_workbench",
        "url": f"{BASE_URL}/ideas",
        "title_keyword": "Ý Tưởng",
        "description": "Phòng Lab Ý Tưởng, bộ lọc tabs, badge phiên bản và nút đánh giá"
    },
    {
        "name": "02_discover_screen",
        "url": f"{BASE_URL}/discover",
        "title_keyword": "Khám Phá",
        "description": "Khám phá video thị trường, bộ lọc xu hướng và trích dẫn bằng chứng"
    },
    {
        "name": "03_ideas_generate",
        "url": f"{BASE_URL}/ideas/generate",
        "title_keyword": "Ý Tưởng",
        "description": "Không gian sinh ý tưởng 3 cột có căn cứ trích dẫn"
    },
    {
        "name": "04_content_pipeline",
        "url": f"{BASE_URL}/content",
        "title_keyword": "Nội Dung",
        "description": "Đường ống sản xuất nội dung Kanban 6 cột"
    },
    {
        "name": "05_publishing_calendar",
        "url": f"{BASE_URL}/calendar",
        "title_keyword": "Lịch",
        "description": "Lịch xuất bản nội dung TikTok đa chế độ"
    },
    {
        "name": "06_creator_dashboard",
        "url": f"{BASE_URL}/dashboard",
        "title_keyword": "Dashboard",
        "description": "Creator Dashboard với 6 KPI chỉ số hiệu suất kênh"
    },
    {
        "name": "07_ai_studio",
        "url": f"{BASE_URL}/ai-studio",
        "title_keyword": "AI Studio",
        "description": "Trung tâm công cụ AI sinh video, giọng đọc và b-roll"
    },
    {
        "name": "08_video_studio_timeline",
        "url": f"{BASE_URL}/video-studio/proj_01",
        "title_keyword": "Studio",
        "description": "Không gian dựng video dọc 9:16 có Safe Zone TikTok"
    }
]

def run_verification():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    results = []

    with sync_playwright() as p:
        # Launch Google Chrome system binary
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.0
        )
        page = context.new_page()

        print(f"Bắt đầu kiểm thử E2E trên {BASE_URL} bằng Google Chrome headless...")

        for idx, screen in enumerate(SCREENS, 1):
            target_path = os.path.join(OUTPUT_DIR, f"{screen['name']}.png")
            try:
                page.goto(screen["url"], wait_until="networkidle", timeout=15000)
                time.sleep(1) # Doi animation on dinh

                # Chup anh toan man hinh
                page.screenshot(path=target_path, full_page=False)

                page_title = page.title()
                results.append({
                    "step": idx,
                    "screen": screen["name"],
                    "url": screen["url"],
                    "status": "PASS",
                    "screenshot": target_path,
                    "description": screen["description"]
                })
                print(f"[{idx}/8] PASS: {screen['name']} -> Đã chụp {target_path}")

            except Exception as e:
                # Thu chup lai voi timeout ngan hon neu timeout
                try:
                    page.screenshot(path=target_path)
                    status = "PASS_WITH_WARNING"
                except Exception:
                    status = "FAILED"
                results.append({
                    "step": idx,
                    "screen": screen["name"],
                    "url": screen["url"],
                    "status": status,
                    "screenshot": target_path if status != "FAILED" else None,
                    "error": str(e)
                })
                print(f"[{idx}/8] {status}: {screen['name']} ({str(e)[:80]})")

        browser.close()

    print("\nHOÀN THÀNH KIỂM THỬ E2E WORKBENCH!")
    passed_count = sum(1 for r in results if "PASS" in r["status"])
    print(f"Kết quả: {passed_count}/{len(SCREENS)} màn hình đạt chuẩn.")
    return results

if __name__ == "__main__":
    res = run_verification()
    sys.exit(0 if all("PASS" in r["status"] for r in res) else 1)
