from __future__ import annotations

import pytest

from django_salmon.config import get_config


@pytest.fixture(autouse=True)
def clear_get_config_cache():
    get_config.cache_clear()
    yield
