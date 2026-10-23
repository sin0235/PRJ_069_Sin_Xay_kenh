"""
Test Suite for Phase P04: Ingestion, Provenance & Snapshots
Tests: T040, T041, T042, T043, T044
Strict Ground Truth Verification.
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.entities import (
    Workspace,
    User,
    Membership,
    SourceRecord,
    SourceObservation,
    MetricSnapshot,
    AuditEvent,
)
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from tests.conftest import tao_bearer_token, setup_test_auth_user

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_p04_env():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    db = SessionLocal()
    auth_db = AuthSessionLocal()
    
    ws = Workspace(id=str(uuid.uuid4()), name="Sin Ingestion Test WS", slug=f"ingest-{uuid.uuid4().hex[:6]}")
    user_admin = User(id=str(uuid.uuid4()), email=f"admin_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Admin User", hashed_password="mock")
    user_editor = User(id=str(uuid.uuid4()), email=f"editor_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Editor User", hashed_password="mock")
    user_viewer = User(id=str(uuid.uuid4()), email=f"viewer_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Viewer User", hashed_password="mock")
    
    db.add_all([ws, user_admin, user_editor, user_viewer])
    db.commit()
    
    m_admin = Membership(workspace_id=ws.id, user_id=user_admin.id, role="admin")
    m_editor = Membership(workspace_id=ws.id, user_id=user_editor.id, role="editor")
    m_viewer = Membership(workspace_id=ws.id, user_id=user_viewer.id, role="viewer")
    db.add_all([m_admin, m_editor, m_viewer])
    db.commit()

    # Dong bo user vao kho Baha Auth
    setup_test_auth_user(auth_db, ws.id, user_admin.id, user_admin.email, "WORKSPACE_OWNER")
    setup_test_auth_user(auth_db, ws.id, user_editor.id, user_editor.email, "WORKSPACE_OWNER")
    setup_test_auth_user(auth_db, ws.id, user_viewer.id, user_viewer.email, "WORKSPACE_OWNER")

    token_admin = tao_bearer_token(user_admin.id)
    token_editor = tao_bearer_token(user_editor.id)
    token_viewer = tao_bearer_token(user_viewer.id)

    admin_headers = {
        "Authorization": f"Bearer {token_admin}",
        "X-Workspace-Id": ws.id,
        "X-User-Id": user_admin.id,
    }
    editor_headers = {
        "Authorization": f"Bearer {token_editor}",
        "X-Workspace-Id": ws.id,
        "X-User-Id": user_editor.id,
    }
    viewer_headers = {
        "Authorization": f"Bearer {token_viewer}",
        "X-Workspace-Id": ws.id,
        "X-User-Id": user_viewer.id,
    }
    
    ctx = {
        "ws_id": ws.id,
        "admin_id": user_admin.id,
        "editor_id": user_editor.id,
        "viewer_id": user_viewer.id,
        "admin_headers": admin_headers,
        "editor_headers": editor_headers,
        "viewer_headers": viewer_headers,
        "headers": editor_headers,
    }
    db.close()
    auth_db.close()
    yield ctx

def test_t040_idempotent_ingestion_no_duplicates(setup_p04_env):
    """
    T040: Ingest same batch twice with same observation IDs ->
    identical unique source count and snapshots; no duplicates.
    """
    headers = setup_p04_env["editor_headers"]

    batch_payload = {
        "items": [
            {
                "observation_id": "obs-001",
                "external_id": "post-vid-101",
                "canonical_url": "https://tiktok.com/@brand/video/101",
                "title": "Hop com giu nhiet locknlock",
                "caption": "Review chi tiet sau 6 thang su dung",
                "provider_id": "customer_import",
                "view_count": 5000,
            },
            {
                "observation_id": "obs-002",
                "external_id": "post-vid-102",
                "canonical_url": "https://tiktok.com/@brand/video/102",
                "title": "Binh giu nhiet inox 316",
                "caption": "Kiem tra kha nang giu lanh 24h",
                "provider_id": "customer_import",
                "view_count": 8200,
            },
        ],
        "is_production": False,
    }

    # First Ingestion
    res1 = client.post("/v1/ingestion/batch", json=batch_payload, headers=headers)
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["created_sources"] == 2
    assert data1["created_observations"] == 2
    assert data1["deduplicated_observations"] == 0

    # Second Ingestion (Exact same batch with same observation IDs)
    res2 = client.post("/v1/ingestion/batch", json=batch_payload, headers=headers)
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["created_sources"] == 0
    assert data2["created_observations"] == 0
    assert data2["deduplicated_observations"] == 2 # 100% deduplicated!

    # Verify DB counts: exactly 2 SourceRecords and 2 MetricSnapshots
    db = SessionLocal()
    records = db.query(SourceRecord).filter(SourceRecord.workspace_id == setup_p04_env["ws_id"]).all()
    assert len(records) == 2

    snapshots = db.query(MetricSnapshot).join(SourceRecord).filter(SourceRecord.workspace_id == setup_p04_env["ws_id"]).all()
    assert len(snapshots) == 2
    db.close()

def test_t041_missing_view_count_null_never_zero(setup_p04_env):
    """
    T041: Missing view count must be stored as NULL / None, NEVER zero unless observed zero.
    """
    headers = setup_p04_env["editor_headers"]

    batch_payload = {
        "items": [
            {
                "observation_id": "obs-missing-vc",
                "external_id": "post-vid-201",
                "canonical_url": "https://tiktok.com/@brand/video/201",
                "title": "Video khong co view count tu provider",
                "caption": "Test missing view count",
                # Omit view_count intentionally
            },
            {
                "observation_id": "obs-explicit-zero-vc",
                "external_id": "post-vid-202",
                "canonical_url": "https://tiktok.com/@brand/video/202",
                "title": "Video co view count bang 0",
                "caption": "Test zero view count",
                "view_count": 0, # Explicitly zero
            },
            {
                "observation_id": "obs-positive-vc",
                "external_id": "post-vid-203",
                "canonical_url": "https://tiktok.com/@brand/video/203",
                "title": "Video co view count 1234",
                "caption": "Test normal view count",
                "view_count": 1234,
            },
        ]
    }

    res = client.post("/v1/ingestion/batch", json=batch_payload, headers=headers)
    assert res.status_code == 200, res.text

    db = SessionLocal()
    # Check item 1: view_count MUST be None (NULL in DB)
    snap_missing = db.query(MetricSnapshot).filter(MetricSnapshot.observation_id == "obs-missing-vc").first()
    assert snap_missing is not None
    assert snap_missing.view_count is None # Strict NULL, not 0!

    # Check item 2: view_count MUST be 0
    snap_zero = db.query(MetricSnapshot).filter(MetricSnapshot.observation_id == "obs-explicit-zero-vc").first()
    assert snap_zero is not None
    assert snap_zero.view_count == 0

    # Check item 3: view_count MUST be 1234
    snap_pos = db.query(MetricSnapshot).filter(MetricSnapshot.observation_id == "obs-positive-vc").first()
    assert snap_pos is not None
    assert snap_pos.view_count == 1234
    db.close()

def test_t042_duplicate_url_different_providers_one_canonical_record(setup_p04_env):
    """
    T042: Duplicate shared URL and different provider payload ->
    one canonical record + separately attributed source observations.
    """
    headers = setup_p04_env["editor_headers"]
    shared_url = "https://tiktok.com/@brand/video/viral-shared-999"

    # Batch 1: Ingest from customer_import
    batch1 = {
        "items": [
            {
                "observation_id": "obs-prov-a-01",
                "external_id": "ext-prov-a",
                "canonical_url": shared_url,
                "title": "Review san pham goc tu khach hang",
                "provider_id": "customer_import",
                "view_count": 3000,
            }
        ]
    }
    res1 = client.post("/v1/ingestion/batch", json=batch1, headers=headers)
    assert res1.status_code == 200

    # Batch 2: Later, another provider observes the exact same URL with different title/stats
    batch2 = {
        "items": [
            {
                "observation_id": "obs-prov-b-02",
                "external_id": "ext-prov-b",
                "canonical_url": shared_url,
                "title": "Ban ghi chinh thuc tu TikTok API",
                "provider_id": "tiktok_official",
                "view_count": 95000,
            }
        ]
    }
    res2 = client.post("/v1/ingestion/batch", json=batch2, headers=headers)
    assert res2.status_code == 200

    # Verify DB: Exactly ONE canonical SourceRecord exists for this shared URL
    db = SessionLocal()
    records = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == setup_p04_env["ws_id"],
        SourceRecord.canonical_url == shared_url,
    ).all()
    assert len(records) == 1
    canonical_record = records[0]

    # Verify Lineage via API endpoint
    res_lineage = client.get(f"/v1/ingestion/lineage/{canonical_record.id}", headers=headers)
    assert res_lineage.status_code == 200
    lineage = res_lineage.json()
    assert lineage["observations_count"] == 2
    prov_ids = [obs["provider_id"] for obs in lineage["observations"]]
    assert "customer_import" in prov_ids
    assert "tiktok_official" in prov_ids
    db.close()

def test_t043_synthetic_fixture_rejected_in_prod(setup_p04_env):
    """
    T043: Synthetic fixture enters prod API -> reject and record safe error; never show as live.
    """
    headers = setup_p04_env["editor_headers"]

    # Payload contains synthetic: true while is_production is True
    batch_synthetic = {
        "items": [
            {
                "observation_id": "obs-synth-fake-01",
                "external_id": "synthetic-fake-01",
                "canonical_url": "https://example.invalid/synthetic-post",
                "title": "Fake synthetic video",
                "provider_id": "test_fixture",
                "synthetic": True, # VIOLATION FOR PRODUCTION!
            }
        ],
        "is_production": True, # Production mode
    }

    res = client.post("/v1/ingestion/batch", json=batch_synthetic, headers=headers)
    assert res.status_code == 422
    err_body = res.json()
    assert "SYNTHETIC_DATA_NOT_ALLOWED_IN_PROD" in str(err_body)

    # Verify no record created in DB
    db = SessionLocal()
    sr = db.query(SourceRecord).filter(SourceRecord.raw_external_id == "synthetic-fake-01").first()
    assert sr is None

    # Verify Audit Event recorded
    audit = db.query(AuditEvent).filter(
        AuditEvent.workspace_id == setup_p04_env["ws_id"],
        AuditEvent.event_type == "SYNTHETIC_DATA_REJECTED",
    ).first()
    assert audit is not None
    assert "synthetic-fake-01" in audit.details
    db.close()

def test_t044_deletion_expiry_purges_fields_and_logs_audit(setup_p04_env):
    """
    T044: Deletion/expiry request -> permitted retained fields purged within
    configured policy; audit event generated.
    """
    editor_headers = setup_p04_env["editor_headers"]
    admin_headers = setup_p04_env["admin_headers"]

    # 1. Ingest a record to be purged later
    batch = {
        "items": [
            {
                "observation_id": "obs-to-purge-01",
                "external_id": "post-to-purge-01",
                "canonical_url": "https://tiktok.com/@brand/video/purge-me",
                "title": "Bi kip skincare giam mun",
                "caption": "Private sensitive feedback and phone 0901234567",
                "provider_id": "customer_import",
            }
        ]
    }
    res_ingest = client.post("/v1/ingestion/batch", json=batch, headers=editor_headers)
    assert res_ingest.status_code == 200

    db = SessionLocal()
    record = db.query(SourceRecord).filter(
        SourceRecord.workspace_id == setup_p04_env["ws_id"],
        SourceRecord.raw_external_id == "post-to-purge-01",
    ).first()
    assert record is not None
    rec_id = record.id
    db.close()

    # 2. Call Purge endpoint
    res_purge = client.post(f"/v1/ingestion/purge/{rec_id}", headers=admin_headers)
    assert res_purge.status_code == 200
    purge_data = res_purge.json()
    assert purge_data["status"] == "PURGED"

    # 3. Check DB to ensure sensitive caption is purged and is_purged is True
    db = SessionLocal()
    purged_sr = db.query(SourceRecord).filter(SourceRecord.id == rec_id).first()
    assert purged_sr.is_purged is True
    assert purged_sr.caption == "[PURGED_DUE_TO_RETENTION_POLICY]"
    assert "0901234567" not in purged_sr.caption

    # Check observation payload is purged
    obs = db.query(SourceObservation).filter(SourceObservation.source_record_id == rec_id).first()
    assert obs.is_purged is True
    assert "PURGED" in obs.raw_payload_json

    # Check audit event generated
    audit = db.query(AuditEvent).filter(
        AuditEvent.workspace_id == setup_p04_env["ws_id"],
        AuditEvent.event_type == "DATA_RETENTION_PURGE",
    ).first()
    assert audit is not None
    assert rec_id in audit.details
    db.close()
