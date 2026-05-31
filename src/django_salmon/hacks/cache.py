from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Callable
from typing import Any

import django.core.cache.backends
from django.core.cache import CacheHandler, InvalidCacheBackendError
from django.core.cache.backends.base import BaseCache
from django.utils.module_loading import import_string

WRAPPED_CACHE_METHODS = [
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


def discover_cache_classes() -> list[type[BaseCache]]:
    classes: set[type[BaseCache]] = set()
    for _, module_name, _ in pkgutil.iter_modules(django.core.cache.backends.__path__):
        try:
            module = importlib.import_module(
                f"django.core.cache.backends.{module_name}"
            )
        except ImportError:
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseCache) and obj.__module__.startswith(
                "django.core.cache.backends"
            ):
                classes.add(obj)
    return list(classes)


WRAPPED_CACHE_CLASSES = discover_cache_classes()


def patch_init(cache_class: type[BaseCache]) -> None:
    original_base_cache_init = cache_class.__init__

    def patched_cache_init(self: BaseCache, *args: Any, **kwargs: Any) -> None:
        alias = kwargs.pop("alias", None)
        original_base_cache_init(self, *args, **kwargs)
        self.alias = alias

    cache_class.__init__ = patched_cache_init


def patch_cache(
    observe_decorator: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> None:
    """
    Patch Django's cache for improved observability.

    This wires up the passed in observe decorator on the wrapped cache methods,
    and patches Django's cache to pass and store the CACHES setting alias
    on the cache instance.
    """

    for cache_class in WRAPPED_CACHE_CLASSES:
        patch_init(cache_class)

        for method in WRAPPED_CACHE_METHODS:
            new_method = observe_decorator(getattr(cache_class, method))
            setattr(cache_class, method, new_method)

    def patched_create_connection(self: CacheHandler, alias: str) -> BaseCache:
        params = self.settings[alias].copy()
        backend = params.pop("BACKEND")
        location = params.pop("LOCATION", "")
        try:
            backend_cls = import_string(backend)
        except ImportError as e:
            raise InvalidCacheBackendError(
                "Could not find backend '%s': %s" % (backend, e)  # noqa: UP031
            ) from e
        connection = backend_cls(location, params, alias=alias)
        connection.alias = alias
        return connection

    CacheHandler.create_connection = patched_create_connection
