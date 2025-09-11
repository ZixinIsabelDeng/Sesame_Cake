# sesa/core/extractor_base.py
from __future__ import annotations
from typing import Any, Dict, Iterator, List
from .base_stage import Stage

Record = Dict[str, Any]
Batch = List[Record]

class Extractor(Stage):
    """
    Reads records from a source (Elasticsearch, S3, API, DB, ...).
    Implement iter_records() to stream dictionaries (bounded memory).
    """

    def iter_records(self) -> Iterator[Record]:
        """Yield one record (dict) at a time."""
        raise NotImplementedError

    def iter_batches(self, batch_size: int) -> Iterator[Batch]:
        """Default batching helper built on iter_records()."""
        batch: Batch = []
        for rec in self.iter_records():
            batch.append(rec)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

__all__ = ["Extractor", "Record", "Batch"]
