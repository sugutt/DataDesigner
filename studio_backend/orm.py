# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from studio_backend.database import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProjectRow(TimestampMixin, Base):
    __tablename__ = "studio_projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("project"))
    name: Mapped[str] = mapped_column(String(255), default="Untitled dataset")
    description: Mapped[str] = mapped_column(Text, default="")
    target_task: Mapped[str] = mapped_column(String(255), default="")
    languages: Mapped[str] = mapped_column(String(255), default="")
    dataset_size: Mapped[int] = mapped_column(Integer, default=100)
    output_schema: Mapped[str] = mapped_column(Text, default="{}")

    sources: Mapped[list[SourceRow]] = relationship(back_populates="project", cascade="all, delete-orphan")


class SourceRow(Base):
    __tablename__ = "studio_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("src"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(64))
    records: Mapped[int] = mapped_column(Integer, default=0)
    columns: Mapped[str] = mapped_column(Text, default="")
    missing: Mapped[str] = mapped_column(String(64), default="")
    object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[ProjectRow] = relationship(back_populates="sources")


class ModelProviderRow(Base):
    __tablename__ = "studio_model_providers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("provider"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    endpoint: Mapped[str] = mapped_column(String(1024))
    provider_type: Mapped[str] = mapped_column(String(64), default="openai")
    api_key_secret: Mapped[str] = mapped_column(String(255), default="MODEL_PROVIDER_API_KEY")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelConfigRow(Base):
    __tablename__ = "studio_model_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("model"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("studio_model_providers.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(64))
    alias: Mapped[str] = mapped_column(String(255))
    model: Mapped[str] = mapped_column(String(255))
    endpoint: Mapped[str] = mapped_column(String(1024), default="")
    temperature: Mapped[float] = mapped_column(default=0.7)
    top_p: Mapped[float] = mapped_column(default=0.9)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    parallel: Mapped[int] = mapped_column(Integer, default=4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ColumnConfigRow(Base):
    __tablename__ = "studio_columns"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("col"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    depends: Mapped[str] = mapped_column(Text, default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PreviewJobRow(TimestampMixin, Base):
    __tablename__ = "studio_preview_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("preview"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    rows: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(64), default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class PreviewRecordRow(Base):
    __tablename__ = "studio_preview_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("record"))
    job_id: Mapped[str] = mapped_column(ForeignKey("studio_preview_jobs.id", ondelete="CASCADE"), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    judge: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(64), default="Needs review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GenerationJobRow(TimestampMixin, Base):
    __tablename__ = "studio_generation_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("gen"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(64), default="queued")
    target_records: Mapped[int] = mapped_column(Integer)
    completed_records: Mapped[int] = mapped_column(Integer, default=0)
    samples_per_second: Mapped[float] = mapped_column(default=0.0)
    tokens_per_second: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(default=0.0)
    acceptance_rate: Mapped[float] = mapped_column(default=0.0)
    rejection_rate: Mapped[float] = mapped_column(default=0.0)
    average_judge_score: Mapped[float] = mapped_column(default=0.0)
    artifact_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewRecordRow(TimestampMixin, Base):
    __tablename__ = "studio_reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("review"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default="Needs edit")
    edited_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class AnalyticsSnapshotRow(Base):
    __tablename__ = "studio_analytics"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("analytics"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    task_distribution: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    score_distribution: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    duplicate_groups: Mapped[int] = mapped_column(Integer, default=0)
    largest_cluster: Mapped[str] = mapped_column(String(64), default="0")
    diversity_score: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportManifestRow(Base):
    __tablename__ = "studio_exports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("export"))
    project_id: Mapped[str] = mapped_column(ForeignKey("studio_projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(64), default="queued")
    format: Mapped[str] = mapped_column(String(64))
    records: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[str] = mapped_column(String(1024), default="")
    download_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
