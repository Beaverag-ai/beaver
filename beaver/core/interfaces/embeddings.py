from __future__ import annotations

from abc import abstractmethod
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingsProvider(Protocol):
    @abstractmethod
    async def embed(
        self,
        texts: str | list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        ...

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        batch_size: int = 10,
    ) -> list[list[float]]:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
