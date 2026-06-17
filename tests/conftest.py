import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


@pytest.fixture(scope="session", autouse=True)
def _bypass_api_key_auth():
    """Disable the X-API-Key gate for the test session.

    ``require_api_key`` reads ``settings.api_key``/``settings.app_env`` live on
    each request. A populated ``.env`` (non-empty ``API_KEY``) would otherwise
    make every authenticated endpoint return 401 in tests, which don't send the
    header. Force the development bypass (empty key + development env) so the
    suite is green regardless of the ambient ``.env``.
    """
    from app.config import settings

    saved = (settings.api_key, settings.app_env)
    settings.api_key = ""
    settings.app_env = "development"
    yield
    settings.api_key, settings.app_env = saved


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
