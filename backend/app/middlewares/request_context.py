import uuid as uuidlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.security import decode_token

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuidlib.uuid4())
        tenant_id = None
        user_id = None

        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            try:
                payload = decode_token(token)
                tenant_id = payload.get("tenant_id")
                user_id = payload.get("sub")
            except Exception:
                pass

        request.state.request_id = request_id
        request.state.tenant_id = tenant_id
        request.state.user_id = user_id

        resp = await call_next(request)
        resp.headers["X-Request-ID"] = request_id
        return resp
