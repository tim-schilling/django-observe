from __future__ import annotations

from django_salmon.cache import observe_cache
from django_salmon.hacks.cache import patch_cache


def patch() -> None:
    patch_cache(observe_cache)
