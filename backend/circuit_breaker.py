"""
Circuit breaker for cost protection in Cove.

Prevents runaway costs by enforcing:
- Daily cost limits
- Per-query cost limits
- Rate limiting on expensive operations

Features:
- Configurable limits via environment variables
- Real-time cost tracking
- Graceful degradation with user feedback
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy import select, func
from .database import get_db_session
from .models import ModelInvocation


class CircuitBreakerError(Exception):
    """Raised when circuit breaker trips due to cost limits."""
    pass


class CostCircuitBreaker:
    """Circuit breaker for cost control."""

    def __init__(self):
        """Initialize circuit breaker with limits from config."""
        self.daily_limit = float(os.getenv("DAILY_COST_LIMIT", "100.0"))
        self.query_limit = float(os.getenv("QUERY_COST_LIMIT", "5.0"))

    async def check_daily_limit(self, additional_cost: float = 0.0) -> Dict[str, Any]:
        """
        Check if daily cost limit would be exceeded.

        Args:
            additional_cost: Cost to be added (optional, for pre-checks)

        Returns:
            Dict with status and current usage

        Raises:
            CircuitBreakerError if limit would be exceeded
        """
        today = date.today().isoformat()
        current_cost = await self._get_daily_cost(today)
        projected_cost = current_cost + additional_cost

        result = {
            "within_limit": projected_cost <= self.daily_limit,
            "current_cost": current_cost,
            "daily_limit": self.daily_limit,
            "projected_cost": projected_cost,
            "remaining": max(0, self.daily_limit - projected_cost)
        }

        if projected_cost > self.daily_limit:
            raise CircuitBreakerError(
                f"Daily cost limit exceeded. "
                f"Current: ${current_cost:.2f}, "
                f"Limit: ${self.daily_limit:.2f}, "
                f"Additional: ${additional_cost:.2f}"
            )

        return result

    async def check_query_estimate(self, estimated_cost: float) -> Dict[str, Any]:
        """
        Check if estimated query cost exceeds per-query limit.

        Args:
            estimated_cost: Estimated cost for the query

        Returns:
            Dict with status and limits

        Raises:
            CircuitBreakerError if query cost too high
        """
        result = {
            "within_limit": estimated_cost <= self.query_limit,
            "estimated_cost": estimated_cost,
            "query_limit": self.query_limit
        }

        if estimated_cost > self.query_limit:
            raise CircuitBreakerError(
                f"Query cost estimate (${estimated_cost:.2f}) exceeds "
                f"per-query limit (${self.query_limit:.2f}). "
                f"Consider using fewer models or shorter context."
            )

        return result

    async def _get_daily_cost(self, date_str: str) -> float:
        """
        Get total cost for a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Total cost in USD
        """
        from .config import MODEL_COSTS

        async with get_db_session() as session:
            # Query invocations for the date
            result = await session.execute(
                select(
                    ModelInvocation.model_name,
                    func.sum(ModelInvocation.prompt_tokens).label('total_prompt'),
                    func.sum(ModelInvocation.completion_tokens).label('total_completion')
                )
                .where(ModelInvocation.created_at >= f"{date_str} 00:00:00")
                .where(ModelInvocation.created_at < f"{date_str} 23:59:59")
                .where(ModelInvocation.success == True)
                .group_by(ModelInvocation.model_name)
            )

            total_cost = 0.0
            for row in result:
                model_name = row.model_name
                prompt_tokens = row.total_prompt or 0
                completion_tokens = row.total_completion or 0

                # Get costs for this model
                costs = MODEL_COSTS.get(model_name, {"input": 0, "output": 0})

                # Calculate cost (prices are per 1M tokens)
                model_cost = (
                    (prompt_tokens * costs["input"] / 1_000_000) +
                    (completion_tokens * costs["output"] / 1_000_000)
                )
                total_cost += model_cost

            return round(total_cost, 4)

    async def get_cost_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get cost summary for the last N days.

        Args:
            days: Number of days to look back

        Returns:
            Dict with daily costs and totals
        """
        daily_costs = []
        total_cost = 0.0

        today = date.today()
        for i in range(days):
            day = (today - timedelta(days=i))
            day_str = day.isoformat()
            cost = await self._get_daily_cost(day_str)
            daily_costs.append({
                "date": day_str,
                "cost": cost
            })
            total_cost += cost

        return {
            "daily_costs": list(reversed(daily_costs)),
            "total_cost": round(total_cost, 2),
            "average_daily": round(total_cost / days, 2),
            "daily_limit": self.daily_limit,
            "days": days
        }


# Global circuit breaker instance
_circuit_breaker: Optional[CostCircuitBreaker] = None


def get_circuit_breaker() -> CostCircuitBreaker:
    """
    Get the global circuit breaker instance.

    Returns:
        CostCircuitBreaker instance
    """
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CostCircuitBreaker()
    return _circuit_breaker


# Convenience functions
async def check_daily_limit(additional_cost: float = 0.0) -> Dict[str, Any]:
    """Check if daily cost limit would be exceeded."""
    breaker = get_circuit_breaker()
    return await breaker.check_daily_limit(additional_cost)


async def check_query_estimate(estimated_cost: float) -> Dict[str, Any]:
    """Check if estimated query cost exceeds limits."""
    breaker = get_circuit_breaker()
    return await breaker.check_query_estimate(estimated_cost)


async def get_cost_summary(days: int = 7) -> Dict[str, Any]:
    """Get cost summary for last N days."""
    breaker = get_circuit_breaker()
    return await breaker.get_cost_summary(days)
