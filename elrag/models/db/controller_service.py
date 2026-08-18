from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model

from elrag.models.base import register_model


@register_model
class ControllerServiceModel(Model):
    """Persistent quota configuration for a controller service."""

    __table_name__ = "controller_services"

    id = columns.UUID(primary_key=True)
    cs_id = columns.UUID()
    vision_limit = columns.Integer()
    gcs_limit = columns.Integer()
    documentai_limit = columns.Integer()
    created_at = columns.DateTime()
