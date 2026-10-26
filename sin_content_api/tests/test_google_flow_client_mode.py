import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cong_cu_tu_dong" / "flow_bridge"))

from google_flow_client import _new_flow_video_tile_index


def test_only_a_new_flow_tile_is_selected():
    existing = ["thumb-a", "thumb-b"]
    assert _new_flow_video_tile_index(existing, ["thumb-a", "thumb-b"]) is None
    assert _new_flow_video_tile_index(existing, ["thumb-a", "thumb-b", "thumb-c"]) == 2
