from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorStore(Protocol):
    @abstractmethod
    async def init(self) -> None:
        ...

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        ...

    @abstractmethod
    async def search(
        self,
        collection: str,
        vector: list[float],
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def delete(
        self,
        collection: str,
        *,
        ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> None:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...
