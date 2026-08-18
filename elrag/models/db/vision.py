from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model

from elrag.models.base import register_model


@register_model
class VisionModel(Model):
    """Persistent Vision processing result."""

    __table_name__ = "vision"

    id = columns.UUID(primary_key=True)
    description = columns.Text()
    metadata = columns.Text()
    content = columns.Text()
