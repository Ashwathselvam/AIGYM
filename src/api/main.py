from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from uuid import uuid4
import asyncio
from concurrent.futures import ThreadPoolExecutor

from models.settings import settings
from memory.vector_store import get_vector_store, VectorStore
from db.core import migrate_sync, get_conn
from workers.embeddings import embed_episode  # local import to avoid circular
from api.solutions import router as solutions_router

app = FastAPI(title="AIGYM API", version="0.1.0")

# Include routers
app.include_router(solutions_router)


@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, migrate_sync)


class EpisodeCreate(BaseModel):
    task_id: str
    task_version: str | None = None
    rubric_version: str | None = None
    content: str  # raw context (simplified for demo)


@app.get("/healthz", tags=["meta"])
async def healthz():
    return {"status": "ok"}


@app.post("/episodes", tags=["episodes"])
async def create_episode(payload: EpisodeCreate):
    episode_id = str(uuid4())

    def _insert():
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO episodes (episode_id, task_id, task_version, rubric_version, content)
                           VALUES (%s,%s,%s,%s,%s)""",
                    (
                        episode_id,
                        payload.task_id,
                        payload.task_version,
                        payload.rubric_version,
                        payload.content,
                    ),
                )
                conn.commit()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _insert)

    # enqueue embedding task (simplified sync call here)
    embed_episode.delay(episode_id, payload.content)

    return {"episode_id": episode_id} 