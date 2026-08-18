import logging

from google.api_core.client_options import ClientOptions
from google.cloud import documentai

from elrag.errors.api import IntegrationError


logger = logging.getLogger(__name__)


class DocumentAIService:
    def __init__(self, location: str):
        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")

        self.client = documentai.DocumentProcessorServiceClient(client_options=opts)

    def process_document_gcs(
        self,
        project_id: str,
        location: str,
        processor_id: str,
        gcs_input_uri: str,
        mime_type: str,
    ):
        try:
            name = self.client.processor_path(
                project_id,
                location,
                processor_id,
            )
            request = documentai.ProcessRequest(
                name=name,
                gcs_document=documentai.GcsDocument(
                    gcs_uri=gcs_input_uri,
                    mime_type=mime_type,
                ),
            )

            result = self.client.process_document(request=request)

            return result.document

        except Exception as exc:
            logger.exception("Document AI processing failed")
            raise IntegrationError(
                source="document_ai",
                code="document_ai_processing_failed",
                message="Document AI processing failed.",
            ) from exc

    def process_document(
        self,
        project_id: str,
        location: str,
        processor_id: str,
        files: bytes,
        mime_type: str,
    ):
        try:
            name = self.client.processor_path(
                project_id,
                location,
                processor_id,
            )
            request = documentai.ProcessRequest(
                name=name,
                raw_document=documentai.RawDocument(
                    content=files,
                    mime_type=mime_type
                ),
            )

            result = self.client.process_document(request=request)

            return result.document

        except Exception as exc:
            logger.exception("Document AI processing failed")
            raise IntegrationError(
                source="document_ai",
                code="document_ai_processing_failed",
                message="Document AI processing failed.",
            ) from exc


