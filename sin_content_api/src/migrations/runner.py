# Migration Runner cho co so du lieu SIN (Ho tro Up va Down/Rollback)
from sqlalchemy import BigInteger, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from src.database import engine, Base
from src.models import (
    Workspace, User, Membership, BrandBriefVersion, SourceRecord,
    MetricSnapshot, IdeaCard, ScriptDraftVersion, AuditEvent,
    PublishedContentLink, PerformanceSnapshot, LearningSignal,
    ExperimentSuggestion, WorkspaceBudget, CostLedger,
    PlatformLLMConfig
)
from src.models.entities import ContentVideoPlan, ContentVideoRun, ContentVideoWorkerLease
from src.models.entities import VoiceProfile, VoiceStudioSetting

def migration_up():
    """Ap dung migration: Khoi tao toan bo cac bang du lieu"""
    from src.modules.flow_sessions import models as flow_models
    Base.metadata.create_all(bind=engine)
    migrate_production_project_workflow_up()
    migrate_media_asset_byte_size_up()
    from src.modules.flow_sessions.migrations import migrate_flow_sessions_up
    migrate_flow_sessions_up(engine)
    migrate_content_video_up()
    migrate_media_job_leases_up()
    inspector = inspect(engine)
    return inspector.get_table_names()

def migration_down():
    """Rollback migration: Xoa sach cac bang du lieu ve trang thai khoi dau"""
    tables = set(inspect(engine).get_table_names())
    if {"content_video_plans", "content_video_runs"} <= tables:
        migrate_content_video_down()
    Base.metadata.drop_all(bind=engine)
    inspector = inspect(engine)
    return inspector.get_table_names()

def get_current_tables():
    inspector = inspect(engine)
    return inspector.get_table_names()


def migrate_production_project_workflow_up(bind=engine):
    """Thêm loại workflow và phân loại lại dự án cũ có asset Auto Edit."""
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "production_projects" not in tables:
        return False
    columns = {column["name"] for column in inspector.get_columns("production_projects")}
    if "workflow_type" not in columns:
        with bind.begin() as connection:
            connection.execute(text(
                "ALTER TABLE production_projects ADD COLUMN workflow_type VARCHAR(32) "
                "NOT NULL DEFAULT 'AI_VIDEO'"
            ))
    if "media_assets" in tables:
        with bind.begin() as connection:
            connection.execute(text(
                "UPDATE production_projects SET workflow_type = 'AUTO_EDIT' "
                "WHERE id IN (SELECT DISTINCT project_id FROM media_assets "
                "WHERE source_product = 'AUTO_EDIT' AND project_id IS NOT NULL)"
            ))
    return True

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


def migrate_media_asset_byte_size_up():
    inspector = inspect(engine)
    if "media_assets" not in inspector.get_table_names():
        return False
    column = next((item for item in inspector.get_columns("media_assets") if item["name"] == "byte_size"), None)
    if not column:
        return False
    if isinstance(column["type"], BigInteger):
        return True
    if engine.dialect.name == "sqlite":
        return True  # SQLite INTEGER đã lưu số nguyên có dấu 64 bit dù khai báo cột là INTEGER.
    if engine.dialect.name != "postgresql":
        raise RuntimeError("MEDIA_ASSET_SIZE_MIGRATION_UNSUPPORTED_DIALECT")
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE media_assets ALTER COLUMN byte_size TYPE BIGINT"))
    return isinstance(next(item["type"] for item in inspect(engine).get_columns("media_assets")
                           if item["name"] == "byte_size"), BigInteger)


def migrate_content_video_up():
    """Create additive content-video plan/run tables without changing existing data."""
    ContentVideoPlan.__table__.create(bind=engine, checkfirst=True)
    ContentVideoRun.__table__.create(bind=engine, checkfirst=True)
    ContentVideoWorkerLease.__table__.create(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    if "voice_asset_id" not in {column["name"] for column in inspector.get_columns("content_video_runs")}:
        try:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE content_video_runs ADD COLUMN voice_asset_id VARCHAR(36) REFERENCES media_assets(id)"))
        except SQLAlchemyError:
            if "voice_asset_id" not in {column["name"] for column in inspect(engine).get_columns("content_video_runs")}:
                raise
        inspector = inspect(engine)
    if "music_asset_id" not in {column["name"] for column in inspector.get_columns("content_video_runs")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE content_video_runs ADD COLUMN music_asset_id VARCHAR(36) REFERENCES media_assets(id)"))
        inspector = inspect(engine)
    if "tts_config_json" not in {column["name"] for column in inspector.get_columns("content_video_runs")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE content_video_runs ADD COLUMN tts_config_json TEXT"))
        inspector = inspect(engine)
    if "include_subtitles" not in {column["name"] for column in inspector.get_columns("content_video_runs")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE content_video_runs ADD COLUMN include_subtitles BOOLEAN NOT NULL DEFAULT TRUE"))
        inspector = inspect(engine)
    return all(name in inspector.get_table_names() for name in (
        "content_video_plans", "content_video_runs", "content_video_worker_leases"
    )) and {"voice_asset_id", "music_asset_id", "tts_config_json", "include_subtitles"} <= {column["name"] for column in inspector.get_columns("content_video_runs")}


def migrate_content_video_down():
    """Drop only the additive content-video tables when no content-video records remain."""
    from sqlalchemy import func
    from src.database import SessionLocal

    with SessionLocal() as db:
        if db.query(func.count(ContentVideoRun.id)).scalar() or db.query(func.count(ContentVideoPlan.id)).scalar():
            raise RuntimeError("Cannot rollback content-video tables while plan or run records exist.")
    ContentVideoWorkerLease.__table__.drop(bind=engine, checkfirst=True)
    ContentVideoRun.__table__.drop(bind=engine, checkfirst=True)
    ContentVideoPlan.__table__.drop(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    return not any(name in inspector.get_table_names() for name in (
        "content_video_plans", "content_video_runs", "content_video_worker_leases"
    ))


def migrate_media_job_leases_up():
    """Migration additive: bảo toàn mọi job hiện có."""
    from src.models.entities import AIGenerationJob
    AIGenerationJob.__table__.create(bind=engine, checkfirst=True)
    for name, kind in (("lease_token", "VARCHAR(36)"), ("lease_expires_at", "TIMESTAMP")):
        if name not in {col["name"] for col in inspect(engine).get_columns("ai_generation_jobs")}:
            with engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE ai_generation_jobs ADD COLUMN {name} {kind}"))
