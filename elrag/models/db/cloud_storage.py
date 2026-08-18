from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model

from elrag.models.base import register_model


@register_model
class CloudStorageModel(Model):
    """Persistent metadata for a Google Cloud Storage object."""

    __table_name__ = "cloud_storage"

    id = columns.UUID(primary_key=True)
    name = columns.Text()
    description = columns.Text()
    bucket_name = columns.Text()
    file_path = columns.Text()
    file_type = columns.Text()
    created_at = columns.DateTime()
