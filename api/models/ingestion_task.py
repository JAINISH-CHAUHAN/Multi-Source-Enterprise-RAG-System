import sqlalchemy as sa
from api.core.database import metadata

ingestion_tasks = sa.Table(
    "ingestion_tasks",
    metadata,

    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    sa.Column("task_type", sa.String, nullable=False),  # ingest | delete
    sa.Column("document_id", sa.UUID(as_uuid=True), nullable=False),
    sa.Column("job_id", sa.UUID(as_uuid=True), nullable=True),  # Link to ingestion_job
    sa.Column("status", sa.String, nullable=False, server_default="pending"),  
    # pending | processing | completed | failed
    sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("error_message", sa.Text, nullable=True),
    sa.Column("metadata", sa.JSON, nullable=True),  # Additional task-specific data
    
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),

    # Foreign key relationships
    sa.ForeignKeyConstraint(
        ["document_id"],
        ["documents.id"],
        ondelete="CASCADE"
    ),
    sa.ForeignKeyConstraint(
        ["job_id"],
        ["ingestion_jobs.id"],
        ondelete="SET NULL"
    ),

    # Ensure valid values
    sa.CheckConstraint(
        "task_type IN ('ingest', 'delete')",
        name="tasks_type_check"
    ),
    sa.CheckConstraint(
        "status IN ('pending', 'processing', 'completed', 'failed')",
        name="tasks_status_check"
    ),
)

# Index for efficient queue polling
sa.Index("idx_tasks_status_created", ingestion_tasks.c.status, ingestion_tasks.c.created_at)
