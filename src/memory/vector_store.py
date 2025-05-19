"""Abstraction layer for vector search back-ends.

Usage:
    from memory.vector_store import get_vector_store
    store = get_vector_store()
    ids = store.upsert([...])
    results = store.query(query_vec, top_k=5)

Backend is chosen via env var VECTOR_BACKEND="pg" (default) or "infinity".
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import List, Sequence, Tuple, Optional, Any

# ---------- shared types ----------
Vector = Sequence[float]
QueryResult = Tuple[str, float]  # (id, score)


# ---------- abstract base ----------
class VectorStore(ABC):
    """Common interface for vector DB drivers."""

    @abstractmethod
    def upsert(self, ids: List[str], vectors: List[Vector], meta: Optional[List[dict]] = None) -> None:  # noqa: D401
        """Insert or update vectors.

        meta is optional payload saved alongside the vector (if supported).
        """

    @abstractmethod
    def query(self, vector: Vector, top_k: int = 10) -> List[QueryResult]:  # noqa: D401
        """Return top-k similar vectors (lower distance ⇢ higher score)."""


# ---------- pgvector driver ----------
class PgVectorStore(VectorStore):
    """pgvector-backed implementation (dev / lightweight)."""

    def __init__(self, dsn: str):
        import psycopg2  # local import to avoid hard dependency if unused

        self._conn = psycopg2.connect(dsn)
        self._ensure_table()

    def _ensure_table(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE EXTENSION IF NOT EXISTS pgvector;
            CREATE TABLE IF NOT EXISTS concept_vectors (
              concept_id TEXT PRIMARY KEY,
              embedding  VECTOR(1536)
            );
            CREATE INDEX IF NOT EXISTS concept_ann ON concept_vectors USING ivfflat (embedding);
            """
        )
        self._conn.commit()

    def upsert(self, ids: List[str], vectors: List[Vector], meta: Optional[List[dict]] = None) -> None:  # noqa: D401
        cur = self._conn.cursor()
        args = [(i, vector_to_str(v)) for i, v in zip(ids, vectors)]
        cur.executemany(
            """
            INSERT INTO concept_vectors (concept_id, embedding)
            VALUES (%s, %s)
            ON CONFLICT (concept_id) DO UPDATE SET embedding = EXCLUDED.embedding;""",
            args,
        )
        self._conn.commit()

    def query(self, vector: Vector, top_k: int = 10) -> List[QueryResult]:  # noqa: D401
        cur = self._conn.cursor()
        cur.execute(
            """SELECT concept_id, 1 - (embedding <=> %s) AS score
               FROM concept_vectors
               ORDER BY embedding <-> %s
               LIMIT %s""",
            (vector_to_str(vector), vector_to_str(vector), top_k),
        )
        return [(row[0], float(row[1])) for row in cur.fetchall()]


def vector_to_str(vec: Vector) -> str:
    """Serialize list[float] to pgvector literal e.g. '[1,2,3]'"""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


# ---------- Qdrant driver ----------
class QdrantStore(VectorStore):
    """Qdrant-based vector store driver."""

    def __init__(self, host: str = "qdrant", port: int = 6333, collection: str = "concept_vectors"):
        from qdrant_client import QdrantClient

        self._collection = collection
        self._client = QdrantClient(host=host, port=port)
        # Ensure collection exists
        if collection not in [c.name for c in self._client.get_collections().collections]:
            self._client.create_collection(
                collection_name=collection,
                vector_size=int(os.getenv("VECTOR_DIM", "1536")),
                distance="Cosine",
            )

    def upsert(self, ids: List[str], vectors: List[Vector], meta: Optional[List[dict]] = None) -> None:
        payload = meta or [{}] * len(ids)
        points = [
            {
                "id": i,
                "vector": v,
                "payload": m,
            }
            for i, v, m in zip(ids, vectors, payload)
        ]
        self._client.upsert(collection_name=self._collection, points=points)

    def query(self, vector: Vector, top_k: int = 10) -> List[QueryResult]:
        res = self._client.search(collection_name=self._collection, query_vector=vector, limit=top_k)
        return [(str(p.id), p.score) for p in res]


# ---------- factory ----------

def get_vector_store() -> VectorStore:
    backend = os.getenv("VECTOR_BACKEND", "pg").lower()

    if backend == "pg":
        dsn = os.getenv("DATABASE_URL", "postgresql://postgres:example@localhost:5432/aigym")
        return PgVectorStore(dsn)

    if backend == "qdrant":
        host = os.getenv("VECTOR_HOST", "qdrant")
        port = int(os.getenv("VECTOR_PORT", "6333"))
        return QdrantStore(host, port)

    raise ValueError(f"Unsupported VECTOR_BACKEND '{backend}'. Choose 'pg' or 'qdrant'.") 