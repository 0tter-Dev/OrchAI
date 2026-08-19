"""Suggestion lifecycle states."""

from enum import StrEnum


class SuggestionStatus(StrEnum):
    """Lifecycle status for non-authoritative recommendations."""

    GENERATED = "GENERATED"
    PRESENTED = "PRESENTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
