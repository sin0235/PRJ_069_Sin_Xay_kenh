# -*- coding: utf-8 -*-
"""
Kho lưu trữ trạng thái bền vững (Persistent Storage Engine) cho module Điều Phối Dựng Video.
Bảo đảm tính Idempotent, chống xung đột ghi (OCC/Lease), duy trì qua service restart
và an toàn đa tiến trình/đa worker bằng SQLite WAL mode.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class KhoLuuTruDung:
    _lock = threading.RLock()
    _db_path: Optional[Path] = None

    @classmethod
    def lay_duong_dan_db(cls) -> Path:
        if cls._db_path is not None:
            return cls._db_path
        env_path = os.getenv("SIN_DUNG_DB_PATH")
        if env_path:
            cls._db_path = Path(env_path)
        else:
            api_root = Path(__file__).resolve().parents[3]
            cls._db_path = api_root / "sin_dieu_phoi_dung.db"
        cls._khoi_tao_schema(cls._db_path)
        return cls._db_path

    @classmethod
    def dat_duong_dan_db(cls, path: Path) -> None:
        with cls._lock:
            cls._db_path = path
            cls._khoi_tao_schema(path)

    @classmethod
    def ket_noi(cls) -> sqlite3.Connection:
        db_path = cls.lay_duong_dan_db()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(db_path),
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @classmethod
    def _khoi_tao_schema(cls, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 30000")
            with conn:
                conn.execute("""
                CREATE TABLE IF NOT EXISTS phien_dung (
                    run_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    base_revision INTEGER NOT NULL,
                    base_hash TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """)
                conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_phien_proj_ws 
                ON phien_dung(project_id, workspace_id)
                """)

                conn.execute("""
                CREATE TABLE IF NOT EXISTS ban_nhap (
                    draft_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    base_revision INTEGER NOT NULL,
                    base_hash TEXT NOT NULL,
                    draft_revision INTEGER NOT NULL,
                    draft_hash TEXT NOT NULL,
                    timeline_json TEXT NOT NULL,
                    is_locked INTEGER NOT NULL DEFAULT 0,
                    is_committed INTEGER NOT NULL DEFAULT 0,
                    committed_version INTEGER,
                    updated_at REAL NOT NULL
                )
                """)
                conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_draft_proj_ws 
                ON ban_nhap(project_id, workspace_id)
                """)

                conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoint_phien (
                    run_id TEXT PRIMARY KEY,
                    checkpoint_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    step_count INTEGER NOT NULL DEFAULT 0,
                    consecutive_error_count INTEGER NOT NULL DEFAULT 0,
                    last_error_fingerprint TEXT,
                    status TEXT NOT NULL,
                    saved_draft_ids_json TEXT NOT NULL DEFAULT '[]',
                    pending_operation_ids_json TEXT NOT NULL DEFAULT '[]',
                    cost_reserved_usd REAL NOT NULL DEFAULT 0.0,
                    cost_actual_usd REAL NOT NULL DEFAULT 0.0,
                    updated_at_epoch REAL NOT NULL
                )
                """)

                conn.execute("""
                CREATE TABLE IF NOT EXISTS writer_leases (
                    project_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    acquired_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """)

                conn.execute("""
                CREATE TABLE IF NOT EXISTS nhat_ky_lenh (
                    operation_id TEXT PRIMARY KEY,
                    draft_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """)

                conn.execute("""
                CREATE TABLE IF NOT EXISTS don_sua_canh (
                    request_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    draft_id TEXT NOT NULL,
                    source_asset_id TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    route TEXT NOT NULL,
                    status TEXT NOT NULL,
                    don_json TEXT NOT NULL,
                    capability_json TEXT NOT NULL,
                    output_asset_id TEXT,
                    receipt_token TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """)
                conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_don_sua_proj_ws 
                ON don_sua_canh(project_id, workspace_id)
                """)

                conn.execute("""
                CREATE TABLE IF NOT EXISTS goi_ban_giao (
                    bundle_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    timeline_hash TEXT NOT NULL,
                    export_format TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    loss_report_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """)
        finally:
            conn.close()

    @classmethod
    def xoa_toan_bo_du_lieu(cls) -> None:
        """Dùng cho kiểm thử để dọn sạch database giữa các test."""
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    conn.execute("DELETE FROM phien_dung")
                    conn.execute("DELETE FROM ban_nhap")
                    conn.execute("DELETE FROM checkpoint_phien")
                    conn.execute("DELETE FROM writer_leases")
                    conn.execute("DELETE FROM nhat_ky_lenh")
                    conn.execute("DELETE FROM don_sua_canh")
                    conn.execute("DELETE FROM goi_ban_giao")
            finally:
                conn.close()

    # --- PHIÊN DỰNG (SESSIONS) ---

    @classmethod
    def luu_phien(cls, phien_dict: Dict[str, Any]) -> None:
        now = time.time()
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    conn.execute("""
                    INSERT INTO phien_dung (
                        run_id, project_id, workspace_id, actor_id,
                        base_revision, base_hash, policy_version,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        base_revision=excluded.base_revision,
                        base_hash=excluded.base_hash,
                        policy_version=excluded.policy_version,
                        updated_at=excluded.updated_at
                    """, (
                        phien_dict["run_id"],
                        phien_dict["project_id"],
                        phien_dict["workspace_id"],
                        phien_dict["actor_id"],
                        phien_dict["base_revision"],
                        phien_dict["base_hash"],
                        phien_dict.get("policy_version", "POLICY_V1_2026_10_23"),
                        now,
                        now
                    ))
            finally:
                conn.close()

    @classmethod
    def lay_phien(cls, run_id: str) -> Optional[Dict[str, Any]]:
        conn = cls.ket_noi()
        try:
            cur = conn.execute(
                "SELECT * FROM phien_dung WHERE run_id = ?",
                (run_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            conn.close()

    # --- LEASE WRITER (OCC) ---

    @classmethod
    def lay_active_writer_lease(cls, project_id: str) -> Optional[Dict[str, Any]]:
        conn = cls.ket_noi()
        try:
            cur = conn.execute(
                "SELECT * FROM writer_leases WHERE project_id = ?",
                (project_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            conn.close()

    @classmethod
    def dang_ky_writer_lease(cls, project_id: str, run_id: str, workspace_id: str) -> None:
        now = time.time()
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    conn.execute("""
                    INSERT INTO writer_leases (project_id, run_id, workspace_id, acquired_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(project_id) DO UPDATE SET
                        run_id=excluded.run_id,
                        workspace_id=excluded.workspace_id,
                        acquired_at=excluded.acquired_at,
                        updated_at=excluded.updated_at
                    """, (project_id, run_id, workspace_id, now, now))
            finally:
                conn.close()

    @classmethod
    def giai_phong_writer_lease(cls, project_id: str, run_id: Optional[str] = None) -> None:
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    if run_id:
                        conn.execute(
                            "DELETE FROM writer_leases WHERE project_id = ? AND run_id = ?",
                            (project_id, run_id)
                        )
                    else:
                        conn.execute(
                            "DELETE FROM writer_leases WHERE project_id = ?",
                            (project_id,)
                        )
            finally:
                conn.close()

    # --- BẢN NHÁP (DRAFTS) ---

    @classmethod
    def luu_ban_nhap(cls, draft_dict: Dict[str, Any]) -> None:
        now = time.time()
        timeline_json = json.dumps(draft_dict["timeline"], ensure_ascii=False)
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    conn.execute("""
                    INSERT INTO ban_nhap (
                        draft_id, run_id, project_id, workspace_id,
                        base_revision, base_hash, draft_revision, draft_hash,
                        timeline_json, is_locked, is_committed, committed_version,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(draft_id) DO UPDATE SET
                        draft_revision=excluded.draft_revision,
                        draft_hash=excluded.draft_hash,
                        timeline_json=excluded.timeline_json,
                        is_locked=excluded.is_locked,
                        is_committed=excluded.is_committed,
                        committed_version=excluded.committed_version,
                        updated_at=excluded.updated_at
                    """, (
                        draft_dict["draft_id"],
                        draft_dict["run_id"],
                        draft_dict["project_id"],
                        draft_dict["workspace_id"],
                        draft_dict["base_revision"],
                        draft_dict["base_hash"],
                        draft_dict["draft_revision"],
                        draft_dict["draft_hash"],
                        timeline_json,
                        1 if draft_dict.get("is_locked", False) else 0,
                        1 if draft_dict.get("is_committed", False) else 0,
                        draft_dict.get("committed_version"),
                        now
                    ))
            finally:
                conn.close()

    @classmethod
    def lay_ban_nhap(cls, draft_id: str) -> Optional[Dict[str, Any]]:
        conn = cls.ket_noi()
        try:
            cur = conn.execute(
                "SELECT * FROM ban_nhap WHERE draft_id = ?",
                (draft_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["timeline"] = json.loads(d["timeline_json"])
            d["is_locked"] = bool(d["is_locked"])
            d["is_committed"] = bool(d["is_committed"])
            return d
        finally:
            conn.close()

    @classmethod
    def tim_ban_nhap_theo_project_revision(
        cls,
        project_id: str,
        revision: int,
        workspace_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        conn = cls.ket_noi()
        try:
            sql = "SELECT * FROM ban_nhap WHERE project_id = ? AND (draft_revision = ? OR committed_version = ?)"
            params = [project_id, revision, revision]
            if workspace_id:
                sql += " AND workspace_id = ?"
                params.append(workspace_id)
            sql += " ORDER BY updated_at DESC LIMIT 1"
            cur = conn.execute(sql, tuple(params))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["timeline"] = json.loads(d["timeline_json"])
            d["is_locked"] = bool(d["is_locked"])
            d["is_committed"] = bool(d["is_committed"])
            return d
        finally:
            conn.close()

    # --- CHECKPOINT ---

    @classmethod
    def luu_checkpoint(cls, cp_dict: Dict[str, Any]) -> None:
        saved_drafts_json = json.dumps(cp_dict.get("saved_draft_ids", []))
        pending_ops_json = json.dumps(cp_dict.get("pending_operation_ids", []))
        now = cp_dict.get("updated_at_epoch", time.time())
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    conn.execute("""
                    INSERT INTO checkpoint_phien (
                        run_id, checkpoint_id, project_id, workspace_id,
                        step_count, consecutive_error_count, last_error_fingerprint,
                        status, saved_draft_ids_json, pending_operation_ids_json,
                        cost_reserved_usd, cost_actual_usd, updated_at_epoch
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        checkpoint_id=excluded.checkpoint_id,
                        step_count=excluded.step_count,
                        consecutive_error_count=excluded.consecutive_error_count,
                        last_error_fingerprint=excluded.last_error_fingerprint,
                        status=excluded.status,
                        saved_draft_ids_json=excluded.saved_draft_ids_json,
                        pending_operation_ids_json=excluded.pending_operation_ids_json,
                        cost_reserved_usd=excluded.cost_reserved_usd,
                        cost_actual_usd=excluded.cost_actual_usd,
                        updated_at_epoch=excluded.updated_at_epoch
                    """, (
                        cp_dict["run_id"],
                        cp_dict["checkpoint_id"],
                        cp_dict["project_id"],
                        cp_dict.get("workspace_id", "default_ws"),
                        cp_dict.get("step_count", 0),
                        cp_dict.get("consecutive_error_count", 0),
                        cp_dict.get("last_error_fingerprint"),
                        cp_dict.get("status", "EDITING"),
                        saved_drafts_json,
                        pending_ops_json,
                        cp_dict.get("cost_reserved_usd", 0.0),
                        cp_dict.get("cost_actual_usd", 0.0),
                        now
                    ))
            finally:
                conn.close()

    @classmethod
    def lay_checkpoint(cls, run_id: str) -> Optional[Dict[str, Any]]:
        conn = cls.ket_noi()
        try:
            cur = conn.execute(
                "SELECT * FROM checkpoint_phien WHERE run_id = ?",
                (run_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["saved_draft_ids"] = json.loads(d["saved_draft_ids_json"])
            d["pending_operation_ids"] = json.loads(d["pending_operation_ids_json"])
            return d
        finally:
            conn.close()

    # --- NHẬT KÝ LỆNH IDEMPOTENT (JOURNAL) ---

    @classmethod
    def lay_nhat_ky_lenh(cls, operation_id: str) -> Optional[Dict[str, Any]]:
        conn = cls.ket_noi()
        try:
            cur = conn.execute(
                "SELECT * FROM nhat_ky_lenh WHERE operation_id = ?",
                (operation_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["result"] = json.loads(d["result_json"])
            return d
        finally:
            conn.close()

    @classmethod
    def luu_nhat_ky_lenh(
        cls,
        operation_id: str,
        draft_id: str,
        payload_hash: str,
        result_dict: Dict[str, Any]
    ) -> None:
        now = time.time()
        result_json = json.dumps(result_dict, ensure_ascii=False)
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    conn.execute("""
                    INSERT INTO nhat_ky_lenh (
                        operation_id, draft_id, payload_hash, result_json, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(operation_id) DO UPDATE SET
                        result_json=excluded.result_json
                    """, (operation_id, draft_id, payload_hash, result_json, now))
            finally:
                conn.close()

    # --- ĐƠN SỬA CẢNH (FLOW / API) ---

    @classmethod
    def luu_don_sua_canh(cls, don_record: Dict[str, Any]) -> None:
        now = time.time()
        don_json = json.dumps(don_record["don"], ensure_ascii=False)
        cap_json = json.dumps(don_record.get("capability", {}), ensure_ascii=False)
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    conn.execute("""
                    INSERT INTO don_sua_canh (
                        request_id, project_id, workspace_id, draft_id,
                        source_asset_id, source_sha256, route, status,
                        don_json, capability_json, output_asset_id, receipt_token,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(request_id) DO UPDATE SET
                        status=excluded.status,
                        output_asset_id=excluded.output_asset_id,
                        receipt_token=excluded.receipt_token,
                        updated_at=excluded.updated_at
                    """, (
                        don_record["request_id"],
                        don_record["project_id"],
                        don_record["workspace_id"],
                        don_record.get("draft_id", ""),
                        don_record["source_asset_id"],
                        don_record.get("source_sha256", ""),
                        don_record["route"],
                        don_record.get("status", "PENDING"),
                        don_json,
                        cap_json,
                        don_record.get("output_asset_id"),
                        don_record.get("receipt_token"),
                        now,
                        now
                    ))
            finally:
                conn.close()

    @classmethod
    def lay_don_sua_canh(cls, request_id: str) -> Optional[Dict[str, Any]]:
        conn = cls.ket_noi()
        try:
            cur = conn.execute(
                "SELECT * FROM don_sua_canh WHERE request_id = ?",
                (request_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["don"] = json.loads(d["don_json"])
            d["capability"] = json.loads(d["capability_json"])
            return d
        finally:
            conn.close()

    @classmethod
    def cap_nhat_trang_thai_don_sua(
        cls,
        request_id: str,
        status: str,
        output_asset_id: Optional[str] = None
    ) -> None:
        now = time.time()
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    if output_asset_id is not None:
                        conn.execute("""
                        UPDATE don_sua_canh
                        SET status = ?, output_asset_id = ?, updated_at = ?
                        WHERE request_id = ?
                        """, (status, output_asset_id, now, request_id))
                    else:
                        conn.execute("""
                        UPDATE don_sua_canh
                        SET status = ?, updated_at = ?
                        WHERE request_id = ?
                        """, (status, now, request_id))
            finally:
                conn.close()

    # --- GÓI BÀN GIAO NLE ---

    @classmethod
    def luu_goi_ban_giao(cls, bundle_record: Dict[str, Any]) -> None:
        now = time.time()
        files_json = json.dumps(bundle_record.get("files", []), ensure_ascii=False)
        loss_report_json = json.dumps(bundle_record.get("loss_report", {}), ensure_ascii=False)
        with cls._lock:
            conn = cls.ket_noi()
            try:
                with conn:
                    conn.execute("""
                    INSERT INTO goi_ban_giao (
                        bundle_id, project_id, workspace_id, revision,
                        timeline_hash, export_format, files_json, loss_report_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bundle_id) DO UPDATE SET
                        files_json=excluded.files_json,
                        loss_report_json=excluded.loss_report_json
                    """, (
                        bundle_record["bundle_id"],
                        bundle_record["project_id"],
                        bundle_record.get("workspace_id", "default_ws"),
                        bundle_record["revision"],
                        bundle_record["timeline_hash"],
                        bundle_record["export_format"],
                        files_json,
                        loss_report_json,
                        now
                    ))
            finally:
                conn.close()

    @classmethod
    def lay_goi_ban_giao(cls, bundle_id: str) -> Optional[Dict[str, Any]]:
        conn = cls.ket_noi()
        try:
            cur = conn.execute(
                "SELECT * FROM goi_ban_giao WHERE bundle_id = ?",
                (bundle_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["files"] = json.loads(d["files_json"])
            d["loss_report"] = json.loads(d["loss_report_json"])
            return d
        finally:
            conn.close()
