"""Context use-case commands."""

from dataclasses import dataclass

from orchai.domain.context import ContextSource
from orchai.domain.identifiers import ExecutionId


@dataclass(frozen=True, slots=True)
class ResolveExecutionContextCommand:
    """Command for resolving context already authorized for an execution."""

    execution_id: ExecutionId
    source: ContextSource = ContextSource.SOURCE_FILE

