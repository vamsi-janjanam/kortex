"""Security primitives for the Kortex API.

Provides:
- ``require_api_key``: a FastAPI dependency enforcing an ``X-API-Key`` header.
- ``limiter``: a shared ``slowapi`` rate limiter, defined here (rather than in
  ``main.py``) so endpoint modules can import it for ``@limiter.limit(...)``
  decorators without creating a circular import with ``app.main``.
"""

import logging
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)

# Shared rate limiter. Defined in this module to avoid a circular import:
# main.py imports this, and endpoint modules also import it for decorators.
limiter = Limiter(key_func=get_remote_address)

# auto_error=False so we can implement the development-mode passthrough below
# and emit a uniform 401 message rather than FastAPI's default.
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    """Validate the ``X-API-Key`` request header.

    Behavior:
    - If ``settings.api_key`` is configured (non-empty), the request must send a
      matching ``X-API-Key`` header. Comparison uses ``secrets.compare_digest``
      for constant-time matching. A missing or wrong key yields HTTP 401.
    - If ``settings.api_key`` is empty/unset:
        * In development (``settings.app_env == "development"``) the request is
          allowed through so local dev isn't blocked. A warning is logged.
        * In any other environment, the request is rejected with HTTP 401 to
          prevent shipping an unauthenticated API to production.
    """
    expected = settings.api_key

    if not expected:
        if settings.app_env == "development":
            logger.warning(
                "API_KEY is not set; allowing request in development mode. "
                "Set API_KEY before any non-local deployment."
            )
            return
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    if api_key is None or not secrets.compare_digest(api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
