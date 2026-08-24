import pytest

from orchai.infrastructure.identity import Argon2PasswordHasher


def test_hash_produces_a_verifiable_argon2id_hash() -> None:
    hasher = Argon2PasswordHasher()

    password_hash = hasher.hash("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert password_hash.startswith("$argon2id$")
    assert hasher.verify("correct horse battery staple", password_hash) is True


def test_verify_rejects_wrong_password() -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash("correct horse battery staple")

    assert hasher.verify("wrong password", password_hash) is False


def test_verify_rejects_malformed_hash_without_raising() -> None:
    hasher = Argon2PasswordHasher()

    assert hasher.verify("anything", "not-a-real-hash") is False


def test_hash_rejects_empty_password() -> None:
    hasher = Argon2PasswordHasher()

    with pytest.raises(ValueError):
        hasher.hash("")
