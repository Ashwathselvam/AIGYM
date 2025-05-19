"""NebulaGraph abstraction layer.

Usage:
    from memory.graph_store import get_graph_store
    graph = get_graph_store()
    graph.upsert_concept(...)
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List

from nebula3.gclient.net import ConnectionPool
from nebula3.Config import Config

from models.settings import settings


class GraphStore(ABC):
    @abstractmethod
    def upsert_concept(self, concept: Dict[str, Any]) -> None: ...

    @abstractmethod
    def upsert_relation(self, src_id: str, dst_id: str, rel_type: str, props: Dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    def get_concept(self, concept_id: str) -> Dict[str, Any] | None: ...


# ---------------- Nebula implementation -----------------
class NebulaStore(GraphStore):
    def __init__(self):
        cfg = Config()
        cfg.max_connection_pool_size = 10
        self._pool = ConnectionPool()
        self._pool.init([(settings.nebula_host, settings.nebula_port)], cfg)
        # Ensure space & schema created (idempotent)
        with self._session() as s:
            s.execute("CREATE SPACE IF NOT EXISTS aigym(vid_type=FIXED_STRING(36)); USE aigym;")
            s.execute(
                "CREATE TAG IF NOT EXISTS Concept(name string, type string, description string, created_at timestamp);"
            )
            s.execute("CREATE EDGE IF NOT EXISTS PREREQUISITE_OF(confidence float);")
            s.execute("CREATE EDGE IF NOT EXISTS PART_OF();")
            s.execute("CREATE EDGE IF NOT EXISTS CAUSES();")

    def _session(self):
        return self._pool.session_context(settings.nebula_user, settings.nebula_pass)

    def upsert_concept(self, concept: Dict[str, Any]) -> None:
        cid = concept["id"]
        props = {k: v for k, v in concept.items() if k != "id"}
        kv = ", ".join(f"{k}: \"{v}\"" for k, v in props.items())
        nql = f'INSERT VERTEX Concept({", ".join(props.keys())}) VALUES "{cid}":({", ".join(f"\"{v}\"" for v in props.values())});'
        with self._session() as s:
            s.execute("USE aigym; " + nql)

    def upsert_relation(self, src_id: str, dst_id: str, rel_type: str, props: Dict[str, Any] | None = None) -> None:
        prop_str = ""
        if props:
            kv = ", ".join(f"{k}: {v}" for k, v in props.items())
            prop_str = f'({kv})'
        nql = f'INSERT EDGE {rel_type}{prop_str} VALUES "{src_id}"->"{dst_id}":()'
        with self._session() as s:
            s.execute("USE aigym; " + nql)

    def get_concept(self, concept_id: str):
        with self._session() as s:
            res = s.execute(f'USE aigym; FETCH PROP ON Concept "{concept_id}";')
            if not res.is_succeeded():
                return None
            row = res.row_values(0)
            return {"id": concept_id, "name": row[0].as_string(), "type": row[1].as_string(), "description": row[2].as_string(), "created_at": row[3].as_time()}  # noqa: E501


# -------------- factory -------------------

def get_graph_store() -> GraphStore:
    return NebulaStore() 