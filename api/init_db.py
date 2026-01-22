from sqlalchemy import create_engine
from api.core.config import settings
from api.core.database import metadata

# IMPORTANT: import all models so tables register
from api.models import user
from api.models import organization
from api.models import session
from api.models import project   # <-- NEW
from api.models import document
from api.models import ingestion_job



def init():
    engine = create_engine(
        settings.DATABASE_URL.replace("+asyncpg", "")
    )
    metadata.create_all(engine)

if __name__ == "__main__":
    init()
