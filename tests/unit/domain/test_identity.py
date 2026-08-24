from datetime import UTC, datetime, timedelta

import pytest

from orchai.domain.identifiers import UserId
from orchai.domain.identity import (
    AccessRole,
    Permission,
    RefreshToken,
    RefreshTokenAlreadyRevokedError,
    User,
    UserAlreadyActiveError,
    UserAlreadyInactiveError,
)


def test_user_normalizes_username_and_optional_email() -> None:
    user = User(
        username="  alice  ",
        email="  ",
        password_hash="hashed",
    )

    assert user.username == "alice"
    assert user.email is None
    assert user.is_active is True
    assert user.is_superuser is False


def test_user_requires_non_empty_password_hash() -> None:
    with pytest.raises(ValueError):
        User(username="alice", email=None, password_hash="   ")


def test_user_deactivate_and_activate_toggle_state() -> None:
    user = User(username="alice", email=None, password_hash="hashed")

    user.deactivate()
    assert user.is_active is False

    with pytest.raises(UserAlreadyInactiveError):
        user.deactivate()

    user.activate()
    assert user.is_active is True

    with pytest.raises(UserAlreadyActiveError):
        user.activate()


def test_user_change_password_hash_updates_timestamp() -> None:
    created_at = datetime(2026, 8, 1, tzinfo=UTC)
    user = User(
        username="alice",
        email=None,
        password_hash="hashed",
        created_at=created_at,
        updated_at=created_at,
    )

    updated_at = created_at + timedelta(minutes=5)
    user.change_password_hash("new-hash", at=updated_at)

    assert user.password_hash == "new-hash"
    assert user.updated_at == updated_at


def test_access_role_requires_non_empty_name() -> None:
    with pytest.raises(ValueError):
        AccessRole(name="  ")


def test_permission_requires_non_empty_key() -> None:
    with pytest.raises(ValueError):
        Permission(key="  ")


def test_refresh_token_requires_expires_at_after_issued_at() -> None:
    issued_at = datetime(2026, 8, 1, tzinfo=UTC)
    with pytest.raises(ValueError):
        RefreshToken(
            user_id=UserId.new(),
            token_hash="hash",
            expires_at=issued_at,
            issued_at=issued_at,
        )


def test_refresh_token_is_active_until_expiry_or_revocation() -> None:
    issued_at = datetime(2026, 8, 1, tzinfo=UTC)
    token = RefreshToken(
        user_id=UserId.new(),
        token_hash="hash",
        expires_at=issued_at + timedelta(days=30),
        issued_at=issued_at,
    )

    assert token.is_active(at=issued_at + timedelta(days=1)) is True
    assert token.is_active(at=issued_at + timedelta(days=31)) is False

    token.revoke(at=issued_at + timedelta(days=2))
    assert token.is_active(at=issued_at + timedelta(days=2, minutes=1)) is False

    with pytest.raises(RefreshTokenAlreadyRevokedError):
        token.revoke()
