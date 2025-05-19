"""
Task workers for handling embeddings generation.
"""
import json
import logging
from celery import Task

from workers.celery_app import celery_app
from workers.llm import embed
from memory.vector_store import get_vector_store
from db.core import get_conn

logger = logging.getLogger(__name__)


class EmbeddingTask(Task):
    """Celery task base class with initialized vector store."""
    _vector_store = None

    @property
    def vector_store(self):
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store


@celery_app.task(bind=True, base=EmbeddingTask)
def embed_episode(self, episode_id, content):
    """
    Generate embeddings for episode content and store them in vector store.
    
    Args:
        episode_id: UUID of the episode
        content: Text content to embed
    """
    try:
        # Generate embeddings
        vector = embed(content)
        
        # Store in vector store
        self.vector_store.upsert([episode_id], [vector])
        
        # Update the episodes table with the vector
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE episodes SET episode_vector = %s WHERE episode_id = %s",
                    (json.dumps(vector), episode_id)
                )
                conn.commit()
                
        return {"status": "success", "episode_id": episode_id}
        
    except Exception as e:
        logger.error(f"Error embedding episode {episode_id}: {e}")
        raise 