"""Danh mục khối và thành phần HyperFrames với phân loại tất định."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

HYPERFRAMES_VERSION = "0.8.222"

# Thứ tự ưu tiên phân loại 13 nhóm khối/thành phần
GROUPS_PRIORITY: list[tuple[str, tuple[str, ...]]] = [
    ("webgpu", ("webgpu", "webgpu-shader")),
    ("can_anh", ("carousel", "gallery", "images", "podcast", "interview", "avatar")),
    ("ma_nguon", ("code", "code-animation", "developer")),
    ("ban_do", ("map",)),
    ("phu_de", ("captions", "caption-style")),
    ("chuyen_canh", ("transition", "transition-primitive", "transitions-dev-port")),
    ("lower_third_mxh", ("lower-third", "social")),
    ("chu_tieu_de", ("typography", "title-card", "text", "handwritten", "text-effects")),
    ("du_lieu", ("data",)),
    ("camera_con_tro", ("camera", "cursor")),
    ("giao_dien_gia_lap", ("mock-ui", "product-demo", "chat", "ui-props", "ad-template", "showcase")),
    ("nen_lop_phu", ("background", "overlay", "texture", "effect", "effects", "reveal", "light", "gradient", "particles", "3d", "webgl", "shader")),
]

FALLBACK_GROUP = "khac"

GPU_TAGS = frozenset({"webgpu", "webgpu-shader"})
ASSETS_TAGS = frozenset({"carousel", "gallery", "images", "podcast", "interview", "avatar"})

# Đường dẫn mặc định tới blocks/index.json
INDEX_PATH = Path(__file__).resolve().parent.parent.parent.parent / "engines" / "hyperframes" / "blocks" / "index.json"


@dataclass(frozen=True)
class CatalogEntry:
    """Mục danh mục đại diện cho một khối hoặc thành phần trong HyperFrames registry."""
    name: str
    kind: Literal["block", "component"]
    tags: tuple[str, ...]
    width: int | None
    height: int | None
    duration: float | None
    group: str
    needs_gpu: bool
    needs_assets: bool


def classify(entry_json: dict) -> str:
    """Phân loại một mục theo thứ tự ưu tiên của nhóm thẻ tag."""
    tags = set(entry_json.get("tags") or [])
    for group_slug, group_tags in GROUPS_PRIORITY:
        if tags.intersection(group_tags):
            return group_slug
    return FALLBACK_GROUP


def _normalize_entry(item: dict) -> dict:
    """Chuyển đổi một mục thô thành cấu trúc chuẩn cho chỉ mục."""
    name = str(item["name"])
    kind = item.get("kind") or item.get("type")
    if kind not in ("block", "component"):
        raise ValueError(f"Loại không hợp lệ cho mục {name}: {kind}")

    tags = list(item.get("tags") or [])
    dims = item.get("dimensions")
    if isinstance(dims, dict):
        width = dims.get("width")
        height = dims.get("height")
    else:
        width = item.get("width")
        height = item.get("height")

    width = int(width) if width is not None else None
    height = int(height) if height is not None else None

    dur = item.get("duration")
    duration = float(dur) if dur is not None else None

    group = item.get("group") or classify(item)

    tags_set = set(tags)
    needs_gpu = item["needs_gpu"] if "needs_gpu" in item else bool(tags_set.intersection(GPU_TAGS))
    needs_assets = item["needs_assets"] if "needs_assets" in item else bool(tags_set.intersection(ASSETS_TAGS))

    return {
        "name": name,
        "kind": kind,
        "tags": tags,
        "width": width,
        "height": height,
        "duration": duration,
        "group": group,
        "needs_gpu": bool(needs_gpu),
        "needs_assets": bool(needs_assets),
    }


def build_index(items: list[dict]) -> dict:
    """Hàm thuần túy tạo tài liệu JSON chỉ mục tất định, sắp xếp theo tên."""
    normalized_entries = [_normalize_entry(item) for item in items]
    sorted_entries = sorted(normalized_entries, key=lambda entry: entry["name"])
    return {
        "hyperframes_version": HYPERFRAMES_VERSION,
        "entries": sorted_entries,
    }


def load_index(path: Path | str | None = None) -> dict[str, CatalogEntry]:
    """Đọc blocks/index.json và trả về danh từ điển CatalogEntry theo tên."""
    target_path = Path(path) if path is not None else INDEX_PATH
    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result: dict[str, CatalogEntry] = {}
    for entry in data.get("entries", []):
        cat_entry = CatalogEntry(
            name=entry["name"],
            kind=entry["kind"],
            tags=tuple(entry.get("tags") or ()),
            width=entry.get("width"),
            height=entry.get("height"),
            duration=float(entry["duration"]) if entry.get("duration") is not None else None,
            group=entry["group"],
            needs_gpu=bool(entry.get("needs_gpu", False)),
            needs_assets=bool(entry.get("needs_assets", False)),
        )
        result[cat_entry.name] = cat_entry
    return result
