from __future__ import annotations

import asyncio
import json
import os
from uuid import UUID, uuid4

from google.protobuf.json_format import MessageToDict

from elrag.errors.database import DatabaseSerializationError, DatabaseUnavailableError
from elrag.lib.documentai import DocumentAIService
from elrag.lib.storage_rest import GCSService
from elrag.models.db.document_ai import DocumentAIModel
from elrag.schemas.db.errors import DatabaseErrorSchema
from elrag.schemas.json.document_ai import DocumentAiBytesResponse, DocumentAiGcsResponse


class DocsServiceBE:
    def __init__(self) -> None:
        self.bucket_name = os.environ.get("GCS_BUCKET")

    async def save_documentai_response(self, response: DocumentAIModel) -> DocumentAIModel:
        try:
            await asyncio.to_thread(response.save)
        except Exception as exc:
            raise DatabaseUnavailableError(
                DatabaseErrorSchema(
                    code="database_unavailable",
                    operation="save",
                    resource="document_ai",
                    retryable=True,
                ),
                cause=exc,
            ) from exc
        return response

    async def get_documentai_response(self, response_id: str) -> DocumentAIModel | None:
        def _get() -> DocumentAIModel | None:
            return DocumentAIModel.objects(id=UUID(response_id)).first()

        try:
            return await asyncio.to_thread(_get)
        except Exception as exc:
            raise DatabaseUnavailableError(
                DatabaseErrorSchema(
                    code="database_unavailable",
                    operation="read",
                    resource="document_ai",
                    retryable=True,
                ),
                cause=exc,
            ) from exc

    @staticmethod
    def serialize_documentai_response(response: DocumentAIModel) -> DocumentAiGcsResponse | DocumentAiBytesResponse:
        metadata = _decode_metadata(response.metadata)
        if response.gcs_uri:
            return DocumentAiGcsResponse(
                id=str(response.id),
                gcs_uri=response.gcs_uri,
                metadata=metadata,
                content=response.content,
            )
        return DocumentAiBytesResponse(
            id=str(response.id),
            filename=response.filename,
            metadata=metadata,
            content=response.content,
        )

    async def process_documents_gcs(self, gcs_uri: str) -> DocumentAiGcsResponse:
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET is not configured")
        gcs_service = GCSService(self.bucket_name)
        gcs_info = await asyncio.to_thread(gcs_service.info_files, gcs_uri)
        if not gcs_info:
            raise ValueError("GCS file not found")

        document_service = DocumentAIService("us")
        document = await asyncio.to_thread(
            document_service.process_document_gcs,
            project_id="adesapt",
            location="us",
            processor_id="2ff00dc23a9dd3f8",
            gcs_input_uri=gcs_info["name"],
            mime_type=gcs_info["content_type"],
        )

        if document is None:
            raise ValueError("Document AI processing failed.")

        response = DocumentAiGcsResponse(
            id=str(uuid4()),
            gcs_uri=gcs_info["name"],
            metadata=MessageToDict(document._pb),
            content=document.text,
        )
        await self._persist_documentai_response(
            response_id=response.id,
            gcs_uri=response.gcs_uri,
            filename=None,
            metadata=response.metadata,
            content=response.content,
        )
        return response

    async def process_documents_bytes(
        self,
        file_bytes: bytes,
        filename: str | None,
        mime_type: str | None,
    ) -> DocumentAiBytesResponse:
        document_service = DocumentAIService("us")
        document = await asyncio.to_thread(
            document_service.process_document,
            project_id="adsapt",
            location="us",
            processor_id="2ff00dc23a9dd3f8",
            files=file_bytes,
            mime_type=mime_type,
        )

        if document is None:
            raise ValueError("Document AI processing failed.")

        response = DocumentAiBytesResponse(
            id=str(uuid4()),
            filename=filename,
            metadata=MessageToDict(document._pb),
            content=document.text,
        )
        await self._persist_documentai_response(
            response_id=response.id,
            gcs_uri=None,
            filename=response.filename,
            metadata=response.metadata,
            content=response.content,
        )
        return response

    async def _persist_documentai_response(
        self,
        *,
        response_id: str,
        gcs_uri: str | None,
        filename: str | None,
        metadata: dict | None,
        content: str | None,
    ) -> None:
        record = DocumentAIModel(
            id=UUID(response_id),
            gcs_uri=gcs_uri,
            filename=filename,
            metadata="" if metadata is None else json.dumps(metadata),
            content=content,
        )
        await self.save_documentai_response(record)


def _decode_metadata(raw_metadata: str | None) -> dict | None:
    if not raw_metadata:
        return None
    try:
        return json.loads(raw_metadata)
    except json.JSONDecodeError as exc:
        raise DatabaseSerializationError(
            DatabaseErrorSchema(
                code="database_serialization_error",
                operation="deserialize",
                resource="document_ai.metadata",
                retryable=False,
            ),
            cause=exc,
        ) from exc
