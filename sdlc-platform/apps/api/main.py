"""Minimal FastAPI app. `/health` is the Phase 00 liveness seed (Phase 01 grows this)."""

from __future__ import annotations

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text

from common.config import get_settings
from common.db import get_engine

app = FastAPI(title="sdlc-platform", version="0.0.1")


@app.get("/health")
async def health() -> dict[str, str]:
    db_status = await _check_db()
    redis_status = await _check_redis()
    overall = "ok" if db_status == "ok" and redis_status == "ok" else "error"
    return {"status": overall, "db": db_status, "redis": redis_status}


async def _check_db() -> str:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def _check_redis() -> str:
    client: Redis | None = None
    try:
        client = Redis.from_url(get_settings().redis_url)
        await client.ping()
        return "ok"
    except Exception:
        return "error"
    finally:
        if client is not None:
            await client.aclose()
