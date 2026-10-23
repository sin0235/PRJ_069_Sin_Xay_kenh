from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .hop_dong import (
    TimelineV2,
    DinhDanhPhien,
    ChinhSachPhien,
    LoiHopDong
)
from .kho_luu_tru import KhoLuuTruDung


class BanNhapDung(BaseModel):
    draft_id: str
    run_id: str
    project_id: str
    workspace_id: str
    base_revision: int
    base_hash: str
    draft_revision: int = 1
    draft_hash: str
    timeline: TimelineV2
    is_locked: bool = False
    is_committed: bool = False
    committed_version: Optional[int] = None


class CheckpointPhien(BaseModel):
    checkpoint_id: str
    run_id: str
    project_id: str
    workspace_id: str = "default_ws"
    step_count: int = 0
    consecutive_error_count: int = 0
    last_error_fingerprint: Optional[str] = None
    status: str = "EDITING"  # CREATED | EDITING | COMPLETED | FAILED | CANCELLED | WAITING_HUMAN
    saved_draft_ids: List[str] = Field(default_factory=list)
    pending_operation_ids: List[str] = Field(default_factory=list)
    cost_reserved_usd: float = 0.0
    cost_actual_usd: float = 0.0
    updated_at_epoch: float = Field(default_factory=time.time)


class QuanLyPhienDung:
    """
    Quan ly vong doi phien dung, ban nhap (draft), CAS (Compare-And-Swap),
    khoa lien tien trinh va phuc hoi checkpoint (Idempotent Resume).
    Luu tru ben vung tren SQLite (KhoLuuTruDung) dam bao phuc hoi sau restart
    va dong bo nhat quan giua cac worker.
    """
    _lock = threading.RLock()
    _active_runs: Dict[str, DinhDanhPhien] = {}
    _drafts: Dict[str, BanNhapDung] = {}
    _checkpoints: Dict[str, CheckpointPhien] = {}
    _operation_journal: Dict[str, Dict[str, Any]] = {}
    _project_active_writer: Dict[str, str] = {}  # project_id -> run_id

    @classmethod
    def tinh_hash_timeline(cls, timeline: TimelineV2) -> str:
        data = timeline.model_dump(mode="json")
        encoded = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def xoa_toan_bo_du_lieu_tam(cls) -> None:
        """Dung de reset test."""
        with cls._lock:
            cls._active_runs.clear()
            cls._drafts.clear()
            cls._checkpoints.clear()
            cls._operation_journal.clear()
            cls._project_active_writer.clear()
            KhoLuuTruDung.xoa_toan_bo_du_lieu()

    @classmethod
    def kiem_tra_so_huu_du_an(cls, project_id: str, workspace_id: str) -> None:
        """Kiem tra du an da ton tai voi workspace khac hay chua de ngan chan cross-workspace access."""
        lease = KhoLuuTruDung.lay_active_writer_lease(project_id)
        if lease and lease.get("workspace_id") and lease["workspace_id"] != workspace_id:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Du an {project_id} thuoc workspace {lease['workspace_id']}, khong the truy cap tu {workspace_id}")

    @classmethod
    def tao_phien(
        cls,
        project_id: str,
        workspace_id: str,
        actor_id: str,
        base_revision: int,
        base_hash: str,
        policy: Optional[ChinhSachPhien] = None
    ) -> DinhDanhPhien:
        cls.kiem_tra_so_huu_du_an(project_id, workspace_id)

        with cls._lock:
            # 1. Chong hai writer cung ghi 1 project qua persistent lease
            existing_lease = KhoLuuTruDung.lay_active_writer_lease(project_id)
            if existing_lease:
                existing_run = existing_lease["run_id"]
                cp_data = KhoLuuTruDung.lay_checkpoint(existing_run)
                if cp_data and cp_data.get("status") in ("EDITING", "CREATED"):
                    # Kiem tra lease timeout (30 phut)
                    if time.time() - cp_data["updated_at_epoch"] < 1800:
                        raise ValueError(f"{LoiHopDong.OCC_CONFLICT_409}: Project dang co phien ghi hoat dong {existing_run}")

            run_id = f"run_{project_id}_{int(time.time()*1000)}"
            pol_ver = policy.policy_version if policy else "POLICY_V1_2026_10_23"
            phien = DinhDanhPhien(
                run_id=run_id,
                project_id=project_id,
                workspace_id=workspace_id,
                actor_id=actor_id,
                base_revision=base_revision,
                base_hash=base_hash,
                policy_version=pol_ver
            )

            # Luu tru vao kho ben vung
            KhoLuuTruDung.luu_phien(phien.model_dump())
            KhoLuuTruDung.dang_ky_writer_lease(project_id, run_id, workspace_id)

            # Tao Checkpoint ban dau
            cp = CheckpointPhien(
                checkpoint_id=f"cp_{run_id}_0",
                run_id=run_id,
                project_id=project_id,
                workspace_id=workspace_id,
                status="CREATED"
            )
            KhoLuuTruDung.luu_checkpoint(cp.model_dump())

            # Cap nhat memory cache
            cls._active_runs[run_id] = phien
            cls._project_active_writer[project_id] = run_id
            cls._checkpoints[run_id] = cp

            return phien

    @classmethod
    def lay_phien(cls, run_id: str) -> Optional[DinhDanhPhien]:
        with cls._lock:
            if run_id in cls._active_runs:
                return cls._active_runs[run_id]
            data = KhoLuuTruDung.lay_phien(run_id)
            if data:
                p = DinhDanhPhien(**data)
                cls._active_runs[run_id] = p
                return p
            return None

    @classmethod
    def xac_thuc_run(cls, run_id: str, project_id: str, workspace_id: str) -> DinhDanhPhien:
        phien = cls.lay_phien(run_id)
        if not phien:
            raise ValueError(f"Khong tim thay run_id {run_id}")
        if phien.workspace_id != workspace_id:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Run {run_id} khong thuoc workspace {workspace_id}")
        if phien.project_id != project_id:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Run {run_id} khong thuoc du an {project_id}")
        return phien

    @classmethod
    def tao_ban_nhap(
        cls,
        run_id: str,
        timeline_base: TimelineV2
    ) -> BanNhapDung:
        with cls._lock:
            phien = cls.lay_phien(run_id)
            if not phien:
                raise ValueError(f"Khong tim thay run_id {run_id}")

            draft_id = f"draft_{phien.project_id}_{int(time.time()*1000)}"
            t_copy = copy.deepcopy(timeline_base)
            draft_hash = cls.tinh_hash_timeline(t_copy)

            ban_nhap = BanNhapDung(
                draft_id=draft_id,
                run_id=run_id,
                project_id=phien.project_id,
                workspace_id=phien.workspace_id,
                base_revision=phien.base_revision,
                base_hash=phien.base_hash,
                draft_revision=1,
                draft_hash=draft_hash,
                timeline=t_copy
            )

            # Luu tru ben vung
            draft_data = ban_nhap.model_dump(mode="json")
            KhoLuuTruDung.luu_ban_nhap(draft_data)
            cls._drafts[draft_id] = ban_nhap

            # Ghi nhan vao checkpoint
            cp_data = KhoLuuTruDung.lay_checkpoint(run_id)
            if cp_data:
                saved_draft_ids = cp_data.get("saved_draft_ids", [])
                if draft_id not in saved_draft_ids:
                    saved_draft_ids.append(draft_id)
                cp_data["saved_draft_ids"] = saved_draft_ids
                cp_data["status"] = "EDITING"
                cp_data["updated_at_epoch"] = time.time()
                KhoLuuTruDung.luu_checkpoint(cp_data)
                cls._checkpoints[run_id] = CheckpointPhien(**cp_data)

            return ban_nhap

    @classmethod
    def lay_ban_nhap(cls, draft_id: str) -> BanNhapDung:
        with cls._lock:
            if draft_id in cls._drafts:
                return cls._drafts[draft_id]

            # Tra cuu tu kho ben vung SQLite
            draft_dict = KhoLuuTruDung.lay_ban_nhap(draft_id)
            if not draft_dict:
                raise ValueError(f"Khong tim thay ban nhap {draft_id}")

            draft = BanNhapDung(**draft_dict)
            cls._drafts[draft_id] = draft
            return draft

    @classmethod
    def xac_thuc_draft(cls, draft_id: str, project_id: str, workspace_id: str) -> BanNhapDung:
        draft = cls.lay_ban_nhap(draft_id)
        if draft.workspace_id != workspace_id:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Ban nhap {draft_id} khong thuoc workspace {workspace_id}")
        if draft.project_id != project_id:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Ban nhap {draft_id} khong thuoc du an {project_id}")
        return draft

    @classmethod
    def cap_nhat_ban_nhap(
        cls,
        draft_id: str,
        expected_revision: int,
        timeline_moi: TimelineV2
    ) -> BanNhapDung:
        with cls._lock:
            draft = cls.lay_ban_nhap(draft_id)
            if draft.is_locked:
                raise ValueError(f"{LoiHopDong.OCC_CONFLICT_409}: Ban nhap {draft_id} da bi khoa, khong duoc phep sua")

            if draft.draft_revision != expected_revision:
                raise ValueError(f"{LoiHopDong.OCC_CONFLICT_409}: Xung dot phien ban (Stale Revision). Hien tai la {draft.draft_revision}, nhung client gui expected {expected_revision}")

            draft.draft_revision += 1
            draft.timeline = copy.deepcopy(timeline_moi)
            draft.draft_hash = cls.tinh_hash_timeline(draft.timeline)

            # Luu vao kho ben vung
            KhoLuuTruDung.luu_ban_nhap(draft.model_dump(mode="json"))
            cls._drafts[draft_id] = draft

            # Cap nhat checkpoint
            cp_data = KhoLuuTruDung.lay_checkpoint(draft.run_id)
            if cp_data:
                cp_data["step_count"] = cp_data.get("step_count", 0) + 1
                cp_data["updated_at_epoch"] = time.time()
                KhoLuuTruDung.luu_checkpoint(cp_data)
                cls._checkpoints[draft.run_id] = CheckpointPhien(**cp_data)

            return draft

    @classmethod
    def tiep_tuc_phien(cls, run_id: str) -> CheckpointPhien:
        """
        Phuc hoi phien sau restart tu checkpoint cu trong kho ben vung SQLite.
        """
        with cls._lock:
            cp_data = KhoLuuTruDung.lay_checkpoint(run_id)
            if not cp_data:
                raise ValueError(f"Khong tim thay checkpoint cho run_id {run_id}")

            cp_data["updated_at_epoch"] = time.time()
            KhoLuuTruDung.luu_checkpoint(cp_data)
            cp = CheckpointPhien(**cp_data)
            cls._checkpoints[run_id] = cp
            return cp

    @classmethod
    def huy_phien(cls, run_id: str) -> None:
        with cls._lock:
            cp_data = KhoLuuTruDung.lay_checkpoint(run_id)
            if cp_data:
                cp_data["status"] = "CANCELLED"
                KhoLuuTruDung.luu_checkpoint(cp_data)
                cls._checkpoints[run_id] = CheckpointPhien(**cp_data)

            phien = cls.lay_phien(run_id)
            if phien:
                KhoLuuTruDung.giai_phong_writer_lease(phien.project_id, run_id)
                if cls._project_active_writer.get(phien.project_id) == run_id:
                    del cls._project_active_writer[phien.project_id]

    @classmethod
    def commit_ban_nhap(
        cls,
        draft_id: str,
        expected_revision: int,
        approval_id: str
    ) -> int:
        with cls._lock:
            draft = cls.lay_ban_nhap(draft_id)
            if draft.is_committed:
                raise ValueError(f"Ban nhap {draft_id} da duoc commit truoc do")

            if draft.draft_revision != expected_revision:
                raise ValueError(f"{LoiHopDong.OCC_CONFLICT_409}: Xung dot phien ban khi commit")

            if not approval_id:
                raise ValueError("Commit ban nhap bat buoc phai co approval_id hop le tu nguoi co tham quyen")

            # Ghi nhan version moi duy nhat
            new_version = draft.base_revision + 1
            draft.is_committed = True
            draft.is_locked = True
            draft.committed_version = new_version

            # Luu vao kho ben vung
            KhoLuuTruDung.luu_ban_nhap(draft.model_dump(mode="json"))
            cls._drafts[draft_id] = draft

            # Giai phong writer lock va cap nhat checkpoint
            cp_data = KhoLuuTruDung.lay_checkpoint(draft.run_id)
            if cp_data:
                cp_data["status"] = "COMPLETED"
                KhoLuuTruDung.luu_checkpoint(cp_data)
                cls._checkpoints[draft.run_id] = CheckpointPhien(**cp_data)

            KhoLuuTruDung.giai_phong_writer_lease(draft.project_id, draft.run_id)
            if draft.project_id in cls._project_active_writer:
                if cls._project_active_writer[draft.project_id] == draft.run_id:
                    del cls._project_active_writer[draft.project_id]

            return new_version
