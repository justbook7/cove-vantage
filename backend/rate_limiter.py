"""
Rate limiting middleware for Cove.

Prevents abuse and ensures fair resource allocation.

Features:
- Per-endpoint rate limits
- IP-based tracking
- Sliding window algorithm
- Configurable limits via environment variables
"""

import os
import time
from typing import Dict, Optional
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from datetime import datetime, timedelta


class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self):
        """Initialize rate limiter with configurable limits."""
        # Rate limits per endpoint (requests per minute)
        self.limits = {
            "message": int(os.getenv("RATE_LIMIT_MESSAGE", "10")),  # 10 req/min for messages
            "conversations": int(os.getenv("RATE_LIMIT_CONVERSATIONS", "30")),  # 30 req/min for list
            "default": int(os.getenv("RATE_LIMIT_DEFAULT", "60"))  # 60 req/min default
        }

        # Storage for request timestamps per IP
        self._requests: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))

        # Cleanup interval
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # seconds

    def _get_client_identifier(self, request: Request) -> str:
        """
        Get unique identifier for the client.

        Args:
            request: FastAPI request object

        Returns:
            Client identifier (IP address)
        """
        # Try to get real IP from headers (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Fallback to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _get_endpoint_key(self, request: Request) -> str:
        """
        Get rate limit key for the endpoint.

        Args:
            request: FastAPI request object

        Returns:
            Endpoint key for rate limiting
        """
        path = request.url.path

        if "/message" in path:
            return "message"
        elif "/conversations" in path:
            return "conversations"
        else:
            return "default"

    def _cleanup_old_requests(self):
        """Periodically cleanup old request timestamps."""
        now = time.time()

        if now - self._last_cleanup < self._cleanup_interval:
            return

        # Clean up requests older than 2 minutes
        cutoff = now - 120

        for client_data in self._requests.values():
            for endpoint_key, timestamps in client_data.items():
                # Remove old timestamps
                while timestamps and timestamps[0] < cutoff:
                    timestamps.popleft()

        self._last_cleanup = now

    async def check_rate_limit(self, request: Request) -> None:
        """
        Check if request should be rate limited.

        Args:
            request: FastAPI request object

        Raises:
            HTTPException: If rate limit exceeded
        """
        # Cleanup periodically
        self._cleanup_old_requests()

        # Get client and endpoint
        client_id = self._get_client_identifier(request)
        endpoint_key = self._get_endpoint_key(request)

        # Get limit for this endpoint
        limit = self.limits.get(endpoint_key, self.limits["default"])

        # Get request history for this client/endpoint
        timestamps = self._requests[client_id][endpoint_key]

        # Current time
        now = time.time()
        window_start = now - 60  # 1 minute window

        # Remove timestamps outside the window
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        # Check if limit exceeded
        if len(timestamps) >= limit:
            # Calculate retry after
            oldest_in_window = timestamps[0]
            retry_after = int(60 - (now - oldest_in_window)) + 1

            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window": "1 minute",
                    "retry_after": retry_after
                },
                headers={"Retry-After": str(retry_after)}
            )

        # Add current request timestamp
        timestamps.append(now)

    def get_rate_limit_info(self, request: Request) -> Dict[str, any]:
        """
        Get current rate limit status for a client.

        Args:
            request: FastAPI request object

        Returns:
            Dict with rate limit info
        """
        client_id = self._get_client_identifier(request)
        endpoint_key = self._get_endpoint_key(request)
        limit = self.limits.get(endpoint_key, self.limits["default"])

        timestamps = self._requests[client_id][endpoint_key]

        # Count requests in current window
        now = time.time()
        window_start = now - 60

        current_count = sum(1 for ts in timestamps if ts >= window_start)

        return {
            "limit": limit,
            "remaining": max(0, limit - current_count),
            "used": current_count,
            "window": "1 minute",
            "reset_at": datetime.fromtimestamp(window_start + 60).isoformat()
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.

    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# Convenience function for FastAPI dependency injection
async def check_rate_limit(request: Request) -> None:
    """
    Check rate limit for a request.

    Use as FastAPI dependency:
    @app.post("/endpoint", dependencies=[Depends(check_rate_limit)])
    """
    limiter = get_rate_limiter()
    await limiter.check_rate_limit(request)


async def get_rate_limit_info(request: Request) -> Dict[str, any]:
    """Get rate limit info for current request."""
    limiter = get_rate_limiter()
    return limiter.get_rate_limit_info(request)
