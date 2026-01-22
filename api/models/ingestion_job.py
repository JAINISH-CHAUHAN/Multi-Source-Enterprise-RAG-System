import sqlalchemy as sa
import uuid
from api.core.database import metadata

ingestion_jobs = sa.Table(
    "ingestion_jobs",
    metadata,

    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("project_id", sa.UUID(as_uuid=True), nullable=False),

    sa.Column("status", sa.String, nullable=False),  
    # pending | running | completed | failed

    sa.Column("error_message", sa.Text, nullable=True),

    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
)
