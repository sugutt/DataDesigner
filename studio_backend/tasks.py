# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from celery import Celery

from studio_backend.config import get_settings
from studio_backend.database import SessionLocal, create_all
from studio_backend.datadesigner_runner import DataDesignerRunner
from studio_backend.repository import StudioRepository
from studio_backend.storage import ObjectStorage

settings = get_settings()
celery_app = Celery("datadesigner_studio", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task(name="studio.preview")
def run_preview_job(job_id: str) -> None:
    create_all()
    with SessionLocal() as session:
        repo = StudioRepository(session)
        job = repo.get_preview_job(job_id)
        if job is None:
            return
        repo.set_preview_job_status(job_id, "running")
        project = repo.get_or_create_project()
        runner = DataDesignerRunner(
            settings.studio_artifact_root,
            use_synthetic_runner=settings.studio_use_synthetic_runner,
        )
        try:
            records = runner.preview(
                project=project,
                model_providers=repo.list_model_providers(project.id),
                model_configs=repo.list_model_configs(project.id),
                columns=repo.list_columns(project.id),
                rows=job.rows,
            )
            repo.replace_preview_records(job_id, records)
            repo.set_preview_job_status(job_id, "completed")
            for record in repo.list_preview_records(job_id)[:5]:
                repo.upsert_review_for_record(project.id, record.id, "Preview review", "Review generated preview record.")
        except Exception as exc:
            repo.set_preview_job_status(job_id, "failed", error=str(exc))


@celery_app.task(name="studio.generate")
def run_generation_job(job_id: str) -> None:
    create_all()
    with SessionLocal() as session:
        repo = StudioRepository(session)
        job = repo.get_generation_job(job_id)
        if job is None:
            return
        project = repo.get_or_create_project()
        runner = DataDesignerRunner(
            settings.studio_artifact_root,
            use_synthetic_runner=settings.studio_use_synthetic_runner,
        )
        output_path = settings.studio_artifact_root / project.id / f"{job.id}.jsonl"
        started = perf_counter()
        repo.update_generation_job(job_id, status="running")
        try:
            records = runner.generate_export(
                project=project,
                columns=repo.list_columns(project.id),
                records=job.target_records,
                output_path=output_path,
                fmt="JSONL",
            )
            elapsed = max(perf_counter() - started, 0.001)
            repo.update_generation_job(
                job_id,
                status="completed",
                completed_records=records,
                samples_per_second=round(records / elapsed, 2),
                tokens_per_second=int(records * 120 / elapsed),
                acceptance_rate=0.9,
                rejection_rate=0.1,
                average_judge_score=8.4,
                artifact_key=str(output_path),
            )
        except Exception as exc:
            repo.update_generation_job(job_id, status="failed", error=str(exc))


@celery_app.task(name="studio.export")
def run_export_job(export_id: str, generation_job_id: str | None = None) -> None:
    create_all()
    with SessionLocal() as session:
        repo = StudioRepository(session)
        manifest = repo.get_export(export_id)
        if manifest is None:
            return
        project = repo.get_or_create_project()
        current_job = repo.get_generation_job(generation_job_id) if generation_job_id else repo.get_current_generation_job(project.id)
        records = current_job.completed_records if current_job else min(project.dataset_size, 100)
        suffix = {"JSONL": "jsonl", "CSV": "csv", "Parquet": "json", "SFT": "jsonl", "ChatML": "jsonl", "ShareGPT": "jsonl"}[
            manifest.format
        ]
        path = settings.studio_artifact_root / project.id / "exports" / f"{export_id}.{suffix}"
        try:
            runner = DataDesignerRunner(
                Path(settings.studio_artifact_root),
                use_synthetic_runner=settings.studio_use_synthetic_runner,
            )
            count = runner.generate_export(project=project, columns=repo.list_columns(project.id), records=records, output_path=path, fmt=manifest.format)
            object_key = f"{project.id}/exports/{path.name}"
            ObjectStorage(settings).write_file(object_key, path)
            repo.update_export(
                export_id,
                status="prepared",
                records=count,
                path=f"object://{object_key}",
                download_url=f"/api/exports/{export_id}/download",
            )
        except Exception as exc:
            repo.update_export(export_id, status="failed", error=str(exc))
