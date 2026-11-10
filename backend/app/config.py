"""Runtime settings, all from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _list(name: str, default: str) -> list[str]:
    return [x.strip().rstrip("/") for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Prognova API")
    allowed_origins: list[str] = field(default_factory=lambda: _list(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"))
    # Regex for preview deployments, e.g. ^https://my-app-.*\.vercel\.app$
    allowed_origin_regex: str | None = os.getenv("ALLOWED_ORIGIN_REGEX") or None
    max_upload_mb: float = float(os.getenv("MAX_UPLOAD_MB", "4"))
    max_upload_rows: int = int(os.getenv("MAX_UPLOAD_ROWS", "200000"))
    max_workspaces: int = int(os.getenv("MAX_WORKSPACES", "4"))
    workspace_ttl_minutes: int = int(os.getenv("WORKSPACE_TTL_MINUTES", "90"))
    preload_sample: bool = os.getenv("PRELOAD_SAMPLE", "false" if os.getenv("VERCEL") else "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
