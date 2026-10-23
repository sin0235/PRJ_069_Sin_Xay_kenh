from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
from pydantic import BaseModel, Field

from .hop_dong import (
    TimelineV2,
    GoiBanGiao,
    LoiHopDong
)
from .kho_luu_tru import KhoLuuTruDung


class BoKetNoiPhanMemDung:
    """
    Adapter xuat/nhap goi ban giao NLE (Final Cut XML / Resolve EDL),
    thuc su tao file tren o dia de relink trong NLE va quan ly che do NATIVE_BOUND bao ve finishing.
    """
    _bundles_store: Dict[str, GoiBanGiao] = {}

    @classmethod
    def _lay_thu_muc_xuat(cls, project_id: str, bundle_id: str) -> Path:
        api_root = Path(__file__).resolve().parents[3]
        export_dir = api_root / "exports" / "nle_bundles" / bundle_id
        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir

    @classmethod
    def xuat_goi_ban_giao(
        cls,
        project_id: str,
        revision: int,
        timeline: TimelineV2,
        adapter_id: str = "FINAL_CUT_XML",
        workspace_id: str = "ws_default"
    ) -> GoiBanGiao:
        bundle_id = f"bnd_{project_id}_rev{revision}"
        
        # 1. Tinh hash timeline
        data = timeline.model_dump(mode="json")
        t_hash = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

        # 2. Xay dung bao cao ton that hieu ung (Loss Report)
        loss_report: Dict[str, List[str]] = {
            "SUPPORTED": ["cuts", "duration", "gain_db", "captions", "speed_ratio"],
            "BAKED_WITH_APPROVAL": ["transitions", "transform_easing"],
            "HUMAN_REQUIRED": ["advanced_color_grading", "3d_tracking", "rotoscoping"],
            "UNSUPPORTED": []
        }

        # 3. Tao thu muc thuc te tren disk va ghi file
        export_dir = cls._lay_thu_muc_xuat(project_id, bundle_id)

        # 3.1 Sinh file timeline.xml chuan Final Cut Pro XML (XMEML v5)
        timeline_xml_path = export_dir / "timeline.xml"
        fps = int(round(timeline.fps_num / timeline.fps_den)) if timeline.fps_den else 30
        
        root_elem = ET.Element("xmeml", version="5")
        seq_elem = ET.SubElement(root_elem, "sequence", id=f"seq_{project_id}")
        ET.SubElement(seq_elem, "name").text = f"SIN_{project_id}_REV{revision}"
        rate_elem = ET.SubElement(seq_elem, "rate")
        ET.SubElement(rate_elem, "timebase").text = str(fps)
        ET.SubElement(rate_elem, "ntsc").text = "FALSE"
        
        media_elem = ET.SubElement(seq_elem, "media")
        video_elem = ET.SubElement(media_elem, "video")
        format_elem = ET.SubElement(video_elem, "format")
        sample_elem = ET.SubElement(format_elem, "samplecharacteristics")
        ET.SubElement(sample_elem, "width").text = "1080"
        ET.SubElement(sample_elem, "height").text = "1920"

        clips_manifest_list = []
        for track in timeline.tracks:
            track_elem = ET.SubElement(video_elem, "track")
            for clip in track.clips:
                clip_elem = ET.SubElement(track_elem, "clipitem", id=clip.clip_id)
                ET.SubElement(clip_elem, "name").text = f"{clip.asset_id}_{clip.clip_id}"
                ET.SubElement(clip_elem, "start").text = str(clip.start_frame)
                ET.SubElement(clip_elem, "end").text = str(clip.start_frame + clip.duration_frames)
                ET.SubElement(clip_elem, "in").text = str(clip.source_in.ticks)
                ET.SubElement(clip_elem, "out").text = str(clip.source_out.ticks)
                
                # File ref phuc vu relink trong Resolve / Premiere / Final Cut
                file_elem = ET.SubElement(clip_elem, "file", id=f"file_{clip.asset_id}")
                ET.SubElement(file_elem, "name").text = f"{clip.asset_id}.mp4"
                ET.SubElement(file_elem, "pathurl").text = f"file://localhost/media/{workspace_id}/{clip.asset_id}.mp4"
                
                clips_manifest_list.append({
                    "clip_id": clip.clip_id,
                    "asset_id": clip.asset_id,
                    "track_id": track.track_id,
                    "start_frame": clip.start_frame,
                    "duration_frames": clip.duration_frames,
                    "source_in_ticks": clip.source_in.ticks,
                    "source_out_ticks": clip.source_out.ticks,
                    "relink_path": f"media/{workspace_id}/{clip.asset_id}.mp4",
                    "lut_asset_id": clip.lut_asset_id,
                    "speed_ratio": clip.speed_ratio
                })

        xml_tree = ET.ElementTree(root_elem)
        xml_tree.write(str(timeline_xml_path), encoding="utf-8", xml_declaration=True)

        # 3.2 Sinh file manifest.json
        manifest_path = export_dir / "manifest.json"
        manifest_data = {
            "bundle_id": bundle_id,
            "project_id": project_id,
            "workspace_id": workspace_id,
            "revision": revision,
            "timeline_hash": t_hash,
            "export_format": adapter_id,
            "tracks_count": len(timeline.tracks),
            "captions_count": len(timeline.captions),
            "clips": clips_manifest_list
        }
        manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # 3.3 Sinh file loss_report.json
        loss_report_path = export_dir / "loss_report.json"
        loss_report_data = {
            "bundle_id": bundle_id,
            "timeline_hash": t_hash,
            "loss_report": loss_report,
            "adapter_id": adapter_id
        }
        loss_report_path.write_text(json.dumps(loss_report_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # 4. Danh sach file trong goi ban giao
        files = [
            f"{bundle_id}/timeline.xml",
            f"{bundle_id}/manifest.json",
            f"{bundle_id}/loss_report.json"
        ]

        bundle = GoiBanGiao(
            bundle_id=bundle_id,
            project_id=project_id,
            revision=revision,
            timeline_hash=t_hash,
            export_format=adapter_id,
            files=files,
            loss_report=loss_report
        )

        # Luu tru vao ca kho ben vung va RAM
        KhoLuuTruDung.luu_goi_ban_giao({
            "bundle_id": bundle_id,
            "project_id": project_id,
            "workspace_id": workspace_id,
            "revision": revision,
            "timeline_hash": t_hash,
            "export_format": adapter_id,
            "files": files,
            "loss_report": loss_report
        })
        cls._bundles_store[bundle_id] = bundle
        return bundle

    @classmethod
    def kiem_tra_goi_relink(cls, bundle_id: str, project_id: Optional[str] = None) -> bool:
        """Kiem tra cac file vat ly cua goi ban giao thuc su ton tai va doc duoc."""
        proj = project_id or (bundle_id.split("_")[1] if "_" in bundle_id else "unknown")
        export_dir = cls._lay_thu_muc_xuat(proj, bundle_id)
        
        xml_p = export_dir / "timeline.xml"
        man_p = export_dir / "manifest.json"
        rep_p = export_dir / "loss_report.json"

        if not (xml_p.exists() and man_p.exists() and rep_p.exists()):
            return False

        # Parse test de dam bao khong corrupt
        try:
            ET.parse(str(xml_p))
            json.loads(man_p.read_text(encoding="utf-8"))
            json.loads(rep_p.read_text(encoding="utf-8"))
            return True
        except Exception:
            return False

    @classmethod
    def nhap_phien_ban_native(
        cls,
        bundle_id: str,
        timeline_base: TimelineV2,
        native_project_asset_id: str,
        native_hash: str
    ) -> TimelineV2:
        bundle = cls._bundles_store.get(bundle_id)
        if not bundle:
            b_data = KhoLuuTruDung.lay_goi_ban_giao(bundle_id)
            if b_data:
                bundle = GoiBanGiao(**b_data)
                cls._bundles_store[bundle_id] = bundle

        if not bundle:
            raise ValueError(f"Khong tim thay bundle_id {bundle_id}")

        new_timeline = copy.deepcopy(timeline_base)
        new_timeline.representation_mode = "NATIVE_BOUND"
        new_timeline.native_project_asset_id = native_project_asset_id
        new_timeline.native_hash = native_hash

        return new_timeline

    @classmethod
    def kiem_tra_render_native_bound(
        cls,
        timeline: TimelineV2,
        actual_native_file_hash: str
    ) -> bool:
        if timeline.representation_mode == "NATIVE_BOUND":
            if not timeline.native_hash or timeline.native_hash != actual_native_file_hash:
                raise ValueError(f"Xung dot ma bam file native: timeline yeu cau {timeline.native_hash} nhung file hien tai la {actual_native_file_hash}. Chặn render de tranh mat finishing!")
        return True

    @classmethod
    def sua_tiep_tren_native(
        cls,
        timeline: TimelineV2,
        op_type: str,
        payload: Dict[str, Any]
    ) -> TimelineV2:
        if timeline.representation_mode == "NATIVE_BOUND":
            # Cac op duoc adapter native ho tro
            supported_native_ops = {"set_caption_text", "set_clip_gain", "trim_clip"}
            if op_type not in supported_native_ops:
                raise ValueError(f"{LoiHopDong.NATIVE_EDIT_REQUIRED}: Thao tac {op_type} khong duoc ho tro tren che do NATIVE_BOUND. Can chuyen sang Editor thao tac tren NLE!")

        # Thuc hien cap nhat ma van bao toan native_hash
        new_t = copy.deepcopy(timeline)
        if op_type == "set_caption_text":
            cap_id = payload["caption_id"]
            for c in new_t.captions:
                if c.caption_id == cap_id:
                    c.text = payload["text"]

        return new_t

    @classmethod
    def bake_sang_canonical(
        cls,
        timeline: TimelineV2,
        approval_id: str
    ) -> TimelineV2:
        if not approval_id:
            raise ValueError("Bake tu NATIVE_BOUND sang CANONICAL bat buoc phai co approval_id tu nguoi co tham quyen")

        forked = copy.deepcopy(timeline)
        forked.representation_mode = "CANONICAL"
        # Luu tru provenance ve nhanh goc
        forked.native_project_asset_id = timeline.native_project_asset_id
        forked.native_hash = None
        return forked
