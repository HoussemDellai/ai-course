from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from azure.core.credentials_async import AsyncTokenCredential
from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError

LEASE_SECONDS = 60


class JobLock(Protocol):
    """Exclusive ownership of a job, so two orchestrator replicas never run the same job."""

    async def renew(self) -> None: ...
    async def release(self) -> None: ...


class ArtifactStore(Protocol):
    """Persists job state and media so long jobs survive restarts of the orchestrator."""

    async def write_text(self, job_id: str, name: str, text: str) -> None: ...
    async def read_text(self, job_id: str, name: str) -> str | None: ...
    async def upload(self, job_id: str, name: str, path: Path) -> None: ...
    async def download(self, job_id: str, name: str, path: Path) -> bool: ...
    async def exists(self, job_id: str, name: str) -> bool: ...
    async def list_jobs(self) -> list[str]: ...
    async def download_url(self, job_id: str, name: str) -> str | None: ...
    async def try_lock(self, job_id: str) -> JobLock | None: ...
    async def aclose(self) -> None: ...


async def write_json(store: ArtifactStore, job_id: str, name: str, data: object) -> None:
    await store.write_text(job_id, name, json.dumps(data, ensure_ascii=False, indent=2, default=str))


async def read_json(store: ArtifactStore, job_id: str, name: str) -> object | None:
    text = await store.read_text(job_id, name)
    return json.loads(text) if text is not None else None


class LocalArtifactStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, job_id: str, name: str) -> Path:
        return self.root / job_id / name

    async def write_text(self, job_id: str, name: str, text: str) -> None:
        p = self.path(job_id, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(p)

    async def read_text(self, job_id: str, name: str) -> str | None:
        p = self.path(job_id, name)
        return p.read_text(encoding="utf-8") if p.exists() else None

    async def upload(self, job_id: str, name: str, path: Path) -> None:
        dest = self.path(job_id, name)
        if dest.resolve() != path.resolve():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)

    async def download(self, job_id: str, name: str, path: Path) -> bool:
        src = self.path(job_id, name)
        if not src.exists():
            return False
        if src.resolve() != path.resolve():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, path)
        return True

    async def exists(self, job_id: str, name: str) -> bool:
        return self.path(job_id, name).exists()

    async def list_jobs(self) -> list[str]:
        return sorted(p.name for p in self.root.iterdir() if (p / "state.json").exists())

    async def download_url(self, job_id: str, name: str) -> str | None:
        return None  # served by the API from local disk

    async def try_lock(self, job_id: str) -> JobLock | None:
        return _NoopLock()  # local mode = a single process; JobManager already prevents duplicates

    async def aclose(self) -> None:
        pass


class _NoopLock:
    async def renew(self) -> None:
        pass

    async def release(self) -> None:
        pass


class _BlobLock:
    def __init__(self, lease):
        self._lease = lease

    async def renew(self) -> None:
        await self._lease.renew()

    async def release(self) -> None:
        try:
            await self._lease.release()
        except HttpResponseError:
            pass


class BlobArtifactStore:
    def __init__(self, account_url: str, container: str, credential: AsyncTokenCredential):
        from azure.storage.blob.aio import BlobServiceClient

        self._service = BlobServiceClient(account_url=account_url, credential=credential)
        self._container = self._service.get_container_client(container)
        self.container = container

    @staticmethod
    def _blob(job_id: str, name: str) -> str:
        return f"{job_id}/{name}"

    async def write_text(self, job_id: str, name: str, text: str) -> None:
        await self._container.upload_blob(self._blob(job_id, name), text.encode("utf-8"), overwrite=True)

    async def read_text(self, job_id: str, name: str) -> str | None:
        try:
            stream = await self._container.download_blob(self._blob(job_id, name))
            return (await stream.readall()).decode("utf-8")
        except ResourceNotFoundError:
            return None

    async def upload(self, job_id: str, name: str, path: Path) -> None:
        from azure.storage.blob import ContentSettings

        content_type = "video/mp4" if path.suffix == ".mp4" else "audio/wav" if path.suffix == ".wav" else None
        with path.open("rb") as f:
            await self._container.upload_blob(
                self._blob(job_id, name), f, overwrite=True, max_concurrency=4,
                content_settings=ContentSettings(content_type=content_type) if content_type else None,
            )

    async def download(self, job_id: str, name: str, path: Path) -> bool:
        try:
            stream = await self._container.download_blob(self._blob(job_id, name), max_concurrency=4)
        except ResourceNotFoundError:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            await stream.readinto(f)
        return True

    async def exists(self, job_id: str, name: str) -> bool:
        return await self._container.get_blob_client(self._blob(job_id, name)).exists()

    async def list_jobs(self) -> list[str]:
        jobs = []
        async for blob in self._container.list_blobs():
            if blob.name.endswith("/state.json"):
                jobs.append(blob.name.split("/", 1)[0])
        return sorted(jobs)

    async def download_url(self, job_id: str, name: str) -> str | None:
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        now = datetime.now(timezone.utc)
        key = await self._service.get_user_delegation_key(now - timedelta(minutes=5), now + timedelta(hours=2))
        sas = generate_blob_sas(
            account_name=self._service.account_name,
            container_name=self.container,
            blob_name=self._blob(job_id, name),
            user_delegation_key=key,
            permission=BlobSasPermissions(read=True),
            expiry=now + timedelta(hours=2),
        )
        return f"{self._container.get_blob_client(self._blob(job_id, name)).url}?{sas}"

    async def try_lock(self, job_id: str) -> JobLock | None:
        """Takes a renewable 60 s blob lease on '<job>/lock'. Returns None if another replica holds it."""
        blob = self._container.get_blob_client(self._blob(job_id, "lock"))
        try:
            await blob.upload_blob(b"", overwrite=False)
        except ResourceExistsError:
            pass
        except HttpResponseError as e:
            if e.status_code != 412:  # 412 = the lock blob exists and is leased
                raise
        try:
            return _BlobLock(await blob.acquire_lease(lease_duration=LEASE_SECONDS))
        except HttpResponseError as e:
            if e.status_code == 409:  # lease already present
                return None
            raise

    async def aclose(self) -> None:
        await self._service.close()
