from cassandra.cqlengine import columns
from cassandra.cqlengine.models import Model

from elrag.models.base import register_model


@register_model
class GoogleOAuthUserModel(Model):
    """Persistent Google OAuth user account."""

    __table_name__ = "google_oauth_user"

    google_sub = columns.Text(primary_key=True)
    email = columns.Text()
    name = columns.Text()
    picture = columns.Text()
    is_active = columns.Boolean(default=False)
    role = columns.Text(default="user")
    created_at = columns.DateTime()
    updated_at = columns.DateTime()
    last_login_at = columns.DateTime()
