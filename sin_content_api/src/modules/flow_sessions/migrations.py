"""Additive Flow schema upgrades for stores created before durable worker leases."""

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError


def migrate_flow_sessions_up(bind) -> bool:
    for table in ("flow_login_sessions", "flow_session_commands"):
        if table not in inspect(bind).get_table_names():
            continue
        if "lease_token" in {col["name"] for col in inspect(bind).get_columns(table)}:
            continue
        try:
            with bind.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN lease_token VARCHAR(36)"))
        except SQLAlchemyError:
            # API and worker may both upgrade the same durable store at startup.
            if "lease_token" not in {col["name"] for col in inspect(bind).get_columns(table)}:
                raise
    return True
