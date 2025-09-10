# SESA ETL Framework Documentation

## 📖 Overview
**SESA** is a lightweight, extensible ETL framework for building data pipelines.  
It focuses on:
- **Extractors**: data sources (Elasticsearch, APIs, databases).  
- **Storage**: intermediate persistence (S3 today, GCS/Azure/local in future).  
- **Transforms**: pluggable transformations (normalize, cast, enrich).  
- **Loaders**: destinations (Elasticsearch now, BigQuery/Snowflake/Postgres later).  

Pipelines are declarative via **YAML configs**, orchestrated by **Airflow**, and runnable via a simple CLI (`sesa run`).  

---

## 🏗️ Architecture

```
Extractor → Storage → [Transforms] → Loader
```

- **Extractor**: streams data from a source (Elasticsearch, API, JDBC, …).  
- **Storage**: writes parts (JSONL or JSONL.GZ) and a manifest to a staging bucket.  
- **Transforms**: apply record- or batch-level modifications.  
- **Loader**: upserts records into a warehouse (Elasticsearch today, others later).  

---

## 📂 Folder Structure

```
sesa/
├─ core/                # runtime + abstract classes
│  ├─ abc.py            # Extractor, Storage, Transformer, Loader, Hooks
│  ├─ job_runner.py     # batching, threading, backpressure
│  ├─ config.py         # pydantic YAML schemas
│  └─ registry.py       # plugin/entry-point loader
│
├─ extractors/          # data sources
│  ├─ elasticsearch_extractor.py
│  ├─ jdbc_extractor.py
│  └─ api_extractor.py
│
├─ storage/             # intermediate storage
│  ├─ base.py
│  ├─ manifest.py
│  ├─ s3_storage.py
│  └─ local_fs.py
│
├─ loaders/             # destinations
│  ├─ base.py
│  ├─ elasticsearch/
│  │   ├─ client.py
│  │   └─ helpers.py
│  └─ bigquery/ (future)
│
├─ transforms/          # reusable transforms
│  ├─ cast.py
│  ├─ normalize.py
│  └─ derive.py
│
├─ cli.py               # Typer CLI (`sesa`)
└─ run.py               # run_job() entrypoint
```

---

## 🔑 Core Abstractions

### Extractor
```python
class Extractor(ABC):
    def open(self): ...
    def iter_records(self) -> Iterator[Record]: ...
    def close(self): ...
```

### Storage
```python
class StorageWriter(ABC):
    def append(self, record: Record) -> None: ...
    def roll_if_needed(self) -> None: ...
    def finalize(self) -> Manifest: ...

class StorageReader(ABC):
    def iter_records(self) -> Iterator[Record]: ...
```

### Transformer
```python
class Transformer(ABC):
    def open(self): ...
    def close(self): ...
    def map_record(self, rec: Record) -> Optional[Record]: ...
    def map_batch(self, batch: list[Record]) -> list[Record]: ...
```

### Loader
```python
class LoaderClient(ABC):
    def connect(self): ...
    def prepare_target(self, dataset: str, options: dict): ...
    def upsert_batch(self, dataset: str, records: list[Record], options: dict) -> LoadResult: ...
    def finalize(self): ...
```

---

## ⚙️ Job Configuration (YAML)

```yaml
job_name: rfi_pipeline
runtime: { batch_size: 2000, max_workers: 8, max_in_flight: 8 }

extractor:
  type: elasticsearch
  connection: { hosts: ["https://es.example.com:9243"] }
  index: "rfi-*"
  query: {"range":{"@timestamp":{"gte":"{{ ds }}","lt":"{{ next_ds }}"}}}
  fields: ["_id","@timestamp","project_id","rfi_number","title","question"]

storage:
  backend: s3
  uri: "s3://my-bucket/etl/rfi/run_date={{ ds }}/run_id={{ ts_nodash }}/"
  options: { part_max_mb: 64, gzip: true }

transform:
  chain:
    - type: normalize
    - type: cast
      fields: ["created_at","responded_at"]
    - type: python_class
      path: "mycompany.transforms:RfiValidateCast"

loader:
  type: elasticsearch
  connection: { hosts: ["https://es.example.com:9243"] }
  dataset: "rfi-enriched-{created_at:%Y.%m}"
  options:
    id_strategy: { type: sha256_concat, fields: ["project_id","rfi_number"] }
    bulk: { actions_per_batch: 2000, concurrency: 4 }

dlq:
  backend: s3
  uri: "s3://my-bucket/etl/rfi/dlq/"
```

---

## 🖥️ Running Jobs

### CLI
```bash
sesa run --config jobs/rfi_pipeline.yaml   --set ds=2025-09-06 --set ts_nodash=20250906T000000Z
```

### Airflow
```python
from airflow.operators.bash import BashOperator

rfi_job = BashOperator(
  task_id="rfi_pipeline",
  bash_command=(
    "sesa run --config /opt/etl/jobs/rfi_pipeline.yaml "
    "--set ds={{ ds }} --set ts_nodash={{ ts_nodash }}"
  ),
)
```

---

## 🔌 Extending the Framework

### Custom Transformer
```python
# mycompany/transforms.py
from sesa.core.abc import Transformer

class RfiValidateCast(Transformer):
    def map_record(self, rec):
        if not rec.get("rfi_number"):
            return None  # drop invalid
        rec["validated"] = True
        return rec
```

In YAML:
```yaml
- type: python_class
  path: "mycompany.transforms:RfiValidateCast"
```

### Adding a new Extractor or Loader
Register via **entry points** in `pyproject.toml`:

```toml
[project.entry-points."sesa.extractors"]
elasticsearch = "sesa.extractors.elasticsearch_extractor:ElasticsearchExtractor"

[project.entry-points."sesa.loaders"]
elasticsearch = "sesa.loaders.elasticsearch.client:ElasticsearchLoaderClient"
```

---



---

## ⚡ Multithreading & Parallelism

SESA is designed for high-throughput pipelines using **batching**, **bounded queues** (backpressure), and a **thread pool** for transforms + loads.

### How it flows

```
Extractor (single thread; streaming)
  → batches (size = batch_size) → bounded queue (max_in_flight)
    → ThreadPool (max_workers)
        → for each batch: apply transform chain → loader.upsert_batch()
```

- **Extractor** typically pages sequentially (safe with Elasticsearch PIT + search_after).  
- **Transforms & Loader** run concurrently per-batch on worker threads.  
- **Backpressure**: if workers fall behind, the extractor blocks when the queue is full.

### Runtime knobs (YAML)

```yaml
runtime:
  batch_size: 2000        # records grouped per worker call
  max_workers: 8          # transform/load worker threads
  max_in_flight: 16       # queued batches allowed before producer blocks
```

### Pseudocode sketch

```python
# core/job_runner.py (simplified)
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

q = Queue(maxsize=cfg.runtime.max_in_flight)

def producer():
    for batch in extractor.iter_batches(cfg.runtime.batch_size):
        q.put(batch)
    for _ in range(cfg.runtime.max_workers):
        q.put(None)  # poison pills

def worker():
    # per-thread lifecycle
    for t in transformers:
        t.open()
    while True:
        batch = q.get()
        if batch is None:
            break
        out = batch
        for t in transformers:
            out = t.map_batch(out)
            if not out:
                break
        if out:
            loader.upsert_batch(cfg.loader.dataset, out, cfg.loader.options)
        q.task_done()
    for t in transformers:
        t.close()
```

### Writing thread‑friendly transforms

- Prefer **stateless** transforms; if stateful, ensure **thread safety**.
- Create per-thread clients in `open()` (e.g., `requests.Session()`), close them in `close()`.
- If you need a **shared rate limit**, use a thread-safe token bucket (or let the loader enforce global concurrency).
- Catch per-record errors and send to **DLQ**, don’t crash the batch.

```python
class ApiEnricher(Transformer):
    def open(self):
        self.session = requests.Session()  # per-thread HTTP client
    def map_batch(self, batch):
        out = []
        for rec in batch:
            try:
                r = self.session.post(self.api, json={"text": rec["question"]}, timeout=20)
                r.raise_for_status()
                rec.update(r.json())
                out.append(rec)
            except Exception as e:
                dlq.write({"record": rec, "error": str(e), "stage": "ApiEnricher"})
        return out
    def close(self):
        self.session.close()
```

### CPU‑bound work

- If a transform is CPU-heavy (e.g., large JSON parsing, NLP), consider a **ProcessPool** for that step, or precompute offline. Threads excel for I/O-bound work.

### Tuning cheatsheet

| Setting         | Typical range | Notes |
|-----------------|---------------|------|
| `batch_size`    | 1k–5k         | Larger batches improve bulk efficiency; too large makes retries costly. |
| `max_workers`   | 8–16          | I/O-bound pipelines; reduce if ES latency/429 rises. |
| `max_in_flight` | ~`max_workers`–2× | Keeps workers fed while bounding RAM. |
| ES bulk actions | 1k–5k         | Tune with `concurrency` 2–8; watch rejects & queue time. |

### Idempotency & ordering

- Batches finish **out of order**—that’s fine. Use deterministic IDs (e.g., hash of business keys) so repeats or out-of-order writes don’t duplicate. Set `id_strategy` in the loader options.


## 📊 Observability
- **Logs**: structured JSON.  
- **Metrics**: counters for records read, transformed, written; DLQ counts.  
- **DLQ**: all failed records are written with error context.  

---

## 🚀 Roadmap
- More storage backends (GCS, Azure Blob).  
- More loaders (BigQuery, Snowflake, Postgres).  
- Built-in validation & monitoring services.  
- Richer Airflow operators for fan-out jobs.  
