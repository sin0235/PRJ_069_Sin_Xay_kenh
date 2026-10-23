# Test kiem thu tich hop cho Gate 4: Tich hop luong P08 voi Budget va Idempotency
import json
import uuid
import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.config import Settings
from src.database import SessionLocal, Base, engine
from src.models.entities import (
    Workspace, User, Membership, BrandBriefVersion, SourceRecord,
    EvidenceExcerpt, IdeaCard, WorkspaceBudget, CostLedger, AuditEvent
)
from src.schemas.contracts import IdeaGenerationRequest, IdeaGenerationResponse
from src.modules.llm.client import LLMClient
from src.modules.ideation.ideation_service import IdeationService

@pytest.fixture
def gate4_setup():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    exc_id = f"exc_{uuid.uuid4().hex[:8]}"

    ws = Workspace(id=ws_id, name="Gate4 Workspace", slug=f"ws-{ws_id[:8]}")
    usr = User(id=user_id, email=f"user_{user_id[:6]}@baha.vn", full_name="Gate4 User")
    mem = Membership(id=str(uuid.uuid4()), workspace_id=ws_id, user_id=user_id, role="editor")

    brief = BrandBriefVersion(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        version=1,
        brand_name="BAHA Studio",
        objective="Tăng nhận diện thương hiệu thời trang TikTok",
        voice_description="Năng động, cuốn hút",
        current_audience="Gen Z",
        target_audience="Nữ 18-24",
        topics_included_json=json.dumps(["thời trang", "mix đồ"]),
        topics_excluded_json=json.dumps(["chính trị", "độc hại"]),
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
        excerpt_text="Bình luận người xem: Áo này mặc mát nhưng cần thêm gợi ý phối chân váy.",
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

def make_test_settings(enabled=True, input_price=0.002, output_price=0.004, budget_per_usd=1.0):
    return Settings(
        llm_enabled=enabled,
        llm_model="gpt-4o-mini" if enabled else "",
        llm_api_key="sk-test-key" if enabled else "",
        llm_base_url="http://127.0.0.1:20128/v1",
        llm_timeout_seconds=5.0,
        llm_max_input_bytes=20000,
        llm_max_output_tokens=1500,
        llm_input_usd_per_1k_tokens=input_price if enabled else 0.0,
        llm_output_usd_per_1k_tokens=output_price if enabled else 0.0,
        llm_budget_units_per_usd=budget_per_usd,
        _env_file=None
    )

def test_gate4_offline_mode_returns_offline_template(gate4_setup):
    """Gate 4: Khi LLM tat, he thong tra ve generation_source='offline_template', chi phi 0."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=False)
    service = IdeationService(settings=cfg)

    req = IdeaGenerationRequest(
        brief_version_id=ctx["brief_id"],
        num_ideas=2,
        allow_hypotheses=False
    )

    res = service.generate_ideas(db, ctx["ws_id"], ctx["user_id"], req, settings=cfg)

    assert isinstance(res, IdeaGenerationResponse)
    assert res.status == "SUCCESS"
    assert res.generation_source == "offline_template"
    assert res.cost_units == 0.0
    assert len(res.ideas) == 2

def test_gate4_llm_success_with_budget_and_idempotency(gate4_setup):
    """Gate 4: Che do LLM thanh cong, tru ngan sach chinh xac, luu the va tra generation_source='llm_router'."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True, input_price=0.002, output_price=0.004)
    service = IdeationService(settings=cfg)

    llm_payload = [
        {
            "title": "3 cách phối áo mát cùng chân váy",
            "target_need": "Gợi ý phối chân váy cùng áo chất liệu mát",
            "hook": "Đừng vội cất chiếc áo này nếu chưa thử 3 cách phối",
            "content_angle": "Hướng dẫn phối đồ trực quan",
            "confidence_tier": "EVIDENCE_BACKED",
            "evidence_excerpt_ids": [ctx["exc_id"]],
            "citations": [
                {
                    "excerpt_id": ctx["exc_id"],
                    "quote_text": "Bình luận người xem: Áo này mặc mát nhưng cần thêm gợi ý phối chân váy.",
                    "source_url": ctx["src_url"],
                    "observed_vs_inferred": "OBSERVED_DIRECT",
                    "confidence_score": 1.0
                }
            ],
            "overall_score": 8.8
        }
    ]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(llm_payload)}}],
                "model": "gpt-4o-mini-2024",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50}
            }
        )

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_handler))

    req = IdeaGenerationRequest(
        brief_version_id=ctx["brief_id"],
        num_ideas=1,
        allow_hypotheses=False,
        max_cost_usd=1.0
    )

    idemp_key = f"key_{uuid.uuid4().hex[:12]}"
    res = service.generate_ideas(
        db, ctx["ws_id"], ctx["user_id"], req,
        idempotency_key=idemp_key,
        llm_client=client,
        settings=cfg
    )

    assert res.status == "SUCCESS"
    assert res.generation_source == "llm_router"
    # actual cost: (100/1000)*0.002 + (50/1000)*0.004 = 0.0002 + 0.0002 = 0.0004 units
    assert res.cost_units == 0.0004
    assert len(res.ideas) == 1
    assert res.ideas[0].title == "3 cách phối áo mát cùng chân váy"

    ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == idemp_key).first()
    assert ledger is not None
    assert ledger.status == "COMMITTED"
    assert ledger.actual_units == 0.0004

    budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ctx["ws_id"]).first()
    assert budget.spent_units == 0.0004
    assert budget.reserved_units == 0.0

def test_gate4_duplicate_idempotency_key_rejected_409(gate4_setup):
    """Gate 4: Goi lai voi cung Idempotency-Key phai bi chan bang HTTP 409, khong goi model lan hai."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True)
    service = IdeationService(settings=cfg)

    call_count = 0
    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps([{
                "title": "Phối đồ đơn giản 123",
                "target_need": "Nhu cầu phối đồ",
                "hook": "Câu mở đầu độc đáo",
                "content_angle": "Góc nhìn phối đồ",
                "confidence_tier": "EVIDENCE_BACKED",
                "evidence_excerpt_ids": [ctx["exc_id"]],
                "overall_score": 8.0
            }])}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10}
        })

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_handler))
    idemp_key = f"key_replay_{uuid.uuid4().hex[:8]}"

    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1)

    # Lan 1: Thanh cong
    res1 = service.generate_ideas(
        db, ctx["ws_id"], ctx["user_id"], req,
        idempotency_key=idemp_key,
        llm_client=client,
        settings=cfg
    )
    assert res1.status == "SUCCESS"
    assert call_count == 1

    # Lan 2: Gui lai cung idempotency_key -> Bi chan bang HTTP 409
    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key=idemp_key,
            llm_client=client,
            settings=cfg
        )
    
    assert exc_info.value.status_code == 409
    assert "đã được sử dụng trước đó" in exc_info.value.detail
    assert call_count == 1

def test_gate4_insufficient_budget_rejected_402(gate4_setup):
    """Gate 4: Ngan sach kha dung khong du se bi tu choi bang HTTP 402 truoc khi goi model."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True, input_price=10.0, output_price=10.0)
    service = IdeationService(settings=cfg)

    budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ctx["ws_id"]).first()
    budget.allocated_units = 0.001
    db.commit()

    called = False
    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_handler))

    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1, max_cost_usd=100.0)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key=f"k_nobudget_{uuid.uuid4().hex[:6]}",
            llm_client=client,
            settings=cfg
        )

    assert exc_info.value.status_code == 402
    assert called is False

def test_gate4_upstream_timeout_refunds_reservation_504(gate4_setup):
    """Gate 4: Upstream timeout gay ra HTTP 504 va hoan tra reservation (REFUNDED)."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True)
    service = IdeationService(settings=cfg)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timeout while waiting for response")

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_handler))
    idemp_key = f"k_timeout_{uuid.uuid4().hex[:6]}"

    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key=idemp_key,
            llm_client=client,
            settings=cfg
        )

    assert exc_info.value.status_code == 504

    ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == idemp_key).first()
    assert ledger.status == "REFUNDED"
    assert ledger.actual_units == 0.0

    budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ctx["ws_id"]).first()
    assert budget.reserved_units == 0.0
    assert budget.spent_units == 0.0

def test_gate4_schema_error_refunds_reservation_422(gate4_setup):
    """Gate 4: LLM tra JSON sai khong the repair se tra ve HTTP 422 va hoan tra ngan sach."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True)
    service = IdeationService(settings=cfg)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Day khong phai la JSON [{{"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10}
        })

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_handler))
    idemp_key = f"k_badschema_{uuid.uuid4().hex[:6]}"

    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key=idemp_key,
            llm_client=client,
            settings=cfg
        )

    assert exc_info.value.status_code == 422

    ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == idemp_key).first()
    assert ledger.status == "REFUNDED"
    assert ledger.actual_units == 0.0

def test_gate4_missing_idempotency_key_rejected_400(gate4_setup):
    """Gate 4: Che do LLM khong co header Idempotency-Key bi chan bang HTTP 400."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True)
    service = IdeationService(settings=cfg)

    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(db, ctx["ws_id"], ctx["user_id"], req, idempotency_key=None, settings=cfg)

    assert exc_info.value.status_code == 400
    assert "Idempotency-Key" in exc_info.value.detail

def test_gate4_unconfigured_price_table_rejected_422(gate4_setup):
    """Gate 4: Bảng giá chưa cấu hình (> 0) bị từ chối 422 trước khi giữ chỗ ngân sách."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True, input_price=0.0, output_price=0.0)
    service = IdeationService(settings=cfg)

    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key="key_noprice",
            settings=cfg
        )

    assert exc_info.value.status_code == 422
    assert "bảng giá LLM" in exc_info.value.detail

def test_gate4_max_cost_exceeded_rejected_422(gate4_setup):
    """Gate 4: Ước lượng chi phí vượt quá req.max_cost_usd bị từ chối 422 trước khi giữ chỗ."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True, input_price=0.01, output_price=0.01)
    service = IdeationService(settings=cfg)

    # max_cost_usd rat nho (0.000001 USD)
    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1, max_cost_usd=0.000001)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key="key_overmaxcost",
            settings=cfg
        )

    assert exc_info.value.status_code == 422
    assert "vượt quá trần ngân sách" in exc_info.value.detail

def test_gate4_verifier_brand_safety_rejection_refunds_422(gate4_setup):
    """Gate 4: Ý tưởng LLM vi phạm chủ đề cấm của brief bị IdeaVerifier từ chối, hoàn tiền và trả 422."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True)
    service = IdeationService(settings=cfg)

    # Payload chứa từ khóa cấm trong brief ("chính trị")
    llm_payload = [
        {
            "title": "Bàn luận chuyện chính trị công sở",
            "target_need": "Nhu cầu bàn luận",
            "hook": "Câu chuyện chính trị gây bão dư luận",
            "content_angle": "Góc nhìn chính trị gay gắt",
            "confidence_tier": "EVIDENCE_BACKED",
            "evidence_excerpt_ids": [ctx["exc_id"]],
            "citations": [
                {
                    "excerpt_id": ctx["exc_id"],
                    "quote_text": "Bình luận người xem: Áo này mặc mát nhưng cần thêm gợi ý phối chân váy.",
                    "source_url": ctx["src_url"]
                }
            ],
            "overall_score": 8.0
        }
    ]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(llm_payload)}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 50}
        })

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_handler))
    idemp_key = f"k_veto_{uuid.uuid4().hex[:6]}"
    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key=idemp_key,
            llm_client=client,
            settings=cfg
        )

    assert exc_info.value.status_code == 422
    assert "IdeaVerifier" in exc_info.value.detail

    # Ngan sach phai duoc hoan tra
    ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == idemp_key).first()
    assert ledger.status == "REFUNDED"

def test_gate4_missing_usage_commits_estimated_units(gate4_setup):
    """Gate 4: Upstream không trả usage -> Commit theo estimated units, vendor_reported_units=None."""
    ctx = gate4_setup
    db: Session = ctx["db"]
    cfg = make_test_settings(enabled=True, input_price=0.002, output_price=0.004)
    service = IdeationService(settings=cfg)

    llm_payload = [
        {
            "title": "Gợi ý phối chân váy cùng áo mát",
            "target_need": "Nhu cầu phối đồ thoải mái",
            "hook": "Thử ngay mẹo phối đồ này",
            "content_angle": "Chia sẻ kinh nghiệm",
            "confidence_tier": "EVIDENCE_BACKED",
            "evidence_excerpt_ids": [ctx["exc_id"]],
            "citations": [
                {
                    "excerpt_id": ctx["exc_id"],
                    "quote_text": "Bình luận người xem: Áo này mặc mát nhưng cần thêm gợi ý phối chân váy.",
                    "source_url": ctx["src_url"]
                }
            ],
            "overall_score": 8.5
        }
    ]

    def mock_handler(request: httpx.Request) -> httpx.Response:
        # Tra ve choices hop le nhung khong co usage
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(llm_payload)}}]
        })

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_handler))
    idemp_key = f"k_nousage_{uuid.uuid4().hex[:6]}"
    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1)

    res = service.generate_ideas(
        db, ctx["ws_id"], ctx["user_id"], req,
        idempotency_key=idemp_key,
        llm_client=client,
        settings=cfg
    )

    assert res.status == "SUCCESS"
    assert res.cost_units > 0 # committed theo estimated units
    ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == idemp_key).first()
    assert ledger.status == "COMMITTED"
    assert ledger.vendor_reported_units is None

