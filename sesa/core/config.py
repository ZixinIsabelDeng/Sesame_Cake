# sesa/core/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ThreadingConfig:
    """Parallelism knobs for the runner."""

    workers: int = 8  # threads for transform+load
    batch_size: int = 2000  # logical records per batch


@dataclass
class StorageConfig:
    """Optional staging (S3/local) between extract and load."""

    enabled: bool = False
    # For writers: rotate policy (only used if enabled)
    part_max_mb: int = 128
    part_max_seconds: int = 600
    part_max_records: Optional[int] = None
    # Arbitrary extra options (bucket, prefix, compression, etc.)
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobConfig:
    """
    Minimal job config the runner understands.
    The concrete components (extractor/loader/transformers/storage) are created by your code; the
    runner only needs behavior knobs.
    """

    name: str = "job"
    threading: ThreadingConfig = field(default_factory=ThreadingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    # Free-form: passed through to extractor/loader as needed
    options: Dict[str, Any] = field(default_factory=dict)
    # Optional DLQ behavior (your loader can use this or ignore)
    dlq_enabled: bool = True
    dlq_max_errors: int = 1000
