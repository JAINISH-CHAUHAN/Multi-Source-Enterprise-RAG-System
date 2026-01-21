import sqlalchemy as sa
import uuid
from api.core.database import metadata

documents = sa.Table(
    "documents",
    metadata,

    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("project_id", sa.UUID(as_uuid=True), nullable=False),
    sa.Column("file_name", sa.String, nullable=False),
    sa.Column("source_type", sa.String, nullable=False),  # pdf, docx, sheet
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)
