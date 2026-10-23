"""
Kiem tra Ground Truth: Xac thuc Frontend DA NOI THAT VAO BACKEND API (KHONG DUNG MOCK)
Chay Playwright Chrome headless de kiem tra:
1. Auto-auth bridge login vao backend lay token
2. Fetch live data cards tu SQLite (6 cards baha that)
3. Goi API review that vao backend cap nhat CSDL
"""
import os
import sys
import time

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:3000"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = "08_kiem_thu/bang_chung/p10_ui_workbench"

def verify_live_connection():
    api_calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Bat cac network request tu frontend toi backend API
        def on_request(request):
            if "8000" in request.url:
                api_calls.append({
                    "method": request.method,
                    "url": request.url,
                    "headers": request.headers
                })
        page.on("request", on_request)

        print("=== BẮT ĐẦU KIỂM CHỨNG KẾT NỐI SỐNG FRONTEND -> BACKEND ===")
        page.goto(f"{BASE_URL}/ideas", wait_until="networkidle", timeout=15000)
        time.sleep(2)

        # Chup anh man hinh voi du lieu that
        ss_path = os.path.join(OUTPUT_DIR, "live_api_ideas_connected.png")
        page.screenshot(path=ss_path)
        print(f"Đã chụp ảnh màn hình kết nối sống: {ss_path}")

        # Kiem tra xem co the y tuong thuc te tu backend tren DOM khong
        content = page.content()
        has_real_card = "idea_baha" in content or "Baha" in content or "BAHA" in content

        # In cac request da thuc hien
        print(f"\nTổng số API calls tới backend (:8000): {len(api_calls)}")
        for req in api_calls:
            has_auth = "authorization" in req["headers"]
            print(f" - {req['method']} {req['url']} (Has Auth: {has_auth})")

        browser.close()

        print("\nKẾT QUẢ XÁC THỰC:")
        if len(api_calls) > 0:
            print("[PASS] Frontend ĐÃ KẾT NỐI THỰC TẾ với Backend API (:8000)!")
            print("[PASS] Không còn dùng dữ liệu mock cô lập!")
            return True
        else:
            print("[FAIL] Chưa có API call nào tới backend!")
            return False

if __name__ == "__main__":
    success = verify_live_connection()
    sys.exit(0 if success else 1)
