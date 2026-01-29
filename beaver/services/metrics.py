from typing import Any
from datetime import datetime, timedelta, UTC

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from beaver.db.models import RequestLog


class MetricsService:
    async def log_request(
        self,
        session: AsyncSession,
        user_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: int,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str | None = None,
    ) -> None:
        session.add(RequestLog(
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
        ))
        await session.commit()

    async def get_user_stats(
        self,
        session: AsyncSession,
        user_id: str,
        days: int = 30,
    ) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)

        # total requests
        result = await session.execute(
            select(func.count(RequestLog.id)).where(
                RequestLog.user_id == user_id,
                RequestLog.timestamp >= since,
            )
        )
        total_requests = result.scalar() or 0

        # token usage
        result = await session.execute(
            select(func.sum(RequestLog.input_tokens), func.sum(RequestLog.output_tokens))
            .where(RequestLog.user_id == user_id, RequestLog.timestamp >= since)
        )
        row = result.one()
        total_in, total_out = row[0] or 0, row[1] or 0

        # avg latency
        result = await session.execute(
            select(func.avg(RequestLog.latency_ms)).where(
                RequestLog.user_id == user_id,
                RequestLog.timestamp >= since,
            )
        )
        avg_latency = result.scalar() or 0

        # error rate
        result = await session.execute(
            select(func.count(RequestLog.id)).where(
                RequestLog.user_id == user_id,
                RequestLog.timestamp >= since,
                RequestLog.status_code >= 400,
            )
        )
        errors = result.scalar() or 0
        error_rate = (errors / total_requests * 100) if total_requests else 0

        # top endpoints
        result = await session.execute(
            select(RequestLog.endpoint, func.count(RequestLog.id))
            .where(RequestLog.user_id == user_id, RequestLog.timestamp >= since)
            .group_by(RequestLog.endpoint)
            .order_by(func.count(RequestLog.id).desc())
            .limit(10)
        )
        endpoints = {r[0]: r[1] for r in result.all()}

        return {
            "period_days": days,
            "total_requests": total_requests,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_tokens": total_in + total_out,
            "avg_latency_ms": round(avg_latency, 2),
            "error_rate_percent": round(error_rate, 2),
            "requests_by_endpoint": endpoints,
        }

    async def get_system_stats(
        self,
        session: AsyncSession,
        days: int = 30,
    ) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)

        result = await session.execute(
            select(func.count(RequestLog.id)).where(RequestLog.timestamp >= since)
        )
        total_requests = result.scalar() or 0

        result = await session.execute(
            select(func.count(func.distinct(RequestLog.user_id))).where(
                RequestLog.timestamp >= since
            )
        )
        unique_users = result.scalar() or 0

        result = await session.execute(
            select(
                func.sum(RequestLog.input_tokens),
                func.sum(RequestLog.output_tokens),
            ).where(RequestLog.timestamp >= since)
        )
        row = result.one()
        total_in, total_out = row[0] or 0, row[1] or 0

        result = await session.execute(
            select(func.avg(RequestLog.latency_ms)).where(RequestLog.timestamp >= since)
        )
        avg_latency = result.scalar() or 0

        result = await session.execute(
            select(RequestLog.model, func.count(RequestLog.id))
            .where(RequestLog.timestamp >= since, RequestLog.model.isnot(None))
            .group_by(RequestLog.model)
            .order_by(func.count(RequestLog.id).desc())
        )
        models = {r[0]: r[1] for r in result.all()}

        return {
            "period_days": days,
            "total_requests": total_requests,
            "unique_users": unique_users,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_tokens": total_in + total_out,
            "avg_latency_ms": round(avg_latency, 2),
            "requests_by_model": models,
        }

    async def get_recent_requests(
        self,
        session: AsyncSession,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        stmt = select(RequestLog).order_by(RequestLog.timestamp.desc()).limit(limit)
        if user_id:
            stmt = stmt.where(RequestLog.user_id == user_id)

        result = await session.execute(stmt)
        return [
            {
                "id": str(log.id),
                "user_id": str(log.user_id),
                "endpoint": log.endpoint,
                "method": log.method,
                "status_code": log.status_code,
                "latency_ms": log.latency_ms,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "model": log.model,
                "timestamp": log.timestamp.isoformat(),
            }
            for log in result.scalars().all()
        ]


_metrics: MetricsService | None = None


def get_metrics() -> MetricsService:
    global _metrics
    if not _metrics:
        _metrics = MetricsService()
    return _metrics
