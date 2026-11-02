# -*- coding: utf-8 -*-
"""
Test Suite for Stage 1: Data Layer, ORM Entities & Schemas Validation
Tests: Schema migration lifecycle (Up/Down/Rollback), new entities CRUD, Pydantic contracts synchronization.
"""
import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, create_engine, inspect, text
from pydantic import ValidationError

from src.database import Base, SessionLocal, engine
from src.migrations.runner import migration_up, migration_down, get_current_tables
from src.migrations import runner as migration_runner
from src.models import (
    Workspace,
    User,
    Membership,
    BrandBriefVersion,
    SourceRecord,
    MetricSnapshot,
    IdeaCard,
    ScriptDraftVersion,
    AuditEvent,
    OwnedChannel,
    TrendVelocityObservation,
    PublishedContentLink,
    PerformanceSnapshot,
    LearningSignal,
    ExperimentSuggestion,
    WorkspaceBudget,
    CostLedger,
)
from src.schemas.contracts import (
    IdeaReviewRequest,
    PublishedContentLinkCreateRequest,
    PublishedContentLinkResponse,
    PerformanceSnapshotCreateRequest,
    PerformanceSnapshotResponse,
    LearningSignalResponse,
    ExperimentSuggestionResponse,
)

def test_database_migration_lifecycle():
    """Verify Up/Down migration lifecycle for all tables including Stage 1 additions."""
    # 1. Chay migration_up
    tables_after_up = migration_up()
    required_tables = [
        "workspaces", "users", "memberships", "brand_brief_versions",
        "source_records", "metric_snapshots", "idea_cards",
        "script_draft_versions", "audit_events",
        "owned_channels", "trend_velocity_observations",
        "published_content_links", "performance_snapshots",
        "learning_signals", "experiment_suggestions",
        "workspace_budgets", "cost_ledgers"
    ]
    for table in required_tables:
        assert table in tables_after_up, f"Thieu bang bat buoc: {table}"
        
    # 2. Chay migration_down (Rollback)
    tables_after_down = migration_down()
    assert len(tables_after_down) == 0, "Rollback chua xoa het bang"
    
    # 3. Phuc hoi lai de san sang chay cac test tiep theo
    tables_restored = migration_up()
    assert len(tables_restored) >= len(required_tables)

def test_stage1_columns_and_constraints():
    """Verify columns on SourceRecord and MetricSnapshot."""
    migration_up()
    inspector = inspect(engine)

    sr_cols = [c["name"] for c in inspector.get_columns("source_records")]
    assert "is_paid" in sr_cols, "Column 'is_paid' missing on source_records"
    assert "channel_id" in sr_cols, "Column 'channel_id' missing on source_records"

    ms_cols = [c["name"] for c in inspector.get_columns("metric_snapshots")]
    assert "workspace_id" in ms_cols, "Column 'workspace_id' missing on metric_snapshots"
    assert "is_paid" in ms_cols, "Column 'is_paid' missing on metric_snapshots"
    assert "channel_id" in ms_cols, "Column 'channel_id' missing on metric_snapshots"


def test_media_asset_byte_size_uses_64_bit_and_upgrade_keeps_large_rows(tmp_path, monkeypatch):
    from src.models.entities import MediaAsset

    assert isinstance(MediaAsset.__table__.c.byte_size.type, BigInteger)
    test_engine = create_engine(f"sqlite:///{tmp_path / 'asset_size.db'}")
    try:
        with test_engine.begin() as connection:
            connection.execute(text("CREATE TABLE media_assets (id TEXT PRIMARY KEY, byte_size INTEGER NOT NULL)"))
            connection.execute(text("INSERT INTO media_assets (id, byte_size) VALUES ('dji', 8428283732)"))
        monkeypatch.setattr(migration_runner, "engine", test_engine)

        assert migration_runner.migrate_media_asset_byte_size_up() is True
        assert migration_runner.migrate_media_asset_byte_size_up() is True
        with test_engine.connect() as connection:
            assert connection.execute(text("SELECT byte_size FROM media_assets WHERE id='dji'")).scalar_one() == 8428283732
    finally:
        test_engine.dispose()

def test_stage1_entities_crud_workflow():
    """Verify creation, relationship binding and querying of new ORM entities."""
    migration_up()
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    with SessionLocal() as db:
        ws = Workspace(id=ws_id, name="Stage 1 Data Test Studio", slug=f"st1-{uuid.uuid4().hex[:6]}")
        user = User(id=user_id, email=f"st1_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Stage1 Tester")
        db.add_all([ws, user])
        db.flush()

        brief = BrandBriefVersion(
            workspace_id=ws_id,
            version=1,
            brand_name="Brand Data Layer",
            objective="Data Verification",
            voice_description="Direct",
            current_audience="Audience",
            target_audience="Target",
            status="APPROVED"
        )
        db.add(brief)
        db.flush()

        card = IdeaCard(
            workspace_id=ws_id,
            brief_version_id=brief.id,
            title="Idea Data 1",
            target_need="Need",
            hook="Hook",
            content_angle="Angle",
            status="APPROVED"
        )
        db.add(card)
        db.flush()

        script = ScriptDraftVersion(
            workspace_id=ws_id,
            idea_id=card.id,
            version=1,
            title="Script Data 1",
            status="APPROVED"
        )
        db.add(script)
        db.flush()

        # 1. PublishedContentLink
        link = PublishedContentLink(
            workspace_id=ws_id,
            script_draft_version_id=script.id,
            platform="tiktok",
            external_post_id="post_ext_001",
            external_post_url="https://tiktok.com/@brand/video/999001",
            channel_id="chan_001",
            is_paid=False,
            status="ACTIVE"
        )
        db.add(link)
        db.flush()

        # 2. PerformanceSnapshot
        snap = PerformanceSnapshot(
            workspace_id=ws_id,
            published_content_link_id=link.id,
            view_count=10000,
            like_count=800,
            comment_count=65,
            completion_rate=0.58,
            is_paid=False
        )
        db.add(snap)
        db.flush()

        # 3. LearningSignal
        signal = LearningSignal(
            workspace_id=ws_id,
            published_content_link_id=link.id,
            signal_type="HOOK_PERFORMANCE",
            score=8.5,
            confidence=0.92,
            formula_applied="completion_rate * 10",
            limitations_note="Short observation interval"
        )
        db.add(signal)
        db.flush()

        # 4. ExperimentSuggestion
        suggestion = ExperimentSuggestion(
            workspace_id=ws_id,
            based_on_signal_id=signal.id,
            hypothesis="Tang do dai hook len 3 giay se tang retention 15%",
            suggested_action="Thu nghiem bien the hook dat cau hoi truc dien",
            status="PROPOSED"
        )
        db.add(suggestion)
        db.flush()

        # 5. WorkspaceBudget & CostLedger
        budget = WorkspaceBudget(
            workspace_id=ws_id,
            allocated_units=200.0,
            reserved_units=10.0,
            spent_units=25.0,
            hard_limit_units=200.0
        )
        ledger = CostLedger(
            workspace_id=ws_id,
            task_id="task_ideation_001",
            idempotency_key="idemp_cost_001",
            action_type="IDEATION",
            estimated_units=5.0,
            actual_units=3.5,
            status="COMMITTED"
        )
        db.add_all([budget, ledger])
        db.commit()

        # Verify DB queries and relationships
        queried_link = db.query(PublishedContentLink).filter(PublishedContentLink.id == link.id).first()
        assert queried_link is not None
        assert len(queried_link.snapshots) == 1
        assert queried_link.snapshots[0].view_count == 10000
        assert len(queried_link.learning_signals) == 1
        assert queried_link.learning_signals[0].signal_type == "HOOK_PERFORMANCE"
        assert len(queried_link.learning_signals[0].experiment_suggestions) == 1
        assert queried_link.learning_signals[0].experiment_suggestions[0].status == "PROPOSED"

        queried_budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ws_id).first()
        assert queried_budget is not None
        assert queried_budget.allocated_units == 200.0

def test_stage1_pydantic_contracts_validation():
    """Verify strict validation on updated Pydantic request & response schemas."""
    # 1. IdeaReviewRequest requires expected_version and expected_status
    with pytest.raises(ValidationError):
        # Missing expected_version and expected_status
        IdeaReviewRequest(action="APPROVE")

    valid_review = IdeaReviewRequest(
        action="APPROVE",
        expected_version=2,
        expected_status="IN_REVIEW",
        review_reason="Dat tieu chuan thuong hieu day du"
    )
    assert valid_review.action == "APPROVE"
    assert valid_review.expected_version == 2
    assert valid_review.expected_status == "IN_REVIEW"

    # 2. PublishedContentLinkCreateRequest
    link_req = PublishedContentLinkCreateRequest(
        script_draft_version_id="scr-123",
        external_post_id="post-456",
        external_post_url="https://tiktok.com/@brand/video/456",
        channel_id="chan-789",
        is_paid=True
    )
    assert link_req.is_paid is True
    assert link_req.platform == "tiktok"

    # 3. ExperimentSuggestionResponse schema
    now = datetime.now(timezone.utc)
    sugg_resp = ExperimentSuggestionResponse(
        id="sugg-001",
        workspace_id="ws-001",
        based_on_signal_id="sig-001",
        hypothesis="Gia thuyet toi uu",
        suggested_action="Hanh dong de xuat",
        status="PROPOSED",
        created_at=now
    )
    assert sugg_resp.status == "PROPOSED"
