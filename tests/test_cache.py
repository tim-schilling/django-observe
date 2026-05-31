from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.dispatch import Signal

from django_salmon.cache import observe_cache
from django_salmon.config import get_config
from django_salmon.signals import observe_cache_operation


@pytest.fixture(autouse=True)
def enable_observing(settings):
    """Enable observing for all tests."""
    settings.OBSERVING = {"enabled": True}


@pytest.fixture
def mock_handler():
    """Create a mock signal handler."""
    handler = MagicMock()
    observe_cache_operation.connect(handler)
    yield handler
    observe_cache_operation.disconnect(handler)


class TestObserveCacheSignal:
    """Test the observe_cache_operation signal."""

    def test_observe_cache_op_is_signal(self):
        """Test that observe_cache_operation is a Signal instance."""
        assert isinstance(observe_cache_operation, Signal)


class TestObserveCacheDecorator:
    """Test the observe_cache decorator."""

    def test_observe_cache_decorates_function(self, settings, mock_handler):
        """Test that observe_cache decorator works on a function."""
        settings.OBSERVING = {"enabled": True}
        get_config.cache_clear()

        @observe_cache
        def cache_get(key):
            return f"value_{key}"

        result = cache_get("test_key")

        assert result == "value_test_key"
        mock_handler.assert_called_once()

    def test_observe_cache_decorates_method(self, settings, mock_handler):
        """Test that observe_cache decorator works on a method."""
        settings.OBSERVING = {"enabled": True}
        get_config.cache_clear()

        class Cache:
            @observe_cache
            def get(self, key):
                return f"value_{key}"

        cache = Cache()
        result = cache.get("test_key")

        assert result == "value_test_key"
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["sender"] == Cache
        assert call_kwargs["instance"] == cache

    def test_observe_cache_applies_registry_decorators(self, settings, mock_handler):
        """Test that observe_cache applies decorators from registry."""
        settings.OBSERVING = {
            "enabled": True,
            "cache": [
                "django_salmon.decorators.with_args",
                "django_salmon.decorators.with_result",
            ],
        }
        get_config.cache_clear()

        @observe_cache
        def cache_get(key):
            return f"value_{key}"

        result = cache_get("test_key")

        assert result == "value_test_key"
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs

        assert "args" in call_kwargs
        assert call_kwargs["args"] == ("test_key",)

        assert "result" in call_kwargs
        assert call_kwargs["result"] == "value_test_key"

    def test_observe_cache_uses_observe_signal(self, settings, mock_handler):
        """Test that observe_cache uses the observe decorator."""
        settings.OBSERVING = {"enabled": True}
        get_config.cache_clear()

        @observe_cache
        def cache_get(key):
            return f"value_{key}"

        result = cache_get("test_key")

        assert result == "value_test_key"
        mock_handler.assert_called_once()

        call_kwargs = mock_handler.call_args.kwargs
        assert "sender" in call_kwargs
        assert "function_name" in call_kwargs
        assert call_kwargs["function_name"] == "cache_get"

    def test_observe_cache_respects_enabled_setting(self, settings, mock_handler):
        """Test that observe_cache respects the enabled setting."""
        settings.OBSERVING = {"enabled": False}
        get_config.cache_clear()

        @observe_cache
        def cache_get(key):
            return f"value_{key}"

        result = cache_get("test_key")

        assert result == "value_test_key"
        mock_handler.assert_not_called()

    def test_observe_cache_with_multiple_arguments(self, settings, mock_handler):
        """Test observe_cache with multiple arguments."""
        settings.OBSERVING = {
            "enabled": True,
            "cache": ["django_salmon.decorators.with_args"],
        }
        get_config.cache_clear()

        @observe_cache
        def cache_set(key, value, timeout=None):
            return True

        result = cache_set("test_key", "test_value", timeout=300)

        assert result is True
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["args"] == ("test_key", "test_value")
        assert call_kwargs["kwargs"] == {"timeout": 300}

    def test_observe_cache_with_timing(self, settings, mock_handler):
        """Test observe_cache with timing decorator."""
        settings.OBSERVING = {
            "enabled": True,
            "cache": ["django_salmon.decorators.with_timing"],
        }
        get_config.cache_clear()

        @observe_cache
        def cache_get(key):
            return f"value_{key}"

        result = cache_get("test_key")

        assert result == "value_test_key"
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        assert "time" in call_kwargs
        assert isinstance(call_kwargs["time"], float)
        assert call_kwargs["time"] >= 0

    def test_observe_cache_default_config(self, settings, mock_handler):
        """Test observe_cache with default configuration."""
        settings.OBSERVING = {"enabled": True}
        get_config.cache_clear()

        class Cache:
            @observe_cache
            def get(self, key):
                return f"value_{key}"

        cache = Cache()
        result = cache.get("test_key")

        assert result == "value_test_key"
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs

        assert "sender" in call_kwargs
        assert "function_name" in call_kwargs

    def test_observe_cache_preserves_function_name(self):
        """Test that observe_cache preserves function name."""

        @observe_cache
        def my_cache_function():
            pass

        assert my_cache_function.__name__ == "my_cache_function"
        # Ensure the decorated function is still callable.
        my_cache_function()


class TestObserveCacheIntegration:
    """Test observe_cache integration with real cache operations."""

    def test_observe_cache_on_cache_class_method(self, settings, mock_handler):
        """Test observe_cache on a cache class method."""
        settings.OBSERVING = {
            "enabled": True,
            "cache": [
                "django_salmon.decorators.with_args",
                "django_salmon.decorators.with_result",
            ],
        }
        get_config.cache_clear()

        class MockCache:
            @observe_cache
            def get(self, key, default=None):
                return default if key == "missing" else f"value_{key}"

            @observe_cache
            def set(self, key, value, timeout=None):
                return True

        cache = MockCache()

        result = cache.get("test_key")
        assert result == "value_test_key"
        assert mock_handler.call_count == 1

        result = cache.set("test_key", "test_value", timeout=300)
        assert result is True
        assert mock_handler.call_count == 2

    def test_observe_cache_multiple_methods(self, settings, mock_handler):
        """Test observe_cache on multiple cache methods."""
        settings.OBSERVING = {
            "enabled": True,
            "cache": ["django_salmon.decorators.with_args"],
        }
        get_config.cache_clear()

        class MockCache:
            @observe_cache
            def get(self, key):
                return f"value_{key}"

            @observe_cache
            def set(self, key, value):
                return True

            @observe_cache
            def delete(self, key):
                return True

        cache = MockCache()

        cache.get("key1")
        cache.set("key2", "value2")
        cache.delete("key3")

        assert mock_handler.call_count == 3

        calls = mock_handler.call_args_list
        assert calls[0].kwargs["function_name"] == "get"
        assert calls[1].kwargs["function_name"] == "set"
        assert calls[2].kwargs["function_name"] == "delete"
