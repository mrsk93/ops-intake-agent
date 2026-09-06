from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from pathlib import Path

import boto3


class LocalFileStorage:
    """Development storage with tenant-derived paths and no public URLs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, tenant_id: str, key: str) -> Path:
        if not tenant_id or not key or Path(key).is_absolute() or ".." in Path(key).parts:
            raise ValueError("invalid tenant-scoped storage key")
        path = (self.root / tenant_id / key).resolve()
        if self.root not in path.parents:
            raise ValueError("storage key escapes root")
        return path

    async def put_stream(
        self,
        *,
        tenant_id: str,
        key: str,
        chunks: AsyncIterable[bytes],
        content_type: str,
    ) -> str:
        del content_type
        path = self._path(tenant_id, key)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, b"")
        async for chunk in chunks:
            await asyncio.to_thread(self._append, path, chunk)
        return key

    @staticmethod
    def _append(path: Path, chunk: bytes) -> None:
        with path.open("ab") as handle:
            handle.write(chunk)

    async def put(self, *, tenant_id: str, key: str, content: bytes, content_type: str) -> str:
        del content_type

        def write() -> None:
            path = self._path(tenant_id, key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(write)
        return key

    async def get(self, *, tenant_id: str, key: str) -> bytes:
        path = self._path(tenant_id, key)
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, *, tenant_id: str, key: str) -> None:
        path = self._path(tenant_id, key)

        def remove() -> None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

        await asyncio.to_thread(remove)


class S3Storage:
    """S3-compatible storage; every object key is prefixed by its tenant."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    @staticmethod
    def _object_key(tenant_id: str, key: str) -> str:
        if not tenant_id or not key or Path(key).is_absolute() or ".." in Path(key).parts:
            raise ValueError("invalid tenant-scoped storage key")
        return f"{tenant_id}/{key}"

    async def put_stream(
        self,
        *,
        tenant_id: str,
        key: str,
        chunks: AsyncIterable[bytes],
        content_type: str,
    ) -> str:
        content = b"".join([chunk async for chunk in chunks])
        return await self.put(
            tenant_id=tenant_id, key=key, content=content, content_type=content_type
        )

    async def put(self, *, tenant_id: str, key: str, content: bytes, content_type: str) -> str:
        object_key = self._object_key(tenant_id, key)
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type,
        )
        return key

    async def get(self, *, tenant_id: str, key: str) -> bytes:
        response = await asyncio.to_thread(
            self.client.get_object, Bucket=self.bucket, Key=self._object_key(tenant_id, key)
        )
        return await asyncio.to_thread(response["Body"].read)

    async def delete(self, *, tenant_id: str, key: str) -> None:
        await asyncio.to_thread(
            self.client.delete_object, Bucket=self.bucket, Key=self._object_key(tenant_id, key)
        )
