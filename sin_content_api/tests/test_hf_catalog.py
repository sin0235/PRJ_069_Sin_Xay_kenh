"""Kiểm thử danh mục và phân loại khối HyperFrames registry."""
from __future__ import annotations

from collections import Counter

from src.modules.tao_video_noi_dung.hf_catalog import (
    CatalogEntry,
    build_index,
    classify,
    load_index,
)


def test_classify_theo_thu_tu_uu_tien() -> None:
    """Kiểm tra phân loại nhóm theo đúng thứ tự ưu tiên của các thẻ."""
    assert classify({"tags": ["webgpu", "transition"]}) == "webgpu"
    assert classify({"tags": ["carousel", "text"]}) == "can_anh"
    assert classify({"tags": ["foo"]}) == "khac"
    assert classify({"tags": ["transition", "text"]}) == "chuyen_canh"


def test_tong_so_muc_va_loai() -> None:
    """Kiểm tra tổng số lượng mục và tỷ lệ giữa block và component."""
    entries = load_index()
    assert len(entries) == 448

    blocks = [e for e in entries.values() if e.kind == "block"]
    components = [e for e in entries.values() if e.kind == "component"]

    assert len(blocks) == 210
    assert len(components) == 238


def test_so_muc_moi_nhom() -> None:
    """Kiểm tra số lượng mục chính xác cho từng nhóm trong tổng số 13 nhóm."""
    entries = load_index()
    counts = Counter(e.group for e in entries.values())

    expected = {
        "webgpu": 40,
        "can_anh": 39,
        "ma_nguon": 12,
        "ban_do": 8,
        "phu_de": 17,
        "chuyen_canh": 69,
        "lower_third_mxh": 13,
        "chu_tieu_de": 66,
        "du_lieu": 10,
        "camera_con_tro": 27,
        "giao_dien_gia_lap": 49,
        "nen_lop_phu": 53,
        "khac": 45,
    }

    assert dict(counts) == expected


def test_index_tat_dinh() -> None:
    """Kiểm tra tính tất định: cùng đầu vào tạo ra kết quả giống nhau và sắp xếp theo tên."""
    sample_items = [
        {"name": "z-item", "type": "component", "tags": ["text"]},
        {
            "name": "a-item",
            "type": "block",
            "tags": ["webgpu"],
            "dimensions": {"width": 1920, "height": 1080},
            "duration": 5.0,
        },
        {"name": "m-item", "type": "component", "tags": ["carousel"]},
    ]

    out1 = build_index(sample_items)
    out2 = build_index(sample_items)

    assert out1 == out2
    names = [e["name"] for e in out1["entries"]]
    assert names == ["a-item", "m-item", "z-item"]


def test_load_index_tra_catalog_entry() -> None:
    """Kiểm tra load_index trả về đối tượng CatalogEntry hợp lệ."""
    catalog = load_index()
    assert "headline-slam" in catalog

    entry = catalog["headline-slam"]
    assert isinstance(entry, CatalogEntry)
    assert entry.kind in ("component", "block")
    assert bool(entry.group)
    assert isinstance(entry.tags, tuple)
