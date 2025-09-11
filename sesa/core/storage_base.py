# sesa/core/storage_base.py
from __future__ import annotations
from typing import Any, Dict, Iterator, List, Optional, Protocol
from .base_stage import Stage

Record = Dict[str, Any]
Batch = List[Record]

class ManifestLike(Protocol):
    parts: List[str]
    total_records: int
    total_bytes: int

class StorageWriter(Stage):
    """
    Writes staged parts (e.g., JSONL/JSONL.GZ) and produces a manifest.
    """

    def append(self, record: Record) -> None:
        """Append a single record to the current part/file."""
        raise NotImplementedError

    def append_batch(self, batch: Batch) -> None:
        """Default vectorized append using append()."""
        for rec in batch:
            self.append(rec)

    def roll_if_needed(self) -> None:
        """Rotate to a new part based on size/time/policy (optional)."""
        pass

    def finalize(self) -> ManifestLike:
        """
        Finish all parts and return a manifest (paths, counts, checksums/bytes).
        """
        raise NotImplementedError


class StorageReader(Stage):
    """
    Streams records back from staged storage (for publish steps or tests).
    """

    def iter_records(self) -> Iterator[Record]:
        raise NotImplementedError

__all__ = ["StorageWriter", "StorageReader", "Record", "Batch", "ManifestLike"]
