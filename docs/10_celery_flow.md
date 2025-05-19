# 10 Celery Worker Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant PG as Postgres
    participant Redis as Redis Broker
    participant Worker as Celery Worker
    participant VStore as Vector Store (Qdrant/pgvector)

    Client->>API: POST /episodes (task, content)
    API->>PG: INSERT row (episode)
    API-->>Redis: enqueue job embed_episode(id, content)
    API-->>Client: 202 + episode_id

    Worker-- Redis: fetch embed_episode
    Worker->>OpenAI: Embedding API
    OpenAI-->>Worker: 1536-dim vector
    Worker->>VStore: upsert(id, vector)
    Worker->>PG: UPDATE episodes.episode_vector
```

The diagram shows how Celery mediates between API ingestion and heavy LLM/vector operations without blocking the HTTP thread. 