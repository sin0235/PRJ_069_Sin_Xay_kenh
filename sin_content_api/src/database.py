# Ket noi co so du lieu SQLAlchemy cho Backend SIN
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import declarative_base, sessionmaker
from src.config import settings

# Ho tro ca SQLite (offline) va PostgreSQL (staging/production)
connect_args = {}
pool_options = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False, "timeout": 30.0}
    if ":memory:" in settings.database_url or "mode=memory" in settings.database_url or settings.database_url == "sqlite://":
        from sqlalchemy.pool import StaticPool
        pool_options["poolclass"] = StaticPool

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,
    **pool_options
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_db_ready() -> bool:
    """Kiem tra ket noi den co so du lieu de phuc vu /readyz"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        return False

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
