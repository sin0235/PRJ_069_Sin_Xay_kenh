"""Cảnh dựng từ khối HyperFrames dựng sẵn: hợp đồng dữ liệu, sửa lỗi cơ học, chuẩn bị mã khối và ghép vào dự án (không cần Chrome)."""
import json
import re

import pytest

from src.modules.tao_video_noi_dung import hf_blocks, hf_project, hf_scenes, planner
from src.modules.tao_video_noi_dung.planner import BLOCK_LAYOUTS, DiagramSpec, UiScene

VALID = {
    "KINETIC_TITLE": {"title": "Một nguồn sự thật", "tag": "sự thật"},
    "MARK_PHRASE": {"title": "Mỗi bộ phận giữ một con số khác nhau", "tag": "một con số khác nhau", "caption": "Không ai sai"},
    "WORD_SWAP": {"title": "Báo cáo", "steps": ["chậm", "lệch", "muộn"], "caption": "mỗi tuần"},
    "PILE_UP": {"title": "Chủ shop", "value": "16"},
    "STAT_RING": {"title": "Đơn đúng hạn", "to_value": 86, "caption": "Đơn đúng hạn"},
    "CHART_STORY": {"title": "Doanh thu", "labels": ["Q1", "Q2", "Q3", "Q4"], "series": [{"name": "dt", "values": [12, 28, 45, 64]}], "unit": "%"},
}


def scene(layout, **override):
    return UiScene(layout=layout, diagram=DiagramSpec(**{**VALID[layout], **override}))


@pytest.mark.parametrize("layout", BLOCK_LAYOUTS)
def test_cau_truc_hop_le_va_khong_can_moc_su_kien(layout):
    item = scene(layout)
    assert planner.diagram_required_events(layout, item.diagram) == []
    assert layout in planner.DIAGRAM_LAYOUTS and layout in planner.PORTRAIT_DIAGRAM_LAYOUTS
    assert planner.resolve_diagram_times(item, "lời đọc của shot này", 5) == {}


@pytest.mark.parametrize("layout, override", [
    ("KINETIC_TITLE", {"title": "Một hai ba bốn năm sáu bảy tám"}),
    ("KINETIC_TITLE", {"tag": "không có trong câu"}),
    ("MARK_PHRASE", {"tag": "cụm không nằm trong câu"}),
    ("WORD_SWAP", {"steps": ["chậm", "chậm", "muộn"]}),
    ("WORD_SWAP", {"steps": ["chậm", "lệch"]}),
    ("PILE_UP", {"value": "3"}),
    ("PILE_UP", {"value": "nhiều"}),
    ("STAT_RING", {"to_value": 130}),
    ("CHART_STORY", {"series": [{"name": "dt", "values": [5, 5, 5, 5]}]}),
    ("CHART_STORY", {"labels": ["Q1", "Q2"]}),
])
def test_du_lieu_sai_bi_tu_choi(layout, override):
    with pytest.raises(ValueError, match=f"DIAGRAM_{layout}_FIELDS"):
        scene(layout, **override)


def test_sua_loi_co_hoc_cho_canh_khoi():
    item = {"layout": "MARK_PHRASE", "diagram": {"title": "Mỗi bộ phận giữ một con số khác nhau", "tag": "không có", "on": {"x": "y"}}}
    planner._repair_diagram_data(item, "lời đọc")
    assert item["diagram"]["on"] == {} and item["diagram"]["tag"] == "khác nhau"
    pile = {"layout": "PILE_UP", "diagram": {"title": "Chủ shop", "value": "5 việc", "on": {"a": "b"}}}
    planner._repair_diagram_data(pile, "lời đọc")
    assert pile["diagram"]["value"] == "8" and pile["diagram"]["on"] == {}
    swap = {"layout": "WORD_SWAP", "diagram": {"title": "Báo cáo", "steps": ["chậm", "Chậm", "lệch", "muộn", "rõ", "thừa"]}}
    planner._repair_diagram_data(swap, "lời đọc")
    assert swap["diagram"]["steps"] == ["chậm", "lệch", "muộn", "rõ"]
    UiScene.model_validate({**swap, "diagram": {**swap["diagram"], "on": {}}})


def test_prompt_nhac_den_sau_loai_canh_khoi():
    source = open(planner.__file__, encoding="utf-8").read()
    for layout in BLOCK_LAYOUTS:
        assert source.count(layout) >= 4, layout


def test_moi_bien_the_tro_toi_khoi_co_that_va_khong_con_cdn():
    for layout, variants in hf_blocks.BLOCK_SCENES.items():
        assert variants
        for variant in variants:
            text = hf_blocks.prepare_block(variant.block, "s01", 5)
            assert "cdn.jsdelivr.net" not in text and "fonts.googleapis.com" not in text
            assert variant.block not in text.replace("hyperframes-registry-item", "")
            assert re.search(r'data-composition-id="s01"', text)
            data = dict(VALID[layout])
            assert isinstance(variant.variables(data), dict)


def test_do_dai_that_duoc_ghi_vao_khoi():
    text = hf_blocks.prepare_block("headline-slam", "s02", 6.2)
    assert 'data-duration="6.200"' in text and 'dataset.duration || "6.200"' in text
    assert "3.5" not in re.findall(r'dataset\.duration \|\| "[^"]+"', text)[0]


def test_chu_mau_tieng_anh_duoc_viet_hoa():
    text = hf_blocks.prepare_block("overwhelm-surround", "s03", 5)
    assert "Hộp thư" in text and '"Inbox"' not in text


def test_chon_bien_the_on_dinh_va_theo_do_dai_tieu_de():
    short = {"title": "Một nguồn"}
    assert hf_blocks.pick_variant("KINETIC_TITLE", short) == hf_blocks.pick_variant("KINETIC_TITLE", short)
    long_title = {"title": "Dữ liệu rời rạc gây trễ đơn"}
    assert hf_blocks.pick_variant("KINETIC_TITLE", long_title).max_chars >= len(long_title["title"])


@pytest.mark.parametrize("aspect", ["16:9", "9:16"])
def test_ghep_canh_khoi_vao_du_an(tmp_path, aspect):
    shots, start = [], 0.0
    for layout in BLOCK_LAYOUTS:
        shots.append({"seconds": 5.0, "scene": scene(layout), "events": {}, "narration": "lời đọc", "start_seconds": start})
        start += 5.0
    info = hf_project.build_project(tmp_path / "p", shots, None, None, transitions=False, aspect_ratio=aspect)
    assert info["native_scenes"] == list(BLOCK_LAYOUTS) and info["legacy_scenes"] == []
    index = (tmp_path / "p" / "index.html").read_text(encoding="utf-8")
    width, height = (1080, 1920) if aspect == "9:16" else (1920, 1080)
    assert f'data-width="{width}" data-height="{height}" data-variable-values=' in index
    assert "--brand:#ffd54a" in index and 'font-family:"Viet"' in index
    for number in range(1, len(BLOCK_LAYOUTS) + 1):
        composition = (tmp_path / "p" / "compositions" / f"s{number:02d}.html").read_text(encoding="utf-8")
        assert f'data-composition-id="s{number:02d}"' in composition
    json.loads(re.search(r"data-variable-values='([^']+)'", index).group(1).replace("&#39;", "'").replace("&amp;", "&"))


def test_ban_do_native_co_du_loai_canh_khoi():
    assert all(layout in hf_scenes.NATIVE for layout in BLOCK_LAYOUTS)


def test_chuyen_canh_luan_phien_va_deu_dinh_thoi():
    assert hf_project.BOUNDARY_TRANSITIONS == ("iris", "whip", "flash")
    iris = hf_project.boundary_transition("iris", "#s03", 10.0)
    assert "circle(0% at 50% 50%)" in iris and iris.count("tl.") == 2 and '9.850' in iris
    assert "xPercent: 100" in hf_project.boundary_transition("whip", "#s05", 20.0)
    flash = hf_project.boundary_transition("flash", "#s07", 30.0)
    assert '"#flash"' in flash and "opacity: 0.85" in flash


def test_ghep_nhieu_canh_dung_du_kieu_chuyen_canh(tmp_path):
    shots, start = [], 0.0
    for layout in list(BLOCK_LAYOUTS) + list(BLOCK_LAYOUTS):
        shots.append({"seconds": 5.0, "scene": scene(layout), "events": {}, "narration": "lời đọc", "start_seconds": start})
        start += 5.0
    hf_project.build_project(tmp_path / "p", shots, None, None, transitions=True, aspect_ratio="16:9")
    index = (tmp_path / "p" / "index.html").read_text(encoding="utf-8")
    assert "circle(0% at 50% 50%)" in index and "xPercent: 100" in index and 'id="flash"' in index and "tr01" in index
    assert "assets/vendor/CustomEase.min.js" in index and (tmp_path / "p" / "assets" / "vendor" / "CustomEase.min.js").is_file()


def test_khung_doc_phong_to_canh_chu_nho():
    data = {**VALID["MARK_PHRASE"], "portrait": True}
    assert "transform:scale(1.5)" in hf_blocks.scene_composition("MARK_PHRASE", "s01", data, 5)[2]
    assert "transform:scale" not in hf_blocks.scene_composition("MARK_PHRASE", "s01", VALID["MARK_PHRASE"], 5)[2]
    assert "transform:scale" not in hf_blocks.scene_composition("STAT_RING", "s01", {**VALID["STAT_RING"], "portrait": True}, 5)[2]


def _storyboard_nhieu_canh_ui(layouts):
    """Storyboard từ mẫu 17 shot: đổi các shot đầu thành cảnh UI theo danh sách layout (cảnh khối không cần neo)."""
    import copy
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parent / "fixtures/storyboard_llm_17shots_valid.json").read_text(encoding="utf-8"))
    for index, layout in enumerate(layouts):
        shot = data["shots"][index]
        shot["shot_kind"], shot["action_beats"], shot["continues_previous"] = "UI_SIM", [], False
        if layout in BLOCK_LAYOUTS:
            shot["ui_scene"] = {"layout": layout, "messages": [], "highlight": None, "diagram": {**VALID[layout], "on": {}}}
        else:
            words = shot["narration"].split()
            shot["ui_scene"] = {"layout": "PROCESS_RAIL", "messages": [], "highlight": None, "diagram": {
                "title": "Luồng xử lý", "steps": ["Nhận", "Duyệt", "Giao"], "block_step": 1, "on": {"stations": words[0], "block": words[1], "release": words[2]}}}
    data["shots"][len(layouts)]["continues_previous"] = False   # Flow không nối tiếp cảnh UI
    return planner.Storyboard.model_validate(copy.deepcopy(data))


def test_canh_bao_mem_khi_video_khong_dung_canh_khoi():
    thieu = _storyboard_nhieu_canh_ui(["PROCESS_RAIL"] * 5)
    assert any(p.startswith("DIAGRAM_BLOCK_LAYOUT_MISSING") for p in planner._soft_problems(thieu))
    du = _storyboard_nhieu_canh_ui(["PROCESS_RAIL", "KINETIC_TITLE", "PROCESS_RAIL", "MARK_PHRASE", "PILE_UP"])
    assert not any(p.startswith("DIAGRAM_BLOCK_LAYOUT_MISSING") for p in planner._soft_problems(du))
    it_shot_ui = _storyboard_nhieu_canh_ui(["PROCESS_RAIL"] * 4)
    assert not any(p.startswith("DIAGRAM_BLOCK_LAYOUT_MISSING") for p in planner._soft_problems(it_shot_ui))
