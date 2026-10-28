# -*- coding: utf-8 -*-
"""
PRJ_069 - Kiem tra trang thai dich vu tren NAS (192.168.1.175)
Cac cong muc tieu:
  - Frontend Web Studio: 3069
  - Backend API: 8069
  - AI Gateway 9Router: https://api-9router.sin-studio.tech/v1
"""

import sys
import json
import socket
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

NAS_IP = "192.168.1.175"
FE_PORT = 3069
API_PORT = 8069

def kiem_tra_cong(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def kiem_tra_http(url: str, timeout: float = 2.0):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PRJ069-Monitor"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(200).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return None, str(e)

def main():
    print("======================================================================")
    print("KIEM TRA TRANG THAI TRIEN KHAI PRJ_069 TREN NAS (192.168.1.175)")
    print("======================================================================\n")

    fe_open = kiem_tra_cong(NAS_IP, FE_PORT)
    api_open = kiem_tra_cong(NAS_IP, API_PORT)
    st, st_h = None, None

    print(f"1. Cong Frontend Web Studio ({FE_PORT}): {'[DANG MO]' if fe_open else '[CHUA MO / STOPPED]'}")
    if fe_open:
        st, body = kiem_tra_http(f"http://{NAS_IP}:{FE_PORT}", timeout=15.0)
        print(f"   -> HTTP Response: {st}")
    else:
        print(f"   -> Dia chi truy cap: http://{NAS_IP}:{FE_PORT}")

    print(f"\n2. Cong Backend API ({API_PORT}): {'[DANG MO]' if api_open else '[CHUA MO / STOPPED]'}")
    if api_open:
        st_h, _ = kiem_tra_http(f"http://{NAS_IP}:{API_PORT}/healthz", timeout=15.0)
        st_r, _ = kiem_tra_http(f"http://{NAS_IP}:{API_PORT}/readyz", timeout=15.0)
        print(f"   -> /healthz: {st_h} | /readyz: {st_r}")
        print(f"   -> Swagger Docs: http://{NAS_IP}:{API_PORT}/docs")
    else:
        print(f"   -> Dia chi API: http://{NAS_IP}:{API_PORT}/docs")

    print("\n----------------------------------------------------------------------")
    # Chi bao thanh cong khi API tra loi HTTP 200; cong TCP mo chua chung minh dich vu con song.
    api_ok = api_open and st_h == 200
    fe_ok = fe_open and st is not None and st < 500
    if fe_ok and api_ok:
        print("[KET QUA] FE va API tra loi dung (healthz 200). Chay kiem_tra_sau_trien_khai.py de kiem tra dang nhap va DB.")
    elif fe_open and api_open:
        print("[KET QUA] Cong da mo nhung dich vu KHONG tra loi dung (API healthz: %s, FE: %s). Xem log container trong DSM." % (st_h, st))
    else:
        print("[TRANG THAI] Cong FE/API chua mo: du an chua chay hoac da dung.")
        print("Trien khai du an moi: xem ha_tang/nas_trien_khai_sach/huong_dan_trien_khai.md (project prj069_v2).")
    print("======================================================================")

if __name__ == "__main__":
    main()
