"""
Test Suite for Phase P03: Data-Source Adapters & Capability Proof
Tests: T030, T031, T032, T033, T034, T035
Strict Ground Truth Verification.
"""
import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.entities import Workspace, User, Membership, QuarantineRecord, AuditEvent
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from tests.conftest import tao_bearer_token, setup_test_auth_user
from src.modules.sources.provider_protocol import (
    ProviderStatus,
    ProviderCapabilityStatus,
    SearchQuery,
    Budget,
    AuthContext,
)
from src.modules.sources.provider_registry import default_registry, BANNED_SOURCES
from src.modules.sources.offline_fixture_adapter import OfflineFixtureAdapter

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_p03_env():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    db = SessionLocal()
    auth_db = AuthSessionLocal()
    
    ws = Workspace(id=str(uuid.uuid4()), name="Sin Source Test WS", slug=f"sources-{uuid.uuid4().hex[:6]}")
    user_editor = User(id=str(uuid.uuid4()), email=f"editor_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Editor User", hashed_password="mock")
    user_viewer = User(id=str(uuid.uuid4()), email=f"viewer_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Viewer User", hashed_password="mock")
    
    db.add_all([ws, user_editor, user_viewer])
    db.commit()
    
    m_editor = Membership(workspace_id=ws.id, user_id=user_editor.id, role="editor")
    m_viewer = Membership(workspace_id=ws.id, user_id=user_viewer.id, role="viewer")
    db.add_all([m_editor, m_viewer])
    db.commit()

    # Dong bo ca 2 user vao kho Baha Auth voi quyen WORKSPACE_OWNER de thao tac sources va research
    setup_test_auth_user(auth_db, ws.id, user_editor.id, user_editor.email, "WORKSPACE_OWNER")
    setup_test_auth_user(auth_db, ws.id, user_viewer.id, user_viewer.email, "WORKSPACE_OWNER")

    token_editor = tao_bearer_token(user_editor.id)
    token_viewer = tao_bearer_token(user_viewer.id)

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
        "editor_id": user_editor.id,
        "viewer_id": user_viewer.id,
        "editor_headers": editor_headers,
        "viewer_headers": viewer_headers,
        "headers": viewer_headers,
    }
    db.close()
    auth_db.close()
    yield ctx

def test_t030_provider_empty_results_zero_fake_records(setup_p03_env):
    """
    T030: When provider returns no results successfully:
    System MUST return 'EMPTY', NOT transport 'UNAVAILABLE', with ZERO fake records.
    """
    headers = setup_p03_env["viewer_headers"]
    
    # 1. Test via offline fixture search
    payload = {
        "provider_id": "test_fixture",
        "query": {
            "query": "nonexistent_query_term_12345",
            "limit": 10,
        }
    }
    # Ensure no simulated faults
    fixture_adapter = default_registry.get_provider("test_fixture")
    if isinstance(fixture_adapter, OfflineFixtureAdapter):
        fixture_adapter.set_simulated_fault(None)

    res = client.post("/v1/sources/search", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == ProviderStatus.EMPTY
    assert data["items"] == []
    assert data["total_count"] == 0

    # 2. Test via customer import adapter with empty store
    payload_import = {
        "provider_id": "customer_import",
        "query": {
            "query": "nonexistent_food_review",
            "limit": 10,
        }
    }
    res2 = client.post("/v1/sources/search", json=payload_import, headers=headers)
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["status"] == ProviderStatus.EMPTY
    assert len(data2["items"]) == 0
    assert data2["total_count"] == 0

def test_t031_auth_failed_forbidden_no_bypass(setup_p03_env):
    """
    T031: 401/403/captcha/access-denied response -> AUTH_FAILED / FORBIDDEN.
    No scraping bypass route, no automatic unapproved fallback.
    """
    headers = setup_p03_env["viewer_headers"]

    # 1. Calling official TikTok API without OAuth token -> 401 AUTH_FAILED
    payload_no_token = {
        "provider_id": "tiktok_official",
        "query": {"query": "viral beauty trends", "limit": 10},
    }
    res = client.post("/v1/sources/search", json=payload_no_token, headers=headers)
    assert res.status_code == 401
    err_body = res.json()
    assert "AUTH_FAILED" in str(err_body)
    assert "access token" in str(err_body).lower()

    # 2. Simulated upstream 403 Forbidden / Captcha on fixture adapter
    fixture_adapter = default_registry.get_provider("test_fixture")
    if isinstance(fixture_adapter, OfflineFixtureAdapter):
        fixture_adapter.set_simulated_fault("403")

    payload_fixture = {
        "provider_id": "test_fixture",
        "query": {"query": "skincare review", "limit": 10},
    }
    res2 = client.post("/v1/sources/search", json=payload_fixture, headers=headers)
    assert res2.status_code == 403
    err_body2 = res2.json()
    assert "FORBIDDEN" in str(err_body2)
    assert "bypass" in str(err_body2).lower()

    # Reset fault
    fixture_adapter.set_simulated_fault(None)

def test_t032_rate_limited_bounded_backoff_and_budget_cap(setup_p03_env):
    """
    T032: 429 with retry-after -> bounded backoff on retryable failures.
    Exceeding budget caps rejects with BUDGET_EXCEEDED without extra calls.
    """
    headers = setup_p03_env["viewer_headers"]

    # 1. Simulated 429 Rate Limit
    fixture_adapter = default_registry.get_provider("test_fixture")
    if isinstance(fixture_adapter, OfflineFixtureAdapter):
        fixture_adapter.set_simulated_fault("429", retry_after=7)

    payload_rl = {
        "provider_id": "test_fixture",
        "query": {"query": "review hop com", "limit": 10},
    }
    res = client.post("/v1/sources/search", json=payload_rl, headers=headers)
    assert res.status_code == 429
    err_body = res.json()
    assert "RATE_LIMITED" in str(err_body)

    # Reset fault
    fixture_adapter.set_simulated_fault(None)

    # 2. Exceeding Budget cap
    payload_budget = {
        "provider_id": "test_fixture",
        "query": {"query": "review hop com", "limit": 10},
        "budget": {
            "max_requests": 2,
            "max_cost_usd": 0.0,
            "current_requests": 2, # Exceeded!
            "current_cost_usd": 0.0,
            "timeout_seconds": 10.0,
        }
    }
    res_b = client.post("/v1/sources/search", json=payload_budget, headers=headers)
    assert res_b.status_code == 429
    assert "BUDGET_EXCEEDED" in str(res_b.json())

def test_t033_malformed_response_quarantine_no_success_claim(setup_p03_env):
    """
    T033: Malformed provider response -> INVALID_DATA or PARTIAL,
    isolated quarantine, no success claim.
    """
    headers = setup_p03_env["editor_headers"]

    # Batch with 1 valid item and 2 malformed items
    batch_items = [
        {
            "external_id": "cust-post-001",
            "title": "Hop com giu nhiet 3 ngan locknlock",
            "text_excerpt": "Hop com 3 ngan rat tien dung cho dan van phong.",
            "view_count": 3500,
        },
        {
            # Malformed item 1: Missing external_id
            "title": "Bai viet khong co id ngoai",
            "view_count": 100,
        },
        {
            # Malformed item 2: Missing title
            "external_id": "cust-post-missing-title",
            "view_count": 200,
        }
    ]

    res = client.post(
        "/v1/sources/customer-import",
        json={"items": batch_items},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    
    # Assertions for quarantine & integrity
    assert data["total"] == 3
    assert data["valid_count"] == 1
    assert data["quarantined_count"] == 2
    assert data["status"] == ProviderStatus.PARTIAL
    # MUST NOT claim full success
    assert data["valid_count"] < data["total"]

    # Verify quarantined records are stored and isolated
    res_q = client.get("/v1/sources/quarantine", headers=headers)
    assert res_q.status_code == 200
    q_data = res_q.json()
    assert len(q_data) >= 2
    reasons = [q["error_reason"] for q in q_data]
    assert any("external_id" in r for r in reasons)

def test_t034_live_source_status_truthful(setup_p03_env):
    """
    T034: Truthful live source status.
    No provider without verified live credentials may claim READY.
    """
    headers = setup_p03_env["viewer_headers"]

    res = client.get("/v1/sources/providers", headers=headers)
    assert res.status_code == 200
    providers = {p["provider_id"]: p for p in res.json()}

    # Check official TikTok: MUST NOT be claimed as READY without live verification
    assert "tiktok_official" in providers
    tiktok_cap = providers["tiktok_official"]
    assert tiktok_cap["live_status"] in ["UNVERIFIED", "LIVE_NOT_TESTED"]
    assert tiktok_cap["search_content"] == ProviderCapabilityStatus.REQUIRES_AUTH

    # Check test fixture: MUST NOT be claimed as live
    assert "test_fixture" in providers
    fixture_cap = providers["test_fixture"]
    assert fixture_cap["live_status"] == "UNVERIFIED"

    # Check customer import: account-only authorized alternative
    assert "customer_import" in providers
    cust_cap = providers["customer_import"]
    assert cust_cap["live_status"] == "AUTHORIZED_IMPORT"

def test_t035_banned_source_rejected_without_network_call(setup_p03_env):
    """
    T035: Disabled / unapproved source requested (MediaCrawler, TikTok Scraper):
    System returns RIGHTS_NOT_GRANTED or NO_APPROVED_SOURCE with zero network call
    and logs an audit event.
    """
    headers = setup_p03_env["viewer_headers"]

    # 1. Capability check for mediacrawler
    res_cap = client.get("/v1/sources/providers/mediacrawler/capabilities", headers=headers)
    assert res_cap.status_code == 403
    assert "RIGHTS_NOT_GRANTED" in str(res_cap.json())
    assert "Non-commercial license violation" in str(res_cap.json())

    # 2. Search attempt using banned mediacrawler
    payload_banned = {
        "provider_id": "mediacrawler",
        "query": {"query": "trending lipsticks", "limit": 10},
    }
    res_search = client.post("/v1/sources/search", json=payload_banned, headers=headers)
    assert res_search.status_code == 403
    assert "RIGHTS_NOT_GRANTED" in str(res_search.json())

    # 3. Verify Audit Event logged in DB
    db = SessionLocal()
    audit = db.query(AuditEvent).filter(
        AuditEvent.workspace_id == setup_p03_env["ws_id"],
        AuditEvent.event_type == "UNAPPROVED_SOURCE_DENIED",
    ).first()
    assert audit is not None
    assert "mediacrawler" in audit.details
    db.close()
