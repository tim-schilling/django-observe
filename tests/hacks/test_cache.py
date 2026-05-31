from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import CacheHandler, InvalidCacheBackendError
from django.core.cache.backends.base import BaseCache
from django.core.cache.backends.db import BaseDatabaseCache, DatabaseCache
from django.core.cache.backends.dummy import DummyCache
from django.core.cache.backends.filebased import FileBasedCache
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.memcached import (
    BaseMemcachedCache,
    PyLibMCCache,
    PyMemcacheCache,
)
from django.core.cache.backends.redis import RedisCache

from django_salmon.cache import observe_cache_operation
from django_salmon.hacks.cache import (
    WRAPPED_CACHE_METHODS,
    discover_cache_classes,
    patch_cache,
)


@pytest.fixture(autouse=True)
def enable_observing(settings):
    """Enable observing for all tests."""
    settings.OBSERVING = {"enabled": True}


@pytest.fixture
def mock_handler():
    """Create a mock signal handler."""
    return MagicMock()


class TestDiscoverCacheClasses:
    def test_returns_expected_classes(self):
        assert set(discover_cache_classes()) == {
            BaseCache,
            BaseDatabaseCache,
            BaseMemcachedCache,
            DatabaseCache,
            DummyCache,
            FileBasedCache,
            LocMemCache,
            PyLibMCCache,
            PyMemcacheCache,
            RedisCache,
        }

    def test_skips_modules_that_cannot_be_imported(self):
        with (
            patch(
                "pkgutil.iter_modules", return_value=iter([("", "bad_module", False)])
            ),
            patch("importlib.import_module", side_effect=ImportError("no module")),
        ):
            classes = discover_cache_classes()
        assert classes == []


class TestWrappedCacheMethods:
    """Test the WRAPPED_CACHE_METHODS list."""

    def test_wrapped_cache_methods_is_list(self):
        """Test that WRAPPED_CACHE_METHODS is a list."""
        assert isinstance(WRAPPED_CACHE_METHODS, list)

    def test_wrapped_cache_methods_contains_expected_methods(self):
        """Test that WRAPPED_CACHE_METHODS contains expected cache methods."""
        expected_methods = [
            "add",
            "get",
            "set",
            "get_or_set",
            "touch",
            "delete",
            "clear",
            "get_many",
            "set_many",
            "delete_many",
            "has_key",
            "incr",
            "decr",
            "incr_version",
            "decr_version",
        ]

        for method in expected_methods:
            assert method in WRAPPED_CACHE_METHODS


class TestPatchCache:
    """Test the patch_cache function."""

    def test_patch_cache_wraps_locmem_cache(self):
        """Test that patch_cache wraps LocMemCache methods."""
        original_get = LocMemCache.get
        original_set = LocMemCache.set

        patch_cache()

        assert LocMemCache.get is not original_get
        assert LocMemCache.set is not original_set

        assert callable(LocMemCache.get)
        assert callable(LocMemCache.set)

    def test_patch_cache_wraps_dummy_cache(self):
        """Test that patch_cache wraps DummyCache methods."""
        original_get = DummyCache.get

        patch_cache()

        assert DummyCache.get is not original_get
        assert callable(DummyCache.get)

    def test_patch_cache_wraps_database_cache(self):
        """Test that patch_cache wraps DatabaseCache methods."""
        original_get = DatabaseCache.get

        patch_cache()

        assert DatabaseCache.get is not original_get
        assert callable(DatabaseCache.get)

    def test_patch_cache_wraps_file_based_cache(self):
        """Test that patch_cache wraps FileBasedCache methods."""
        original_get = FileBasedCache.get

        patch_cache()

        assert FileBasedCache.get is not original_get
        assert callable(FileBasedCache.get)

    def test_patch_cache_wraps_redis_cache(self):
        """Test that patch_cache wraps RedisCache methods."""
        original_get = RedisCache.get

        patch_cache()

        assert RedisCache.get is not original_get
        assert callable(RedisCache.get)

    def test_patch_cache_wraps_all_specified_methods(self):
        """Test that patch_cache wraps all methods in WRAPPED_CACHE_METHODS."""
        original_methods = {
            method: getattr(LocMemCache, method, None)
            for method in WRAPPED_CACHE_METHODS
        }

        patch_cache()

        for method in WRAPPED_CACHE_METHODS:
            current_method = getattr(LocMemCache, method)
            assert current_method is not original_methods[method]

    def test_patch_cache_wrapped_methods_are_callable(self):
        """Test that wrapped methods are still callable."""
        patch_cache()

        for method_name in WRAPPED_CACHE_METHODS:
            assert callable(getattr(LocMemCache, method_name))


class TestPatchCacheFunctionality:
    """Test that patched cache methods actually work."""

    def test_patched_locmem_cache_get(self):
        """Test that patched LocMemCache.get still works."""
        patch_cache()

        cache = LocMemCache("test", {"LOCATION": "test"})
        cache.set("key", "value")

        result = cache.get("key")
        assert result == "value"

    def test_patched_locmem_cache_set(self):
        """Test that patched LocMemCache.set still works."""
        patch_cache()

        cache = LocMemCache("test", {"LOCATION": "test"})

        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_patched_locmem_cache_delete(self):
        """Test that patched LocMemCache.delete still works."""
        patch_cache()

        cache = LocMemCache("test", {"LOCATION": "test"})
        cache.set("key", "value")

        cache.delete("key")
        assert cache.get("key") is None

    def test_patched_dummy_cache_get(self):
        """Test that patched DummyCache.get still works."""
        patch_cache()

        cache = DummyCache("test", {})

        result = cache.get("key")
        assert result is None

    def test_patched_cache_triggers_signal(self, mock_handler):
        """Test that patched cache methods trigger signals."""
        patch_cache()
        observe_cache_operation.connect(mock_handler)

        cache = LocMemCache("test", {"LOCATION": "test"})

        cache.set("key", "value")

        mock_handler.assert_called()
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["function_name"] == "set"
        assert call_kwargs["sender"] == LocMemCache

        observe_cache_operation.disconnect(mock_handler)

    def test_patched_cache_multiple_operations(self, mock_handler):
        """Test that multiple cache operations trigger multiple signals."""
        patch_cache()
        observe_cache_operation.connect(mock_handler)

        cache = LocMemCache("test", {"LOCATION": "test"})

        cache.set("key1", "value1")
        cache.get("key1")
        cache.delete("key1")

        assert mock_handler.call_count == 3

        calls = [call.kwargs["function_name"] for call in mock_handler.call_args_list]
        assert "set" in calls
        assert "get" in calls
        assert "delete" in calls

        observe_cache_operation.disconnect(mock_handler)


class TestPatchCacheAlias:
    """Test that patch_cache patches BaseCache.__init__ and CacheHandler.create_connection."""

    def test_base_cache_init_accepts_alias(self):
        patch_cache()

        cache = BaseCache({}, alias="my-alias")
        assert cache.alias == "my-alias"

    def test_base_cache_init_alias_defaults_to_none(self):
        patch_cache()

        cache = BaseCache({})
        assert cache.alias is None

    def test_cache_handler_sets_alias_on_connection(self, settings):
        settings.CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            }
        }
        patch_cache()

        handler = CacheHandler()
        cache = handler["default"]
        assert cache.alias == "default"

    def test_cache_handler_sets_alias_for_named_cache(self, settings):
        settings.CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            },
            "secondary": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            },
        }
        patch_cache()

        handler = CacheHandler()
        assert handler["default"].alias == "default"
        assert handler["secondary"].alias == "secondary"


class TestPatchCacheWithDisabledObserving:
    """Test patched cache with observing disabled."""

    def test_patched_cache_works_when_disabled(self, settings):
        """Test that patched cache still works when observing is disabled."""
        settings.OBSERVING = {"enabled": False}

        patch_cache()

        cache = LocMemCache("test", {"LOCATION": "test"})

        cache.set("key", "value")
        result = cache.get("key")
        assert result == "value"

    def test_patched_cache_no_signal_when_disabled(self, settings, mock_handler):
        """Test that patched cache doesn't send signals when disabled."""
        settings.OBSERVING = {"enabled": False}

        patch_cache()
        observe_cache_operation.connect(mock_handler)

        cache = LocMemCache("test", {"LOCATION": "test"})
        cache.set("key", "value")

        mock_handler.assert_not_called()

        observe_cache_operation.disconnect(mock_handler)


class TestPatchedCreateConnectionErrors:
    def test_raises_on_invalid_backend(self, settings):
        settings.CACHES = {
            "default": {
                "BACKEND": "nonexistent.module.CacheClass",
            }
        }
        patch_cache()

        handler = CacheHandler()
        with pytest.raises(InvalidCacheBackendError):
            _ = handler["default"]
