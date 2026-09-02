from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol, Sequence

from pymilvus import DataType, MilvusClient

from data_pipeline.xls_parser import ChannelRule, XLSPipeline


ROOT = Path(__file__).resolve().parents[1]
MILVUS_DB_PATH = ROOT / "vectordb" / "milvus_data.db"
COLLECTION_NAME = "shipping_rules"
EMBEDDING_DIM = 1024
DASHSCOPE_BATCH_SIZE = 20


class EmbeddingClient(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class DashScopeEmbeddingClient:
    """Thin adapter around DashScope text-embedding-v4."""

    def __init__(self, api_key: str | None = None) -> None:
        import dashscope

        self._dashscope = dashscope
        if api_key:
            self._dashscope.api_key = api_key

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        values = list(texts)
        if not values:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(values), DASHSCOPE_BATCH_SIZE):
            batch = values[start : start + DASHSCOPE_BATCH_SIZE]
            response = self._dashscope.TextEmbedding.call(
                model="text-embedding-v4",
                input=batch,
            )
            status = getattr(response, "status_code", None)
            if status not in (None, 200):
                raise RuntimeError(f"DashScope embedding failed: {response}")

            output = getattr(response, "output", None)
            if output is None and isinstance(response, dict):
                output = response.get("output")
            embeddings = output.get("embeddings") if isinstance(output, dict) else getattr(output, "embeddings", None)
            if not embeddings:
                raise RuntimeError(f"DashScope embedding returned no embeddings: {response}")

            batch_vectors: list[list[float]] = []
            for item in embeddings:
                vector = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
                if vector is None:
                    raise RuntimeError(f"DashScope embedding item has no vector: {item}")
                batch_vectors.append([float(value) for value in vector])
            if len(batch_vectors) != len(batch):
                raise RuntimeError("DashScope embedding count does not match input count")
            if any(len(vector) != EMBEDDING_DIM for vector in batch_vectors):
                raise RuntimeError(f"Expected {EMBEDDING_DIM}-dimensional embeddings")
            vectors.extend(batch_vectors)

        return vectors


class MilvusRuleLoader:
    """Create, rebuild, search, and browse the shipping rule vector collection."""

    collection_name = COLLECTION_NAME

    def __init__(
        self,
        uri: str | Path | None = None,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        db_path = Path(uri or os.getenv("MILVUS_URI", str(MILVUS_DB_PATH)))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.uri = str(db_path)
        self.client = MilvusClient(uri=self.uri)
        self.embedding_client = embedding_client or DashScopeEmbeddingClient()

    def create_collection(self) -> None:
        if self.client.has_collection(self.collection_name):
            return
        schema = self.client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        schema.add_field("sheet_name", DataType.VARCHAR, max_length=255)
        schema.add_field("channel_name", DataType.VARCHAR, max_length=255)
        schema.add_field("rule_category", DataType.VARCHAR, max_length=64)
        schema.add_field("metadata", DataType.JSON)
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="L2",
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )

    def drop_collection(self) -> None:
        if self.client.has_collection(self.collection_name):
            self.client.drop_collection(self.collection_name)

    def rebuild(self, rules: Sequence[ChannelRule | dict[str, Any]]) -> int:
        self.drop_collection()
        self.create_collection()
        return self.load_rules(rules)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return self.embedding_client.embed(texts)

    def load_rules(self, rules: Sequence[ChannelRule | dict[str, Any]]) -> int:
        normalized = [self._normalize_rule(rule) for rule in rules]
        normalized = [rule for rule in normalized if rule["text"]]
        if not normalized:
            return 0
        self.create_collection()
        vectors = self.embed_texts([rule["text"] for rule in normalized])
        if len(vectors) != len(normalized):
            raise RuntimeError("Embedding count does not match rule count")
        rows = []
        for rule, vector in zip(normalized, vectors):
            rows.append({
                "embedding": vector,
                "text": rule["text"],
                "sheet_name": rule["sheet_name"],
                "channel_name": rule["channel_name"] or "",
                "rule_category": rule["rule_category"],
                "metadata": rule["metadata"],
            })
        result = self.client.insert(collection_name=self.collection_name, data=rows)
        self.client.flush(self.collection_name)
        return len(result.get("ids", rows))

    def search(
        self,
        query: str,
        top_k: int = 3,
        sheet_name: str | None = None,
        rule_category: str | None = None,
    ) -> list[dict[str, Any]]:
        if not query or top_k <= 0 or not self.client.has_collection(self.collection_name):
            return []
        vector = self.embed_texts([query])[0]
        filters = []
        if sheet_name:
            filters.append(f"sheet_name == {json.dumps(sheet_name, ensure_ascii=False)}")
        if rule_category:
            filters.append(f"rule_category == {json.dumps(rule_category, ensure_ascii=False)}")
        filter_expr = " and ".join(filters) if filters else None
        results = self.client.search(
            collection_name=self.collection_name,
            data=[vector],
            limit=top_k,
            filter=filter_expr,
            output_fields=["text", "sheet_name", "channel_name", "rule_category", "metadata"],
        )
        items: list[dict[str, Any]] = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            items.append({
                "id": hit.get("id"),
                "distance": hit.get("distance"),
                "text": entity.get("text"),
                "sheet_name": entity.get("sheet_name"),
                "channel_name": entity.get("channel_name") or None,
                "rule_category": entity.get("rule_category"),
                "metadata": entity.get("metadata") or {},
            })
        return items

    def list_rules(
        self,
        sheet_name: str | None = None,
        channel_name: str | None = None,
        rule_category: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return rules matching exact metadata filters without embedding a query."""
        if limit <= 0 or not self.client.has_collection(self.collection_name):
            return []
        filters = []
        if sheet_name:
            filters.append(f"sheet_name == {json.dumps(sheet_name, ensure_ascii=False)}")
        if channel_name:
            filters.append(f"channel_name == {json.dumps(channel_name, ensure_ascii=False)}")
        if rule_category:
            filters.append(f"rule_category == {json.dumps(rule_category, ensure_ascii=False)}")
        filter_expr = " and ".join(filters) if filters else None
        rows = self.client.query(
            collection_name=self.collection_name,
            filter=filter_expr,
            output_fields=["text", "sheet_name", "channel_name", "rule_category", "metadata"],
            limit=limit,
        )
        return [
            {
                "id": row.get("id"),
                "text": row.get("text"),
                "sheet_name": row.get("sheet_name"),
                "channel_name": row.get("channel_name") or None,
                "rule_category": row.get("rule_category"),
                "metadata": row.get("metadata") or {},
            }
            for row in rows
        ]

    @staticmethod
    def _normalize_rule(rule: ChannelRule | dict[str, Any]) -> dict[str, Any]:
        if isinstance(rule, ChannelRule):
            return {
                "text": rule.content.strip(),
                "sheet_name": rule.sheet_name,
                "channel_name": rule.channel_name,
                "rule_category": rule.rule_category,
                "metadata": {},
            }
        return {
            "text": str(rule.get("content", rule.get("text", ""))).strip(),
            "sheet_name": str(rule.get("sheet_name", "")),
            "channel_name": rule.get("channel_name"),
            "rule_category": str(rule.get("rule_category", "其他")),
            "metadata": rule.get("metadata") or {},
        }


def load_rules_from_xls(xls_path: str | Path, uri: str | Path | None = None) -> int:
    pipeline = XLSPipeline(xls_path)
    loader = MilvusRuleLoader(uri=uri)
    return loader.rebuild(pipeline.extract_all_rules())


__all__ = [
    "COLLECTION_NAME",
    "DASHSCOPE_BATCH_SIZE",
    "EMBEDDING_DIM",
    "MILVUS_DB_PATH",
    "DashScopeEmbeddingClient",
    "MilvusRuleLoader",
    "load_rules_from_xls",
]
