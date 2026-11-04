"""Kiểm thử tự động cho bộ kiểm thử khói khối HyperFrames."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

# Đảm bảo đường dẫn ha_tang/hyperframes nằm trong sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HA_TANG_DIR = REPO_ROOT / "ha_tang" / "hyperframes"
if str(HA_TANG_DIR) not in sys.path:
    sys.path.insert(0, str(HA_TANG_DIR))

from kiem_thu_khoi import (  # noqa: E402
    SmokeResult,
    names_done,
    select_names,
    smoke_block,
    write_contact_sheet,
)
from src.modules.tao_video_noi_dung.hf_catalog import load_index  # noqa: E402


@pytest.mark.browser
def test_smoke_block_headline_slam(tmp_path: Path) -> None:
    """Kiểm tra khối headline-slam: renders=True, runtime_errors=0, đúng 2 khung hình PNG tồn tại."""
    res = smoke_block("headline-slam", tmp_path)

    assert isinstance(res, SmokeResult)
    assert res.name == "headline-slam"
    assert res.renders is True
    assert res.runtime_errors == 0
    assert len(res.frames) == 2
    for frame_path in res.frames:
        p = Path(frame_path)
        assert p.is_file(), f"Khung hình không tồn tại: {frame_path}"
        assert frame_path.endswith(".png"), f"Khung hình không phải PNG: {frame_path}"


@pytest.mark.browser
def test_smoke_ghi_nhan_snippet(tmp_path: Path) -> None:
    """Kiểm tra khối number-wheel là snippet: renders=False và reason='snippet'."""
    res = smoke_block("number-wheel", tmp_path)

    assert isinstance(res, SmokeResult)
    assert res.name == "number-wheel"
    assert res.renders is False
    assert res.reason == "snippet"
    assert len(res.frames) == 0


def test_chon_muc_bo_qua_webgpu_va_can_anh() -> None:
    """Kiểm tra hàm chọn tên: bỏ qua webgpu và can_anh mặc định, nhận cả hai khi ca_webgpu=True, và lọc theo nhóm."""
    index = load_index()
    assert len(index) == 448

    # 1. Mặc định bỏ qua webgpu và can_anh
    mac_dinh = select_names(index, nhom="all", ca_webgpu=False)
    assert len(mac_dinh) == 369
    for name in mac_dinh:
        assert index[name].group not in ("webgpu", "can_anh")

    # 2. Bao gồm cả webgpu và can_anh khi ca_webgpu=True
    tat_ca = select_names(index, nhom="all", ca_webgpu=True)
    assert len(tat_ca) == 448
    assert any(index[name].group == "webgpu" for name in tat_ca)
    assert any(index[name].group == "can_anh" for name in tat_ca)

    # 3. Lọc theo nhóm chu_tieu_de chỉ trả về các khối thuộc nhóm đó
    chu_tieu_de = select_names(index, nhom="chu_tieu_de", ca_webgpu=False)
    assert len(chu_tieu_de) == 66
    for name in chu_tieu_de:
        assert index[name].group == "chu_tieu_de"
    assert "headline-slam" in chu_tieu_de


def test_ghi_jsonl_va_tiep_tuc(tmp_path: Path) -> None:
    """Kiểm tra hàm names_done: tệp chưa có trả về tập hợp rỗng, tệp có sẵn trả về đúng danh sách tên."""
    jsonl_file = tmp_path / "kiem_thu_khoi.jsonl"

    # Khi tệp chưa tồn tại
    assert names_done(jsonl_file) == set()

    # Tạo tệp jsonl với dữ liệu mẫu
    mau = [
        {"name": "headline-slam", "renders": True},
        {"name": "number-wheel", "renders": False},
        {"name": "kinetic-text", "renders": True},
    ]
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for item in mau:
            f.write(json.dumps(item) + "\n")

    # Khi tệp đã tồn tại
    da_lam = names_done(jsonl_file)
    assert da_lam == {"headline-slam", "number-wheel", "kinetic-text"}


def test_write_contact_sheet(tmp_path: Path) -> None:
    """Kiểm tra tạo bảng liên lạc contact sheet từ danh sách SmokeResult có khung hình."""
    out_png = tmp_path / "test_sheet.png"

    # Trường hợp danh sách rỗng
    write_contact_sheet([], out_png)
    assert not out_png.exists()

    # Tạo 2 tệp ảnh giả lập
    f1 = tmp_path / "frame-00-at-1.2s.png"
    f2 = tmp_path / "frame-01-at-2.6s.png"
    try:
        from PIL import Image
        Image.new("RGB", (320, 180), color=(20, 40, 60)).save(f1)
        Image.new("RGB", (320, 180), color=(60, 40, 20)).save(f2)

        results = [
            SmokeResult(
                name="headline-slam",
                renders=True,
                reason="ok",
                runtime_errors=0,
                layout_errors=0,
                seconds=1.5,
                frames=(str(f1), str(f2)),
                external_deps=(),
            )
        ]
        write_contact_sheet(results, out_png)
        assert out_png.is_file()
        assert out_png.stat().st_size > 0
    except ImportError:
        pass
