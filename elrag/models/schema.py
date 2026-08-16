from typing import Any, Optional
from pydantic import BaseModel, Field

#DocumentAI Schema
class DocumentAIResponseGCS(BaseModel):
    id: str = Field(..., description="Unique document record identifier")
    gcs_uri: Optional[str] = Field(
        None, description="Google Cloud Storage URI for the document"
    )
    metadata: Optional[dict] = Field(
        None, description="Optional metadata or extracted text summary"
    )
    content: Optional[str] = Field(None, description="Optional raw content or OCR text")

class DocumentAIResponseBytes(BaseModel):
    id: str = Field(..., description="Unique document record identifier")
    filename: Optional[str] = Field(
        None, description="Name of the uploaded file"
    )
    metadata: Optional[dict] = Field(
        None, description="Optional metadata or extracted text summary"
    )
    content: Optional[str] = Field(None, description="Optional raw content or OCR text")

class DocumentAIRequestGCS(BaseModel):
    gcs_uri: str = Field(..., description="Google Cloud Storage URI for the document")
    mime_type: str = Field(..., description="MIME type of the document (e.g., application/pdf, image/jpeg)")

class DocumentAIRequestBytes(BaseModel):
    files: bytes = Field(..., description="The document files to be processed")
    mime_type: str = Field(..., description="MIME type of the document (e.g., application/pdf, image/jpeg)")


class GCSUploadResponse(BaseModel):
    message: str = Field(..., description="Response message")
    cloud_storage_id: Optional[str] = Field(
        None, description="ID of the created cloud storage record if upload is successful"
    )


#Vision Schema

class Vision(BaseModel):
    id: str = Field(..., description="Unique vision record identifier")
    gcs_uri: Optional[str] = Field(
        None, description="Google Cloud Storage URI for the image or document"
    )
    
    metadata: Optional[str] = Field(
        None, description="Optional metadata or extracted text summary"
    )
    content: Optional[str] = Field(None, description="Optional raw content or OCR text")

class VisionResponse(BaseModel):
    id: str = Field(..., description="Unique vision record identifier")
    metadata: Optional[str] = Field(
        None, description="Optional metadata or extracted text summary"
    )
    content: Optional[str] = Field(None, description="Optional raw content or OCR text")

class GMSResponse(BaseModel):
    input_text: str = Field(..., description="Input text for autocomplete")
    language_code: Optional[str] = Field(None, description="Optional language code for autocomplete")
    language_detection: str = Field(..., description="Language detection result for the input text")


class AgentRunRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(None, min_length=1, max_length=128)
    stream: bool = False


class AgentRunResponse(BaseModel):
    run_id: Optional[str] = None
    session_id: Optional[str] = None
    content: Any



class RouteRequest(BaseModel):
    origin: tuple[float, float]
    destination: tuple[float, float]
