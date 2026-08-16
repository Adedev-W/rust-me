from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from elrag.core.docs_be import DocsServiceBE
from elrag.models.schema import DocumentAIResponseBytes, DocumentAIResponseGCS

docs_api = APIRouter()
docs_service = DocsServiceBE()


@docs_api.post("/documentai/gcs", response_model=DocumentAIResponseGCS)
async def process_documents_gcs(gcs_uri: str) -> JSONResponse:
    """Extracts text and structured data from a document stored in Google Cloud Storage using Document AI."""
    try:
        final_response = await docs_service.process_documents_gcs(gcs_uri)
        return JSONResponse(content=final_response.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=404, content={"message": str(exc)})


@docs_api.post("/documentai/bytes", response_model=DocumentAIResponseBytes)
async def process_documents_bytes(
    file: Annotated[UploadFile, File(description="Document file to process")],
) -> JSONResponse:
    """Extracts text and structured data from a document uploaded as bytes using Document AI."""
    file_bytes = await file.read()
    final_response = await docs_service.process_documents_bytes(
        file_bytes=file_bytes,
        filename=file.filename,
        mime_type=file.content_type,
    )
    return JSONResponse(content=final_response.model_dump())


@docs_api.get("/documentai/{response_id}")
async def get_documentai_response(response_id: str) -> JSONResponse:
    response = await docs_service.get_documentai_response(response_id)
    if response is None:
        return JSONResponse(status_code=404, content={"message": "Document AI response not found"})
    return JSONResponse(content=docs_service.serialize_documentai_response(response))
