"""Alembic upgrade/downgrade and pgvector extension."""

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from tests.integration.conftest import ROOT

from common.config import get_settings
from common.db import make_async_engine


async def test_pgvector_extension_enabled(migrated_database_url: str) -> None:
    engine = make_async_engine(migrated_database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
        assert result.scalar_one() == "vector"
    await engine.dispose()


async def test_expected_tables_and_hitl_request_type_exist(migrated_database_url: str) -> None:
    engine = make_async_engine(migrated_database_url)
    async with engine.connect() as conn:
        tables = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' "
                "AND tablename IN ('tasks', 'cost_tracking', 'approvals', 'hitl_log')"
            )
        )
        names = {row[0] for row in tables.fetchall()}
        assert names == {"tasks", "cost_tracking", "approvals", "hitl_log"}
        col = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'hitl_log' AND column_name = 'request_type'"
            )
        )
        assert col.scalar_one() == 1
        idx = await conn.execute(
            text("SELECT 1 FROM pg_indexes WHERE indexname = 'idx_hitl_request_type'")
        )
        assert idx.scalar_one() == 1
    await engine.dispose()


def test_alembic_downgrade_and_upgrade_are_reversible(migrated_database_url: str) -> None:
    get_settings.cache_clear()
    cfg = Config(str(ROOT / "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


def test_alembic_check_has_no_model_drift(migrated_database_url: str) -> None:
    get_settings.cache_clear()
    cfg = Config(str(ROOT / "alembic.ini"))
    command.check(cfg)
