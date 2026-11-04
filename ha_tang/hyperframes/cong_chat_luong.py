"""Cổng chất lượng kiểm tra trước khi dựng video HyperFrames (Task 12).

Kiểm tra toàn bộ các cảnh khối (registry blocks) của storyboard với nội dung thật
trước khi tốn tín dụng Flow:
- Chạy `hyperframes check --json` để bắt lỗi lint, runtime và layout.
- Quét tĩnh các tệp composition HTML để phát hiện từ mẫu tiếng Anh (ENGLISH_SAMPLE_WORDS).
- Quét các URL từ xa bằng hf_vendor.scan_external.
- Chụp ảnh snapshot tại 60% thời lượng của từng shot và kiểm tra chữ có tràn mép
  khung hình (9:16 và 16:9) hay không.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "sin_content_api"), str(ROOT)]

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE.parent / "chay_dev_local" / ".env.dev", override=True)

from src.database import SessionLocal  # noqa: E402
from src.models.entities import ContentVideoPlan  # noqa: E402
from src.modules.tao_video_noi_dung import hf_blocks, hf_project, hf_vendor  # noqa: E402
from src.modules.tao_video_noi_dung.hf_project import _RENDER_LOCK, _env, _node, hyperframes_cli  # noqa: E402
from src.modules.tao_video_noi_dung.planner import BLOCK_LAYOUTS, Storyboard  # noqa: E402

# Danh sách từ mẫu tiếng Anh bị cấm rò rỉ từ các khối dựng sẵn
_BASE_ENGLISH_WORDS = {
    "Inbox", "Workspace", "Draft", "Published", "Brand A", "Brand B", "Brand C",
    "Your brand", "Streaming", "Subscribers", "RETENTION", "NET GROWTH",
    "Fix checkout", "To do", "In progress", "Messages", "Calendar", "Reminders", "Lorem"
}
_VIET_KEYS = {k for d in getattr(hf_blocks, "_VIETNAMESE_TEXT", {}).values() for k in d.keys()}
ENGLISH_SAMPLE_WORDS: frozenset[str] = frozenset(_BASE_ENGLISH_WORDS | _VIET_KEYS)

_JS_STRING_RE = re.compile(
    r"""(?:"(?P<q1>[^"\\]*(?:\\.[^"\\]*)*)"|'(?P<q2>[^'\\]*(?:\\.[^'\\]*)*)'|`(?P<q3>[^`\\]*(?:\\.[^`\\]*)*)`)"""
)


def scan_english(composition_html: str) -> list[str]:
    """Quét tĩnh nội dung HTML của composition để tìm các từ mẫu tiếng Anh.

    Phát hiện các từ thuộc ENGLISH_SAMPLE_WORDS xuất hiện dưới dạng chữ hiển thị
    (visible text) hoặc chuỗi ký tự trong mã JS (quoted JS string).
    """
    scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", composition_html, flags=re.I)
    quoted_js_strings: list[str] = []
    for s in scripts:
        for m in _JS_STRING_RE.finditer(s):
            val = m.group("q1") or m.group("q2") or m.group("q3") or ""
            quoted_js_strings.append(val)

    clean = re.sub(r"<!--[\s\S]*?-->", "", composition_html)
    no_script_style = re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", clean, flags=re.I)
    visible_text = html.unescape(re.sub(r"<[^>]+>", " ", no_script_style))

    found: set[str] = set()
    for word in ENGLISH_SAMPLE_WORDS:
        lead = r"(?<!\w)" if word[0].isalnum() else r"(?:(?<=\s)|(?<=^))"
        trail = r"(?!\w)" if word[-1].isalnum() else r"(?:(?=\s)|(?=$))"
        pat = re.compile(rf"{lead}{re.escape(word)}{trail}")
        if pat.search(visible_text):
            found.add(word)
            continue
        for q in quoted_js_strings:
            if pat.search(q):
                found.add(word)
                break
    return sorted(found)


def scan_urls(composition_html: str) -> list[str]:
    """Tìm tất cả các URL từ xa trong mã HTML composition qua hf_vendor.scan_external."""
    return hf_vendor.scan_external(composition_html)


def check_text_touches_edge(image: Image.Image) -> bool:
    """Kiểm tra chữ có tràn mép khung hình hay không.

    Đọc ảnh PNG bằng PIL, lấy độ sáng góc khung hình (0, 0) làm màu mép.
    Đếm số pixel trong phạm vi 8px tính từ viền trái hoặc phải có độ lệch độ sáng > 60.
    Nếu số pixel lệch vượt quá 0.3% tổng số pixel trong hai dải viền, coi là chữ tràn mép.
    """
    img_l = image.convert("L")
    w, h = img_l.size
    corner_lum = img_l.getpixel((0, 0))
    diff_count = sum(
        1 for x in range(8) for y in range(h) if abs(img_l.getpixel((x, y)) - corner_lum) > 60
    ) + sum(
        1 for x in range(w - 8, w) for y in range(h) if abs(img_l.getpixel((x, y)) - corner_lum) > 60
    )
    total_border_pixels = 16 * h
    return (diff_count / total_border_pixels) > 0.003


def _resolve_finding_shot_id(finding: dict, block_shots: list[Any], shots_payload: list[dict]) -> str:
    """Xác định shot_id tương ứng với một lỗi phát hiện từ hyperframes check."""
    source_file = str(finding.get("sourceFile", ""))
    m = re.search(r"s(\d+)\.html", source_file)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(block_shots):
            return block_shots[idx].shot_id

    for key in ("selector", "containerSelector"):
        val = str(finding.get(key, ""))
        m = re.search(r"#s(\d+)\b", val)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(block_shots):
                return block_shots[idx].shot_id

    t = finding.get("time")
    if isinstance(t, (int, float)):
        for sp, shot in zip(shots_payload, block_shots):
            if sp["start_seconds"] <= t <= sp["start_seconds"] + sp["seconds"] + 0.05:
                return shot.shot_id

    return block_shots[0].shot_id if block_shots else "unknown"


def run_project_check(project_dir: Path) -> dict:
    """Chạy lệnh hyperframes check --json trên thư mục dự án."""
    cmd = [_node(), str(hyperframes_cli()), "check", "--json", str(project_dir)]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
        timeout=120,
    )
    stdout = res.stdout or ""
    try:
        idx = stdout.index("{")
        return json.loads(stdout[idx:])
    except (ValueError, json.JSONDecodeError):
        return {}


def capture_snapshots(project_dir: Path, output_dir: Path, at_times: list[float]) -> list[dict]:
    """Chụp các ảnh snapshot tại các mốc thời gian bằng hyperframes snapshot."""
    output_dir.mkdir(parents=True, exist_ok=True)
    at_str = ",".join(str(t) for t in at_times)
    cmd = [
        _node(),
        str(hyperframes_cli()),
        "snapshot",
        "--at",
        at_str,
        "--no-end",
        "-o",
        str(output_dir),
        "--json",
        str(project_dir),
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_env(),
        timeout=180,
    )
    stdout = res.stdout or ""
    try:
        idx = stdout.index("{")
        data = json.loads(stdout[idx:])
        return data.get("frames", [])
    except (ValueError, json.JSONDecodeError):
        return []


def gate_storyboard(storyboard, aspect: str, work_dir: Path | None = None) -> list[str]:
    """Cổng chất lượng kiểm tra storyboard trước khi dựng.

    Chỉ dựng một dự án HyperFrames gồm các cảnh UI layout khối (BLOCK_LAYOUTS)
    với thời lượng thật, chạy kiểm tra lint/runtime/layout, quét từ mẫu tiếng Anh,
    quét URL từ xa, và kiểm tra chữ tràn mép qua ảnh chụp khung hình.
    """
    block_shots = [
        s for s in storyboard.shots
        if getattr(s, "shot_kind", None) == "UI_SIM"
        and getattr(s, "ui_scene", None) is not None
        and getattr(s.ui_scene, "layout", None) in BLOCK_LAYOUTS
    ]
    if not block_shots:
        return []

    if work_dir is not None:
        target_dir = Path(work_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        return _run_gate(block_shots, aspect, target_dir)
    else:
        with tempfile.TemporaryDirectory() as td:
            return _run_gate(block_shots, aspect, Path(td) / "project")


def _run_gate(block_shots: list[Any], aspect: str, project_dir: Path) -> list[str]:
    problems: list[str] = []
    shots_payload: list[dict] = []
    start_sec = 0.0
    for i, shot in enumerate(block_shots):
        sec = float(shot.duration_seconds)
        shots_payload.append({
            "seconds": sec,
            "scene": shot.ui_scene,
            "events": getattr(shot.ui_scene.diagram, "on", {}) if getattr(shot.ui_scene, "diagram", None) else {},
            "narration": getattr(shot, "narration", "") or "lời đọc",
            "start_seconds": start_sec,
            "shot_id": getattr(shot, "shot_id", f"s{i + 1:02d}"),
        })
        start_sec += sec

    hf_project.build_project(project_dir, shots_payload, None, None, transitions=False, aspect_ratio=aspect)

    with _RENDER_LOCK:
        check_result = run_project_check(project_dir)

    for section in ("lint", "runtime", "layout"):
        for finding in check_result.get(section, {}).get("findings", []):
            if finding.get("severity") == "error":
                shot_id = _resolve_finding_shot_id(finding, block_shots, shots_payload)
                code = finding.get("code", "UNKNOWN")
                msg = finding.get("message", "")
                problems.append(f"{shot_id}: {code}: {msg}")

    for i, shot in enumerate(block_shots):
        cid = f"s{i + 1:02d}"
        comp_file = project_dir / "compositions" / f"{cid}.html"
        if comp_file.is_file():
            comp_html = comp_file.read_text(encoding="utf-8")
            for word in scan_english(comp_html):
                problems.append(f"{shot.shot_id}: ENGLISH_SAMPLE_TEXT: {word}")
            for url in scan_urls(comp_html):
                problems.append(f"{shot.shot_id}: EXTERNAL_URL: {url}")

    if aspect in ("9:16", "16:9"):
        at_times = [round(sp["start_seconds"] + 0.6 * sp["seconds"], 3) for sp in shots_payload]
        snap_dir = project_dir / ".snapshots"
        with _RENDER_LOCK:
            frames = capture_snapshots(project_dir, snap_dir, at_times)

        for i, shot in enumerate(block_shots):
            target_t = at_times[i]
            matching_frames = [f for f in frames if abs(f.get("time", -999) - target_t) < 0.15]
            frame_info = matching_frames[0] if matching_frames else (frames[i] if i < len(frames) else None)
            if frame_info and "path" in frame_info and Path(frame_info["path"]).is_file():
                img = Image.open(frame_info["path"])
                if check_text_touches_edge(img):
                    problems.append(f"{shot.shot_id}: TEXT_TOUCHES_EDGE")

    return problems


def gate_plan(project_id: str, plan_id: str) -> list[str]:
    """Kiểm tra kế hoạch video theo mã dự án và mã kế hoạch trong cơ sở dữ liệu."""
    with SessionLocal() as db:
        plan = db.query(ContentVideoPlan).filter(
            ContentVideoPlan.id == plan_id,
            ContentVideoPlan.project_id == project_id,
        ).first()
        if not plan:
            plan = db.query(ContentVideoPlan).filter(ContentVideoPlan.id == plan_id).first()
        if not plan:
            raise ValueError(f"PLAN_NOT_FOUND: {plan_id}")

        snapshot = json.loads(plan.style_snapshot_json) if plan.style_snapshot_json else {}
        aspect = snapshot.get("aspect_ratio", "16:9")
        storyboard = Storyboard.model_validate_json(plan.storyboard_json)
        return gate_storyboard(storyboard, aspect)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cổng chất lượng kiểm tra trước khi dựng video")
    parser.add_argument("--bai", required=True, help="Số thứ tự bài viết (ví dụ: 13, 01, 02)")
    args = parser.parse_args()

    state_file = HERE.parent / "chay_dev_local" / "data" / "lo_video" / "trang_thai.json"
    if not state_file.is_file():
        print(f"Không tìm thấy tệp trạng thái: {state_file}")
        sys.exit(1)

    state = json.loads(state_file.read_text(encoding="utf-8"))
    key = str(args.bai)
    entry = state.get(key) or state.get(key.zfill(2)) or state.get(str(int(key)) if key.isdigit() else key)
    if not entry or "plan_id" not in entry or "project_id" not in entry:
        print(f"Bài {args.bai} chưa có thông tin plan_id hoặc project_id trong tệp trạng thái.")
        sys.exit(1)

    problems = gate_plan(entry["project_id"], entry["plan_id"])
    if not problems:
        print("đạt cổng chất lượng")
    else:
        for p in problems:
            print(p)


if __name__ == "__main__":
    main()
