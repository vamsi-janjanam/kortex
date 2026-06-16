import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables before the test session; drop them after.

    If no database is reachable (e.g. running DB-free unit tests like the
    hermetic agent-workflow tests without Docker), skip table setup so those
    tests can still collect and run. Tests that actually need a session will
    surface their own connection error.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.exc import SQLAlchemyError

    import app.models  # noqa: F401 — registers all ORM models with Base
    from app.config import settings
    from app.models.base import Base

    engine = create_engine(settings.database_url)
    try:
        Base.metadata.create_all(engine)
    except SQLAlchemyError:
        engine.dispose()
        yield
        return

    yield
    Base.metadata.drop_all(engine)
    engine.dispose()
