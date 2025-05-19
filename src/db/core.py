import logging
import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.pool import SimpleConnectionPool

from models.settings import settings

logger = logging.getLogger(__name__)

_POOL: SimpleConnectionPool | None = None


def _get_pool() -> SimpleConnectionPool:
    global _POOL
    if _POOL is None:
        _POOL = SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=settings.database_url,
        )
    return _POOL


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


DDL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS episodes (
    episode_id UUID PRIMARY KEY,
    task_id TEXT NOT NULL,
    task_version TEXT,
    rubric_version TEXT,
    agent_version TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    content TEXT,
    episode_vector VECTOR({settings.vector_dim}),
    success BOOLEAN,
    score FLOAT,
    metrics JSONB
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id SERIAL PRIMARY KEY,
    episode_id UUID NOT NULL REFERENCES episodes(episode_id),
    source TEXT NOT NULL,
    rating FLOAT,
    rationale TEXT,
    rubric_section TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_episode ON feedback(episode_id);
"""


def migrate_sync() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)
            conn.commit()
