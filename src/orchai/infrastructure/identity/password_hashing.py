"""Argon2id password hashing adapter."""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Argon2PasswordHasher:
    """Password hashing adapter backed by argon2-cffi (argon2id).

    Implements `application.identity.ports.PasswordHasher`. Kept in
    infrastructure, not domain, per the existing layering convention
    (domain stays free of third-party/cryptographic dependencies).
    """

    def __init__(self) -> None:
        self._hasher = _Argon2PasswordHasher()

    def hash(self, plain_password: str) -> str:
        if not plain_password:
            raise ValueError("plain_password must not be empty")
        return self._hasher.hash(plain_password)

    def verify(self, plain_password: str, password_hash: str) -> bool:
        try:
            return self._hasher.verify(password_hash, plain_password)
        except VerifyMismatchError, VerificationError, InvalidHashError:
            return False
