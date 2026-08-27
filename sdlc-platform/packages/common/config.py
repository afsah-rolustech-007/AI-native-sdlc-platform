"""Load config from environment. This is the only module allowed to read env vars."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process settings. Names match `.env.example` (DATABASE_URL → database_url)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://sdlc:sdlc@localhost:5432/sdlc"
    redis_url: str = "redis://localhost:6379/0"
    environment: str = "development"
    # Spec does not name a number; 100 is a fail-closed ceiling until Phase 06 has data.
    max_node_visits: int = 100
    # Empty = console exporter only (no OTLP). Optional Langfuse/collector later.
    otlp_endpoint: str = ""
    sandbox_image: str = "alpine:3.20"
    sandbox_memory: str = "256m"
    sandbox_cpus: str = "0.5"
    # GLM / Z.AI — never hard-code secrets. Empty key means adapters cannot call the network.
    glm_api_key: str = ""
    glm_base_url: str = "https://api.z.ai/api/paas/v4/"
    glm_chat_model: str = "glm-4.7-flash"
    glm_embed_model: str = "embedding-3"
    pricing_registry_path: str = "configs/pricing/registry.yaml"
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_s: float = 30.0


@lru_cache
def get_settings() -> Settings:
    """Cached so every caller shares one validated snapshot."""
    return Settings()
