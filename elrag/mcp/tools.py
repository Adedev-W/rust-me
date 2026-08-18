from __future__ import annotations

import base64

from elrag.core.docs_be import DocsServiceBE
from elrag.core.gcs_be import GCSServiceBE
from elrag.core.vision_be import VisionServiceBE


_vision_service = VisionServiceBE()
_gcs_service = GCSServiceBE()
_docs_service = DocsServiceBE()


def _decode_bytes(file_bytes_b64: str) -> bytes:
    return base64.b64decode(file_bytes_b64)


def register_tools(mcp) -> None:
    @mcp.tool
    async def vision_process_bytes(file_bytes_b64: str) -> dict:
        """Process raw file bytes with Vision OCR and persist the response."""
        response = await _vision_service.process_vision_bytes(_decode_bytes(file_bytes_b64))
        return response.model_dump(by_alias=True)

    @mcp.tool
    async def vision_process_gcs(gcs_uri: str) -> dict:
        """Process a GCS object with Vision OCR and persist the response."""
        response = await _vision_service.process_vision_gcs(gcs_uri)
        return response.model_dump(by_alias=True)

    @mcp.tool
    async def gcs_upload_file(file_name: str, file_bytes_b64: str) -> dict:
        """Upload a file to GCS and persist the storage metadata."""
        response = await _gcs_service.upload_file_to_gcs(file_name, _decode_bytes(file_bytes_b64))
        return response.model_dump(by_alias=True)

    @mcp.tool
    async def gcs_list_files() -> list[str]:
        """List files in the configured GCS bucket."""
        return await _gcs_service.list_files()

    @mcp.tool
    async def gcs_info_file(blob_name: str) -> dict | None:
        """Fetch metadata for a GCS object."""
        return await _gcs_service.info_file(blob_name)

    @mcp.tool
    async def gcs_download_file(blob_name: str) -> dict:
        """Download a GCS object into the configured local destination."""
        success = await _gcs_service.download_file(blob_name)
        return {
            "message": "File downloaded successfully." if success else "File download failed.",
            "success": success,
        }

    @mcp.tool
    async def docs_process_gcs(gcs_uri: str) -> dict:
        """Process a GCS document with Document AI and persist the response."""
        response = await _docs_service.process_documents_gcs(gcs_uri)
        return response.model_dump(by_alias=True)

    @mcp.tool
    async def docs_process_bytes(
        file_bytes_b64: str,
        filename: str | None = None,
        mime_type: str | None = None,
    ) -> dict:
        """Process raw file bytes with Document AI and persist the response."""
        response = await _docs_service.process_documents_bytes(
            file_bytes=_decode_bytes(file_bytes_b64),
            filename=filename,
            mime_type=mime_type,
        )
        return response.model_dump(by_alias=True)
