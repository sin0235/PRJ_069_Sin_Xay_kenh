from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .hop_dong import (
    TimelineV2,
    BangChungNguon,
    ChinhSachPhien,
    KeHoachDung,
    LenhDung,
    LoiHopDong,
    kiem_tra_ke_hoach
)


class YeuCauPhanHoi(BaseModel):
    feedback_id: str
    target_clip_id: Optional[str] = None
    timecode_ms: Optional[int] = None
    instruction: str
    preserve_list: List[str] = Field(default_factory=list)
    base_revision: int


class RecipeDung(BaseModel):
    recipe_id: str
    version: str = "1.0"
    recipe_type: str = Field(description="dung_co_loi | product_montage | dung_tu_anh | da_camera | sua_canh_flow")
    description: str
    checklist: List[str] = Field(default_factory=list)


RECIPES_CHUAN: Dict[str, RecipeDung] = {
    "dung_co_loi": RecipeDung(
        recipe_id="rcp_speech_01",
        version="1.0",
        recipe_type="dung_co_loi",
        description="Dung video ngan tu footage co thoai: Hook 3s dau, truyen tai thong diep chinh, CTA cuoi",
        checklist=["Chon phan doan co confidence ASR cao", "Giu safe zone cho phu de", "Auto-ducking nhac nen khi co giong doc"]
    ),
    "product_montage": RecipeDung(
        recipe_id="rcp_product_01",
        version="1.0",
        recipe_type="product_montage",
        description="Dung video gioi thieu san pham khong thoai: nhip nhanh theo beat, visual bat mat",
        checklist=["Chon cac canh quay can canh sac net", "Cat dung theo nhip am thanh", "Khong bia dat transcript cho footage im lang"]
    ),
    "dung_tu_anh": RecipeDung(
        recipe_id="rcp_image_01",
        version="1.0",
        recipe_type="dung_tu_anh",
        description="Dung video tu bo suu tap anh tinh: ken burns keyframe chuyen dong, logo, text overlay",
        checklist=["Scale keyframe 1.0 -> 1.15", "Thoi luong 2.5s moi anh", "Dat logo o vi tri an toan"]
    ),
    "da_camera": RecipeDung(
        recipe_id="rcp_multicam_01",
        version="1.0",
        recipe_type="da_camera",
        description="Dung talkshow hoac huong dan tu 2 goc camera va audio roi",
        checklist=["Dong bo audio tai clap marker", "Chuyen goc may phu hop voi nguoi noi", "Bao toan dong bo audio master"]
    ),
    "sua_canh_flow": RecipeDung(
        recipe_id="rcp_flow_repair_01",
        version="1.0",
        recipe_type="sua_canh_flow",
        description="Sua visual mot phan canh bang Flow hoac Gemini API",
        checklist=["Xac dinh ro target_clip_id can sua", "Dinh nghia preserve list nghiem ngat", "Kiem tra thoi luong khop 100%"]
    )
}


class DaoDienDung:
    """
    Agent dao dien lap ke hoach dung rough cut, sua theo phan hoi
    va tu gioi han so luot/cong cu/vong lap.
    """

    @classmethod
    def lap_ke_hoach(
        cls,
        brief: Dict[str, Any],
        snapshot: TimelineV2,
        evidence: List[BangChungNguon],
        policy: ChinhSachPhien
    ) -> KeHoachDung:
        plan_id = f"plan_{brief.get('brief_id', 'default')}_{int(len(evidence))}"
        recipe_type = brief.get("type", "dung_co_loi")
        recipe = RECIPES_CHUAN.get(recipe_type, RECIPES_CHUAN["dung_co_loi"])

        evidence_by_id = {e.evidence_id: e for e in evidence}
        commands: List[LenhDung] = []
        missing_evidence: List[str] = []

        # Kiem tra brief co yeu cau bang chung nao dac thu khong
        target_evidence_ids = brief.get("required_evidence_ids", [])
        for tid in target_evidence_ids:
            if tid not in evidence_by_id:
                missing_evidence.append(tid)

        # Neu khong co evidence nao duoc cung cap cho brief co thoai
        if recipe_type == "dung_co_loi" and not any(e.modality == "speech" for e in evidence):
            missing_evidence.append("ASR_SPEECH_EVIDENCE_REQUIRED")

        # Sinh cac lenh rough cut tu evidence hop le
        current_frame = 0
        fps = float(snapshot.fps_num) / float(snapshot.fps_den)

        for e in evidence:
            if e.modality == "speech":
                start_ms = e.source_range.get("start_ms", 0)
                end_ms = e.source_range.get("end_ms", 1000)
                dur_ms = end_ms - start_ms
                dur_frames = max(1, int(round((dur_ms / 1000.0) * fps)))

                cmd = LenhDung(
                    operation_id=f"cmd_rough_{e.evidence_id}",
                    draft_id=brief.get("draft_id", "draft_tmp"),
                    expected_draft_revision=1,
                    type="insert_clip",
                    payload={
                        "track_id": "trk_v1",
                        "asset_id": e.asset_id,
                        "at_frame": current_frame,
                        "duration_frames": dur_frames,
                        "clip_id": f"clip_{e.evidence_id}"
                    },
                    evidence_ids=[e.evidence_id]
                )
                commands.append(cmd)
                current_frame += dur_frames

        estimated_cost = len(commands) * 0.1  # 0.1 USD per command

        plan = KeHoachDung(
            plan_id=plan_id,
            brief_id=brief.get("brief_id", "b1"),
            base_revision=1,
            proposed_commands=commands,
            missing_evidence=missing_evidence,
            estimated_cost_usd=estimated_cost
        )

        return plan

    @classmethod
    def lap_ke_hoach_sua(
        cls,
        feedback: YeuCauPhanHoi,
        snapshot: TimelineV2,
        evidence: List[BangChungNguon],
        policy: ChinhSachPhien
    ) -> KeHoachDung:
        # 1. Kiem tra phan hoi mo ho (Ambiguous feedback detection)
        text = feedback.instruction.lower().strip()
        tu_khoa_mo_ho = ["cho đẹp hơn", "làm hay hơn", "chỉnh lại đi", "nhìn chán quá", "sao cũng được"]
        if any(kw in text for kw in tu_khoa_mo_ho) and not feedback.target_clip_id and feedback.timecode_ms is None:
            # Phan hoi qua mo ho -> Tu choi sua linh tinh, yeu cau lam ro
            return KeHoachDung(
                plan_id=f"plan_ambiguous_{feedback.feedback_id}",
                brief_id=feedback.feedback_id,
                base_revision=feedback.base_revision,
                proposed_commands=[],
                missing_evidence=["FEEDBACK_AMBIGUOUS_NEEDS_CLARIFICATION"],
                estimated_cost_usd=0.0
            )

        commands: List[LenhDung] = []

        # 2. Xac dinh clip can sua
        target_clip_id = feedback.target_clip_id
        if not target_clip_id and feedback.timecode_ms is not None:
            # Tim clip tai timecode
            fps = float(snapshot.fps_num) / float(snapshot.fps_den)
            target_frame = int(round((feedback.timecode_ms / 1000.0) * fps))
            for trk in snapshot.tracks:
                for c in trk.clips:
                    if c.start_frame <= target_frame <= c.start_frame + c.duration_frames:
                        target_clip_id = c.clip_id
                        break

        # 3. Tao patch chi tac dong vao target clip
        if target_clip_id:
            if "nhạc" in text or "volume" in text or "tiếng" in text:
                cmd = LenhDung(
                    operation_id=f"cmd_fix_{feedback.feedback_id}",
                    draft_id="draft_tmp",
                    expected_draft_revision=feedback.base_revision,
                    type="set_clip_gain",
                    payload={"track_id": "trk_v1", "clip_id": target_clip_id, "gain_db": -6.0}
                )
                commands.append(cmd)
            elif "cắt" in text or "trim" in text:
                cmd = LenhDung(
                    operation_id=f"cmd_fix_{feedback.feedback_id}",
                    draft_id="draft_tmp",
                    expected_draft_revision=feedback.base_revision,
                    type="trim_clip",
                    payload={"track_id": "trk_v1", "clip_id": target_clip_id, "trim_in_ms": 0, "trim_out_ms": 2000}
                )
                commands.append(cmd)

        return KeHoachDung(
            plan_id=f"plan_fix_{feedback.feedback_id}",
            brief_id=feedback.feedback_id,
            base_revision=feedback.base_revision,
            proposed_commands=commands,
            missing_evidence=[] if target_clip_id else ["TARGET_CLIP_NOT_FOUND"],
            estimated_cost_usd=0.05
        )

    @classmethod
    def kiem_tra_vong_lap_khong_tien_trien(
        cls,
        consecutive_identical_errors: int,
        consecutive_no_change_steps: int
    ) -> bool:
        """
        Dung khan cap neu 3 buoc lien tiep cung fingerprint loi hoac khong lam thay doi draft
        """
        if consecutive_identical_errors >= 3 or consecutive_no_change_steps >= 3:
            return True
        return False
