import sqlalchemy as sa
from api.core.database import metadata
import uuid

organizations = sa.Table(
    "organizations",
    metadata,
    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)
