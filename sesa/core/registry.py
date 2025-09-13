# sesa/core/registry.py
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Type, TypeVar

T = TypeVar("T")


class Registry:
    """
    Lightweight class registry.
    Example:
        @register("elasticsearch_extractor")
        class ElasticsearchExtractor(...): ...
    """

    def __init__(self) -> None:
        self._items: Dict[str, Type[Any]] = {}

    def register(self, name: str, cls: Type[Any]) -> None:
        key = name.lower()
        if key in self._items and self._items[key] is not cls:
            raise ValueError(f"Registry already has a different item for '{name}'")
        self._items[key] = cls

    def get(self, name: str) -> Optional[Type[Any]]:
        return self._items.get(name.lower())

    def create(self, name: str, *args: Any, **kwargs: Any) -> Any:
        cls = self.get(name)
        if not cls:
            raise KeyError(f"Unknown component '{name}'")
        return cls(*args, **kwargs)


# Global registry instance and decorator shortcut
_global_registry = Registry()


def register(name: str) -> Callable[[Type[T]], Type[T]]:
    def deco(cls: Type[T]) -> Type[T]:
        _global_registry.register(name, cls)
        return cls

    return deco


# convenience exports
def get_registry() -> Registry:
    return _global_registry
