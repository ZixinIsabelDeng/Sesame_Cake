# sesa/extractor/es_extractor.py
from __future__ import annotations

from typing import Any, Dict, Iterator

from elasticsearch import Elasticsearch, helpers
from sesa.core.extractor_base import Extractor, Record


class ElasticsearchExtractor(Extractor):
    """
    Concrete extractor that streams records from an Elasticsearch index.
    Uses scroll/scan under the hood to avoid deep pagination.
    """

    def __init__(self, hosts: list[str], index: str, query: Dict[str, Any] | None = None):
        self.hosts = hosts
        self.index = index
        self.query = query or {"query": {"match_all": {}}}
        self.client: Elasticsearch | None = None

    def open(self) -> None:
        """Initialize Elasticsearch client."""
        self.client = Elasticsearch(self.hosts)

    def iter_records(self) -> Iterator[Record]:
        """Stream documents one by one as dicts."""
        assert self.client, "Extractor not opened. Call .open() first."
        # helpers.scan handles scroll under the hood
        for doc in helpers.scan(self.client, index=self.index, query=self.query):
            # Each doc is a dict like {"_id": "...", "_source": {...}}
            yield {"_id": doc["_id"], **doc["_source"]}

    def close(self) -> None:
        """Close client."""
        if self.client:
            self.client.transport.close()
            self.client = None
