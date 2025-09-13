# sesa/core/storage_base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Protocol

from .base_stage import Stage

Record = Dict[str, Any]
Batch = List[Record]


class ManifestLike(Protocol):
    parts: List[str]
    total_records: int
    total_bytes: int


class StorageWriter(Stage, ABC):
    """
    Writes staged parts (e.g., JSONL/JSONL.GZ) and produces a manifest.
    """

    @abstractmethod
    def append(self, record: Record) -> None:
        """Append a single record to the current part/file."""
        ...

    def append_batch(self, batch: Batch) -> None:
        """Default vectorized append using append()."""
        for rec in batch:
            self.append(rec)

    def roll_if_needed(self) -> None:
        """Rotate to a new part based on size/time/policy (optional)."""
        pass

    @abstractmethod
    def finalize(self) -> ManifestLike:
        """
        Finish all parts and return a manifest (paths, counts, checksums/bytes).
        """
        raise NotImplementedError


class StorageReader(Stage, ABC):
    """
    Streams records back from staged storage (for publish steps or tests).
    """

    def iter_records(self) -> Iterator[Record]:
        raise NotImplementedError


__all__ = ["StorageWriter", "StorageReader", "Record", "Batch", "ManifestLike"]
