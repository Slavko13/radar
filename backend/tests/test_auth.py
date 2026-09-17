from argon2 import PasswordHasher

from app.auth.service import AuthService
from app.config import Settings


def test_development_password_and_token_roundtrip() -> None:
    auth = AuthService(
        Settings(
            environment="development",
            admin_password="correct horse",
            app_secret_key="test-secret-key-used-only-for-unit-tests",
        )
    )
    assert auth.verify_password("correct horse") is True
    assert auth.verify_password("wrong") is False
    assert auth.validate_token(auth.create_token()) is True
    assert auth.validate_token("invalid-token") is False


def test_argon_hash_takes_precedence() -> None:
    password_hash = PasswordHasher().hash("secure password")
    auth = AuthService(
        Settings(
            environment="production",
            admin_password="ignored",
            admin_password_hash=password_hash,
            app_secret_key="a-production-secret-key-with-32-characters",
        )
    )
    assert auth.verify_password("secure password") is True
    assert auth.verify_password("ignored") is False


def test_production_requires_secure_configuration() -> None:
    settings = Settings(
        environment="production",
        app_secret_key="short",
        admin_password_hash=None,
    )
    try:
        settings.validate_security()
    except ValueError as exc:
        assert "APP_SECRET_KEY" in str(exc)
    else:
        raise AssertionError("Insecure production configuration must be rejected")
