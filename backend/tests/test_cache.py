"""Tests for caching utilities."""

import time
from unittest.mock import MagicMock

import pytest
from cachetools import TTLCache

from utils.cache import (
    CACHE_CONTROL_PRIVATE,
    CACHE_CONTROL_PUBLIC,
    CACHE_CONTROL_PUBLIC_LONG,
    CACHE_TTL_LONG_SECONDS,
    CACHE_TTL_SECONDS,
    CACHE_TTL_VERY_LONG_SECONDS,
    cached_conditions,
    cached_recommendations,
    cached_resorts,
    cached_snow_quality,
    clear_all_caches,
    get_all_conditions_cache,
    get_cache_key,
    get_recommendations_cache,
    get_resort_metadata_cache,
    get_timeline_cache,
)


@pytest.fixture(autouse=True)
def _clear_caches():
    """Clear all caches before and after each test."""
    clear_all_caches()
    yield
    clear_all_caches()


class TestCacheConstants:
    """Test cache constant values."""

    def test_cache_ttl_seconds(self):
        """Test default TTL is 5 minutes."""
        assert CACHE_TTL_SECONDS == 300

    def test_cache_ttl_long_seconds(self):
        """Test long TTL is 1 hour."""
        assert CACHE_TTL_LONG_SECONDS == 3600

    def test_cache_ttl_very_long_seconds(self):
        """Test very long TTL is 24 hours."""
        assert CACHE_TTL_VERY_LONG_SECONDS == 86400

    def test_cache_control_public(self):
        """Test public cache control header value."""
        assert CACHE_CONTROL_PUBLIC == "public, max-age=300"

    def test_cache_control_public_long(self):
        """Test long public cache control header value."""
        assert CACHE_CONTROL_PUBLIC_LONG == "public, max-age=3600"

    def test_cache_control_private(self):
        """Test private cache control header value."""
        assert CACHE_CONTROL_PRIVATE == "private, no-cache"


class TestGetCacheKey:
    """Test cache key generation."""

    def test_same_args_produce_same_key(self):
        """Test that identical arguments produce the same cache key."""
        key1 = get_cache_key("resort-1", "mid")
        key2 = get_cache_key("resort-1", "mid")
        assert key1 == key2

    def test_different_args_produce_different_keys(self):
        """Test that different arguments produce different cache keys."""
        key1 = get_cache_key("resort-1", "mid")
        key2 = get_cache_key("resort-2", "top")
        assert key1 != key2

    def test_kwargs_order_does_not_matter(self):
        """Test that keyword argument order does not affect the key."""
        key1 = get_cache_key(region="alps", country="CH")
        key2 = get_cache_key(country="CH", region="alps")
        assert key1 == key2

    def test_args_vs_kwargs_produce_different_keys(self):
        """Test that positional vs keyword arguments produce different keys."""
        key1 = get_cache_key("resort-1")
        key2 = get_cache_key(resort_id="resort-1")
        assert key1 != key2

    def test_key_is_hex_string(self):
        """Test that the cache key is a valid MD5 hex digest."""
        key = get_cache_key("test")
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)

    def test_empty_args_produces_valid_key(self):
        """Test that no arguments still produces a valid key."""
        key = get_cache_key()
        assert len(key) == 32

    def test_complex_args_produce_valid_key(self):
        """Test that complex argument types produce a valid key."""
        key = get_cache_key(
            [1, 2, 3],
            {"nested": "dict"},
            enabled=True,
            count=42,
        )
        assert len(key) == 32

    def test_non_serializable_args_use_str_fallback(self):
        """Test that non-JSON-serializable args are handled via str default."""
        obj = object()
        key = get_cache_key(obj)
        assert len(key) == 32


class TestCachedResorts:
    """Test the cached_resorts decorator."""

    def test_caches_result(self):
        """Test that repeated calls return cached result without re-calling."""
        mock_fn = MagicMock(return_value=["resort-a", "resort-b"])
        decorated = cached_resorts(mock_fn)

        result1 = decorated("CA")
        result2 = decorated("CA")

        assert result1 == ["resort-a", "resort-b"]
        assert result2 == ["resort-a", "resort-b"]
        assert mock_fn.call_count == 1

    def test_different_args_call_function_again(self):
        """Test that different arguments bypass the cache."""
        mock_fn = MagicMock(side_effect=lambda country: [f"resort-{country}"])
        decorated = cached_resorts(mock_fn)

        result1 = decorated("CA")
        result2 = decorated("US")

        assert result1 == ["resort-CA"]
        assert result2 == ["resort-US"]
        assert mock_fn.call_count == 2

    def test_preserves_function_name(self):
        """Test that the decorator preserves the wrapped function's name."""

        @cached_resorts
        def get_resorts():
            return []

        assert get_resorts.__name__ == "get_resorts"

    def test_cache_returns_same_object(self):
        """Test that cached result is the same object (not a copy)."""
        data = {"key": "value"}
        mock_fn = MagicMock(return_value=data)
        decorated = cached_resorts(mock_fn)

        result1 = decorated("CA")
        result2 = decorated("CA")

        assert result1 is result2


class TestCachedConditions:
    """Test the cached_conditions decorator."""

    def test_caches_result(self):
        """Test that repeated calls return cached result."""
        mock_fn = MagicMock(return_value={"temp": -5.0})
        decorated = cached_conditions(mock_fn)

        result1 = decorated("big-white", "mid")
        result2 = decorated("big-white", "mid")

        assert result1 == {"temp": -5.0}
        assert result2 == {"temp": -5.0}
        assert mock_fn.call_count == 1

    def test_different_args_bypass_cache(self):
        """Test that different arguments result in separate cache entries."""
        call_count = 0

        def mock_fn(resort_id, level):
            nonlocal call_count
            call_count += 1
            return {"resort": resort_id, "level": level}

        decorated = cached_conditions(mock_fn)

        result1 = decorated("big-white", "mid")
        result2 = decorated("big-white", "top")

        assert result1["level"] == "mid"
        assert result2["level"] == "top"
        assert call_count == 2

    def test_preserves_function_name(self):
        """Test that the decorator preserves the wrapped function's name."""

        @cached_conditions
        def get_conditions():
            return {}

        assert get_conditions.__name__ == "get_conditions"


class TestCachedSnowQuality:
    """Test the cached_snow_quality decorator."""

    def test_caches_result(self):
        """Test that repeated calls return cached result."""
        mock_fn = MagicMock(return_value={"quality": "excellent"})
        decorated = cached_snow_quality(mock_fn)

        result1 = decorated("whistler")
        result2 = decorated("whistler")

        assert result1 == {"quality": "excellent"}
        assert result2 == {"quality": "excellent"}
        assert mock_fn.call_count == 1

    def test_different_args_bypass_cache(self):
        """Test that different arguments result in separate cache lookups."""
        mock_fn = MagicMock(side_effect=lambda rid: {"resort": rid})
        decorated = cached_snow_quality(mock_fn)

        decorated("whistler")
        decorated("big-white")

        assert mock_fn.call_count == 2

    def test_preserves_function_name(self):
        """Test that the decorator preserves the wrapped function's name."""

        @cached_snow_quality
        def compute_quality():
            return {}

        assert compute_quality.__name__ == "compute_quality"


class TestCachedRecommendations:
    """Test the cached_recommendations decorator."""

    def test_caches_result(self):
        """Test that repeated calls return cached result."""
        mock_fn = MagicMock(return_value=[{"resort": "whistler", "score": 95}])
        decorated = cached_recommendations(mock_fn)

        result1 = decorated(lat=49.0, lon=-120.0)
        result2 = decorated(lat=49.0, lon=-120.0)

        assert result1 == [{"resort": "whistler", "score": 95}]
        assert result2 == [{"resort": "whistler", "score": 95}]
        assert mock_fn.call_count == 1

    def test_different_args_bypass_cache(self):
        """Test that different kwargs result in separate cache entries."""
        mock_fn = MagicMock(return_value=[])
        decorated = cached_recommendations(mock_fn)

        decorated(lat=49.0, lon=-120.0)
        decorated(lat=50.0, lon=-121.0)

        assert mock_fn.call_count == 2

    def test_preserves_function_name(self):
        """Test that the decorator preserves the wrapped function's name."""

        @cached_recommendations
        def get_recommendations():
            return []

        assert get_recommendations.__name__ == "get_recommendations"


class TestCacheAccessors:
    """Test functions that return cache instances for direct access."""

    def test_get_recommendations_cache_returns_ttl_cache(self):
        """Test that get_recommendations_cache returns a TTLCache."""
        cache = get_recommendations_cache()
        assert isinstance(cache, TTLCache)

    def test_get_all_conditions_cache_returns_ttl_cache(self):
        """Test that get_all_conditions_cache returns a TTLCache."""
        cache = get_all_conditions_cache()
        assert isinstance(cache, TTLCache)

    def test_get_resort_metadata_cache_returns_ttl_cache(self):
        """Test that get_resort_metadata_cache returns a TTLCache."""
        cache = get_resort_metadata_cache()
        assert isinstance(cache, TTLCache)

    def test_get_timeline_cache_returns_ttl_cache(self):
        """Test that get_timeline_cache returns a TTLCache."""
        cache = get_timeline_cache()
        assert isinstance(cache, TTLCache)

    def test_recommendations_cache_maxsize(self):
        """Test that recommendations cache has expected maxsize."""
        cache = get_recommendations_cache()
        assert cache.maxsize == 100

    def test_all_conditions_cache_maxsize(self):
        """Test that all_conditions cache has maxsize of 1."""
        cache = get_all_conditions_cache()
        assert cache.maxsize == 1

    def test_resort_metadata_cache_maxsize(self):
        """Test that resort metadata cache has expected maxsize."""
        cache = get_resort_metadata_cache()
        assert cache.maxsize == 15000

    def test_timeline_cache_maxsize(self):
        """Test that timeline cache has expected maxsize."""
        cache = get_timeline_cache()
        assert cache.maxsize == 600

    def test_direct_cache_read_write(self):
        """Test that cache instances support direct read/write."""
        cache = get_recommendations_cache()
        cache["test_key"] = {"result": 42}
        assert cache["test_key"] == {"result": 42}

    def test_direct_cache_cleared_by_clear_all(self):
        """Test that direct cache entries are cleared by clear_all_caches."""
        cache = get_recommendations_cache()
        cache["test_key"] = "value"
        assert "test_key" in cache

        clear_all_caches()

        assert "test_key" not in cache


class TestClearAllCaches:
    """Test the clear_all_caches function."""

    def test_clears_resorts_cache(self):
        """Test that clear_all_caches clears the resorts cache."""
        mock_fn = MagicMock(return_value="data")
        decorated = cached_resorts(mock_fn)

        decorated("CA")
        assert mock_fn.call_count == 1

        clear_all_caches()

        decorated("CA")
        assert mock_fn.call_count == 2

    def test_clears_conditions_cache(self):
        """Test that clear_all_caches clears the conditions cache."""
        mock_fn = MagicMock(return_value="data")
        decorated = cached_conditions(mock_fn)

        decorated("big-white", "mid")
        assert mock_fn.call_count == 1

        clear_all_caches()

        decorated("big-white", "mid")
        assert mock_fn.call_count == 2

    def test_clears_snow_quality_cache(self):
        """Test that clear_all_caches clears the snow quality cache."""
        mock_fn = MagicMock(return_value="data")
        decorated = cached_snow_quality(mock_fn)

        decorated("whistler")
        assert mock_fn.call_count == 1

        clear_all_caches()

        decorated("whistler")
        assert mock_fn.call_count == 2

    def test_clears_recommendations_cache(self):
        """Test that clear_all_caches clears the recommendations cache."""
        mock_fn = MagicMock(return_value="data")
        decorated = cached_recommendations(mock_fn)

        decorated(lat=49.0)
        assert mock_fn.call_count == 1

        clear_all_caches()

        decorated(lat=49.0)
        assert mock_fn.call_count == 2

    def test_clears_all_direct_caches(self):
        """Test that all directly-accessed caches are cleared."""
        caches = [
            get_all_conditions_cache(),
            get_recommendations_cache(),
            get_resort_metadata_cache(),
            get_timeline_cache(),
        ]

        for i, cache in enumerate(caches):
            cache[f"key_{i}"] = f"value_{i}"

        clear_all_caches()

        for i, cache in enumerate(caches):
            assert f"key_{i}" not in cache

    def test_clear_is_idempotent(self):
        """Test that calling clear_all_caches multiple times is safe."""
        clear_all_caches()
        clear_all_caches()
        clear_all_caches()
        # No exception raised


class TestCacheTTLBehavior:
    """Test TTL-based expiration using a short-lived cache."""

    def test_ttl_expiration(self):
        """Test that entries expire after the TTL elapses."""
        # Create a cache with a very short TTL to test expiration
        short_cache = TTLCache(maxsize=10, ttl=0.1)  # 100ms TTL
        short_cache["key"] = "value"
        assert "key" in short_cache

        time.sleep(0.2)

        assert "key" not in short_cache

    def test_maxsize_eviction(self):
        """Test that entries are evicted when maxsize is exceeded."""
        small_cache = TTLCache(maxsize=2, ttl=300)
        small_cache["a"] = 1
        small_cache["b"] = 2
        small_cache["c"] = 3  # Should evict "a"

        assert "a" not in small_cache
        assert "b" in small_cache
        assert "c" in small_cache


class TestCacheKeyEdgeCases:
    """Test edge cases for cache key generation."""

    def test_none_argument(self):
        """Test that None argument produces a valid key."""
        key = get_cache_key(None)
        assert len(key) == 32

    def test_boolean_arguments(self):
        """Test that boolean arguments produce distinct keys."""
        key_true = get_cache_key(active=True)
        key_false = get_cache_key(active=False)
        assert key_true != key_false

    def test_numeric_arguments(self):
        """Test that int and float arguments produce distinct keys."""
        key_int = get_cache_key(42)
        key_float = get_cache_key(42.0)
        # JSON serializes 42 and 42.0 differently in Python 3.12+
        assert len(key_int) == 32
        assert len(key_float) == 32
        assert key_int != key_float

    def test_empty_string_vs_no_args(self):
        """Test that empty string arg differs from no args."""
        key_empty = get_cache_key("")
        key_none = get_cache_key()
        assert key_empty != key_none

    def test_unicode_arguments(self):
        """Test that Unicode arguments produce valid keys."""
        key = get_cache_key("Chamonix-Mont-Blanc", region="Alpes")
        assert len(key) == 32

    def test_large_argument(self):
        """Test that a large argument produces a fixed-size key."""
        large_list = list(range(10000))
        key = get_cache_key(large_list)
        assert len(key) == 32


class TestDecoratorWithExceptions:
    """Test decorator behavior when the wrapped function raises exceptions."""

    def test_exception_is_not_cached(self):
        """Test that exceptions from the function are not cached."""
        call_count = 0

        @cached_resorts
        def failing_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("temporary failure")
            return "success"

        with pytest.raises(ValueError, match="temporary failure"):
            failing_fn()

        # Second call should execute the function again (not return cached error)
        result = failing_fn()
        assert result == "success"
        assert call_count == 2

    def test_none_result_is_cached(self):
        """Test that a None return value is still cached."""
        mock_fn = MagicMock(return_value=None)
        decorated = cached_resorts(mock_fn)

        result1 = decorated("empty-resort")
        result2 = decorated("empty-resort")

        assert result1 is None
        assert result2 is None
        assert mock_fn.call_count == 1

    def test_empty_dict_is_cached(self):
        """Test that an empty dict return value is cached."""
        mock_fn = MagicMock(return_value={})
        decorated = cached_conditions(mock_fn)

        result1 = decorated("resort-a")
        result2 = decorated("resort-a")

        assert result1 == {}
        assert result2 == {}
        assert mock_fn.call_count == 1

    def test_falsy_values_are_cached(self):
        """Test that falsy return values (0, empty list) are cached."""
        mock_fn = MagicMock(return_value=0)
        decorated = cached_snow_quality(mock_fn)

        result1 = decorated("resort-a")
        result2 = decorated("resort-a")

        assert result1 == 0
        assert result2 == 0
        assert mock_fn.call_count == 1
