"""Tệp checkpoint giọng đọc phải đủ ngắn để đường dẫn đầy đủ dưới 260 ký tự của Windows."""
import hashlib
import re
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "src/modules/tao_video_noi_dung/runner.py"


def test_tts_checkpoint_names_are_short():
    text = RUNNER.read_text(encoding="utf-8")
    assert 'hexdigest()[:32]' in text and 'path.with_suffix(f".{token[:8]}.tmp")' in text


def test_worst_case_full_path_stays_under_windows_limit():
    root = r"C:\Users\Baha Group\Documents\PRJ_069_Sin_Xay_kenh_git_push_wt_auto_edit_ui\ha_tang\chay_dev_local\data\media_assets"
    token = "ba6ee154-ab31-4d0e-b4eb-8a90744f4ac4"
    key = hashlib.sha256(b"x").hexdigest()[:32]
    temp = rf"{root}\workspaces\9fd7c928-7ac4-4d95-8b71-60b8653fe5f3\media\.tts\{key}_{token[:8]}.{token[:8]}.tmp"
    assert len(temp) < 250
