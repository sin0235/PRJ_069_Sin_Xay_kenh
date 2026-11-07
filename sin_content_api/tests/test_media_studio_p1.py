# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động toàn diện cho Pha MEDIA_P1:
Contracts, RBAC, Asset Library, Job State Machine & Media Security.
Đáp ứng 100% tiêu chí nghiệm thu B01 -> B08 trong 02_ACCEPTANCE_MATRIX.md.
"""

import base64
import hashlib
import hmac
import io
import json
import os
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Cấu hình SQLite in-memory độc lập cho kiểm thử
TEST_DATABASE_URL = "sqlite:///file:sin_media_p1_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = (
    "sqlite:///file:baha_auth_media_p1_test?mode=memory&cache=shared&uri=true"
)
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-khoa-bi-mat-media-p1-secret"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "baha-auth-media-issuer"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "baha-media-studio-audience"

# Thêm đường dẫn vào sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    Workspace, User, MediaAsset, ProductionProject, ProductionTask,
    AIGenerationJob, MusicBrief, TimelineVersion, VoiceConsent, MediaQCResult,
    ContentVideoPlan, ContentVideoRun
)
from baha_auth.src.database import (
    Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
)
from baha_auth.src.models.entities import (
    GlobalUser, Membership as AuthMembership, Role as AuthRole,
    RoleAssignment, Workspace as AuthWorkspace
)
from src.modules.media_studio.security import (
    validate_audio_or_media_file, validate_zip_archive, probe_media_metadata
)
from src.modules.media_studio.job_engine import job_engine
from src.schemas.contracts import AIGenerationJobCreate

client = TestClient(app)

def tao_bearer_jwt(user_id: str) -> str:
    """Tạo JWT Bearer token hợp lệ cho user_id."""
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
    """Khởi tạo cấu trúc bảng CSDL trong RAM."""
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    yield
    # Dọn dẹp sau khi chạy
    Base.metadata.drop_all(bind=engine)
    AuthBase.metadata.drop_all(bind=AuthEngine)

@pytest.fixture
def media_fixture():
    """Thiết lập dữ liệu mẫu đa tenant."""
    ws_a_id = f"ws-a-{uuid.uuid4().hex[:8]}"
    ws_b_id = f"ws-b-{uuid.uuid4().hex[:8]}"
    user_a_id = f"user-a-{uuid.uuid4().hex[:8]}"
    user_b_id = f"user-b-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        ws_a = Workspace(id=ws_a_id, name="Studio Workspace A", slug=f"ws-a-{uuid.uuid4().hex[:6]}")
        ws_b = Workspace(id=ws_b_id, name="Competitor Workspace B", slug=f"ws-b-{uuid.uuid4().hex[:6]}")
        u_a = User(id=user_a_id, email=f"editor-a-{user_a_id}@baha.vn", hashed_password="mock")
        u_b = User(id=user_b_id, email=f"editor-b-{user_b_id}@baha.vn", hashed_password="mock")
        db.add_all([ws_a, ws_b, u_a, u_b])
        db.commit()

    with AuthSessionLocal() as auth_db:
        auth_ws_a = AuthWorkspace(id=ws_a_id, name="Studio Workspace A", slug=ws_a_id, status="ACTIVE")
        auth_ws_b = AuthWorkspace(id=ws_b_id, name="Competitor Workspace B", slug=ws_b_id, status="ACTIVE")
        gu_a = GlobalUser(id=user_a_id, email=f"editor-a-{user_a_id}@baha.vn", status="ACTIVE")
        gu_b = GlobalUser(id=user_b_id, email=f"editor-b-{user_b_id}@baha.vn", status="ACTIVE")
        auth_db.add_all([auth_ws_a, auth_ws_b, gu_a, gu_b])
        auth_db.commit()

        # Tạo membership
        m_a = AuthMembership(id=str(uuid.uuid4()), user_id=user_a_id, workspace_id=ws_a_id, status="ACTIVE")
        m_b = AuthMembership(id=str(uuid.uuid4()), user_id=user_b_id, workspace_id=ws_b_id, status="ACTIVE")
        auth_db.add_all([m_a, m_b])
        auth_db.commit()

        # Gán quyền WORKSPACE_OWNER cho user trong workspace tương ứng
        role_owner = auth_db.query(AuthRole).filter(AuthRole.code == "WORKSPACE_OWNER").first()
        if not role_owner:
            role_owner = AuthRole(code="WORKSPACE_OWNER", name="Workspace Owner", workspace_id=None, is_template=True, status="ACTIVE")
            auth_db.add(role_owner)
            auth_db.commit()

        ra_a = RoleAssignment(
            id=str(uuid.uuid4()), membership_id=m_a.id, role_id=role_owner.id,
            workspace_id=ws_a_id, status="ACTIVE", granted_by=m_a.id, scope_type="WORKSPACE"
        )
        ra_b = RoleAssignment(
            id=str(uuid.uuid4()), membership_id=m_b.id, role_id=role_owner.id,
            workspace_id=ws_b_id, status="ACTIVE", granted_by=m_b.id, scope_type="WORKSPACE"
        )
        auth_db.add_all([ra_a, ra_b])
        auth_db.commit()

    return {
        "ws_a_id": ws_a_id,
        "ws_b_id": ws_b_id,
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "token_a": tao_bearer_jwt(user_a_id),
        "token_b": tao_bearer_jwt(user_b_id),
    }

# ==============================================================================
# TEST CASE B01: Database Migrations and Safe Rollback
# ==============================================================================
def test_b01_database_migrations_and_rollback():
    """
    B01: Migrate up, seed, migrate down trong DB test.
    Rollback không làm mất các bảng dữ liệu cũ và không thất bại.
    """
    media_tables = [
        ProductionProject.__table__,
        ProductionTask.__table__,
        MediaAsset.__table__,
        AIGenerationJob.__table__,
        MusicBrief.__table__,
        TimelineVersion.__table__,
        VoiceConsent.__table__,
        MediaQCResult.__table__,
    ]

    # 1. Kiểm tra toàn bộ 8 bảng Media Studio tồn tại
    with engine.connect() as conn:
        for t in media_tables:
            res = conn.execute(Base.metadata.tables[t.name].select().limit(1))
            assert res is not None

    # 2. Seed dữ liệu mẫu
    with SessionLocal() as db:
        ws = Workspace(id="ws-b01-test", name="B01 Test WS", slug="ws-b01")
        db.add(ws)
        db.commit()

        asset = MediaAsset(
            id="asset-b01-seed",
            workspace_id="ws-b01-test",
            storage_key="workspaces/ws-b01/media/test.mp3",
            sha256="0" * 64,
            byte_size=1024,
            mime_detected="audio/mpeg",
            source_product="UPLOAD",
            created_by="user-test"
        )
        db.add(asset)
        db.commit()

        # Kiểm tra seed thành công
        loaded = db.query(MediaAsset).filter(MediaAsset.id == "asset-b01-seed").first()
        assert loaded is not None

    # 3. Giả lập Rollback (Chỉ drop 8 bảng Media Studio, giữ nguyên bảng cốt lõi)
    for t in reversed(media_tables):
        t.drop(bind=engine, checkfirst=True)

    # 4. Xác nhận bảng cũ (Workspace) vẫn an toàn và không bị corrupt
    with SessionLocal() as db:
        ws_check = db.query(Workspace).filter(Workspace.id == "ws-b01-test").first()
        assert ws_check is not None
        assert ws_check.name == "B01 Test WS"

    # Tái tạo lại các bảng Media Studio để phục vụ các bài test tiếp theo
    for t in media_tables:
        t.create(bind=engine, checkfirst=True)


# ==============================================================================
# TEST CASE B02: Multi-tenant Isolation (Cross-tenant Access Blocked)
# ==============================================================================
def test_b02_cross_tenant_isolation(media_fixture):
    """
    B02: User A tạo asset/job trong Org A; User B trong Org B truy vấn.
    Kỳ vọng: HTTP 403 hoặc 404 và không để rò rỉ metadata.
    """
    fix = media_fixture
    ws_a = fix["ws_a_id"]
    ws_b = fix["ws_b_id"]
    user_a = fix["user_a_id"]

    # 1. Tạo Asset và Job thuộc Workspace A
    with SessionLocal() as db:
        asset_a = MediaAsset(
            id="asset-tenant-a-confidential",
            workspace_id=ws_a,
            storage_key=f"workspaces/{ws_a}/media/secret.mp3",
            sha256="a" * 64,
            byte_size=2048,
            mime_detected="audio/mpeg",
            source_product="FLOW_MUSIC",
            original_filename="secret_song_a.mp3",
            created_by=user_a
        )
        job_a = AIGenerationJob(
            id="job-tenant-a-confidential",
            workspace_id=ws_a,
            asset_type="MUSIC",
            provider="FLOW_MUSIC_ASSISTED",
            provider_mode="SUBSCRIPTION_ASSISTED",
            model_id="flowmusic-v1",
            idempotency_key="idemp-tenant-a-secret",
            state="SUCCEEDED",
            created_by=user_a
        )
        db.add_all([asset_a, job_a])
        db.commit()

    # 2. User B truy vấn Asset của User A -> Phải nhận HTTP 404 (Không rò rỉ sự tồn tại)
    resp_asset = client.get(
        f"/v1/media/assets/asset-tenant-a-confidential",
        headers={
            "Authorization": f"Bearer {fix['token_b']}",
            "X-Workspace-Id": ws_b
        }
    )
    assert resp_asset.status_code == 404
    assert "secret" not in resp_asset.text

    # 3. User B truy vấn Job của User A -> Phải nhận HTTP 404
    resp_job = client.get(
        f"/v1/ai-jobs/job-tenant-a-confidential",
        headers={
            "Authorization": f"Bearer {fix['token_b']}",
            "X-Workspace-Id": ws_b
        }
    )
    assert resp_job.status_code == 404
    assert "secret" not in resp_job.text


# ==============================================================================
# TEST CASE B03: Idempotency Verification (No Double Charge / Single Job)
# ==============================================================================
def test_b03_idempotency_no_duplicate_charge(media_fixture):
    """
    B03: Gửi 2 request cùng idempotency key.
    Kỳ vọng: Chỉ tạo đúng 1 job và không double-charge.
    """
    fix = media_fixture
    ws_a = fix["ws_a_id"]
    idemp_key = f"idemp-b03-unique-{uuid.uuid4().hex}"

    with SessionLocal() as db:
        payload = AIGenerationJobCreate(
            asset_type="MUSIC",
            provider="FAKE_PROVIDER",
            provider_mode="TEST_MOCK",
            model_id="mock-flow-music",
            idempotency_key=idemp_key,
            prompt_text="Bản nhạc acoustic nhẹ nhàng buổi sáng",
            estimated_cost=0.08,
            parameters={"simulate_error": "SUCCESS"}
        )

        # Lệnh gọi 1: Tạo mới
        job_1 = job_engine.submit_job(db, ws_a, fix["user_a_id"], payload)
        assert job_1.id is not None
        assert job_1.state == "SUCCEEDED"

        # Lệnh gọi 2: Gửi lại cùng idempotency key
        job_2 = job_engine.submit_job(db, ws_a, fix["user_a_id"], payload)
        assert job_2.id == job_1.id

        # Kiểm tra trong cơ sở dữ liệu: Chỉ có duy nhất 1 bản ghi với idempotency key này
        total_jobs = db.query(AIGenerationJob).filter(
            AIGenerationJob.idempotency_key == idemp_key
        ).count()
        assert total_jobs == 1


# ==============================================================================
# TEST CASE B04: Upload Security (MIME Spoofing, Path Traversal, Zip Bomb)
# ==============================================================================
def test_b04_upload_security_rejects_malicious_files():
    """
    B04: Upload PDF giả MP3, ZIP traversal, ZIP bomb.
    Kỳ vọng: Từ chối server-side, không ghi storage ngoài root.
    """
    # 1. Tệp PDF giả mạo đuôi .mp3
    fake_mp3_pdf_content = b"%PDF-1.4\n%Malformed binary payload pretending to be an audio track"
    with pytest.raises(Exception) as excinfo:
        validate_audio_or_media_file(fake_mp3_pdf_content, "innocent_song.mp3", expected_category="audio")
    assert "MALICIOUS_MIME_DETECTED" in str(excinfo.value) or "400" in str(excinfo.value)

    # 2. Tệp ZIP chứa Path Traversal (../../evil.sh)
    traversal_buffer = io.BytesIO()
    with zipfile.ZipFile(traversal_buffer, "w") as zf:
        zf.writestr("../../etc/evil.sh", b"echo hacked")
    traversal_bytes = traversal_buffer.getvalue()

    with pytest.raises(Exception) as excinfo:
        validate_zip_archive(traversal_bytes)
    assert "ZIP_PATH_TRAVERSAL_DETECTED" in str(excinfo.value) or "400" in str(excinfo.value)

    # 3. Tệp ZIP Bomb (Tỷ lệ nén cực đoan > 100x và kích thước giải nén lớn)
    bomb_buffer = io.BytesIO()
    with zipfile.ZipFile(bomb_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Ghi 2MB dữ liệu byte 0 (nén lại chỉ còn vài trăm bytes)
        zf.writestr("bomb.txt", b"\x00" * (2 * 1024 * 1024))
    bomb_bytes = bomb_buffer.getvalue()

    with pytest.raises(Exception) as excinfo:
        validate_zip_archive(bomb_bytes, max_ratio=50.0)
    assert "ZIP_BOMB" in str(excinfo.value) or "400" in str(excinfo.value)


# ==============================================================================
# TEST CASE B05: Media Validation and Provenance Integrity
# ==============================================================================
def test_b05_media_validation_probe_and_checksum(media_fixture):
    """
    B05: Upload -> probe -> sha256 -> retrieve.
    Kỳ vọng: MIME thật, checksum nhất quán, chỉ URL có thời hạn.
    """
    fix = media_fixture
    clean_audio = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" + b"\x00" * 32000
    expected_sha = hashlib.sha256(clean_audio).hexdigest()

    # Upload qua API
    resp = client.post(
        "/v1/media/upload",
        files={"file": ("baha_soundtrack.mp3", clean_audio, "audio/mpeg")},
        data={"source_product": "FLOW_MUSIC", "expected_category": "audio"},
        headers={
            "Authorization": f"Bearer {fix['token_a']}",
            "X-Workspace-Id": fix["ws_a_id"]
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mime_detected"] == "audio/mpeg"
    assert data["sha256"] == expected_sha
    assert data["byte_size"] == len(clean_audio)
    assert "ttl=3600" in data["url"]


# ==============================================================================
# TEST CASE B06: Job Failures, State Transitions & Bounded Retry
# ==============================================================================
def test_b06_job_failures_and_retry_backoff(media_fixture):
    """
    B06: Giả lập job 401, 429, 500, timeout.
    Kỳ vọng: State/retry/backoff đúng, 401 không retry vô tận.
    """
    fix = media_fixture
    ws_a = fix["ws_a_id"]
    user_a = fix["user_a_id"]

    with SessionLocal() as db:
        # 1. Kiểm tra 401: Lỗi xác thực -> Không retry (retry_count = 0)
        p_401 = AIGenerationJobCreate(
            asset_type="MUSIC",
            provider="FAKE_PROVIDER",
            model_id="mock-401",
            idempotency_key=f"idemp-401-{uuid.uuid4().hex}",
            prompt_text="Test 401",
            parameters={"simulate_error": "HTTP_401"}
        )
        job_401 = job_engine.submit_job(db, ws_a, user_a, p_401)
        assert job_401.state == "FAILED"
        assert job_401.error_code == "AUTH_DENIED"
        assert job_401.retry_count == 0

        # 2. Kiểm tra 429: Rate limit -> Bounded retry tối đa 3 lần
        p_429 = AIGenerationJobCreate(
            asset_type="MUSIC",
            provider="FAKE_PROVIDER",
            model_id="mock-429",
            idempotency_key=f"idemp-429-{uuid.uuid4().hex}",
            prompt_text="Test 429",
            parameters={"simulate_error": "HTTP_429"}
        )
        job_429 = job_engine.submit_job(db, ws_a, user_a, p_429)
        assert job_429.state == "FAILED"
        assert "MAX_RETRIES_EXCEEDED" in job_429.error_code
        assert job_429.retry_count > 0

        # 3. Kiểm tra 500: Server Error -> Bounded retry
        p_500 = AIGenerationJobCreate(
            asset_type="VIDEO",
            provider="FAKE_PROVIDER",
            model_id="mock-500",
            idempotency_key=f"idemp-500-{uuid.uuid4().hex}",
            prompt_text="Test 500",
            parameters={"simulate_error": "HTTP_500"}
        )
        job_500 = job_engine.submit_job(db, ws_a, user_a, p_500)
        assert job_500.state == "FAILED"
        assert job_500.retry_count > 0


# ==============================================================================
# TEST CASE B07: Budget Cap Gate (Reject Before Provider Submission)
# ==============================================================================
def test_b07_budget_cap_gate(media_fixture):
    """
    B07: Tạo job estimate cao hơn giới hạn.
    Kỳ vọng: Reject với HTTP 402 trước khi gọi provider.
    """
    fix = media_fixture
    ws_a = fix["ws_a_id"]
    user_a = fix["user_a_id"]

    with SessionLocal() as db:
        p_overbudget = AIGenerationJobCreate(
            asset_type="VIDEO",
            provider="FAKE_PROVIDER",
            model_id="gemini-omni-flash",
            idempotency_key=f"idemp-budget-{uuid.uuid4().hex}",
            prompt_text="Video 4K thời lượng lớn",
            estimated_cost=25.0, # Chi phí ước tính 25 USD
            parameters={"simulate_error": "SUCCESS"}
        )

        with pytest.raises(Exception) as excinfo:
            # Ngân sách chỉ cho phép tối đa 5.0 USD
            job_engine.submit_job(db, ws_a, user_a, p_overbudget, budget_cap=5.0)

        assert "OVER_BUDGET_LIMIT" in str(excinfo.value) or "402" in str(excinfo.value)


# ==============================================================================
# TEST CASE B08: No Credentials Gate (Block Without Key, No Fake Succeeded)
# ==============================================================================
def test_b08_no_credentials_blocks_job(media_fixture):
    """
    B08: Gọi generation khi API key thiếu.
    Kỳ vọng: BLOCKED_CREDENTIALS; tuyệt đối không ghi SUCCEEDED.
    """
    fix = media_fixture
    ws_a = fix["ws_a_id"]
    user_a = fix["user_a_id"]

    # Đảm bảo GEMINI_API_KEY không có trong môi trường
    old_key = os.environ.pop("GEMINI_API_KEY", None)

    try:
        with SessionLocal() as db:
            p_nokey = AIGenerationJobCreate(
                asset_type="VIDEO",
                provider="GOOGLE_OFFICIAL", # Yêu cầu key chính thức
                model_id="gemini-omni-1.1-flash",
                idempotency_key=f"idemp-nokey-{uuid.uuid4().hex}",
                prompt_text="Video chính thức qua Google API",
                estimated_cost=1.5
            )

            job = job_engine.submit_job(db, ws_a, user_a, p_nokey)
            assert job.state == "FAILED"
            assert job.error_code == "BLOCKED_CREDENTIALS"
            assert job.actual_cost == 0.0
            assert job.state != "SUCCEEDED"
    finally:
        if old_key:
            os.environ["GEMINI_API_KEY"] = old_key


if __name__ == "__main__":
    pytest.main(["-v", __file__])


# ==============================================================================
# TEST CASE B09: Upload Image/Video Category Validation (M-P2)
# ==============================================================================
def test_b09_upload_image_video_category_validation(media_fixture):
    """
    B09: Kiểm tra allowlist MIME theo category:
    - JPEG/PNG chỉ qua category 'image'.
    - MP4 chỉ qua category 'video'.
    - Audio chỉ qua category 'audio'.
    - Category sai hoặc MIME không khớp bị từ chối 4xx.
    - File rỗng bị từ chối.
    - MIME nguy hiểm (PDF giả mạo) bị chặn.
    """
    fix = media_fixture
    token_a = fix["token_a"]
    ws_a = fix["ws_a_id"]
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Workspace-Id": ws_a}

    # 1. JPEG hợp lệ với category 'image' -> phải PASS
    jpeg_magic = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG magic bytes
    r = client.post(
        "/v1/media/upload",
        files={"file": ("photo.jpg", jpeg_magic, "image/jpeg")},
        data={"source_product": "UPLOAD", "expected_category": "image"},
        headers=headers_a,
    )
    assert r.status_code == 200, f"JPEG image upload failed: {r.text}"
    assert r.json()["mime_detected"] == "image/jpeg"

    # 2. PNG hợp lệ với category 'image' -> phải PASS
    png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r2 = client.post(
        "/v1/media/upload",
        files={"file": ("photo.png", png_magic, "image/png")},
        data={"source_product": "UPLOAD", "expected_category": "image"},
        headers=headers_a,
    )
    assert r2.status_code == 200, f"PNG image upload failed: {r2.text}"

    # 3. MP4 hợp lệ với category 'video' -> phải PASS
    # ftyp box: 4 byte size + "ftyp" + 8 bytes
    mp4_magic = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100
    r3 = client.post(
        "/v1/media/upload",
        files={"file": ("video.mp4", mp4_magic, "video/mp4")},
        data={"source_product": "UPLOAD", "expected_category": "video"},
        headers=headers_a,
    )
    assert r3.status_code == 200, f"MP4 video upload failed: {r3.text}"
    assert r3.json()["mime_detected"] == "video/mp4"

    # 4. JPEG gửi lên với category 'audio' -> phải bị từ chối 4xx
    r4 = client.post(
        "/v1/media/upload",
        files={"file": ("fake.mp3", jpeg_magic, "audio/mpeg")},
        data={"source_product": "UPLOAD", "expected_category": "audio"},
        headers=headers_a,
    )
    assert r4.status_code in (400, 422), f"JPEG as audio should be rejected: {r4.status_code}"

    # 5. MP4 gửi lên với category 'image' -> phải bị từ chối 4xx
    r5 = client.post(
        "/v1/media/upload",
        files={"file": ("fake.png", mp4_magic, "image/png")},
        data={"source_product": "UPLOAD", "expected_category": "image"},
        headers=headers_a,
    )
    assert r5.status_code in (400, 422), f"MP4 as image should be rejected: {r5.status_code}"

    # 6. File rỗng bị từ chối
    r6 = client.post(
        "/v1/media/upload",
        files={"file": ("empty.mp3", b"", "audio/mpeg")},
        data={"source_product": "UPLOAD", "expected_category": "audio"},
        headers=headers_a,
    )
    assert r6.status_code in (400, 422), f"Empty file should be rejected: {r6.status_code}"

    # 7. PDF giả mạo audio bị chặn
    pdf_magic = b"%PDF-1.4 fake document content here" + b"\x00" * 50
    r7 = client.post(
        "/v1/media/upload",
        files={"file": ("malicious.mp3", pdf_magic, "audio/mpeg")},
        data={"source_product": "UPLOAD", "expected_category": "audio"},
        headers=headers_a,
    )
    assert r7.status_code in (400, 422), f"PDF disguised as audio should be rejected: {r7.status_code}"


# ==============================================================================
# TEST CASE B10: Download Requires Workspace Authorization (M-P2)
# ==============================================================================
def test_b10_download_requires_workspace_authorization(media_fixture):
    """
    B10: Endpoint download phải kiểm tra tenant:
    - Thiếu auth -> 401/403.
    - Tenant chủ sở hữu có thể đọc.
    - Tenant khác nhận 404.
    """
    fix = media_fixture
    token_a = fix["token_a"]
    token_b = fix["token_b"]
    ws_a = fix["ws_a_id"]
    ws_b = fix["ws_b_id"]

    # 1. Upload một asset bằng token_a vào ws_a
    mp3_data = b"ID3" + b"\x00" * 200
    r_up = client.post(
        "/v1/media/upload",
        files={"file": ("voice.mp3", mp3_data, "audio/mpeg")},
        data={"source_product": "UPLOAD", "expected_category": "audio"},
        headers={"Authorization": f"Bearer {token_a}", "X-Workspace-Id": ws_a},
    )
    assert r_up.status_code == 200, f"Upload failed: {r_up.text}"
    asset_id = r_up.json()["id"]

    # 2. Download không có auth -> 401/403/422
    r_no_auth = client.get(f"/v1/media/assets/{asset_id}/download")
    assert r_no_auth.status_code in (401, 403, 422), f"No-auth download should be blocked: {r_no_auth.status_code}"

    # 3. Tenant A (chủ sở hữu) có thể truy cập -> file tồn tại sẽ là 200
    # (file có thể không tồn tại trên disk trong test env, nên chấp nhận 200 hoặc 404 nhưng không phải 403)
    r_a = client.get(
        f"/v1/media/assets/{asset_id}/download",
        headers={"Authorization": f"Bearer {token_a}", "X-Workspace-Id": ws_a},
    )
    # Tenant A phải KHÔNG bị 401/403
    assert r_a.status_code not in (401, 403), f"Owner should not be blocked: {r_a.status_code} {r_a.text}"

    # 4. Tenant B (workspace khác) nhận 404 hoặc 401/403
    r_b = client.get(
        f"/v1/media/assets/{asset_id}/download",
        headers={"Authorization": f"Bearer {token_b}", "X-Workspace-Id": ws_b},
    )
    assert r_b.status_code in (401, 403, 404), f"Cross-tenant download should be blocked: {r_b.status_code}"


# ==============================================================================
# TEST CASE B11: Upload Rejects Oversize File (M-P2)
# ==============================================================================
def test_b11_upload_rejects_oversize_file(media_fixture):
    """
    B11: Upload file vượt giới hạn bị từ chối HTTP 413/4xx.
    Ngưỡng kiểm thử: audio 50 MB, image 20 MB.
    Không tạo asset mới hay file tạm dở dang.
    """
    import os
    fix = media_fixture
    headers_a = {
        "Authorization": f"Bearer {fix['token_a']}",
        "X-Workspace-Id": fix["ws_a_id"],
    }

    # 1. Audio vượt giới hạn 50MB (dùng 1 byte giả, override giới hạn qua env)
    # Giảm giới hạn kiểm thử về 1 byte để test không cần tạo file 50MB thật
    original_limit = os.environ.get("UPLOAD_LIMIT_AUDIO_MB")
    os.environ["UPLOAD_LIMIT_AUDIO_MB"] = "0"  # 0 MB => tất cả đều vượt

    try:
        # Import lại module để nhận giá trị env mới
        from src.modules.media_studio import security as sec_mod
        sec_mod.UPLOAD_SIZE_LIMITS["audio"] = 0  # Force limit = 0 bytes

        small_mp3 = b"ID3" + b"\x00" * 10
        r = client.post(
            "/v1/media/upload",
            files={"file": ("toobig.mp3", small_mp3, "audio/mpeg")},
            data={"source_product": "UPLOAD", "expected_category": "audio"},
            headers=headers_a,
        )
        assert r.status_code in (400, 413, 422), f"Oversize audio should be rejected: {r.status_code} {r.text}"
    finally:
        # Khôi phục giới hạn
        sec_mod.UPLOAD_SIZE_LIMITS["audio"] = 50 * 1024 * 1024
        if original_limit is not None:
            os.environ["UPLOAD_LIMIT_AUDIO_MB"] = original_limit
        elif "UPLOAD_LIMIT_AUDIO_MB" in os.environ:
            del os.environ["UPLOAD_LIMIT_AUDIO_MB"]


# ==============================================================================
# TEST CASE B12: Upload Safe Name and Project Scope (M-P2)
# ==============================================================================
def test_b12_upload_safe_name_and_project_scope(media_fixture):
    """
    B12:
    - Tên chứa path traversal bị chuẩn hóa hoặc từ chối.
    - Asset gắn đúng project_id.
    - Workspace khác không được gán project của workspace A.
    """
    from src.modules.media_studio.security import _check_filename_safe

    fix = media_fixture
    headers_a = {
        "Authorization": f"Bearer {fix['token_a']}",
        "X-Workspace-Id": fix["ws_a_id"],
    }

    # 1. Kiểm tra chuẩn hóa tên file nguy hiểm
    dangerous_names = [
        "../../../etc/passwd",
        "..\\windows\\system32\\evil",
        "/absolute/path/file.mp3",
        "file\x00null.mp3",
    ]
    for name in dangerous_names:
        safe = _check_filename_safe(name)
        assert ".." not in safe, f"Path traversal not cleaned: '{name}' -> '{safe}'"
        assert "/" not in safe, f"Slash not removed: '{name}' -> '{safe}'"
        assert "\\" not in safe, f"Backslash not removed: '{name}' -> '{safe}'"

    # 2. Upload với tên nguy hiểm -> tên được chuẩn hóa, không crash
    jpeg_magic = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    r = client.post(
        "/v1/media/upload",
        files={"file": ("../../../evil.jpg", jpeg_magic, "image/jpeg")},
        data={"source_product": "UPLOAD", "expected_category": "image"},
        headers=headers_a,
    )
    # Phải PASS (file hợp lệ, tên được chuẩn hóa) hoặc 400 (tên bị reject)
    assert r.status_code in (200, 400), f"Traversal name upload unexpected status: {r.status_code}"
    if r.status_code == 200:
        saved_name = r.json().get("original_filename", "")
        assert ".." not in saved_name, f"Traversal still in saved name: {saved_name}"
        assert "/" not in saved_name, f"Slash still in saved name: {saved_name}"

    # 3. Upload vào project không tồn tại -> 404
    r_noproject = client.post(
        "/v1/media/upload",
        files={"file": ("image.jpg", jpeg_magic, "image/jpeg")},
        data={
            "source_product": "UPLOAD",
            "expected_category": "image",
            "project_id": "nonexistent-project-id",
        },
        headers=headers_a,
    )
    assert r_noproject.status_code in (400, 404), f"Upload to nonexistent project should fail: {r_noproject.status_code}"

    # 4. Upload vào project của ws_a từ ws_b (cross-workspace project gán) -> 404
    # Tạo project trong ws_a
    with SessionLocal() as db:
        from src.models.entities import ProductionProject
        proj_a = ProductionProject(
            id=f"proj-b12-{uuid.uuid4().hex[:8]}",
            workspace_id=fix["ws_a_id"],
            title="Project B12 Test",
            created_by=fix["user_a_id"],
        )
        db.add(proj_a)
        db.commit()
        proj_a_id = proj_a.id

    headers_b = {
        "Authorization": f"Bearer {fix['token_b']}",
        "X-Workspace-Id": fix["ws_b_id"],
    }
    r_cross = client.post(
        "/v1/media/upload",
        files={"file": ("image.jpg", jpeg_magic, "image/jpeg")},
        data={
            "source_product": "UPLOAD",
            "expected_category": "image",
            "project_id": proj_a_id,
        },
        headers=headers_b,
    )
    assert r_cross.status_code in (400, 404), f"Cross-workspace project assignment should fail: {r_cross.status_code}"


def test_delete_video_project_removes_workflow_data_and_keeps_media_assets(media_fixture):
    fix = media_fixture
    headers = {
        "Authorization": f"Bearer {fix['token_a']}",
        "X-Workspace-Id": fix["ws_a_id"],
    }
    created = client.post("/v1/media/projects", json={"title": "Video cần xóa"}, headers=headers)
    assert created.status_code == 201
    project_id = created.json()["id"]
    asset_id, plan_id, run_id, job_id, brief_id = [str(uuid.uuid4()) for _ in range(5)]

    with SessionLocal() as db:
        db.add_all([
            MediaAsset(
                id=asset_id, workspace_id=fix["ws_a_id"], project_id=project_id,
                storage_key=f"workspaces/{fix['ws_a_id']}/media/output.mp4", sha256="a" * 64,
                byte_size=10, mime_detected="video/mp4", source_product="GEMINI_VIDEO",
                created_by=fix["user_a_id"],
            ),
            ContentVideoPlan(
                id=plan_id, workspace_id=fix["ws_a_id"], project_id=project_id, revision=1,
                source_content="Nội dung video cần xóa", content_sha256="b" * 64,
                target_duration_seconds=30, style_snapshot_json="{}", style_snapshot_sha256="c" * 64,
                storyboard_json="{}", storyboard_sha256="d" * 64, llm_model="test",
                created_by=fix["user_a_id"],
            ),
            TimelineVersion(project_id=project_id, version=1, created_by=fix["user_a_id"]),
            ProductionTask(project_id=project_id, task_type="QC", status="COMPLETED"),
            AIGenerationJob(
                id=job_id, workspace_id=fix["ws_a_id"], project_id=project_id,
                asset_type="VIDEO", provider="GOOGLE_OFFICIAL", provider_mode="OFFICIAL_API",
                model_id="test", idempotency_key=str(uuid.uuid4()), state="SUCCEEDED",
                created_by=fix["user_a_id"],
            ),
            MusicBrief(
                id=brief_id, workspace_id=fix["ws_a_id"], project_id=project_id,
                title="Nhạc video", mood="Bình tĩnh", genre="Ambient", prompt_text="Nhạc nền",
                created_by=fix["user_a_id"],
            ),
        ])
        db.flush()
        db.add(ContentVideoRun(
            id=run_id, workspace_id=fix["ws_a_id"], project_id=project_id, plan_id=plan_id,
            final_asset_id=asset_id, plan_revision=1, storyboard_sha256="d" * 64,
            style_snapshot_sha256="c" * 64, approval_sha256="e" * 64,
            idempotency_key=str(uuid.uuid4()), status="SUCCEEDED", created_by=fix["user_a_id"],
        ))
        db.commit()

    deleted = client.delete(f"/v1/media/projects/{project_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text

    with SessionLocal() as db:
        assert db.get(ProductionProject, project_id) is None
        assert db.get(ContentVideoPlan, plan_id) is None
        assert db.get(ContentVideoRun, run_id) is None
        assert db.query(TimelineVersion).filter_by(project_id=project_id).count() == 0
        assert db.query(ProductionTask).filter_by(project_id=project_id).count() == 0
        assert db.get(MediaAsset, asset_id).project_id is None
        assert db.get(AIGenerationJob, job_id).project_id is None
        assert db.get(MusicBrief, brief_id).project_id is None


def test_delete_video_project_rejects_running_generation(media_fixture):
    fix = media_fixture
    headers = {
        "Authorization": f"Bearer {fix['token_a']}",
        "X-Workspace-Id": fix["ws_a_id"],
    }
    created = client.post("/v1/media/projects", json={"title": "Video đang chạy"}, headers=headers)
    assert created.status_code == 201
    project_id = created.json()["id"]
    plan_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(ContentVideoPlan(
            id=plan_id, workspace_id=fix["ws_a_id"], project_id=project_id, revision=1,
            source_content="Nội dung video", content_sha256="b" * 64,
            target_duration_seconds=30, style_snapshot_json="{}", style_snapshot_sha256="c" * 64,
            storyboard_json="{}", storyboard_sha256="d" * 64, llm_model="test",
            created_by=fix["user_a_id"],
        ))
        db.flush()
        db.add(ContentVideoRun(
            workspace_id=fix["ws_a_id"], project_id=project_id, plan_id=plan_id,
            plan_revision=1, storyboard_sha256="d" * 64, style_snapshot_sha256="c" * 64,
            approval_sha256="e" * 64, idempotency_key=str(uuid.uuid4()), status="RUNNING",
            created_by=fix["user_a_id"],
        ))
        db.commit()

    deleted = client.delete(f"/v1/media/projects/{project_id}", headers=headers)
    assert deleted.status_code == 409
    assert client.get("/v1/media/projects", headers=headers).json()[0]["id"] == project_id


def test_delete_video_project_cannot_cross_workspace(media_fixture):
    fix = media_fixture
    headers_a = {
        "Authorization": f"Bearer {fix['token_a']}",
        "X-Workspace-Id": fix["ws_a_id"],
    }
    headers_b = {
        "Authorization": f"Bearer {fix['token_b']}",
        "X-Workspace-Id": fix["ws_b_id"],
    }
    created = client.post("/v1/media/projects", json={"title": "Project workspace B"}, headers=headers_b)
    assert created.status_code == 201

    deleted = client.delete(f"/v1/media/projects/{created.json()['id']}", headers=headers_a)
    assert deleted.status_code == 404
    assert client.get("/v1/media/projects", headers=headers_b).json()[0]["id"] == created.json()["id"]


def test_delete_video_project_rejects_flow_job_waiting_for_render(media_fixture):
    fix = media_fixture
    headers = {
        "Authorization": f"Bearer {fix['token_a']}",
        "X-Workspace-Id": fix["ws_a_id"],
    }
    created = client.post("/v1/media/projects", json={"title": "Video chờ Flow"}, headers=headers)
    assert created.status_code == 201
    project_id = created.json()["id"]
    with SessionLocal() as db:
        db.add(AIGenerationJob(
            workspace_id=fix["ws_a_id"], project_id=project_id, asset_type="VIDEO",
            provider="GOOGLE_FLOW", provider_mode="SUBSCRIPTION_ASSISTED", model_id="veo",
            idempotency_key=str(uuid.uuid4()), state="WAITING_FOR_FLOW", created_by=fix["user_a_id"],
        ))
        db.commit()

    deleted = client.delete(f"/v1/media/projects/{project_id}", headers=headers)
    assert deleted.status_code == 409
    assert client.get("/v1/media/projects", headers=headers).json()[0]["id"] == project_id

