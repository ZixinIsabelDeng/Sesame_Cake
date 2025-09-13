# sesa/core/transformer_base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from .base_stage import Stage
from .storage_base import Batch, Record


class Transformer(Stage, ABC):
    """
    Abstract base for all transformers.
    Implement at least map_record(); optionally override map_batch() for batch-level work.
    Prefer stateless logic; if stateful (e.g., HTTP clients), create them in open().
    Return None from map_record() to drop a record.
    """

    @abstractmethod
    def map_record(self, rec: Record) -> Optional[Record]:
        """
        Transform one record.
        Return:
          - a dict (kept) or
          - None (dropped)
        """
        ...

    def map_batch(self, batch: Batch) -> Batch:
        """
        Default batch transform: apply map_record() to each item and drop Nones.
        Override for vectorized ops (e.g., dedup across batch, one HTTP call per batch).
        """
        out: List[Record] = []
        for rec in batch:
            mapped = self.map_record(rec)
            if mapped is not None:
                out.append(mapped)
        return out


__all__ = ["Transformer"]
