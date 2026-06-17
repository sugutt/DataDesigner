# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class ApiMessage(BaseModel):
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    target_task: str = ""
    languages: str = ""
    dataset_size: int = Field(default=100, ge=1)
    output_schema: str = "{}"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectUpdate(BaseModel):
    name: str
    description: str = ""
    target_task: str = ""
    languages: str = ""
    dataset_size: int = Field(default=100, ge=1)
    output_schema: str = "{}"


class Source(BaseModel):
    id: str
    project_id: str
    name: str
    type: Literal["Seed Dataset", "Knowledge Source", "Generated Data"]
    records: int = Field(default=0, ge=0)
    columns: str = ""
    missing: str = ""
    object_key: str | None = None
    status: Literal["uploaded", "indexed", "failed"] = "uploaded"
    created_at: datetime | None = None


class SourceCreate(BaseModel):
    source_kind: Literal["seed", "knowledge", "generated"]
    name: str | None = None
    records: int = Field(default=0, ge=0)
    columns: str = ""
    missing: str = ""


class ModelProvider(BaseModel):
    id: str
    project_id: str
    name: str
    endpoint: str
    provider_type: Literal["openai"] = "openai"
    api_key_secret: str = "MODEL_PROVIDER_API_KEY"
    created_at: datetime | None = None


class ModelProviderCreate(BaseModel):
    name: str
    endpoint: str
    provider_type: Literal["openai"] = "openai"
    api_key_secret: str = "MODEL_PROVIDER_API_KEY"


class ModelConfig(BaseModel):
    id: str
    project_id: str
    provider_id: str | None = None
    role: Literal["Generator", "Judge", "Validator", "Embedding"]
    alias: str
    model: str
    endpoint: str = ""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1)
    parallel: int = Field(default=4, ge=1)
    created_at: datetime | None = None


class ModelConfigCreate(BaseModel):
    provider_id: str | None = None
    role: Literal["Generator", "Judge", "Validator", "Embedding"]
    alias: str
    model: str
    endpoint: str = ""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1)
    parallel: int = Field(default=4, ge=1)


class ColumnConfig(BaseModel):
    id: str
    project_id: str
    type: Literal["Sampler", "Generated Column", "Derived Column", "Retrieval Column", "Judge Score", "Static"]
    name: str
    depends: str = ""
    prompt: str
    created_at: datetime | None = None


class ColumnConfigCreate(BaseModel):
    type: Literal["Sampler", "Generated Column", "Derived Column", "Retrieval Column", "Judge Score", "Static"]
    name: str
    depends: str = ""
    prompt: str


class PreviewRecord(BaseModel):
    id: str
    job_id: str
    data: dict[str, Any]
    judge: str = ""
    status: Literal["Approved", "Needs review", "Rejected"] = "Needs review"
    created_at: datetime | None = None


class PreviewJobCreate(BaseModel):
    rows: int = Field(default=10, ge=1, le=100)


class PreviewJob(BaseModel):
    id: str
    project_id: str
    rows: int
    status: JobStatus
    error: str | None = None
    records: list[PreviewRecord] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GenerationJobCreate(BaseModel):
    target_records: int = Field(ge=1)


class GenerationJob(BaseModel):
    id: str
    project_id: str
    status: JobStatus
    target_records: int
    completed_records: int = 0
    samples_per_second: float = 0.0
    tokens_per_second: int = 0
    estimated_cost: float = 0.0
    acceptance_rate: float = 0.0
    rejection_rate: float = 0.0
    average_judge_score: float = 0.0
    artifact_key: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReviewRecord(BaseModel):
    id: str
    project_id: str
    record_id: str | None = None
    title: str
    detail: str
    status: Literal["Needs edit", "Reject", "Accept"] = "Needs edit"
    edited_data: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReviewUpdate(BaseModel):
    status: Literal["Needs edit", "Reject", "Accept"]
    edited_data: dict[str, Any] | None = None


class Analytics(BaseModel):
    task_distribution: dict[str, int] = Field(default_factory=dict)
    score_distribution: dict[str, int] = Field(default_factory=dict)
    duplicate_groups: int = 0
    largest_cluster: str = "0"
    diversity_score: float = 0.0


class ExportRequest(BaseModel):
    format: Literal["JSONL", "CSV", "Parquet", "SFT", "ChatML", "ShareGPT"]


class ExportManifest(BaseModel):
    id: str
    project_id: str
    status: Literal["queued", "prepared", "failed"]
    format: str
    records: int
    path: str
    download_url: str | None = None
    error: str | None = None
    created_at: datetime | None = None


class StudioState(BaseModel):
    project: Project
    sources: list[Source]
    model_providers: list[ModelProvider]
    models: list[ModelConfig]
    columns: list[ColumnConfig]
    preview_records: list[PreviewRecord]
    generation_job: GenerationJob | None
    reviews: list[ReviewRecord]
    analytics: Analytics
    yaml: str


class ObjectStoreConfig(BaseModel):
    endpoint: HttpUrl | None = None
    bucket: str
