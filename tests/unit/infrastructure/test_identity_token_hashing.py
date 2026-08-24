import pytest

from orchai.infrastructure.identity import Sha256RefreshTokenHasher


def test_hash_is_deterministic() -> None:
    hasher = Sha256RefreshTokenHasher()

    first = hasher.hash("some-raw-refresh-token")
    second = hasher.hash("some-raw-refresh-token")

    assert first == second


def test_hash_differs_for_different_inputs() -> None:
    hasher = Sha256RefreshTokenHasher()

    assert hasher.hash("token-a") != hasher.hash("token-b")


def test_hash_does_not_return_the_raw_token() -> None:
    hasher = Sha256RefreshTokenHasher()

    assert hasher.hash("some-raw-refresh-token") != "some-raw-refresh-token"


def test_hash_rejects_empty_token() -> None:
    hasher = Sha256RefreshTokenHasher()

    with pytest.raises(ValueError):
        hasher.hash("")
