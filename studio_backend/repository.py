# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from studio_backend import orm
from studio_backend.models import (
    Analytics,
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
    PreviewRecord,
    Project,
    ProjectUpdate,
    ReviewRecord,
    ReviewUpdate,
    Source,
    SourceCreate,
    StudioState,
)


SOURCE_KIND_TO_TYPE = {
    "seed": "Seed Dataset",
    "knowledge": "Knowledge Source",
    "generated": "Generated Data",
}


class StudioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_project(self) -> Project:
        row = self.session.scalars(select(orm.ProjectRow).order_by(orm.ProjectRow.created_at)).first()
        if row is None:
            row = self.seed_project()
        return self.project_from_row(row)

    def seed_project(self) -> orm.ProjectRow:
        row = orm.ProjectRow(
            name="Kalenjin Instruction SFT",
            description="Generate supervised fine-tuning examples for translation and cultural language tasks.",
            target_task="English to Kalenjin instruction following",
            languages="English, Kalenjin",
            dataset_size=50000,
            output_schema='{\n  "instruction": "",\n  "input": "",\n  "output": "",\n  "difficulty": ""\n}',
        )
        self.session.add(row)
        self.session.flush()
        self.session.add_all(
            [
                orm.ModelProviderRow(
                    project_id=row.id,
                    name="modal-vllm",
                    endpoint="https://workspace--datadesigner-vllm-endpoint-serve.modal.run/v1",
                    api_key_secret="MODAL_MODEL_API_KEY",
                ),
                orm.ColumnConfigRow(project_id=row.id, type="Sampler", name="topic", prompt="Agriculture\nHealthcare\nEducation\nCulture"),
                orm.ColumnConfigRow(project_id=row.id, type="Sampler", name="difficulty", prompt="easy\nmedium\nhard"),
                orm.ColumnConfigRow(
                    project_id=row.id,
                    type="Generated Column",
                    name="instruction",
                    depends="topic, difficulty",
                    prompt="Create an instruction about {{topic}} with {{difficulty}} difficulty.",
                ),
                orm.ColumnConfigRow(
                    project_id=row.id,
                    type="Generated Column",
                    name="output",
                    depends="instruction",
                    prompt="Answer the instruction clearly and faithfully.",
                ),
            ]
        )
        self.session.flush()
        provider = self.session.scalars(select(orm.ModelProviderRow).where(orm.ModelProviderRow.project_id == row.id)).first()
        provider_id = provider.id if provider else None
        self.session.add(
            orm.ModelConfigRow(
                project_id=row.id,
                provider_id=provider_id,
                role="Generator",
                alias="modal-chat",
                model="modal-chat",
                endpoint="https://workspace--datadesigner-vllm-endpoint-serve.modal.run/v1",
            )
        )
        self.session.commit()
        return row

    def update_project(self, project_update: ProjectUpdate) -> Project:
        row = self.session.get(orm.ProjectRow, self.get_or_create_project().id)
        if row is None:
            raise ValueError("Project does not exist.")
        for key, value in project_update.model_dump().items():
            setattr(row, key, value)
        self.session.commit()
        return self.project_from_row(row)

    def list_sources(self, project_id: str) -> list[Source]:
        rows = self.session.scalars(select(orm.SourceRow).where(orm.SourceRow.project_id == project_id)).all()
        return [self.source_from_row(row) for row in rows]

    def add_source(self, project_id: str, source_create: SourceCreate, object_key: str | None = None) -> Source:
        row = orm.SourceRow(
            project_id=project_id,
            name=source_create.name or f"{source_create.source_kind}_source",
            type=SOURCE_KIND_TO_TYPE[source_create.source_kind],
            records=source_create.records,
            columns=source_create.columns,
            missing=source_create.missing,
            object_key=object_key,
        )
        self.session.add(row)
        self.session.commit()
        return self.source_from_row(row)

    def list_model_providers(self, project_id: str) -> list[ModelProvider]:
        rows = self.session.scalars(select(orm.ModelProviderRow).where(orm.ModelProviderRow.project_id == project_id)).all()
        return [self.provider_from_row(row) for row in rows]

    def add_model_provider(self, project_id: str, provider_create: ModelProviderCreate) -> ModelProvider:
        row = orm.ModelProviderRow(project_id=project_id, **provider_create.model_dump())
        self.session.add(row)
        self.session.commit()
        return self.provider_from_row(row)

    def list_model_configs(self, project_id: str) -> list[ModelConfig]:
        rows = self.session.scalars(select(orm.ModelConfigRow).where(orm.ModelConfigRow.project_id == project_id)).all()
        return [self.model_from_row(row) for row in rows]

    def add_model_config(self, project_id: str, model_create: ModelConfigCreate) -> ModelConfig:
        row = orm.ModelConfigRow(project_id=project_id, **model_create.model_dump())
        self.session.add(row)
        self.session.commit()
        return self.model_from_row(row)

    def list_columns(self, project_id: str) -> list[ColumnConfig]:
        rows = self.session.scalars(select(orm.ColumnConfigRow).where(orm.ColumnConfigRow.project_id == project_id)).all()
        return [self.column_from_row(row) for row in rows]

    def add_column(self, project_id: str, column_create: ColumnConfigCreate) -> ColumnConfig:
        row = orm.ColumnConfigRow(project_id=project_id, **column_create.model_dump())
        self.session.add(row)
        self.session.commit()
        return self.column_from_row(row)

    def create_preview_job(self, project_id: str, job_create: PreviewJobCreate) -> PreviewJob:
        row = orm.PreviewJobRow(project_id=project_id, rows=job_create.rows, status="queued")
        self.session.add(row)
        self.session.commit()
        return self.preview_job_from_row(row, records=[])

    def get_preview_job(self, job_id: str) -> PreviewJob | None:
        row = self.session.get(orm.PreviewJobRow, job_id)
        if row is None:
            return None
        records = self.list_preview_records(job_id)
        return self.preview_job_from_row(row, records=records)

    def get_latest_preview_job(self, project_id: str) -> PreviewJob | None:
        row = self.session.scalars(
            select(orm.PreviewJobRow)
            .where(orm.PreviewJobRow.project_id == project_id)
            .order_by(desc(orm.PreviewJobRow.created_at))
        ).first()
        if row is None:
            return None
        return self.preview_job_from_row(row, records=self.list_preview_records(row.id))

    def set_preview_job_status(self, job_id: str, status: str, error: str | None = None) -> None:
        row = self.session.get(orm.PreviewJobRow, job_id)
        if row is None:
            return
        row.status = status
        row.error = error
        self.session.commit()

    def replace_preview_records(self, job_id: str, records: list[dict[str, Any]]) -> None:
        self.session.query(orm.PreviewRecordRow).filter(orm.PreviewRecordRow.job_id == job_id).delete()
        self.session.add_all([orm.PreviewRecordRow(job_id=job_id, data=record, judge=str(record.get("judge", ""))) for record in records])
        self.session.commit()

    def list_preview_records(self, job_id: str) -> list[PreviewRecord]:
        rows = self.session.scalars(select(orm.PreviewRecordRow).where(orm.PreviewRecordRow.job_id == job_id)).all()
        return [self.preview_record_from_row(row) for row in rows]

    def create_generation_job(self, project_id: str, job_create: GenerationJobCreate) -> GenerationJob:
        row = orm.GenerationJobRow(project_id=project_id, status="queued", target_records=job_create.target_records)
        self.session.add(row)
        self.session.commit()
        return self.generation_job_from_row(row)

    def get_generation_job(self, job_id: str) -> GenerationJob | None:
        row = self.session.get(orm.GenerationJobRow, job_id)
        return None if row is None else self.generation_job_from_row(row)

    def get_current_generation_job(self, project_id: str) -> GenerationJob | None:
        row = self.session.scalars(
            select(orm.GenerationJobRow)
            .where(orm.GenerationJobRow.project_id == project_id)
            .order_by(desc(orm.GenerationJobRow.created_at))
        ).first()
        return None if row is None else self.generation_job_from_row(row)

    def update_generation_job(self, job_id: str, **values: Any) -> None:
        row = self.session.get(orm.GenerationJobRow, job_id)
        if row is None:
            return
        for key, value in values.items():
            setattr(row, key, value)
        self.session.commit()

    def cancel_generation_job(self, job_id: str) -> GenerationJob | None:
        self.update_generation_job(job_id, status="cancelled")
        return self.get_generation_job(job_id)

    def list_reviews(self, project_id: str) -> list[ReviewRecord]:
        rows = self.session.scalars(select(orm.ReviewRecordRow).where(orm.ReviewRecordRow.project_id == project_id)).all()
        return [self.review_from_row(row) for row in rows]

    def upsert_review_for_record(self, project_id: str, record_id: str, title: str, detail: str) -> None:
        self.session.add(orm.ReviewRecordRow(project_id=project_id, record_id=record_id, title=title, detail=detail))
        self.session.commit()

    def update_review(self, review_id: str, review_update: ReviewUpdate) -> ReviewRecord | None:
        row = self.session.get(orm.ReviewRecordRow, review_id)
        if row is None:
            return None
        row.status = review_update.status
        row.edited_data = review_update.edited_data
        self.session.commit()
        return self.review_from_row(row)

    def get_analytics(self, project_id: str) -> Analytics:
        row = self.session.scalars(
            select(orm.AnalyticsSnapshotRow)
            .where(orm.AnalyticsSnapshotRow.project_id == project_id)
            .order_by(desc(orm.AnalyticsSnapshotRow.created_at))
        ).first()
        if row is None:
            return Analytics()
        return Analytics(
            task_distribution=row.task_distribution,
            score_distribution=row.score_distribution,
            duplicate_groups=row.duplicate_groups,
            largest_cluster=row.largest_cluster,
            diversity_score=row.diversity_score,
        )

    def create_export(self, project_id: str, export_request: ExportRequest) -> ExportManifest:
        row = orm.ExportManifestRow(project_id=project_id, format=export_request.format, status="queued")
        self.session.add(row)
        self.session.commit()
        return self.export_from_row(row)

    def update_export(self, export_id: str, **values: Any) -> None:
        row = self.session.get(orm.ExportManifestRow, export_id)
        if row is None:
            return
        for key, value in values.items():
            setattr(row, key, value)
        self.session.commit()

    def get_export(self, export_id: str) -> ExportManifest | None:
        row = self.session.get(orm.ExportManifestRow, export_id)
        return None if row is None else self.export_from_row(row)

    def get_state(self) -> StudioState:
        project = self.get_or_create_project()
        latest_preview = self.get_latest_preview_job(project.id)
        preview_records = latest_preview.records if latest_preview else []
        return StudioState(
            project=project,
            sources=self.list_sources(project.id),
            model_providers=self.list_model_providers(project.id),
            models=self.list_model_configs(project.id),
            columns=self.list_columns(project.id),
            preview_records=preview_records,
            generation_job=self.get_current_generation_job(project.id),
            reviews=self.list_reviews(project.id),
            analytics=self.get_analytics(project.id),
            yaml=self.generate_yaml(project.id),
        )

    def generate_yaml(self, project_id: str) -> str:
        project = self.project_from_row(self.session.get(orm.ProjectRow, project_id))
        models = self.list_model_configs(project_id)
        columns = self.list_columns(project_id)
        lines = [
            f"project: {project.name}",
            f"target_task: {project.target_task}",
            f"languages: {project.languages}",
            f"dataset_size: {project.dataset_size}",
            "models:",
        ]
        lines.extend([f"  - alias: {model.alias}\n    model: {model.model}\n    role: {model.role}" for model in models])
        lines.append("columns:")
        lines.extend([f"  - name: {column.name}\n    type: {column.type}\n    depends: {column.depends}" for column in columns])
        return "\n".join(lines)

    @staticmethod
    def project_from_row(row: orm.ProjectRow | None) -> Project:
        if row is None:
            raise ValueError("Project row is required.")
        return Project.model_validate(row, from_attributes=True)

    @staticmethod
    def source_from_row(row: orm.SourceRow) -> Source:
        return Source.model_validate(row, from_attributes=True)

    @staticmethod
    def provider_from_row(row: orm.ModelProviderRow) -> ModelProvider:
        return ModelProvider.model_validate(row, from_attributes=True)

    @staticmethod
    def model_from_row(row: orm.ModelConfigRow) -> ModelConfig:
        return ModelConfig.model_validate(row, from_attributes=True)

    @staticmethod
    def column_from_row(row: orm.ColumnConfigRow) -> ColumnConfig:
        return ColumnConfig.model_validate(row, from_attributes=True)

    @staticmethod
    def preview_record_from_row(row: orm.PreviewRecordRow) -> PreviewRecord:
        return PreviewRecord.model_validate(row, from_attributes=True)

    @staticmethod
    def preview_job_from_row(row: orm.PreviewJobRow, records: list[PreviewRecord]) -> PreviewJob:
        return PreviewJob(
            id=row.id,
            project_id=row.project_id,
            rows=row.rows,
            status=row.status,
            error=row.error,
            records=records,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def generation_job_from_row(row: orm.GenerationJobRow) -> GenerationJob:
        return GenerationJob.model_validate(row, from_attributes=True)

    @staticmethod
    def review_from_row(row: orm.ReviewRecordRow) -> ReviewRecord:
        return ReviewRecord.model_validate(row, from_attributes=True)

    @staticmethod
    def export_from_row(row: orm.ExportManifestRow) -> ExportManifest:
        return ExportManifest.model_validate(row, from_attributes=True)
