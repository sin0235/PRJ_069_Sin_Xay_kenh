from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, inspect, text


def test_legacy_flow_lease_migration_preserves_rows_and_is_concurrent_idempotent(tmp_path):
    from src.modules.flow_sessions.migrations import migrate_flow_sessions_up

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite'}", connect_args={"timeout": 20})
    with engine.begin() as conn:
        for table in ("flow_login_sessions", "flow_session_commands"):
            conn.execute(text(f"CREATE TABLE {table} (id VARCHAR(36) PRIMARY KEY, state TEXT)"))
            conn.execute(text(f"INSERT INTO {table} (id, state) VALUES ('keep', 'legacy')"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert all(pool.map(lambda _: migrate_flow_sessions_up(engine), range(3)))
    assert migrate_flow_sessions_up(engine)
    for table in ("flow_login_sessions", "flow_session_commands"):
        assert "lease_token" in {col["name"] for col in inspect(engine).get_columns(table)}
        with engine.connect() as conn:
            assert conn.execute(text(f"SELECT id, state, lease_token FROM {table}")).one() == ("keep", "legacy", None)
