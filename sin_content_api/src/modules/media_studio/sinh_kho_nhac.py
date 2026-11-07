# -*- coding: utf-8 -*-
"""
Script khởi tạo Thư viện Nhạc nền có sẵn chuẩn hóa (15 bản nhạc BGM, 48kHz Stereo, -16 LUFS)
cho dự án PRJ_069_Sin_Xay_kenh.
Bản quyền: NỘI BỘ DỰ ÁN (INTERNAL_OWNED) & BẢN QUYỀN THƯƠNG MẠI AN TOÀN 100% TIKTOK.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(__file__).resolve().parent / "am_thanh_nhac_nen"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = OUTPUT_DIR / "BANG_KE_BAN_QUYEN_NHAC_NEN.json"

SAMPLE_RATE = 48000

# Bảng tần số nốt nhạc chuẩn (Hz)
NOTE_FREQS = {
    "C2": 65.41, "D2": 73.42, "Eb2": 77.78, "E2": 82.41, "F2": 87.31, "F#2": 92.50, "G2": 98.00, "Ab2": 103.83, "A2": 110.00, "Bb2": 116.54, "B2": 123.47,
    "C3": 130.81, "C#3": 138.59, "D3": 146.83, "Eb3": 155.56, "E3": 164.81, "F3": 174.61, "F#3": 185.00, "G3": 196.00, "Ab3": 207.65, "A3": 220.00, "Bb3": 233.08, "B3": 246.94,
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "Eb4": 311.13, "E4": 329.63, "F4": 349.23, "F#4": 369.99, "G4": 392.00, "Ab4": 415.30, "A4": 440.00, "Bb4": 466.16, "B4": 493.88,
    "C5": 523.25, "C#5": 554.37, "D5": 587.33, "Eb5": 622.25, "E5": 659.25, "F5": 698.46, "F#5": 739.99, "G5": 783.99, "Ab5": 830.61, "A5": 880.00, "Bb5": 932.33, "B5": 987.77,
}

TRACK_SPECS = [
    # 1. Chuyên nghiệp B2B
    {
        "id": "b2b_cong_nghe_so",
        "ten": "Công Nghệ Số B2B",
        "danh_muc": "chuyen_nghiep_b2b",
        "nhan_dien_tam_trang": "Tập trung, hiện đại, số hóa",
        "bpm": 104,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("Fm", "F2", ["F3", "Ab3", "C4", "Eb4"]),
            ("Db", "Db2", ["Db3", "F3", "Ab3", "C4"]),
            ("Ab", "Ab2", ["Ab3", "C4", "Eb4", "G4"]),
            ("Eb", "Eb2", ["Eb3", "G3", "Bb3", "D4"]),
        ],
        "kieu_nhip": "pulse",
    },
    {
        "id": "b2b_chuyen_nghiep_hien_dai",
        "ten": "Chuyên Nghiệp Hiện Đại",
        "danh_muc": "chuyen_nghiep_b2b",
        "nhan_dien_tam_trang": "Gọn gàng, tin cậy, chuẩn mực",
        "bpm": 108,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("C", "C2", ["C3", "E3", "G3", "B3"]),
            ("G", "G2", ["G3", "B3", "D4", "F4"]),
            ("Am", "A2", ["A3", "C4", "E4", "G4"]),
            ("F", "F2", ["F3", "A3", "C4", "E4"]),
        ],
        "kieu_nhip": "arp",
    },
    {
        "id": "b2b_sang_tao_doanh_nghiep",
        "ten": "Sáng Tạo Doanh Nghiệp",
        "danh_muc": "chuyen_nghiep_b2b",
        "nhan_dien_tam_trang": "Đổi mới, bứt phá, giải pháp",
        "bpm": 112,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("Dm", "D2", ["D3", "F3", "A3", "C4"]),
            ("Bb", "Bb2", ["Bb3", "D4", "F4", "A4"]),
            ("F", "F2", ["F3", "A3", "C4", "E4"]),
            ("C", "C2", ["C3", "E3", "G3", "B3"]),
        ],
        "kieu_nhip": "piano_pulse",
    },
    # 2. Năng lượng bắt nhịp
    {
        "id": "upbeat_nhip_nhanh",
        "ten": "Nhịp Nhanh Bắt Mắt",
        "danh_muc": "nang_luong_bat_nhip",
        "nhan_dien_tam_trang": "Sôi động, kích thích tương tác",
        "bpm": 124,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("G", "G2", ["G3", "B3", "D4", "F#4"]),
            ("D", "D2", ["D3", "F#3", "A3", "C4"]),
            ("Em", "E2", ["E3", "G3", "B3", "D4"]),
            ("C", "C2", ["C3", "E3", "G3", "B3"]),
        ],
        "kieu_nhip": "dance_beat",
    },
    {
        "id": "upbeat_bat_trend_hook",
        "ten": "Bắt Trend 3 Giây Vàng",
        "danh_muc": "nang_luong_bat_nhip",
        "nhan_dien_tam_trang": "Giữ chân, dồn dập, sắc nét",
        "bpm": 126,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("Am", "A2", ["A3", "C4", "E4", "G4"]),
            ("F", "F2", ["F3", "A3", "C4", "E4"]),
            ("C", "C2", ["C3", "E3", "G3", "B3"]),
            ("G", "G2", ["G3", "B3", "D4", "F4"]),
        ],
        "kieu_nhip": "hook_synth",
    },
    {
        "id": "upbeat_soi_dong_tich_cuc",
        "ten": "Sôi Động Tích Cực",
        "danh_muc": "nang_luong_bat_nhip",
        "nhan_dien_tam_trang": "Lạc quan, thúc đẩy hành động",
        "bpm": 120,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("E", "E2", ["E3", "G#3", "B3", "D#4"]),
            ("B", "B2", ["B3", "D#4", "F#4", "A4"]),
            ("C#m", "C#3", ["C#3", "E3", "G#3", "B3"]),
            ("A", "A2", ["A3", "C#4", "E4", "G#4"]),
        ],
        "kieu_nhip": "dance_beat",
    },
    # 3. Tâm sự kể chuyện
    {
        "id": "lofi_tam_su_dem",
        "ten": "Lo-Fi Tâm Sự Đêm",
        "danh_muc": "tam_su_ke_chuyen",
        "nhan_dien_tam_trang": "Sâu lắng, ấm cúng, trải lòng",
        "bpm": 80,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("Ebmaj7", "Eb2", ["Eb3", "G3", "Bb3", "D4"]),
            ("Cm7", "C2", ["C3", "Eb3", "G3", "Bb3"]),
            ("Fm7", "F2", ["F3", "Ab3", "C4", "Eb4"]),
            ("Bb7", "Bb2", ["Bb3", "D4", "F4", "Ab4"]),
        ],
        "kieu_nhip": "lofi_chill",
    },
    {
        "id": "lofi_chill_am_ap",
        "ten": "Lo-Fi Chill Ấm Áp",
        "danh_muc": "tam_su_ke_chuyen",
        "nhan_dien_tam_trang": "Thư giãn, nhẹ nhàng, podcast",
        "bpm": 84,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("Cmaj7", "C2", ["C3", "E3", "G3", "B3"]),
            ("Am7", "A2", ["A3", "C4", "E4", "G4"]),
            ("Dm7", "D2", ["D3", "F3", "A3", "C4"]),
            ("G7", "G2", ["G3", "B3", "D4", "F4"]),
        ],
        "kieu_nhip": "lofi_chill",
    },
    {
        "id": "lofi_dong_chay_suy_ngam",
        "ten": "Dòng Chảy Suy Ngẫm",
        "danh_muc": "tam_su_ke_chuyen",
        "nhan_dien_tam_trang": "Trầm tư, bài học kinh nghiệm",
        "bpm": 78,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("Bbm7", "Bb2", ["Bb3", "Db4", "F4", "Ab4"]),
            ("Gbmaj7", "F#2", ["Gb3", "Bb3", "Db4", "F4"]),
            ("Ebm7", "Eb2", ["Eb3", "Gb3", "Bb3", "Db4"]),
            ("F7", "F2", ["F3", "A3", "C4", "Eb4"]),
        ],
        "kieu_nhip": "lofi_chill",
    },
    # 4. Kịch tính cảnh báo
    {
        "id": "kich_tinh_canh_bao_rui_ro",
        "ten": "Cảnh Báo Rủi Ro",
        "danh_muc": "kich_tinh_canh_bao",
        "nhan_dien_tam_trang": "Cảnh giác, áp lực, khẩn cấp",
        "bpm": 100,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("Dm", "D2", ["D3", "F3", "A3", "D4"]),
            ("Dm/C", "C2", ["D3", "F3", "A3", "C4"]),
            ("Bb", "Bb2", ["Bb3", "D4", "F4", "Bb4"]),
            ("A", "A2", ["A3", "C#4", "E4", "A4"]),
        ],
        "kieu_nhip": "tense_drone",
    },
    {
        "id": "kich_tinh_diem_dau_b2b",
        "ten": "Điểm Đau Vận Hành",
        "danh_muc": "kich_tinh_canh_bao",
        "nhan_dien_tam_trang": "Vấn đề tồn tại, nghẽn dòng",
        "bpm": 96,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("Bm", "B2", ["B3", "D4", "F#4", "B4"]),
            ("G", "G2", ["G3", "B3", "D4", "G4"]),
            ("Em", "E2", ["E3", "G3", "B3", "E4"]),
            ("F#", "F#2", ["F#3", "A#3", "C#4", "F#4"]),
        ],
        "kieu_nhip": "tense_drone",
    },
    {
        "id": "kich_tinh_hoi_hop_truoc_sau",
        "ten": "Hồi Hộp Trước Sau",
        "danh_muc": "kich_tinh_canh_bao",
        "nhan_dien_tam_trang": "So sánh Before/After, kịch tính",
        "bpm": 104,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("F#m", "F#2", ["F#3", "A3", "C#4", "F#4"]),
            ("D", "D2", ["D3", "F#3", "A3", "D4"]),
            ("Bm", "B2", ["B3", "D4", "F#4", "B4"]),
            ("C#", "C#2", ["C#3", "F3", "G#3", "C#4"]),
        ],
        "kieu_nhip": "tense_drone",
    },
    # 5. Truyền cảm hứng
    {
        "id": "cam_hung_vuon_tam",
        "ten": "Vươn Tầm Khát Vọng",
        "danh_muc": "truyen_cam_hung",
        "nhan_dien_tam_trang": "Hùng tráng, mở rộng, tầm nhìn",
        "bpm": 100,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("A", "A2", ["A3", "C#4", "E4", "A4"]),
            ("E", "E2", ["E3", "G#3", "B3", "E4"]),
            ("F#m", "F#2", ["F#3", "A3", "C#4", "F#4"]),
            ("D", "D2", ["D3", "F#3", "A3", "D4"]),
        ],
        "kieu_nhip": "inspirational_swell",
    },
    {
        "id": "cam_hung_khoi_nghiep_thanh_cong",
        "ten": "Khởi Nghiệp Thành Công",
        "danh_muc": "truyen_cam_hung",
        "nhan_dien_tam_trang": "Tự hào, tích cực, đích đến",
        "bpm": 108,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("C", "C2", ["C3", "E3", "G3", "C4"]),
            ("Em", "E2", ["E3", "G3", "B3", "E4"]),
            ("F", "F2", ["F3", "A3", "C4", "F4"]),
            ("G", "G2", ["G3", "B3", "D4", "G4"]),
        ],
        "kieu_nhip": "inspirational_swell",
    },
    {
        "id": "cam_hung_tu_hao_dong_doi",
        "ten": "Tự Hào Đồng Đội",
        "danh_muc": "truyen_cam_hung",
        "nhan_dien_tam_trang": "Gắn kết, chung sức, phát triển",
        "bpm": 98,
        "thoi_luong_giay": 32,
        "am_luong_mac_dinh_db": -18.0,
        "hop_am": [
            ("G", "G2", ["G3", "B3", "D4", "G4"]),
            ("Bm", "B2", ["B3", "D4", "F#4", "B4"]),
            ("C", "C2", ["C3", "E3", "G3", "C4"]),
            ("D", "D2", ["D3", "F#3", "A3", "D4"]),
        ],
        "kieu_nhip": "inspirational_swell",
    },
]


def _note_to_freq(note_name: str) -> float:
    return NOTE_FREQS.get(note_name, 220.0)


def _synthesize_oscillator(freq: float, duration_sec: float, wave_type: str = "sine") -> np.ndarray:
    t = np.linspace(0, duration_sec, int(SAMPLE_RATE * duration_sec), endpoint=False)
    if wave_type == "sine":
        return np.sin(2 * np.pi * freq * t)
    elif wave_type == "triangle":
        return 2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1
    elif wave_type == "soft_saw":
        # Additive soft sawtooth (first 5 harmonics)
        sig = np.sin(2 * np.pi * freq * t)
        for h in range(2, 6):
            sig += (1.0 / h) * np.sin(2 * np.pi * freq * h * t) * (0.6 ** h)
        return sig / 1.5
    elif wave_type == "warm_pad":
        # Detuned pair + sub-harmonic
        s1 = np.sin(2 * np.pi * freq * t)
        s2 = np.sin(2 * np.pi * (freq * 1.003) * t)
        sub = 0.4 * np.sin(2 * np.pi * (freq * 0.5) * t)
        return (s1 + s2 + sub) / 2.4
    return np.sin(2 * np.pi * freq * t)


def _apply_envelope(signal: np.ndarray, attack_sec: float, release_sec: float) -> np.ndarray:
    n = len(signal)
    env = np.ones(n, dtype=np.float32)
    att_samples = int(attack_sec * SAMPLE_RATE)
    rel_samples = int(release_sec * SAMPLE_RATE)
    if att_samples > 0 and att_samples < n:
        env[:att_samples] = np.linspace(0, 1, att_samples)
    if rel_samples > 0 and rel_samples < n:
        env[-rel_samples:] = np.linspace(1, 0, rel_samples)
    return signal * env


def _build_track_audio(spec: dict) -> tuple[np.ndarray, np.ndarray]:
    """Tạo tín hiệu âm thanh stereo (L, R) cho một bản nhạc."""
    total_sec = spec["thoi_luong_giay"]
    total_samples = int(SAMPLE_RATE * total_sec)
    left_channel = np.zeros(total_samples, dtype=np.float32)
    right_channel = np.zeros(total_samples, dtype=np.float32)

    chords = spec["hop_am"]
    num_chords = len(chords)
    chord_duration = total_sec / num_chords
    samples_per_chord = int(SAMPLE_RATE * chord_duration)

    kieu_nhip = spec["kieu_nhip"]
    bpm = spec["bpm"]
    beat_sec = 60.0 / bpm

    for idx, (chord_name, bass_note, treble_notes) in enumerate(chords):
        start_samp = idx * samples_per_chord
        end_samp = min(total_samples, (idx + 1) * samples_per_chord)
        c_len = end_samp - start_samp
        dur = c_len / SAMPLE_RATE

        # 1. Bassline (ấm, dày)
        bass_freq = _note_to_freq(bass_note)
        bass_sig = _synthesize_oscillator(bass_freq, dur, "soft_saw")
        bass_sig = _apply_envelope(bass_sig, 0.08, 0.12) * 0.40
        left_channel[start_samp:end_samp] += bass_sig
        right_channel[start_samp:end_samp] += bass_sig

        # 2. Chords Pad (Stereo Spread)
        for t_idx, note_name in enumerate(treble_notes):
            freq = _note_to_freq(note_name)
            pad_sig = _synthesize_oscillator(freq, dur, "warm_pad")
            pad_sig = _apply_envelope(pad_sig, 0.25, 0.35) * 0.22
            # Pan spread across notes
            pan = (t_idx / max(1, len(treble_notes) - 1)) * 0.6 - 0.3  # -0.3 đến +0.3
            left_channel[start_samp:end_samp] += pad_sig * (0.5 - pan)
            right_channel[start_samp:end_samp] += pad_sig * (0.5 + pan)

        # 3. Rhythmic pulses / Arpeggios tùy theo kieu_nhip
        num_beats_in_chord = int(dur / beat_sec)
        for beat_i in range(num_beats_in_chord):
            b_start = int(start_samp + beat_i * beat_sec * SAMPLE_RATE)
            if b_start >= total_samples:
                break

            if kieu_nhip in ("dance_beat", "hook_synth"):
                # Sub kick pulse
                k_dur = 0.08
                k_samples = min(total_samples - b_start, int(k_dur * SAMPLE_RATE))
                if k_samples > 0:
                    kt = np.linspace(0, k_dur, k_samples)
                    kick = np.sin(2 * np.pi * 55.0 * np.exp(-18 * kt) * kt) * 0.35
                    left_channel[b_start:b_start + k_samples] += kick
                    right_channel[b_start:b_start + k_samples] += kick

                # Snare/hi-hat click on off-beat
                off_start = int(b_start + (beat_sec * 0.5) * SAMPLE_RATE)
                hh_samples = min(total_samples - off_start, int(0.04 * SAMPLE_RATE))
                if off_start < total_samples and hh_samples > 0:
                    noise = (np.random.rand(hh_samples) * 2 - 1).astype(np.float32)
                    noise = _apply_envelope(noise, 0.005, 0.035) * 0.08
                    left_channel[off_start:off_start + hh_samples] += noise * 0.8
                    right_channel[off_start:off_start + hh_samples] += noise * 1.2

            elif kieu_nhip == "pulse":
                # Subtle tech pulse (8th note tick)
                tick_dur = 0.05
                tick_samples = min(total_samples - b_start, int(tick_dur * SAMPLE_RATE))
                if tick_samples > 0:
                    tick_freq = _note_to_freq(treble_notes[beat_i % len(treble_notes)]) * 2
                    tt = np.linspace(0, tick_dur, tick_samples)
                    pulse = np.sin(2 * np.pi * tick_freq * tt) * np.exp(-30 * tt) * 0.12
                    left_channel[b_start:b_start + tick_samples] += pulse * 0.7
                    right_channel[b_start:b_start + tick_samples] += pulse * 1.0

            elif kieu_nhip == "arp":
                # Arpeggiated melody note
                arp_dur = beat_sec * 0.95
                arp_samples = min(total_samples - b_start, int(arp_dur * SAMPLE_RATE))
                if arp_samples > 0:
                    arp_freq = _note_to_freq(treble_notes[(beat_i * 2) % len(treble_notes)])
                    arp_sig = _synthesize_oscillator(arp_freq, arp_dur, "triangle")
                    arp_sig = _apply_envelope(arp_sig, 0.04, 0.10) * 0.18
                    left_channel[b_start:b_start + arp_samples] += arp_sig * 1.1
                    right_channel[b_start:b_start + arp_samples] += arp_sig * 0.8

            elif kieu_nhip == "lofi_chill":
                # Soft mellow rhodes-like tap
                tap_dur = beat_sec * 0.8
                tap_samples = min(total_samples - b_start, int(tap_dur * SAMPLE_RATE))
                if tap_samples > 0:
                    tap_freq = _note_to_freq(treble_notes[beat_i % len(treble_notes)])
                    tap_sig = _synthesize_oscillator(tap_freq, tap_dur, "sine")
                    tap_sig = _apply_envelope(tap_sig, 0.03, 0.20) * 0.15
                    left_channel[b_start:b_start + tap_samples] += tap_sig * 0.9
                    right_channel[b_start:b_start + tap_samples] += tap_sig * 1.0

            elif kieu_nhip == "tense_drone":
                # Pulsing sub tension
                p_dur = beat_sec * 1.5
                p_samples = min(total_samples - b_start, int(p_dur * SAMPLE_RATE))
                if p_samples > 0:
                    pt = np.linspace(0, p_dur, p_samples)
                    drone = np.sin(2 * np.pi * (bass_freq * 1.5) * pt) * (1.0 + 0.3 * np.sin(2 * np.pi * 4 * pt)) * 0.10
                    left_channel[b_start:b_start + p_samples] += drone
                    right_channel[b_start:b_start + p_samples] += drone

            elif kieu_nhip == "inspirational_swell":
                # Warm bell chime on 1st & 3rd beat
                if beat_i % 2 == 0:
                    c_dur = beat_sec * 1.8
                    c_samples = min(total_samples - b_start, int(c_dur * SAMPLE_RATE))
                    if c_samples > 0:
                        c_freq = _note_to_freq(treble_notes[-1]) * 1.5
                        ct = np.linspace(0, c_dur, c_samples)
                        chime = (np.sin(2 * np.pi * c_freq * ct) + 0.4 * np.sin(2 * np.pi * (c_freq * 2.02) * ct)) * np.exp(-4 * ct) * 0.14
                        left_channel[b_start:b_start + c_samples] += chime * 1.1
                        right_channel[b_start:b_start + c_samples] += chime * 0.9

    # Soft limiter / normalization to avoid clipping before FFmpeg loudnorm
    max_amp = max(np.max(np.abs(left_channel)), np.max(np.abs(right_channel)), 0.001)
    if max_amp > 0.85:
        left_channel = (left_channel / max_amp) * 0.85
        right_channel = (right_channel / max_amp) * 0.85

    return left_channel, right_channel


def _save_raw_wav(left: np.ndarray, right: np.ndarray, path: Path) -> None:
    pcm_left = (np.clip(left, -1.0, 1.0) * 32767).astype(np.int16)
    pcm_right = (np.clip(right, -1.0, 1.0) * 32767).astype(np.int16)
    interleaved = np.empty((len(pcm_left) * 2,), dtype=np.int16)
    interleaved[0::2] = pcm_left
    interleaved[1::2] = pcm_right

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(interleaved.tobytes())


def _normalize_loudness_ffmpeg(input_wav: Path, output_wav: Path, target_lufs: float = -16.0) -> None:
    """Chuẩn hóa âm thanh sang chuẩn phát sóng TikTok (-16 LUFS, True Peak <= -1.5 dBTP)."""
    filter_expr = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=10"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(input_wav),
        "-af", filter_expr,
        "-c:a", "pcm_s16le",
        "-ar", str(SAMPLE_RATE),
        str(output_wav)
    ]
    subprocess.run(cmd, check=True)


def sinh_toan_bo_thu_vien():
    print("Bắt đầu sinh 15 bản nhạc nền chuẩn hóa...")
    manifest_items = []

    with tempfile.TemporaryDirectory(prefix="bgm_synth_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        for spec in TRACK_SPECS:
            track_id = spec["id"]
            final_wav_path = OUTPUT_DIR / f"{track_id}.wav"
            temp_raw = tmp_path / f"raw_{track_id}.wav"

            print(f"-> Đang tạo bản nhạc: {spec['ten']} ({track_id})...")
            left, right = _build_track_audio(spec)
            _save_raw_wav(left, right, temp_raw)

            _normalize_loudness_ffmpeg(temp_raw, final_wav_path, target_lufs=-16.0)

            # Tính mã băm SHA256 và dung lượng
            import hashlib
            data = final_wav_path.read_bytes()
            sha256_hash = hashlib.sha256(data).hexdigest()

            manifest_items.append({
                "id": track_id,
                "ten": spec["ten"],
                "danh_muc": spec["danh_muc"],
                "nhan_dien_tam_trang": spec["nhan_dien_tam_trang"],
                "bpm": spec["bpm"],
                "thoi_luong_giay": spec["thoi_luong_giay"],
                "am_luong_mac_dinh_db": spec["am_luong_mac_dinh_db"],
                "dinh_dang": "audio/wav",
                "sample_rate_hz": SAMPLE_RATE,
                "channels": 2,
                "target_lufs": -16.0,
                "sha256": sha256_hash,
                "byte_size": len(data),
                "tep_tin": f"{track_id}.wav",
                "ban_quyen": {
                    "nguon": "INTERNAL_SYNTH_STUDIO",
                    "giay_phep": "CC0_EQUIVALENT_INTERNAL_OWNED",
                    "an_toan_tiktok_commercial": True,
                    "ghi_chu": "Bản quyền nội bộ BAHA AI Media Studio, miễn phí thương mại, an toàn tuyệt đối với TikTok Content ID."
                }
            })

    # Lưu manifest
    manifest_data = {
        "phien_ban_kho_nhac": "1.0.0",
        "tong_so_bai": len(manifest_items),
        "muc_tieu_am_luong_goc_lufs": -16.0,
        "muc_ha_nen_mac_dinh_db": -18.0,
        "danh_muc": [
            {"ma": "chuyen_nghiep_b2b", "ten": "Chuyên Nghiệp B2B & Công Nghệ", "so_bai": 3},
            {"ma": "nang_luong_bat_nhip", "ten": "Năng Lượng Bắt Nhịp", "so_bai": 3},
            {"ma": "tam_su_ke_chuyen", "ten": "Tâm Sự Kể Chuyện (Lo-Fi)", "so_bai": 3},
            {"ma": "kich_tinh_canh_bao", "ten": "Kịch Tính Cảnh Báo", "so_bai": 3},
            {"ma": "truyen_cam_hung", "ten": "Truyền Cảm Hứng & Thành Tựu", "so_bai": 3},
        ],
        "danh_sach_nhac": manifest_items
    }

    MANIFEST_PATH.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Hoàn tất sinh 15 bản nhạc! Danh mục đã lưu tại: {MANIFEST_PATH}")


if __name__ == "__main__":
    sinh_toan_bo_thu_vien()
