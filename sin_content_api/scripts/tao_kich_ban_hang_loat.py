"""Để LLM tự viết nội dung nguồn và kịch bản (storyboard cảnh giấy) từ danh sách chủ đề, không dựng giọng và không dựng video.

Mỗi chủ đề đi hai bước, dùng đúng mã của pipeline:
  1. LLM viết nội dung nguồn tiếng Việt (có số liệu minh họa và các ý hợp với nhiều loại cảnh khác nhau).
  2. planner.generate_storyboard ở chế độ diagram_only sinh kịch bản: mỗi shot một loại cảnh, lời đọc, cụm neo từng sự kiện.
Đầu ra cho mỗi chủ đề: noi_dung.txt, storyboard.json, kich_ban.md (bản đọc được cho người duyệt) và một dòng thống kê trong tong_hop.md.

Dùng: python tao_kich_ban_hang_loat.py --chu-de-tep chu_de.txt --ra <thu_muc> --llm-env <tệp có url và api-key> [--thoi-luong 90]
chu_de.txt: mỗi dòng một chủ đề. Khóa API đọc từ tệp, không in và không ghi vào đầu ra.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tao_video_canh_giay_tron_goi import GatewayClient, read_env_file, log   # noqa: E402  (đã thêm ROOT vào sys.path)

SOURCE_RULES = (
    "Bạn viết nội dung nguồn tiếng Việt có dấu để làm video giải thích 90 giây cho BAHA Group (giải pháp AI và tự động hóa cho doanh nghiệp). "
    "Độ dài 1400 đến 2200 ký tự, 5 đến 7 đoạn ngắn. Đoạn đầu là một câu hỏi hoặc con số gây chú ý. "
    "BẮT BUỘC có số liệu minh họa cụ thể, VIẾT BẰNG CHỮ (ví dụ: sáu mươi lăm phần trăm, một nghìn khách), "
    "và nói rõ đó là số liệu minh họa. Trộn nhiều dạng ý để dựng hình khác nhau: so với mục tiêu hoặc ngưỡng, hao dần qua các bước, "
    "trước và sau khi thay đổi, cơ cấu phần trăm, xếp hạng, quy trình có điểm nghẽn, lộ trình theo mốc thời gian, "
    "danh sách việc cần làm, giao việc cho người cụ thể, khách chờ, dữ liệu rời rạc cần gom, hai con số lệch nhau, dòng tiền. "
    "Không dùng emoji, không dùng ký hiệu lạ, viết Ba-ha thay cho BAHA khi nhắc tên. Đoạn cuối mời trao đổi cùng Ba-ha Group. "
    "Chỉ trả nội dung, không tiêu đề, không giải thích."
)


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")[:48] or "chu_de"


def script_markdown(topic: str, storyboard, soft: list[str]) -> str:
    lines = [f"# Kịch bản: {topic}", "", f"Số shot: {len(storyboard.shots)}. Loại cảnh theo thứ tự: " + ", ".join(s.ui_scene.layout if s.ui_scene else s.shot_kind for s in storyboard.shots), ""]
    for index, shot in enumerate(storyboard.shots, 1):
        scene, spec = shot.ui_scene, shot.ui_scene.diagram if shot.ui_scene else None
        if spec is None:
            lines += [f"## Shot {index}: {scene.layout if scene else shot.shot_kind} (clip Flow, không phải cảnh giấy)", f"- Lời đọc: {shot.narration}",
                      f"- Mật độ: {len(shot.action_beats)} nhịp hành động, prompt {len(shot.prompt)} ký tự", ""]
            continue
        lines += [f"## Shot {index}: {scene.layout}", f"- Tiêu đề cảnh: {spec.title}", f"- Lời đọc: {shot.narration}",
                  "- Sự kiện gắn với lời: " + "; ".join(f"{key} = \"{phrase}\"" for key, phrase in spec.on.items()), ""]
    lines += ["## Cảnh báo chất lượng", *(f"- {item}" for item in soft)] if soft else ["## Cảnh báo chất lượng", "- Không có."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chu-de-tep", required=True)
    parser.add_argument("--ra", required=True)
    parser.add_argument("--llm-env", required=True)
    parser.add_argument("--model", default="cx/gpt-6-luna")
    parser.add_argument("--thoi-luong", type=int, default=90)
    parser.add_argument("--lai", action="store_true", help="Chế độ lai: LLM được chọn cả clip Flow lẫn cảnh giấy (mặc định chỉ cảnh giấy)")
    args = parser.parse_args()
    out = Path(args.ra).resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{(out / 'tam.db').as_posix()}", "BAHA_AUTH_DATABASE_URL": f"sqlite:///{(out / 'tam_auth.db').as_posix()}",
        "SIN_DUNG_DB_PATH": str(out / "tam_dung.db"), "MEDIA_ROOT_DIR": str(out / "media"),
    })
    import logging
    logging.basicConfig(level=logging.WARNING, format="[log] %(name)s: %(message)s")
    from src.modules.tao_video_noi_dung import planner

    style = {"style_name": "Giấy gấp", "visual_rules": "Phong cách giấy gấp thống nhất: nền kem, xanh ngọc và xanh navy, vật liệu giấy.",
             "palette": ["kem", "xanh ngọc", "navy"], "aspect_ratio": "16:9", "diagram_only": not args.lai}
    env = read_env_file(Path(args.llm_env))
    client = GatewayClient(env["url"], env["api-key"], args.model)
    topics = [line.strip() for line in Path(args.chu_de_tep).read_text(encoding="utf-8").splitlines() if line.strip()]
    summary, layouts_all = ["# Tổng hợp kịch bản do LLM sinh", "", "| Chủ đề | Số shot | Loại cảnh | Cảnh báo |", "|---|---|---|---|"], Counter()
    for topic in topics:
        folder = out / slug(topic)
        folder.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        try:
            log(f"Chủ đề: {topic}")
            content = client.complete([{"role": "system", "content": SOURCE_RULES}, {"role": "user", "content": f"Chủ đề: {topic}"}], max_tokens=3000).content.strip()
            (folder / "noi_dung.txt").write_text(content, encoding="utf-8")
            storyboard, model_name = planner.generate_storyboard(content, args.thoi_luong, style, client)
            (folder / "storyboard.json").write_text(storyboard.model_dump_json(indent=1), encoding="utf-8")
            soft = planner._soft_problems(storyboard, "16:9", not args.lai)
            (folder / "kich_ban.md").write_text(script_markdown(topic, storyboard, soft), encoding="utf-8")
            layouts = [shot.ui_scene.layout if shot.ui_scene else shot.shot_kind for shot in storyboard.shots]
            layouts_all.update(set(layouts))
            summary.append(f"| {topic} | {len(layouts)} | {', '.join(layouts)} | {len(soft)} |")
            log(f"  xong sau {time.monotonic() - started:.0f} giây: {', '.join(layouts)}; cảnh báo: {len(soft)}")
        except Exception as exc:   # một chủ đề lỗi không dừng cả lô
            summary.append(f"| {topic} | lỗi | {type(exc).__name__}: {str(exc)[:160].replace(chr(10), ' ')} | - |")
            log(f"  LỖI: {type(exc).__name__}: {str(exc)[:300]}")
            (folder / "loi.txt").write_text(str(exc), encoding="utf-8")   # giữ nguyên thông báo đầy đủ để sửa prompt hoặc luật
    summary += ["", "Số kịch bản dùng từng loại cảnh: " + ", ".join(f"{name} {count}" for name, count in layouts_all.most_common()),
                f"Số loại cảnh khác nhau đã dùng: {len(layouts_all)} trên {len(planner.DIAGRAM_LAYOUTS)}"]
    (out / "tong_hop.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    log("XONG: " + str(out / "tong_hop.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
