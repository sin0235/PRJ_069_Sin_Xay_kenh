"""Sinh giọng VieNeu v3 Turbo (ONNX, CPU) cho một danh sách đoạn lời; chạy ở tiến trình riêng để không trộn gói với tiến trình chính.

Dùng:  python tts_vieneu_rieng.py <vao.json> <thu_muc_ra> [--giong "Hải Đăng"] [--luong 4] [--goi-path <thư mục gói>]
vao.json: [{"id": "s1", "text": "..."}, ...]; ra: <id>.wav (PCM 16 bit, mono) và ket_qua.json (thời lượng từng đoạn).
Tham số suy luận giống src/modules/tao_video_noi_dung/tts_provider.py (_load_vieneu và _infer).
"""
from __future__ import annotations

import argparse
import json
import os
import time
import wave
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vao")
    parser.add_argument("ra")
    parser.add_argument("--giong", default="Hải Đăng")
    parser.add_argument("--luong", type=int, default=4)
    parser.add_argument("--goi-path", help="Thư mục chứa gói vieneu (Python nhúng bỏ qua PYTHONPATH)")
    parser.add_argument("--ref-audio", help="Tệp giọng mẫu (WAV) để clone; có thì bỏ qua --giong (giống tts_provider._infer của v3turbo)")
    args = parser.parse_args()
    if args.goi_path:
        import sys
        sys.path.insert(0, args.goi_path)

    cache_home = Path(os.environ.get("PRJ069_VIENU_HF_HOME") or Path.home() / ".cache" / "prj069-vieneu").expanduser()
    os.environ["HF_HOME"] = str(cache_home)
    os.environ["HF_HUB_CACHE"] = str(cache_home / "hub")
    os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"
    import numpy as np
    from vieneu import Vieneu

    items = json.loads(Path(args.vao).read_text(encoding="utf-8"))
    out_dir = Path(args.ra)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    model = Vieneu(mode="v3turbo", device="cpu", backend="onnx", precision="fp32", threads=args.luong)
    print(f"Nạp mô hình: {time.monotonic() - started:.1f} giây", flush=True)
    results = {}
    for item in items:
        started = time.monotonic()
        voice_options = {"ref_audio": args.ref_audio} if args.ref_audio else {"voice": args.giong}
        audio = model.infer(
            item["text"], **voice_options, denoise=False, use_ref_codes=True, temperature=0.8, top_k=25, top_p=0.95,
            max_new_frames=300, repetition_penalty=1.2, max_chars=128,
        )
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        rate = int(model.sample_rate)
        if not samples.size or not np.isfinite(samples).all():
            raise SystemExit(f"TTS_AUDIO_INVALID: {item['id']}")
        with wave.open(str(out_dir / f"{item['id']}.wav"), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes((np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes())
        results[item["id"]] = {"duration_seconds": len(samples) / rate, "sample_rate": rate}
        print(f"{item['id']}: {len(samples) / rate:.2f} giây giọng trong {time.monotonic() - started:.1f} giây", flush=True)
    (out_dir / "ket_qua.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
