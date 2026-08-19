"""Async execution engine."""

from __future__ import annotations

import asyncio

from orchai.application.context import ContextService, ResolveExecutionContextCommand
from orchai.application.executions.commands import (
    CompleteExecutionCommand,
    TransitionExecutionCommand,
)
from orchai.application.executions.ports import (
    AIProviderContractError,
    AIProviderContextItem,
    AIProviderError,
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderPort,
    ExecutionRepository,
)
from orchai.application.executions.service import ExecutionService
from orchai.infrastructure.projects.errors import ProjectAdapterError
from orchai.domain.context import ContextError
from orchai.domain.executions import Execution, ExecutionState, ResourceUsage
from orchai.domain.identifiers import ExecutionId


class ExecutionEngine:
    """Runs authorized executions through a replaceable AI provider adapter."""

    def __init__(
        self,
        *,
        execution_repository: ExecutionRepository,
        execution_service: ExecutionService,
        context_service: ContextService,
        ai_provider: AIProviderPort,
    ) -> None:
        self._execution_repository = execution_repository
        self._execution_service = execution_service
        self._context_service = context_service
        self._ai_provider = ai_provider

    def dispatch(self, execution_id: ExecutionId) -> asyncio.Task[Execution]:
        """Schedule an authorized execution in the current event loop."""

        return asyncio.create_task(self.run(execution_id))

    async def run(self, execution_id: ExecutionId) -> Execution:
        """Run one authorized execution to completion or provider failure."""

        execution = await self._execution_repository.get(execution_id)
        if execution.state is not ExecutionState.AUTHORIZED:
            raise ValueError("execution must be AUTHORIZED before provider dispatch")

        try:
            execution = await self._execution_service.transition_execution(
                TransitionExecutionCommand(
                    execution_id=execution.id,
                    target_state=ExecutionState.PREPARING,
                )
            )
            package = await self._context_service.resolve_execution_context(
                ResolveExecutionContextCommand(execution_id=execution.id)
            )
            execution = await self._execution_service.transition_execution(
                TransitionExecutionCommand(
                    execution_id=execution.id,
                    target_state=ExecutionState.STARTED,
                )
            )
            execution = await self._execution_service.transition_execution(
                TransitionExecutionCommand(
                    execution_id=execution.id,
                    target_state=ExecutionState.RUNNING,
                )
            )
            result = await self._ai_provider.execute(
                AIProviderExecutionRequest(
                    execution_id=execution.id,
                    task_id=execution.task_id,
                    role=execution.role,
                    action=execution.action,
                    model_id=execution.model_id,
                    project_id=execution.project_id,
                    context=tuple(
                        AIProviderContextItem(
                            resource=item.reference.resource,
                            content=item.content,
                            source=item.reference.source.value,
                            metadata=item.metadata,
                        )
                        for item in package.items
                    ),
                    metadata={"context_provided_at": package.provided_at.isoformat()},
                )
            )
            result = _validated_provider_result(result, execution=execution)
            if result.success:
                return await self._execution_service.complete_execution(
                    CompleteExecutionCommand(
                        execution_id=execution.id,
                        output=result.output,
                        success=True,
                        warnings=result.warnings,
                        resource_usage=ResourceUsage(
                            input_tokens=result.input_tokens,
                            output_tokens=result.output_tokens,
                            estimated_cost=result.estimated_cost,
                            metadata=result.metadata,
                        ),
                        metadata=result.metadata,
                    )
                )
            return await self._fail_execution(
                execution.id,
                output=result.output,
                errors=result.errors or ("provider reported execution failure",),
                warnings=result.warnings,
                resource_usage=ResourceUsage(
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    estimated_cost=result.estimated_cost,
                    metadata=result.metadata,
                ),
                metadata=result.metadata,
            )
        except AIProviderError as exc:
            return await self._fail_execution(
                execution.id,
                output="",
                errors=(str(exc),),
                metadata={
                    "error_type": exc.__class__.__name__,
                    "error_boundary": "provider",
                },
            )
        except (ContextError, ProjectAdapterError) as exc:
            return await self._fail_execution(
                execution.id,
                output="",
                errors=(str(exc),),
                metadata={
                    "error_type": exc.__class__.__name__,
                    "error_boundary": "context",
                },
            )
        except Exception as exc:
            return await self._fail_execution(
                execution.id,
                output="",
                errors=(str(exc),),
                metadata={
                    "error_type": exc.__class__.__name__,
                    "error_boundary": "execution",
                },
            )

    async def _fail_execution(
        self,
        execution_id: ExecutionId,
        *,
        output: str,
        errors: tuple[str, ...],
        warnings: tuple[str, ...] = (),
        resource_usage: ResourceUsage | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Execution:
        return await self._execution_service.complete_execution(
            CompleteExecutionCommand(
                execution_id=execution_id,
                output=output,
                success=False,
                errors=errors,
                warnings=warnings,
                resource_usage=resource_usage or ResourceUsage(),
                metadata=metadata or {},
            )
        )


def _validated_provider_result(
    result: AIProviderExecutionResult,
    *,
    execution: Execution,
) -> AIProviderExecutionResult:
    provider_name = result.provider_name.strip()
    if not provider_name:
        raise AIProviderContractError("provider result must declare provider_name")
    metadata = {
        "provider": provider_name,
        "model_id": str(execution.model_id),
        "execution_id": str(execution.id),
        **dict(result.metadata),
    }
    return AIProviderExecutionResult(
        output=result.output,
        success=result.success,
        errors=result.errors,
        warnings=result.warnings,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost=result.estimated_cost,
        metadata=metadata,
        provider_name=provider_name,
    )
