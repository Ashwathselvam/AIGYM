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


# ---------- Infinity driver ----------
class InfinityStore(VectorStore):
    """Infinity vector engine driver (hybrid / prod)."""

    def __init__(self, host: str = "infinity", port: int = 8000):
        from infinity_python_client import Infinity

        self._client = Infinity(host=host, port=port)
        # Ensure collection exists
        if "concept_vectors" not in self._client.list_collections():
            self._client.create_collection("concept_vectors", dim=1536, metric="cosine")

    def upsert(self, ids: List[str], vectors: List[Vector], meta: Optional[List[dict]] = None) -> None:  # noqa: D401
        payload = meta or [{}] * len(ids)
        docs = [
            {"id": i, "vector": list(v), "metadata": m}
            for i, v, m in zip(ids, vectors, payload)
        ]
        self._client.upsert("concept_vectors", docs)

    def query(self, vector: Vector, top_k: int = 10) -> List[QueryResult]:  # noqa: D401
        res = self._client.search("concept_vectors", vector, topk=top_k)
        return [(hit["id"], hit["score"]) for hit in res]


# ---------- factory ----------

def get_vector_store() -> VectorStore:
    backend = os.getenv("VECTOR_BACKEND", "pg").lower()

    if backend == "pg":
        dsn = os.getenv("DATABASE_URL", "postgresql://postgres:example@localhost:5432/aigym")
        return PgVectorStore(dsn)

    if backend == "infinity":
        host = os.getenv("VECTOR_HOST", "infinity")
        port = int(os.getenv("VECTOR_PORT", "8000"))
        return InfinityStore(host, port)

    raise ValueError(f"Unsupported VECTOR_BACKEND '{backend}'. Choose 'pg' or 'infinity'.") 