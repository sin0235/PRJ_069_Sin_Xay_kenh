"""Khai báo định dạng manifest thuần dữ liệu (JSON) cho các khối HyperFrames.

Thay thế toàn bộ logic Python lambda trước đây bằng cây biểu thức tự lượng giá (expression AST),
bảo đảm an toàn tuyệt đối không dùng eval/exec và có thể kiểm định tĩnh (validate)
với định nghĩa biến trong tệp HTML của từng khối.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BLOCKS_DIR = Path(__file__).resolve().parents[3] / "engines" / "hyperframes" / "blocks"
MANIFESTS_DIR = BLOCKS_DIR / "manifest"

LAYOUT_ORDER = (
    "KINETIC_TITLE",
    "MARK_PHRASE",
    "WORD_SWAP",
    "PILE_UP",
    "STAT_RING",
    "CHART_STORY",
    "AI_RANK",
    "DRAG_TASKS",
    "CARD_SHIFT",
)


@dataclass(frozen=True)
class BlockManifest:
    """Bản kê khai báo khối giao diện HyperFrames."""
    block: str
    layout: str
    variant_key: str
    variables: dict
    literals: dict = field(default_factory=dict)
    max_chars: int = 999
    portrait_scale: dict[str, float] = field(default_factory=dict)
    square: bool = False
    order: int = 0


# ---------------------------------------------------------------------------
# Các hàm tính toán nội tại (Built-in functions) cho cây biểu thức
# ---------------------------------------------------------------------------

def _fn_default(value: Any, fallback: Any) -> Any:
    if value is None or value == "" or value == []:
        return fallback
    return value


def _fn_upper(text: Any) -> str:
    return str(text or "").upper()


def _fn_join(lst: Any, sep: str) -> str:
    if not lst:
        return ""
    parts = []
    for item in lst:
        if isinstance(item, float):
            s = f"{round(item, 1):.1f}".rstrip("0").rstrip(".")
            parts.append(s)
        else:
            parts.append(str(item))
    return sep.join(parts)


def _fn_first(lst: Any) -> Any:
    if not lst:
        return None
    if isinstance(lst, (list, tuple)):
        return lst[0]
    return lst


def _fn_last(lst: Any) -> Any:
    if not lst:
        return None
    if isinstance(lst, (list, tuple)):
        return lst[-1]
    return lst


def _fn_clamp(value: Any, lo: Any, hi: Any) -> int | float:
    v = float(value)
    res = min(float(hi), max(float(lo), v))
    if isinstance(value, int) and isinstance(lo, int) and isinstance(hi, int):
        return int(res)
    return res


def _fn_to_int(value: Any) -> int:
    return int(value)


def _fn_add(a: Any, b: Any) -> int | float:
    return a + b


def _fn_concat(*parts: Any) -> str:
    return "".join(str(p) if p is not None else "" for p in parts)


def _fn_words(text: Any) -> list[str]:
    if not text:
        return []
    return str(text).split()


def _fn_accent_index(title: Any, tag: Any) -> int:
    words = str(title or "").split()
    if tag:
        tag_words = str(tag).split()
        first = tag_words[0].casefold().strip(".,!?:;") if tag_words else ""
        for index, word in enumerate(words):
            if word.casefold().strip(".,!?:;") == first:
                return index
    return max(0, len(words) - 1)


def _fn_html_escape(text: Any) -> str:
    if text is None:
        return ""
    return html.escape(str(text), quote=False)


def _fn_digits_or(value: Any, fallback: Any) -> int | float:
    if value is None:
        return fallback
    try:
        if isinstance(value, (int, float)):
            return value
        s = str(value).strip()
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
        return float(s)
    except (ValueError, TypeError):
        return fallback


def _fn_take(seq: Any, n: Any) -> Any:
    if seq is None:
        return "" if isinstance(seq, str) else []
    if isinstance(n, str) and n == "half":
        half = max(1, len(seq) // 2)
        return seq[:half]
    if isinstance(n, float) and 0 < n < 1:
        half = max(1, int(len(seq) * n))
        return seq[:half]
    try:
        count = int(n)
        return seq[:count]
    except (ValueError, TypeError):
        return seq


def _fn_nth(lst: Any, i: Any) -> Any:
    if lst is None:
        return None
    if isinstance(lst, dict):
        return lst.get(i)
    try:
        idx = int(i)
        if 0 <= idx < len(lst):
            return lst[idx]
        return None
    except (ValueError, TypeError, IndexError):
        return None


def _fn_len(x: Any) -> int:
    if x is None:
        return 0
    return len(x)


BUILTIN_FNS = {
    "default": _fn_default,
    "upper": _fn_upper,
    "join": _fn_join,
    "first": _fn_first,
    "last": _fn_last,
    "clamp": _fn_clamp,
    "to_int": _fn_to_int,
    "add": _fn_add,
    "concat": _fn_concat,
    "words": _fn_words,
    "accent_index": _fn_accent_index,
    "html_escape": _fn_html_escape,
    "digits_or": _fn_digits_or,
    "take": _fn_take,
    "nth": _fn_nth,
    "len": _fn_len,
}


def _lookup_field(data: dict, field_path: str) -> Any:
    if not field_path:
        return None
    if field_path in data:
        return data[field_path]
    parts = field_path.split(".")
    curr = data
    for part in parts:
        if curr is None:
            return None
        if isinstance(curr, dict):
            curr = curr.get(part)
        elif isinstance(curr, (list, tuple)):
            try:
                idx = int(part)
                curr = curr[idx] if 0 <= idx < len(curr) else None
            except ValueError:
                return None
        else:
            return None
    return curr


def evaluate(node: Any, data: dict) -> Any:
    """Lượng giá một nút biểu thức mà KHÔNG dùng eval/exec.

    Dạng nút:
    - Giá trị literal JSON (str, int, float, bool, None).
    - {"field": "key"}: tra cứu trong data, trả về None nếu thiếu.
    - {"fn": "name", "args": [nodes...]}: gọi hàm nội tại đã định nghĩa.
    """
    if isinstance(node, (str, int, float, bool)) or node is None:
        return node
    if isinstance(node, list):
        return [evaluate(item, data) for item in node]
    if isinstance(node, dict):
        if set(node.keys()) == {"field"}:
            return _lookup_field(data, node["field"])
        elif "fn" in node:
            if not set(node.keys()).issubset({"fn", "args"}):
                raise ValueError("HYPERFRAMES_MANIFEST_NODE_INVALID")
            fn_name = node["fn"]
            if fn_name not in BUILTIN_FNS:
                raise ValueError("HYPERFRAMES_MANIFEST_FN_INVALID")
            args = [evaluate(arg, data) for arg in node.get("args", [])]
            return BUILTIN_FNS[fn_name](*args)
        else:
            raise ValueError("HYPERFRAMES_MANIFEST_NODE_INVALID")
    raise ValueError("HYPERFRAMES_MANIFEST_NODE_INVALID")


def render_variables(manifest: BlockManifest, data: dict) -> dict:
    """Lượng giá toàn bộ biến trong manifest với dữ liệu cảnh cụ thể."""
    return {key: evaluate(node, data) for key, node in manifest.variables.items()}


def render_literals(manifest: BlockManifest, data: dict) -> dict:
    """Lượng giá các chuỗi thay thế cố định trong mã khối."""
    if not manifest.literals:
        return {}
    res = {}
    for key, node in manifest.literals.items():
        if isinstance(node, str):
            res[key] = node
        else:
            res[key] = str(evaluate(node, data))
    return res


def validate_manifest(manifest: BlockManifest, block_text: str) -> list[str]:
    """Kiểm tra manifest so với mã HTML thực tế của khối.

    Trả về danh sách chuỗi lỗi cho:
    - Biến không được khai báo trong data-composition-variables của khối.
    - Biến enum có giá trị mẫu không nằm trong danh sách options hợp lệ.
    - Chuỗi literal không xuất hiện trong nội dung khối.
    """
    errors: list[str] = []

    # 1. Trích xuất khai báo biến từ data-composition-variables
    m = re.search(r'data-composition-variables=(["\'])(.*?)\1', block_text, re.DOTALL)
    declared_vars: dict[str, dict] = {}
    if m:
        raw = m.group(2).replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&")
        try:
            items = json.loads(raw)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and "id" in item:
                        declared_vars[item["id"]] = item
        except (json.JSONDecodeError, ValueError):
            pass

    # 2. Kiểm tra các biến được khai báo
    for var_name, node in manifest.variables.items():
        if var_name not in declared_vars:
            errors.append(f"HYPERFRAMES_MANIFEST_UNDECLARED_VARIABLE:{manifest.block}:{var_name}")
            continue

        var_def = declared_vars[var_name]
        if var_def.get("type") == "enum":
            options_raw = var_def.get("options", [])
            allowed = [opt["value"] if isinstance(opt, dict) else opt for opt in options_raw]
            try:
                val = evaluate(node, {})
            except Exception:
                val = node if isinstance(node, (str, int, float, bool)) else None
            if val is not None and isinstance(val, str) and allowed and val not in allowed:
                errors.append(f"HYPERFRAMES_MANIFEST_ENUM_INVALID:{manifest.block}:{var_name}:{val}")

    # 3. Kiểm tra các chuỗi literal
    for lit_key in (manifest.literals or {}):
        if lit_key not in block_text:
            errors.append(f"HYPERFRAMES_MANIFEST_LITERAL_MISSING:{manifest.block}:{lit_key}")

    return errors


def load_manifests(directory: Path | None = None) -> dict[str, list[BlockManifest]]:
    """Đọc toàn bộ manifest từ thư mục blocks/manifest/*.json.

    Trả về dict[layout, list[BlockManifest]] theo đúng thứ tự bố cục và thứ tự biến thể.
    """
    manifest_dir = directory or MANIFESTS_DIR
    if not manifest_dir.is_dir():
        return {}

    manifests_by_layout: dict[str, list[tuple[int, BlockManifest]]] = {}
    for p in sorted(manifest_dir.glob("*.json")):
        try:
            raw_data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue

        items = raw_data if isinstance(raw_data, list) else [raw_data]
        for item in items:
            if not isinstance(item, dict) or "layout" not in item or "block" not in item:
                continue
            manifest = BlockManifest(
                block=item["block"],
                layout=item["layout"],
                variant_key=item.get("variant_key", item["block"]),
                variables=item.get("variables", {}),
                literals=item.get("literals", {}),
                max_chars=int(item.get("max_chars", 999)),
                portrait_scale=item.get("portrait_scale", {}),
                square=bool(item.get("square", False)),
                order=int(item.get("order", 0)),
            )
            order_key = int(item.get("order", 0))
            manifests_by_layout.setdefault(manifest.layout, []).append((order_key, manifest))

    result: dict[str, list[BlockManifest]] = {}
    for layout in LAYOUT_ORDER:
        if layout in manifests_by_layout:
            result[layout] = [m for _, m in sorted(manifests_by_layout[layout], key=lambda x: x[0])]
    for layout in sorted(manifests_by_layout):
        if layout not in result:
            result[layout] = [m for _, m in sorted(manifests_by_layout[layout], key=lambda x: x[0])]

    return result
