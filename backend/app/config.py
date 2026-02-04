from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    amadeus_host: str = os.getenv("AMADEUS_HOST", "test.api.amadeus.com")
    amadeus_client_id: str | None = os.getenv("AMADEUS_CLIENT_ID")
    amadeus_client_secret: str | None = os.getenv("AMADEUS_CLIENT_SECRET")

    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "600"))
    watch_poll_seconds: int = int(os.getenv("WATCH_POLL_SECONDS", "30"))


settings = Settings()
