# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class StudioSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./studio.db"
    redis_url: str = "redis://localhost:6379/0"
    studio_admin_token: str = "dev-token"
    studio_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    studio_artifact_root: Path = Path("artifacts/studio")
    studio_object_store_endpoint: str | None = None
    studio_object_store_access_key_id: str | None = None
    studio_object_store_secret_access_key: str | None = None
    studio_object_store_region: str = "us-east-1"
    studio_object_store_bucket: str = "datadesigner-studio"
    studio_object_store_secure: bool = False
    studio_run_jobs_inline: bool = False
    studio_use_synthetic_runner: bool = False

    @field_validator("studio_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> StudioSettings:
    return StudioSettings()
