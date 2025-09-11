# sesa/core/base_stage.py
from __future__ import annotations
from abc import ABC
from typing import Any

class Stage(ABC):
    """
    Minimal lifecycle base for all ETL stages.
    Subclasses override open()/close() if they need resources (clients, files, etc.).
    """

    def open(self) -> None:
        """Per-run init. Called once before work starts."""
        pass

    def close(self) -> None:
        """Per-run teardown. Called once after work finishes (success or failure)."""
        pass

__all__ = ["Stage"]
