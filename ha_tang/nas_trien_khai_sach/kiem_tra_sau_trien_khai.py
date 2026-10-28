"""Kiểm tra sau triển khai PRJ_069 v2: chỉ báo thành công khi từng bước trả đúng kết quả thật.

Dùng: python kiem_tra_sau_trien_khai.py --api http://192.168.1.175:8069 --web http://192.168.1.175:3069
Mật khẩu Founder lấy từ biến PRJ069_MAT_KHAU hoặc hỏi tại chỗ. Thoát mã 0 nếu mọi bước đạt, mã 1 nếu có bước lỗi.
"""

import argparse
import getpass
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

EMAIL_FOUNDER = "phuctoan235@gmail.com"
WORKSPACE_ID = "b6102190-1f6f-5624-bfb8-2e1091fa2560"
ket_qua: list[tuple[str, bool, str]] = []


def yeu_cau(opener, phuong_thuc, url, du_lieu=None, tieu_de=None, han=20):
    """Trả (mã HTTP, nội dung JSON hoặc chữ, giây). Mã 0 nghĩa là không kết nối/hết hạn."""
    tieu_de = {"Content-Type": "application/json", **(tieu_de or {})}
    goi = urllib.request.Request(
        url, method=phuong_thuc, headers=tieu_de,
        data=json.dumps(du_lieu).encode("utf-8") if du_lieu is not None else None,
    )
    bat_dau = time.monotonic()
    try:
        with opener.open(goi, timeout=han) as phan_hoi:
            ma, noi_dung = phan_hoi.status, phan_hoi.read()
    except urllib.error.HTTPError as loi:
        ma, noi_dung = loi.code, loi.read()
    except Exception as loi:
        return 0, str(loi), time.monotonic() - bat_dau
    try:
        noi_dung = json.loads(noi_dung)
    except ValueError:
        noi_dung = noi_dung[:200].decode("utf-8", "replace")
    return ma, noi_dung, time.monotonic() - bat_dau


def buoc(ten, dat, chi_tiet=""):
    ket_qua.append((ten, dat, chi_tiet))
    print(f"[{'DAT' if dat else 'LOI'}] {ten}" + (f" - {chi_tiet}" if chi_tiet else ""), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://192.168.1.175:8069")
    parser.add_argument("--web", default="http://192.168.1.175:3069", help="Để rỗng để bỏ qua kiểm tra giao diện.")
    tham_so = parser.parse_args()
    api, web = tham_so.api.rstrip("/"), tham_so.web.rstrip("/")
    mat_khau = os.environ.get("PRJ069_MAT_KHAU") or getpass.getpass("Mật khẩu Founder: ")

    khong_cookie = urllib.request.build_opener()
    dang_nhap = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    tieu_de_ws = {"X-Workspace-Id": WORKSPACE_ID}

    ma, nd, giay = yeu_cau(khong_cookie, "GET", f"{api}/healthz", han=30)
    buoc("API /healthz", ma == 200, f"HTTP {ma} sau {giay:.1f}s")
    if ma != 200:
        print("API không phản hồi; dừng. Xem log container prj069-v2-api trong Container Manager.")
        return 1
    ma, nd, _ = yeu_cau(khong_cookie, "GET", f"{api}/readyz")
    buoc("API /readyz (content DB)", ma == 200 and nd.get("database_connected") is True, f"HTTP {ma}")
    buoc("Môi trường là production", yeu_cau(khong_cookie, "GET", f"{api}/healthz")[1].get("environment") == "production")

    ma, _, _ = yeu_cau(khong_cookie, "GET", f"{api}/v1/auth/me")
    buoc("Chưa đăng nhập thì /v1/auth/me bị từ chối (bypass đã tắt)", ma == 401, f"HTTP {ma}")
    ma, _, _ = yeu_cau(khong_cookie, "POST", f"{api}/v1/auth/login", {"email": EMAIL_FOUNDER, "password": "mat-khau-sai-0123456"})
    buoc("Sai mật khẩu bị từ chối", ma == 401, f"HTTP {ma}")
    ma, _, _ = yeu_cau(khong_cookie, "POST", f"{api}/v1/auth/login", {"email": EMAIL_FOUNDER, "password": "BahaGroup@2026"})
    buoc("Mật khẩu dự phòng cũ không còn hiệu lực", ma == 401, f"HTTP {ma}")

    ma, nd, _ = yeu_cau(dang_nhap, "POST", f"{api}/v1/auth/login", {"email": EMAIL_FOUNDER, "password": mat_khau})
    buoc("Đăng nhập Founder", ma == 200, f"HTTP {ma}" + ("" if ma == 200 else f" {nd}"))
    if ma == 200:
        ma, nd, _ = yeu_cau(dang_nhap, "GET", f"{api}/v1/auth/me")
        dat = ma == 200 and isinstance(nd, dict) and nd.get("workspace", {}).get("id") == WORKSPACE_ID
        buoc("Đọc Auth DB: /v1/auth/me trả đúng workspace", dat, f"HTTP {ma} vai trò {nd.get('workspace', {}).get('role') if isinstance(nd, dict) else nd}")
        for ten, duong_dan in (("TTS: cài đặt", "/v1/voice-studio/settings"), ("TTS: thư viện giọng", "/v1/voice-studio/voices"),
                               ("TTS: lịch sử tác vụ", "/v1/voice-studio/jobs")):
            ma, nd, giay = yeu_cau(dang_nhap, "GET", f"{api}{duong_dan}", tieu_de=tieu_de_ws)
            buoc(ten, ma == 200, f"HTTP {ma} sau {giay:.1f}s")

    if web:
        ma, _, giay = yeu_cau(khong_cookie, "GET", f"{web}/auth/v1/login", han=60)
        buoc("Giao diện: trang đăng nhập", ma == 200, f"HTTP {ma} sau {giay:.1f}s")
        ma, _, _ = yeu_cau(khong_cookie, "GET", f"{web}/v1/auth/me")
        buoc("Giao diện chuyển tiếp /v1/* tới API (nhận 401 từ API)", ma == 401, f"HTTP {ma}")

    loi = [ten for ten, dat, _ in ket_qua if not dat]
    print(f"\nTổng: {len(ket_qua) - len(loi)}/{len(ket_qua)} bước đạt." + (f" Lỗi: {'; '.join(loi)}" if loi else ""))
    print("Chưa kiểm tra bằng script này: nghe âm thanh TTS thật và phiên Google Flow (xem huong_dan_trien_khai.md).")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
