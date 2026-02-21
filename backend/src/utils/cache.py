"""Caching utilities for the Snow Quality Tracker API."""

import hashlib
import json
from functools import wraps
from typing import Any, Callable

from cachetools import TTLCache

# Global caches - persist across Lambda invocations (warm starts)
CACHE_TTL_SECONDS = 300  # 5 minutes for frequently changing data
CACHE_TTL_LONG_SECONDS = 3600  # 1 hour for expensive aggregate queries
CACHE_TTL_VERY_LONG_SECONDS = 86400  # 24 hours for rarely changing data
_resorts_cache: TTLCache = TTLCache(maxsize=1000, ttl=CACHE_TTL_SECONDS)
_conditions_cache: TTLCache = TTLCache(maxsize=5000, ttl=CACHE_TTL_SECONDS)
# Batch conditions cache - used by recommendations, 5-min TTL
_all_conditions_cache: TTLCache = TTLCache(maxsize=1, ttl=CACHE_TTL_SECONDS)
# Snow quality uses 1-hour TTL since weather updates hourly
# Sized for 10K+ resorts to support large databases
_snow_quality_cache: TTLCache = TTLCache(maxsize=15000, ttl=CACHE_TTL_LONG_SECONDS)
_recommendations_cache: TTLCache = TTLCache(maxsize=100, ttl=CACHE_TTL_LONG_SECONDS)
# Timeline cache - 30-min TTL, sized for 200 resorts * 3 elevations
_timeline_cache: TTLCache = TTLCache(maxsize=600, ttl=1800)
# Resort metadata cache - names, countries, etc. (rarely changes)
_resort_metadata_cache: TTLCache = TTLCache(
    maxsize=15000, ttl=CACHE_TTL_VERY_LONG_SECONDS
)


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


def cached_recommendations(func: Callable) -> Callable:
    """Cache decorator for recommendations (1-hour TTL)."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        cache_key = get_cache_key(*args, **kwargs)
        if cache_key in _recommendations_cache:
            return _recommendations_cache[cache_key]
        result = func(*args, **kwargs)
        _recommendations_cache[cache_key] = result
        return result

    return wrapper


def get_recommendations_cache():
    """Get the recommendations cache for direct access."""
    return _recommendations_cache


def get_all_conditions_cache():
    """Get the all_conditions cache for batch conditions fetch."""
    return _all_conditions_cache


def get_resort_metadata_cache():
    """Get the resort metadata cache for direct access."""
    return _resort_metadata_cache


def get_timeline_cache():
    """Get the timeline cache for direct access."""
    return _timeline_cache


def clear_all_caches() -> None:
    """Clear all caches. Useful for testing."""
    _resorts_cache.clear()
    _conditions_cache.clear()
    _all_conditions_cache.clear()
    _snow_quality_cache.clear()
    _recommendations_cache.clear()
    _timeline_cache.clear()
    _resort_metadata_cache.clear()


# Cache-Control header values (weather updates hourly, aggressive caching is safe)
CACHE_CONTROL_PUBLIC = "public, max-age=300"  # 5 minutes, cacheable by any cache
CACHE_CONTROL_PUBLIC_LONG = "public, max-age=3600"  # 1 hour, for slow aggregate queries
CACHE_CONTROL_PRIVATE = "private, no-cache"  # User-specific data, no caching
