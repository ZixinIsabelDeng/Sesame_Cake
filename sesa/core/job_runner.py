# sesa/core/job_runner.py
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List, Sequence

from .config import JobConfig
from .extractor_base import Batch, Extractor
from .loader_base import LoaderClient, LoadResult
from .storage_base import ManifestLike, StorageReader, StorageWriter
from .transformer_base import Transformer


class JobRunner:
    """
    Orchestrates a job:
      - Option A: Extract -> Storage (stage only)
      - Option B: Extract -> [Transforms] -> Loader
      - Option C: StorageReader -> [Transforms] -> Loader (publish from staged data)
    Thread pool is applied around Transform+Load for throughput.
    """

    def __init__(self, cfg: JobConfig) -> None:
        self.cfg = cfg
        self._lock = threading.Lock()
        self._total_ok = 0
        self._total_err = 0

    # ---------------------- public entry points ----------------------

    def run_extract_to_storage(self, extractor: Extractor, writer: StorageWriter) -> ManifestLike:
        """Pipeline: Extract → Storage (produce manifest)."""
        extractor.open()
        writer.open()
        try:
            for batch in extractor.iter_batches(self.cfg.threading.batch_size):
                writer.append_batch(batch)
                writer.roll_if_needed()
            manifest = writer.finalize()
            return manifest
        finally:
            # always close in reverse order
            writer.close()
            extractor.close()

    def run_storage_to_loader(
        self,
        reader: StorageReader,
        transformers: Sequence[Transformer],
        loader: LoaderClient,
    ) -> tuple[int, int]:
        """Pipeline: StorageReader → [Transforms] → Loader."""
        reader.open()
        for t in transformers:
            t.open()
        loader.connect()
        loader.prepare_target(
            dataset=self.cfg.options.get("dataset", "default"), options=self.cfg.options
        )

        try:
            # central batching (reader yields records)
            batches = _batch_iter(reader.iter_records(), self.cfg.threading.batch_size)
            self._run_batches_parallel(batches, transformers, loader)
            loader.finalize()
            return (self._total_ok, self._total_err)
        finally:
            loader.close()
            for t in reversed(transformers):
                t.close()
            reader.close()

    def run_extract_to_loader(
        self,
        extractor: Extractor,
        transformers: Sequence[Transformer],
        loader: LoaderClient,
    ) -> tuple[int, int]:
        """Pipeline: Extract → [Transforms] → Loader (no staging)."""
        extractor.open()
        for t in transformers:
            t.open()
        loader.connect()
        loader.prepare_target(
            dataset=self.cfg.options.get("dataset", "default"), options=self.cfg.options
        )

        try:
            batches = extractor.iter_batches(self.cfg.threading.batch_size)
            self._run_batches_parallel(batches, transformers, loader)
            loader.finalize()
            return (self._total_ok, self._total_err)
        finally:
            loader.close()
            for t in reversed(transformers):
                t.close()
            extractor.close()

    # ---------------------- internals ----------------------

    def _run_batches_parallel(
        self,
        batches: Iterable[Batch],
        transformers: Sequence[Transformer],
        loader: LoaderClient,
    ) -> None:
        """
        Apply transforms then load, using a thread pool.
        Each task:
          1) transform batch through chain
          2) call loader.upsert_batch
        """
        workers = max(1, self.cfg.threading.workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(self._process_one, batch, transformers, loader) for batch in batches
            ]
            for fut in as_completed(futures):
                ok, err = fut.result()
                with self._lock:
                    self._total_ok += ok
                    self._total_err += err

    def _process_one(
        self,
        batch: Batch,
        transformers: Sequence[Transformer],
        loader: LoaderClient,
    ) -> tuple[int, int]:
        # 1) run through transformers (map_batch chaining)
        for t in transformers:
            batch = t.map_batch(batch)
            if not batch:
                return (0, 0)

        # 2) load
        result: LoadResult = loader.upsert_batch(
            dataset=self.cfg.options.get("dataset", "default"),
            records=batch,
            options=self.cfg.options,
        )
        return (result.success_count, result.error_count)


# ------------ helpers ------------


def _batch_iter(records: Iterable[dict], size: int) -> Iterable[Batch]:
    """Turn an iterator of records into an iterator of batches."""
    batch: List[dict] = []
    for rec in records:
        batch.append(rec)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
