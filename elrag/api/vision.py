from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from elrag.api.error_handling import build_error_response
from elrag.core.vision_be import VisionServiceBE
from elrag.errors.api import IntegrationError
from elrag.schemas.json.vision import VisionResponse

vision_api = APIRouter()
vision_service = VisionServiceBE()


@vision_api.get("/vision/{vision_id}", response_model=VisionResponse)
async def get_vision_data(request: Request, vision_id: UUID) -> JSONResponse:
    response = await vision_service.get_vision_response(str(vision_id))
    if response is None:
        return build_error_response(
            request=request,
            status_code=404,
            code="vision_not_found",
            message="Vision record was not found.",
        )
    return JSONResponse(
        content=vision_service.serialize_vision_response(response).model_dump(by_alias=True)
    )


@vision_api.post("/vision", response_model=VisionResponse)
async def extract_features(
    request: Request,
    files: Annotated[UploadFile, File(description="Image file to analyze")],
) -> JSONResponse:
    try:
        data = await files.read()
        output = await vision_service.process_vision_bytes(data)
        return JSONResponse(status_code=200, content=output.model_dump(by_alias=True))
    except IntegrationError as exc:
        return build_error_response(
            request,
            status_code=502,
            code=exc.code,
            message=exc.message,
            source=exc.source,
            exception=exc,
        )


@vision_api.post("/vision-gcs", response_model=VisionResponse)
async def extract_features_gcs(request: Request, gcs_uri: str) -> JSONResponse:
    try:
        output = await vision_service.process_vision_gcs(gcs_uri)
        return JSONResponse(status_code=200, content=output.model_dump(by_alias=True))
    except IntegrationError as exc:
        return build_error_response(
            request,
            status_code=502,
            code=exc.code,
            message=exc.message,
            source=exc.source,
            exception=exc,
        )
