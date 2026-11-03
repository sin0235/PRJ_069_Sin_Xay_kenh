import pathlib
import subprocess
import sys
import importlib.util

import pytest


API_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT_ROOT = API_ROOT.parent
WATERMARK_TOOL = PROJECT_ROOT / "cong_cu_tu_dong" / "veo_watermark_remover" / "GeminiWatermarkTool-Video.exe"


def test_remover_uses_verified_runner_executable(tmp_path, monkeypatch):
    executable = tmp_path / "GeminiWatermarkTool-Video"
    executable.write_bytes(b"kiem tra duong dan")
    monkeypatch.setenv("PRJ069_VEO_REMOVER_PATH", str(executable))
    spec = importlib.util.spec_from_file_location("remover_kiem_thu", WATERMARK_TOOL.with_name("remover_service.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_EXECUTABLE_PATH == executable
    assert module.VeoWatermarkRemover().exe_path == executable


@pytest.mark.skipif(WATERMARK_TOOL.exists(), reason="Watermark executable is installed")
def test_video_processor_imports_when_optional_windows_tool_is_missing():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {str(API_ROOT)!r}); import src.modules.media_studio.video_processor as processor; assert processor.veo_remover is None",
        ],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
