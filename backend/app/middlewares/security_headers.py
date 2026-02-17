from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        resp = await call_next(request)

        # Basic hardening
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS only if behind HTTPS (reverse proxy should terminate TLS)
        # Enable when deployed with HTTPS:
        # resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return resp
