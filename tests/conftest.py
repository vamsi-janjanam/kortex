import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables before the test session; drop them after."""
    from sqlalchemy import create_engine

    import app.models  # noqa: F401 — registers all ORM models with Base
    from app.config import settings
    from app.models.base import Base

    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()
