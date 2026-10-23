from __future__ import annotations

import math
from typing import Any, Dict, List
from .hop_dong import TimelineV2, TrackV2, ClipV2, CaptionV2, ThoiGianNguon


def chuyen_timeline_v1(
    doc: Dict[str, Any],
    fps_num: int = 30,
    fps_den: int = 1
) -> TimelineV2:
    """
    Chuyen doi an toan tu TimelineDocument v1 (thoi gian ms) sang TimelineV2 (rational ThoiGianNguon).
    Bao toan 100% du lieu cu va khong sua doi JSON v1 goc trong co so du lieu.
    """
    fps = float(fps_num) / float(fps_den)
    tracks: List[TrackV2] = []
    
    # 1. Chuyen doi cac clips video/audio sang Track V1
    v1_clips = doc.get("clips", [])
    video_clips: List[ClipV2] = []
    current_frame = 0

    for idx, c in enumerate(v1_clips):
        clip_id = c.get("clip_id") or f"c_v1_{idx}"
        asset_id = c.get("asset_id", "")
        duration_ms = int(c.get("duration_ms", 3000))
        trim_in_ms = int(c.get("trim_in_ms", 0))
        trim_out_ms = int(c.get("trim_out_ms", 0))
        fit_mode = c.get("fit_mode", "cover")

        if trim_out_ms > trim_in_ms:
            actual_dur_ms = trim_out_ms - trim_in_ms
        else:
            actual_dur_ms = duration_ms

        # Tinh toan thoi luong theo frame
        duration_frames = max(1, int(round((actual_dur_ms / 1000.0) * fps)))
        
        # ThoiGianNguon voi time_base la 1/1000 (ms)
        source_in = ThoiGianNguon(ticks=trim_in_ms, time_base_num=1, time_base_den=1000)
        end_tick = trim_out_ms if trim_out_ms > trim_in_ms else (trim_in_ms + actual_dur_ms)
        source_out = ThoiGianNguon(ticks=end_tick, time_base_num=1, time_base_den=1000)

        clip_v2 = ClipV2(
            clip_id=clip_id,
            asset_id=asset_id,
            start_frame=current_frame,
            duration_frames=duration_frames,
            source_in=source_in,
            source_out=source_out,
            fit_mode=fit_mode,
            gain_db=0.0,
            speed_ratio=1.0,
            effects=[]
        )
        video_clips.append(clip_v2)
        current_frame += duration_frames

    # Tao Video Track 1 (V1)
    if video_clips or not doc.get("audio_tracks"):
        tracks.append(TrackV2(
            track_id="trk_v1_main",
            track_type="video",
            layer_index=0,
            name="Video Track 1",
            clips=video_clips
        ))

    # 2. Chuyen doi cac audio tracks
    v1_audio = doc.get("audio_tracks", [])
    for a_idx, a in enumerate(v1_audio):
        track_id = a.get("track_id") or f"trk_a_{a_idx}"
        asset_id = a.get("asset_id", "")
        volume = float(a.get("volume", 1.0))
        gain_db = 20.0 * math.log10(volume) if volume > 0 else -60.0
        gain_db = max(-60.0, min(12.0, gain_db))
        
        # Tinh toan duration cua audio track theo video hoac mac dinh
        audio_clip = ClipV2(
            clip_id=f"ac_{a_idx}",
            asset_id=asset_id,
            start_frame=0,
            duration_frames=current_frame if current_frame > 0 else int(30 * fps),
            source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
            source_out=ThoiGianNguon(ticks=int(round((current_frame / fps) * 1000.0)), time_base_num=1, time_base_den=1000),
            gain_db=gain_db
        )
        tracks.append(TrackV2(
            track_id=track_id,
            track_type="audio",
            layer_index=a_idx,
            name=f"Audio Track {a_idx + 1}",
            clips=[audio_clip]
        ))

    # 3. Chuyen doi Captions
    captions: List[CaptionV2] = []
    v1_captions = doc.get("captions", [])
    for cap_idx, cap in enumerate(v1_captions):
        start_ms = int(cap.get("start_ms", 0))
        end_ms = int(cap.get("end_ms", 2000))
        if end_ms <= start_ms:
            end_ms = start_ms + 1000
        captions.append(CaptionV2(
            caption_id=cap.get("caption_id") or f"cap_{cap_idx}",
            start_ms=start_ms,
            end_ms=end_ms,
            text=cap.get("text", ""),
            safe_zone=cap.get("safe_zone", True)
        ))

    return TimelineV2(
        schema_version=2,
        fps_num=fps_num,
        fps_den=fps_den,
        width=1080,
        height=1920,
        tracks=tracks,
        captions=captions,
        representation_mode="CANONICAL"
    )


def map_vfr_pts(
    pts_list: List[int],
    time_base_num: int,
    time_base_den: int,
    target_fps_num: int = 30,
    target_fps_den: int = 1
) -> List[int]:
    """
    Anh xa danh sach Presentation Time Stamps (PTS) cua video Variable Frame Rate (VFR)
    sang chi so frame dich tren timeline Constant Frame Rate (CFR).
    Khong lay chi so mau chia avg FPS de tranh tich luy sai so (drift).
    """
    target_fps = float(target_fps_num) / float(target_fps_den)
    frame_indices: List[int] = []

    for pts in pts_list:
        seconds = (pts * time_base_num) / float(time_base_den)
        frame_idx = int(round(seconds * target_fps))
        frame_indices.append(max(0, frame_idx))

    return frame_indices
