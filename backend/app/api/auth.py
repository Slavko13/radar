from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth.middleware import LoginRateLimiter
from app.auth.service import COOKIE_NAME, AuthService
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
auth_service = AuthService(settings)
rate_limiter = LoginRateLimiter()


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class AuthStatus(BaseModel):
    authenticated: bool


@router.post("/login", response_model=AuthStatus)
async def login(payload: LoginRequest, request: Request, response: Response) -> AuthStatus:
    client = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts")
    if not auth_service.verify_password(payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid password")
    rate_limiter.reset(client)
    response.set_cookie(
        COOKIE_NAME,
        auth_service.create_token(),
        max_age=settings.auth_token_ttl_hours * 3600,
        httponly=True,
        secure=settings.secure_cookie_enabled,
        samesite="lax",
        path="/",
    )
    return AuthStatus(authenticated=True)


@router.get("/status", response_model=AuthStatus)
async def auth_status(request: Request) -> AuthStatus:
    return AuthStatus(authenticated=auth_service.validate_token(request.cookies.get(COOKIE_NAME)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME, path="/", secure=settings.secure_cookie_enabled, samesite="lax"
    )
