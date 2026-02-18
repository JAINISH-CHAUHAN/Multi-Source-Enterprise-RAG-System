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
    
    # Content-addressed registry fields
    sa.Column("file_hash", sa.String, nullable=True),  # SHA-256 hash for deduplication
    sa.Column("status", sa.String, nullable=False, server_default="pending"),  
    # Status: pending | processing | active | deleting | failed
    sa.Column("chunk_count", sa.Integer, nullable=True),
    sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
    
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    
    # Ensure status is valid
    sa.CheckConstraint(
        "status IN ('pending', 'processing', 'active', 'deleting', 'failed')",
        name="documents_status_check"
    ),
)

# Index for deduplication: same file content cannot exist twice in same project
# Partial index that only applies when is_deleted = FALSE
sa.Index(
    "uix_documents_hash_project",
    documents.c.file_hash,
    documents.c.project_id,
    unique=True,
    postgresql_where=(documents.c.is_deleted == False)
)

