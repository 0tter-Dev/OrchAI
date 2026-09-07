import asyncio

from orchai.application.suggestions import SuggestionEngine
from orchai.domain.suggestions import SuggestionStatus
from orchai.domain.tasks import Task, TaskScope, TaskState
from orchai.infrastructure.persistence import InMemorySuggestionRepository


def _task(state: TaskState = TaskState.PLANNING) -> Task:
    task = Task(
        title="Sample task",
        description="Exercise the suggestion engine.",
        scope=TaskScope(requested_change="Do the thing."),
    )
    task._state = state
    return task


def test_suggest_next_creates_and_persists_a_suggestion_for_a_fresh_task() -> None:
    async def run() -> None:
        repository = InMemorySuggestionRepository()
        engine = SuggestionEngine(repository)
        task = _task(TaskState.PLANNING)

        suggestion = await engine.suggest_next(task)

        assert suggestion is not None
        assert suggestion.suggested_action.value == "PLAN"
        assert await repository.list(task_id=task.id) == (suggestion,)

    asyncio.run(run())


def test_suggest_next_reuses_a_still_presented_suggestion_instead_of_duplicating() -> None:
    """Regression test: repeated calls while blocked must not create duplicates.

    This is the exact scenario that produced the OrchAI Desktop Phase 5
    bug: /approve delegates to run_task_workflow_stage(stage=None), which
    calls suggest_next() again for a task still in the same state.
    """

    async def run() -> None:
        repository = InMemorySuggestionRepository()
        engine = SuggestionEngine(repository)
        task = _task(TaskState.PLANNING)

        first = await engine.suggest_next(task)
        await engine.mark_status(first, SuggestionStatus.PRESENTED)

        second = await engine.suggest_next(task)

        assert second.id == first.id
        assert len(await repository.list(task_id=task.id)) == 1

    asyncio.run(run())


def test_suggest_next_generates_a_new_suggestion_once_the_previous_one_is_resolved() -> None:
    async def run() -> None:
        repository = InMemorySuggestionRepository()
        engine = SuggestionEngine(repository)
        task = _task(TaskState.PLANNING)

        first = await engine.suggest_next(task)
        await engine.mark_status(first, SuggestionStatus.ACCEPTED)

        second = await engine.suggest_next(task)

        assert second.id != first.id
        assert len(await repository.list(task_id=task.id)) == 2

    asyncio.run(run())


def test_suggest_next_ignores_a_stale_presented_suggestion_for_a_different_stage() -> None:
    """A PRESENTED suggestion left over from a state the task has since
    moved past (e.g. via a direct state transition bypassing the
    suggestion flow) must never be reused for an unrelated stage.
    """

    async def run() -> None:
        repository = InMemorySuggestionRepository()
        engine = SuggestionEngine(repository)
        planning_task = _task(TaskState.PLANNING)
        stale = await engine.suggest_next(planning_task)
        await engine.mark_status(stale, SuggestionStatus.PRESENTED)

        planned_task = _task(TaskState.PLANNED)
        # Same task id as the stale suggestion, different current state.
        planned_task.id = planning_task.id

        fresh = await engine.suggest_next(planned_task)

        assert fresh.id != stale.id
        assert fresh.suggested_action.value == "IMPLEMENT"

    asyncio.run(run())


def test_suggest_next_returns_none_for_a_terminal_task_state() -> None:
    async def run() -> None:
        engine = SuggestionEngine(InMemorySuggestionRepository())
        task = _task(TaskState.COMPLETED)

        suggestion = await engine.suggest_next(task)

        assert suggestion is None

    asyncio.run(run())
