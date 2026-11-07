"""Tạo một video hoàn chỉnh theo phong cách cảnh giấy, từ nội dung chữ tới MP4, không qua cơ sở dữ liệu và không dùng Flow.

Các bước (dùng đúng mã của pipeline, chỉ thay chỗ lưu trữ bằng thư mục):
  1. LLM sinh brief và storyboard ở chế độ diagram_only (planner.generate_storyboard).
  2. VieNeu sinh giọng từng shot (tiến trình riêng, tts_vieneu_rieng.py); kiểm giọng có phủ đủ hình (runner._check_voice_fits).
  3. Nhận dạng giọng từng shot, lấy mốc từng từ, quy về clip hình có tính tốc độ co giãn toàn video (như runner._diagram_word_times).
  4. Dựng từng cảnh giấy (render_engines.render_scene: playwright, hyperframes hoặc remotion) rồi ghép timeline, phụ đề karaoke theo mốc từ, giữ nguyên giọng (video_processor).
  5. Kiểm chất lượng (evaluate_video_qc cộng kiểm giọng-hình) và ghi báo cáo.

Dùng: python tao_video_canh_giay_tron_goi.py --noi-dung noi_dung.txt --ra <thu_muc> --llm-env <tệp có url và api-key> --vieneu-path <thư mục gói vieneu>
Khóa API đọc từ tệp, không in ra và không ghi vào đầu ra.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
sys.path[:0] = [str(ROOT), str(WORK), str(WORK / "cong_cu_tu_dong" / "flow_bridge")]


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class GatewayClient:
    """Cổng LLM tương thích OpenAI của dự án (cùng giao diện `complete` mà planner dùng)."""
    is_enabled = True
    max_output_tokens = 12000

    def __init__(self, url: str, key: str, model: str):
        self.url, self.key, self.model = url.rstrip("/"), key, model

    def complete(self, messages, max_tokens=None):
        import httpx

        started = time.monotonic()
        response = httpx.post(
            f"{self.url}/chat/completions", headers={"Authorization": f"Bearer {self.key}"}, timeout=600,
            json={"model": self.model, "messages": messages, "max_tokens": max_tokens or self.max_output_tokens, "temperature": 0.4},
        )
        response.raise_for_status()
        data = response.json()
        log(f"LLM trả lời trong {time.monotonic() - started:.0f} giây")
        return SimpleNamespace(content=data["choices"][0]["message"]["content"], model=data.get("model", self.model))


def read_env_file(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--noi-dung", required=True, help="Tệp chữ nội dung nguồn (không quá 12 KB)")
    parser.add_argument("--ra", required=True, help="Thư mục đầu ra")
    parser.add_argument("--llm-env", required=True, help="Tệp .env có url và api-key của cổng LLM")
    parser.add_argument("--model", default="cx/gpt-6-luna")
    parser.add_argument("--thoi-luong", type=int, default=90, help="Thời lượng mục tiêu (giây, bội của 10)")
    parser.add_argument("--vieneu-path", required=True, help="Thư mục đã cài gói vieneu (pip --target)")
    parser.add_argument("--giong", default="Hải Đăng")
    parser.add_argument("--giong-mau", help="Tệp WAV giọng mẫu để clone (ví dụ giọng Sếp); có thì dùng clone thay cho --giong")
    parser.add_argument("--ten-giong", default="", help="Tên giọng clone để ghi vào báo cáo (ví dụ Sếp); dạng @tệp thì đọc tên từ tệp UTF-8 (tránh lỗi mã hóa của cmd)")
    parser.add_argument("--storyboard", help="Dùng storyboard JSON có sẵn thay vì gọi LLM")
    parser.add_argument("--engine", default="playwright", choices=["playwright", "hyperframes", "remotion"], help="Engine dựng cảnh giấy (engine Node cần thư mục engines đã cài)")
    parser.add_argument("--dung-lai", action="store_true", help="Dùng lại storyboard.json và giọng đã có trong thư mục đầu ra")
    args = parser.parse_args()
    if args.ten_giong.startswith("@"):
        args.ten_giong = Path(args.ten_giong[1:]).read_text(encoding="utf-8").strip()

    import logging

    logging.basicConfig(level=logging.WARNING, format="[log] %(name)s: %(message)s")
    logging.getLogger("src.modules.tao_video_noi_dung.planner").setLevel(logging.INFO)
    out = Path(args.ra).resolve()
    (out / "canh").mkdir(parents=True, exist_ok=True)
    # Không động vào cơ sở dữ liệu thật: mọi đường dẫn lưu trữ trỏ vào thư mục đầu ra.
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{(out / 'tam.db').as_posix()}", "BAHA_AUTH_DATABASE_URL": f"sqlite:///{(out / 'tam_auth.db').as_posix()}",
        "SIN_DUNG_DB_PATH": str(out / "tam_dung.db"), "MEDIA_ROOT_DIR": str(out / "media"),
    })
    os.environ.setdefault("PRJ069_VIENU_HF_HOME", str(out / "vieneu_cache"))   # đặt sẵn biến này để dùng lại mô hình đã tải
    from src.modules.tao_video_noi_dung import planner, runner
    from src.modules.tao_video_noi_dung.render_engines import render_scene
    from src.modules.tao_video_noi_dung.brand import restore_display_words, to_spoken
    from src.modules.tao_video_noi_dung.vietsub import align_script_words, transcribe_words_cached
    from src.modules.media_studio.video_processor import fit_voice_speed, video_processor
    from src.schemas.contracts import TimelineAudioTrack, TimelineClip, TimelineDocument, TimelineMediaType

    style = {"style_name": "Giấy gấp", "visual_rules": "Phong cách giấy gấp thống nhất: nền kem, xanh ngọc và xanh navy, vật liệu giấy.",
             "palette": ["kem", "xanh ngọc", "navy"], "aspect_ratio": "16:9", "diagram_only": True, "render_engine": args.engine}

    # --- 1. kịch bản
    if args.storyboard or (args.dung_lai and (out / "storyboard.json").exists()):
        storyboard = planner.Storyboard.model_validate_json(Path(args.storyboard or out / "storyboard.json").read_text(encoding="utf-8"))
        model_name = "storyboard có sẵn"
    else:
        env = read_env_file(Path(args.llm_env))
        client = GatewayClient(env["url"], env["api-key"], args.model)
        content = Path(args.noi_dung).read_text(encoding="utf-8")
        log(f"Sinh storyboard từ {len(content)} ký tự nội dung, mục tiêu {args.thoi_luong} giây")
        storyboard, model_name = planner.generate_storyboard(content, args.thoi_luong, style, client)
    (out / "storyboard.json").write_text(storyboard.model_dump_json(indent=1), encoding="utf-8")
    shots = storyboard.shots
    bad = [shot.shot_id for shot in shots if not (shot.shot_kind == "UI_SIM" and shot.ui_scene and shot.ui_scene.layout in planner.DIAGRAM_LAYOUTS)]
    log(f"Storyboard {len(shots)} shot ({model_name}); loại cảnh: " + ", ".join(shot.ui_scene.layout for shot in shots if shot.ui_scene))
    if bad:
        log(f"DỪNG: shot không phải cảnh giấy dựng bằng mã: {bad}")
        return 2
    soft = planner._soft_problems(storyboard, "16:9", True)
    log("Cảnh báo storyboard: " + ("; ".join(soft) if soft else "không"))

    # --- 2. giọng
    texts = [{"id": shot.shot_id, "text": to_spoken(shot.narration)} for shot in shots]
    (out / "tts_vao.json").write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    if args.dung_lai and (out / "giong" / "ket_qua.json").exists():
        log("Dùng lại giọng đã sinh")
    else:
        log("Sinh giọng VieNeu (tiến trình riêng)")
        subprocess.run([sys.executable, str(Path(__file__).with_name("tts_vieneu_rieng.py")), str(out / "tts_vao.json"), str(out / "giong"), "--giong", args.giong, "--goi-path", args.vieneu_path, *(["--ref-audio", args.giong_mau] if args.giong_mau else [])],
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=True)
    tts = json.loads((out / "giong" / "ket_qua.json").read_text(encoding="utf-8"))
    import numpy as np

    rate = tts[shots[0].shot_id]["sample_rate"]

    def read_wav(path: Path):
        with wave.open(str(path), "rb") as wav:
            return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32767

    audios = [read_wav(out / "giong" / f"{shot.shot_id}.wav") for shot in shots]
    durations = [len(audio) / rate for audio in audios]
    # Mỗi cảnh giấy dài đúng bằng giọng của shot (cộng đệm), nên hình luôn khớp giọng; không có tua hình, không có đuôi im lặng.
    LEAD, TAIL = 0.15, 0.5
    clip_seconds = [min(20, max(4, int(-(-(duration + LEAD + TAIL) // 1)))) for duration in durations]
    if any(duration + LEAD + TAIL > 20 for duration in durations):
        log("DỪNG: có shot giọng dài hơn 19 giây, rút gọn lời của shot đó")
        return 3
    padded = []
    for audio, seconds in zip(audios, clip_seconds):
        padded.append(np.concatenate([np.zeros(round(LEAD * rate), dtype=np.float32), audio, np.zeros(round(seconds * rate) - round(LEAD * rate) - len(audio), dtype=np.float32)]))
    full = np.concatenate(padded)
    full_path = out / "giong" / "toan_bo.wav"
    with wave.open(str(full_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes((np.clip(full, -1, 1) * 32767).astype("<i2").tobytes())
    video_total = sum(clip_seconds)
    speed = fit_voice_speed(video_total, len(full) / rate)
    log(f"Giọng thật {sum(durations):.1f} giây; clip từng shot (giây): {clip_seconds}; tổng hình {video_total} giây; tốc độ hình {speed:.3f}")

    # --- 3. mốc từ từng shot rồi 4. dựng cảnh
    clips, paths, clip_start = [], {}, 0
    for index, shot in enumerate(shots):
        started = time.monotonic()
        words = to_spoken(shot.narration).split()   # căn mốc theo chữ đọc
        word_times = None
        try:
            asr = transcribe_words_cached(out / "giong" / f"{shot.shot_id}.wav", out / "cache" / f"{shot.shot_id}.json")
            aligned = align_script_words(words, asr)
            word_times = [LEAD + item["start_ms"] / 1000 for item in aligned]
        except Exception as error:
            log(f"  {shot.shot_id}: không có mốc từ ({type(error).__name__}), neo theo âm tiết")
        path = out / "canh" / f"{shot.shot_id}.mp4"
        if args.dung_lai and path.is_file() and path.stat().st_size > 20000:
            scene_meta = {"render_engine": "dùng lại clip đã dựng"}   # chạy lại sau khi bị ngắt: storyboard và giọng không đổi nên clip vẫn đúng
        else:
            scene_meta = render_scene(shot.ui_scene, style, clip_seconds[index], "16:9", path, narration=shot.narration, word_times=word_times)
        paths[shot.shot_id] = path
        times = planner.resolve_diagram_times(shot.ui_scene, shot.narration, clip_seconds[index], word_times)
        log(f"  {shot.shot_id} {shot.ui_scene.layout} ({clip_seconds[index]}s, giọng {durations[index]:.1f}s): dựng xong bằng {scene_meta['render_engine']} sau {time.monotonic() - started:.0f} giây; neo: " + ", ".join(f"{k}={v:.1f}" for k, v in times.items()))
        clips.append(TimelineClip(clip_id=shot.shot_id, asset_id=shot.shot_id, media_type=TimelineMediaType.VIDEO, start_ms=clip_start * 1000,
                                  duration_ms=clip_seconds[index] * 1000, trim_in_ms=0, trim_out_ms=clip_seconds[index] * 1000))
        clip_start += clip_seconds[index]

    # --- 5. phụ đề theo mốc từ cả video, ghép timeline
    display_text = " ".join(shot.narration for shot in shots)
    asr_all = transcribe_words_cached(full_path, out / "cache" / "toan_bo.json")
    # Căn theo chữ đọc (Ba-ha, Gờ-rúp) rồi trả về chữ hiển thị (BAHA, Group) cho phụ đề.
    aligned_all = restore_display_words(display_text.split(), align_script_words(to_spoken(display_text).split(), asr_all))
    captions = runner._karaoke_captions(aligned_all, 1080, 1920, speed)
    timeline = TimelineDocument(width=1920, height=1080, fps=30, clips=clips, voice_track=TimelineAudioTrack(asset_id="voice", duration_ms=round(len(full) / rate * 1000)), captions=captions)
    final = out / "video_hoan_chinh.mp4"
    log("Ghép timeline, phụ đề, giữ nguyên giọng")
    resolver = lambda asset_id: full_path if asset_id == "voice" else paths[asset_id]
    render_meta = video_processor.render_timeline_document(timeline, resolver, final, transition_seconds=0.3, caption_style="vietsub_karaoke_v2", preserve_voice_audio=True)

    # --- 6. kiểm chất lượng
    meta = video_processor.probe_video(final)
    for key in ("video_playback_speed", "video_content_duration_seconds", "voice_audio_duration_seconds", "silent_tail_seconds", "frozen_tail_seconds"):
        if key in render_meta:
            meta[key] = render_meta[key]
    decode = subprocess.run([video_processor.ffmpeg_bin, "-v", "error", "-i", str(final), "-f", "null", "-"], capture_output=True, text=True)
    issues = runner.evaluate_video_qc(meta, render_meta.get("duration_seconds", video_total), decode.returncode == 0 and not decode.stderr.strip(), aspect_ratio="16:9")
    if max(meta.get("silent_tail_seconds", 0), meta.get("frozen_tail_seconds", 0)) > 1.0:
        issues.append("VOICE_VIDEO_DURATION_MISMATCH")
    sha = hashlib.sha256(final.read_bytes()).hexdigest()
    report = {"trang_thai": "ĐẠT" if not issues else "KHÔNG ĐẠT", "loi": issues, "mo_hinh_llm": model_name, "so_shot": len(shots), "giong": (args.ten_giong or args.giong) + (" (clone từ giọng mẫu)" if args.giong_mau else ""), "thoi_luong_giong_giay": round(sum(durations), 2), "clip_tung_shot_giay": clip_seconds,
              "thoi_luong_video_giay": meta.get("duration_seconds"), "toc_do_hinh": round(speed, 4), "sha256": sha, "do_ro_phu_de": len(captions), "meta": meta}
    (out / "bao_cao_kiem_tra.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"XONG: {final} | {report['trang_thai']} | lỗi: {issues or 'không'} | video {meta.get('duration_seconds')} giây, giọng {sum(durations):.2f} giây")
    return 0 if not issues else 4


if __name__ == "__main__":
    sys.exit(main())
