"""Basic suggestion engine."""

from __future__ import annotations

from orchai.application.suggestions.ports import SuggestionRepository
from orchai.domain.actions import ActionName
from orchai.domain.capabilities import CapabilityName
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion, SuggestionStatus
from orchai.domain.tasks import Task, TaskState


class SuggestionEngine:
    """Generates non-authoritative next-step recommendations."""

    def __init__(self, repository: SuggestionRepository) -> None:
        self._repository = repository

    async def suggest_next(self, task: Task) -> Suggestion | None:
        suggestion = _suggestion_for_task(task)
        if suggestion is not None:
            await self._repository.add(suggestion)
        return suggestion

    async def mark_status(
        self,
        suggestion: Suggestion,
        status: SuggestionStatus,
    ) -> Suggestion:
        updated = suggestion.with_status(status)
        await self._repository.save(updated)
        return updated


def _suggestion_for_task(task: Task) -> Suggestion | None:
    if task.state is TaskState.PLANNING:
        return Suggestion(
            task_id=task.id,
            suggested_role=RoleName.TASK_PLANNER,
            suggested_action=ActionName.PLAN,
            rationale="Task is in planning; explicit planning is the next step.",
            required_capabilities=frozenset({CapabilityName.READ_DOCUMENTATION}),
            expected_impact="Turn the task into an executable plan.",
            authorization_required=True,
            confidence=0.85,
            metadata={"task_state": task.state.value},
        )
    if task.state is TaskState.PLANNED:
        return Suggestion(
            task_id=task.id,
            suggested_role=RoleName.DEVELOPER,
            suggested_action=ActionName.IMPLEMENT,
            rationale="Task is planned; implementation is the next executable step.",
            required_capabilities=frozenset({CapabilityName.READ_PROJECT}),
            expected_impact="Move from planning to an implementation attempt.",
            authorization_required=True,
            confidence=0.8,
            metadata={"task_state": task.state.value},
        )
    if task.state is TaskState.IMPLEMENTED:
        return Suggestion(
            task_id=task.id,
            suggested_role=RoleName.QUALITY_AGENT,
            suggested_action=ActionName.REVIEW,
            rationale="Implementation is complete; review is the next quality step.",
            required_capabilities=frozenset({CapabilityName.READ_PROJECT}),
            expected_impact="Prepare the task for validation or completion.",
            authorization_required=True,
            confidence=0.7,
            metadata={"task_state": task.state.value},
        )
    if task.state is TaskState.REVIEWING:
        return Suggestion(
            task_id=task.id,
            suggested_role=RoleName.QUALITY_AGENT,
            suggested_action=ActionName.VALIDATE,
            rationale="Review is underway; validation is the next bounded quality step.",
            required_capabilities=frozenset({CapabilityName.READ_PROJECT}),
            expected_impact="Validate whether the reviewed result meets requirements.",
            authorization_required=True,
            confidence=0.7,
            metadata={"task_state": task.state.value},
        )
    if task.state is TaskState.VALIDATING:
        return Suggestion(
            task_id=task.id,
            suggested_role=RoleName.QUALITY_AGENT,
            suggested_action=ActionName.TEST,
            rationale="Validation is in progress; tests are the next executable check.",
            required_capabilities=frozenset({CapabilityName.RUN_TESTS}),
            expected_impact="Increase confidence before final completion.",
            authorization_required=True,
            confidence=0.65,
            metadata={"task_state": task.state.value},
        )
    if task.state is TaskState.VALIDATED:
        return Suggestion(
            task_id=task.id,
            suggested_role=RoleName.DEVELOPER,
            suggested_action=ActionName.DOCUMENT,
            rationale="The task is validated; documentation is the next closing step.",
            required_capabilities=frozenset({CapabilityName.WRITE_DOCUMENTATION}),
            expected_impact="Capture the validated outcome before completion.",
            authorization_required=True,
            confidence=0.6,
            metadata={"task_state": task.state.value},
        )
    return None
