"""Transient value objects produced/consumed by the login/refresh/logout flow.

These are not persisted entities -- `RefreshToken` (`domain.identity`) is
the persisted record; `AuthenticationResult` and `IssuedAccessToken` exist
only to hand a caller the one-time values (the raw refresh token, the
signed access token) that persistence never stores in cleartext/plaintext
form.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from orchai.domain.identifiers import UserId
from orchai.domain.identity import RefreshToken, User


@dataclass(frozen=True, slots=True)
class IssuedAccessToken:
    """A freshly issued, signed access token and its expiry."""

    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Claims decoded from a validated access token."""

    user_id: UserId
    username: str
    is_superuser: bool
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Everything a successful login/refresh call hands back to the caller."""

    user: User
    access_token: IssuedAccessToken
    refresh_token: RefreshToken
    raw_refresh_token: str
