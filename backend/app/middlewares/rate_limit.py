from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

@dataclass
class RateLimitRule:
    window_sec: int
    max_requests: int

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiter.
    ✅ Good for single-instance deployment
    ⚠️ For multi-instance production: move to Redis (same algorithm, shared store).
    """
    def __init__(self, app, rule: RateLimitRule, key_prefix: str = "rl"):
        super().__init__(app)
        self.rule = rule
        self.key_prefix = key_prefix
        self.buckets: Dict[str, Deque[float]] = defaultdict(deque)

    def _key(self, request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        return f"{self.key_prefix}:{ip}:{path}"

    async def dispatch(self, request: Request, call_next) -> Response:
        key = self._key(request)
        now = time.time()
        window_start = now - self.rule.window_sec

        q = self.buckets[key]
        while q and q[0] < window_start:
            q.popleft()

        if len(q) >= self.rule.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
                headers={"Retry-After": str(self.rule.window_sec)},
            )

        q.append(now)
        return await call_next(request)
