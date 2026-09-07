"""In-memory automatic-mode policy repository."""

from __future__ import annotations

from orchai.application.policies import AutomaticExecutionPolicy, AutomaticPolicyRepository


class InMemoryAutomaticPolicyRepository(AutomaticPolicyRepository):
    """Non-durable, single-slot storage for the automatic-mode policy."""

    def __init__(self) -> None:
        self._policy: AutomaticExecutionPolicy | None = None

    async def get(self) -> AutomaticExecutionPolicy:
        return self._policy or AutomaticExecutionPolicy()

    async def set(self, policy: AutomaticExecutionPolicy) -> None:
        self._policy = policy
