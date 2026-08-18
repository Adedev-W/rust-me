import logging

from google.cloud import storage

from elrag.errors.api import IntegrationError

logger = logging.getLogger(__name__)


class GCSService:
    def __init__(self, bucket_name: str):
        self.client = storage.Client(project="adsapt")
        self.bucket = self.client.bucket(bucket_name)

    def upload_file(self, local_file_path: str, destination_blob_name: str):
        """Upload a local file to Google Cloud Storage."""
        try:
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_filename(local_file_path)
            return True
        except Exception as exc:
            logger.exception("Google Cloud Storage upload failed")
            raise IntegrationError(
                source="gcs",
                code="gcs_upload_failed",
                message="Google Cloud Storage upload failed.",
            ) from exc

    def info_files(self, blob_name: str):
        """Return metadata for one Google Cloud Storage object."""
        try:
            blob = self.bucket.blob(blob_name)
            if blob.exists():
                info = {
                    "name": blob.name,
                    "size": blob.size,
                    "content_type": blob.content_type,
                    "updated": blob.updated,
                }
                return info
            return None
        except Exception as exc:
            logger.exception("Google Cloud Storage metadata lookup failed")
            raise IntegrationError(
                source="gcs",
                code="gcs_metadata_lookup_failed",
                message="Google Cloud Storage metadata lookup failed.",
            ) from exc

    def list_files(self):
        """Return object names in the configured bucket."""
        try:
            blobs = self.bucket.list_blobs()
            file_list = [blob.name for blob in blobs]
            return file_list
        except Exception as exc:
            logger.exception("Google Cloud Storage listing failed")
            raise IntegrationError(
                source="gcs",
                code="gcs_listing_failed",
                message="Google Cloud Storage listing failed.",
            ) from exc

    def download_file(self, source_blob_name: str):
        """Download one Google Cloud Storage object."""
        try:
            blob = self.bucket.blob(source_blob_name)
            blob.download_as_text()
            return True
        except Exception as exc:
            logger.exception("Google Cloud Storage download failed")
            raise IntegrationError(
                source="gcs",
                code="gcs_download_failed",
                message="Google Cloud Storage download failed.",
            ) from exc
