# sesa/core/extractor_base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List

from .base_stage import Stage

Record = Dict[str, Any]
Batch = List[Record]


class Extractor(Stage, ABC):
    """
    Abstract base for all extractors. Subclasses must implement iter_records().
    Reads records from a source (Elasticsearch, S3, API, DB, ...).
    """

    @abstractmethod
    def iter_records(self) -> Iterator[Record]:
        """Yield one record (dict) at a time (streaming, bounded memory)."""
        ...

    def iter_batches(self, batch_size: int) -> Iterator[Batch]:
        """Default batching helper built on iter_records(). Override if needed."""
        batch: Batch = []
        for rec in self.iter_records():
            batch.append(rec)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


__all__ = ["Extractor", "Record", "Batch"]
