from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.dispatch import Signal

from django_salmon.decorators import (
    observe,
    observe_context,
    observe_lock,
    prevent_nested_observe,
    should_observe,
    with_args,
    with_resources,
    with_result,
    with_stacktrace,
    with_timing,
)


@pytest.fixture
def test_signal():
    """Create a test signal for use in tests."""
    return Signal()


@pytest.fixture
def mock_handler(test_signal):
    """Create a mock signal handler."""
    handler = MagicMock()
    test_signal.connect(handler)
    yield handler
    test_signal.disconnect(handler)


@pytest.fixture(autouse=True)
def enable_observing(settings):
    """Enable observing for all tests."""
    settings.OBSERVING = {"enabled": True}


@pytest.fixture(autouse=True)
def reset_context_vars():
    """Reset context variables between tests."""
    yield
    # Reset observe_lock
    observe_lock.set(False)
    # Reset observe_context
    observe_context.set(None)


class TestShouldObserve:
    """Test the should_observe function."""

    def test_returns_true_when_enabled(self, settings):
        """Test should_observe returns True when enabled."""
        settings.OBSERVING = {"enabled": True}
        assert should_observe() is True

    def test_returns_false_when_disabled(self, settings):
        """Test should_observe returns False when disabled."""
        settings.OBSERVING = {"enabled": False}

        assert should_observe() is False

    def test_returns_false_when_observing_locked(self, settings):
        """Test should_observe returns False when observe_lock is set."""
        settings.OBSERVING = {"enabled": True}
        observe_lock.set(True)
        assert should_observe() is False


class TestObserveDecorator:
    """Test the observe decorator."""

    def test_observe_method_sends_signal(self, test_signal, mock_handler):
        """Test that observe decorator sends signal for a method."""

        class TestClass:
            @observe(test_signal)
            def test_method(self):
                return "result"

        instance = TestClass()
        result = instance.test_method()

        assert result == "result"
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["sender"] == TestClass
        assert call_kwargs["instance"] == instance
        assert call_kwargs["function_name"] == "test_method"

    def test_observe_function_sends_signal(self, test_signal, mock_handler):
        """Test that observe decorator sends signal for a standalone function."""

        @observe(test_signal)
        def test_function():
            return "result"

        result = test_function()

        assert result == "result"
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["sender"] == test_function.__wrapped__  # type: ignore[attr-defined]
        assert call_kwargs["instance"] is None
        assert call_kwargs["function_name"] == "test_function"

    def test_observe_respects_enabled_setting(
        self, settings, test_signal, mock_handler
    ):
        """Test that observe decorator respects the enabled setting."""
        settings.OBSERVING = {"enabled": False}

        @observe(test_signal)
        def test_function():
            return "result"

        result = test_function()

        assert result == "result"
        mock_handler.assert_not_called()

    def test_observe_preserves_function_name(self, test_signal):
        """Test that observe decorator preserves the function name."""

        @observe(test_signal)
        def my_function():
            pass

        assert my_function.__name__ == "my_function"
        # Ensure the decorated function is still callable.
        my_function()

    def test_observe_stores_signal_attribute(self, test_signal):
        """Test that observe decorator stores signal on wrapper."""

        @observe(test_signal)
        def test_function():
            pass

        assert test_function.signal == test_signal  # type: ignore[attr-defined]
        # Ensure the decorated function is still callable.
        test_function()


class TestWithArgsDecorator:
    """Test the with_args decorator."""

    def test_with_args_adds_arguments(self, test_signal, mock_handler):
        """Test that with_args adds function arguments to signal."""

        class TestClass:
            @observe(test_signal)
            @with_args
            def test_method(self, arg1, arg2, kwarg1=None):
                return "result"

        instance = TestClass()
        result = instance.test_method("val1", "val2", kwarg1="kwval")

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["args"] == ("val1", "val2")
        assert call_kwargs["kwargs"] == {"kwarg1": "kwval"}

    def test_with_args_function(self, test_signal, mock_handler):
        """Test with_args with standalone function."""

        @observe(test_signal)
        @with_args
        def test_function(arg1, arg2, kwarg1=None):
            return "result"

        result = test_function("val1", "val2", kwarg1="kwval")

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["args"] == ("val1", "val2")
        assert call_kwargs["kwargs"] == {"kwarg1": "kwval"}

    def test_with_args_preserves_function_name(self, test_signal):
        """Test that with_args preserves function name."""

        @observe(test_signal)
        @with_args
        def my_function():
            pass

        assert my_function.__name__ == "my_function"
        # Ensure the decorated function is still callable.
        my_function()

    def test_with_args_classmethod(self, test_signal, mock_handler):
        """Test with_args with classmethod."""

        class TestClass:
            @classmethod
            @observe(test_signal)
            @with_args
            def test_method(cls, arg1, arg2, kwarg1=None):
                return "result"

        result = TestClass.test_method("val1", "val2", kwarg1="kwval")

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["args"] == ("val1", "val2")
        assert call_kwargs["kwargs"] == {"kwarg1": "kwval"}

    def test_with_args_staticmethod(self, test_signal, mock_handler):
        """Test with_args with staticmethod."""

        class TestClass:
            @staticmethod
            @observe(test_signal)
            @with_args
            def test_method(arg1, arg2, kwarg1=None):
                return "result"

        result = TestClass.test_method("val1", "val2", kwarg1="kwval")

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["args"] == ("val1", "val2")
        assert call_kwargs["kwargs"] == {"kwarg1": "kwval"}


class TestWithResultDecorator:
    """Test the with_result decorator."""

    def test_with_result_adds_return_value(self, test_signal, mock_handler):
        """Test that with_result adds function return value to signal."""

        @observe(test_signal)
        @with_result
        def test_function():
            return "my_result"

        result = test_function()

        assert result == "my_result"
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["result"] == "my_result"

    def test_with_result_with_none(self, test_signal, mock_handler):
        """Test with_result when function returns None."""

        @observe(test_signal)
        @with_result
        def test_function():
            return None

        result = test_function()

        assert result is None
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["result"] is None

    def test_with_result_preserves_function_name(self, test_signal):
        """Test that with_result preserves function name."""

        @observe(test_signal)
        @with_result
        def my_function():
            pass

        assert my_function.__name__ == "my_function"
        # Ensure the decorated function is still callable.
        my_function()


class TestWithStacktraceDecorator:
    """Test the with_stacktrace decorator."""

    def test_with_stacktrace_adds_stacktrace(self, test_signal, mock_handler):
        """Test that with_stacktrace adds stacktrace to signal."""

        @observe(test_signal)
        @with_stacktrace
        def test_function():
            return "result"

        result = test_function()

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs
        assert "stacktrace" in call_kwargs
        assert callable(call_kwargs["stacktrace"])

        # Test that calling the stacktrace function returns a list of strings
        stacktrace = call_kwargs["stacktrace"]()
        assert isinstance(stacktrace, list)
        assert all(isinstance(frame, str) for frame in stacktrace)

    def test_with_stacktrace_preserves_function_name(self, test_signal):
        """Test that with_stacktrace preserves function name."""

        @observe(test_signal)
        @with_stacktrace
        def my_function():
            pass

        assert my_function.__name__ == "my_function"
        # Ensure the decorated function is still callable.
        my_function()


class TestWithTimingDecorator:
    """Test the with_timing decorator."""

    def test_with_timing_adds_execution_time(self, test_signal, mock_handler):
        """Test that with_timing adds execution time to signal."""

        @observe(test_signal)
        @with_timing
        def test_function():
            return "result"

        result = test_function()

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs
        assert "time" in call_kwargs
        assert isinstance(call_kwargs["time"], float)
        assert call_kwargs["time"] >= 0

    def test_with_timing_preserves_function_name(self, test_signal):
        """Test that with_timing preserves function name."""

        @observe(test_signal)
        @with_timing
        def my_function():
            pass

        assert my_function.__name__ == "my_function"
        # Ensure the decorated function is still callable.
        my_function()


class TestWithResourcesDecorator:
    """Test the with_resources decorator."""

    def test_with_resources_adds_resource_usage(self, test_signal, mock_handler):
        """Test that with_resources adds resource usage to signal."""

        @observe(test_signal)
        @with_resources
        def test_function():
            return "result"

        result = test_function()

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs
        assert "resources" in call_kwargs
        resources = call_kwargs["resources"]
        assert isinstance(resources, dict)
        assert "utime" in resources
        assert "stime" in resources
        assert "vcsw" in resources
        assert "ivcsw" in resources
        assert "minflt" in resources
        assert "majflt" in resources

    def test_with_resources_preserves_function_name(self, test_signal):
        """Test that with_resources preserves function name."""

        @observe(test_signal)
        @with_resources
        def my_function():
            pass

        assert my_function.__name__ == "my_function"
        # Ensure the decorated function is still callable.
        my_function()


class TestPreventNestedObserve:
    """Test the prevent_nested_observe decorator."""

    def test_prevent_nested_observe_blocks_nested_signals(
        self, test_signal, mock_handler
    ):
        """Test that prevent_nested_observe blocks signals in nested calls."""

        @observe(test_signal)
        @prevent_nested_observe
        def outer_function():
            inner_function()
            return "outer"

        @observe(test_signal)
        @prevent_nested_observe
        def inner_function():
            return "inner"

        result = outer_function()

        assert result == "outer"
        # Only outer function should send signal
        assert mock_handler.call_count == 1
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["function_name"] == "outer_function"

    def test_prevent_nested_observe_allows_sequential_calls(
        self, test_signal, mock_handler
    ):
        """Test that prevent_nested_observe allows sequential (non-nested) calls."""

        @observe(test_signal)
        @prevent_nested_observe
        def test_function():
            return "result"

        result1 = test_function()
        result2 = test_function()

        assert result1 == "result"
        assert result2 == "result"
        assert mock_handler.call_count == 2

    def test_prevent_nested_observe_preserves_function_name(self, test_signal):
        """Test that prevent_nested_observe preserves function name."""

        @observe(test_signal)
        @prevent_nested_observe
        def my_function():
            pass

        assert my_function.__name__ == "my_function"
        # Ensure the decorated function is still callable.
        my_function()


class TestDecoratorCombinations:
    """Test combinations of multiple decorators."""

    def test_all_decorators_combined(self, test_signal, mock_handler):
        """Test using all decorators together."""

        @observe(test_signal)
        @prevent_nested_observe
        @with_args
        @with_result
        @with_stacktrace
        @with_timing
        @with_resources
        def test_function(arg1, kwarg1=None):
            return "result"

        result = test_function("val1", kwarg1="kwval")

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs

        # Check all data is present
        assert call_kwargs["sender"] is not None
        assert call_kwargs["function_name"] == "test_function"
        assert call_kwargs["args"] == ("val1",)
        assert call_kwargs["kwargs"] == {"kwarg1": "kwval"}
        assert call_kwargs["result"] == "result"
        assert "stacktrace" in call_kwargs
        assert "time" in call_kwargs
        assert "resources" in call_kwargs

    def test_partial_decorators(self, test_signal, mock_handler):
        """Test using a subset of decorators."""

        @observe(test_signal)
        @with_args
        @with_timing
        def test_function(arg1):
            return "result"

        result = test_function("val1")

        assert result == "result"
        call_kwargs = mock_handler.call_args.kwargs
        assert call_kwargs["args"] == ("val1",)
        assert "time" in call_kwargs
        # These should not be present
        assert "result" not in call_kwargs
        assert "stacktrace" not in call_kwargs
        assert "resources" not in call_kwargs


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_observe_without_observe_context(self):
        """Test decorators when there's no observe context."""
        # This shouldn't happen in normal usage, but test it anyway
        observe_context.set(None)

        @with_args
        def test_function(arg1):
            return "result"

        # Should not raise an error
        result = test_function("val1")
        assert result == "result"

    def test_with_resources_without_observe_context(self):
        observe_context.set(None)

        @with_resources
        def test_function():
            return "result"

        result = test_function()
        assert result == "result"

    def test_observe_with_class_method(self, test_signal, mock_handler):
        """Test observe with a class method."""

        class TestClass:
            @classmethod
            @observe(test_signal)
            def test_method(cls):
                return "result"

        result = TestClass.test_method()

        assert result == "result"
        mock_handler.assert_called_once()

    def test_observe_with_static_method(self, test_signal, mock_handler):
        """Test observe with a static method."""

        class TestClass:
            @staticmethod
            @observe(test_signal)
            def test_method():
                return "result"

        result = TestClass.test_method()

        assert result == "result"
        mock_handler.assert_called_once()

    def test_observe_with_exception(self, test_signal, mock_handler):
        """Test that exception in decorated function propagates correctly."""

        @observe(test_signal)
        def test_function():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            test_function()

        # Signal should not be sent if function raises before completion
        mock_handler.assert_not_called()
