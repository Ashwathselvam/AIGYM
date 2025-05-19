# 07 Deployment Plan (Open-Source Focus)

> Draft v0.2 · last updated {{DATE}}

## Purpose
Provide a **code-level, open-source** deployment recipe that developers can run on a single VM or laptop using Docker Compose—yet still scalable enough to move to lightweight orchestration later.

## 1. Environments
| Env | Purpose | Infra | Data |
|-----|---------|-------|------|
| Local | Day-to-day dev & tests | Docker Compose | Sample seed data |
| Staging | Pre-merge CI or preview | Docker Compose (GitHub Actions or self-hosted runner) | Ephemeral |
| Prod-Lite | Small VPS / bare-metal | Docker Compose + systemd | Full memory DBs + nightly backups |

_No Kubernetes required at this stage._

## 2. Stack Components (all OSS licences)
| Service | Image | Ports | Volume |
|---------|-------|-------|--------|
| **FastAPI Gateway** | `python:3.11-slim` | 8000 | code bind-mount |
| **Worker Queue** | `redis:7-alpine` + `celery` in worker container | 6379 | — |
| **Episodic DB** | `postgres:15` (with `pgvector` ext) | 5432 | `pg_data` |
| **Semantic Graph** | **NebulaGraph** (metad/graphd/storaged) | 9669 | `nebula_data*` |
| **Vector Store** | **Qdrant** | 6333 | `qdrant_data` |
| **Simulation Runner** | `docker:dind` side-car + task container | — | task tmp dirs |
| **Frontend** | `node:20-alpine` (Next.js build) | 3000 | static build |

## 3. docker-compose.yml (excerpt)
```yaml
version: "3.9"
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: example
    volumes:
      - pg_data:/var/lib/postgresql/data
    ports: ["5432:5432"]
    command: ["postgres", "-c", "shared_preload_libraries=pgvector"]

  nebula-metad:
    image: vesoft/nebula-metad:v3
    environment:
      USER: root
    volumes:
      - nebula_meta:/data/meta
    ports: ["9559:9559"]

  nebula-storaged:
    image: vesoft/nebula-storaged:v3
    depends_on: [nebula-metad]
    volumes:
      - nebula_storage:/data/storage
    environment:
      USER: root
    ports: ["9779:9779"]

  nebula-graphd:
    image: vesoft/nebula-graphd:v3
    depends_on: [nebula-metad, nebula-storaged]
    ports: ["9669:9669"]

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    ports: ["6333:6333"]

  api:
    build: ./src
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      DATABASE_URL: postgresql://postgres:example@postgres:5432/aigym
      GRAPH_HOST: nebula-graphd
      GRAPH_PORT: 9669
      GRAPH_USER: root
      GRAPH_PASS: password
      VECTOR_HOST: qdrant
      VECTOR_PORT: 6333
    depends_on: [postgres, nebula-graphd, qdrant]
    ports: ["8000:8000"]

volumes:
  pg_data:
  nebula_meta:
  nebula_storage:
  qdrant_data:
```

## 4. CI/CD with GitHub Actions
```yaml
# .github/workflows/ci.yml
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres: {image: postgres:15, ports: [5432]}
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - run: pytest -q
```
_You can add a second job that builds & pushes images to Docker Hub plus `docker compose up -d` on the prod VPS via SSH._

## 5. Observability (lightweight)
| Tool | Uses | How to Deploy |
|------|------|--------------|
| **Prometheus + Grafana** | CPU / RAM graphs | `docker-compose` pre-built stack |
| **OpenTelemetry python** | API tracing | Exporter → `jaegertracing/all-in-one` |
| **pgAdmin** | Postgres GUI | optional service |

## 6. Backups & Maintenance
| Resource | Method | Schedule |
|----------|--------|----------|
| Postgres | `pg_dump` → cron job, push to S3/Backblaze | nightly |
| Neo4j/Memgraph | `neo4j-admin dump` or `mg_backup` | nightly |
| Qdrant | Volume snapshot (rsync) | nightly |

## 7. Scaling Path Later
1. **Compose → Docker Swarm** if you need multi-host but still simple.  
2. **Swarm → lightweight k8s** (k3s) when horizontal scaling is necessary.  
3. Swap `neo4j` Community for `memgraph` cluster or `arangodb` if clustering is required.

---
This plan keeps everything **100 % open-source** and runnable via a single `docker compose up` while leaving headroom for future growth. 