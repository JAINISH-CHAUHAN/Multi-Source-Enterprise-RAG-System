from sqlalchemy import create_engine
from api.core.config import settings
from api.core.database import metadata

# IMPORTANT: import models so tables register themselves
from api.models import user
from api.models import organization
from api.models import session


def init():
    engine = create_engine(
        settings.DATABASE_URL.replace("+asyncpg", "")
    )
    metadata.create_all(engine)


if __name__ == "__main__":
    init()
