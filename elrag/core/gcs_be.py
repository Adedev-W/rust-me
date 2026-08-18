from __future__ import annotations

import asyncio
import os
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

from elrag.errors.database import DatabaseUnavailableError
from elrag.lib.storage_rest import GCSService
from elrag.models.db.cloud_storage import CloudStorageModel
from elrag.schemas.db.errors import DatabaseErrorContext
from elrag.schemas.json.gcs import GcsUploadResponse


class GCSServiceBE:
    def __init__(self) -> None:
        self.bucket_name = os.environ.get("GCS_BUCKET")

    async def save_cloud_storage(self, response: CloudStorageModel) -> CloudStorageModel:
        try:
            await asyncio.to_thread(response.save)
        except Exception as exc:
            raise DatabaseUnavailableError(
                DatabaseErrorContext(
                    code="database_unavailable",
                    operation="save",
                    resource="cloud_storage",
                    retryable=True,
                ),
                cause=exc,
            ) from exc
        return response

    async def get_cloud_storage(self, storage_id: str) -> CloudStorageModel | None:
        def _get() -> CloudStorageModel | None:
            return CloudStorageModel.objects(id=UUID(storage_id)).first()

        try:
            return await asyncio.to_thread(_get)
        except Exception as exc:
            raise DatabaseUnavailableError(
                DatabaseErrorContext(
                    code="database_unavailable",
                    operation="read",
                    resource="cloud_storage",
                    retryable=True,
                ),
                cause=exc,
            ) from exc

    @staticmethod
    def serialize_cloud_storage(response: CloudStorageModel) -> dict:
        return {
            "id": str(response.id),
            "name": response.name,
            "description": response.description,
            "bucket_name": response.bucket_name,
            "file_path": response.file_path,
            "file_type": response.file_type,
            "created_at": response.created_at,
        }

    async def upload_file_to_gcs(self, file_name: str, file_bytes: bytes) -> GcsUploadResponse:
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET is not configured")

        with NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as temp_file:
            temp_file.write(file_bytes)
            temp_file_path = temp_file.name

        try:
            gcs_service = GCSService(bucket_name=self.bucket_name)
            destination_blob_name = f"uploads/{file_name}"
            upload_success = await asyncio.to_thread(
                gcs_service.upload_file,
                temp_file_path,
                destination_blob_name,
            )

            if not upload_success:
                raise ValueError("Google Cloud Storage upload failed.")

            cloud_storage_id = str(uuid4())
            record = CloudStorageModel(
                id=UUID(cloud_storage_id),
                name=file_name,
                description="Uploaded file to Google Cloud Storage.",
                bucket_name=self.bucket_name,
                file_path=f"gs://{self.bucket_name}/{destination_blob_name}",
                file_type="application/octet-stream",
            )
            await self.save_cloud_storage(record)

            return GcsUploadResponse(
                message="File uploaded successfully.",
                cloud_storage_id=cloud_storage_id,
            )
        finally:
            try:
                os.remove(temp_file_path)
            except OSError:
                pass

    async def list_files(self) -> list[str]:
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET is not configured")

        gcs_service = GCSService(bucket_name=self.bucket_name)
        return await asyncio.to_thread(gcs_service.list_files)

    async def info_file(self, blob_name: str) -> dict | None:
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET is not configured")

        gcs_service = GCSService(bucket_name=self.bucket_name)
        return await asyncio.to_thread(gcs_service.info_files, blob_name)

    async def download_file(self, blob_name: str) -> bool:
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET is not configured")

        gcs_service = GCSService(bucket_name=self.bucket_name)
        return await asyncio.to_thread(gcs_service.download_file, blob_name)
