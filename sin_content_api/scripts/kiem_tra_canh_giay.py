"""Chạy thử cảnh giấy với giọng thật trong container worker.

Làm gì: đọc lời đọc mẫu của một loại cảnh, sinh giọng bằng bộ TTS đã cấu hình (hoặc dùng tệp WAV có sẵn), nhận dạng mốc từng từ,
so mốc sự kiện theo ASR với mốc ước theo âm tiết, dựng một video cảnh giấy ngắn và in kết quả. Không ghi vào cơ sở dữ liệu.

Dùng (trong terminal của container worker):
    python /app/scripts/kiem_tra_canh_giay.py --layout COMPARE_DOCS
    python /app/scripts/kiem_tra_canh_giay.py --layout COST_SLICE --wav /data/media_assets/giong_mau.wav
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import wave
from pathlib import Path

from src.modules.media_studio.security import MEDIA_ROOT_DIR
from src.modules.tao_video_noi_dung.planner import UiScene, resolve_diagram_times
from src.modules.tao_video_noi_dung.ui_sim import render_ui_scene
from src.modules.tao_video_noi_dung.vietsub import align_script_words, transcribe_words_cached

# Cùng dữ liệu với các ca test (tests/test_content_video_pipeline.py::_DIAGRAM_CASES), để so với kết quả test trên máy dev.
CASES = {
    "COMPARE_DOCS": (
        "Một tài liệu ghi bảy mươi phần trăm. Tài liệu khác lại ghi sáu mươi lăm phần trăm. Hai con số chênh nhau năm điểm, cần xác minh.",
        dict(title="Đối chiếu", docs=[{"title": "Hợp đồng", "label": "Tỷ lệ", "value": "70%"}, {"title": "Biên bản", "label": "Tỷ lệ", "value": "65%"}],
             diff_label="Chênh 5 điểm", stamp="ĐANG XÁC MINH",
             on={"doc0": "Một tài liệu", "v0": "bảy mươi", "doc1": "Tài liệu khác", "v1": "sáu mươi lăm", "thread": "chênh nhau", "label": "năm điểm", "stamp": "xác minh"}),
    ),
    "COST_SLICE": (
        "Đơn bán một triệu đồng. Trừ giá vốn sáu trăm nghìn, phí vận chuyển một trăm năm mươi nghìn. Lãi thật còn hai trăm năm mươi nghìn.",
        dict(title="Lãi thật của đơn hàng", unit="nghìn", total=1000, total_label="đơn hàng", final_label="Lãi thật",
             slices=[{"label": "Giá vốn", "value": 600}, {"label": "Phí vận chuyển", "value": 150}], on={"d0": "giá vốn", "d1": "phí vận chuyển", "final": "lãi thật"}),
    ),
    "PROCESS_RAIL": (
        "Hồ sơ đi qua bốn bước tiếp nhận duyệt giao việc hoàn tất. Bước duyệt đang nghẽn nên hồ sơ dồn lại. Khi gỡ nghẽn hồ sơ chảy tiếp.",
        dict(title="Hồ sơ đi qua bốn bước", steps=["Tiếp nhận", "Duyệt", "Giao việc", "Hoàn tất"], block_step=1,
             on={"stations": "bốn bước", "block": "đang nghẽn", "release": "gỡ nghẽn"}),
    ),
}


def synthesize_wav(narration: str, out: Path, provider: str) -> float:
    import numpy as np

    from src.modules.tao_video_noi_dung.tts_provider import tts_provider_manager

    audio, rate = tts_provider_manager.synthesize({"provider": provider}, narration, None)
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    with wave.open(str(out), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(rate))
        wav.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes())
    return len(audio) / rate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--layout", choices=sorted(CASES), default="COMPARE_DOCS")
    parser.add_argument("--wav", help="Tệp WAV giọng đọc có sẵn của đúng lời mẫu; bỏ trống để sinh bằng TTS")
    parser.add_argument("--provider", default="VIE_NEU_V3_TURBO", help="Bộ TTS khi không có --wav")
    parser.add_argument("--duration", type=int, default=10, help="Thời lượng clip hình (giây, 1 đến 10)")
    args = parser.parse_args()

    narration, spec = CASES[args.layout]
    scene = UiScene(layout=args.layout, diagram=spec)
    out_dir = MEDIA_ROOT_DIR / "_kiem_tra_canh_giay"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kt_canh_giay_") as tmp:
        wav_path = Path(args.wav) if args.wav else Path(tmp) / "giong.wav"
        started = time.monotonic()
        if not args.wav:
            voice_seconds = synthesize_wav(narration, wav_path, args.provider)
            print(f"TTS: {voice_seconds:.2f} giây giọng trong {time.monotonic() - started:.1f} giây")
        started = time.monotonic()
        asr_words = transcribe_words_cached(wav_path, out_dir / "cache_asr.json")
        words = narration.split()
        aligned = align_script_words(words, asr_words)
        print(f"ASR và căn chỉnh: {len(asr_words)} từ nhận dạng, {len(aligned)} từ lời, {time.monotonic() - started:.1f} giây")
    voice_total = aligned[-1]["end_ms"] / 1000
    # Một shot đơn lẻ: giọng bắt đầu ở giây 0 của clip hình và tốc độ co giãn 1,0 (khác pipeline thật có nhiều shot).
    asr_times = [item["start_ms"] / 1000 for item in aligned]
    by_asr = resolve_diagram_times(scene, narration, args.duration, asr_times)
    by_ratio = resolve_diagram_times(scene, narration, args.duration)
    print(f"\nGiọng dài {voice_total:.2f} giây; clip hình {args.duration} giây")
    print(f"{'sự kiện':<10}{'theo ASR':>10}{'theo âm tiết':>14}{'lệch':>8}")
    worst = 0.0
    for key, value in by_asr.items():
        diff = value - by_ratio[key]
        worst = max(worst, abs(diff))
        print(f"{key:<10}{value:>10.2f}{by_ratio[key]:>14.2f}{diff:>+8.2f}")
    output = out_dir / f"{args.layout}_{int(time.time())}.mp4"
    started = time.monotonic()
    meta = render_ui_scene(scene, {}, args.duration, "16:9", output, narration=narration, word_times=asr_times)
    print(f"\nDựng video: {output} ({output.stat().st_size} byte, {meta['duration_seconds']:.2f} giây, {meta['width']}x{meta['height']}) trong {time.monotonic() - started:.1f} giây")
    print(json.dumps({"layout": args.layout, "lech_toi_da_giay": round(worst, 2), "video": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
