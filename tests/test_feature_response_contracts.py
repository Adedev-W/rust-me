from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from elrag.api.docs import docs_api
from elrag.api.gcs import gcs_api
from elrag.api.vision import vision_api
from elrag.schemas.json.document_ai import DocumentAiBytesResponse
from elrag.schemas.json.gcs import GcsUploadResponse
from elrag.schemas.json.vision import VisionResponse


class FeatureResponseContractTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(vision_api)
        self.app.include_router(gcs_api)
        self.app.include_router(docs_api)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_vision_endpoint_returns_json_schema(self) -> None:
        output = VisionResponse(id="vision-1", metadata=None, content="detected text")

        with patch(
            "elrag.api.vision.vision_service.process_vision_bytes",
            new=AsyncMock(return_value=output),
        ):
            response = await self.client.post(
                "/vision",
                files={"files": ("image.png", b"image-bytes", "image/png")},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"id": "vision-1", "metadata": None, "content": "detected text"},
            response.json(),
        )

    async def test_gcs_endpoint_returns_camel_case_json_schema(self) -> None:
        output = GcsUploadResponse(
            message="File uploaded successfully.",
            cloud_storage_id="storage-1",
        )

        with patch(
            "elrag.api.gcs.gcs_service.upload_file_to_gcs",
            new=AsyncMock(return_value=output),
        ):
            response = await self.client.post(
                "/upload",
                files={"file": ("document.pdf", b"document-bytes", "application/pdf")},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "message": "File uploaded successfully.",
                "cloudStorageId": "storage-1",
            },
            response.json(),
        )

    async def test_document_ai_endpoint_returns_json_schema(self) -> None:
        output = DocumentAiBytesResponse(
            id="document-1",
            filename="document.pdf",
            metadata={"pages": 1},
            content="document text",
        )

        with patch(
            "elrag.api.docs.docs_service.process_documents_bytes",
            new=AsyncMock(return_value=output),
        ):
            response = await self.client.post(
                "/documentai/bytes",
                files={"file": ("document.pdf", b"document-bytes", "application/pdf")},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "id": "document-1",
                "filename": "document.pdf",
                "metadata": {"pages": 1},
                "content": "document text",
            },
            response.json(),
        )


if __name__ == "__main__":
    unittest.main()
