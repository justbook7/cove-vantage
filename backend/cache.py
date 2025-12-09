"""
Response caching for Cove.

Reduces costs and latency by caching LLM responses.
Uses in-memory caching with LRU eviction (Redis optional).

Features:
- Cache key based on model + messages hash
- TTL-based expiration
- LRU eviction when memory limit reached
- Optional Redis backend for distributed caching
"""

import hashlib
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import lru_cache


# In-memory cache implementation
class InMemoryCache:
    """Simple in-memory cache with TTL and LRU eviction."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        Initialize in-memory cache.

        Args:
            max_size: Maximum number of cache entries
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get value from cache if it exists and hasn't expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        entry = self._cache[key]
        expires_at = entry.get("expires_at")

        # Check if expired
        if expires_at and datetime.now() > expires_at:
            del self._cache[key]
            return None

        # Update access time for LRU
        entry["last_accessed"] = datetime.now()
        return entry.get("value")

    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        # Evict old entries if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_lru()

        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "last_accessed": datetime.now(),
            "created_at": datetime.now()
        }

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find entry with oldest last_accessed time
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k]["last_accessed"]
        )
        del self._cache[lru_key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "utilization": len(self._cache) / self.max_size if self.max_size > 0 else 0
        }


# Redis cache implementation (optional)
class RedisCache:
    """Redis-based cache for distributed systems."""

    def __init__(self, redis_url: str, default_ttl: int = 3600):
        """
        Initialize Redis cache.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default time-to-live in seconds
        """
        try:
            import redis
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.default_ttl = default_ttl
            # Test connection
            self.redis.ping()
            print("✓ Connected to Redis cache")
        except ImportError:
            raise ImportError("Redis package not installed. Run: pip install redis")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from Redis cache."""
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Redis GET error: {e}")
            return None

    def set(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Set value in Redis cache with TTL."""
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value)
            if ttl > 0:
                self.redis.setex(key, ttl, serialized)
            else:
                self.redis.set(key, serialized)
        except Exception as e:
            print(f"Redis SET error: {e}")

    def clear(self) -> None:
        """Clear all cache entries."""
        try:
            self.redis.flushdb()
        except Exception as e:
            print(f"Redis CLEAR error: {e}")

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            info = self.redis.info()
            return {
                "keys": self.redis.dbsize(),
                "memory_used": info.get("used_memory_human", "unknown"),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0)
            }
        except Exception as e:
            return {"error": str(e)}


# Global cache instance
_cache_instance: Optional[Any] = None


def get_cache():
    """
    Get the global cache instance.

    Returns:
        Cache instance (InMemoryCache or RedisCache)
    """
    global _cache_instance

    if _cache_instance is None:
        # Try to use Redis if configured
        redis_url = os.getenv("REDIS_URL")
        default_ttl = int(os.getenv("CACHE_TTL", "3600"))

        if redis_url:
            try:
                _cache_instance = RedisCache(redis_url, default_ttl)
            except Exception as e:
                print(f"Redis unavailable, falling back to in-memory cache: {e}")
                _cache_instance = InMemoryCache(default_ttl=default_ttl)
        else:
            _cache_instance = InMemoryCache(default_ttl=default_ttl)

    return _cache_instance


def generate_cache_key(model: str, messages: list) -> str:
    """
    Generate a cache key from model and messages.

    Args:
        model: Model identifier
        messages: List of message dicts

    Returns:
        SHA256 hash as cache key
    """
    # Create a deterministic string from model + messages
    cache_input = f"{model}:{json.dumps(messages, sort_keys=True)}"
    return hashlib.sha256(cache_input.encode()).hexdigest()


async def get_cached_response(model: str, messages: list) -> Optional[Dict[str, Any]]:
    """
    Get cached response for model + messages.

    Args:
        model: Model identifier
        messages: List of message dicts

    Returns:
        Cached response or None if not found
    """
    cache = get_cache()
    key = generate_cache_key(model, messages)
    return cache.get(key)


async def set_cached_response(
    model: str,
    messages: list,
    response: Dict[str, Any],
    ttl: Optional[int] = None
) -> None:
    """
    Cache a response for model + messages.

    Args:
        model: Model identifier
        messages: List of message dicts
        response: Response to cache
        ttl: Time-to-live in seconds (optional)
    """
    cache = get_cache()
    key = generate_cache_key(model, messages)
    cache.set(key, response, ttl)


def clear_cache() -> None:
    """Clear all cached responses."""
    cache = get_cache()
    cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict with cache metrics
    """
    cache = get_cache()
    return cache.stats()
