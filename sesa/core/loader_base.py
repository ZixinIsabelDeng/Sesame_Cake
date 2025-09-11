# sesa/core/loader_base.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
from .storage_base import Batch
from .base_stage import Stage

@dataclass(frozen=True)
class LoadResult:
    success_count: int
    error_count: int = 0
    # Keep messages short; for details use DLQ
    errors: List[str] | None = None

class LoaderClient(Stage):
    """
    Writes batches to a destination (Elasticsearch, S3, DB, ...).
    Must be safe to call concurrently from multiple threads.
    """

    def connect(self) -> None:
        """Establish connections/clients. Optional."""
        pass

    def prepare_target(self, dataset: str, options: Dict[str, Any]) -> None:
        """Create target resources (e.g., ES index template/alias). Optional."""
        pass

    def upsert_batch(self, dataset: str, records: Batch, options: Dict[str, Any]) -> LoadResult:
        """Write a batch; should be idempotent when possible."""
        raise NotImplementedError

    def finalize(self) -> None:
        """Flush/close connections. Optional."""
        pass

__all__ = ["LoaderClient", "LoadResult"]
