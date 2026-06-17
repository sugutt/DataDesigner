# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Initial Synthetic Data Studio schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260616_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "studio_projects",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_task", sa.String(length=255), nullable=False),
        sa.Column("languages", sa.String(length=255), nullable=False),
        sa.Column("dataset_size", sa.Integer(), nullable=False),
        sa.Column("output_schema", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "studio_sources",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("records", sa.Integer(), nullable=False),
        sa.Column("columns", sa.Text(), nullable=False),
        sa.Column("missing", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_sources_project_id", "studio_sources", ["project_id"])
    op.create_table(
        "studio_model_providers",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=1024), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("api_key_secret", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_model_providers_project_id", "studio_model_providers", ["project_id"])
    op.create_table(
        "studio_model_configs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_id", sa.String(length=64), sa.ForeignKey("studio_model_providers.id"), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("endpoint", sa.String(length=1024), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("top_p", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("parallel", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_model_configs_project_id", "studio_model_configs", ["project_id"])
    op.create_table(
        "studio_columns",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("depends", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_columns_project_id", "studio_columns", ["project_id"])
    op.create_table(
        "studio_preview_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_preview_jobs_project_id", "studio_preview_jobs", ["project_id"])
    op.create_table(
        "studio_preview_records",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("job_id", sa.String(length=64), sa.ForeignKey("studio_preview_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("judge", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_preview_records_job_id", "studio_preview_records", ["job_id"])
    op.create_table(
        "studio_generation_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("target_records", sa.Integer(), nullable=False),
        sa.Column("completed_records", sa.Integer(), nullable=False),
        sa.Column("samples_per_second", sa.Float(), nullable=False),
        sa.Column("tokens_per_second", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("acceptance_rate", sa.Float(), nullable=False),
        sa.Column("rejection_rate", sa.Float(), nullable=False),
        sa.Column("average_judge_score", sa.Float(), nullable=False),
        sa.Column("artifact_key", sa.String(length=1024), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_generation_jobs_project_id", "studio_generation_jobs", ["project_id"])
    op.create_table(
        "studio_reviews",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("edited_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_reviews_project_id", "studio_reviews", ["project_id"])
    op.create_table(
        "studio_analytics",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_distribution", sa.JSON(), nullable=False),
        sa.Column("score_distribution", sa.JSON(), nullable=False),
        sa.Column("duplicate_groups", sa.Integer(), nullable=False),
        sa.Column("largest_cluster", sa.String(length=64), nullable=False),
        sa.Column("diversity_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_analytics_project_id", "studio_analytics", ["project_id"])
    op.create_table(
        "studio_exports",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("studio_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("format", sa.String(length=64), nullable=False),
        sa.Column("records", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("download_url", sa.String(length=1024), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_studio_exports_project_id", "studio_exports", ["project_id"])


def downgrade() -> None:
    for table in [
        "studio_exports",
        "studio_analytics",
        "studio_reviews",
        "studio_generation_jobs",
        "studio_preview_records",
        "studio_preview_jobs",
        "studio_columns",
        "studio_model_configs",
        "studio_model_providers",
        "studio_sources",
        "studio_projects",
    ]:
        op.drop_table(table)
