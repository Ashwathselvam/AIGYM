# 08 SLA & Performance Targets

> Draft v0.1 · {{DATE}}

These targets guide scaling decisions and serve as acceptance criteria for production readiness.

| Metric | Target | Measurement Window | Notes |
|--------|--------|--------------------|-------|
| API p95 latency (POST /episodes) | ≤ 300 ms | 1 min rolling | assumes vector search + DB writes |
| LLM call latency (GPT-4o) | ≤ 6 s avg | per call | includes 3-retry fallback |
| Vector query p95 (Infinity, 10 M rows) | ≤ 30 ms | 5 min | measured inside container |
| Graph query p95 (NebulaGraph, 3-hop) | ≤ 50 ms | 5 min | |
| Episode ingestion throughput | 10 eps/sec sustained | 1 min | Celery workers auto-scale |
| Availability | 99.5 % monthly | | excludes scheduled maintenance |

All automated monitors must alert (PagerDuty / Slack) when any p95 exceeds target for >5 min. 