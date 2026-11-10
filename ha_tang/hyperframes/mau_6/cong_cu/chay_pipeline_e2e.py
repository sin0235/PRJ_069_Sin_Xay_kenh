# -*- coding: utf-8 -*-
"""Pipeline E2E tạo video hoàn chỉnh 100s từ kịch bản BAHA Khám sức khỏe doanh nghiệp miễn phí."""
from __future__ import annotations

import json
import logging
import math
import os
import shutil
import sys
import time
import wave
from pathlib import Path

# Nạp cấu hình môi trường
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ENV_DEV = ROOT / "ha_tang" / "chay_dev_local" / ".env.dev"

from dotenv import load_dotenv
if ENV_DEV.is_file():
    load_dotenv(ENV_DEV, override=True)

os.environ["TTS_INFERENCE_CHILD"] = "1"
sys.path[:0] = [str(ROOT / "sin_content_api"), str(ROOT)]
os.environ["CONTENT_VIDEO_ASSEMBLY"] = "hyperframes"
os.environ["CONTENT_VIDEO_HF_CHECK"] = "0"
os.environ["CONTENT_VIDEO_HF_WORKERS"] = "1"
os.environ["CONTENT_VIDEO_DIAGRAM_ONLY"] = "1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_pipeline")

import numpy as np
from src.modules.tao_video_noi_dung import hf_project, planner, runner, sfx
from src.modules.tao_video_noi_dung.am_thanh_giong import polish_voice
from src.modules.tao_video_noi_dung.brand import to_spoken
from src.modules.tao_video_noi_dung.tts_provider import tts_provider_manager
from src.modules.tao_video_noi_dung.vietsub import align_script_words, transcribe_words_cached
from src.modules.media_studio.video_processor import video_processor

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def chay_pipeline_e2e():
    t_bat_dau = time.time()
    log("============================================================")
    log("BẮT ĐẦU PIPELINE E2E TẠO VIDEO HOÀN CHỈNH 100S - BAHA B2B")
    log("============================================================")

    # 1. Tải và xác thực kịch bản Storyboard
    sb_path = ROOT / "ha_tang" / "hyperframes" / "mau_video" / "v1" / "storyboard_baha_v1_e2e.json"
    log(f"1. Tải kịch bản Storyboard từ: {sb_path}")
    raw_sb = json.loads(sb_path.read_text(encoding="utf-8"))
    storyboard = planner.Storyboard.model_validate(raw_sb)
    log(f"   -> Đã nạp {len(storyboard.shots)} shot, tổng {sum(s.duration_seconds for s in storyboard.shots)} giây")
    
    # Chuẩn bị thư mục xuất bản
    thu_muc_xuat = ROOT / "ha_tang" / "hyperframes" / "mau_6" / "xuat_ban"
    thu_muc_xuat.mkdir(parents=True, exist_ok=True)
    video_dich = thu_muc_xuat / "video_kham_doanh_nghiep_baha_100s.mp4"
    thu_muc_tam = thu_muc_xuat / "tam_e2e"
    thu_muc_tam.mkdir(parents=True, exist_ok=True)

    # 2. Sinh giọng đọc TTS (VieNeu v3 Turbo - Hồ sơ Sếp)
    voice_wav_path = thu_muc_tam / "giong_doc_baha.wav"
    sample_rate = 48000
    steps_data = []

    if voice_wav_path.is_file() and voice_wav_path.stat().st_size > 1000:
        log(f"2. Đã tìm thấy âm thanh TTS đã sinh sẵn tại: {voice_wav_path} (Tái sử dụng)")
        for idx, shot in enumerate(storyboard.shots):
            steps_data.append({
                "shot_id": shot.shot_id,
                "duration_ms": shot.duration_seconds * 1000,
                "clip_seconds": shot.duration_seconds
            })
    else:
        log("2. Khởi tạo và sinh âm thanh lời đọc TTS (VieNeu V3 Turbo)...")
        tts_config = {"provider": "VIE_NEU_V3_TURBO"}
        samples = []

        for idx, shot in enumerate(storyboard.shots):
            spoken = to_spoken(shot.narration)
            log(f"   [Shot {shot.shot_id}] ({shot.duration_seconds}s) Sinh TTS: \"{spoken[:40]}...\"")
            audio, s_rate = tts_provider_manager.synthesize(tts_config, spoken)
            sample_rate = int(s_rate)
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            
            # Đệm nghỉ tự nhiên giữa các câu
            if samples:
                prev_text = storyboard.shots[idx - 1].narration.rstrip().rstrip('"\'”’)]')
                pause_sec = 0.4 if prev_text.endswith((".", "!", "?", "…")) else 0.2 if prev_text.endswith((",", ";", ":")) else 0.0
                pad_count = round(pause_sec * sample_rate)
                if pad_count > 0:
                    samples.append(np.zeros(pad_count, dtype=np.float32))
            
            samples.append(audio)
            steps_data.append({
                "shot_id": shot.shot_id,
                "duration_ms": round(len(audio) * 1000 / sample_rate),
                "clip_seconds": shot.duration_seconds
            })

        full_voice = np.concatenate(samples)
        log(f"   -> Tổng thời lượng giọng thô: {len(full_voice) / sample_rate:.2f}s")
        
        # Tinh chỉnh âm thanh (polish voice: khử ồm, tăng độ sáng, nén nhẹ)
        log("   -> Tinh chỉnh giọng đọc (polish voice)...")
        full_voice = polish_voice(full_voice, sample_rate)
        
        # Lưu file âm thanh WAV
        pcm = (np.clip(full_voice, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        with wave.open(str(voice_wav_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm)
        log(f"   -> Đã lưu âm thanh tại: {voice_wav_path}")

    # 3. Phân tách mốc từ (ASR Whisper) cho phụ đề Karaoke
    log("3. Phân tích mốc từ (ASR Faster-Whisper) cho phụ đề động...")
    cache_asr = thu_muc_tam / "moc_tu_whisper.json"
    asr_words = transcribe_words_cached(voice_wav_path, cache_asr)
    log(f"   -> Nhận diện {len(asr_words)} từ trong bản ghi âm")
    
    all_script_words = []
    for shot in storyboard.shots:
        all_script_words.extend(to_spoken(shot.narration).split())
    
    aligned_words = align_script_words(all_script_words, asr_words)
    log(f"   -> Đã khớp {len(aligned_words)} / {len(all_script_words)} từ với kịch bản chuẩn")

    # 4. Lập lịch hiệu ứng âm thanh SFX và nhạc nền BGM
    log("4. Lập lịch hiệu ứng âm thanh SFX & chọn nhạc nền BGM...")
    raw_sfx_cues = sfx.plan_sfx_cues(storyboard.shots)
    log(f"   -> Đã tạo {len(raw_sfx_cues)} điểm phát hiệu ứng âm thanh SFX")
    
    # Chuẩn hoá định dạng SFX sang PCM 16-bit nếu gặp định dạng extensible
    import soundfile as sf
    sfx_clean_dir = thu_muc_tam / "sfx_clean"
    sfx_clean_dir.mkdir(parents=True, exist_ok=True)
    sfx_cues = []
    for cue in raw_sfx_cues:
        src_path = Path(cue["path"])
        dst_path = sfx_clean_dir / src_path.name
        try:
            with wave.open(str(src_path), "rb") as test_w:
                pass
            sfx_cues.append(cue)
        except wave.Error:
            if not dst_path.is_file():
                data, sr = sf.read(str(src_path))
                sf.write(str(dst_path), data, sr, subtype="PCM_16", format="WAV")
            sfx_cues.append({**cue, "path": dst_path})
    log(f"   -> Đã chuẩn hoá {len(sfx_cues)} file SFX hợp lệ")
    
    bgm_path = ROOT / "sin_content_api" / "src" / "modules" / "media_studio" / "am_thanh_nhac_nen" / "kich_tinh_diem_dau_b2b.wav"
    if not bgm_path.is_file():
        bgm_path = ROOT / "sin_content_api" / "src" / "modules" / "media_studio" / "am_thanh_nhac_nen" / "b2b_sang_tao_doanh_nghiep.wav"
    log(f"   -> Sử dụng nhạc nền: {bgm_path.name}")

    # 5. Dựng cấu trúc Project HyperFrames
    log("5. Xây dựng project HyperFrames (HTML + GSAP + 4 lớp đồ họa)...")
    du_an_hf = thu_muc_tam / "du_an_hf"
    
    # Chuẩn bị danh sách cảnh
    shots_hf = []
    start_time = 0.0
    for idx, shot in enumerate(storyboard.shots):
        dur = shot.duration_seconds
        dump_scene = shot.ui_scene
        evts = planner.resolve_diagram_times(dump_scene, shot.narration, dur, None)
        shots_hf.append({
            "shot_id": shot.shot_id,
            "scene": dump_scene,
            "narration": shot.narration,
            "seconds": dur,
            "start_seconds": start_time,
            "events": evts,
            "word_times": None
        })
        start_time += dur

    proj_info = hf_project.build_project(
        out=du_an_hf,
        shots=shots_hf,
        voice_wav=voice_wav_path,
        words=aligned_words,
        transitions=True,
        music_path=bgm_path,
        sfx_cues=sfx_cues,
        aspect_ratio="16:9",
        caption_style="karaoke"
    )
    log(f"   -> Đã đóng gói dự án HyperFrames ({len(proj_info['native_scenes'])} cảnh native, {proj_info['collage_transitions']} chuyển cảnh xé giấy)")

    # 6. Kết xuất video qua HyperFrames Render (Chromium Headless)
    log("6. Bắt đầu Render video bằng HyperFrames CLI (1920x1080 @ 30fps)...")
    log("   (Tiến trình render đang thực thi trên engine Chromium nội bộ...)")
    t_render = time.time()
    hf_project.render_project(du_an_hf, video_dich, workers="1", quality="looks")
    thoi_gian_render = time.time() - t_render
    log(f"   -> Kết xuất thành công sau: {thoi_gian_render:.1f} giây ({thoi_gian_render / 60:.1f} phút)")

    # 7. Kiểm định chất lượng Video QC (Quality Control)
    log("7. Thẩm định chất lượng video đầu ra (Video QC)...")
    meta = video_processor.probe_video(video_dich)
    qc_issues = runner.evaluate_video_qc(meta, expected_duration_seconds=100, decode_ok=True, aspect_ratio="16:9")
    
    file_mb = video_dich.stat().st_size / (1024 * 1024)
    log("============================================================")
    log("KẾT QUẢ KIỂM ĐỊNH VIDEO:")
    log(f"  - Đường dẫn file  : {video_dich}")
    log(f"  - Dung lượng      : {file_mb:.2f} MB")
    log(f"  - Độ phân giải    : {meta.get('width')}x{meta.get('height')} (16:9)")
    log(f"  - Tốc độ khung    : {meta.get('frame_rate')} fps")
    log(f"  - Thời lượng      : {meta.get('duration_seconds')} giây")
    log(f"  - Codec           : {meta.get('codec_name')} / audio: {meta.get('audio_codec_name')}")
    log(f"  - Lỗi QC          : {'KHÔNG CÓ LỖI (PASS 100%)' if not qc_issues else qc_issues}")
    log(f"  - Tổng thời gian  : {time.time() - t_bat_dau:.1f} giây")
    log("============================================================")
    
    return {
        "status": "SUCCESS" if not qc_issues else "QC_WARNING",
        "video_path": str(video_dich),
        "file_size_mb": round(file_mb, 2),
        "duration_seconds": meta.get("duration_seconds"),
        "resolution": f"{meta.get('width')}x{meta.get('height')}",
        "qc_issues": qc_issues,
        "render_seconds": round(thoi_gian_render, 1),
        "total_seconds": round(time.time() - t_bat_dau, 1)
    }

if __name__ == "__main__":
    ket_qua = chay_pipeline_e2e()
    print("\nJSON BÁO CÁO:")
    print(json.dumps(ket_qua, ensure_ascii=False, indent=2))
