from __future__ import annotations

import asyncio
import json
from uuid import UUID, uuid4

from elrag.errors.database import DatabaseUnavailableError
from elrag.lib.vision import VisionService
from elrag.models.db.vision import VisionModel
from elrag.schemas.db.errors import DatabaseErrorSchema
from elrag.schemas.json.vision import VisionResponse


class VisionServiceBE:
    async def save_vision_response(self, response: VisionModel) -> VisionModel:
        try:
            await asyncio.to_thread(response.save)
        except Exception as exc:
            raise DatabaseUnavailableError(
                DatabaseErrorSchema(
                    code="database_unavailable",
                    operation="save",
                    resource="vision",
                    retryable=True,
                ),
                cause=exc,
            ) from exc
        return response

    async def get_vision_response(self, vision_id: str) -> VisionModel | None:
        def _get() -> VisionModel | None:
            return VisionModel.objects(id=UUID(vision_id)).first()

        try:
            return await asyncio.to_thread(_get)
        except Exception as exc:
            raise DatabaseUnavailableError(
                DatabaseErrorSchema(
                    code="database_unavailable",
                    operation="read",
                    resource="vision",
                    retryable=True,
                ),
                cause=exc,
            ) from exc

    @staticmethod
    def serialize_vision_response(response: VisionModel) -> VisionResponse:
        return VisionResponse(
            id=str(response.id),
            metadata=response.metadata,
            content=response.content,
        )

    async def process_vision_bytes(self, file_bytes: bytes) -> VisionResponse:
        vision_service = VisionService()
        output = await asyncio.to_thread(vision_service.detect_text, file_bytes)

        response = VisionResponse(
            id=str(uuid4()),
            metadata=None,
            content=output,
        )
        await self._persist_vision_response(
            response_id=response.id,
            gcs_uri=None,
            metadata=response.metadata,
            content=response.content,
        )
        return response

    async def process_vision_gcs(self, gcs_uri: str) -> VisionResponse:
        vision_service = VisionService()
        output = await asyncio.to_thread(vision_service.detect_text_forgcs, gcs_uri)

        response = VisionResponse(
            id=str(uuid4()),
            metadata=None,
            content=output,
        )
        await self._persist_vision_response(
            response_id=response.id,
            gcs_uri=gcs_uri,
            metadata=response.metadata,
            content=response.content,
        )
        return response

    async def _persist_vision_response(
        self,
        *,
        response_id: str,
        gcs_uri: str | None,
        metadata: dict | str | None,
        content: str | None,
    ) -> None:
        if isinstance(metadata, dict):
            metadata_value = json.dumps(metadata)
        else:
            metadata_value = metadata

        record = VisionModel(
            id=UUID(response_id),
            gcs_uri=gcs_uri,
            metadata=metadata_value,
            content=content,
        )
        await self.save_vision_response(record)
