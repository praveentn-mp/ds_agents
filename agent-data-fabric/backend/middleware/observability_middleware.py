"""Observability middleware — capture LLM call metrics."""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("adf.observability")


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration = int((time.monotonic() - start) * 1000)

        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} ({duration}ms)"
        )
        response.headers["X-Request-Duration-Ms"] = str(duration)
        return response
