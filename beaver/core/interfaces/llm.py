from abc import abstractmethod
from typing import Any, AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[dict[str, Any]]:
        ...

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
