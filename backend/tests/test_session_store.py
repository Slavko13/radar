from app.telegram.session_store import EncryptedSessionStore, SessionStoreError


def test_session_is_encrypted_at_rest(tmp_path) -> None:
    store = EncryptedSessionStore(str(tmp_path), "a-test-secret-key")
    reference = store.write(123, "sensitive-string-session")

    assert b"sensitive-string-session" not in (tmp_path / reference).read_bytes()
    assert store.read(reference) == "sensitive-string-session"


def test_session_reference_cannot_escape_root(tmp_path) -> None:
    store = EncryptedSessionStore(str(tmp_path), "a-test-secret-key")
    try:
        store.read("../session")
    except SessionStoreError:
        pass
    else:
        raise AssertionError("Path traversal must be rejected")


def test_api_credentials_are_encrypted_and_restored(tmp_path) -> None:
    store = EncryptedSessionStore(str(tmp_path), "a-test-secret-key")
    store.write_api_credentials(123456, "a" * 32)

    encrypted = (tmp_path / "api-credentials.enc").read_bytes()
    assert b"123456" not in encrypted
    assert b"a" * 32 not in encrypted
    assert store.read_api_credentials() == (123456, "a" * 32)


def test_notification_bot_credentials_are_encrypted_and_removable(tmp_path) -> None:
    store = EncryptedSessionStore(str(tmp_path), "a-test-secret-key")
    store.write_notification_bot("123456:secret-token", "-100123456")

    encrypted = (tmp_path / "notification-bot.enc").read_bytes()
    assert b"secret-token" not in encrypted
    assert b"-100123456" not in encrypted
    assert store.read_notification_bot() == ("123456:secret-token", "-100123456")

    store.delete_notification_bot()
    assert store.read_notification_bot() is None
