"""API /health against real Postgres + Redis."""

from fastapi.testclient import TestClient

from common.config import get_settings
from common.db import reset_engine


def test_health_ok_when_postgres_and_redis_up(
    migrated_database_url: str, redis_url: str, monkeypatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    monkeypatch.setenv("REDIS_URL", redis_url)
    get_settings.cache_clear()
    reset_engine()
    from api.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "db": "ok", "redis": "ok"}
    reset_engine()
    get_settings.cache_clear()


def test_health_reports_redis_error(migrated_database_url: str, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    get_settings.cache_clear()
    reset_engine()
    from api.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "ok"
    assert body["redis"] == "error"
    assert body["status"] == "error"
    reset_engine()
    get_settings.cache_clear()
