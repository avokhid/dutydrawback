"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache
def get_settings() -> "Settings":
    return Settings()


class Settings:
    def __init__(self) -> None:
        self.anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
        claim_date_str = os.getenv("CLAIM_DATE", "2025-09-02")
        self.default_claim_date = date.fromisoformat(claim_date_str)
