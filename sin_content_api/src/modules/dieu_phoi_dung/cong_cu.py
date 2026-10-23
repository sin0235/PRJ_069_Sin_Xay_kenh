from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Optional

from .hop_dong import (
    TimelineV2,
    TrackV2,
    ClipV2,
    CaptionV2,
    ThoiGianNguon,
    LenhDung,
    KetQuaCongCu,
    LoiHopDong
)
from .phien_dung import QuanLyPhienDung, BanNhapDung
from .kho_luu_tru import KhoLuuTruDung
from .bo_render import BoRenderDung


class DieuPhoiCongCu:
    """
    Tool Broker dieu phoi cac lenh dung video.
    Bao dam tinh nguyen tu (All-or-Nothing), kiem tra ranh gioi (bounds check),
    chong trung lap side-effect (Idempotency) va cap nhat revision nhat quan.
    """
    _journal: Dict[str, Dict[str, Any]] = {}  # operation_id -> {payload_hash, ket_qua}

    @classmethod
    def _tinh_hash_payload(cls, payload: Dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def thuc_hien_lenh(
        cls,
        draft_id: str,
        expected_draft_revision: int,
        commands: List[LenhDung],
        workspace_id: Optional[str] = None
    ) -> KetQuaCongCu:
        if not commands:
            draft = QuanLyPhienDung.lay_ban_nhap(draft_id)
            if workspace_id and draft.workspace_id != workspace_id:
                raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Ban nhap {draft_id} khong thuoc workspace {workspace_id}")
            return KetQuaCongCu(
                operation_id="noop",
                status="SUCCESS",
                revision_after=draft.draft_revision,
                hash_after=draft.draft_hash,
                changed_ids=[]
            )

        # 1. Kiem tra Idempotency cho lenh dau tien (hoac batch)
        first_cmd = commands[0]
        op_id = first_cmd.operation_id
        payload_hash = cls._tinh_hash_payload(first_cmd.payload)

        # Tra cuu kho ben vung va in-memory journal
        saved = KhoLuuTruDung.lay_nhat_ky_lenh(op_id)
        if not saved and op_id in cls._journal:
            saved = cls._journal[op_id]

        if saved:
            if saved["payload_hash"] == payload_hash:
                # Cung key, cung payload -> Tra ket qua da thuc hien (Idempotent Replay)
                res = saved["result"]
                return res if isinstance(res, KetQuaCongCu) else KetQuaCongCu(**res)
            else:
                # Cung key, khac payload -> Xung dot (Conflict)
                raise ValueError(f"{LoiHopDong.OCC_CONFLICT_409}: Lenh {op_id} da duoc thuc thi voi payload khac")

        # 2. Lay ban nhap hien tai va tao ban sao tam (Working Copy)
        draft = QuanLyPhienDung.lay_ban_nhap(draft_id)
        if workspace_id and draft.workspace_id != workspace_id:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Ban nhap {draft_id} khong thuoc workspace {workspace_id}")

        if draft.is_locked:
            raise ValueError(f"{LoiHopDong.OCC_CONFLICT_409}: Ban nhap {draft_id} da bi khoa")

        if draft.draft_revision != expected_draft_revision:
            raise ValueError(f"{LoiHopDong.OCC_CONFLICT_409}: Xung dot phien ban draft: hien tai {draft.draft_revision}, nhung client truyen {expected_draft_revision}")

        working_timeline = copy.deepcopy(draft.timeline)
        changed_ids: List[str] = []

        # 3. Thuc thi tat ca lenh trong batch (All-or-Nothing)
        try:
            for cmd in commands:
                cls._ap_dung_lenh_don(working_timeline, cmd, changed_ids)
        except Exception as e:
            # Rollback: Working copy bi huy bo, khong cap nhat draft
            raise ValueError(f"Thuc thi lenh {cmd.operation_id} that bai, da rollback toan bo batch: {str(e)}")

        # 4. Neu toan bo batch thanh cong -> Cap nhat ban nhap (CAS)
        updated_draft = QuanLyPhienDung.cap_nhat_ban_nhap(
            draft_id=draft_id,
            expected_revision=expected_draft_revision,
            timeline_moi=working_timeline
        )

        result = KetQuaCongCu(
            operation_id=op_id,
            status="SUCCESS",
            revision_after=updated_draft.draft_revision,
            hash_after=updated_draft.draft_hash,
            changed_ids=list(set(changed_ids)),
            cost_units=len(commands)
        )

        # 5. Ghi nhat ky Journal vao ca kho ben vung va RAM
        KhoLuuTruDung.luu_nhat_ky_lenh(
            operation_id=op_id,
            draft_id=draft_id,
            payload_hash=payload_hash,
            result_dict=result.model_dump(mode="json")
        )
        cls._journal[op_id] = {
            "payload_hash": payload_hash,
            "result": result
        }

        return result

    @classmethod
    def _ap_dung_lenh_don(
        cls,
        timeline: TimelineV2,
        cmd: LenhDung,
        changed_ids: List[str]
    ) -> None:
        cmd_type = cmd.type
        p = cmd.payload

        # Kiem tra execution adapter san sang truoc khi thuc thi lenh
        is_supported, err_code = BoRenderDung.kiem_tra_kha_nang_thuc_thi(cmd_type, p)
        if not is_supported:
            raise ValueError(f"{err_code}: Thao tac {cmd_type} khong duoc ho tro tren execution adapter hoac render pipeline hien tai")

        if cmd_type == "split_clip":
            track_id = p["track_id"]
            clip_id = p["clip_id"]
            split_frame = int(p["split_frame"])

            track = cls._tim_track(timeline, track_id)
            clip_idx, clip = cls._tim_clip(track, clip_id)

            if not (clip.start_frame < split_frame < clip.start_frame + clip.duration_frames):
                raise ValueError(f"{LoiHopDong.OOB_RANGE}: Diem chia split_frame {split_frame} nam ngoai pham vi clip [{clip.start_frame}, {clip.start_frame + clip.duration_frames}]")

            left_duration = split_frame - clip.start_frame
            right_duration = clip.duration_frames - left_duration

            # Tinh toan thoi gian nguon tuong ung
            fps = float(timeline.fps_num) / float(timeline.fps_den)
            split_sec = left_duration / fps
            split_ticks = clip.source_in.ticks + int(round(split_sec * (clip.source_in.time_base_den / clip.source_in.time_base_num)))

            clip_left = copy.deepcopy(clip)
            clip_left.duration_frames = left_duration
            clip_left.source_out = ThoiGianNguon(
                ticks=split_ticks,
                time_base_num=clip.source_in.time_base_num,
                time_base_den=clip.source_in.time_base_den
            )

            clip_right = copy.deepcopy(clip)
            clip_right.clip_id = f"{clip_id}_part2"
            clip_right.start_frame = split_frame
            clip_right.duration_frames = right_duration
            clip_right.source_in = ThoiGianNguon(
                ticks=split_ticks,
                time_base_num=clip.source_in.time_base_num,
                time_base_den=clip.source_in.time_base_den
            )

            track.clips[clip_idx] = clip_left
            track.clips.insert(clip_idx + 1, clip_right)
            changed_ids.extend([clip.clip_id, clip_right.clip_id])

        elif cmd_type == "trim_clip":
            track_id = p["track_id"]
            clip_id = p["clip_id"]
            trim_in_ms = int(p["trim_in_ms"])
            trim_out_ms = int(p["trim_out_ms"])

            if trim_out_ms <= trim_in_ms:
                raise ValueError(f"{LoiHopDong.OOB_RANGE}: trim_out_ms bat buoc phai lon hon trim_in_ms")

            track = cls._tim_track(timeline, track_id)
            _, clip = cls._tim_clip(track, clip_id)

            fps = float(timeline.fps_num) / float(timeline.fps_den)
            actual_dur_s = (trim_out_ms - trim_in_ms) / 1000.0
            clip.duration_frames = max(1, int(round(actual_dur_s * fps)))
            clip.source_in = ThoiGianNguon(ticks=trim_in_ms, time_base_num=1, time_base_den=1000)
            clip.source_out = ThoiGianNguon(ticks=trim_out_ms, time_base_num=1, time_base_den=1000)
            changed_ids.append(clip_id)

        elif cmd_type == "insert_clip":
            track_id = p["track_id"]
            asset_id = p["asset_id"]
            at_frame = int(p.get("at_frame", 0))
            duration_frames = int(p.get("duration_frames", 90))

            track = cls._tim_track(timeline, track_id)
            new_clip_id = p.get("clip_id") or f"c_ins_{len(track.clips)+1}"

            # Day cac clip phia sau sang phai (Ripple Insert)
            for c in track.clips:
                if c.start_frame >= at_frame:
                    c.start_frame += duration_frames

            new_clip = ClipV2(
                clip_id=new_clip_id,
                asset_id=asset_id,
                start_frame=at_frame,
                duration_frames=duration_frames,
                source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
                source_out=ThoiGianNguon(ticks=int(round((duration_frames / 30.0)*1000)), time_base_num=1, time_base_den=1000)
            )
            track.clips.append(new_clip)
            track.clips.sort(key=lambda x: x.start_frame)
            changed_ids.append(new_clip_id)

        elif cmd_type == "ripple_delete":
            track_id = p["track_id"]
            clip_id = p["clip_id"]

            track = cls._tim_track(timeline, track_id)
            clip_idx, clip = cls._tim_clip(track, clip_id)
            deleted_duration = clip.duration_frames

            track.clips.pop(clip_idx)
            # Keo toan bo cac clip phia sau lui lai
            for c in track.clips:
                if c.start_frame > clip.start_frame:
                    c.start_frame -= deleted_duration

            changed_ids.append(clip_id)

        elif cmd_type == "set_clip_gain":
            track_id = p["track_id"]
            clip_id = p["clip_id"]
            gain_db = float(p["gain_db"])

            if not (-60.0 <= gain_db <= 12.0):
                raise ValueError(f"{LoiHopDong.OOB_RANGE}: gain_db phai nam trong khoang [-60.0, 12.0] dB")

            track = cls._tim_track(timeline, track_id)
            _, clip = cls._tim_clip(track, clip_id)
            clip.gain_db = gain_db
            changed_ids.append(clip_id)

        elif cmd_type == "set_caption_text":
            caption_id = p["caption_id"]
            new_text = str(p["text"]).strip()
            if not new_text:
                raise ValueError("Noi dung phu de khong duoc de trong")

            cap_found = False
            for cap in timeline.captions:
                if cap.caption_id == caption_id:
                    cap.text = new_text
                    if "safe_zone" in p:
                        cap.safe_zone = bool(p["safe_zone"])
                    cap_found = True
                    break

            if not cap_found:
                raise ValueError(f"Khong tim thay caption {caption_id}")

            changed_ids.append(caption_id)

        elif cmd_type == "apply_color_lut":
            track_id = p["track_id"]
            clip_id = p["clip_id"]
            lut_id = p.get("lut_asset_id")
            if not lut_id:
                raise ValueError(f"{LoiHopDong.UNSUPPORTED_EFFECT}: Lenh apply_color_lut thieu lut_asset_id")

            track = cls._tim_track(timeline, track_id)
            _, clip = cls._tim_clip(track, clip_id)
            clip.lut_asset_id = lut_id
            
            # Gan execution spec de render FFmpeg/NLE thuc su ap filter khi xuat video
            lut_render_spec = BoRenderDung.sinh_render_spec_lut(lut_id)
            if not hasattr(clip, "effects") or clip.effects is None:
                clip.effects = []
            clip.effects.append(lut_render_spec)
            changed_ids.append(clip_id)

        elif cmd_type == "set_retime_speed":
            track_id = p["track_id"]
            clip_id = p["clip_id"]
            speed_ratio = float(p["speed_ratio"])

            if not (0.25 <= speed_ratio <= 4.0):
                raise ValueError(f"{LoiHopDong.OOB_RANGE}: speed_ratio phai nam trong doan [0.25, 4.0]")

            track = cls._tim_track(timeline, track_id)
            _, clip = cls._tim_clip(track, clip_id)
            clip.speed_ratio = speed_ratio
            clip.duration_frames = max(1, int(round(clip.duration_frames / speed_ratio)))
            
            # Gan execution spec cho Retime
            retime_render_spec = BoRenderDung.sinh_render_spec_retime(speed_ratio)
            if not hasattr(clip, "effects") or clip.effects is None:
                clip.effects = []
            clip.effects.append(retime_render_spec)
            changed_ids.append(clip_id)

        elif cmd_type == "overwrite_clip":
            track_id = p["track_id"]
            asset_id = p["asset_id"]
            at_frame = int(p.get("at_frame", 0))
            duration_frames = int(p.get("duration_frames", 90))
            new_clip_id = p.get("clip_id") or f"c_ovw_{at_frame}"

            track = cls._tim_track(timeline, track_id)
            # Tim va loai bo clip bi ghi de hoac thu hep clip bi che
            new_clips: List[ClipV2] = []
            for c in track.clips:
                c_end = c.start_frame + c.duration_frames
                if c_end <= at_frame or c.start_frame >= at_frame + duration_frames:
                    new_clips.append(c)
                elif c.start_frame < at_frame and c_end > at_frame + duration_frames:
                    # Clip bi cat lam 2
                    c_left = copy.deepcopy(c)
                    c_left.duration_frames = at_frame - c.start_frame
                    c_right = copy.deepcopy(c)
                    c_right.start_frame = at_frame + duration_frames
                    c_right.duration_frames = c_end - (at_frame + duration_frames)
                    new_clips.extend([c_left, c_right])
                elif c.start_frame < at_frame:
                    c.duration_frames = at_frame - c.start_frame
                    new_clips.append(c)
                elif c_end > at_frame + duration_frames:
                    c.duration_frames = c_end - (at_frame + duration_frames)
                    c.start_frame = at_frame + duration_frames
                    new_clips.append(c)

            new_clip = ClipV2(
                clip_id=new_clip_id,
                asset_id=asset_id,
                start_frame=at_frame,
                duration_frames=duration_frames,
                source_in=ThoiGianNguon(ticks=0, time_base_num=1, time_base_den=1000),
                source_out=ThoiGianNguon(ticks=int(round((duration_frames / 30.0)*1000)), time_base_num=1, time_base_den=1000)
            )
            new_clips.append(new_clip)
            new_clips.sort(key=lambda x: x.start_frame)
            track.clips = new_clips
            changed_ids.append(new_clip_id)

        elif cmd_type == "slip_clip":
            track_id = p["track_id"]
            clip_id = p["clip_id"]
            slip_delta_ms = int(p["slip_delta_ms"])

            track = cls._tim_track(timeline, track_id)
            _, clip = cls._tim_clip(track, clip_id)

            new_in_ticks = clip.source_in.ticks + slip_delta_ms
            new_out_ticks = clip.source_out.ticks + slip_delta_ms

            if new_in_ticks < 0:
                raise ValueError(f"{LoiHopDong.OOB_RANGE}: slip_delta_ms khien source_in < 0")

            max_source_dur = int(p.get("max_source_duration_ms", 999999))
            if new_out_ticks > max_source_dur:
                raise ValueError(f"{LoiHopDong.OOB_RANGE}: slip_delta_ms vuot qua tong thoi luong nguon cua asset")

            clip.source_in.ticks = new_in_ticks
            clip.source_out.ticks = new_out_ticks
            changed_ids.append(clip_id)

        elif cmd_type == "add_track":
            track_id = p["track_id"]
            track_type = p.get("track_type", "video")
            layer_index = int(p.get("layer_index", len(timeline.tracks)))
            name = p.get("name", f"Track {layer_index + 1}")

            # Kiem tra track_id trung
            if any(t.track_id == track_id for t in timeline.tracks):
                raise ValueError(f"Track {track_id} da ton tai")

            new_trk = TrackV2(
                track_id=track_id,
                track_type=track_type,
                layer_index=layer_index,
                name=name,
                clips=[]
            )
            timeline.tracks.append(new_trk)
            timeline.tracks.sort(key=lambda x: (x.track_type, x.layer_index))
            changed_ids.append(track_id)

        elif cmd_type == "add_transition":
            track_id = p["track_id"]
            clip_id = p["clip_id"]
            handle_frames_needed = int(p.get("handle_frames", 15))
            available_handle_frames = int(p.get("available_handle_frames", 0))

            if available_handle_frames < handle_frames_needed:
                raise ValueError(f"{LoiHopDong.OOB_RANGE}: Transition thieu handle: can {handle_frames_needed} frames nhung chi co {available_handle_frames} frames")

            track = cls._tim_track(timeline, track_id)
            _, clip = cls._tim_clip(track, clip_id)
            clip.effects.append({
                "type": "transition",
                "name": p.get("transition_name", "crossfade"),
                "duration_frames": handle_frames_needed
            })
            changed_ids.append(clip_id)

        else:
            raise ValueError(f"Lenh {cmd_type} chua duoc ho tro")

    @classmethod
    def _tim_track(cls, timeline: TimelineV2, track_id: str) -> TrackV2:
        for t in timeline.tracks:
            if t.track_id == track_id:
                if t.is_locked:
                    raise ValueError(f"{LoiHopDong.OCC_CONFLICT_409}: Track {track_id} da bi khoa (locked)")
                return t
        raise ValueError(f"Khong tim thay track {track_id}")

    @classmethod
    def _tim_clip(cls, track: TrackV2, clip_id: str) -> tuple[int, ClipV2]:
        for idx, c in enumerate(track.clips):
            if c.clip_id == clip_id:
                return idx, c
        raise ValueError(f"Khong tim thay clip {clip_id} tren track {track.track_id}")
