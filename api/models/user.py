import sqlalchemy as sa
from api.core.database import metadata
import uuid

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("org_id", sa.UUID(as_uuid=True), nullable=False),
    sa.Column("email", sa.String, unique=True, index=True, nullable=False),
    sa.Column("password_hash", sa.String, nullable=False),
    sa.Column("is_active", sa.Boolean, default=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)
