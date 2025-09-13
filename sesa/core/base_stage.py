# sesa/core/base_stage.py
from __future__ import annotations

from abc import ABC


class Stage(ABC):  # noqa: B024
    """
    Minimal lifecycle base for all ETL stages.
    Subclasses override open()/close() if they need resources (clients, files, etc.).
    """

    def open(self) -> None:  # noqa: B027
        """Per-run init. Called once before work starts."""
        pass

    def close(self) -> None:  # noqa: B027
        """Per-run teardown. Called once after work finishes (success or failure)."""
        pass


__all__ = ["Stage"]
