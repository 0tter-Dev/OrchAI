from types import MappingProxyType

import pytest

from orchai.domain.events import DomainEvent, EventType


def test_domain_event_payload_is_shallow_immutable() -> None:
    event = DomainEvent(
        event_type=EventType.TASK_CREATED,
        source="test",
        payload={"state": "CREATED"},
    )

    assert isinstance(event.payload, MappingProxyType)
    assert event.payload["state"] == "CREATED"

    with pytest.raises(TypeError):
        event.payload["state"] = "PLANNING"


def test_domain_event_requires_source() -> None:
    with pytest.raises(ValueError):
        DomainEvent(event_type=EventType.TASK_CREATED, source=" ")

