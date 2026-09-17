import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import Settings

COOKIE_NAME = "lead_radar_admin"


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.password_hasher = PasswordHasher()

    def verify_password(self, candidate: str) -> bool:
        if self.settings.admin_password_hash:
            try:
                return self.password_hasher.verify(self.settings.admin_password_hash, candidate)
            except (VerificationError, InvalidHashError):
                return False
        if self.settings.is_production or not self.settings.admin_password:
            return False
        return secrets.compare_digest(candidate, self.settings.admin_password)

    def create_token(self) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": "admin",
                "iat": now,
                "exp": now + timedelta(hours=self.settings.auth_token_ttl_hours),
            },
            self.settings.app_secret_key,
            algorithm="HS256",
        )

    def validate_token(self, token: str | None) -> bool:
        if not token:
            return False
        try:
            payload = jwt.decode(token, self.settings.app_secret_key, algorithms=["HS256"])
        except jwt.PyJWTError:
            return False
        return payload.get("sub") == "admin"

