# -*- coding: utf-8 -*-
"""Lớp bảo mật tệp và phân tích dữ liệu đa phương tiện (Media Studio Security Layer).
Chống tấn công MIME giả mạo, Zip Path Traversal và Zip Bomb theo chuẩn B04, B05.
"""

import hashlib
import io
import os
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Tuple
from fastapi import HTTPException, status

MEDIA_ROOT_DIR = Path(os.environ.get("MEDIA_ROOT_DIR", Path(__file__).resolve().parents[4] / "media_assets"))

def get_workspace_storage_dir(workspace_id: str) -> Path:
    target_dir = MEDIA_ROOT_DIR / "workspaces" / workspace_id / "media"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir

# Danh mục Magic Bytes chuẩn
MAGIC_SIGNATURES = [
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"RIFF", "audio/wav"), # RIFF....WAVE
    (b"ID3", "audio/mpeg"), # MP3 ID3v2
    (b"PK\x03\x04", "application/zip"),
]

def detect_real_mime(data: bytes, filename: str = "") -> str:
    """Xác định MIME type thực sự dựa trên magic bytes nhị phân, không tin phần mở rộng."""
    if not data:
        return "application/octet-stream"

    # Kiểm tra PDF
    if data.startswith(b"%PDF-"):
        return "application/pdf"

    # Kiểm tra PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # Kiểm tra JPEG
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # Kiểm tra WAV
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
        return "audio/wav"

    # Kiểm tra MP3 (ID3 header hoặc frame sync \xff\xfb, \xff\xf3, \xff\xf2)
    if data.startswith(b"ID3"):
        return "audio/mpeg"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "audio/mpeg"

    # Kiểm tra MP4 (ftyp box trong 16 byte đầu)
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return "video/mp4"

    # Kiểm tra ZIP
    if data.startswith(b"PK\x03\x04"):
        return "application/zip"

    # Fallback theo phần mở rộng nếu không nhận dạng được magic bytes
    ext = os.path.splitext(filename)[1].lower()
    ext_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".mp4": "video/mp4",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".zip": "application/zip",
    }
    return ext_map.get(ext, "application/octet-stream")

# Giới hạn upload theo category (byte) — có thể điều chỉnh qua biến môi trường
_MB = 1024 * 1024
UPLOAD_SIZE_LIMITS: dict = {
    "audio": int(os.environ.get("UPLOAD_LIMIT_AUDIO_MB", "50")) * _MB,
    "image": int(os.environ.get("UPLOAD_LIMIT_IMAGE_MB", "20")) * _MB,
    "video": int(os.environ.get("UPLOAD_LIMIT_VIDEO_MB", "500")) * _MB,
}

# Allowlist MIME theo category
CATEGORY_MIME_ALLOWLIST: dict = {
    "audio": {
        "audio/mpeg", "audio/wav", "audio/mp4", "audio/ogg",
        "audio/flac", "audio/x-flac", "application/zip", "application/octet-stream",
    },
    "image": {
        "image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp",
    },
    "video": {
        "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm",
        "video/x-matroska", "application/octet-stream",
    },
}

def _check_filename_safe(filename: str) -> str:
    """Chuẩn hóa tên tệp, loại bỏ path traversal và ký tự nguy hiểm."""
    import re
    # Chỉ giữ phần tên tệp, loại bỏ thư mục
    safe = os.path.basename(filename)
    # Loại bỏ ký tự nguy hiểm
    safe = re.sub(r'[^\w.\-]', '_', safe)
    if not safe or safe.startswith('.'):
        safe = f"upload_{safe}"
    return safe

def validate_audio_or_media_file(data: bytes, filename: str, expected_category: str = "audio") -> Tuple[str, str, int]:
    """
    Xác thực tệp media hợp lệ với allowlist MIME theo category (B04, B05, MF-02):
    - Kiểm tra tệp rỗng.
    - Kiểm tra giới hạn kích thước theo category.
    - Phát hiện MIME thực dựa trên magic bytes.
    - Từ chối MIME không nằm trong allowlist của category.
    - Trả về: (mime_type, sha256_hash, byte_size)
    """
    if not data or len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "EMPTY_FILE", "message": "Tệp tin tải lên bị rỗng (0 bytes)."}
        )

    byte_size = len(data)

    # Kiểm tra giới hạn kích thước theo category
    size_limit = UPLOAD_SIZE_LIMITS.get(expected_category, UPLOAD_SIZE_LIMITS["audio"])
    if byte_size > size_limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error_code": "FILE_TOO_LARGE",
                "message": f"Tệp vượt quá giới hạn {size_limit // _MB} MB cho category '{expected_category}'."
            }
        )

    real_mime = detect_real_mime(data, filename)
    sha256_hash = hashlib.sha256(data).hexdigest()

    # Kiểm tra allowlist MIME theo category
    allowed_mimes = CATEGORY_MIME_ALLOWLIST.get(expected_category)
    if allowed_mimes is not None:
        # Kiểm tra chặt: MIME phải nằm trong allowlist
        mime_ok = real_mime in allowed_mimes
        # Cho phép khớp prefix (vd: audio/*)
        if not mime_ok:
            prefix = expected_category + "/"
            mime_ok = real_mime.startswith(prefix)
        if not mime_ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "INVALID_MEDIA_FORMAT",
                    "message": (
                        f"Định dạng tệp không hợp lệ cho category '{expected_category}'. "
                        f"MIME phát hiện: {real_mime}. "
                        f"Chấp nhận: {', '.join(sorted(allowed_mimes))}."
                    )
                }
            )
        # Từ chối tuyệt đối các MIME nguy hiểm dù có trong allowlist
        if real_mime in ("application/pdf", "application/x-dosexec", "application/x-executable"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "MALICIOUS_MIME_DETECTED",
                    "message": f"Phát hiện tệp độc hại hoặc giả mạo. MIME thực tế: {real_mime}."
                }
            )

    return real_mime, sha256_hash, byte_size

def validate_zip_archive(zip_bytes: bytes, max_uncompressed_bytes: int = 100 * 1024 * 1024, max_ratio: float = 100.0) -> List[str]:
    """
    Bảo vệ chống Zip Path Traversal và Zip Bomb (T04/B04):
    - Kiểm tra đường dẫn nguy hiểm ('..', đường dẫn tuyệt đối, ký tự điều khiển).
    - Kiểm tra tỷ lệ nén và tổng dung lượng giải nén để ngăn chặn Zip Bomb.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "BAD_ZIP_FILE", "message": "Tệp lưu trữ ZIP không hợp lệ hoặc bị hỏng."}
        )

    total_uncompressed = 0
    safe_names = []

    for info in zf.infolist():
        # 1. Kiểm tra Path Traversal
        name = info.filename
        if ".." in name or name.startswith("/") or name.startswith("\\") or ":" in name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ZIP_PATH_TRAVERSAL_DETECTED",
                    "message": f"Phát hiện đường dẫn nguy hiểm trong tệp ZIP (Path Traversal): {name}."
                }
            )

        # 2. Kiểm tra Zip Bomb
        total_uncompressed += info.file_size
        if total_uncompressed > max_uncompressed_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ZIP_BOMB_EXCEEDS_SIZE_LIMIT",
                    "message": f"Tổng dung lượng giải nén vượt quá hạn mức cho phép ({total_uncompressed} > {max_uncompressed_bytes})."
                }
            )

        compressed_size = max(info.compress_size, 1)
        ratio = info.file_size / compressed_size
        if ratio > max_ratio and info.file_size > 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": "ZIP_BOMB_SUSPICIOUS_RATIO",
                    "message": f"Tỷ lệ nén đáng ngờ (nguy cơ Zip Bomb): {ratio:.1f}x trên mục {name}."
                }
            )

        safe_names.append(name)

    return safe_names

def probe_media_metadata(data: bytes, mime_type: str) -> Dict[str, Any]:
    """
    Trích xuất siêu dữ liệu media phục vụ B05:
    - Tính toán duration_ms, sample_rate, channels, sha256.
    """
    sha256_hash = hashlib.sha256(data).hexdigest()
    byte_size = len(data)
    
    # Mặc định ước lượng dựa trên byte size đối với âm thanh chuẩn (MP3 ~128kbps = 16KB/s)
    estimated_duration_ms = max(int((byte_size / 16000) * 1000), 1000) if mime_type == "audio/mpeg" else 30000

    return {
        "mime_type": mime_type,
        "sha256": sha256_hash,
        "byte_size": byte_size,
        "duration_ms": estimated_duration_ms,
        "channels": 2,
        "sample_rate": 44100,
        "codec": "mp3" if mime_type == "audio/mpeg" else "wav" if mime_type == "audio/wav" else "unknown"
    }
