"""Công cụ quét danh mục HyperFrames và tạo chỉ mục blocks/index.json tất định."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Xác định đường dẫn gốc kho mã nguồn
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Thêm sin_content_api vào sys.path để import hf_catalog
SIN_CONTENT_API_DIR = REPO_ROOT / "sin_content_api"
if str(SIN_CONTENT_API_DIR) not in sys.path:
    sys.path.insert(0, str(SIN_CONTENT_API_DIR))

from src.modules.tao_video_noi_dung.hf_catalog import build_index  # noqa: E402

DEFAULT_CLI_PATH = (
    REPO_ROOT
    / "sin_content_api"
    / "engines"
    / "hyperframes"
    / "node_modules"
    / "hyperframes"
    / "bin"
    / "hyperframes.mjs"
)
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "sin_content_api"
    / "engines"
    / "hyperframes"
    / "blocks"
    / "index.json"
)


def quet_danh_muc_va_tao_index(
    cli_path: Path | str | None = None,
    output_path: Path | str | None = None,
) -> Path:
    """Chạy lệnh CLI hyperframes catalog --json và ghi tệp index.json."""
    resolved_cli = Path(cli_path) if cli_path is not None else DEFAULT_CLI_PATH
    resolved_output = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH

    if not resolved_cli.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp CLI HyperFrames tại: {resolved_cli}")

    env = {
        **os.environ,
        "HYPERFRAMES_NO_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
    }

    cmd = ["node", str(resolved_cli), "catalog", "--json"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    if proc.returncode != 0:
        error_msg = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"CLI hyperframes catalog thất bại với mã lỗi {proc.returncode}: {error_msg}")

    stdout = proc.stdout
    first_bracket = stdout.find("[")
    if first_bracket == -1:
        raise ValueError(f"Không tìm thấy mảng JSON '[' trong kết quả trả về từ CLI:\n{stdout}")

    raw_items = json.loads(stdout[first_bracket:])
    if not isinstance(raw_items, list):
        raise TypeError(f"Dữ liệu trả về từ CLI không phải danh sách: {type(raw_items)}")

    index_data = build_index(raw_items)

    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    with open(resolved_output, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=1)
        f.write("\n")

    return resolved_output


def main() -> None:
    """Điểm vào chạy trực tiếp từ dòng lệnh."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    out_file = quet_danh_muc_va_tao_index()
    print(f"Đã tạo chỉ mục thành công tại: {out_file}")


if __name__ == "__main__":
    main()
