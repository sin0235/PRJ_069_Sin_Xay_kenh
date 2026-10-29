# -*- coding: utf-8 -*-
"""Tầng nghiệp vụ Media Studio (Service Layer).
Quản lý lưu trữ tệp, bảo đảm an toàn đa tenant và liên kết dự án sản xuất.
"""

import os
import pathlib
import tempfile
import uuid
from typing import BinaryIO, List, Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.entities import MediaAsset, ProductionProject, ProductionTask
from src.modules.media_studio.security import (
    validate_audio_or_media_file,
    probe_media_metadata,
    probe_media_metadata_from_values,
    stream_media_to_tempfile,
    MEDIA_ROOT_DIR,
    _check_filename_safe,
)
from src.schemas.contracts import ProductionProjectCreate

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
            script_id=payload.script_id,
            status="DRAFT",
            created_by=user_id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    def list_projects(self, db: Session, workspace_id: str) -> List[ProductionProject]:
        return db.query(ProductionProject).filter(
            ProductionProject.workspace_id == workspace_id
        ).order_by(ProductionProject.created_at.desc()).all()

media_service = MediaStudioService()
