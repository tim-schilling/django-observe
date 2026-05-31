from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from django_salmon.decorators import with_args, with_result, with_timing
from django_salmon.registry import ObserveRegistry, registry


@pytest.fixture
def test_registry():
    """Create a fresh registry for testing."""
    return ObserveRegistry()


@pytest.fixture
def mock_decorator() -> Callable[[Callable[..., Any], int | None], Callable[..., Any]]:
    """Create a mock decorator function."""

    def decorator(
        func: Callable[..., Any], registry_wrapped_index: int | None = None
    ) -> Callable[..., Any]:
        func._decorated = True  # type: ignore[attr-defined]
        func._wrapped_index = registry_wrapped_index  # type: ignore[attr-defined]
        return func

    return decorator


@pytest.fixture
def another_mock_decorator() -> Callable[
    [Callable[..., Any], int | None], Callable[..., Any]
]:
    """Create another mock decorator function."""

    def decorator(
        func: Callable[..., Any], registry_wrapped_index: int | None = None
    ) -> Callable[..., Any]:
        func._another_decorated = True  # type: ignore[attr-defined]
        func._another_wrapped_index = registry_wrapped_index  # type: ignore[attr-defined]
        return func

    return decorator


class TestObserveRegistry:
    """Test the ObserveRegistry class."""

    def test_register_single_decorator(self, test_registry, mock_decorator):
        """Test registering a single decorator."""
        test_registry.register("cache", mock_decorator)

        decorators = test_registry.get_decorators("cache")
        assert mock_decorator in decorators

    def test_register_multiple_decorators(
        self, test_registry, mock_decorator, another_mock_decorator, settings
    ):
        """Test registering multiple decorators for same component."""
        settings.OBSERVING = {"enabled": True}

        test_registry.register("cache", mock_decorator)
        test_registry.register("cache", another_mock_decorator)

        decorators = test_registry.get_decorators("cache")
        assert mock_decorator in decorators
        assert another_mock_decorator in decorators

    def test_register_different_components(
        self, test_registry, mock_decorator, settings
    ):
        """Test registering decorators for different components."""
        settings.OBSERVING = {"enabled": True}

        test_registry.register("cache", mock_decorator)
        test_registry.register("database", mock_decorator)

        cache_decorators = test_registry.get_decorators("cache")
        database_decorators = test_registry.get_decorators("database")

        assert mock_decorator in cache_decorators
        assert mock_decorator in database_decorators

    def test_get_decorators_empty_component(self, test_registry):
        """Test getting decorators for a component with no decorators."""
        decorators = test_registry.get_decorators("nonexistent")
        assert decorators == []

    def test_get_decorators_from_settings(self, test_registry, settings):
        """Test getting decorators from Django settings."""
        settings.OBSERVING = {
            "enabled": True,
            "test_component": [
                "django_salmon.decorators.with_args",
                "django_salmon.decorators.with_result",
            ],
        }

        decorators = test_registry.get_decorators("test_component")

        assert with_args in decorators
        assert with_result in decorators

    def test_get_decorators_combines_settings_and_registry(
        self, test_registry, settings, mock_decorator
    ):
        """Test that get_decorators combines settings and registry decorators."""
        settings.OBSERVING = {
            "enabled": True,
            "cache": ["django_salmon.decorators.with_args"],
        }

        test_registry.register("cache", mock_decorator)

        decorators = test_registry.get_decorators("cache")

        assert with_args in decorators
        assert mock_decorator in decorators

    def test_get_decorators_handles_non_list_settings(self, test_registry, settings):
        """Test that get_decorators handles non-list settings gracefully."""
        settings.OBSERVING = {
            "enabled": True,
            "test_component": "not a list",
        }

        decorators = test_registry.get_decorators("test_component")
        assert decorators == []

    def test_apply_decorators_single(self, test_registry, mock_decorator):
        """Test applying a single decorator to a function."""
        test_registry.register("test", mock_decorator)

        def test_func():
            return "result"

        decorated = test_registry.apply_decorators("test", test_func)

        assert hasattr(decorated, "_decorated")
        assert decorated._decorated is True
        assert decorated() == "result"

    def test_apply_decorators_multiple(
        self, test_registry, mock_decorator, another_mock_decorator
    ):
        """Test applying multiple decorators to a function."""
        test_registry.register("test", mock_decorator)
        test_registry.register("test", another_mock_decorator)

        def test_func():
            return "result"

        decorated = test_registry.apply_decorators("test", test_func)

        # Both decorators should be applied
        assert hasattr(decorated, "_decorated")
        assert decorated._wrapped_index == 1
        assert hasattr(decorated, "_another_decorated")
        assert decorated._another_wrapped_index == 0
        assert decorated() == "result"

    def test_apply_decorators_order(self, test_registry):
        """Test that decorators are applied in the correct order."""
        order = []

        def first_decorator(func, registry_wrapped_index):
            order.append("first")
            return func

        def second_decorator(func, registry_wrapped_index):
            order.append("second")
            return func

        test_registry.register("test", first_decorator)
        test_registry.register("test", second_decorator)

        def test_func():
            pass

        result_func = test_registry.apply_decorators("test", test_func)
        # Ensure the decorated function is still callable.
        result_func()

        # Decorators should be applied in order: first, then second
        assert order == ["first", "second"]

    def test_apply_decorators_no_decorators(self, test_registry):
        """Test applying decorators when none are registered."""

        def test_func():
            return "result"

        decorated = test_registry.apply_decorators("nonexistent", test_func)

        # Should return the original function unchanged
        assert decorated is test_func
        assert decorated() == "result"


class TestGlobalRegistry:
    """Test the global registry instance."""

    def test_global_registry_is_observe_registry(self):
        """Test that the global registry is an ObserveRegistry instance."""
        assert isinstance(registry, ObserveRegistry)

    def test_global_registry_register(self):
        """Test that we can register decorators on the global registry."""

        def test_decorator(func):
            return func

        # Register on global registry
        registry.register("test_component", test_decorator)

        # Should be retrievable
        decorators = registry.get_decorators("test_component")
        assert test_decorator in decorators
        assert test_decorator(test_decorator) is test_decorator

        # Clean up
        registry._decorators.pop("test_component", None)

    def test_global_registry_persistence(self):
        """Test that registrations persist on the global registry."""

        def test_decorator(func):
            return func

        registry.register("persistent_test", test_decorator)

        # Should be retrievable later
        decorators = registry.get_decorators("persistent_test")
        assert test_decorator in decorators
        assert test_decorator(test_decorator) is test_decorator

        # Clean up
        registry._decorators.pop("persistent_test", None)


class TestRegistryIntegration:
    """Test registry integration with real decorators."""

    def test_registry_with_real_decorators(self, test_registry, settings):
        """Test registry with actual observe decorators."""
        settings.OBSERVING = {
            "enabled": True,
            "test_component": [
                "django_salmon.decorators.with_args",
                "django_salmon.decorators.with_result",
            ],
        }
        test_registry.register("test_component", with_timing)

        decorators = test_registry.get_decorators("test_component")

        assert with_args in decorators
        assert with_result in decorators
        assert with_timing in decorators

    def test_apply_decorators_functional(self, test_registry):
        """Test that apply_decorators actually works with functional decorators."""
        test_registry.register("test", with_args)
        test_registry.register("test", with_result)

        def test_func():
            return "result"

        decorated = test_registry.apply_decorators("test", test_func)

        assert decorated is not test_func
        assert callable(decorated)
        assert decorated() == "result"
