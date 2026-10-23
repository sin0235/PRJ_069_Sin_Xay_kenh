# Test kiem thu cho 5 van de ranh gioi bao ve LLM duoc phat hien boi Codex
import json
import uuid
import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from pydantic import ValidationError

from src.config import Settings
from src.database import SessionLocal, Base, engine
from src.models.entities import (
    Workspace, User, Membership, BrandBriefVersion, SourceRecord,
    EvidenceExcerpt, IdeaCard, WorkspaceBudget, CostLedger, AuditEvent
)
from src.schemas.contracts import IdeaGenerationRequest
from src.modules.llm.client import LLMClient
from src.modules.ideation.ideation_service import IdeationService
from src.modules.staging_reliability.budget_guard import budget_guard

@pytest.fixture
def edge_setup():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    exc_id = f"exc_{uuid.uuid4().hex[:8]}"

    ws = Workspace(id=ws_id, name="Edge Workspace", slug=f"ws-{ws_id[:8]}")
    usr = User(id=user_id, email=f"edge_{user_id[:6]}@baha.vn", full_name="Edge User")
    mem = Membership(id=str(uuid.uuid4()), workspace_id=ws_id, user_id=user_id, role="editor")

    brief = BrandBriefVersion(
        id=str(uuid.uuid4()),
        workspace_id=ws_id,
        version=1,
        brand_name="BAHA Guard",
        objective="Kiem thu an toan ngan sach",
        voice_description="Nghiem ngat",
        current_audience="All",
        target_audience="Devs",
        topics_included_json=json.dumps(["thời trang"]),
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

def make_cfg(enabled=True, input_price=0.002, output_price=0.004, budget_per_usd=1.0, max_output=1500):
    return Settings(
        llm_enabled=enabled,
        llm_model="gpt-4o-mini" if enabled else "",
        llm_api_key="sk-test-secret" if enabled else "",
        llm_base_url="http://127.0.0.1:20128/v1",
        llm_timeout_seconds=5.0,
        llm_max_input_bytes=20000,
        llm_max_output_tokens=max_output,
        llm_input_usd_per_1k_tokens=input_price if enabled else 0.0,
        llm_output_usd_per_1k_tokens=output_price if enabled else 0.0,
        llm_budget_units_per_usd=budget_per_usd,
        _env_file=None
    )

# ==================== VẤN ĐỀ 1: HỆ SỐ QUY ĐỔI NGÂN SÁCH ÂM ====================

def test_p1_negative_budget_units_per_usd_rejected():
    """Vấn đề 1: llm_budget_units_per_usd = -1 bị Pydantic từ chối ngay lập tức."""
    with pytest.raises(ValidationError) as exc:
        Settings(llm_budget_units_per_usd=-1.0, _env_file=None)
    assert "phải là số thực hữu hạn lớn hơn 0" in str(exc.value)

def test_p1_budget_guard_rejects_negative_or_zero_units(edge_setup):
    """Vấn đề 1: reserve_budget từ chối estimated_units <= 0 hoặc NaN/Inf bằng HTTP 422."""
    ctx = edge_setup
    db: Session = ctx["db"]

    with pytest.raises(HTTPException) as exc1:
        budget_guard.reserve_budget(
            db, ctx["ws_id"], "task_neg", "idemp_neg", "LLM_TEST", estimated_units=-5.0
        )
    assert exc1.value.status_code == 422
    assert "phải là số thực dương hữu hạn" in exc1.value.detail

    with pytest.raises(HTTPException) as exc2:
        budget_guard.reserve_budget(
            db, ctx["ws_id"], "task_zero", "idemp_zero", "LLM_TEST", estimated_units=0.0
        )
    assert exc2.value.status_code == 422
    assert "Không thể giữ chỗ ngân sách âm hoặc bằng 0" in exc2.value.detail

# ==================== VẤN ĐỀ 2: PHÍ THỰC TẾ VƯỢT TRẦN (OVERRUN) ====================

def test_p2_actual_cost_exceeding_max_cost_overrun_not_refunded(edge_setup):
    """
    Vấn đề 2: Upstream LLM trả token usage vượt quá max_cost_usd:
    - Bị từ chối bằng HTTP 422
    - KHÔNG lưu bất kỳ thẻ ý tưởng nào
    - KHÔNG hoàn tiền (ghi nhận actual cost thực trả vào ledger với discrepancy_alert=True)
    - Ghi nhận AuditEvent LLM_BUDGET_OVERRUN_ALERT
    """
    ctx = edge_setup
    db: Session = ctx["db"]
    cfg = make_cfg(enabled=True, input_price=0.01, output_price=0.02)
    service = IdeationService(settings=cfg)

    # Payload ý tưởng hợp lệ
    llm_payload = [
        {
            "title": "Cách phối đồ đẹp",
            "target_need": "Gợi ý đồ",
            "hook": "Đừng bỏ qua mẫu này",
            "content_angle": "Thực tế",
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

    # Gateway trả usage khổng lồ: 10,000 input tokens và 5,000 output tokens
    # Cost = (10000/1000)*0.01 + (5000/1000)*0.02 = 0.10 + 0.10 = 0.20 USD
    def mock_overrun(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(llm_payload)}}],
            "model": "gpt-4o-overrun",
            "usage": {"prompt_tokens": 10000, "completion_tokens": 5000}
        })

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_overrun))

    # Yêu cầu cho phép trần 0.10 USD (lớn hơn ước tính 0.06 USD nhưng nhỏ hơn 0.20 USD thực tế từ gateway)
    req = IdeaGenerationRequest(
        brief_version_id=ctx["brief_id"],
        num_ideas=1,
        max_cost_usd=0.10
    )
    idemp_key = f"key_overrun_{uuid.uuid4().hex[:8]}"

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key=idemp_key,
            llm_client=client,
            settings=cfg
        )

    assert exc_info.value.status_code == 422
    assert "vượt quá hạn mức yêu cầu" in exc_info.value.detail

    # 1. Kiem tra khong co the nao duoc luu trong DB
    cards_in_db = db.query(IdeaCard).filter(
        IdeaCard.workspace_id == ctx["ws_id"],
        IdeaCard.title == "Cách phối đồ đẹp"
    ).all()
    assert len(cards_in_db) == 0

    # 2. Kiem tra ledger khong bi hoan (status = COMMITTED vi da tieu tien nha cung cap)
    ledger = db.query(CostLedger).filter(
        CostLedger.workspace_id == ctx["ws_id"],
        CostLedger.idempotency_key == idemp_key
    ).first()
    assert ledger is not None
    assert ledger.status == "COMMITTED"
    assert ledger.actual_units == 0.20
    assert ledger.discrepancy_alert is True

    # 3. Kiem tra audit event LLM_BUDGET_OVERRUN_ALERT
    audit = db.query(AuditEvent).filter(
        AuditEvent.workspace_id == ctx["ws_id"],
        AuditEvent.event_type == "LLM_BUDGET_OVERRUN_ALERT"
    ).first()
    assert audit is not None
    details = json.loads(audit.details)
    assert "vượt quá hạn mức cho phép" in details["message"]

# ==================== VẤN ĐỀ 3: RANH GIỚI GIAO DỊCH (TRANSACTION BOUNDARY) ====================

def test_p3_no_partial_cards_committed_on_verifier_failure(edge_setup):
    """
    Vấn đề 3: Khi IdeaVerifier từ chối toàn bộ thẻ (ví dụ vi phạm an toàn thương hiệu):
    - Exception 422 được ném ra
    - Không có bất kỳ thẻ nào bị commit dở dang vào cơ sở dữ liệu
    - Ledger được hoàn trả an toàn (REFUNDED)
    """
    ctx = edge_setup
    db: Session = ctx["db"]
    cfg = make_cfg(enabled=True)
    service = IdeationService(settings=cfg)

    # Thẻ chứa từ cấm chính trị (brief đã cấu hình cấm "chính trị")
    llm_toxic_payload = [
        {
            "title": "Bàn luận chính trị thời trang",
            "target_need": "Nhu cầu sai",
            "hook": "chính trị độc hại",
            "content_angle": "Góc nhìn sai",
            "confidence_tier": "EVIDENCE_BACKED",
            "evidence_excerpt_ids": [ctx["exc_id"]],
            "citations": [],
            "overall_score": 3.0
        }
    ]

    def mock_toxic(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(llm_toxic_payload)}}],
            "model": "gpt-4o-toxic",
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        })

    client = LLMClient(settings=cfg, transport=httpx.MockTransport(mock_toxic))
    req = IdeaGenerationRequest(brief_version_id=ctx["brief_id"], num_ideas=1)
    idemp_key = f"key_toxic_{uuid.uuid4().hex[:8]}"

    with pytest.raises(HTTPException) as exc_info:
        service.generate_ideas(
            db, ctx["ws_id"], ctx["user_id"], req,
            idempotency_key=idemp_key,
            llm_client=client,
            settings=cfg
        )

    assert exc_info.value.status_code == 422

    # Kiem tra tuyet doi khong co the nao bi commit do dang
    cards = db.query(IdeaCard).filter(
        IdeaCard.workspace_id == ctx["ws_id"],
        IdeaCard.title == "Bàn luận chính trị thời trang"
    ).all()
    assert len(cards) == 0

    # Kiem tra ledger duoc hoan tien hop le
    ledger = db.query(CostLedger).filter(
        CostLedger.workspace_id == ctx["ws_id"],
        CostLedger.idempotency_key == idemp_key
    ).first()
    assert ledger is not None
    assert ledger.status == "REFUNDED"
    assert ledger.actual_units == 0.0

# ==================== VẤN ĐỀ 4: KÍCH HOẠT GATE 6 & ĐỒNG BỘ CONFIG ====================

def test_p4_llm_enabled_flag_and_api_key_enforcement(tmp_path):
    """Vấn đề 4: LLM_ENABLED=True bắt buộc phải có LLM_API_KEY và LLM_MODEL."""
    # Thiếu API key
    with pytest.raises(ValidationError) as exc1:
        Settings(llm_enabled=True, llm_model="gpt-4o", llm_api_key="", llm_api_key_file=tmp_path / "missing", _env_file=None)
    assert "LLM_API_KEY bắt buộc" in str(exc1.value)

    # Thiếu Model
    with pytest.raises(ValidationError) as exc2:
        Settings(llm_enabled=True, llm_model="", llm_api_key="sk-123", _env_file=None)
    assert "LLM_MODEL (hoặc LLM_DEFAULT_MODEL) bắt buộc" in str(exc2.value)

    # Đầy đủ -> is_llm_enabled = True
    s = Settings(llm_enabled=True, LLM_DEFAULT_MODEL="gpt-4o-mini", llm_api_key="sk-123", _env_file=None)
    assert s.is_llm_enabled is True
    assert s.llm_model == "gpt-4o-mini"

# ==================== VẤN ĐỀ 5: KIỂM TRA URL & WILDCARD 0.0.0.0 ====================

def test_p5_wildcard_0000_rejected():
    """Vấn đề 5: 0.0.0.0 bị từ chối rõ ràng, không được coi là loopback."""
    with pytest.raises(ValidationError) as exc:
        Settings(llm_base_url="http://0.0.0.0:20128/v1", _env_file=None)
    assert "bắt buộc phải sử dụng HTTPS" in str(exc.value)

def test_p5_url_query_and_userinfo_rejected_without_leak():
    """Vấn đề 5: Cấm URL nhúng token query hoặc userinfo, không làm lộ bí mật."""
    with pytest.raises(ValidationError) as exc1:
        Settings(llm_base_url="http://127.0.0.1:20128/v1?token=my_secret_token", _env_file=None)
    assert "không được chứa query parameters" in str(exc1.value)

    with pytest.raises(ValidationError) as exc2:
        Settings(llm_base_url="http://admin:password123@127.0.0.1:20128/v1", _env_file=None)
    assert "không được chứa thông tin xác thực userinfo" in str(exc2.value)
