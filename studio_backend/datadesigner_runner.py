# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from studio_backend.models import ColumnConfig, ModelConfig, ModelProvider, Project


class DataDesignerRunner:
    def __init__(self, artifact_root: Path, *, use_synthetic_runner: bool = False) -> None:
        self.artifact_root = artifact_root
        self.use_synthetic_runner = use_synthetic_runner
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def preview(
        self,
        *,
        project: Project,
        model_providers: list[ModelProvider],
        model_configs: list[ModelConfig],
        columns: list[ColumnConfig],
        rows: int,
    ) -> list[dict[str, Any]]:
        if not self.use_synthetic_runner and self._can_run_real(columns):
            return self._run_real_preview(
                project=project,
                model_providers=model_providers,
                model_configs=model_configs,
                columns=columns,
                rows=rows,
            )
        return self._synthetic_records(project=project, columns=columns, rows=rows)

    def generate_export(
        self,
        *,
        project: Project,
        columns: list[ColumnConfig],
        records: int,
        output_path: Path,
        fmt: str,
    ) -> int:
        data = self._synthetic_records(project=project, columns=columns, rows=records)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "JSONL":
            output_path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in data), encoding="utf-8")
        elif fmt == "CSV":
            self._write_csv(output_path, data)
        else:
            output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return len(data)

    def _run_real_preview(
        self,
        *,
        project: Project,
        model_providers: list[ModelProvider],
        model_configs: list[ModelConfig],
        columns: list[ColumnConfig],
        rows: int,
    ) -> list[dict[str, Any]]:
        from data_designer.config import (
            CategorySamplerParams,
            ChatCompletionInferenceParams,
            DataDesignerConfigBuilder,
            LLMJudgeColumnConfig,
            LLMTextColumnConfig,
            ModelConfig as DDModelConfig,
            ModelProvider as DDModelProvider,
            SamplerColumnConfig,
            SamplerType,
        )
        from data_designer.interface.data_designer import DataDesigner

        providers = [
            DDModelProvider(
                name=provider.name,
                endpoint=provider.endpoint,
                provider_type=provider.provider_type,
                api_key=provider.api_key_secret,
            )
            for provider in model_providers
        ]
        builder = DataDesignerConfigBuilder(
            model_configs=[
                DDModelConfig(
                    alias=model.alias,
                    model=model.model,
                    provider=self._provider_name_for_model(model, model_providers),
                    inference_parameters=ChatCompletionInferenceParams(
                        temperature=model.temperature,
                        top_p=model.top_p,
                        max_tokens=model.max_tokens,
                        max_parallel_requests=model.parallel,
                    ),
                )
                for model in model_configs
            ]
        )
        for column in columns:
            if column.type == "Sampler":
                values = [value.strip() for value in column.prompt.splitlines() if value.strip()]
                if values:
                    builder.add_column(
                        SamplerColumnConfig(
                            name=column.name,
                            sampler_type=SamplerType.CATEGORY,
                            params=CategorySamplerParams(values=values),
                        )
                    )
            elif column.type == "Generated Column":
                builder.add_column(
                    LLMTextColumnConfig(
                        name=column.name,
                        prompt=column.prompt,
                        model_alias=self._first_generator_alias(model_configs),
                    )
                )
            elif column.type == "Judge Score":
                builder.add_column(
                    LLMJudgeColumnConfig(
                        name=column.name,
                        prompt=column.prompt,
                        model_alias=self._first_judge_alias(model_configs),
                    )
                )
        designer = DataDesigner(artifact_path=self.artifact_root / project.id, model_providers=providers)
        results = designer.preview(builder, num_records=rows)
        dataset = results.load_dataset()
        return dataset.to_dict(orient="records")

    @staticmethod
    def _can_run_real(columns: list[ColumnConfig]) -> bool:
        return any(column.type == "Generated Column" for column in columns)

    @staticmethod
    def _provider_name_for_model(model: ModelConfig, providers: list[ModelProvider]) -> str:
        for provider in providers:
            if provider.id == model.provider_id:
                return provider.name
        return providers[0].name if providers else "default"

    @staticmethod
    def _first_generator_alias(model_configs: list[ModelConfig]) -> str:
        for model in model_configs:
            if model.role == "Generator":
                return model.alias
        return model_configs[0].alias if model_configs else "default"

    @staticmethod
    def _first_judge_alias(model_configs: list[ModelConfig]) -> str:
        for model in model_configs:
            if model.role == "Judge":
                return model.alias
        return DataDesignerRunner._first_generator_alias(model_configs)

    @staticmethod
    def _synthetic_records(*, project: Project, columns: list[ColumnConfig], rows: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for index in range(rows):
            row: dict[str, Any] = {"_project": project.name, "_row": index + 1}
            for column in columns:
                row[column.name] = DataDesignerRunner._value_for_column(column, index)
            if "instruction" not in row:
                row["instruction"] = f"Create a {project.target_task or 'dataset'} sample #{index + 1}."
            if "output" not in row:
                row["output"] = f"Production preview output #{index + 1}."
            records.append(row)
        return records

    @staticmethod
    def _value_for_column(column: ColumnConfig, index: int) -> str:
        values = [value.strip() for value in column.prompt.splitlines() if value.strip()]
        if column.type == "Sampler" and values:
            return values[index % len(values)]
        if column.type == "Judge Score":
            return str(8 + (index % 3))
        return f"{column.name} value {index + 1}"

    @staticmethod
    def _write_csv(output_path: Path, data: list[dict[str, Any]]) -> None:
        import csv

        if not data:
            output_path.write_text("", encoding="utf-8")
            return
        fieldnames = sorted({key for row in data for key in row})
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
