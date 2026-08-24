"""SHA-256 refresh-token hashing adapter."""

from __future__ import annotations

import hashlib


class Sha256RefreshTokenHasher:
    """Refresh-token hashing adapter backed by plain SHA-256.

    Implements `application.identity.ports.RefreshTokenHasher`. Deliberately
    not Argon2/bcrypt/scrypt: refresh tokens are generated as high-entropy
    random strings (`secrets.token_urlsafe`), not user-chosen secrets, so
    there is no offline-guessing risk to defend against with a slow,
    memory-hard hash -- a fast deterministic hash is the correct fit, since
    it also has to support exact-match lookup by hash
    (`RefreshTokenRepository.get_by_token_hash`), which a salted hash
    could not.
    """

    def hash(self, raw_token: str) -> str:
        if not raw_token:
            raise ValueError("raw_token must not be empty")
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
