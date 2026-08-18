from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model

from elrag.models.base import register_model


@register_model
class DocumentAIModel(Model):
    """Persistent Document AI processing result."""

    __table_name__ = "document_ai"

    id = columns.UUID(primary_key=True)
    gcs_uri = columns.Text()
    filename = columns.Text()
    metadata = columns.Text()
    content = columns.Text()
