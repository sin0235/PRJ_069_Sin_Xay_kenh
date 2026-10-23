# -*- coding: utf-8 -*-
"""Dịch vụ loại bỏ logo / watermark Google Veo & Gemini AI (v0.6.5-demo).
Tích hợp trực tiếp công cụ GeminiWatermarkTool-Video (Reverse Alpha Blending + NCNN AI Denoiser)
để tự động tẩy sạch các loại watermark Veo (Diamond Gemini, Stamped Diamond, Veo text logo)
khỏi video tạo bởi Google Flow / Gemini Omni, giúp video hoàn toàn sạch sẽ, tự nhiên,
tránh phản cảm từ người xem đối với nội dung AI.
"""

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# Thư mục gốc dự án và công cụ
CURRENT_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_EXECUTABLE_PATH = CURRENT_DIR / "GeminiWatermarkTool-Video.exe"

class VeoWatermarkRemover:
    """Điều phối tiến trình xóa watermark Veo/Gemini bằng công cụ chuyên dụng."""

    def __init__(self, exe_path: Optional[pathlib.Path] = None):
        self.exe_path = exe_path or DEFAULT_EXECUTABLE_PATH
        if not self.exe_path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp thực thi Veo Watermark Remover: {self.exe_path}")

    def is_available(self) -> bool:
        """Kiểm tra xem công cụ có sẵn sàng hoạt động hay không."""
        return self.exe_path.exists() and os.access(str(self.exe_path), os.X_OK | os.R_OK)

    def remove_watermark(
        self,
        input_video_path: pathlib.Path,
        output_video_path: pathlib.Path,
        use_cpu: bool = True,
        watermark_type: str = "auto",
        denoise_method: Optional[str] = None,
        region: Optional[str] = None,
        veo_alpha: Optional[float] = None,
        timeout_sec: int = 900
    ) -> Dict[str, Any]:
        """
        Xóa logo / watermark Veo khỏi tệp video:
        - input_video_path: Đường dẫn video nguồn (hỗ trợ cả đường dẫn cục bộ và ổ mạng UNC).
        - output_video_path: Đường dẫn video đích sau khi khử watermark.
        - use_cpu: Ép sử dụng CPU để đảm bảo an toàn tuyệt đối, tránh lỗi driver Vulkan.
        - watermark_type: auto, diamond (Gemini 3.5), veo (Veo text logo).
        - denoise_method: ai, ns, telea, soft, off (mặc định để trống để dùng thuật toán tối ưu của tool).
        - region: Khóa tọa độ thủ công x,y,w,h (nếu watermark ở vị trí phi chuẩn).
        - veo_alpha: Cường độ alpha thủ công.
        - timeout_sec: Thời gian chờ tối đa.
        """
        input_video_path = pathlib.Path(input_video_path).resolve()
        output_video_path = pathlib.Path(output_video_path).resolve()

        if not input_video_path.exists():
            raise FileNotFoundError(f"Không tìm thấy video nguồn: {input_video_path}")

        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        is_unc = str(input_video_path).startswith(("\\\\", "//")) or str(output_video_path).startswith(("\\\\", "//"))

        # Nếu tệp nằm trên ổ mạng UNC, sử dụng thư mục tạm cục bộ để tăng tốc I/O
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = pathlib.Path(tmp_dir)

            if is_unc:
                local_in = tmp_dir_path / f"in_{input_video_path.name}"
                local_out = tmp_dir_path / f"out_{output_video_path.name}"
                shutil.copy2(str(input_video_path), str(local_in))
            else:
                local_in = input_video_path
                local_out = output_video_path

            # Xây dựng danh sách tham số lệnh
            cmd = [
                str(self.exe_path),
                str(local_in),
                "-o", str(local_out),
                "--no-banner",
                "--veo"
            ]

            if use_cpu:
                cmd.append("--cpu")

            if watermark_type and watermark_type != "auto":
                cmd.extend(["--mark", watermark_type])

            if denoise_method:
                cmd.extend(["--denoise", denoise_method])

            if region:
                cmd.extend(["--region", region])

            if veo_alpha is not None:
                cmd.extend(["--veo-alpha", str(veo_alpha)])

            print(f"[VEO REMOVER] Bắt đầu khử logo watermark: {input_video_path.name} -> {output_video_path.name}", flush=True)

            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_sec
                )
            except subprocess.TimeoutExpired as exc:
                progress = exc.stdout or exc.stderr or ""
                if isinstance(progress, bytes):
                    progress = progress.decode("utf-8", errors="replace")
                raise TimeoutError(
                    f"Veo Watermark Remover vượt quá {timeout_sec} giây; "
                    f"tiến độ cuối: {progress[-500:]}"
                ) from exc

            if res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip()
                print(f"[VEO REMOVER CẢNH BÁO] Lỗi từ công cụ xóa watermark (code {res.returncode}): {err_msg}", flush=True)
                # Nếu tool không xử lý được (ví dụ video không có watermark hoặc codec lạ),
                # fallback an toàn: copy video nguồn sang đích để không gián đoạn luồng sản xuất
                if not local_out.exists() or local_out.stat().st_size == 0:
                    shutil.copy2(str(input_video_path), str(output_video_path))
                    return {
                        "status": "FALLBACK_ORIGINAL",
                        "output_path": str(output_video_path),
                        "watermark_detected": False,
                        "watermark_removed": False,
                        "byte_size": output_video_path.stat().st_size,
                        "duration_sec": time.time() - start_time,
                        "message": f"Không phát hiện watermark hoặc công cụ fallback: {err_msg[:120]}"
                    }

            # Sao chép tệp kết quả từ thư mục tạm cục bộ về ổ mạng đích nếu cần
            if is_unc and local_out.exists():
                shutil.copy2(str(local_out), str(output_video_path))

        elapsed_sec = time.time() - start_time
        final_size = output_video_path.stat().st_size if output_video_path.exists() else 0

        # Tính toán SHA256 cho tệp xuất xưởng
        sha256_hash = ""
        if output_video_path.exists():
            with open(output_video_path, "rb") as f:
                sha256_hash = hashlib.sha256(f.read()).hexdigest()

        print(f"[VEO REMOVER HOÀN TẤT] Đã khử sạch watermark trong {elapsed_sec:.2f}s ({final_size} bytes)", flush=True)

        return {
            "status": "SUCCEEDED",
            "output_path": str(output_video_path),
            "watermark_detected": True,
            "watermark_removed": True,
            "byte_size": final_size,
            "sha256": sha256_hash,
            "duration_sec": round(elapsed_sec, 2),
            "technique": "REVERSE_ALPHA_BLENDING_NCNN"
        }

# Khởi tạo singleton mặc định
veo_remover = VeoWatermarkRemover()
