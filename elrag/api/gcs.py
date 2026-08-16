from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from elrag.core.gcs_be import GCSServiceBE
from elrag.models.schema import GCSUploadResponse

gcs_api = APIRouter()
gcs_service = GCSServiceBE()


@gcs_api.post("/upload", response_model=GCSUploadResponse)
async def upload_file_to_gcs(
    file: Annotated[UploadFile, File(description="File to upload")],
) -> JSONResponse:
    try:
        file_bytes = await file.read()
        response = await gcs_service.upload_file_to_gcs(file.filename, file_bytes)
        return JSONResponse(status_code=200, content=response.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=500, content={"message": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"message": f"Terjadi kesalahan: {exc}"})


@gcs_api.get("/files")
async def list_files() -> JSONResponse:
    try:
        files = await gcs_service.list_files()
        return JSONResponse(status_code=200, content={"data": files})
    except ValueError as exc:
        return JSONResponse(status_code=500, content={"message": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"message": f"Terjadi kesalahan: {exc}"})


@gcs_api.get("/files/info")
async def info_file(blob_name: str) -> JSONResponse:
    try:
        info = await gcs_service.info_file(blob_name)
        if info is None:
            return JSONResponse(status_code=404, content={"message": "File not found"})
        return JSONResponse(status_code=200, content=info)
    except ValueError as exc:
        return JSONResponse(status_code=500, content={"message": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"message": f"Terjadi kesalahan: {exc}"})


@gcs_api.get("/files/download")
async def download_file(blob_name: str) -> JSONResponse:
    try:
        success = await gcs_service.download_file(blob_name)
        if not success:
            return JSONResponse(status_code=500, content={"message": "Failed to download file"})
        return JSONResponse(status_code=200, content={"message": "File downloaded"})
    except ValueError as exc:
        return JSONResponse(status_code=500, content={"message": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"message": f"Terjadi kesalahan: {exc}"})
