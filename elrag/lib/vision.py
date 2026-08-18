import logging

from google.cloud import vision

from elrag.errors.api import IntegrationError


logger = logging.getLogger(__name__)


class VisionService:
    def __init__(self):
        self.client = vision.ImageAnnotatorClient()

    def detect_text_forgcs(self, gs_image_path: str):
        """Detect text in a Google Cloud Storage image."""
        try:
            image = vision.Image(source=vision.ImageSource(gcs_image_uri=gs_image_path))
            response = self.client.text_detection(image=image)
            texts = response.text_annotations
            if texts:
                return texts[0].description
            return ""
        except Exception as exc:
            logger.exception("Google Cloud Vision GCS detection failed")
            raise IntegrationError(
                source="vision",
                code="vision_detection_failed",
                message="Google Cloud Vision text detection failed.",
            ) from exc

    def detect_text(self, image_data: bytes):
        """Detect text in image bytes."""
        try:
            image = vision.Image(content=image_data)
            response = self.client.text_detection(image=image)
            texts = response.text_annotations
            if texts:
                return texts[0].description
            return ""
        except Exception as exc:
            logger.exception("Google Cloud Vision byte detection failed")
            raise IntegrationError(
                source="vision",
                code="vision_detection_failed",
                message="Google Cloud Vision text detection failed.",
            ) from exc
