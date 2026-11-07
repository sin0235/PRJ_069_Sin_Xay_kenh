from src.modules.tao_video_noi_dung.brand import display_json
from src.modules.tao_video_noi_dung.hf_scenes import NATIVE
from src.modules.tao_video_noi_dung.render_engines import assembly_mode


def test_baha_editorial_motion_uses_hyperframes_by_default(monkeypatch):
    monkeypatch.delenv("CONTENT_VIDEO_ASSEMBLY", raising=False)

    assert assembly_mode({"style_name": "BAHA Editorial Motion B2B v1"}) == "hyperframes"
    assert assembly_mode({"style_name": "Bản dựng cổ điển"}) == "classic"
    assert assembly_mode({"style_name": "BAHA Editorial Motion B2B v1", "assembly": "classic"}) == "classic"


def test_hyperframes_scaffold_giu_tieng_viet():
    scene = display_json({
        "kind": "CHECKLIST",
        "title": "Kiểm tra tiếng Việt",
        "steps": ["Ghi nhận kết quả"],
        "stamp": "SẴN SÀNG",
    })
    html = NATIVE["CHECKLIST"]("probe", scene, 0, 5, {})

    assert "Ghi nhận kết quả" in html
    assert "SẴN SÀNG" in html
    assert "S?N S?NG" not in html