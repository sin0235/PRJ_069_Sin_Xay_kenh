from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .hop_dong import BangChungNguon


class CauHinhPhanTich(BaseModel):
    analysis_version: str = "1.0"
    enable_asr: bool = True
    enable_visual: bool = True
    min_confidence_threshold: float = 0.5
    dense_sampling_fps: int = 5  # FPS day khi phat hien canh nhanh


class BoHieuTuLieu:
    """
    Module hieu tu lieu da phuong thuc (ASR, Visual evidence, Scene detection).
    Co lap cache theo workspace, bao ve ranh gioi SHA256 va khong bia dat evidence.
    """
    # Cache key: (workspace_id, asset_id) -> { "sha256": str, "evidence": list[BangChungNguon] }
    _cache: Dict[tuple[str, str], Dict[str, Any]] = {}

    @classmethod
    def phan_tich_tu_lieu(
        cls,
        workspace_id: str,
        asset_id: str,
        source_sha256: str,
        transcript_data: Optional[List[Dict[str, Any]]] = None,
        scenes_data: Optional[List[Dict[str, Any]]] = None,
        config: Optional[CauHinhPhanTich] = None
    ) -> List[BangChungNguon]:
        cfg = config or CauHinhPhanTich()
        cache_key = (workspace_id, asset_id)

        # 1. Kiem tra cache va kiem tra SHA256 invalidation
        if cache_key in cls._cache:
            entry = cls._cache[cache_key]
            if entry["sha256"] == source_sha256:
                return entry["evidence"]
            else:
                # SHA256 thay doi -> Vo hieu hoa toan bo cache cu
                del cls._cache[cache_key]

        evidence_list: List[BangChungNguon] = []

        # 2. Xu ly ASR Tieng Viet
        if cfg.enable_asr and transcript_data:
            for idx, item in enumerate(transcript_data):
                text = item.get("text", "").strip()
                # Neu la khoang lang (silence) hoac khong co tu -> Khong bia dat transcript
                is_silence = item.get("is_silence", False)
                if not text or is_silence:
                    continue

                words = item.get("words", [])
                word_ids = [w.get("word_id", f"w_{idx}_{w_idx}") for w_idx, w in enumerate(words)]
                
                # Confidence: Neu provider khong tra, bat buoc giu None, khong tu gan gia tri
                conf = item.get("confidence")

                ev_speech = BangChungNguon(
                    evidence_id=f"ev_sp_{asset_id}_{idx}",
                    asset_id=asset_id,
                    source_sha256=source_sha256,
                    analysis_version=cfg.analysis_version,
                    modality="speech",
                    source_range={
                        "start_ms": item.get("start_ms", 0),
                        "end_ms": item.get("end_ms", 1000)
                    },
                    word_ids=word_ids,
                    confidence=conf,
                    notes=text
                )
                evidence_list.append(ev_speech)

        # 3. Xu ly Visual Evidence & Canh nhanh (Rapid scenes)
        if cfg.enable_visual and scenes_data:
            for idx, sc in enumerate(scenes_data):
                start_ms = sc.get("start_ms", 0)
                end_ms = sc.get("end_ms", 1000)
                dur_ms = end_ms - start_ms

                # Canh qua nhanh (< 300ms, vi du 200ms) khong duoc ket luan voi lay mau thua
                sampled_fps = sc.get("sampled_fps", 1)
                is_rapid = dur_ms <= 300

                notes = sc.get("label", "Scene segment")
                if is_rapid and sampled_fps < cfg.dense_sampling_fps:
                    # Yeu cau xem bo sung voi mau day (dense sampling)
                    notes += " [CAN_XEM_BO_SUNG_DENSE_SAMPLING]"

                ev_vis = BangChungNguon(
                    evidence_id=f"ev_vis_{asset_id}_{idx}",
                    asset_id=asset_id,
                    source_sha256=source_sha256,
                    analysis_version=cfg.analysis_version,
                    modality="visual",
                    source_range={"start_ms": start_ms, "end_ms": end_ms},
                    frame_ids=sc.get("frame_ids", [f"frame_{idx}"]),
                    confidence=sc.get("confidence"),
                    notes=notes
                )
                evidence_list.append(ev_vis)

        # 4. Luu vao cache co lap theo workspace
        cls._cache[cache_key] = {
            "sha256": source_sha256,
            "evidence": evidence_list
        }

        return evidence_list

    @classmethod
    def tim_tu_lieu_theo_tu_khoa(
        cls,
        workspace_id: str,
        asset_id: str,
        query: str
    ) -> List[BangChungNguon]:
        cache_key = (workspace_id, asset_id)
        if cache_key not in cls._cache:
            return []

        q = query.lower()
        results: List[BangChungNguon] = []
        for ev in cls._cache[cache_key]["evidence"]:
            if ev.notes and q in ev.notes.lower():
                results.append(ev)
        return results

    @classmethod
    def xoa_cache_workspace(cls, workspace_id: str) -> None:
        keys_to_del = [k for k in cls._cache if k[0] == workspace_id]
        for k in keys_to_del:
            del cls._cache[k]
