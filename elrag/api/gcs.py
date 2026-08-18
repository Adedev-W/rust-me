from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from elrag.api.error_handling import build_error_response
from elrag.core.gcs_be import GCSServiceBE
from elrag.errors.api import IntegrationError
from elrag.schemas.json.gcs import (
    GcsDownloadResponse,
    GcsFileInfoResponse,
    GcsFileListResponse,
    GcsUploadResponse,
)

gcs_api = APIRouter()
gcs_service = GCSServiceBE()


@gcs_api.post("/upload", response_model=GcsUploadResponse)
async def upload_file_to_gcs(
    request: Request,
    file: Annotated[UploadFile, File(description="File to upload")],
) -> JSONResponse:
    try:
        file_bytes = await file.read()
        response = await gcs_service.upload_file_to_gcs(file.filename, file_bytes)
        return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))
    except ValueError as exc:
        return build_error_response(
            request,
            status_code=500,
            code="gcs_configuration_error",
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
    except Exception as exc:
        return build_error_response(
            request,
            status_code=502,
            code="gcs_upload_failed",
            message="Google Cloud Storage upload failed.",
            exception=exc,
        )


@gcs_api.get("/files", response_model=GcsFileListResponse)
async def list_files(request: Request) -> JSONResponse:
    try:
        files = await gcs_service.list_files()
        return JSONResponse(
            status_code=200,
            content=GcsFileListResponse(data=files).model_dump(by_alias=True),
        )
    except ValueError as exc:
        return build_error_response(
            request,
            status_code=500,
            code="gcs_configuration_error",
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


@gcs_api.get("/files/info", response_model=GcsFileInfoResponse)
async def info_file(request: Request, blob_name: str) -> JSONResponse:
    try:
        info = await gcs_service.info_file(blob_name)
        if info is None:
            return build_error_response(
                request,
                status_code=404,
                code="gcs_file_not_found",
                message="Google Cloud Storage file was not found.",
            )
        response = GcsFileInfoResponse(**info)
        return JSONResponse(status_code=200, content=response.model_dump(by_alias=True, mode="json"))
    except ValueError as exc:
        return build_error_response(
            request,
            status_code=500,
            code="gcs_configuration_error",
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


@gcs_api.get("/files/download", response_model=GcsDownloadResponse)
async def download_file(request: Request, blob_name: str) -> JSONResponse:
    try:
        success = await gcs_service.download_file(blob_name)
        if not success:
            return build_error_response(
                request,
                status_code=500,
                code="gcs_download_failed",
                message="Google Cloud Storage file download failed.",
            )
        return JSONResponse(
            status_code=200,
            content=GcsDownloadResponse(
                message="File downloaded successfully.",
                success=True,
            ).model_dump(by_alias=True),
        )
    except ValueError as exc:
        return build_error_response(
            request,
            status_code=500,
            code="gcs_configuration_error",
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
