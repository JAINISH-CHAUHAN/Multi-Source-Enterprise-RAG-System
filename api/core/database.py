from databases import Database
from sqlalchemy import MetaData
from api.core.config import settings

# Single shared metadata object
metadata = MetaData()

# Async database connection
database = Database(
    settings.DATABASE_URL,
    force_rollback=settings.APP_ENV == "test"
)
