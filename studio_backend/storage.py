# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from studio_backend.config import StudioSettings


class ObjectStorage:
    def __init__(self, settings: StudioSettings) -> None:
        self.settings = settings
        self.local_root = settings.studio_artifact_root / "object-store"
        self.local_root.mkdir(parents=True, exist_ok=True)
        self._client = None

    def write_text(self, key: str, content: str) -> str:
        return self.write_bytes(key, content.encode("utf-8"))

    def write_bytes(self, key: str, content: bytes) -> str:
        if self._uses_s3:
            client = self._s3_client()
            self._ensure_bucket()
            client.put_object(Bucket=self.settings.studio_object_store_bucket, Key=key, Body=content)
            return key
        path = self.local_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def write_file(self, key: str, path: Path) -> str:
        return self.write_bytes(key, path.read_bytes())

    def read_text(self, key: str) -> str:
        return self.read_bytes(key).decode("utf-8")

    def read_bytes(self, key: str) -> bytes:
        if self._uses_s3:
            response = self._s3_client().get_object(Bucket=self.settings.studio_object_store_bucket, Key=key)
            return response["Body"].read()
        return (self.local_root / key).read_bytes()

    def local_path(self, key: str) -> Path:
        return self.local_root / key

    def download_url(self, key: str) -> str:
        return f"/api/object/{key}"

    @property
    def _uses_s3(self) -> bool:
        return self.settings.studio_object_store_endpoint is not None

    def _s3_client(self):
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.studio_object_store_endpoint,
                aws_access_key_id=self.settings.studio_object_store_access_key_id,
                aws_secret_access_key=self.settings.studio_object_store_secret_access_key,
                region_name=self.settings.studio_object_store_region,
            )
        return self._client

    def _ensure_bucket(self) -> None:
        client = self._s3_client()
        bucket = self.settings.studio_object_store_bucket
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            client.create_bucket(Bucket=bucket)
