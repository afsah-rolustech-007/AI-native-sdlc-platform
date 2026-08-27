"""Config is the only production module that loads environment variables."""

from pathlib import Path

from common.config import Settings, get_settings


def test_settings_reads_database_and_redis_urls(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    settings = Settings()
    assert settings.database_url.endswith("/db")
    assert settings.redis_url.startswith("redis://")
    assert settings.environment == "test"
    assert settings.max_node_visits == 100
    get_settings.cache_clear()


def test_no_direct_os_environ_outside_config() -> None:
    root = Path(__file__).resolve().parents[2] / "packages" / "common"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "config.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "os.environ" in text or "os.getenv" in text:
            offenders.append(path.name)
    assert offenders == []
