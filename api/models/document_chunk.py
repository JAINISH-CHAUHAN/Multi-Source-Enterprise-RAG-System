import sqlalchemy as sa
import uuid
from api.core.database import metadata

document_chunks = sa.Table(
    "document_chunks",
    metadata,

    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("document_id", sa.UUID(as_uuid=True), nullable=False),
    sa.Column("vector_id", sa.String, nullable=False),
    sa.Column("chunk_index", sa.Integer, nullable=False),
    sa.Column("chunk_text", sa.Text, nullable=True),  # Optional: for audit/debug
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),

    # Foreign key relationship
    sa.ForeignKeyConstraint(
        ["document_id"],
        ["documents.id"],
        ondelete="CASCADE"
    ),

    # Ensure unique chunk per document
    sa.UniqueConstraint("document_id", "chunk_index", name="uix_document_chunk"),
)

# Index for efficient deletion lookups
sa.Index("idx_chunks_document_id", document_chunks.c.document_id)
