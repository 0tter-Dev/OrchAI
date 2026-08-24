"""PyJWT-backed access-token issuance/validation adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt

from orchai.application.identity.tokens import AccessTokenClaims, IssuedAccessToken
from orchai.domain.identifiers import UserId
from orchai.domain.identity import InvalidAccessTokenError, User


class JWTAccessTokenIssuer:
    """Access-token adapter backed by PyJWT.

    Implements `application.identity.ports.AccessTokenIssuer`. Issues
    short-lived, signed access tokens (default 15 minutes) carrying the
    user id, username, and superuser flag as claims; validates signature,
    expiry, and required-claim shape on decode.
    """

    def __init__(
        self,
        *,
        secret_key: str,
        algorithm: str = "HS256",
        ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        if not secret_key:
            raise ValueError("secret_key must not be empty")
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._ttl = ttl

    def issue(self, user: User) -> IssuedAccessToken:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + self._ttl
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "is_superuser": user.is_superuser,
            "iat": issued_at,
            "exp": expires_at,
        }
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return IssuedAccessToken(token=token, expires_at=expires_at)

    def decode(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"require": ["sub", "username", "is_superuser", "exp"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidAccessTokenError(
                "access token failed signature, expiry, or claim checks"
            ) from exc
        try:
            return AccessTokenClaims(
                user_id=UserId(payload["sub"]),
                username=payload["username"],
                is_superuser=bool(payload["is_superuser"]),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidAccessTokenError(
                "access token payload has an unexpected shape"
            ) from exc
