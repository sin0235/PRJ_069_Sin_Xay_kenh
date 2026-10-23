# -*- coding: utf-8 -*-
import os
import pathlib
import subprocess
import time

def ensure_profile_free(profile_dir: pathlib.Path):
    try:
        ps_cmd = "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe'\" | ForEach-Object { if ($_.CommandLine -like '*BahaFlowBridge*' -or $_.CommandLine -like '*browser_profile*') { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }"
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=10)
    except Exception:
        pass

    lock_names = ["lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"]
    for lock_name in lock_names:
        lf = profile_dir / lock_name
        for _ in range(3):
            if lf.exists():
                try:
                    lf.unlink()
                    break
                except Exception:
                    time.sleep(0.3)
            else:
                break
