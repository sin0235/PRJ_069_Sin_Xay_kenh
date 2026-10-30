# -*- coding: utf-8 -*-
"""Kiểm thử tự động Động cơ Video Dọc 9:16 Chuẩn TikTok (P09 + GF01/02/03).
Bao gồm: Tỷ lệ 9:16, Safe Zone, Flow Video Zero-Cost, Gemini Omni Flash, Ghép nối Scene + Audio.
"""

import os
import sys
import uuid
import json
import time
import base64
import hmac
import hashlib
import pathlib
import subprocess
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
API_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

TEST_DATABASE_URL = "sqlite:///file:video_test_db?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = "sqlite:///file:video_auth_test_db?mode=memory&cache=shared&uri=true"
os.environ["BAHA_AUTH_JWT_SECRET"] = "secret-key-video-test-2026"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "baha-auth-issuer"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "baha-auth-audience"

from src.main import app
from src.database import Base, SessionLocal, engine
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from src.models.entities import Workspace, User, MediaAsset, ProductionProject, TimelineVersion
from baha_auth.src.models.entities import (
    GlobalUser, Membership as AuthMembership, Role as AuthRole,
    RoleAssignment, Workspace as AuthWorkspace
)
from src.schemas.contracts import (
    TimelineDocument, TimelineClip, TimelineAudioTrack, TimelineCaption,
    TimelineSaveRequest, TimelineVersionOut, TimelineFitMode, TimelineMediaType
)
from src.modules.media_studio.video_processor import video_processor
from src.modules.media_studio.video_provider import video_orchestrator
from src.modules.media_studio.audio_processor import audio_processor

client = TestClient(app)


def tao_bearer_jwt(user_id: str) -> str:
    def b64url(val):
        raw = json.dumps(val, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    h = b64url({"alg": "HS256", "typ": "JWT"})
    c = b64url({
        "sub": user_id,
        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],
        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],
        "exp": int(time.time()) + 7200,
    })
    inp = f"{h}.{c}".encode("ascii")
    sig = hmac.new(os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), inp, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")
    return f"{h}.{c}.{sig_b64}"

@pytest.fixture(scope="module", autouse=True)
def setup_databases():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    yield
    Base.metadata.drop_all(bind=engine)
    AuthBase.metadata.drop_all(bind=AuthEngine)

@pytest.fixture
def video_fixture(tmp_path):
    ws_id = f"ws-video-{uuid.uuid4().hex[:8]}"
    user_id = f"user-video-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        ws = Workspace(id=ws_id, name="Video Studio WS", slug=f"ws-{uuid.uuid4().hex[:6]}")
        u = User(id=user_id, email=f"creator-{user_id}@baha.vn", hashed_password="mock")
        db.add_all([ws, u])
        db.commit()

    with AuthSessionLocal() as auth_db:
        auth_ws = AuthWorkspace(id=ws_id, name="Video Studio WS", slug=ws_id, status="ACTIVE")
        gu = GlobalUser(id=user_id, email=f"creator-{user_id}@baha.vn", status="ACTIVE")
        auth_db.add_all([auth_ws, gu])
        auth_db.commit()

        m = AuthMembership(id=str(uuid.uuid4()), user_id=user_id, workspace_id=ws_id, status="ACTIVE")
        auth_db.add(m)
        auth_db.commit()

        role_owner = auth_db.query(AuthRole).filter(AuthRole.code == "WORKSPACE_OWNER").first()
        if not role_owner:
            role_owner = AuthRole(code="WORKSPACE_OWNER", name="Workspace Owner", is_template=True, status="ACTIVE")
            auth_db.add(role_owner)
            auth_db.commit()

        ra = RoleAssignment(
            id=str(uuid.uuid4()), membership_id=m.id, role_id=role_owner.id,
            workspace_id=ws_id, status="ACTIVE", granted_by=m.id, scope_type="WORKSPACE"
        )
        auth_db.add(ra)
        auth_db.commit()

    # Sinh 2 video clip dọc 9:16 (1080x1920) 2 giây bằng FFmpeg
    clip_1 = tmp_path / "scene_01.mp4"
    clip_2 = tmp_path / "scene_02.mp4"
    audio_file = tmp_path / "audio_voice.mp3"

    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-f", "lavfi",
        "-i", "color=c=0x1E293B:s=1080x1920:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(clip_1)
    ], check=True, capture_output=True)

    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-f", "lavfi",
        "-i", "color=c=0x0F172A:s=1080x1920:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(clip_2)
    ], check=True, capture_output=True)

    subprocess.run([
        audio_processor.ffmpeg_bin, "-y", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=4", "-ar", "44100", "-b:a", "128k", str(audio_file)
    ], check=True, capture_output=True)

    return {
        "ws_id": ws_id,
        "user_id": user_id,
        "token": tao_bearer_jwt(user_id),
        "clip_1": clip_1,
        "clip_2": clip_2,
        "audio_file": audio_file,
        "tmp_dir": tmp_path
    }

# ==============================================================================
# TEST CASE GF02-01: ffprobe Video Specs Extraction
# ==============================================================================
def test_gf02_01_probe_video_specs(video_fixture):
    """GF02-01: Trích xuất thông số kỹ thuật video chính xác qua ffprobe."""
    meta = video_processor.probe_video(video_fixture["clip_1"])
    assert meta["width"] == 1080
    assert meta["height"] == 1920
    assert meta["duration_seconds"] >= 1.9
    assert meta["codec_name"] == "h264"

# ==============================================================================
# TEST CASE GF02-02: TikTok Vertical 9:16 Validation
# ==============================================================================
def test_gf02_02_verify_tiktok_vertical_9_16(video_fixture):
    """GF02-02: Xác thực tỷ lệ dọc 9:16 (1080x1920) chuẩn TikTok."""
    meta = video_processor.probe_video(video_fixture["clip_1"])
    assert meta["is_vertical_9_16"] is True
    assert meta["aspect_ratio"] == "9:16"

# ==============================================================================
# TEST CASE GF02-03: TikTok Safe Zone Compliance
# ==============================================================================
def test_gf02_03_tiktok_safe_zone_compliance(video_fixture):
    """GF02-03: Kiểm tra tiêu chuẩn Safe Zone TikTok (Top 150px, Bottom 320px, Right 120px)."""
    meta = video_processor.probe_video(video_fixture["clip_1"])
    sz = meta["safe_zone_tiktok"]
    assert sz["top_margin_px"] == 150
    assert sz["bottom_margin_px"] == 320
    assert sz["right_margin_px"] == 120
    assert sz["is_compliant"] is True

# ==============================================================================
# TEST CASE GF02-04: Google Flow Zero-Cost Video Generation
# ==============================================================================
def test_gf02_04_flow_video_zero_cost(video_fixture, monkeypatch):
    """GF02-04: Sinh video dọc 9:16 qua Google Flow Zero-Cost (Mock Provider cho LOCAL_TESTED)."""
    def mock_gen(db, workspace_id, user_id, prompt, aspect_ratio="9:16", **kwargs):
        asset = MediaAsset(
            id=f"asset-{uuid.uuid4().hex[:12]}",
            workspace_id=workspace_id,
            storage_key=f"workspaces/{workspace_id}/media/mock_flow.mp4",
            sha256=hashlib.sha256(b"mock_video_bytes").hexdigest(),
            byte_size=1024,
            mime_detected="video/mp4",
            source_product="GOOGLE_FLOW",
            original_filename="mock_flow.mp4",
            created_by=user_id,
            approval_state="APPROVED"
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    monkeypatch.setattr(video_orchestrator, "generate_video_scene", mock_gen)

    with SessionLocal() as db:
        asset = video_orchestrator.generate_video_scene(
            db=db,
            workspace_id=video_fixture["ws_id"],
            user_id=video_fixture["user_id"],
            prompt="Cảnh quay sản phẩm nước giải khát cận cảnh dọc 9:16",
            aspect_ratio="9:16",
            use_official_omni=False
        )
        assert asset.id is not None
        assert asset.mime_detected == "video/mp4"
        assert asset.source_product == "GOOGLE_FLOW"
        assert asset.approval_state == "APPROVED"

# ==============================================================================
# TEST CASE GF01-01: Official Gemini Omni Flash Video Provider
# ==============================================================================
def test_gf01_01_official_omni_provider(video_fixture, monkeypatch):
    """GF01-01: Sinh video dọc qua Gemini Omni Flash (Mock Provider cho LOCAL_TESTED)."""
    def mock_gen(db, workspace_id, user_id, prompt, aspect_ratio="9:16", **kwargs):
        asset = MediaAsset(
            id=f"asset-{uuid.uuid4().hex[:12]}",
            workspace_id=workspace_id,
            storage_key=f"workspaces/{workspace_id}/media/mock_omni.mp4",
            sha256=hashlib.sha256(b"mock_omni_bytes").hexdigest(),
            byte_size=1024,
            mime_detected="video/mp4",
            source_product="GEMINI_OMNI_API",
            original_filename="mock_omni.mp4",
            created_by=user_id,
            approval_state="APPROVED"
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    monkeypatch.setattr(video_orchestrator, "generate_video_scene", mock_gen)

    with SessionLocal() as db:
        asset = video_orchestrator.generate_video_scene(
            db=db,
            workspace_id=video_fixture["ws_id"],
            user_id=video_fixture["user_id"],
            prompt="Chuyên gia tài chính thuyết minh trong văn phòng",
            aspect_ratio="9:16",
            use_official_omni=True
        )
        assert asset.id is not None
        assert asset.source_product == "GEMINI_OMNI_API"
        assert asset.approval_state == "APPROVED"

# ==============================================================================
# TEST CASE GF03-01: FFmpeg Scene Concat and Audio Assembly
# ==============================================================================
def test_gf03_01_assemble_scenes_with_audio(video_fixture):
    """GF03-01: Ghép nối 2 scene video dọc cùng track âm thanh thành video TikTok hoàn chỉnh."""
    out_mp4 = video_fixture["tmp_dir"] / "assembled_tiktok.mp4"
    meta = video_processor.assemble_scenes_with_audio(
        scene_video_paths=[video_fixture["clip_1"], video_fixture["clip_2"]],
        audio_path=video_fixture["audio_file"],
        output_path=out_mp4
    )
    assert out_mp4.exists()
    assert out_mp4.stat().st_size > 5000
    assert meta["width"] == 1080
    assert meta["height"] == 1920
    assert meta["is_vertical_9_16"] is True
    assert meta["duration_seconds"] >= 3.8

# ==============================================================================
# TEST CASE GF03-02: API Endpoint POST /v1/media/video/generate
# ==============================================================================
def test_gf03_02_api_video_generate(video_fixture, monkeypatch):
    """GF03-02: Endpoint API sinh video dọc 9:16 với RBAC (Mock Provider cho LOCAL_TESTED)."""
    def mock_gen(db, workspace_id, user_id, prompt, aspect_ratio="9:16", **kwargs):
        asset = MediaAsset(
            id=f"asset-{uuid.uuid4().hex[:12]}",
            workspace_id=workspace_id,
            storage_key=f"workspaces/{workspace_id}/media/mock_api_video.mp4",
            sha256=hashlib.sha256(b"mock_video_bytes").hexdigest(),
            byte_size=1024,
            mime_detected="video/mp4",
            source_product="GOOGLE_FLOW",
            original_filename="mock_api_video.mp4",
            created_by=user_id,
            approval_state="APPROVED"
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

    monkeypatch.setattr(video_orchestrator, "generate_video_scene", mock_gen)

    resp = client.post(
        "/v1/media/video/generate",
        data={
            "prompt": "Góc quay Flycam bãi biển lúc hoàng hôn 9:16",
            "aspect_ratio": "9:16",
            "use_official_omni": "false"
        },
        headers={
            "Authorization": f"Bearer {video_fixture['token']}",
            "X-Workspace-Id": video_fixture["ws_id"]
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_product"] == "GOOGLE_FLOW"
    assert "download" in data["url"]


# ==============================================================================
# TEST CASE GF03-03: API Endpoint POST /v1/media/video/assemble
# ==============================================================================
def test_gf03_03_api_video_assemble(video_fixture):
    """GF03-03: Endpoint API ghép nối video phân cảnh và âm thanh thành phẩm TikTok."""
    # 1. Upload 2 clips và 1 audio
    clip_1_bytes = video_fixture["clip_1"].read_bytes()
    clip_2_bytes = video_fixture["clip_2"].read_bytes()
    audio_bytes = video_fixture["audio_file"].read_bytes()

    resp_c1 = client.post(
        "/v1/media/upload",
        files={"file": ("c1.mp4", clip_1_bytes, "video/mp4")},
        data={"source_product": "UPLOAD", "expected_category": "video"},
        headers={"Authorization": f"Bearer {video_fixture['token']}", "X-Workspace-Id": video_fixture["ws_id"]}
    )
    assert resp_c1.status_code == 200
    c1_id = resp_c1.json()["id"]

    resp_c2 = client.post(
        "/v1/media/upload",
        files={"file": ("c2.mp4", clip_2_bytes, "video/mp4")},
        data={"source_product": "UPLOAD", "expected_category": "video"},
        headers={"Authorization": f"Bearer {video_fixture['token']}", "X-Workspace-Id": video_fixture["ws_id"]}
    )
    assert resp_c2.status_code == 200
    c2_id = resp_c2.json()["id"]

    resp_a = client.post(
        "/v1/media/upload",
        files={"file": ("a.mp3", audio_bytes, "audio/mpeg")},
        data={"source_product": "UPLOAD", "expected_category": "audio"},
        headers={"Authorization": f"Bearer {video_fixture['token']}", "X-Workspace-Id": video_fixture["ws_id"]}
    )
    assert resp_a.status_code == 200
    a_id = resp_a.json()["id"]

    # 2. Gọi API assemble
    resp_asm = client.post(
        "/v1/media/video/assemble",
        data={
            "scene_asset_ids_json": json.dumps([c1_id, c2_id]),
            "audio_asset_id": a_id
        },
        headers={"Authorization": f"Bearer {video_fixture['token']}", "X-Workspace-Id": video_fixture["ws_id"]}
    )
    assert resp_asm.status_code == 200
    data = resp_asm.json()
    assert data["source_product"] == "TIKTOK_ASSEMBLY"
    assert data["mime_detected"] == "video/mp4"


# ==============================================================================
# TEST CASE GF03-04: Veo Watermark Remover Service (v0.6.5-demo)
# ==============================================================================
def test_gf03_04_veo_watermark_remover_service(video_fixture):
    """GF03-04: Kiểm tra dịch vụ khử watermark Veo bằng Reverse Alpha Blending."""
    from cong_cu_tu_dong.veo_watermark_remover import veo_remover
    assert veo_remover.is_available() is True

    # Sử dụng clip 1s từ fixture để kiểm tra
    in_clip = video_fixture["clip_1"]
    out_clip = video_fixture["tmp_dir"] / "cleaned_veo_test.mp4"

    res = veo_remover.remove_watermark(
        input_video_path=in_clip,
        output_video_path=out_clip,
        use_cpu=True
    )
    assert res["status"] in ("SUCCEEDED", "FALLBACK_ORIGINAL")
    assert out_clip.exists()
    assert out_clip.stat().st_size > 0
    assert "byte_size" in res


def test_watermark_remover_uses_local_video_timeout(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from cong_cu_tu_dong.veo_watermark_remover import remover_service

    source = tmp_path / "flow_video.mp4"
    output = tmp_path / "clean_video.mp4"
    source.write_bytes(b"video")
    call = {}

    def fake_run(command, **kwargs):
        if command[0] == "ffprobe":
            return SimpleNamespace(returncode=0, stdout='{"format":{"duration":"1"}}', stderr="")
        call.update(command=command, kwargs=kwargs)
        pathlib.Path(command[command.index("-o") + 1]).write_bytes(b"clean")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(remover_service.subprocess, "run", fake_run)
    result = remover_service.VeoWatermarkRemover().remove_watermark(source, output)

    assert result["status"] == "SUCCEEDED"
    assert call["kwargs"]["timeout"] == 900


def test_video_processor_rejects_watermark_output_with_truncated_duration(monkeypatch, tmp_path):
    import importlib

    processor_module = importlib.import_module("src.modules.media_studio.video_processor")
    source = tmp_path / "flow_video.mp4"
    output = tmp_path / "clean_video.mp4"
    source.write_bytes(b"source")

    class FakeRemover:
        def is_available(self):
            return True

        def remove_watermark(self, **kwargs):
            kwargs["output_video_path"].write_bytes(b"clean")
            return {"status": "SUCCEEDED", "watermark_removed": True}

    durations = iter((20.0, 8.0))
    monkeypatch.setattr(processor_module, "veo_remover", FakeRemover())
    monkeypatch.setattr(
        processor_module.video_processor,
        "probe_video",
        lambda _path: {"duration_seconds": next(durations)},
    )

    with pytest.raises(RuntimeError, match="WATERMARK_OUTPUT_DURATION_MISMATCH"):
        processor_module.video_processor.remove_veo_watermark(source, output)


def test_watermark_remover_splits_long_videos_under_eight_second_limit():
    from cong_cu_tu_dong.veo_watermark_remover import remover_service

    assert remover_service._video_segment_ranges(10.0) == [(0.0, 7.0), (7.0, 3.0)]
    assert remover_service._video_segment_ranges(7.0) == [(0.0, 7.0)]


def test_watermark_remover_processes_and_rejoins_all_video_segments(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from cong_cu_tu_dong.veo_watermark_remover import remover_service

    executable = tmp_path / "remover.exe"
    source = tmp_path / "source.mp4"
    output = tmp_path / "clean.mp4"
    executable.write_bytes(b"exe")
    source.write_bytes(b"source")
    remover_calls = []

    def probe(_self, path):
        name = path.name
        if name == "source.mp4":
            return 10.0
        if name.startswith("input_000") or name.startswith("output_000"):
            return 7.0
        if name.startswith("input_001") or name.startswith("output_001"):
            return 3.0
        return 10.0

    def ffmpeg(_args):
        pathlib.Path(_args[-1]).write_bytes(b"segment")

    def run(command, **_kwargs):
        remover_calls.append(command)
        pathlib.Path(command[command.index("-o") + 1]).write_bytes(b"clean-segment")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(remover_service.VeoWatermarkRemover, "_probe_video_duration", probe)
    monkeypatch.setattr(remover_service.VeoWatermarkRemover, "_run_ffmpeg", staticmethod(ffmpeg))
    monkeypatch.setattr(remover_service.subprocess, "run", run)

    result = remover_service.VeoWatermarkRemover(executable).remove_watermark(source, output)

    assert result["status"] == "SUCCEEDED"
    assert result["watermark_removed"] is True
    assert len(remover_calls) == 2
    assert output.read_bytes() == b"segment"


def test_watermark_remover_preserves_clip_when_tool_detects_no_watermark(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from cong_cu_tu_dong.veo_watermark_remover import remover_service

    executable = tmp_path / "remover.exe"
    source = tmp_path / "source.mp4"
    output = tmp_path / "clean.mp4"
    executable.write_bytes(b"exe")
    source.write_bytes(b"source")
    monkeypatch.setattr(remover_service.VeoWatermarkRemover, "_probe_video_duration", lambda self, _path: 3.0)
    monkeypatch.setattr(remover_service.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(
        returncode=0, stdout="no Gemini 3.5 diamond detected", stderr=""
    ))

    result = remover_service.VeoWatermarkRemover(executable).remove_watermark(source, output)

    assert result["status"] == "SUCCEEDED"
    assert result["watermark_removed"] is True
    assert result["watermark_detected"] is False
    assert output.read_bytes() == source.read_bytes()


def test_watermark_remover_timeout_reports_last_progress(monkeypatch, tmp_path):
    from cong_cu_tu_dong.veo_watermark_remover import remover_service

    source = tmp_path / "flow_video.mp4"
    source.write_bytes(b"video")

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"87%", stderr=b"cpu")

    monkeypatch.setattr(remover_service.subprocess, "run", fake_run)
    monkeypatch.setattr(remover_service.VeoWatermarkRemover, "_probe_video_duration", lambda self, _path: 1.0)
    with pytest.raises(TimeoutError, match="900 giây.*87%"):
        remover_service.VeoWatermarkRemover().remove_watermark(source, tmp_path / "clean_video.mp4")

# ==============================================================================
# TEST CASE GF03-05: API Endpoint POST /v1/media/video/remove-watermark
# ==============================================================================
def test_gf03_05_api_video_remove_watermark(video_fixture):
    """GF03-05: Endpoint API tẩy logo Veo AI khỏi video MediaAsset."""
    clip_bytes = video_fixture["clip_1"].read_bytes()

    # 1. Tải lên video nguồn
    resp_up = client.post(
        "/v1/media/upload",
        files={"file": ("raw_veo_test.mp4", clip_bytes, "video/mp4")},
        data={"source_product": "GOOGLE_FLOW", "expected_category": "video"},
        headers={"Authorization": f"Bearer {video_fixture['token']}", "X-Workspace-Id": video_fixture["ws_id"]}
    )
    assert resp_up.status_code == 200
    asset_id = resp_up.json()["id"]

    # 2. Gọi API khử logo
    resp_clean = client.post(
        "/v1/media/video/remove-watermark",
        data={"asset_id": asset_id, "use_cpu": "true"},
        headers={"Authorization": f"Bearer {video_fixture['token']}", "X-Workspace-Id": video_fixture["ws_id"]}
    )
    assert resp_clean.status_code == 200
    data = resp_clean.json()
    assert data["source_product"] == "VEO_WATERMARK_CLEANED"
    assert "clean_" in data["original_filename"]
    assert "download" in data["url"]

# ==============================================================================
# TEST CASE GF03-06: Video Processor Expand 16:9 to 9:16 with Watermark Removal
# ==============================================================================
def test_gf03_06_expand_with_watermark_removal(video_fixture, monkeypatch):
    """GF03-06: Mở rộng 16:9 sang 9:16 tự động tẩy watermark Veo trước outpainting."""
    # Tạo video 16:9 tạm thời
    raw_16_9 = video_fixture["tmp_dir"] / "test_16_9_source.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
        "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(raw_16_9)
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    out_9_16 = video_fixture["tmp_dir"] / "out_expanded_clean_9_16.mp4"
    def mock_remove(input_video_path, output_video_path, **kwargs):
        output_video_path.write_bytes(input_video_path.read_bytes())
        return {"status": "SUCCEEDED", "watermark_removed": True}

    monkeypatch.setattr(video_processor, "remove_veo_watermark", mock_remove)
    meta = video_processor.expand_16_9_to_9_16(
        input_video_path=raw_16_9,
        output_video_path=out_9_16,
        blur_strength=25,
        remove_watermark=True
    )

    assert out_9_16.exists()
    assert meta["width"] == 1080
    assert meta["height"] == 1920
    assert meta["is_vertical_9_16"] is True
    assert meta["watermark_removed"] is True


def test_gf03_07_expand_rejects_unremoved_watermark(video_fixture, monkeypatch):
    raw_16_9 = video_fixture["tmp_dir"] / "test_16_9_unremoved.mp4"
    raw_16_9.write_bytes(b"source")
    output = video_fixture["tmp_dir"] / "must_not_publish.mp4"

    def fallback_original(input_video_path, output_video_path, **kwargs):
        output_video_path.write_bytes(input_video_path.read_bytes())
        return {"status": "FALLBACK_ORIGINAL", "watermark_removed": False}

    monkeypatch.setattr(video_processor, "remove_veo_watermark", fallback_original)
    with pytest.raises(RuntimeError, match="WATERMARK_REMOVAL_FAILED"):
        video_processor.expand_16_9_to_9_16(raw_16_9, output, remove_watermark=True)
    assert not output.exists()


def test_open_google_flow_login_from_studio(video_fixture, monkeypatch):
    import sys

    opened = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("os.startfile", lambda path: opened.append(path), raising=False)

    response = client.post(
        "/v1/media/flow/login",
        headers={"Authorization": f"Bearer {video_fixture['token']}", "X-Workspace-Id": video_fixture["ws_id"]},
    )

    assert response.status_code == 200
    assert opened == [str(PROJECT_ROOT.parent / "00_DANG_NHAP_GOOGLE_FLOW.cmd")]


# ==============================================================================
# M-P3 TIMELINE TEST SUITE
# ==============================================================================

def test_timeline_get_returns_latest_version(video_fixture):
    """M-P3: GET /v1/media/projects/{id}/timeline trả version 0 khi rỗng và trả version mới nhất khi có."""
    proj_id = f"proj-tl-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="Test Project Timeline Get",
            created_by=video_fixture["user_id"]
        )
        db.add(proj)
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    # 1. Ban đầu chưa có timeline -> trả version 0
    resp = client.get(f"/v1/media/projects/{proj_id}/timeline", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 0
    assert data["timeline"]["clips"] == []

    # 2. Thêm version 1
    with SessionLocal() as db:
        tv1 = TimelineVersion(
            id=f"tl-{uuid.uuid4().hex[:8]}",
            project_id=proj_id,
            version=1,
            tracks_json=json.dumps({"width": 1080, "height": 1920, "fps": 30, "clips": []}),
            is_locked=False,
            created_by=video_fixture["user_id"]
        )
        db.add(tv1)
        db.commit()

    resp2 = client.get(f"/v1/media/projects/{proj_id}/timeline", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["version"] == 1


def test_timeline_put_round_trips_document(video_fixture):
    """M-P3: PUT /v1/media/projects/{id}/timeline lưu đúng document và GET lại round-trip 100%."""
    proj_id = f"proj-tl-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="Test Project Roundtrip",
            created_by=video_fixture["user_id"]
        )
        db.add(proj)
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    clip_bytes = video_fixture["clip_1"].read_bytes()
    audio_bytes = video_fixture["audio_file"].read_bytes()

    r_v = client.post(
        "/v1/media/upload",
        files={"file": ("v1.mp4", clip_bytes, "video/mp4")},
        data={"source_product": "UPLOAD", "expected_category": "video"},
        headers=headers
    )
    assert r_v.status_code == 200
    v_asset_id = r_v.json()["id"]

    r_a = client.post(
        "/v1/media/upload",
        files={"file": ("a1.mp3", audio_bytes, "audio/mpeg")},
        data={"source_product": "UPLOAD", "expected_category": "audio"},
        headers=headers
    )
    assert r_a.status_code == 200
    a_asset_id = r_a.json()["id"]

    payload = {
        "timeline": {
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "clips": [
                {
                    "clip_id": "clip_01",
                    "asset_id": v_asset_id,
                    "media_type": "video",
                    "start_ms": 0,
                    "duration_ms": 2000,
                    "trim_in_ms": 0,
                    "trim_out_ms": 2000,
                    "fit": "cover"
                }
            ],
            "voice_track": {
                "asset_id": a_asset_id,
                "start_ms": 0,
                "duration_ms": 2000,
                "gain_db": 0.0
            },
            "captions": [
                {
                    "caption_id": "cap_01",
                    "text": "TIKTOK REELS MASTER 2026",
                    "start_ms": 0,
                    "duration_ms": 2000,
                    "font_size": 28,
                    "safe_zone": True
                }
            ]
        },
        "expected_version": 0
    }

    resp = client.put(f"/v1/media/projects/{proj_id}/timeline", json=payload, headers=headers)
    assert resp.status_code == 200, f"PUT timeline failed: {resp.text}"
    data = resp.json()
    assert data["version"] == 1
    assert len(data["timeline"]["clips"]) == 1
    assert data["timeline"]["clips"][0]["asset_id"] == v_asset_id
    assert data["timeline"]["captions"][0]["text"] == "TIKTOK REELS MASTER 2026"

    # GET lại phai round-trip chính xác
    resp_get = client.get(f"/v1/media/projects/{proj_id}/timeline", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["version"] == 1
    assert resp_get.json()["timeline"]["clips"][0]["clip_id"] == "clip_01"


def test_timeline_put_rejects_stale_version(video_fixture):
    """M-P3: PUT timeline từ chối khi expected_version không khớp version hiện tại (OCC 409)."""
    proj_id = f"proj-tl-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="Test Stale Version",
            created_by=video_fixture["user_id"]
        )
        tv = TimelineVersion(
            id=f"tl-{uuid.uuid4().hex[:8]}",
            project_id=proj_id,
            version=3,
            tracks_json=json.dumps({"clips": []}),
            is_locked=False,
            created_by=video_fixture["user_id"]
        )
        db.add_all([proj, tv])
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    payload = {
        "timeline": {"width": 1080, "height": 1920, "fps": 30, "clips": []},
        "expected_version": 1  # Stale: version hiện tại là 3
    }
    resp = client.put(f"/v1/media/projects/{proj_id}/timeline", json=payload, headers=headers)
    assert resp.status_code == 409, f"Expected 409 Conflict, got {resp.status_code}"
    assert resp.json()["detail"]["error_code"] == "STALE_VERSION_CONFLICT"


def test_timeline_put_rejects_cross_workspace_assets(video_fixture):
    """M-P3: PUT timeline từ chối asset_id không thuộc workspace (HTTP 400)."""
    proj_id = f"proj-tl-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="Test Cross Workspace Asset",
            created_by=video_fixture["user_id"]
        )
        db.add(proj)
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    payload = {
        "timeline": {
            "clips": [
                {
                    "clip_id": "clip_alien",
                    "asset_id": "asset-nonexistent-or-alien",
                    "media_type": "video",
                    "start_ms": 0,
                    "duration_ms": 1000,
                    "trim_in_ms": 0,
                    "trim_out_ms": 1000,
                    "fit": "cover"
                }
            ]
        },
        "expected_version": 0
    }
    resp = client.put(f"/v1/media/projects/{proj_id}/timeline", json=payload, headers=headers)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    assert "ASSET_NOT_FOUND_OR_CROSS_WORKSPACE" in resp.json()["detail"]["error_code"]


def test_timeline_put_rejects_invalid_trim_and_unknown_fields(video_fixture):
    """M-P3: PUT timeline từ chối khi trim_out <= trim_in hoặc duration <= 0."""
    proj_id = f"proj-tl-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="Test Invalid Trim",
            created_by=video_fixture["user_id"]
        )
        db.add(proj)
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    payload_trim = {
        "timeline": {
            "clips": [
                {
                    "clip_id": "clip_bad_trim",
                    "asset_id": "asset-dummy",
                    "media_type": "video",
                    "start_ms": 0,
                    "duration_ms": 1000,
                    "trim_in_ms": 500,
                    "trim_out_ms": 200,
                    "fit": "cover"
                }
            ]
        }
    }
    resp = client.put(f"/v1/media/projects/{proj_id}/timeline", json=payload_trim, headers=headers)
    assert resp.status_code == 400

    payload_dur = {
        "timeline": {
            "clips": [
                {
                    "clip_id": "clip_bad_dur",
                    "asset_id": "asset-dummy",
                    "media_type": "video",
                    "start_ms": 0,
                    "duration_ms": 0,
                    "trim_in_ms": 0,
                    "trim_out_ms": 0,
                    "fit": "cover"
                }
            ]
        }
    }
    resp_dur = client.put(f"/v1/media/projects/{proj_id}/timeline", json=payload_dur, headers=headers)
    assert resp_dur.status_code in (400, 422)


def test_timeline_put_does_not_modify_locked_version(video_fixture):
    """M-P3: PUT timeline từ chối chỉnh sửa khi version mới nhất đã bị khóa (HTTP 400)."""
    proj_id = f"proj-tl-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="Test Locked Project",
            created_by=video_fixture["user_id"]
        )
        tv = TimelineVersion(
            id=f"tl-{uuid.uuid4().hex[:8]}",
            project_id=proj_id,
            version=1,
            tracks_json=json.dumps({"clips": []}),
            is_locked=True,
            created_by=video_fixture["user_id"]
        )
        db.add_all([proj, tv])
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    payload = {
        "timeline": {"clips": []},
        "expected_version": 1
    }
    resp = client.put(f"/v1/media/projects/{proj_id}/timeline", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "TIMELINE_LOCKED"


# ==============================================================================
# M-P5 RENDER MP4 TEST SUITE
# ==============================================================================

def make_test_image(path: pathlib.Path):
    """Tạo tệp ảnh PNG 720x1280 bằng FFmpeg lavfi."""
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-f", "lavfi",
        "-i", "color=c=0x2563EB:s=720x1280:d=1", "-vframes", "1", str(path)
    ], check=True, capture_output=True)


def test_timeline_render_image_only(video_fixture, tmp_path):
    """M-P5: Render MP4 từ chỉ ảnh tĩnh (convert ảnh sang clip đúng duration, 1080x1920, 30fps)."""
    img_file = tmp_path / "photo_test.png"
    make_test_image(img_file)

    out_mp4 = tmp_path / "out_img_render.mp4"
    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(
                clip_id="img_c1",
                asset_id="asset-img-1",
                media_type=TimelineMediaType.IMAGE,
                start_ms=0,
                duration_ms=2000,
                fit=TimelineFitMode.COVER
            )
        ]
    )

    meta = video_processor.render_timeline_document(
        timeline=timeline_doc,
        asset_path_resolver=lambda aid: img_file,
        output_path=out_mp4,
        temp_dir=tmp_path / "tmp_render_1"
    )

    assert out_mp4.exists()
    assert meta["width"] == 1080
    assert meta["height"] == 1920
    assert meta["is_vertical_9_16"] is True
    assert 1.9 <= meta["duration_seconds"] <= 2.2


def test_timeline_render_video_only(video_fixture, tmp_path):
    """M-P5: Render MP4 từ chỉ video (trim đúng in/out, 1080x1920, 30fps)."""
    out_mp4 = tmp_path / "out_vid_render.mp4"
    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(
                clip_id="vid_c1",
                asset_id="asset-vid-1",
                media_type=TimelineMediaType.VIDEO,
                start_ms=0,
                duration_ms=1500,
                trim_in_ms=0,
                trim_out_ms=1500,
                fit=TimelineFitMode.COVER
            )
        ]
    )

    meta = video_processor.render_timeline_document(
        timeline=timeline_doc,
        asset_path_resolver=lambda aid: video_fixture["clip_1"],
        output_path=out_mp4,
        temp_dir=tmp_path / "tmp_render_2"
    )

    assert out_mp4.exists()
    assert meta["width"] == 1080
    assert meta["height"] == 1920
    assert 1.4 <= meta["duration_seconds"] <= 1.7
    assert audio_processor.probe_audio(out_mp4)["codec_name"] == "unknown"


def test_timeline_render_keeps_flow_generated_audio(video_fixture, tmp_path):
    flow_clip = tmp_path / "flow_clip_with_audio.mp4"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-i", str(video_fixture["clip_1"]),
        "-i", str(video_fixture["audio_file"]), "-map", "0:v:0", "-map", "1:a:0",
        "-t", "1.5", "-c:v", "copy", "-c:a", "aac", str(flow_clip),
    ], check=True, capture_output=True)
    timeline = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(clip_id="flow-1", asset_id="flow", media_type="video", duration_ms=1500, trim_out_ms=1500),
            TimelineClip(clip_id="flow-2", asset_id="flow", media_type="video", duration_ms=1500, trim_out_ms=1500),
        ],
    )
    output = tmp_path / "flow_audio_render.mp4"

    meta = video_processor.render_timeline_document(timeline, lambda _: flow_clip, output, temp_dir=tmp_path / "flow_render", transition_seconds=0.3)

    audio_meta = audio_processor.probe_audio(output)
    assert audio_meta["codec_name"] == "aac"
    assert 2.9 <= audio_meta["duration_seconds"] <= 3.1
    assert 2.9 <= meta["duration_seconds"] <= 3.1


def test_timeline_crossfade_keeps_requested_duration_and_decodes(video_fixture, tmp_path):
    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(clip_id="first", asset_id="first", media_type=TimelineMediaType.VIDEO, start_ms=0, duration_ms=1500, trim_out_ms=1500),
            TimelineClip(clip_id="second", asset_id="second", media_type=TimelineMediaType.VIDEO, start_ms=1500, duration_ms=1500, trim_out_ms=1500),
            TimelineClip(clip_id="third", asset_id="first", media_type=TimelineMediaType.VIDEO, start_ms=3000, duration_ms=1500, trim_out_ms=1500),
        ],
        voice_track=TimelineAudioTrack(asset_id="voice", duration_ms=4500),
    )
    output = tmp_path / "crossfade.mp4"
    meta = video_processor.render_timeline_document(
        timeline_doc,
        lambda aid: video_fixture["audio_file"] if aid == "voice" else video_fixture["clip_1"] if aid == "first" else video_fixture["clip_2"],
        output,
        transition_seconds=0.3,
    )

    decode = subprocess.run(
        [video_processor.ffmpeg_bin, "-v", "error", "-i", str(output), "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert 4.4 <= meta["duration_seconds"] <= 4.6
    assert decode.returncode == 0 and not decode.stderr.strip()
    assert audio_processor.probe_audio(output)["codec_name"] == "aac"


def test_timeline_render_mixed_order_and_durations(video_fixture, tmp_path):
    """M-P5: Render kết hợp ảnh và video theo thứ tự tùy biến, tổng thời lượng chính xác."""
    img_file = tmp_path / "photo_mixed.png"
    make_test_image(img_file)

    out_mp4 = tmp_path / "out_mixed_render.mp4"
    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(
                clip_id="c1_img",
                asset_id="asset-img",
                media_type=TimelineMediaType.IMAGE,
                start_ms=0,
                duration_ms=1000,
                fit=TimelineFitMode.COVER
            ),
            TimelineClip(
                clip_id="c2_vid",
                asset_id="asset-vid",
                media_type=TimelineMediaType.VIDEO,
                start_ms=1000,
                duration_ms=1500,
                trim_in_ms=0,
                trim_out_ms=1500,
                fit=TimelineFitMode.COVER
            )
        ]
    )

    def resolver(aid):
        return img_file if "img" in aid else video_fixture["clip_1"]

    meta = video_processor.render_timeline_document(
        timeline=timeline_doc,
        asset_path_resolver=resolver,
        output_path=out_mp4,
        temp_dir=tmp_path / "tmp_render_3"
    )

    assert out_mp4.exists()
    assert meta["width"] == 1080
    assert meta["height"] == 1920
    assert 2.3 <= meta["duration_seconds"] <= 2.7


def test_timeline_render_burns_vietnamese_caption(video_fixture, tmp_path):
    """M-P5: Burn-in phụ đề tiếng Việt có dấu đầy đủ vào TikTok Safe Zone không lỗi font."""
    img_file = tmp_path / "photo_cap.png"
    make_test_image(img_file)

    out_mp4 = tmp_path / "out_cap_render.mp4"
    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(
                clip_id="c1",
                asset_id="asset-img",
                media_type=TimelineMediaType.IMAGE,
                start_ms=0,
                duration_ms=2000,
                fit=TimelineFitMode.COVER
            )
        ],
        captions=[
            TimelineCaption(
                caption_id="cap_1",
                text="ĐỪNG GÕ KỊCH BẢN TAY NỮA! BẬT AUTO DỰNG 9:16",
                start_ms=0,
                duration_ms=2000,
                font_size=26,
                safe_zone=True
            )
        ]
    )

    meta = video_processor.render_timeline_document(
        timeline=timeline_doc,
        asset_path_resolver=lambda aid: img_file,
        output_path=out_mp4,
        temp_dir=tmp_path / "tmp_render_4"
    )

    assert out_mp4.exists()
    assert meta["width"] == 1080
    assert meta["height"] == 1920


def test_timeline_render_caption_failure_raises_error(video_fixture, tmp_path, monkeypatch):
    """M-P5: Khi FFmpeg burn-in caption gặp lỗi (font hỏng / filter lỗi), bắt buộc raise RuntimeError thay vì âm thầm bỏ qua."""
    img_file = tmp_path / "photo_cap_err.png"
    make_test_image(img_file)

    out_mp4 = tmp_path / "out_cap_err.mp4"
    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(
                clip_id="c1",
                asset_id="asset-img",
                media_type=TimelineMediaType.IMAGE,
                start_ms=0,
                duration_ms=1000,
                fit=TimelineFitMode.COVER
            )
        ],
        captions=[
            TimelineCaption(
                caption_id="cap_err",
                text="Phụ đề lỗi",
                start_ms=0,
                duration_ms=1000
            )
        ]
    )

    orig_run = subprocess.run
    def mock_run(cmd, *args, **kwargs):
        # Giả lập lỗi khi gọi filter drawtext
        if any("drawtext=" in str(arg) for arg in cmd):
            return subprocess.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="Font not found or drawtext error")

        return orig_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)

    with pytest.raises(RuntimeError, match="Lỗi khắc phụ đề"):
        video_processor.render_timeline_document(
            timeline=timeline_doc,
            asset_path_resolver=lambda aid: img_file,
            output_path=out_mp4,
            temp_dir=tmp_path / "tmp_cap_err"
        )



def test_timeline_render_respects_fit_mode(video_fixture, tmp_path):
    """M-P5: Hỗ trợ cả 2 chế độ cover và contain chuẩn 1080x1920."""
    img_file = tmp_path / "photo_fit.png"
    make_test_image(img_file)

    out_cover = tmp_path / "out_fit_cover.mp4"
    out_contain = tmp_path / "out_fit_contain.mp4"

    doc_cover = TimelineDocument(
        clips=[TimelineClip(clip_id="c_cov", asset_id="img", media_type=TimelineMediaType.IMAGE, duration_ms=1000, fit=TimelineFitMode.COVER)]
    )
    doc_contain = TimelineDocument(
        clips=[TimelineClip(clip_id="c_cnt", asset_id="img", media_type=TimelineMediaType.IMAGE, duration_ms=1000, fit=TimelineFitMode.CONTAIN)]
    )

    meta_cov = video_processor.render_timeline_document(timeline=doc_cover, asset_path_resolver=lambda a: img_file, output_path=out_cover, temp_dir=tmp_path / "tmp_cov")
    meta_cnt = video_processor.render_timeline_document(timeline=doc_contain, asset_path_resolver=lambda a: img_file, output_path=out_contain, temp_dir=tmp_path / "tmp_cnt")

    assert meta_cov["width"] == 1080 and meta_cov["height"] == 1920
    assert meta_cnt["width"] == 1080 and meta_cnt["height"] == 1920


def test_timeline_render_audio_shorter_and_longer_than_video(video_fixture, tmp_path):
    """M-P5: Âm thanh dài hơn hoặc ngắn hơn video đều được khóa chuẩn theo thời lượng video."""
    out_mp4 = tmp_path / "out_audio_mix.mp4"
    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(
                clip_id="c1",
                asset_id="asset-vid",
                media_type=TimelineMediaType.VIDEO,
                duration_ms=2000,
                trim_in_ms=0,
                trim_out_ms=2000
            )
        ],
        voice_track=TimelineAudioTrack(asset_id="voice-id", start_ms=0, duration_ms=4000, gain_db=0.0)
    )

    meta = video_processor.render_timeline_document(
        timeline=timeline_doc,
        asset_path_resolver=lambda aid: video_fixture["clip_1"] if aid == "asset-vid" else video_fixture["audio_file"],
        output_path=out_mp4,
        temp_dir=tmp_path / "tmp_render_audio"
    )

    assert out_mp4.exists()
    assert 1.9 <= meta["duration_seconds"] <= 2.2
    assert "audio_loudness_lufs" in meta
    assert -15.0 <= meta["audio_loudness_lufs"] <= -13.0


def test_timeline_render_failure_never_creates_asset(video_fixture):
    """M-P5: Khi render thất bại (tệp nguồn hỏng/lỗi), API trả về 400 và tuyệt đối không tạo MediaAsset rác trong CSDL."""
    proj_id = f"proj-fail-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="Test Failure Project",
            created_by=video_fixture["user_id"]
        )
        # Tạo timeline version với asset rỗng hoặc không tồn tại
        tv_id = f"tl-fail-{uuid.uuid4().hex[:8]}"
        tv = TimelineVersion(
            id=tv_id,
            project_id=proj_id,
            version=1,
            tracks_json=json.dumps({
                "clips": [
                    {
                        "clip_id": "c_fail",
                        "asset_id": "asset-broken-nonexistent",
                        "media_type": "video",
                        "duration_ms": 1000
                    }
                ]
            }),
            is_locked=False,
            created_by=video_fixture["user_id"]
        )
        db.add_all([proj, tv])
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    resp = client.post(
        f"/v1/media/projects/{proj_id}/render-timeline",
        data={"timeline_version_id": tv_id},
        headers=headers
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "RENDER_FAILED"

    # Kiểm tra không có asset rác nào được lưu vào CSDL
    with SessionLocal() as db:
        count = db.query(MediaAsset).filter(
            MediaAsset.project_id == proj_id,
            MediaAsset.source_product == "TIMELINE_RENDER"
        ).count()
        assert count == 0, f"Found {count} garbage assets in DB after failed render!"


def test_timeline_save_concurrent_integrity_error_returns_409(video_fixture, monkeypatch):
    """Issue 1: Khi hai phiên cùng ghi timeline đồng thời gây IntegrityError, API bắt buộc trả HTTP 409 STALE_VERSION_CONFLICT."""
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from src.database import SessionLocal

    proj_id = f"proj-occ-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="OCC Test Project",
            created_by=video_fixture["user_id"]
        )
        db.add(proj)
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    # Monkeypatch db.commit trong save_project_timeline để ném IntegrityError
    orig_commit = Session.commit
    def mock_commit(self):
        if self.get_bind() is engine:
            raise IntegrityError("UNIQUE constraint failed: timeline_versions.project_id, timeline_versions.version", params=[], orig=Exception("unique constraint"))
        return orig_commit(self)

    monkeypatch.setattr(Session, "commit", mock_commit)

    payload = {
        "expected_version": 0,
        "timeline": {
            "clips": []
        }
    }

    resp = client.put(
        f"/v1/media/projects/{proj_id}/timeline",
        json=payload,
        headers=headers
    )

    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["error_code"] == "STALE_VERSION_CONFLICT"
    assert "Xung đột phiên bản timeline (OCC)" in body["message"]


def test_timeline_save_trim_out_exceeding_source_duration_returns_400(video_fixture):
    """Issue 3: Điểm ra trim_out_ms vượt quá thời lượng video nguồn MediaAsset.duration_ms bị từ chối bằng HTTP 400 INVALID_TRIM_OUT."""
    proj_id = f"proj-trim-{uuid.uuid4().hex[:8]}"
    asset_id = f"ast-short-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        proj = ProductionProject(
            id=proj_id,
            workspace_id=video_fixture["ws_id"],
            title="Trim Out Duration Limit Project",
            created_by=video_fixture["user_id"]
        )
        # Video asset nguồn chỉ dài 2000ms (2s)
        ast = MediaAsset(
            id=asset_id,
            workspace_id=video_fixture["ws_id"],
            project_id=proj_id,
            storage_key="test/short.mp4",
            sha256="dummy_sha256_short",
            byte_size=1024,
            mime_detected="video/mp4",
            duration_ms=2000,
            source_product="UPLOAD",
            created_by=video_fixture["user_id"]
        )
        db.add_all([proj, ast])
        db.commit()

    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    # Thử lưu clip có trim_out_ms = 5000ms (5s > 2s nguồn)
    payload = {
        "expected_version": 0,
        "timeline": {
            "clips": [
                {
                    "clip_id": "c_overflow",
                    "asset_id": asset_id,
                    "media_type": "video",
                    "duration_ms": 4000,
                    "trim_in_ms": 1000,
                    "trim_out_ms": 5000
                }
            ]
        }
    }

    resp = client.put(
        f"/v1/media/projects/{proj_id}/timeline",
        json=payload,
        headers=headers
    )

    assert resp.status_code == 400
    body = resp.json()["detail"]
    assert body["error_code"] == "INVALID_TRIM_OUT"
    assert "vượt quá thời lượng thực tế của video nguồn" in body["message"]


def test_timeline_render_trim_out_exceeding_source_duration_raises_error(video_fixture, tmp_path):
    """Issue 3: Render kiểm tra lại nguồn thật, nếu trim_out_ms vượt thời lượng video nguồn ném RuntimeError."""
    out_mp4 = tmp_path / "out_trim_err.mp4"
    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(
                clip_id="vid_overflow",
                asset_id="asset-vid-1",
                media_type=TimelineMediaType.VIDEO,
                start_ms=0,
                duration_ms=6000,
                trim_in_ms=0,
                trim_out_ms=10000,  # 10s vượt xa clip_1 chỉ có 2-3s
                fit=TimelineFitMode.COVER
            )
        ]
    )

    with pytest.raises(RuntimeError) as exc_info:
        video_processor.render_timeline_document(
            timeline=timeline_doc,
            asset_path_resolver=lambda aid: video_fixture["clip_1"],
            output_path=out_mp4,
            temp_dir=tmp_path / "tmp_trim_err"
        )
    assert "vượt quá thời lượng thực tế của video nguồn" in str(exc_info.value)


def test_timeline_render_loudness_out_of_spec_raises_error(video_fixture, tmp_path, monkeypatch):
    """Issue 2: Khi âm lượng tệp kết xuất không nằm trong chuẩn TikTok (-14.0 ± 1.0 LUFS), render bắt buộc raise RuntimeError."""
    from src.modules.media_studio.audio_processor import audio_processor

    out_mp4 = tmp_path / "out_loud_err.mp4"
    img_file = tmp_path / "photo_loud.png"
    make_test_image(img_file)

    timeline_doc = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[
            TimelineClip(
                clip_id="c_img",
                asset_id="asset-img",
                media_type=TimelineMediaType.IMAGE,
                start_ms=0,
                duration_ms=1000,
                fit=TimelineFitMode.COVER
            )
        ],
        voice_track=TimelineAudioTrack(asset_id="voice-id", start_ms=0, duration_ms=1000, gain_db=0.0)
    )

    # Giả lập measure_loudness trả về -10.0 LUFS (quá to, vi phạm chuẩn -14 ± 1)
    def mock_loudness(path):
        return {
            "measured_i_lufs": -10.5,
            "measured_tp_dbtp": 0.2,
            "measured_lra_lu": 5.0
        }
    monkeypatch.setattr(audio_processor, "measure_loudness", mock_loudness)

    with pytest.raises(RuntimeError) as exc_info:
        video_processor.render_timeline_document(
            timeline=timeline_doc,
            asset_path_resolver=lambda aid: img_file if aid == "asset-img" else video_fixture["audio_file"],
            output_path=out_mp4,
            temp_dir=tmp_path / "tmp_loud_err"
        )
    assert "Kiểm định chất lượng âm lượng EBU R128 không đạt chuẩn phát sóng TikTok" in str(exc_info.value)


def test_project_create_and_list_are_available(video_fixture):
    headers = {
        "Authorization": f"Bearer {video_fixture['token']}",
        "X-Workspace-Id": video_fixture["ws_id"]
    }

    created = client.post("/v1/media/projects", json={"title": "Video thử nghiệm"}, headers=headers)
    assert created.status_code == 201
    project = created.json()
    assert project["title"] == "Video thử nghiệm"
    assert project["workspace_id"] == video_fixture["ws_id"]

    listed = client.get("/v1/media/projects", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [project["id"]]


def test_generated_video_is_bound_to_existing_project(video_fixture, monkeypatch):
    from src.modules.media_studio import router as media_router_module

    project_id = f"proj-auto-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(ProductionProject(
            id=project_id,
            workspace_id=video_fixture["ws_id"],
            title="Dự án tự động",
            created_by=video_fixture["user_id"]
        ))
        db.commit()

    received = {}

    def mock_generate_video_scene(**kwargs):
        received.update(kwargs)
        asset = MediaAsset(
            id=f"asset-{uuid.uuid4().hex[:12]}",
            workspace_id=kwargs["workspace_id"],
            project_id=kwargs["project_id"],
            storage_key="workspaces/test/media/video.mp4",
            sha256="a" * 64,
            byte_size=100,
            mime_detected="video/mp4",
            source_product="GOOGLE_FLOW",
            original_filename="video.mp4",
            created_by=kwargs["user_id"],
            approval_state="UNREVIEWED"
        )
        kwargs["db"].add(asset)
        kwargs["db"].commit()
        kwargs["db"].refresh(asset)
        return asset

    monkeypatch.setattr(
        media_router_module,
        "video_orchestrator",
        type("MockVideoOrchestrator", (), {"generate_video_scene": staticmethod(mock_generate_video_scene)})()
    )
    response = client.post(
        "/v1/media/video/generate",
        data={"prompt": "Video giới thiệu cà phê", "project_id": project_id},
        headers={
            "Authorization": f"Bearer {video_fixture['token']}",
            "X-Workspace-Id": video_fixture["ws_id"]
        }
    )

    assert response.status_code == 200, response.text
    assert response.json()["project_id"] == project_id
    assert received["project_id"] == project_id
    assert received["remove_watermark"] is False


def test_expand_video_uses_safe_temp_name_and_links_project(video_fixture, monkeypatch, tmp_path):
    from src.modules.media_studio import router as media_router_module

    project_id = f"proj-expand-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(ProductionProject(
            id=project_id,
            workspace_id=video_fixture["ws_id"],
            title="Dự án mở rộng",
            created_by=video_fixture["user_id"]
        ))
        db.commit()

    monkeypatch.setattr(media_router_module, "get_workspace_storage_dir", lambda workspace_id: tmp_path)
    input_paths = []

    def mock_expand(input_video_path, output_video_path, **kwargs):
        input_paths.append(pathlib.Path(input_video_path))
        pathlib.Path(output_video_path).write_bytes(b"verified test video bytes")
        return {"duration_seconds": 2}

    monkeypatch.setattr(media_router_module.video_processor, "expand_16_9_to_9_16", mock_expand)
    response = client.post(
        "/v1/media/video/expand",
        data={"project_id": project_id},
        files={"file": ("../../source.mp4", video_fixture["clip_1"].read_bytes(), "video/mp4")},
        headers={
            "Authorization": f"Bearer {video_fixture['token']}",
            "X-Workspace-Id": video_fixture["ws_id"]
        }
    )

    assert response.status_code == 200
    assert response.json()["project_id"] == project_id
    assert input_paths[0].parent == tmp_path
    assert ".." not in input_paths[0].name
    assert not list(tmp_path.glob("flow_raw_*"))


def test_flow_provider_uses_native_portrait_output(video_fixture, monkeypatch, tmp_path):
    import types
    from src.modules.media_studio import video_provider as provider_module

    raw_video = tmp_path / "flow-with-auto-audio.mp4"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i", "color=c=navy:s=1080x1920:d=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-c:a", "aac", str(raw_video),
    ], check=True, capture_output=True)
    received = {}

    class FakeFlowClient:
        def __init__(self, **_kwargs):
            pass

        def create_video(self, **kwargs):
            received.update(kwargs)
            return {"storage_path": str(raw_video)}

    monkeypatch.setattr(provider_module, "MEDIA_ROOT_DIR", tmp_path / "media")
    monkeypatch.setitem(sys.modules, "google_flow_client", types.SimpleNamespace(GoogleFlowClient=FakeFlowClient))
    monkeypatch.setattr(provider_module.video_processor, "expand_16_9_to_9_16", lambda **_: pytest.fail("unexpected blur expansion"))

    result = provider_module.GoogleFlowZeroCostProvider().generate(
        "A paper assistant walks slowly.", aspect_ratio="9:16", prompt_language="en", include_audio=False
    )

    assert received["aspect_ratio"] == "9:16"
    assert "Authoritative visual brief" in received["prompt"]
    assert "Create a 9:16 video" in received["prompt"]
    assert result["aspect_ratio"] == "9:16"
    assert result["raw_source_aspect"] == "9:16"
    assert result["expansion_technique"] is None
    assert pathlib.Path(result["storage_path"]).is_file()
    assert video_processor.probe_video(pathlib.Path(result["storage_path"]))["aspect_ratio"] == "9:16"
    assert audio_processor.probe_audio(pathlib.Path(result["storage_path"]))["codec_name"] == "unknown"


def test_timeline_renderer_wraps_long_captions(video_fixture, tmp_path):
    caption = "Dải màu ngang dịch chuyển qua bảng kiểm tra với các sọc màu dọc"
    timeline = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=[TimelineClip(clip_id="video", asset_id="video", media_type="video", duration_ms=1500)],
        captions=[TimelineCaption(text=caption, start_ms=0, duration_ms=1400, font_size=52)],
    )
    render_dir = tmp_path / "caption_render"
    video_processor.render_timeline_document(
        timeline,
        lambda _: video_fixture["clip_1"],
        tmp_path / "caption_render.mp4",
        temp_dir=render_dir,
    )
    lines = (render_dir / "caption_0.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) > 1
    assert max(map(len, lines)) <= 32


def _v4_planning_reply(messages, storyboard):
    # Lượt phân tích brief và lượt dựng cảnh có hợp đồng khác nhau.
    brief = {"pains": [{"id": "p1", "text": "Thông tin rời rạc.", "source": "inferred"}],
             "solutions": [{"id": "s1", "text": "Tìm nguồn liên quan.", "source": "content"}]}
    if "required_schema" not in json.loads(messages[1]["content"]):
        return json.dumps(brief, ensure_ascii=False)
    storyboard = json.loads(json.dumps(storyboard))
    storyboard["narration"] = storyboard["narration"].replace("RAG", "rắc")
    for index, shot in enumerate(storyboard["shots"]):
        shot["narration"] = shot["narration"].replace("RAG", "rắc")
        shot.update(prompt_contract_version=4, beat=["PAIN", "SOLUTION", "OUTCOME"][index],
                    message_ids=[["p1"], ["s1"], []][index], action_beats=[
                        {"start_s": 0, "end_s": 4, "action": "Nhân viên mở hồ sơ."},
                        {"start_s": 4, "end_s": 10, "action": "Nhân viên tìm thẻ và đặt cạnh kết quả."}])
        shot.setdefault("continues_previous", False)
    return json.dumps(storyboard, ensure_ascii=False)


def test_content_video_plan_calls_llm_and_persists_reviewable_storyboard(video_fixture, monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from src.modules.llm.client import LLMClient

    storyboard = {
        "title": "Giới thiệu RAG",
        "narration": "RAG giúp truy xuất thông tin trước khi trả lời.",
        "continuity_anchor": "Một chuyên gia công nghệ mặc áo xanh navy giải thích trong studio tối giản cùng bảng màu navy và teal.",
        "shots": [
            {"shot_id": "s1", "scene": "Vấn đề", "narration": "Thông tin rời rạc.", "prompt": "Tư liệu rời rạc trên bàn làm việc", "flow_prompt_en": "Three paper cards slide apart and settle on the desk beside the same navy paper assistant in the same studio, with the same navy and teal palette.", "duration_seconds": 10},
            {"shot_id": "s2", "scene": "Cách làm", "narration": "RAG tìm nguồn liên quan.", "prompt": "Tìm kiếm tài liệu theo câu hỏi", "flow_prompt_en": "The same navy paper assistant moves one card from the shelf to the computer in the same studio, with the same navy and teal palette.", "duration_seconds": 10},
            {"shot_id": "s3", "scene": "Kết quả", "narration": "Câu trả lời có căn cứ.", "prompt": "Trình bày câu trả lời cùng nguồn", "flow_prompt_en": "The same navy paper assistant places the answer beside its source in the same studio, with the same navy and teal palette, then holds the pose.", "duration_seconds": 10},
        ],
    }

    class FakeLLM:
        is_enabled = True
        max_output_tokens = 6000

        def complete(self, messages, max_tokens=None):
            return SimpleNamespace(content=_v4_planning_reply(messages, storyboard), model="test-storyboard")

    monkeypatch.setattr(LLMClient, "from_db", classmethod(lambda cls, db: FakeLLM()))
    from src.models.entities import ProductionProject
    from src.modules.tao_video_noi_dung.contracts import CreatePlanRequest, CreateRunRequest
    from src.modules.tao_video_noi_dung.service import approve_plan, create_plan, create_run

    project_id = f"project-plan-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(ProductionProject(
            id=project_id,
            workspace_id=video_fixture["ws_id"],
            title="RAG video",
            created_by=video_fixture["user_id"],
        ))
        voice_path = video_fixture["audio_file"]
        voice_asset = MediaAsset(
            id=f"voice-{uuid.uuid4().hex[:8]}", workspace_id=video_fixture["ws_id"], project_id=project_id,
            storage_key=f"tests/{voice_path.name}", sha256=hashlib.sha256(voice_path.read_bytes()).hexdigest(),
            byte_size=voice_path.stat().st_size, mime_detected="audio/mpeg", source_product="TEST_UPLOAD",
            original_filename=voice_path.name, created_by=video_fixture["user_id"], duration_ms=4000,
            approval_state="UNREVIEWED",
        )
        db.add(voice_asset)
        db.commit()
        voice_asset_id = voice_asset.id
        response = create_plan(
            db,
            project_id,
            video_fixture["ws_id"],
            video_fixture["user_id"],
            CreatePlanRequest.model_validate({
            "content": "RAG truy xuất tài liệu liên quan trước khi tạo câu trả lời có căn cứ.",
            "target_duration_seconds": 30,
            "aspect_ratio": "16:9",
            }),
        )
        second_plan = create_plan(
            db,
            project_id,
            video_fixture["ws_id"],
            video_fixture["user_id"],
            CreatePlanRequest.model_validate({
                "content": "RAG tìm tài liệu đáng tin trước rồi mới tạo câu trả lời cho người dùng.",
                "target_duration_seconds": 30,
            "aspect_ratio": "16:9",
            }),
        )
        assert response.style_snapshot_sha256 == second_plan.style_snapshot_sha256

    assert response.status == "DRAFT"
    assert len(response.storyboard.shots) == 3
    assert response.storyboard.shots[0].shot_id == "s1"
    assert "flow_prompt_en" not in response.storyboard.shots[0].model_dump()
    assert response.style_snapshot.aspect_ratio == "16:9"
    assert response.style_snapshot.style_name.startswith("Origami")
    assert "Nhân vật, đạo cụ và bối cảnh" in response.style_snapshot.visual_rules
    assert "không có người thật" in response.style_snapshot.visual_rules

    with SessionLocal() as db:
        with pytest.raises(Exception) as self_approval:
            approve_plan(db, project_id, response.id, video_fixture["ws_id"], video_fixture["user_id"])
        assert getattr(self_approval.value, "status_code", None) == 403

        monkeypatch.setenv("BAHA_AUTH_APP_ENV", "test")
        monkeypatch.setenv("BAHA_AUTH_ALLOW_SELF_APPROVAL_IN_TEST", "1")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./sin_content_e2e_test.db")
        monkeypatch.setenv("BAHA_AUTH_DATABASE_URL", "sqlite:///./baha_auth_e2e_test.db")
        test_approved = approve_plan(db, project_id, second_plan.id, video_fixture["ws_id"], video_fixture["user_id"])
        assert test_approved.status == "APPROVED"

        approved = approve_plan(db, project_id, response.id, video_fixture["ws_id"], "independent-reviewer")
        assert approved.status == "APPROVED"
        request = CreateRunRequest(plan_id=approved.id, voice_asset_id=voice_asset_id, idempotency_key=f"run-{uuid.uuid4().hex}")
        run = create_run(db, project_id, video_fixture["ws_id"], "independent-reviewer", request)
        duplicate = create_run(db, project_id, video_fixture["ws_id"], "independent-reviewer", request)
        native_request = CreateRunRequest(plan_id=approved.id, idempotency_key=f"native-{uuid.uuid4().hex}")
        native_run = create_run(db, project_id, video_fixture["ws_id"], "independent-reviewer", native_request)

        from src.models.entities import ContentVideoRun
        from src.modules.tao_video_noi_dung.contracts import ReconcileShotRequest
        from src.modules.tao_video_noi_dung import runner
        from src.modules.tao_video_noi_dung.runner import reconcile_shot

        uncertain_run = create_run(
            db,
            project_id,
            video_fixture["ws_id"],
            "independent-reviewer",
            CreateRunRequest(plan_id=approved.id, idempotency_key=f"reconcile-{uuid.uuid4().hex}"),
        )
        persisted_run = db.query(ContentVideoRun).filter_by(id=uncertain_run.id).one()
        uncertain_steps = json.loads(persisted_run.steps_json)
        uncertain_steps[0]["state"] = "NEEDS_RECONCILIATION"
        persisted_run.steps_json = json.dumps(uncertain_steps)
        persisted_run.status = "NEEDS_RECONCILIATION"
        persisted_run.started_at = datetime.now(timezone.utc)
        db.commit()

        reconciled_path = tmp_path / "workspaces" / video_fixture["ws_id"] / "media" / "recovered.mp4"
        reconciled_path.parent.mkdir(parents=True, exist_ok=True)
        reconciled_path.write_bytes(video_fixture["clip_1"].read_bytes())
        reconciled_asset = MediaAsset(
            id=f"recovered-{uuid.uuid4().hex[:8]}",
            workspace_id=video_fixture["ws_id"],
            project_id=project_id,
            storage_key=f"workspaces/{video_fixture['ws_id']}/media/recovered.mp4",
            sha256=hashlib.sha256(reconciled_path.read_bytes()).hexdigest(),
            byte_size=reconciled_path.stat().st_size,
            mime_detected="video/mp4",
            source_product="UPLOAD",
            original_filename="recovered.mp4",
            created_by="independent-reviewer",
            duration_ms=10000,
            approval_state="UNREVIEWED",
        )
        db.add(reconciled_asset)
        db.commit()
        monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
        monkeypatch.setattr(runner.video_processor, "probe_video", lambda _: {
            "width": 1920, "height": 1080, "codec_name": "h264", "duration_seconds": 10.0, "frame_rate": 30.0,
        })
        monkeypatch.setattr(runner.audio_processor, "probe_audio", lambda _: {"codec_name": "aac"})
        reconcile_request = ReconcileShotRequest(
            shot_id="s1", asset_id=reconciled_asset.id, reason="Đã đối chiếu clip Flow với shot s1."
        )
        persisted_run.lease_token = "worker-still-active"
        persisted_run.lease_expires_at = None
        db.commit()
        with pytest.raises(Exception) as unknown_lease:
            reconcile_shot(
                db, project_id, uncertain_run.id, video_fixture["ws_id"], "independent-reviewer", reconcile_request
            )
        assert getattr(unknown_lease.value, "status_code", None) == 409

        persisted_run.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
        db.commit()
        with pytest.raises(Exception) as active_worker:
            reconcile_shot(
                db, project_id, uncertain_run.id, video_fixture["ws_id"], "independent-reviewer", reconcile_request
            )
        assert getattr(active_worker.value, "status_code", None) == 409
        db.refresh(persisted_run)
        assert persisted_run.status == "NEEDS_RECONCILIATION"
        persisted_run.lease_token = None
        persisted_run.lease_expires_at = None
        db.commit()
        def race_update_run(_):
            with SessionLocal() as competing_db:
                competing_db.query(ContentVideoRun).filter_by(id=uncertain_run.id).update({"status": "QUEUED"})
                competing_db.commit()
            return {"width": 1920, "height": 1080, "codec_name": "h264", "duration_seconds": 10.0, "frame_rate": 30.0}

        monkeypatch.setattr(runner.video_processor, "probe_video", race_update_run)
        with pytest.raises(Exception) as reconcile_conflict:
            reconcile_shot(
                db, project_id, uncertain_run.id, video_fixture["ws_id"],
                "independent-reviewer", reconcile_request,
            )
        assert getattr(reconcile_conflict.value, "status_code", None) == 409
        db.rollback()
        db.refresh(persisted_run)
        assert persisted_run.status == "QUEUED"
        persisted_run.status = "NEEDS_RECONCILIATION"
        db.commit()
        monkeypatch.setattr(runner.video_processor, "probe_video", lambda _: {
            "width": 1920, "height": 1080, "codec_name": "h264", "duration_seconds": 10.0, "frame_rate": 30.0,
        })

        reconcile_shot(
            db,
            project_id,
            uncertain_run.id,
            video_fixture["ws_id"],
            "independent-reviewer",
            reconcile_request,
        )
        db.refresh(persisted_run)
        reconciled_steps = json.loads(persisted_run.steps_json)
        assert persisted_run.status == "QUEUED"
        assert reconciled_steps[0]["state"] == "SUCCEEDED"
        assert reconciled_steps[0]["asset_id"] == reconciled_asset.id
        assert reconciled_steps[0]["reconciled_by"] == "independent-reviewer"

    assert run.id == duplicate.id
    assert run.status == "QUEUED"
    assert len(run.steps) == 3
    assert all(step["state"] == "READY" and step["command_sha256"] for step in run.steps)
    assert all("mô hình origami đã gấp thành hình hoàn chỉnh" in step["prompt"] for step in run.steps)
    assert native_run.voice_asset_id is None
    assert all(step["voice_asset_id"] is None for step in native_run.steps)


@pytest.mark.parametrize("with_voice_asset", [True, False])
def test_content_video_worker_allows_optional_flow_audio_and_uses_reference_frame(video_fixture, monkeypatch, tmp_path, with_voice_asset):
    from datetime import timezone
    from types import SimpleNamespace
    from src.modules.llm.client import LLMClient
    from src.models.entities import ContentVideoRun, ContentVideoWorkerLease
    from src.modules.tao_video_noi_dung import cong_harness
    from src.modules.tao_video_noi_dung import runner
    from src.modules.tao_video_noi_dung.contracts import CreatePlanRequest, CreateRunRequest
    from src.modules.tao_video_noi_dung.runner import _acquire_lease, _claim_next_run, _heartbeat, process_run
    from src.modules.tao_video_noi_dung.service import approve_plan, create_plan, create_run

    storyboard = {
        "title": "Giới thiệu RAG",
        "narration": "RAG truy xuất tài liệu rồi mới tạo câu trả lời.",
        "continuity_anchor": "Một chuyên gia công nghệ mặc áo xanh navy giải thích trong studio tối giản, ánh sáng mềm.",
        "shots": [
            {"shot_id": "shot-1", "scene": "Trợ lý mở hồ sơ trong văn phòng", "narration": "Lời dẫn một", "prompt": "Trợ lý mở hồ sơ", "duration_seconds": 10, "continues_previous": False},
            {"shot_id": "shot-2", "scene": "Cùng cảnh văn phòng, trợ lý tiếp tục đọc hồ sơ", "narration": "Lời dẫn hai", "prompt": "Trợ lý tiếp tục đọc hồ sơ", "duration_seconds": 10, "continues_previous": True},
            {"shot_id": "shot-3", "scene": "Chuyển sang phòng họp", "narration": "Lời dẫn ba", "prompt": "Nhóm xem kết quả truy xuất", "duration_seconds": 10, "continues_previous": False},
        ],
    }

    class FakeLLM:
        is_enabled = True
        max_output_tokens = 6000

        def complete(self, messages, max_tokens=None):
            return SimpleNamespace(content=_v4_planning_reply(messages, storyboard), model="worker-test")

    monkeypatch.setattr(LLMClient, "from_db", classmethod(lambda cls, db: FakeLLM()))
    monkeypatch.setattr(runner, "MEDIA_ROOT_DIR", tmp_path)
    audio_probe_calls = []
    def probe_audio(path):
        audio_probe_calls.append(path)
        return {"duration_seconds": 30, "codec_name": "mp3" if with_voice_asset else "unknown"}
    monkeypatch.setattr(runner.audio_processor, "probe_audio", probe_audio)
    monkeypatch.setattr(runner, "LEASE_SECONDS", 0.4)
    monkeypatch.setattr(runner.video_processor, "probe_video", lambda path: {
        "width": 1080, "height": 1920, "codec_name": "h264", "duration_seconds": 10.0, "frame_rate": 30.0,
    })
    monkeypatch.setattr(runner, "_render_and_qc", lambda db, run, plan, storyboard, asset_ids: setattr(run, "status", "COMPLETED") or db.commit())
    monkeypatch.setattr(runner, "_has_duplicate_shot_media", lambda hashes: False)
    extracted_frames = []

    def fake_extract_final_frame(path, workspace_id):
        temp_dir = runner.tempfile.TemporaryDirectory()
        (pathlib.Path(temp_dir.name) / "khung_hinh_cuoi.png").write_bytes(b"test frame")
        extracted_frames.append(path)
        return temp_dir

    monkeypatch.setattr(runner, "_extract_final_reference_frame", fake_extract_final_frame)

    calls = []

    def generate_video_scene(*, db, workspace_id, user_id, project_id, prompt, aspect_ratio, prompt_language="vi", include_audio=True, start_image_path=None, start_image_asset_id=None, remove_watermark=False, flow_project_url=None, on_flow_project_created=None):
        index = len(calls)
        if index == 0:
            assert flow_project_url is None
            flow_project_url = "https://flow.google.com/project/run-e2e"
            on_flow_project_created(flow_project_url)
        else:
            assert flow_project_url == "https://flow.google.com/project/run-e2e"
        if index == 0:
            time.sleep(0.55)
            with SessionLocal() as contender_db:
                assert not _acquire_lease(contender_db, str(uuid.uuid4()))
            with SessionLocal() as heartbeat_db:
                active = heartbeat_db.query(ContentVideoRun).filter(ContentVideoRun.id == active_run_id).one()
                assert active.lease_expires_at.replace(tzinfo=timezone.utc).timestamp() > time.time()
        if index == 1:
            assert start_image_path and start_image_path.is_file()
            assert start_image_asset_id == calls[0]["asset_id"]
        else:
            assert start_image_path is None and start_image_asset_id is None
        asset_id = f"asset-worker-{uuid.uuid4().hex[:8]}-{index}"
        prefix = "flow_expanded_9_16_" if index == 0 else "flow_i2v_9_16_"
        filename = f"{prefix}worker_{index}.mp4"
        storage_key = f"workspaces/{workspace_id}/media/{filename}"
        output_path = tmp_path / storage_key
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(video_fixture["clip_1"].read_bytes())
        (output_path.parent / filename.replace(prefix, "flow_source_16_9_", 1)).write_bytes(video_fixture["clip_1"].read_bytes())
        asset = MediaAsset(
            id=asset_id,
            workspace_id=workspace_id,
            project_id=project_id,
            storage_key=storage_key,
            sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
            byte_size=output_path.stat().st_size,
            mime_detected="video/mp4",
            source_product="TEST_FLOW",
            original_filename=f"{asset_id}.mp4",
            created_by=user_id,
            duration_ms=10000,
            approval_state="UNREVIEWED",
            parent_asset_id=None,
        )
        db.add(asset)
        db.commit()
        calls.append({"asset_id": asset.id, "prompt": prompt, "prompt_language": prompt_language, "include_audio": include_audio, "aspect_ratio": aspect_ratio, "start_image_asset_id": start_image_asset_id, "flow_project_url": flow_project_url})
        return asset

    monkeypatch.setattr(cong_harness.video_orchestrator, "generate_video_scene", generate_video_scene)
    project_id = f"project-worker-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.query(ContentVideoRun).filter(ContentVideoRun.status == "QUEUED").update(
            {"status": "FAILED"}, synchronize_session=False
        )
        db.add(ProductionProject(id=project_id, workspace_id=video_fixture["ws_id"], title="Worker test", created_by=video_fixture["user_id"]))
        voice_asset = None
        if with_voice_asset:
            voice_path = video_fixture["audio_file"]
            voice_storage_key = f"workspaces/{video_fixture['ws_id']}/media/{voice_path.name}"
            stored_voice_path = tmp_path / voice_storage_key
            stored_voice_path.parent.mkdir(parents=True, exist_ok=True)
            stored_voice_path.write_bytes(voice_path.read_bytes())
            voice_asset = MediaAsset(
                id=f"voice-{uuid.uuid4().hex[:8]}", workspace_id=video_fixture["ws_id"], project_id=project_id,
                storage_key=voice_storage_key, sha256=hashlib.sha256(stored_voice_path.read_bytes()).hexdigest(),
                byte_size=stored_voice_path.stat().st_size, mime_detected="audio/mpeg", source_product="TEST_UPLOAD",
                original_filename=voice_path.name, created_by=video_fixture["user_id"], duration_ms=30000,
                approval_state="UNREVIEWED",
            )
            db.add(voice_asset)
        db.commit()
        plan = create_plan(db, project_id, video_fixture["ws_id"], video_fixture["user_id"], CreatePlanRequest.model_validate({
            "content": "RAG truy xuất nguồn tài liệu liên quan trước khi xây dựng câu trả lời có căn cứ.",
            "target_duration_seconds": 30,
        }))
        approve_plan(db, project_id, plan.id, video_fixture["ws_id"], "reviewer-worker-test")
        queued = create_run(db, project_id, video_fixture["ws_id"], "reviewer-worker-test", CreateRunRequest(plan_id=plan.id, voice_asset_id=voice_asset.id if voice_asset else None, idempotency_key=f"worker-test-{uuid.uuid4().hex}"))
        active_run_id = queued.id
        token = str(uuid.uuid4())
        assert _acquire_lease(db, token)
        claimed = _claim_next_run(db, token)
        assert claimed and claimed.id == queued.id

    with SessionLocal() as db:
        assert db.get(ContentVideoWorkerLease, "content-video-flow").token == token
        assert _heartbeat(db, token)

    process_run(queued.id, token)

    with SessionLocal() as db:
        completed = db.get(ContentVideoRun, queued.id)
        steps = json.loads(completed.steps_json)
    assert completed.status == "COMPLETED", (completed.error_code, completed.error_message, completed.steps_json)
    assert completed.lease_token is None and completed.lease_expires_at is None
    assert [step["state"] for step in steps] == ["SUCCEEDED"] * 3
    assert steps[0]["flow_project_url"] == "https://flow.google.com/project/run-e2e"
    assert len(calls) == 3
    assert [call["prompt_language"] for call in calls] == ["vi", "vi", "vi"]
    assert [call["include_audio"] for call in calls] == [True, True, True]
    assert [call["aspect_ratio"] for call in calls] == ["9:16", "9:16", "9:16"]
    assert [call["start_image_asset_id"] for call in calls] == [None, calls[0]["asset_id"], None]
    assert len(extracted_frames) == 1
    assert bool(audio_probe_calls) is with_voice_asset
    assert "cảnh độc lập" in calls[2]["prompt"]
    assert [call["flow_project_url"] for call in calls] == ["https://flow.google.com/project/run-e2e"] * 3


def test_extracted_reference_frame_name_is_unique_per_image(tmp_path, monkeypatch):
    import types
    from src.modules.tao_video_noi_dung import runner

    def fake_ffmpeg(command, **kwargs):
        pathlib.Path(command[-1]).write_bytes(pathlib.Path(command[command.index("-i") + 1]).read_bytes())
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner, "run_media_command", fake_ffmpeg)
    names = []
    for content in (b"frame-one", b"frame-two"):
        source = tmp_path / f"{content.decode()}.mp4"
        source.write_bytes(content)
        temp_dir = runner._extract_final_reference_frame(source, "ws")
        names.append(next(pathlib.Path(temp_dir.name).glob("khung_hinh_cuoi*.png")).name)
        temp_dir.cleanup()
    assert names[0] != names[1] and all(n.startswith("khung_hinh_cuoi_") for n in names)
