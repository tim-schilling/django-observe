from __future__ import annotations

from django_salmon.config import CONFIG_DEFAULTS, get_config
from django_salmon.decorators import should_observe, with_args, with_result
from django_salmon.registry import ObserveRegistry


class TestGetConfig:
    """Test the get_config function."""

    def test_get_config_returns_defaults_when_no_user_config(self, settings):
        """Test that get_config returns defaults when no user config is set."""
        settings.OBSERVING = {}
        config = get_config()

        assert config["enabled"] is True
        assert "cache" in config
        assert isinstance(config["cache"], list)

    def test_get_config_merges_user_config(self, settings):
        """Test that get_config merges user config with defaults."""
        settings.OBSERVING = {
            "enabled": False,
            "custom_key": "custom_value",
        }

        config = get_config()

        # User config should override defaults
        assert config["enabled"] is False
        # User config should add new keys
        assert config["custom_key"] == "custom_value"
        # Defaults should still be present if not overridden
        assert "cache" in config

    def test_get_config_overrides_cache_setting(self, settings):
        """Test that user can override the cache setting."""
        settings.OBSERVING = {
            "cache": ["custom.decorator.path"],
        }

        config = get_config()

        assert config["cache"] == ["custom.decorator.path"]

    def test_config_defaults_cache_decorators(self):
        """Test that CONFIG_DEFAULTS contains expected cache decorators."""
        cache_decorators: list[str] = CONFIG_DEFAULTS["cache"]  # type: ignore[assignment]

        # Check for expected decorators
        expected_decorators = [
            "django_salmon.decorators.prevent_nested_observe",
            "django_salmon.decorators.with_args",
            "django_salmon.decorators.with_result",
            "django_salmon.decorators.with_stacktrace",
            "django_salmon.decorators.with_timing",
        ]

        for expected in expected_decorators:
            assert expected in cache_decorators

    def test_get_config_empty_user_config(self, settings):
        """Test get_config with empty user config."""
        settings.OBSERVING = {}

        config = get_config()

        # Should have all defaults
        assert config["enabled"] is True
        assert "cache" in config

    def test_get_config_partial_user_config(self, settings):
        """Test get_config with partial user config."""
        settings.OBSERVING = {
            "enabled": False,
        }

        config = get_config()

        # User setting should be applied
        assert config["enabled"] is False
        # Defaults should fill in the rest
        assert "cache" in config
        assert config["cache"] == CONFIG_DEFAULTS["cache"]

    def test_get_config_with_complex_user_config(self, settings):
        """Test get_config with complex user configuration."""
        settings.OBSERVING = {
            "enabled": True,
            "cache": [
                "custom.decorator.one",
                "custom.decorator.two",
            ],
            "database": [
                "custom.db.decorator",
            ],
            "custom_setting": {
                "nested": "value",
            },
        }

        config = get_config()

        assert config["enabled"] is True
        assert config["cache"] == ["custom.decorator.one", "custom.decorator.two"]
        assert config["database"] == ["custom.db.decorator"]
        assert config["custom_setting"] == {"nested": "value"}


class TestConfigurationIntegration:
    """Test configuration integration with other components."""

    def test_config_used_by_decorators(self, settings):
        """Test that decorators use config to determine if observing is enabled."""
        settings.OBSERVING = {"enabled": True}

        assert should_observe() is True

        settings.OBSERVING = {"enabled": False}
        get_config.cache_clear()

        assert should_observe() is False

    def test_config_used_by_registry(self, settings):
        """Test that registry uses config to get decorators from settings."""
        settings.OBSERVING = {
            "test_component": [
                "django_salmon.decorators.with_args",
                "django_salmon.decorators.with_result",
            ],
        }

        registry = ObserveRegistry()
        decorators = registry.get_decorators("test_component")

        assert with_args in decorators
        assert with_result in decorators
