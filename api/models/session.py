import sqlalchemy as sa
from api.core.database import metadata
import uuid

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
)
