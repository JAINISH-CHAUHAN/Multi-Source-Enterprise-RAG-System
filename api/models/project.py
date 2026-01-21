import sqlalchemy as sa
import uuid
from api.core.database import metadata

projects = sa.Table(
    "projects",
    metadata,

    sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    sa.Column("workspace_id", sa.UUID(as_uuid=True), nullable=False),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("vector_store_path", sa.String, nullable=False),

    # Soft delete fields
    sa.Column("is_deleted", sa.Boolean, nullable=False, default=False),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),

    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    ),
)

# ✅ PARTIAL UNIQUE INDEX (Postgres-specific)
sa.Index(
    "uq_projects_workspace_name_active",
    projects.c.workspace_id,
    projects.c.name,
    unique=True,
    postgresql_where=projects.c.is_deleted.is_(False),
)
