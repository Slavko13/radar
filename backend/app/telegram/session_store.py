import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class SessionStoreError(RuntimeError):
    pass


class EncryptedSessionStore:
    """Stores StringSession values encrypted and outside the database."""

    def __init__(self, root: str, secret_key: str) -> None:
        self.root = Path(root).resolve()
        key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode("utf-8")).digest())
        self.cipher = Fernet(key)

    def write(self, telegram_user_id: int, session: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"account-{telegram_user_id}.session.enc"
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_bytes(self.cipher.encrypt(session.encode("utf-8")))
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(path)
        return path.name

    def read(self, reference: str) -> str:
        path = self._safe_path(reference)
        try:
            return self.cipher.decrypt(path.read_bytes()).decode("utf-8")
        except (OSError, InvalidToken, UnicodeDecodeError) as exc:
            raise SessionStoreError("Telegram session cannot be decrypted") from exc

    def delete(self, reference: str) -> None:
        path = self._safe_path(reference)
        path.unlink(missing_ok=True)

    def write_api_credentials(self, api_id: int, api_hash: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "api-credentials.enc"
        temporary_path = path.with_suffix(".tmp")
        payload = json.dumps({"api_id": api_id, "api_hash": api_hash}).encode("utf-8")
        temporary_path.write_bytes(self.cipher.encrypt(payload))
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(path)

    def read_api_credentials(self) -> tuple[int, str] | None:
        path = self.root / "api-credentials.enc"
        if not path.exists():
            return None
        try:
            payload = json.loads(self.cipher.decrypt(path.read_bytes()).decode("utf-8"))
            return int(payload["api_id"]), str(payload["api_hash"])
        except (OSError, InvalidToken, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            raise SessionStoreError("Telegram API credentials cannot be decrypted") from exc

    def write_notification_bot(self, token: str, chat_id: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "notification-bot.enc"
        temporary_path = path.with_suffix(".tmp")
        payload = json.dumps({"token": token, "chat_id": chat_id}).encode("utf-8")
        temporary_path.write_bytes(self.cipher.encrypt(payload))
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(path)

    def read_notification_bot(self) -> tuple[str, str] | None:
        path = self.root / "notification-bot.enc"
        if not path.exists():
            return None
        try:
            payload = json.loads(self.cipher.decrypt(path.read_bytes()).decode("utf-8"))
            return str(payload["token"]), str(payload["chat_id"])
        except (OSError, InvalidToken, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
            raise SessionStoreError("Notification bot credentials cannot be decrypted") from exc

    def delete_notification_bot(self) -> None:
        (self.root / "notification-bot.enc").unlink(missing_ok=True)

    def write_ai_credentials(
        self, provider: str, api_key: str, model: str, base_url: str
    ) -> None:
        self._write_json(
            "ai-credentials.enc",
            {
                "provider": provider,
                "api_key": api_key,
                "model": model,
                "base_url": base_url,
            },
        )

    def read_ai_credentials(self) -> dict[str, str] | None:
        payload = self._read_json("ai-credentials.enc", "AI credentials cannot be decrypted")
        if payload is None:
            return None
        try:
            return {
                "provider": str(payload["provider"]),
                "api_key": str(payload["api_key"]),
                "model": str(payload["model"]),
                "base_url": str(payload["base_url"]),
            }
        except (KeyError, TypeError) as exc:
            raise SessionStoreError("AI credentials cannot be decrypted") from exc

    def delete_ai_credentials(self) -> None:
        (self.root / "ai-credentials.enc").unlink(missing_ok=True)

    def _write_json(self, filename: str, payload: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / filename
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_bytes(
            self.cipher.encrypt(json.dumps(payload).encode("utf-8"))
        )
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(path)

    def _read_json(self, filename: str, error: str) -> dict | None:
        path = self.root / filename
        if not path.exists():
            return None
        try:
            value = json.loads(self.cipher.decrypt(path.read_bytes()).decode("utf-8"))
            if not isinstance(value, dict):
                raise TypeError
            return value
        except (OSError, InvalidToken, UnicodeDecodeError, ValueError, TypeError) as exc:
            raise SessionStoreError(error) from exc

    def _safe_path(self, reference: str) -> Path:
        if Path(reference).name != reference:
            raise SessionStoreError("Invalid Telegram session reference")
        path = (self.root / reference).resolve()
        if path.parent != self.root:
            raise SessionStoreError("Invalid Telegram session path")
        return path
