# Tests cho Gate 4: Tich hop luong sinh y tuong tu Dong voi Cau hinh Database Singleton
import os
import json
import uuid
import pytest
import httpx
from sqlalchemy.orm import Session

os.environ["TESTING"] = "1"

from src.database import SessionLocal, Base, engine
from src.models.entities import (
    Workspace, User, Membership, BrandBriefVersion, SourceRecord,
    EvidenceExcerpt, IdeaCard, WorkspaceBudget, CostLedger, PlatformLLMConfig
)
from src.schemas.contracts import IdeaGenerationRequest
from src.modules.ideation.ideation_service import ideation_service
from src.modules.platform_config.crypto_vault import encrypt_secret

@pytest.fixture
def ideation_setup():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    exc_id = f"exc_{uuid.uuid4().hex[:8]}"

    ws = Workspace(id=ws_id, name="Gate 4 Workspace", slug=f"ws-{ws_id[:8]}")
    usr = User(id=user_id, email=f"gate4_{user_id[:6]}@baha.vn", full_name="Gate 4 User")
    mem = Membership(id=str(uuid.uuid4()), workspace_id=ws_id, user_id=user_id, role="editor")

    brief = BrandBriefVersion(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        version=1,
        brand_name="BAHA Studio Gate 4",
        objective="Kiểm thử tích hợp LLM từ Database",
        voice_description="Chân thực",
        current_audience="Gen Z",
        target_audience="Creators",
        topics_included_json=json.dumps(["thời trang", "công nghệ"]),
        topics_excluded_json=json.dumps(["chính trị"]),
        status="APPROVED"
    )

    src_url = f"https://tiktok.com/@baha/video/{uuid.uuid4().hex[:6]}"
    src = SourceRecord(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        provider_id="CUSTOMER_IMPORT",
        raw_external_id=f"rec_{uuid.uuid4().hex[:6]}",
        canonical_url=src_url,
        rights_basis="SIGNED_LICENSE",
        is_purged=False
    )

    exc = EvidenceExcerpt(
        id=exc_id,
        workspace_id=ws_id,
        source_record_id=src.id,
        excerpt_text="Bình luận người xem: Áo này mặc đi làm công sở rất thanh lịch và thoáng mát.",
        excerpt_type="COMMENT"
    )

    budget = WorkspaceBudget(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        allocated_units=100.0,
        reserved_units=0.0,
        spent_units=0.0,
        hard_limit_units=100.0
    )

    db.add_all([ws, usr, mem, brief, src, exc, budget])
    db.commit()

    yield {
        "db": db,
        "ws_id": ws_id,
        "user_id": user_id,
        "brief_id": brief.id,
        "exc_id": exc_id,
        "src_url": src_url
    }

    db.close()

def test_gate4_ideation_uses_db_config_when_enabled(ideation_setup, monkeypatch):
    """Khi DB bật LLM (is_enabled=True), ideation_service tự động gọi qua gateway với cấu hình DB."""
    ctx = ideation_setup
    db: Session = ctx["db"]

    # 1. Cấu hình DB singleton
    raw_key = "sk-live-db-key-9988"
    cfg = db.query(PlatformLLMConfig).filter(PlatformLLMConfig.id == "default_platform_llm_config").first()
    if not cfg:
        cfg = PlatformLLMConfig(id="default_platform_llm_config")
        db.add(cfg)

    cfg.is_enabled = True
    cfg.base_url = "http://127.0.0.1:20128/v1"
    cfg.model = "gpt-4o-from-db"
    cfg.api_key_ciphertext = encrypt_secret(raw_key)
    cfg.key_fingerprint = "••••••••••••9988"
    cfg.input_usd_per_1k_tokens = 0.005
    cfg.output_usd_per_1k_tokens = 0.010
    cfg.budget_units_per_usd = 20.0
    cfg.max_output_tokens = 1000
    db.commit()

    # Payload LLM mock
    llm_payload = [
        {
            "title": "Áo sơ mi công sở thoáng mát",
            "target_need": "Đồ công sở thanh lịch",
            "hook": "Đi làm mùa hè mặc gì vừa đẹp vừa mát?",
            "content_angle": "Gợi ý phối đồ thực tế",
            "confidence_tier": "EVIDENCE_BACKED",
            "evidence_excerpt_ids": [ctx["exc_id"]],
            "citations": [
                {
                    "excerpt_id": ctx["exc_id"],
                    "quote_text": "Bình luận người xem: Áo này mặc đi làm công sở rất thanh lịch và thoáng mát.",
                    "source_url": ctx["src_url"]
                }
            ],
            "overall_score": 8.8
        }
    ]

    called_endpoint = []
    def mock_post(self, url, **kwargs):
        called_endpoint.append(str(url))
        assert "Bearer " + raw_key == kwargs["headers"]["Authorization"]
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(llm_payload)}}],
            "model": "gpt-4o-from-db",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        })

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    req = IdeaGenerationRequest(
        brief_version_id=ctx["brief_id"],
        num_ideas=1,
        max_cost_usd=1.0
    )
    idemp_key = f"key_db_{uuid.uuid4().hex[:8]}"

    # Gọi sinh ý tưởng mà KHÔNG cần truyền llm_client hay settings ngoại lai
    res = ideation_service.generate_ideas(
        db, ctx["ws_id"], ctx["user_id"], req,
        idempotency_key=idemp_key
    )

    assert res.status == "SUCCESS"
    assert res.generation_source == "llm_router"
    assert len(res.ideas) == 1
    assert res.ideas[0].title == "Áo sơ mi công sở thoáng mát"
    assert "http://127.0.0.1:20128/v1/chat/completions" in called_endpoint[0]

def test_gate4_ideation_falls_back_to_offline_when_db_disabled(ideation_setup):
    """Khi DB tắt LLM (is_enabled=False), ideation_service tự động chuyển sang offline_template."""
    ctx = ideation_setup
    db: Session = ctx["db"]

    cfg = db.query(PlatformLLMConfig).first()
    cfg.is_enabled = False
    db.commit()

    req = IdeaGenerationRequest(
        brief_version_id=ctx["brief_id"],
        num_ideas=1
    )

    res = ideation_service.generate_ideas(
        db, ctx["ws_id"], ctx["user_id"], req
    )

    assert res.status == "SUCCESS"
    assert res.generation_source == "offline_template"
    assert len(res.ideas) >= 1
