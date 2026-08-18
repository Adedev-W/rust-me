from elrag.schemas.json.agent import AgentRunRequest, AgentRunResponse
from elrag.schemas.json.auth import (
    AuthCallbackResponse,
    AuthMeResponse,
    AuthenticatedUserResponse,
)
from elrag.schemas.json.document_ai import (
    DocumentAiBytesRequest,
    DocumentAiBytesResponse,
    DocumentAiGcsRequest,
    DocumentAiGcsResponse,
)
from elrag.schemas.json.gcs import (
    GcsDownloadResponse,
    GcsFileInfoResponse,
    GcsFileListResponse,
    GcsUploadResponse,
)
from elrag.schemas.json.maps import (
    GoogleMapsAutocompleteResponse,
    RouteRequest,
)
from elrag.schemas.json.vision import VisionResponse

DocumentAIResponseGCS = DocumentAiGcsResponse
DocumentAIResponseBytes = DocumentAiBytesResponse
DocumentAIRequestGCS = DocumentAiGcsRequest
DocumentAIRequestBytes = DocumentAiBytesRequest
GCSUploadResponse = GcsUploadResponse
GMSResponse = GoogleMapsAutocompleteResponse
