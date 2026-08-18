from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from elrag.api.error_handling import build_error_response
from elrag.core.docs_be import DocsServiceBE
from elrag.errors.api import IntegrationError
from elrag.schemas.json.document_ai import DocumentAiBytesResponse, DocumentAiGcsResponse

docs_api = APIRouter()
docs_service = DocsServiceBE()


@docs_api.post("/documentai/gcs", response_model=DocumentAiGcsResponse)
async def process_documents_gcs(request: Request, gcs_uri: str) -> JSONResponse:
    """Extracts text and structured data from a document stored in Google Cloud Storage using Document AI."""
    try:
        final_response = await docs_service.process_documents_gcs(gcs_uri)
        return JSONResponse(content=final_response.model_dump(by_alias=True))
    except ValueError as exc:
        status_code = 404 if str(exc) == "GCS file not found" else 502
        code = "document_not_found" if status_code == 404 else "document_ai_processing_failed"
        return build_error_response(
            request,
            status_code=status_code,
            code=code,
            message=str(exc),
            exception=exc,
        )
    except IntegrationError as exc:
        return build_error_response(
            request,
            status_code=502,
            code=exc.code,
            message=exc.message,
            source=exc.source,
            exception=exc,
        )


@docs_api.post("/documentai/bytes", response_model=DocumentAiBytesResponse)
async def process_documents_bytes(
    request: Request,
    file: Annotated[UploadFile, File(description="Document file to process")],
) -> JSONResponse:
    """Extracts text and structured data from a document uploaded as bytes using Document AI."""
    try:
        file_bytes = await file.read()
        final_response = await docs_service.process_documents_bytes(
            file_bytes=file_bytes,
            filename=file.filename,
            mime_type=file.content_type,
        )
        return JSONResponse(content=final_response.model_dump(by_alias=True))
    except IntegrationError as exc:
        return build_error_response(
            request,
            status_code=502,
            code=exc.code,
            message=exc.message,
            source=exc.source,
            exception=exc,
        )


@docs_api.get("/documentai/{response_id}")
async def get_documentai_response(request: Request, response_id: UUID) -> JSONResponse:
    response = await docs_service.get_documentai_response(str(response_id))
    if response is None:
        return build_error_response(
            request,
            status_code=404,
            code="document_ai_not_found",
            message="Document AI response was not found.",
        )
    return JSONResponse(
        content=docs_service.serialize_documentai_response(response).model_dump(
            by_alias=True
        )
    )
