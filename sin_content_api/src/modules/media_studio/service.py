# -*- coding: utf-8 -*-
"""Tầng nghiệp vụ Media Studio (Service Layer).
Quản lý lưu trữ tệp, bảo đảm an toàn đa tenant và liên kết dự án sản xuất.
"""

import os
import pathlib
import json
import logging
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from typing import BinaryIO, List, Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.entities import (
    AIGenerationJob, ContentVideoPlan, ContentVideoRun, MediaAsset, MusicBrief,
    ProductionProject, ProductionTask, TimelineVersion,
)
from src.modules.media_studio.security import (
    validate_audio_or_media_file,
    probe_media_metadata,
    probe_media_metadata_from_values,
    stream_media_to_tempfile,
    hash_file,
    MEDIA_ROOT_DIR,
    _check_filename_safe,
    UPLOAD_SIZE_LIMITS,
    UPLOAD_STREAM_CHUNK_BYTES,
    validate_media_file_info,
)
from src.schemas.contracts import ProductionProjectCreate

VIDEO_UPLOAD_CHUNK_BYTES = 64 * 1024 * 1024
VIDEO_UPLOAD_SESSION_TTL_SECONDS = 24 * 60 * 60
VIDEO_UPLOAD_DISK_RESERVE_BYTES = 512 * 1024 * 1024
logger = logging.getLogger(__name__)


@contextmanager
def _lock_upload_session(lock_path: pathlib.Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                import msvcrt
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

class MediaStudioService:
    def __init__(self):
        # Thiết lập thư mục lưu trữ cục bộ an toàn (SSOT)
        self.storage_base = MEDIA_ROOT_DIR
        self.storage_base.mkdir(parents=True, exist_ok=True)

    def upload_asset(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        filename: str,
        data: bytes,
        source_product: str = "UPLOAD",
        project_id: Optional[str] = None,
        expected_category: str = "audio"
    ) -> MediaAsset:
        """Tải lên và đăng ký tư liệu truyền thông vào thư viện với xác thực nghiêm ngặt (B04, B05)."""
        mime_type, sha256_hash, byte_size = validate_audio_or_media_file(
            data, filename, expected_category=expected_category
        )
        metadata = probe_media_metadata(data, mime_type)
        safe_filename = _check_filename_safe(filename)
        self._validate_project_scope(db, workspace_id, project_id)
        staged_path = self._stage_bytes(data)
        return self._store_and_register(
            db=db,
            staged_path=staged_path,
            workspace_id=workspace_id,
            user_id=user_id,
            project_id=project_id,
            source_product=source_product,
            safe_filename=safe_filename,
            sha256_hash=sha256_hash,
            byte_size=byte_size,
            mime_type=mime_type,
            metadata=metadata,
        )

    def upload_asset_stream(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        filename: str,
        file_obj: BinaryIO,
        source_product: str = "UPLOAD",
        project_id: Optional[str] = None,
        expected_category: str = "audio",
    ) -> MediaAsset:
        """Stream a seekable upload to disk, validate it, then atomically store and register it."""
        self._validate_project_scope(db, workspace_id, project_id)
        staged_path, mime_type, sha256_hash, byte_size = stream_media_to_tempfile(
            file_obj,
            filename,
            expected_category,
            self.storage_base,
        )
        try:
            return self._store_and_register(
                db=db,
                staged_path=staged_path,
                workspace_id=workspace_id,
                user_id=user_id,
                project_id=project_id,
                source_product=source_product,
                safe_filename=_check_filename_safe(filename),
                sha256_hash=sha256_hash,
                byte_size=byte_size,
                mime_type=mime_type,
                metadata=probe_media_metadata_from_values(byte_size, mime_type, sha256_hash),
            )
        finally:
            staged_path.unlink(missing_ok=True)

    def _upload_session_paths(self, session_id: str) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
        try:
            if uuid.UUID(hex=session_id).hex != session_id:
                raise ValueError("Invalid upload session id")
        except (ValueError, AttributeError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên tải lên.")
        root = self.storage_base / ".upload_sessions"
        return root, root / f"{session_id}.json", root / f"{session_id}.part"

    def _write_upload_session(self, manifest_path: pathlib.Path, session: Dict[str, Any]) -> None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=manifest_path.parent, delete=False) as temporary:
                temporary_path = pathlib.Path(temporary.name)
                json.dump(session, temporary, ensure_ascii=False)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, manifest_path)
        finally:
            if temporary_path:
                temporary_path.unlink(missing_ok=True)

    def _load_upload_session(
        self,
        manifest_path: pathlib.Path,
        workspace_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        try:
            session = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên tải lên.")
        if session.get("workspace_id") != workspace_id or session.get("user_id") != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên tải lên.")
        if session.get("expires_at", 0) < time.time():
            manifest_path.unlink(missing_ok=True)
            manifest_path.with_suffix(".part").unlink(missing_ok=True)
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Phiên tải lên đã hết hạn.")
        return session

    def create_video_upload_session(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        filename: str,
        byte_size: int,
        project_id: str,
    ) -> Dict[str, Any]:
        if byte_size <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Video không được để trống.")
        if byte_size > UPLOAD_SIZE_LIMITS["video"]:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Video vượt giới hạn 12 GiB.")
        self._validate_project_scope(db, workspace_id, project_id)
        self.storage_base.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(self.storage_base).free < byte_size + VIDEO_UPLOAD_DISK_RESERVE_BYTES:
            raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail="Không đủ dung lượng trống để nhận video an toàn.")

        safe_filename = _check_filename_safe(filename)
        root = self.storage_base / ".upload_sessions"
        root.mkdir(parents=True, exist_ok=True)
        now = time.time()
        for manifest_path in root.glob("*.json"):
            try:
                old_session = json.loads(manifest_path.read_text(encoding="utf-8"))
                if old_session.get("expires_at", 0) < now:
                    manifest_path.unlink(missing_ok=True)
                    manifest_path.with_suffix(".part").unlink(missing_ok=True)
                    manifest_path.with_suffix(".lock").unlink(missing_ok=True)
            except (OSError, json.JSONDecodeError):
                manifest_path.unlink(missing_ok=True)
                manifest_path.with_suffix(".part").unlink(missing_ok=True)
        for part_path in root.glob("*.part"):
            try:
                if not part_path.with_suffix(".json").exists() and part_path.stat().st_mtime < now - VIDEO_UPLOAD_SESSION_TTL_SECONDS:
                    part_path.unlink(missing_ok=True)
            except OSError:
                continue

        session_id = uuid.uuid4().hex
        _, manifest_path, part_path = self._upload_session_paths(session_id)
        part_path.touch(mode=0o600, exist_ok=False)
        session = {
            "session_id": session_id,
            "workspace_id": workspace_id,
            "user_id": user_id,
            "project_id": project_id,
            "filename": safe_filename,
            "byte_size": byte_size,
            "next_offset": 0,
            "expires_at": now + VIDEO_UPLOAD_SESSION_TTL_SECONDS,
        }
        try:
            self._write_upload_session(manifest_path, session)
        except Exception:
            part_path.unlink(missing_ok=True)
            raise
        return {**session, "chunk_size": VIDEO_UPLOAD_CHUNK_BYTES}

    def video_upload_session_status(self, session_id: str, workspace_id: str, user_id: str) -> Dict[str, Any]:
        root, manifest_path, part_path = self._upload_session_paths(session_id)
        with _lock_upload_session(root / f"{session_id}.lock"):
            session = self._load_upload_session(manifest_path, workspace_id, user_id)
            if part_path.exists() and part_path.stat().st_size > session["next_offset"]:
                with part_path.open("r+b") as partial:
                    partial.truncate(session["next_offset"])
            return {**session, "chunk_size": VIDEO_UPLOAD_CHUNK_BYTES}

    def append_video_upload_chunk(
        self,
        session_id: str,
        workspace_id: str,
        user_id: str,
        offset: int,
        chunk_file: BinaryIO,
    ) -> Dict[str, Any]:
        root, manifest_path, part_path = self._upload_session_paths(session_id)
        with _lock_upload_session(root / f"{session_id}.lock"):
            session = self._load_upload_session(manifest_path, workspace_id, user_id)
            next_offset = session["next_offset"]
            if offset < next_offset:
                return {"session_id": session_id, "next_offset": next_offset, "byte_size": session["byte_size"]}
            if offset != next_offset:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_code": "UPLOAD_OFFSET_MISMATCH", "next_offset": next_offset})
            with _lock_upload_session(root / "disk.lock"):
                if shutil.disk_usage(self.storage_base).free < min(VIDEO_UPLOAD_CHUNK_BYTES, session["byte_size"] - offset) + VIDEO_UPLOAD_DISK_RESERVE_BYTES:
                    raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail="Ổ lưu video gần hết dung lượng trống.")

                part_path.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                try:
                    with part_path.open("r+b") as destination:
                        if destination.seek(0, os.SEEK_END) > offset:
                            destination.truncate(offset)
                        destination.seek(offset)
                        chunk_file.seek(0)
                        while True:
                            chunk = chunk_file.read(UPLOAD_STREAM_CHUNK_BYTES)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > VIDEO_UPLOAD_CHUNK_BYTES or offset + written > session["byte_size"]:
                                raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Khối tải lên vượt kích thước phiên cho phép.")
                            destination.write(chunk)
                        if written == 0:
                            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Khối tải lên bị rỗng.")
                        destination.flush()
                        os.fsync(destination.fileno())
                except Exception:
                    with part_path.open("r+b") as partial:
                        partial.truncate(offset)
                    raise

                session["next_offset"] = offset + written
                session["expires_at"] = time.time() + VIDEO_UPLOAD_SESSION_TTL_SECONDS
                self._write_upload_session(manifest_path, session)
                return {"session_id": session_id, "next_offset": session["next_offset"], "byte_size": session["byte_size"]}

    def complete_video_upload_session(
        self,
        db: Session,
        session_id: str,
        workspace_id: str,
        user_id: str,
    ) -> MediaAsset:
        root, manifest_path, part_path = self._upload_session_paths(session_id)
        with _lock_upload_session(root / f"{session_id}.lock"):
            session = self._load_upload_session(manifest_path, workspace_id, user_id)
            if session["next_offset"] != session["byte_size"] or not part_path.is_file() or part_path.stat().st_size != session["byte_size"]:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Video chưa được tải lên đầy đủ.")
            self._validate_project_scope(db, workspace_id, session["project_id"])
            registration_path = part_path.with_suffix(".register")
            try:
                registration_path.unlink(missing_ok=True)
                os.link(part_path, registration_path)
                asset = self.upload_asset_path(
                    db, workspace_id, user_id, session["filename"], registration_path,
                    source_product="UPLOAD", project_id=session["project_id"], expected_category="video",
                )
            except Exception:
                registration_path.unlink(missing_ok=True)
                raise
            part_path.unlink(missing_ok=True)
            manifest_path.unlink(missing_ok=True)
            return asset

    def upload_asset_path(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        filename: str,
        staged_path: pathlib.Path,
        source_product: str = "UPLOAD",
        project_id: Optional[str] = None,
        expected_category: str = "video",
    ) -> MediaAsset:
        self._validate_project_scope(db, workspace_id, project_id)
        sha256_hash, byte_size = hash_file(staged_path)
        with staged_path.open("rb") as source:
            prefix = source.read(64 * 1024)
        mime_type, sha256_hash, byte_size = validate_media_file_info(
            prefix, filename, expected_category, byte_size, sha256_hash,
        )
        storage_key = f"workspaces/{workspace_id}/media/{sha256_hash[:16]}_{_check_filename_safe(filename)}"
        existing = db.query(MediaAsset).filter(
            MediaAsset.workspace_id == workspace_id,
            MediaAsset.project_id == project_id,
            MediaAsset.storage_key == storage_key,
            MediaAsset.sha256 == sha256_hash,
        ).first()
        if existing:
            staged_path.unlink(missing_ok=True)
            return existing
        return self._store_and_register(
            db=db,
            staged_path=staged_path,
            workspace_id=workspace_id,
            user_id=user_id,
            project_id=project_id,
            source_product=source_product,
            safe_filename=_check_filename_safe(filename),
            sha256_hash=sha256_hash,
            byte_size=byte_size,
            mime_type=mime_type,
            metadata=probe_media_metadata_from_values(byte_size, mime_type, sha256_hash),
        )

    def _validate_project_scope(self, db: Session, workspace_id: str, project_id: Optional[str]) -> None:
        if project_id and not db.query(ProductionProject.id).filter(
            ProductionProject.id == project_id,
            ProductionProject.workspace_id == workspace_id,
        ).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PROJECT_NOT_FOUND", "message": "Không tìm thấy dự án sản xuất trong workspace."},
            )

    def _stage_bytes(self, data: bytes) -> pathlib.Path:
        self.storage_base.mkdir(parents=True, exist_ok=True)
        staged_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix=".upload-", dir=self.storage_base, delete=False) as temporary:
                staged_path = pathlib.Path(temporary.name)
                temporary.write(data)
                temporary.flush()
                os.fsync(temporary.fileno())
            return staged_path
        except Exception:
            if staged_path:
                staged_path.unlink(missing_ok=True)
            raise

    def _store_and_register(
        self,
        *,
        db: Session,
        staged_path: pathlib.Path,
        workspace_id: str,
        user_id: str,
        project_id: Optional[str],
        source_product: str,
        safe_filename: str,
        sha256_hash: str,
        byte_size: int,
        mime_type: str,
        metadata: Dict[str, Any],
    ) -> MediaAsset:
        if mime_type.startswith("video/"):
            try:
                from src.modules.media_studio.video_processor import video_processor

                duration_seconds = float(video_processor.probe_video(staged_path).get("duration_seconds") or 0)
                metadata["duration_ms"] = int(duration_seconds * 1000) if duration_seconds > 0 else None
            except Exception as exc:
                metadata["duration_ms"] = None
                logger.warning("Video duration probe failed; storing unknown duration (%s)", type(exc).__name__)
        storage_key = f"workspaces/{workspace_id}/media/{sha256_hash[:16]}_{safe_filename}"
        target_path = self.storage_base / storage_key
        target_existed = True
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_existed = target_path.exists()
            os.replace(staged_path, target_path)
            asset = MediaAsset(
                id=str(uuid.uuid4()),
                workspace_id=workspace_id,
                project_id=project_id,
                storage_key=storage_key,
                sha256=sha256_hash,
                byte_size=byte_size,
                mime_detected=mime_type,
                duration_ms=metadata.get("duration_ms"),
                source_product=source_product,
                original_filename=safe_filename,
                approval_state="UNREVIEWED",
                created_by=user_id,
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            return asset
        except Exception:
            db.rollback()
            if not target_existed:
                target_path.unlink(missing_ok=True)
            raise
        finally:
            staged_path.unlink(missing_ok=True)

    def get_asset(self, db: Session, workspace_id: str, asset_id: str) -> MediaAsset:
        """Lấy thông tin tài sản có bảo vệ ranh giới tenant nghiêm ngặt (B02)."""
        asset = db.query(MediaAsset).filter(MediaAsset.id == asset_id).first()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ASSET_NOT_FOUND", "message": "Không tìm thấy tư liệu truyền thông."}
            )

        if asset.workspace_id != workspace_id:
            # Ngăn chặn rò rỉ metadata giữa các tenant (B02)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ASSET_NOT_FOUND", "message": "Không tìm thấy tư liệu truyền thông."}
            )

        return asset

    def list_assets(
        self,
        db: Session,
        workspace_id: str,
        project_id: Optional[str] = None,
        limit: int = 50
    ) -> List[MediaAsset]:
        """Liệt kê danh sách tư liệu trong không gian làm việc."""
        query = db.query(MediaAsset).filter(MediaAsset.workspace_id == workspace_id)
        if project_id:
            query = query.filter(MediaAsset.project_id == project_id)
        return query.order_by(MediaAsset.created_at.desc()).limit(limit).all()

    def create_project(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        payload: ProductionProjectCreate
    ) -> ProductionProject:
        """Khởi tạo dự án sản xuất video."""
        project = ProductionProject(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            title=payload.title,
            workflow_type=payload.workflow_type,
            script_id=payload.script_id,
            status="DRAFT",
            created_by=user_id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def list_projects(
        self,
        db: Session,
        workspace_id: str,
        workflow_type: str = "AI_VIDEO",
    ) -> List[ProductionProject]:
        return db.query(ProductionProject).filter(
            ProductionProject.workspace_id == workspace_id,
            ProductionProject.workflow_type == workflow_type,
        ).order_by(ProductionProject.created_at.desc()).all()

    def delete_project(self, db: Session, workspace_id: str, project_id: str) -> None:
        project = db.query(ProductionProject).filter(
            ProductionProject.id == project_id,
            ProductionProject.workspace_id == workspace_id,
        ).with_for_update().first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy dự án.")

        active_run = db.query(ContentVideoRun.id).filter(
            ContentVideoRun.project_id == project_id,
            ContentVideoRun.status.in_(("QUEUED", "RUNNING", "WAITING_FOR_FLOW")),
        ).with_for_update().first()
        active_job = db.query(AIGenerationJob.id).filter(
            AIGenerationJob.project_id == project_id,
            AIGenerationJob.state.in_(("QUEUED", "RUNNING", "WAITING_FOR_FLOW")),
        ).with_for_update().first()
        active_task = db.query(ProductionTask.id).filter(
            ProductionTask.project_id == project_id,
            ProductionTask.status == "RUNNING",
        ).with_for_update().first()
        if active_run or active_job or active_task:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Không thể xóa dự án khi video hoặc tác vụ vẫn đang chạy.",
            )

        db.query(ContentVideoRun).filter(ContentVideoRun.project_id == project_id).delete(synchronize_session=False)
        db.query(ContentVideoPlan).filter(ContentVideoPlan.project_id == project_id).delete(synchronize_session=False)
        db.query(TimelineVersion).filter(TimelineVersion.project_id == project_id).delete(synchronize_session=False)
        db.query(ProductionTask).filter(ProductionTask.project_id == project_id).delete(synchronize_session=False)
        db.query(MediaAsset).filter(MediaAsset.project_id == project_id).update(
            {MediaAsset.project_id: None}, synchronize_session=False
        )
        db.query(AIGenerationJob).filter(AIGenerationJob.project_id == project_id).update(
            {AIGenerationJob.project_id: None}, synchronize_session=False
        )
        db.query(MusicBrief).filter(MusicBrief.project_id == project_id).update(
            {MusicBrief.project_id: None}, synchronize_session=False
        )
        db.delete(project)
        db.commit()

media_service = MediaStudioService()
