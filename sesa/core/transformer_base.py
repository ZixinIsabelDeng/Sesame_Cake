# sesa/core/transformer_base.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
from .storage_base import Batch, Record
from .base_stage import Stage

class Transformer(Stage):
    """
    Transforms records. Prefer stateless logic.
    If stateful (e.g., HTTP clients), create per-thread resources in open().
    Return None to drop a record.
    """

    def map_record(self, rec: Record) -> Optional[Record]:
        """Default per-record transform: identity."""
        return rec

    def map_batch(self, batch: Batch) -> Batch:
        """
        Default batch transform applies map_record() and drops None results.
        Override for vectorized operations or API fanout.
        """
        out: List[Record] = []
        for rec in batch:
            mapped = self.map_record(rec)
            if mapped is not None:
                out.append(mapped)
        return out

__all__ = ["Transformer"]
