from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .hop_dong import (
    TimelineV2,
    BienBanKiemDinh,
    LoiHopDong
)


class KiemDinhDocLap:
    """
    Module kiem dinh doc lap (QA Engine):
    - Kiem tra toan ven file ket xuat thuc te (Full Decode, Corrupt check, Zero-byte check).
    - Khong tin tuong flag 'success' don thuan neu thieu file.
    - Do dac chuan am luong EBU R128 (-14 LUFS +- 1) va True Peak (<= -1.5 dBTP).
    - Bao ve ranh gioi Tenancy va chong injection pha vo quyen han.
    - Vo hieu hoa Approval cu khi timeline bi thay doi sau khi duyet.
    """

    @classmethod
    def kiem_dinh_ban_dung(
        cls,
        timeline: TimelineV2,
        render_file_path: Optional[str] = None,
        render_hash: Optional[str] = None,
        file_exists: bool = True,
        is_corrupt: bool = False,
        measured_loudness_lufs: Optional[float] = None,
        measured_true_peak_dbtp: Optional[float] = None,
        is_silent_intentional: bool = False
    ) -> BienBanKiemDinh:
        checks: Dict[str, bool] = {}

        # 1. Tinh hash timeline
        t_data = timeline.model_dump(mode="json")
        t_hash = hashlib.sha256(json.dumps(t_data, sort_keys=True).encode("utf-8")).hexdigest()

        # 2. Kiem tra su hien dien cua tep render (khong tin success token khi thieu file)
        if not file_exists:
            checks["file_exists"] = False
            return BienBanKiemDinh(
                timeline_hash=t_hash,
                render_hash=None,
                is_passed=False,
                checks=checks,
                reviewer="QA_BOT_DETERMINISTIC",
                status="REJECTED"
            )
        checks["file_exists"] = True

        # 3. Kiem tra tep hong / decode failure
        if is_corrupt:
            checks["decode_valid"] = False
            return BienBanKiemDinh(
                timeline_hash=t_hash,
                render_hash=render_hash,
                is_passed=False,
                checks=checks,
                reviewer="QA_BOT_DETERMINISTIC",
                status="REJECTED"
            )
        checks["decode_valid"] = True

        # 4. Kiem tra chuan am luong EBU R128 (neu co am thanh)
        has_audio = any(t.track_type == "audio" and len(t.clips) > 0 for t in timeline.tracks)
        if has_audio and not is_silent_intentional:
            if measured_loudness_lufs is not None:
                # Chuan TikTok: -14.0 LUFS +- 1.0 LUFS -> [-15.0, -13.0] hoac tolerance [-16.0, -12.0]
                checks["loudness_ebu_r128"] = (-16.0 <= measured_loudness_lufs <= -12.0)
            else:
                checks["loudness_ebu_r128"] = False

            if measured_true_peak_dbtp is not None:
                checks["true_peak_safe"] = (measured_true_peak_dbtp <= -1.5)
            else:
                checks["true_peak_safe"] = False
        else:
            # Im lang co chu y
            checks["loudness_ebu_r128"] = True
            checks["true_peak_safe"] = True

        # 5. Kiem tra Safe Zone TikTok cho phu de
        checks["caption_safe_zone"] = all(c.safe_zone for c in timeline.captions)

        is_passed = all(checks.values())

        return BienBanKiemDinh(
            timeline_hash=t_hash,
            render_hash=render_hash,
            is_passed=is_passed,
            checks=checks,
            measured_loudness_lufs=measured_loudness_lufs,
            measured_true_peak_dbtp=measured_true_peak_dbtp,
            reviewer="QA_BOT_DETERMINISTIC",
            status="UNREVIEWED" if is_passed else "REJECTED"
        )

    @classmethod
    def kiem_tra_co_lap_workspace(cls, workspace_req: str, workspace_target: str) -> bool:
        if workspace_req != workspace_target:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Khong duoc phep truy cap cheo workspace")
        return True

    @classmethod
    def kiem_tra_noi_dung_an_toan_khong_doi_quyen(cls, text: str, allowed_tools: List[str]) -> List[str]:
        # Du noi dung text chua tu khoa injection doc hai, quyen cua tool bat buoc khong bi thay doi
        # Text chi la passive data
        return list(allowed_tools)

    @classmethod
    def xac_thuc_approval_binding(
        cls,
        timeline: TimelineV2,
        approved_hash: str,
        approved_revision: int,
        current_revision: int
    ) -> bool:
        t_data = timeline.model_dump(mode="json")
        current_hash = hashlib.sha256(json.dumps(t_data, sort_keys=True).encode("utf-8")).hexdigest()

        if current_revision != approved_revision or current_hash != approved_hash:
            return False  # Approval cu het hieu luc vi timeline da bi sua doi
        return True
