import pathlib
import subprocess
import sys

import pytest


API_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT_ROOT = API_ROOT.parent
WATERMARK_TOOL = PROJECT_ROOT / "cong_cu_tu_dong" / "veo_watermark_remover" / "GeminiWatermarkTool-Video.exe"


@pytest.mark.skipif(WATERMARK_TOOL.exists(), reason="Watermark executable is installed")
def test_video_processor_imports_when_optional_windows_tool_is_missing():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import src.modules.media_studio.video_processor as processor; assert processor.veo_remover is None",
        ],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
