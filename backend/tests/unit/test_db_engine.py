import app.db.engine as database_engine
from app.core.config import Settings


def test_database_engine_bounds_connection_and_pool_without_global_sql_timeout(monkeypatch):
    captured = {}

    def create_engine(url, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(database_engine, "create_engine", create_engine)
    database_engine.create_database_engine(
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg://user:password@localhost/benefits",
        )
    )
    assert captured["pool_timeout"] == 5
    assert captured["pool_pre_ping"] is True
    assert captured["connect_args"] == {
        "connect_timeout": 5,
        "keepalives": 1,
        "keepalives_idle": 5,
        "keepalives_interval": 1,
        "keepalives_count": 3,
    }
