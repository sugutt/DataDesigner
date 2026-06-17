# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.gettempdir()) / f'studio-test-{uuid4().hex}.db'}"
os.environ["STUDIO_ADMIN_TOKEN"] = "test-token"
os.environ["STUDIO_RUN_JOBS_INLINE"] = "true"
os.environ["STUDIO_USE_SYNTHETIC_RUNNER"] = "true"
os.environ["STUDIO_ARTIFACT_ROOT"] = str(Path(tempfile.gettempdir()) / f"studio-artifacts-{uuid4().hex}")

from fastapi.testclient import TestClient

from studio_backend.app import create_app


def test_protected_routes_require_bearer_token() -> None:
    client = TestClient(create_app())

    response = client.get("/api/state")

    assert response.status_code == 401


def test_studio_api_end_to_end_smoke() -> None:
    client = TestClient(create_app())
    headers = {"Authorization": "Bearer test-token"}

    assert client.get("/api/health").json()["message"] == "ok"
    assert client.get("/api/ready", headers=headers).json()["message"] == "ready"
    state = client.get("/api/state", headers=headers).json()
    assert state["project"]["name"]

    provider = client.post(
        "/api/model-providers",
        headers=headers,
        json={"name": "local-vllm", "endpoint": "http://localhost:8001/v1", "api_key_secret": "LOCAL_API_KEY"},
    )
    assert provider.status_code == 200

    column = client.post(
        "/api/columns",
        headers=headers,
        json={"type": "Sampler", "name": "domain", "depends": "", "prompt": "Health\nEducation"},
    )
    assert column.status_code == 200

    preview = client.post("/api/preview-jobs", headers=headers, json={"rows": 3})
    assert preview.status_code == 200
    preview_job = client.get(f"/api/preview-jobs/{preview.json()['id']}", headers=headers).json()
    assert preview_job["status"] == "completed"
    assert len(preview_job["records"]) == 3

    generation = client.post("/api/generation-jobs", headers=headers, json={"target_records": 2})
    assert generation.status_code == 200
    generation_job = client.get(f"/api/generation-jobs/{generation.json()['id']}", headers=headers).json()
    assert generation_job["status"] == "completed"
    assert generation_job["completed_records"] == 2

    export = client.post("/api/exports", headers=headers, json={"format": "JSONL"})
    assert export.status_code == 200
    manifest = export.json()
    assert manifest["status"] == "prepared"
    assert client.get(f"/api/exports/{manifest['id']}/download", headers=headers).status_code == 200
