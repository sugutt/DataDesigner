# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session

from studio_backend.auth import require_admin_token
from studio_backend.config import StudioSettings, get_settings
from studio_backend.database import create_all, get_session
from studio_backend.models import (
    Analytics,
    ApiMessage,
    ColumnConfig,
    ColumnConfigCreate,
    ExportManifest,
    ExportRequest,
    GenerationJob,
    GenerationJobCreate,
    ModelConfig,
    ModelConfigCreate,
    ModelProvider,
    ModelProviderCreate,
    PreviewJob,
    PreviewJobCreate,
    Project,
    ProjectUpdate,
    ReviewRecord,
    ReviewUpdate,
    Source,
    SourceCreate,
    StudioState,
)
from studio_backend.repository import StudioRepository
from studio_backend.storage import ObjectStorage
from studio_backend.tasks import run_export_job, run_generation_job, run_preview_job


def get_repository(session: Session = Depends(get_session)) -> StudioRepository:
    return StudioRepository(session)


def dispatch_task(task, *args: str | None) -> None:
    try:
        task.delay(*args)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Job queue is unavailable: {exc}") from exc


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_all()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Synthetic Data Studio", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.studio_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    protected = [Depends(require_admin_token)]

    @app.get("/api/health", response_model=ApiMessage)
    def get_health() -> ApiMessage:
        return ApiMessage(message="ok")

    @app.get("/api/ready", response_model=ApiMessage, dependencies=protected)
    def get_ready(
        repo: StudioRepository = Depends(get_repository),
        current_settings: StudioSettings = Depends(get_settings),
    ) -> ApiMessage:
        project = repo.get_or_create_project()
        if not current_settings.studio_run_jobs_inline:
            try:
                import redis

                redis.from_url(current_settings.redis_url).ping()
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"Redis is unavailable: {exc}") from exc
        return ApiMessage(message="ready", data={"project_id": project.id})

    @app.get("/api/state", response_model=StudioState, dependencies=protected)
    def get_state(repo: StudioRepository = Depends(get_repository)) -> StudioState:
        return repo.get_state()

    @app.get("/api/projects/current", response_model=Project, dependencies=protected)
    def get_project(repo: StudioRepository = Depends(get_repository)) -> Project:
        return repo.get_or_create_project()

    @app.put("/api/projects/current", response_model=Project, dependencies=protected)
    def update_project(project: ProjectUpdate, repo: StudioRepository = Depends(get_repository)) -> Project:
        return repo.update_project(project)

    @app.get("/api/sources", response_model=list[Source], dependencies=protected)
    def list_sources(repo: StudioRepository = Depends(get_repository)) -> list[Source]:
        project = repo.get_or_create_project()
        return repo.list_sources(project.id)

    @app.post("/api/sources", response_model=Source, dependencies=protected)
    def create_source(source_create: SourceCreate, repo: StudioRepository = Depends(get_repository)) -> Source:
        project = repo.get_or_create_project()
        return repo.add_source(project.id, source_create)

    @app.post("/api/sources/upload", response_model=Source, dependencies=protected)
    async def upload_source(
        source_kind: str,
        file: UploadFile = File(...),
        repo: StudioRepository = Depends(get_repository),
        current_settings: StudioSettings = Depends(get_settings),
    ) -> Source:
        project = repo.get_or_create_project()
        safe_name = Path(file.filename or "upload").name
        object_key = f"{project.id}/uploads/{safe_name}"
        ObjectStorage(current_settings).write_bytes(object_key, await file.read())
        return repo.add_source(
            project.id,
            SourceCreate(source_kind=source_kind, name=safe_name, records=0, columns="", missing=""),
            object_key=object_key,
        )

    @app.get("/api/model-providers", response_model=list[ModelProvider], dependencies=protected)
    def list_model_providers(repo: StudioRepository = Depends(get_repository)) -> list[ModelProvider]:
        project = repo.get_or_create_project()
        return repo.list_model_providers(project.id)

    @app.post("/api/model-providers", response_model=ModelProvider, dependencies=protected)
    def create_model_provider(
        provider_create: ModelProviderCreate,
        repo: StudioRepository = Depends(get_repository),
    ) -> ModelProvider:
        project = repo.get_or_create_project()
        return repo.add_model_provider(project.id, provider_create)

    @app.get("/api/model-configs", response_model=list[ModelConfig], dependencies=protected)
    def list_model_configs(repo: StudioRepository = Depends(get_repository)) -> list[ModelConfig]:
        project = repo.get_or_create_project()
        return repo.list_model_configs(project.id)

    @app.post("/api/model-configs", response_model=ModelConfig, dependencies=protected)
    def create_model_config(model_create: ModelConfigCreate, repo: StudioRepository = Depends(get_repository)) -> ModelConfig:
        project = repo.get_or_create_project()
        return repo.add_model_config(project.id, model_create)

    @app.get("/api/columns", response_model=list[ColumnConfig], dependencies=protected)
    def list_columns(repo: StudioRepository = Depends(get_repository)) -> list[ColumnConfig]:
        project = repo.get_or_create_project()
        return repo.list_columns(project.id)

    @app.post("/api/columns", response_model=ColumnConfig, dependencies=protected)
    def create_column(column_create: ColumnConfigCreate, repo: StudioRepository = Depends(get_repository)) -> ColumnConfig:
        project = repo.get_or_create_project()
        return repo.add_column(project.id, column_create)

    @app.post("/api/preview-jobs", response_model=PreviewJob, dependencies=protected)
    def create_preview_job(
        job_create: PreviewJobCreate,
        repo: StudioRepository = Depends(get_repository),
        current_settings: StudioSettings = Depends(get_settings),
    ) -> PreviewJob:
        project = repo.get_or_create_project()
        job = repo.create_preview_job(project.id, job_create)
        if current_settings.studio_run_jobs_inline:
            run_preview_job(job.id)
        else:
            dispatch_task(run_preview_job, job.id)
        return job

    @app.get("/api/preview-jobs/latest", response_model=PreviewJob, dependencies=protected)
    def get_latest_preview_job(repo: StudioRepository = Depends(get_repository)) -> PreviewJob:
        project = repo.get_or_create_project()
        job = repo.get_latest_preview_job(project.id)
        if job is None:
            raise HTTPException(status_code=404, detail="No preview job exists.")
        return job

    @app.get("/api/preview-jobs/{job_id}", response_model=PreviewJob, dependencies=protected)
    def get_preview_job(job_id: str, repo: StudioRepository = Depends(get_repository)) -> PreviewJob:
        job = repo.get_preview_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Preview job was not found.")
        return job

    @app.post("/api/generation-jobs", response_model=GenerationJob, dependencies=protected)
    def create_generation_job(
        job_create: GenerationJobCreate,
        repo: StudioRepository = Depends(get_repository),
        current_settings: StudioSettings = Depends(get_settings),
    ) -> GenerationJob:
        project = repo.get_or_create_project()
        job = repo.create_generation_job(project.id, job_create)
        if current_settings.studio_run_jobs_inline:
            run_generation_job(job.id)
        else:
            dispatch_task(run_generation_job, job.id)
        return job

    @app.get("/api/generation-jobs/current", response_model=GenerationJob, dependencies=protected)
    def get_current_generation_job(repo: StudioRepository = Depends(get_repository)) -> GenerationJob:
        project = repo.get_or_create_project()
        job = repo.get_current_generation_job(project.id)
        if job is None:
            raise HTTPException(status_code=404, detail="No generation job exists.")
        return job

    @app.get("/api/generation-jobs/{job_id}", response_model=GenerationJob, dependencies=protected)
    def get_generation_job(job_id: str, repo: StudioRepository = Depends(get_repository)) -> GenerationJob:
        job = repo.get_generation_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Generation job was not found.")
        return job

    @app.post("/api/generation-jobs/{job_id}/cancel", response_model=GenerationJob, dependencies=protected)
    def cancel_generation_job(job_id: str, repo: StudioRepository = Depends(get_repository)) -> GenerationJob:
        job = repo.cancel_generation_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Generation job was not found.")
        return job

    @app.get("/api/reviews", response_model=list[ReviewRecord], dependencies=protected)
    def list_reviews(repo: StudioRepository = Depends(get_repository)) -> list[ReviewRecord]:
        project = repo.get_or_create_project()
        return repo.list_reviews(project.id)

    @app.patch("/api/reviews/{review_id}", response_model=ReviewRecord, dependencies=protected)
    def update_review(review_id: str, review_update: ReviewUpdate, repo: StudioRepository = Depends(get_repository)) -> ReviewRecord:
        review = repo.update_review(review_id, review_update)
        if review is None:
            raise HTTPException(status_code=404, detail="Review was not found.")
        return review

    @app.get("/api/analytics", response_model=Analytics, dependencies=protected)
    def get_analytics(repo: StudioRepository = Depends(get_repository)) -> Analytics:
        project = repo.get_or_create_project()
        return repo.get_analytics(project.id)

    @app.post("/api/exports", response_model=ExportManifest, dependencies=protected)
    def create_export(
        export_request: ExportRequest,
        repo: StudioRepository = Depends(get_repository),
        current_settings: StudioSettings = Depends(get_settings),
    ) -> ExportManifest:
        project = repo.get_or_create_project()
        manifest = repo.create_export(project.id, export_request)
        current_job = repo.get_current_generation_job(project.id)
        if current_settings.studio_run_jobs_inline:
            run_export_job(manifest.id, current_job.id if current_job else None)
        else:
            dispatch_task(run_export_job, manifest.id, current_job.id if current_job else None)
        updated = repo.get_export(manifest.id)
        return updated or manifest

    @app.get("/api/exports/{export_id}/download", dependencies=protected)
    def download_export(
        export_id: str,
        repo: StudioRepository = Depends(get_repository),
        current_settings: StudioSettings = Depends(get_settings),
    ) -> FileResponse | Response:
        manifest = repo.get_export(export_id)
        if manifest is None or not manifest.path:
            raise HTTPException(status_code=404, detail="Export was not found.")
        if manifest.path.startswith("object://"):
            key = manifest.path.removeprefix("object://")
            return Response(
                ObjectStorage(current_settings).read_bytes(key),
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{Path(key).name}"'},
            )
        path = Path(manifest.path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Export file was not found.")
        return FileResponse(path, filename=path.name)

    @app.get("/api/config/yaml", response_class=PlainTextResponse, dependencies=protected)
    def get_config_yaml(repo: StudioRepository = Depends(get_repository)) -> str:
        project = repo.get_or_create_project()
        return repo.generate_yaml(project.id)

    return app


app = create_app()
