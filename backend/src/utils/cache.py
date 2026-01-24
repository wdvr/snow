"""Caching utilities for the Snow Quality Tracker API."""

import hashlib
import json
from functools import wraps
from typing import Any, Callable

from cachetools import TTLCache

# Global caches with 60-second TTL
# These persist across Lambda invocations (warm starts)
_resorts_cache: TTLCache = TTLCache(maxsize=100, ttl=60)
_conditions_cache: TTLCache = TTLCache(maxsize=500, ttl=60)
_snow_quality_cache: TTLCache = TTLCache(maxsize=100, ttl=60)


def get_cache_key(*args, **kwargs) -> str:
    """Generate a cache key from function arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    # MD5 is used here only for cache key generation, not for security purposes
    return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()


def cached_resorts(func: Callable) -> Callable:
    """Cache decorator for resort data (60-second TTL)."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = get_cache_key(*args, **kwargs)
        if cache_key in _resorts_cache:
            return _resorts_cache[cache_key]
        result = func(*args, **kwargs)
        _resorts_cache[cache_key] = result
        return result

    return wrapper


def cached_conditions(func: Callable) -> Callable:
    """Cache decorator for weather conditions (60-second TTL)."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = get_cache_key(*args, **kwargs)
        if cache_key in _conditions_cache:
            return _conditions_cache[cache_key]
        result = func(*args, **kwargs)
        _conditions_cache[cache_key] = result
        return result

    return wrapper


def cached_snow_quality(func: Callable) -> Callable:
    """Cache decorator for snow quality calculations (60-second TTL)."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = get_cache_key(*args, **kwargs)
        if cache_key in _snow_quality_cache:
            return _snow_quality_cache[cache_key]
        result = func(*args, **kwargs)
        _snow_quality_cache[cache_key] = result
        return result

    return wrapper


def clear_all_caches() -> None:
    """Clear all caches. Useful for testing."""
    _resorts_cache.clear()
    _conditions_cache.clear()
    _snow_quality_cache.clear()


# Cache-Control header values
CACHE_CONTROL_PUBLIC = "public, max-age=60"  # Cacheable by any cache
CACHE_CONTROL_PRIVATE = "private, no-cache"  # User-specific data, no caching
