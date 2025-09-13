# sesa/core/loader_base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List

from .base_stage import Stage
from .storage_base import Batch


@dataclass(frozen=True)
class LoadResult:
    """
    Lightweight result object returned by LoaderClient.upsert_batch().
    - success_count: number of records successfully written
    - error_count: number of records failed to write
    - errors: optional short error messages (details should go to a DLQ)
    """

    success_count: int
    error_count: int = 0
    errors: List[str] | None = None


class LoaderClient(Stage, ABC):
    """
    Abstract base for all loaders (Elasticsearch, S3, DB, ...).
    A Loader receives batches of records and writes them to a destination.
    Implementations must provide upsert_batch(). Other hooks are optional.
    """

    def connect(self) -> None:
        """Establish clients/connections (optional)."""
        # Subclasses override if they need a client (e.g., Elasticsearch(), boto3.client("s3"))
        pass

    def prepare_target(self, dataset: str, options: Dict[str, Any]) -> None:
        """
        Ensure the destination is ready (optional).
        e.g., create ES index/alias, set mappings; create S3 prefix; migrate tables, etc.
        """
        pass

    @abstractmethod
    def upsert_batch(self, dataset: str, records: Batch, options: Dict[str, Any]) -> LoadResult:
        """
        Write one batch to the destination (MUST be implemented by subclasses).
        Should be idempotent when possible (same input → safe to re-run).
        Return a LoadResult with success/error counts.
        """
        ...

    def finalize(self) -> None:
        """Flush/close resources (optional)."""
        # Subclasses override to flush buffers or close clients
        pass


__all__ = ["LoaderClient", "LoadResult"]
