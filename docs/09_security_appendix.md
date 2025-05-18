# 09 Security & Secret Management

> Draft v0.1 · {{DATE}}

## 1. Secret Management
| Secret | Storage | Access Path |
|--------|---------|-------------|
| OpenAI API Key | `.env` (dev) → Docker secret in prod | `settings.openai_api_key` |
| Postgres password | `.env` / Docker secret | `DATABASE_URL` |
| Nebula root pass | Docker secret | `NEBULA_PASS` |
| Infinity admin token (future) | Docker secret | `VECTOR_SECRET` |

## 2. Network Isolation
* **Simulation containers** run under Docker-in-Docker with `--network none` and a read-only filesystem.  
* Use `gVisor` or `firejail` for additional syscall filtering when hosting untrusted code.

## 3. TLS & Ingress (future)
* Use Caddy reverse-proxy with automatic Let's Encrypt certs.  
* Internal service-to-service comms stay in Docker network; external traffic terminates at Caddy.

## 4. Audit Logging
* All CRUD on `episodes`, `concept_vectors`, Nebula mutations emit JSON logs to Loki.  
* Retention: 30 days searchable, 1 year archived in S3.

## 5. Dependency Scanning
* `pip-audit` run in CI.  
* Trivy scans Docker images on every push.

## 6. RBAC (phase-2)
* Integrate OIDC login; admin role can delete episodes, teacher role can add feedback, agent role is read-mostly. 