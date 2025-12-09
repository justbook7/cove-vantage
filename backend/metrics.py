"""
Cost and performance metrics tracking for Cove.

This module provides:
- Recording of all model invocations with cost and latency
- Analytics queries for cost dashboards
- Performance metrics per model
- Daily/weekly/monthly cost aggregation
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy import func, and_
from sqlalchemy.future import select
from sqlalchemy.types import Integer

from .database import get_db
from .models import ModelInvocation, ToolCall, Conversation, Message, StageResult
from .config import MODEL_COSTS


class MetricsCollector:
    """
    Singleton metrics collector for tracking model usage and costs.
    """

    async def record_invocation(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        success: bool,
        error_message: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> int:
        """
        Record a model invocation for cost and performance tracking.

        Args:
            model: Model identifier (e.g., "openai/gpt-5.1")
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            latency_ms: Response latency in milliseconds
            success: Whether the invocation succeeded
            error_message: Error message if failed
            metadata: Additional context (conversation_id, workspace, etc.)

        Returns:
            Invocation ID
        """
        # Calculate cost based on token usage
        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        async with get_db() as db:
            invocation = ModelInvocation(
                timestamp=datetime.utcnow(),
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost=cost,
                latency_ms=latency_ms,
                success=success,
                error_message=error_message,
                metadata_json=metadata or {},
            )
            db.add(invocation)
            await db.commit()
            await db.refresh(invocation)
            return invocation.id

    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost in USD based on model pricing.

        Args:
            model: Model identifier
            prompt_tokens: Input tokens
            completion_tokens: Output tokens

        Returns:
            Cost in USD
        """
        if model not in MODEL_COSTS:
            # Unknown model, use rough estimate
            return (prompt_tokens + completion_tokens) * 0.000001  # $0.001 per 1K tokens

        pricing = MODEL_COSTS[model]
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def get_daily_stats(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get aggregated statistics for a specific day.

        Args:
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            {
                "date": str,
                "total_cost": float,
                "total_invocations": int,
                "successful_invocations": int,
                "failed_invocations": int,
                "avg_latency_ms": float,
                "total_tokens": int,
            }
        """
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            target_date = datetime.utcnow()

        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        async with get_db() as db:
            # Query aggregated metrics
            result = await db.execute(
                select(
                    func.sum(ModelInvocation.cost).label('total_cost'),
                    func.count(ModelInvocation.id).label('total_invocations'),
                    func.sum(func.cast(ModelInvocation.success, Integer)).label('successful'),
                    func.avg(ModelInvocation.latency_ms).label('avg_latency'),
                    func.sum(ModelInvocation.prompt_tokens + ModelInvocation.completion_tokens).label('total_tokens'),
                ).where(
                    and_(
                        ModelInvocation.timestamp >= start_of_day,
                        ModelInvocation.timestamp < end_of_day
                    )
                )
            )
            row = result.first()

            return {
                "date": start_of_day.strftime("%Y-%m-%d"),
                "total_cost": float(row.total_cost or 0),
                "total_invocations": int(row.total_invocations or 0),
                "successful_invocations": int(row.successful or 0),
                "failed_invocations": int((row.total_invocations or 0) - (row.successful or 0)),
                "avg_latency_ms": float(row.avg_latency or 0),
                "total_tokens": int(row.total_tokens or 0),
            }

    async def get_model_stats(self, model: Optional[str] = None, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get per-model performance statistics.

        Args:
            model: Specific model to query, or None for all models
            days: Number of days to look back

        Returns:
            List of {
                "model": str,
                "total_cost": float,
                "total_invocations": int,
                "success_rate": float,
                "avg_latency_ms": float,
                "total_tokens": int,
            }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        async with get_db() as db:
            query = select(
                ModelInvocation.model,
                func.sum(ModelInvocation.cost).label('total_cost'),
                func.count(ModelInvocation.id).label('total_invocations'),
                func.avg(func.cast(ModelInvocation.success, Integer)).label('success_rate'),
                func.avg(ModelInvocation.latency_ms).label('avg_latency'),
                func.sum(ModelInvocation.prompt_tokens + ModelInvocation.completion_tokens).label('total_tokens'),
            ).where(
                ModelInvocation.timestamp >= cutoff_date
            ).group_by(ModelInvocation.model)

            if model:
                query = query.where(ModelInvocation.model == model)

            result = await db.execute(query)
            rows = result.all()

            return [
                {
                    "model": row.model,
                    "total_cost": float(row.total_cost or 0),
                    "total_invocations": int(row.total_invocations or 0),
                    "success_rate": float(row.success_rate or 0),
                    "avg_latency_ms": float(row.avg_latency or 0),
                    "total_tokens": int(row.total_tokens or 0),
                }
                for row in rows
            ]

    async def get_dashboard_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive metrics for cost dashboard.

        Args:
            start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
            end_date: End date (YYYY-MM-DD), defaults to today

        Returns:
            {
                "daily_costs": [{date, cost}, ...],
                "model_costs": [{model, cost, percentage}, ...],
                "workspace_costs": [{workspace, cost}, ...],
                "expensive_queries": [{query, cost, timestamp}, ...],
                "model_performance": [{model, avg_latency, success_rate, total_cost}, ...],
            }
        """
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d")
        else:
            end = datetime.utcnow()

        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start = end - timedelta(days=30)

        async with get_db() as db:
            # Daily costs
            daily_result = await db.execute(
                select(
                    func.date(ModelInvocation.timestamp).label('date'),
                    func.sum(ModelInvocation.cost).label('cost'),
                ).where(
                    and_(
                        ModelInvocation.timestamp >= start,
                        ModelInvocation.timestamp <= end
                    )
                ).group_by(func.date(ModelInvocation.timestamp)).order_by('date')
            )
            daily_costs = [
                {"date": str(row.date), "cost": float(row.cost or 0)}
                for row in daily_result.all()
            ]

            # Model costs
            model_result = await db.execute(
                select(
                    ModelInvocation.model,
                    func.sum(ModelInvocation.cost).label('cost'),
                ).where(
                    and_(
                        ModelInvocation.timestamp >= start,
                        ModelInvocation.timestamp <= end
                    )
                ).group_by(ModelInvocation.model)
            )
            model_rows = model_result.all()
            total_cost = sum(row.cost or 0 for row in model_rows)
            model_costs = [
                {
                    "model": row.model,
                    "cost": float(row.cost or 0),
                    "percentage": round((row.cost or 0) / total_cost * 100, 1) if total_cost > 0 else 0,
                }
                for row in model_rows
            ]

            # Model performance
            performance_result = await db.execute(
                select(
                    ModelInvocation.model,
                    func.avg(ModelInvocation.latency_ms).label('avg_latency'),
                    func.avg(func.cast(ModelInvocation.success, Integer)).label('success_rate'),
                    func.sum(ModelInvocation.cost).label('total_cost'),
                ).where(
                    and_(
                        ModelInvocation.timestamp >= start,
                        ModelInvocation.timestamp <= end
                    )
                ).group_by(ModelInvocation.model)
            )
            model_performance = [
                {
                    "model": row.model,
                    "avg_latency": round(float(row.avg_latency or 0), 2),
                    "success_rate": round(float(row.success_rate or 0) * 100, 1),
                    "total_cost": float(row.total_cost or 0),
                }
                for row in performance_result.all()
            ]

            return {
                "daily_costs": daily_costs,
                "model_costs": model_costs,
                "workspace_costs": [],  # TODO: Implement workspace tracking
                "expensive_queries": [],  # TODO: Implement query cost tracking
                "model_performance": model_performance,
            }


# Global metrics collector instance
metrics_collector = MetricsCollector()
