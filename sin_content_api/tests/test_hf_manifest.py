"""Kiểm thử tính đúng đắn, an toàn và toàn vẹn của hệ thống manifest khối HyperFrames."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.modules.tao_video_noi_dung import hf_blocks, hf_manifest
from src.modules.tao_video_noi_dung.hf_manifest import (
    BLOCKS_DIR,
    BlockManifest,
    evaluate,
    load_manifests,
    render_literals,
    render_variables,
    validate_manifest,
)
from tests.test_khoi_hyperframes import VALID

GOLDEN_PATH = Path(__file__).resolve().parent / "fixtures" / "hf_manifest_golden.json"


def test_khop_golden_cho_moi_bien_the() -> None:
    """Mọi biến thể khối trong manifest khi lượng giá phải khớp hoàn toàn với tệp golden:
    biến, chuỗi literal, hệ số phóng và chuỗi CSS style.
    """
    assert GOLDEN_PATH.is_file(), f"Thiếu tệp golden: {GOLDEN_PATH}"
    golden: dict[str, list[dict]] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    manifests_by_layout = load_manifests()

    for layout, golden_entries in golden.items():
        assert layout in manifests_by_layout, f"Layout {layout} thiếu trong manifests"
        m_list = manifests_by_layout[layout]
        # Biến thể mới chỉ được thêm vào SAU các biến thể gốc, không đổi thứ tự hay nội dung gốc.
        assert len(m_list) >= len(golden_entries), f"Layout {layout} mất biến thể so với golden"
        m_list = m_list[: len(golden_entries)]

        data = VALID[layout]
        data_portrait = {**data, "portrait": True}

        for idx, (m, g) in enumerate(zip(m_list, golden_entries)):
            assert m.block == g["block"], f"Tên khối không khớp tại {layout}[{idx}]"

            # 1. Khớp biến (variables)
            rendered_vars = render_variables(m, dict(data))
            assert rendered_vars == g["variables"], (
                f"Biến không khớp tại {layout}[{idx}] ({m.variant_key}):\n"
                f"Thực tế: {rendered_vars}\nKỳ vọng: {g['variables']}"
            )

            # 2. Khớp chuỗi literal
            rendered_lits = render_literals(m, dict(data)) if m.literals else None
            assert rendered_lits == g["literals"], (
                f"Literals không khớp tại {layout}[{idx}] ({m.variant_key}):\n"
                f"Thực tế: {rendered_lits}\nKỳ vọng: {g['literals']}"
            )

            # 3. Khớp hệ số phóng khung dọc (portrait_scale)
            calc_scale = hf_blocks.portrait_scale(layout, data_portrait)
            assert calc_scale == g["portrait_scale"], (
                f"Hệ số phóng dọc không khớp tại {layout}[{idx}]: {calc_scale} != {g['portrait_scale']}"
            )

            # 4. Khớp chuỗi style từ scene_composition
            style_portrait = hf_blocks.scene_composition(layout, "s01", data_portrait, 5.0)[2]
            assert style_portrait == g["style_portrait"], (
                f"Style dọc không khớp tại {layout}[{idx}]:\n{style_portrait}\n!=\n{g['style_portrait']}"
            )

            style_non_portrait = hf_blocks.scene_composition(layout, "s01", dict(data), 5.0)[2]
            assert style_non_portrait == g["style_non_portrait"], (
                f"Style ngang không khớp tại {layout}[{idx}]:\n{style_non_portrait}\n!=\n{g['style_non_portrait']}"
            )


def test_validate_manifest_sach_cho_moi_manifest() -> None:
    """Tất cả manifest hiện có phải vượt qua kiểm định validate_manifest với 0 lỗi."""
    manifests_by_layout = load_manifests()
    assert manifests_by_layout, "Không tải được manifest nào"

    for layout, m_list in manifests_by_layout.items():
        for m in m_list:
            block_file = BLOCKS_DIR / f"{m.block}.html"
            assert block_file.is_file(), f"Thiếu tệp khối {m.block}.html"
            block_text = block_file.read_text(encoding="utf-8")

            errors = validate_manifest(m, block_text)
            assert errors == [], f"Lỗi kiểm định manifest tại {layout} ({m.variant_key}): {errors}"


def test_validate_bao_bien_khong_ton_tai() -> None:
    """validate_manifest phát hiện chính xác biến chưa khai báo, enum sai và literal thiếu."""
    sample_block_html = (BLOCKS_DIR / "headline-slam.html").read_text(encoding="utf-8")

    # 1. Biến chưa khai báo trong data-composition-variables
    fake_undeclared = BlockManifest(
        block="headline-slam",
        layout="KINETIC_TITLE",
        variant_key="fake_undeclared",
        variables={"bien_khong_ton_tai": "gia_tri"},
        literals={},
    )
    errs_undeclared = validate_manifest(fake_undeclared, sample_block_html)
    assert len(errs_undeclared) > 0
    assert any("bien_khong_ton_tai" in err for err in errs_undeclared)
    assert any("HYPERFRAMES_MANIFEST_UNDECLARED_VARIABLE" in err for err in errs_undeclared)

    # 2. Giá trị enum không nằm trong options hợp lệ
    fake_bad_enum = BlockManifest(
        block="headline-slam",
        layout="KINETIC_TITLE",
        variant_key="fake_bad_enum",
        variables={"accent": "mau_khong_hop_le"},
        literals={},
    )
    errs_enum = validate_manifest(fake_bad_enum, sample_block_html)
    assert len(errs_enum) > 0
    assert any("HYPERFRAMES_MANIFEST_ENUM_INVALID" in err for err in errs_enum)

    # 3. Chuỗi literal không xuất hiện trong nội dung khối
    fake_bad_literal = BlockManifest(
        block="headline-slam",
        layout="KINETIC_TITLE",
        variant_key="fake_bad_literal",
        variables={},
        literals={"chuoi_hoan_toan_khong_co_trong_block": "thay_the"},
    )
    errs_lit = validate_manifest(fake_bad_literal, sample_block_html)
    assert len(errs_lit) > 0
    assert any("HYPERFRAMES_MANIFEST_LITERAL_MISSING" in err for err in errs_lit)


def test_evaluate_khong_dung_eval() -> None:
    """evaluate phải từ chối hàm không nằm trong danh mục built-in và cấu trúc nút bất thường."""
    # 1. Nút gọi hàm độc hại/ngoài danh mục phải ném ValueError HYPERFRAMES_MANIFEST_FN_INVALID
    with pytest.raises(ValueError, match="HYPERFRAMES_MANIFEST_FN_INVALID"):
        evaluate({"fn": "__import__"}, {})

    with pytest.raises(ValueError, match="HYPERFRAMES_MANIFEST_FN_INVALID"):
        evaluate({"fn": "eval", "args": ["1 + 1"]}, {})

    # 2. Dict chứa khóa không rõ ràng (không phải field cũng không phải fn) ném ValueError
    with pytest.raises(ValueError, match="HYPERFRAMES_MANIFEST_NODE_INVALID"):
        evaluate({"unknown_key": "val"}, {})

    with pytest.raises(ValueError, match="HYPERFRAMES_MANIFEST_NODE_INVALID"):
        evaluate({"field": "title", "extra_bad_key": 123}, {})

    with pytest.raises(ValueError, match="HYPERFRAMES_MANIFEST_NODE_INVALID"):
        evaluate({"fn": "upper", "args": ["a"], "illegal_key": "x"}, {})


def test_thu_tu_bien_the_giu_nguyen() -> None:
    """Thứ tự layout trong BLOCK_SCENES và thứ tự các khối trong từng layout phải bằng đúng tệp golden."""
    golden: dict[str, list[dict]] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    # Kiểm tra thứ tự các layout
    # Layout mới (CHAT_THREAD...) chỉ được nối vào cuối, các layout gốc giữ nguyên thứ tự.
    layout_goc = list(hf_blocks.BLOCK_SCENES.keys())[: len(golden)]
    assert layout_goc == list(golden.keys()), (
        f"Thứ tự layout khác biệt: {layout_goc} != {list(golden.keys())}"
    )

    # Kiểm tra thứ tự biến thể của từng layout
    for layout in golden:
        golden_blocks = [item["block"] for item in golden[layout]]
        scenes_blocks = [v.block for v in hf_blocks.BLOCK_SCENES[layout]][: len(golden_blocks)]
        assert scenes_blocks == golden_blocks, (
            f"Thứ tự khối tại layout {layout} khác biệt:\n{scenes_blocks}\n!=\n{golden_blocks}"
        )
