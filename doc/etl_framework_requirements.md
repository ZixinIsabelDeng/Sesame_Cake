# ETL Framework – Requirements

## Goal
Build a lightweight, performant Python ETL framework that moves data **from** Elasticsearch or S3 **to** Elasticsearch or S3, with optional transforms (data manipulation + external API calls) and **Airflow** orchestration. It must support **multithreading** and **parallel processing**.

---

## 1. Scope & Non-Goals

### In Scope
- Sources: Elasticsearch (ES), Amazon S3.
- Destinations: Elasticsearch (ES), Amazon S3.
- Transforms: record/batch manipulation, lookups via external HTTP APIs.
- Orchestration: Airflow DAGs (daily/hourly, backfills).
- Observability: logging + simple metrics.
- Reliability: retries, backoff, idempotency.

### Not in Scope (for v1)
- Streaming systems (Kafka, Kinesis).
- Complex schema evolution tooling.
- GUI/portal interface.

---

## 2. High-Level Architecture

```
Airflow DAG
   └── ETL Job (Python)
        ├── Extractor (ES/S3)
        ├── Transformer (pure funcs + API clients)
        └── Loader (ES bulk / S3 put)
```

- **ETL Job** is a reusable class configured with:
  - `SourceConfig`
  - `TransformConfig`
  - `DestinationConfig`
  - `RuntimeConfig`
- **Concurrency**: IO-bound steps use `ThreadPoolExecutor`; CPU-heavy steps may use `ProcessPoolExecutor`.

---

## 3. Functional Requirements

### 3.1 Extractors
- **Elasticsearch**
  - Support index + query (DSL) + time range.
  - Use **Point-In-Time (PIT)** or **Scroll** for pagination.
  - Configurable page size (default 1,000).
  - Return `_source` only; include `_id` if requested.
- **S3**
  - Support `s3://bucket/prefix` listing.
  - Read JSON Lines (`.jsonl`) or gzip’ed JSONL (`.jsonl.gz`).
  - Optional client-side decompression.

### 3.2 Transformers
- **Record-level** pure functions (e.g., field renames, type casts, filters).
- **Batch-level** functions (e.g., aggregation, deduplication).
- **External API enrichment**
  - HTTP client with connection pooling, timeouts, and rate limiting.
  - Retries with exponential backoff.
  - Optional in-memory caching.
- **Config-driven**: chain transforms via YAML/JSON.

### 3.3 Loaders
- **Elasticsearch**
  - Bulk API with configurable batch size (default 2,000 docs).
  - Upsert by `_id` (idempotent) or insert with auto IDs.
  - Route bad docs to **dead-letter file** in S3.
- **S3**
  - Write JSONL or JSONL.GZ to `s3://bucket/prefix/date=/run_id=.../part-xxxxx`.
  - Support multipart upload for large files.
  - Optional partitioning by date or custom field.

### 3.4 Airflow Orchestration
- Provide a **DAG factory** to generate DAGs from job config.
- Tasks: `extract → transform → load → finalize`.
- Backfill support (`start_date` + `schedule_interval`).
- XCom for small metadata only.
- Fail task if error rate > threshold; persist dead-letter queue.

---

## 4. Non-Functional Requirements

- **Language**: Python 3.11.
- **Performance Targets**
  - ES→S3: ≥ 15k docs/min (1 KB docs, single worker).
  - S3→ES: ≥ 8k docs/min (single worker, bulked).
- **Scalability**
  - Configurable `max_workers`, `batch_size`, `max_in_flight_batches`.
  - Backpressure: pause new API calls if in-flight > limit.
- **Reliability**
  - Retries with jittered exponential backoff.
  - Idempotent loads (ES by `_id`; S3 by deterministic key).
- **Security**
  - Credentials via environment/secret backend (no hardcoding).
  - IAM least privilege.
- **Observability**
  - Structured JSON logs.
  - Metrics: counts, duration, error rate, retries.
- **Testing**
  - Unit tests (extract/transform/load).
  - Integration tests (ES test container + moto for S3).

---

## 5. Tech Choices

- **Core**: Python 3.11, `pydantic` (config validation).
- **Elasticsearch**: `elasticsearch` (official client).
- **S3**: `boto3`.
- **HTTP**: `requests` (simple, consistent).
- **Concurrency**: `concurrent.futures.ThreadPoolExecutor`.
- **Retries**: `tenacity`.
- **Compression**: `gzip`.
- **Logging**: `structlog` or stdlib JSON logging.
- **Airflow**: v2.x, using `PythonOperator` or TaskFlow API.

---

## 6. Example Job Configuration

**job.yaml**
```yaml
job_name: es_to_s3_daily
runtime:
  batch_size: 2000
  max_workers: 16
  max_in_flight_batches: 8
  api_rate_per_sec: 20
source:
  type: elasticsearch
  hosts: ["https://es.company:9243"]
  index: "logs-*"
  query: {"range": {"@timestamp": {"gte": "{{ ds }}", "lt": "{{ next_ds }}"}}}
  fields: ["@timestamp","message","app","host"]
transform:
  steps:
    - type: filter
      where: "record.get('app') == 'frontend'"
```
