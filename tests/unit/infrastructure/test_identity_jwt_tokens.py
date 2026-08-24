from datetime import UTC, datetime, timedelta

import jwt
import pytest

from orchai.domain.identity import InvalidAccessTokenError, User
from orchai.infrastructure.identity import JWTAccessTokenIssuer

_SECRET_KEY = "test-secret-key-with-at-least-32-characters"
_OTHER_SECRET_KEY = "a-different-test-secret-key-also-32-plus-chars"


def _make_user() -> User:
    return User(
        username="alice",
        email=None,
        password_hash="irrelevant-for-this-test",
    )


def test_issue_and_decode_round_trip() -> None:
    issuer = JWTAccessTokenIssuer(secret_key=_SECRET_KEY)
    user = _make_user()

    issued = issuer.issue(user)
    claims = issuer.decode(issued.token)

    assert claims.user_id == user.id
    assert claims.username == "alice"
    assert claims.is_superuser is False
    # JWT `exp` is second-precision, so the round trip drops microseconds.
    assert claims.expires_at == issued.expires_at.replace(microsecond=0)


def test_issued_token_expires_after_configured_ttl() -> None:
    issuer = JWTAccessTokenIssuer(secret_key=_SECRET_KEY, ttl=timedelta(minutes=5))
    user = _make_user()
    before = datetime.now(UTC)

    issued = issuer.issue(user)

    expected_expiry = before + timedelta(minutes=5)
    assert abs((issued.expires_at - expected_expiry).total_seconds()) < 5


def test_decode_rejects_expired_token() -> None:
    issuer = JWTAccessTokenIssuer(secret_key=_SECRET_KEY, ttl=timedelta(seconds=-1))
    user = _make_user()

    issued = issuer.issue(user)

    with pytest.raises(InvalidAccessTokenError):
        issuer.decode(issued.token)


def test_decode_rejects_tampered_signature() -> None:
    issuer = JWTAccessTokenIssuer(secret_key=_SECRET_KEY)
    other_issuer = JWTAccessTokenIssuer(secret_key=_OTHER_SECRET_KEY)
    user = _make_user()

    issued = issuer.issue(user)

    with pytest.raises(InvalidAccessTokenError):
        other_issuer.decode(issued.token)


def test_decode_rejects_malformed_token() -> None:
    issuer = JWTAccessTokenIssuer(secret_key=_SECRET_KEY)

    with pytest.raises(InvalidAccessTokenError):
        issuer.decode("not-a-real-jwt")


def test_decode_rejects_token_missing_required_claims() -> None:
    issuer = JWTAccessTokenIssuer(secret_key=_SECRET_KEY)
    bare_token = jwt.encode({"sub": "some-id"}, _SECRET_KEY, algorithm="HS256")

    with pytest.raises(InvalidAccessTokenError):
        issuer.decode(bare_token)


def test_constructor_rejects_empty_secret_key() -> None:
    with pytest.raises(ValueError):
        JWTAccessTokenIssuer(secret_key="")
