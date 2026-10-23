"""Quản lý engine và session chuẩn; ứng dụng không tự tạo schema."""

import contextvars
from typing import Generator, Optional

from sqlalchemy import create_engine, inspect, text, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException, status

from baha_auth.src.config import settings


_current_tenant_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "baha_auth_current_tenant_id", default=None
)

engine = None
if settings.database_url:
    connect_args = {"check_same_thread": False, "timeout": 30.0} if settings.database_url.startswith("sqlite") else {}
    pool_options = {}
    if settings.database_url in ("sqlite://", "sqlite:///:memory:") or "mode=memory" in settings.database_url or ":memory:" in settings.database_url:
        pool_options["poolclass"] = StaticPool
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        echo=settings.debug,
        **pool_options,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


if engine is not None and settings.database_url and settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def set_tenant_context(workspace_id: str, db: Optional[Session] = None) -> None:
    """Gắn workspace đã xác minh vào yêu cầu và giao dịch PostgreSQL hiện tại."""
    _current_tenant_id.set(workspace_id)
    if db is not None:
        db.info["baha_auth.trusted_workspace_id"] = workspace_id
        # Bắt đầu giao dịch để hook after_begin đặt ngữ cảnh RLS trước khi truy vấn.
        db.connection()


def get_tenant_context() -> Optional[str]:
    return _current_tenant_id.get()


def clear_tenant_context(db: Optional[Session] = None) -> None:
    _current_tenant_id.set(None)
    if db is not None:
        db.info.pop("baha_auth.trusted_workspace_id", None)


@event.listens_for(Session, "after_begin")
def _apply_postgres_tenant_context(db: Session, _transaction, connection) -> None:
    workspace_id = db.info.get("baha_auth.trusted_workspace_id")
    if workspace_id and connection.dialect.name == "postgresql":
        connection.execute(
            text("SELECT set_config('baha.current_workspace_id', :workspace_id, true)"),
            {"workspace_id": workspace_id},
        )


def get_db() -> Generator[Session, None, None]:
    if engine is None or not settings.database_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "AUTH_DATABASE_NOT_CONFIGURED", "message": "Cơ sở dữ liệu phân quyền chưa được cấu hình."},
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        clear_tenant_context(db)
        db.close()


def init_db() -> None:
    """Dừng khởi động nếu thiếu schema được quản lý bên ngoài; không tự tạo schema."""
    if engine is None or not settings.database_url:
        raise RuntimeError("AUTH_DATABASE_NOT_CONFIGURED")
    existing = set(inspect(engine).get_table_names())
    required = set(Base.metadata.tables)
    missing = sorted(required - existing)
    if missing:
        raise RuntimeError("AUTH_SCHEMA_NOT_INITIALIZED")
