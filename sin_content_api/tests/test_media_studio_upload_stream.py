import hashlib
import importlib
import inspect
import sys
import tempfile
import types
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.entities import MediaAsset, ProductionProject, Workspace
from src.modules.media_studio import security
from src.modules.media_studio.service import MediaStudioService


@pytest.fixture
def upload_context(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    workspace_id = f"ws-stream-{uuid.uuid4().hex[:8]}"
    other_workspace_id = f"ws-other-{uuid.uuid4().hex[:8]}"
    db.add_all([
        Workspace(id=workspace_id, name="Stream upload test", slug=workspace_id),
        Workspace(id=other_workspace_id, name="Other workspace", slug=other_workspace_id),
    ])
    db.commit()

    media_root = tmp_path / "media"
    media_root.mkdir()
    service = object.__new__(MediaStudioService)
    service.storage_base = media_root
    try:
        yield db, service, workspace_id, other_workspace_id, media_root
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


class BoundedSeekableReader:
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.read_sizes = []

    def read(self, size=-1):
        assert size > 0, "upload stream must never call read() without a positive bound"
        assert size <= security.UPLOAD_STREAM_CHUNK_BYTES, "upload stream requested an oversized chunk"
        self.read_sizes.append(size)
        return self.wrapped.read(size)

    def seekable(self):
        return self.wrapped.seekable()

    def seek(self, *args):
        return self.wrapped.seek(*args)


def test_stream_upload_hashes_and_stores_real_seekable_file_in_bounded_chunks(upload_context):
    db, service, workspace_id, _, media_root = upload_context
    project_id = f"project-{uuid.uuid4().hex[:8]}"
    db.add(ProductionProject(
        id=project_id,
        workspace_id=workspace_id,
        title="Scoped project",
        created_by="user-stream",
    ))
    db.commit()
    content = b"\x00\x00\x00\x18ftypmp42" + b"v" * (2 * security.UPLOAD_STREAM_CHUNK_BYTES + 73)

    with tempfile.TemporaryFile(mode="w+b") as real_file:
        real_file.write(content)
        real_file.seek(0)
        source = BoundedSeekableReader(real_file)
        assert source.seekable()

        asset = service.upload_asset_stream(
            db=db,
            workspace_id=workspace_id,
            user_id="user-stream",
            filename="scene.mp4",
            file_obj=source,
            source_product="UPLOAD",
            project_id=project_id,
            expected_category="video",
        )

    stored = media_root / asset.storage_key
    assert source.read_sizes
    assert len(source.read_sizes) >= 3
    assert asset.workspace_id == workspace_id
    assert asset.project_id == project_id
    assert asset.byte_size == len(content)
    assert asset.sha256 == hashlib.sha256(content).hexdigest()
    assert asset.mime_detected == "video/mp4"
    assert stored.read_bytes() == content
    assert not list(media_root.glob(".upload-*"))


def test_stream_upload_rejects_cross_workspace_project_before_staging(upload_context):
    db, service, workspace_id, other_workspace_id, media_root = upload_context
    project_id = f"project-{uuid.uuid4().hex[:8]}"
    db.add(ProductionProject(
        id=project_id,
        workspace_id=other_workspace_id,
        title="Foreign project",
        created_by="other-user",
    ))
    db.commit()
    source = BoundedSeekableReader(tempfile.TemporaryFile(mode="w+b"))

    with pytest.raises(HTTPException) as error:
        service.upload_asset_stream(
            db=db,
            workspace_id=workspace_id,
            user_id="user-stream",
            filename="scene.mp4",
            file_obj=source,
            project_id=project_id,
            expected_category="video",
        )

    assert error.value.status_code == 404
    assert error.value.detail["error_code"] == "PROJECT_NOT_FOUND"
    assert source.read_sizes == []
    assert db.query(MediaAsset).count() == 0
    assert list(media_root.iterdir()) == []
    source.wrapped.close()


def test_oversize_stream_removes_partial_tempfile_and_registers_no_asset(upload_context, monkeypatch):
    db, service, workspace_id, _, media_root = upload_context
    monkeypatch.setitem(security.UPLOAD_SIZE_LIMITS, "video", security.UPLOAD_STREAM_CHUNK_BYTES + 32)
    content = b"\x00\x00\x00\x18ftypmp42" + b"x" * (security.UPLOAD_STREAM_CHUNK_BYTES + 64)
    real_file = tempfile.TemporaryFile(mode="w+b")
    real_file.write(content)
    real_file.seek(0)
    source = BoundedSeekableReader(real_file)

    try:
        with pytest.raises(HTTPException) as error:
            service.upload_asset_stream(
                db=db,
                workspace_id=workspace_id,
                user_id="user-stream",
                filename="too-large.mp4",
                file_obj=source,
                expected_category="video",
            )

        assert error.value.status_code == 413
        assert error.value.detail["error_code"] == "FILE_TOO_LARGE"
        assert source.read_sizes
        assert max(source.read_sizes) <= security.UPLOAD_STREAM_CHUNK_BYTES
        assert db.query(MediaAsset).count() == 0
        assert list(media_root.iterdir()) == []
    finally:
        real_file.close()


def test_stream_mime_validation_removes_invalid_upload(upload_context):
    db, service, workspace_id, _, media_root = upload_context
    with tempfile.TemporaryFile(mode="w+b") as real_file:
        real_file.write(b"%PDF-1.7 malicious video extension")
        real_file.seek(0)
        source = BoundedSeekableReader(real_file)
        with pytest.raises(HTTPException) as error:
            service.upload_asset_stream(
                db=db, workspace_id=workspace_id, user_id="user-stream",
                filename="disguised.mp4", file_obj=source, expected_category="video",
            )

    assert error.value.status_code == 400
    assert db.query(MediaAsset).count() == 0
    assert list(media_root.iterdir()) == []


def test_bytes_upload_callers_still_use_existing_api(upload_context):
    db, service, workspace_id, _, media_root = upload_context
    content = b"\x00\x00\x00\x18ftypmp42legacy-bytes"

    asset = service.upload_asset(
        db=db,
        workspace_id=workspace_id,
        user_id="user-stream",
        filename="legacy.mp4",
        data=content,
        expected_category="video",
    )

    assert asset.byte_size == len(content)
    assert asset.sha256 == hashlib.sha256(content).hexdigest()
    assert (media_root / asset.storage_key).read_bytes() == content


def test_router_upload_uses_sync_streaming_service(upload_context, monkeypatch):
    db, service, workspace_id, _, media_root = upload_context
    flow_session = types.ModuleType("session_manager")
    flow_session.FlowLoginRequired = type("FlowLoginRequired", (Exception,), {})
    flow_session.FlowSubmissionNotSent = type("FlowSubmissionNotSent", (Exception,), {})
    flow_session.FlowQuotaExceeded = type("FlowQuotaExceeded", (Exception,), {})
    flow_session.LOCAL_BROWSER_PROFILE_DIR = None
    monkeypatch.setitem(sys.modules, "session_manager", flow_session)
    media_router = importlib.import_module("src.modules.media_studio.router")
    monkeypatch.setattr(media_router.media_service, "upload_asset_stream", service.upload_asset_stream)
    content = b"\x00\x00\x00\x18ftypmp42route-stream"

    with tempfile.TemporaryFile(mode="w+b") as real_file:
        real_file.write(content)
        real_file.seek(0)
        source = BoundedSeekableReader(real_file)
        response = media_router.upload_asset(
            file=SimpleNamespace(file=source, filename="route.mp4"),
            source_product="UPLOAD",
            project_id=None,
            expected_category="video",
            db=db,
            tenant=SimpleNamespace(workspace_id=workspace_id, user_id="user-stream"),
        )

    assert not inspect.iscoroutinefunction(media_router.upload_asset)
    assert response.sha256 == hashlib.sha256(content).hexdigest()
    assert response.byte_size == len(content)
    assert (media_root / response.storage_key).read_bytes() == content


@pytest.mark.parametrize("filename,expected", [
    (r"..\windows\system32\evil.mp4", "evil.mp4"),
    ("../../../clip...take.mp4", "clip_take.mp4"),
    ("folder/clip..mp4", "clip.mp4"),
])
def test_upload_filename_normalization_preserves_extension(filename, expected):
    assert security._check_filename_safe(filename) == expected
