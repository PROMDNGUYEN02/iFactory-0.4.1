# src/iFactory/application/mediator/pipeline.py
"""Pipeline for chaining behaviors."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Generic, List, TypeVar

from iFactory.application.mediator.behaviors import IPipelineBehavior

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


class Pipeline(Generic[TRequest, TResponse]):
    """Pipeline that chains behaviors around a handler."""

    def __init__(self) -> None:
        self._behaviors: List[IPipelineBehavior[Any, Any]] = []

    def add(self, behavior: IPipelineBehavior[TRequest, TResponse]) -> "Pipeline[TRequest, TResponse]":
        """Add a behavior to the pipeline."""
        self._behaviors.append(behavior)
        return self

    def clear(self) -> None:
        """Remove all behaviors."""
        self._behaviors.clear()

    @property
    def behaviors(self) -> List[IPipelineBehavior[Any, Any]]:
        """Get list of registered behaviors."""
        return self._behaviors.copy()

    async def execute(
        self,
        request: TRequest,
        handler: Callable[[TRequest], Awaitable[TResponse]],
    ) -> TResponse:
        """Execute the pipeline."""
        if not self._behaviors:
            return await handler(request)

        # Build chain from inside out
        current_handler = handler

        for behavior in reversed(self._behaviors):
            next_handler = current_handler

            async def create_wrapper(
                b: IPipelineBehavior,
                h: Callable,
            ) -> Callable:
                async def wrapper(req: TRequest) -> TResponse:
                    return await b.handle(req, h)

                return wrapper

            current_handler = await create_wrapper(behavior, next_handler)

        return await current_handler(request)


class PipelineBuilder(Generic[TRequest, TResponse]):
    """Builder for creating pipelines."""

    def __init__(self) -> None:
        self._pipeline: Pipeline[TRequest, TResponse] = Pipeline()

    def use(self, behavior: IPipelineBehavior[TRequest, TResponse]) -> "PipelineBuilder[TRequest, TResponse]":
        """Add a behavior."""
        self._pipeline.add(behavior)
        return self

    def build(self) -> Pipeline[TRequest, TResponse]:
        """Build the pipeline."""
        return self._pipeline


__all__ = [
    "Pipeline",
    "PipelineBuilder",
]
