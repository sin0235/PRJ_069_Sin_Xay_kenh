import pytest

from src.modules.tao_video_noi_dung.contracts import StyleSnapshot
from src.modules.tao_video_noi_dung import service


def test_snapshot_cu_giu_nguyen_cau_truc_va_hash(monkeypatch):
    monkeypatch.delenv("CONTENT_VIDEO_REMOTION_NATIVE", raising=False)
    original = service._CONTENT_VIDEO_STYLE_SNAPSHOT.model_dump(mode="json")
    assert service._plan_style_snapshot("9:16") == original
    assert "remotion_native" not in original
    assert "render_engine" not in original
    assert StyleSnapshot.model_validate(original).model_dump(mode="json") == original


def test_plan_moi_ghi_day_du_lua_chon_native(monkeypatch):
    monkeypatch.setenv("CONTENT_VIDEO_REMOTION_NATIVE", "1")
    style = service._plan_style_snapshot("16:9")
    assert style["aspect_ratio"] == "16:9"
    assert style["render_engine"] == "remotion"
    assert style["remotion_native"] is True
    assert style["assembly"] == "hyperframes"
    assert StyleSnapshot.model_validate(style).model_dump(mode="json") == style
    monkeypatch.delenv("CONTENT_VIDEO_REMOTION_NATIVE")
    assert service._plan_style_snapshot("16:9").get("remotion_native") is None


def test_snapshot_van_chan_truong_la():
    raw = service._CONTENT_VIDEO_STYLE_SNAPSHOT.model_dump(mode="json")
    with pytest.raises(ValueError):
        StyleSnapshot.model_validate({**raw, "ma_tuy_y": "khong duoc phep"})
