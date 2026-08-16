from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from elrag.core.vision_be import VisionServiceBE
from elrag.models.schema import VisionResponse

vision_api = APIRouter()
vision_service = VisionServiceBE()


@vision_api.get("/vision/{vision_id}", response_model=VisionResponse)
async def get_vision_data(vision_id: str) -> JSONResponse:
    response = await vision_service.get_vision_response(vision_id)
    if response is None:
        return JSONResponse(status_code=404, content={"message": "Vision not found"})
    return JSONResponse(content=vision_service.serialize_vision_response(response))


@vision_api.post("/vision", response_model=VisionResponse)
async def extract_features(
    files: Annotated[UploadFile, File(description="Image file to analyze")],
) -> JSONResponse:
    data = await files.read()
    output = await vision_service.process_vision_bytes(data)
    return JSONResponse(status_code=200, content=output.model_dump())


@vision_api.post("/vision-gcs", response_model=VisionResponse)
async def extract_features(gcs_uri: str) -> JSONResponse:
    output = await vision_service.process_vision_gcs(gcs_uri)
    return JSONResponse(status_code=200, content=output.model_dump())
