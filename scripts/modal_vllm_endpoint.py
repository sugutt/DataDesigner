# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

"""Serve a Hugging Face chat model on Modal as an OpenAI-compatible endpoint.

Prerequisites:
    pip install modal
    modal setup
    modal secret create datadesigner-modal-vllm MODAL_MODEL_API_KEY=<your-token>

For gated Hugging Face models, add HF_TOKEN to the same Modal secret.

Deploy:
    modal deploy scripts/modal_vllm_endpoint.py

Smoke test:
    modal run scripts/modal_vllm_endpoint.py

Use the deployed endpoint in DataDesigner with ``/v1`` appended to the Modal URL:
    dd.ModelProvider(
        name="modal-vllm",
        endpoint="https://<workspace>--datadesigner-vllm-endpoint-serve.modal.run/v1",
        provider_type="openai",
        api_key="MODAL_MODEL_API_KEY",
    )
"""

import json
import os
import subprocess
from typing import Any

import aiohttp
import modal

APP_NAME = "datadesigner-vllm-endpoint"
SECRET_NAME = "datadesigner-modal-vllm"

MODEL_NAME = os.environ.get("DD_MODAL_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
MODEL_REVISION = os.environ.get("DD_MODAL_MODEL_REVISION")
SERVED_MODEL_NAME = os.environ.get("DD_MODAL_SERVED_MODEL_NAME", "modal-chat")

GPU_TYPE = os.environ.get("DD_MODAL_GPU", "L40S")
FAST_BOOT = os.environ.get("DD_MODAL_FAST_BOOT", "0") == "1"
VLLM_PORT = 8000

MINUTES = 60

app = modal.App(APP_NAME)

vllm_image = (
    modal.Image.from_registry("nvidia/cuda:12.9.0-devel-ubuntu22.04", add_python="3.12")
    .entrypoint([])
    .uv_pip_install("vllm==0.21.0", "aiohttp>=3.9.0,<4")
    .env(
        {
            "HF_XET_HIGH_PERFORMANCE": "1",
            "VLLM_LOG_STATS_INTERVAL": "10",
        }
    )
)

hf_cache_volume = modal.Volume.from_name("datadesigner-huggingface-cache", create_if_missing=True)
vllm_cache_volume = modal.Volume.from_name("datadesigner-vllm-cache", create_if_missing=True)


@app.function(
    image=vllm_image,
    gpu=GPU_TYPE,
    timeout=10 * MINUTES,
    scaledown_window=15 * MINUTES,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    volumes={
        "/root/.cache/huggingface": hf_cache_volume,
        "/root/.cache/vllm": vllm_cache_volume,
    },
)
@modal.concurrent(max_inputs=100)
@modal.web_server(port=VLLM_PORT, startup_timeout=10 * MINUTES)
def serve() -> None:
    """Start the vLLM OpenAI-compatible server."""
    api_key = os.environ.get("MODAL_MODEL_API_KEY")
    if not api_key:
        raise RuntimeError(f"Modal secret {SECRET_NAME!r} must define MODAL_MODEL_API_KEY to protect the endpoint.")

    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--host",
        "0.0.0.0",
        "--port",
        str(VLLM_PORT),
        "--served-model-name",
        SERVED_MODEL_NAME,
        "--api-key",
        api_key,
        "--uvicorn-log-level",
        "info",
    ]
    if MODEL_REVISION:
        cmd.extend(["--revision", MODEL_REVISION])
    cmd.append("--enforce-eager" if FAST_BOOT else "--no-enforce-eager")

    print("Starting vLLM:", " ".join(_redact_command(cmd)))
    subprocess.Popen(cmd)


@app.local_entrypoint()
async def test(content: str = "Say hello from the DataDesigner Modal endpoint.") -> None:
    """Run a Modal-hosted health check and chat completion request."""
    url = await serve.get_web_url.aio()
    api_key = os.environ.get("MODAL_MODEL_API_KEY")
    if not api_key:
        raise RuntimeError("Set MODAL_MODEL_API_KEY locally before running the smoke test.")

    timeout = aiohttp.ClientTimeout(total=15 * MINUTES)
    async with aiohttp.ClientSession(base_url=url, timeout=timeout) as session:
        print(f"Checking health at {url}/health")
        async with session.get("/health") as response:
            response.raise_for_status()

        payload: dict[str, Any] = {
            "model": SERVED_MODEL_NAME,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 64,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        print(f"Sending chat request to {url}/v1/chat/completions")
        async with session.post("/v1/chat/completions", json=payload, headers=headers) as response:
            response.raise_for_status()
            body = await response.json()
            print(json.dumps(body, indent=2))

    print("\nDataDesigner endpoint:")
    print(f"{url}/v1")
    print(f"Served model name: {SERVED_MODEL_NAME}")


def _redact_command(cmd: list[str]) -> list[str]:
    redacted = list(cmd)
    for index, value in enumerate(redacted):
        if value == "--api-key" and index + 1 < len(redacted):
            redacted[index + 1] = "<redacted>"
    return redacted
