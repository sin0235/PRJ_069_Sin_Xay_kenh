# Migration Runner cho co so du lieu SIN (Ho tro Up va Down/Rollback)
from sqlalchemy import inspect
from src.database import engine, Base
from src.models import (
    Workspace, User, Membership, BrandBriefVersion, SourceRecord,
    MetricSnapshot, IdeaCard, ScriptDraftVersion, AuditEvent,
    PublishedContentLink, PerformanceSnapshot, LearningSignal,
    ExperimentSuggestion, WorkspaceBudget, CostLedger,
    PlatformLLMConfig
)

def migration_up():
    """Ap dung migration: Khoi tao toan bo cac bang du lieu"""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    return inspector.get_table_names()

def migration_down():
    """Rollback migration: Xoa sach cac bang du lieu ve trang thai khoi dau"""
    Base.metadata.drop_all(bind=engine)
    inspector = inspect(engine)
    return inspector.get_table_names()

def get_current_tables():
    inspector = inspect(engine)
    return inspector.get_table_names()

def migrate_platform_llm_config_up():
    """Migration nang cap luy dang (Idempotent): Chi tao bang platform_llm_configurations neu chua co."""
    PlatformLLMConfig.__table__.create(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    return "platform_llm_configurations" in inspector.get_table_names()

def migrate_platform_llm_config_down():
    """Rollback an toan: Chi xoa bang platform_llm_configurations ma khong gay anh huong den bang khac."""
    PlatformLLMConfig.__table__.drop(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    return "platform_llm_configurations" not in inspector.get_table_names()
