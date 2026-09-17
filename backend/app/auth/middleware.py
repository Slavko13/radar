from collections import defaultdict, deque
from time import monotonic

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.service import COOKIE_NAME, AuthService

PUBLIC_API_PATHS = {
    "/api/auth/login",
    "/api/auth/status",
}


class AdminAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth: AuthService) -> None:
        super().__init__(app)
        self.auth = auth

    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or not path.startswith("/api") or path in PUBLIC_API_PATHS:
            return await call_next(request)
        token = request.cookies.get(COOKIE_NAME)
        authorization = request.headers.get("Authorization", "")
        if not token and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
        if not self.auth.validate_token(token):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        return await call_next(request)


class LoginRateLimiter:
    def __init__(self, limit: int = 5, window_seconds: int = 300) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.attempts: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client: str) -> bool:
        now = monotonic()
        attempts = self.attempts[client]
        while attempts and now - attempts[0] > self.window_seconds:
            attempts.popleft()
        if len(attempts) >= self.limit:
            return False
        attempts.append(now)
        return True

    def reset(self, client: str) -> None:
        self.attempts.pop(client, None)

