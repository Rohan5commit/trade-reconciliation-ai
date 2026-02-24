# Intelligent Trade Reconciliation and Exception Management System

AI-powered platform to automate trade matching, detect breaks, predict reconciliation failures, route exceptions, and provide operational analytics.

## Key Capabilities

1. Multi-system ingestion from OMS/custodian connectors (extensible to prime broker/exchange)
2. Fuzzy semantic trade matching with weighted scoring
3. Predictive break detection with ML
4. Exception routing with SLA escalation
5. Root-cause pattern analysis
6. Auto-remediation suggestions for low-risk breaks
7. Reporting APIs for SLA, aging, and run history

## Architecture

- API: FastAPI (`src/api`)
- Data Layer: SQLAlchemy models (`src/models`)
- Ingestion: Connector framework (`src/ingestion`)
- Matching: Fuzzy engine + reconciliation orchestration (`src/matching`)
- ML: Feature engineering, train, and inference (`src/ml`)
- Workflows: Routing, root cause, remediation (`src/workflows`)
- Async Tasks: Celery workers + beat (`src/tasks`)
- Analytics: Reporting service (`src/reporting`)

## Project Structure

```text
trade-reconciliation-ai/
  src/
    api/
    config/
    ingestion/
    matching/
    ml/
    models/
    reporting/
    rules/
    tasks/
    workflows/
  tests/
  data/
  models/
  scripts/
  dashboards/
```

## Quick Start

1. Create env file:

```bash
cp .env.example .env
```

Default `.env.example` is configured for Kraken public API mode (no credentials required).

2. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Optional extended packages (NLP, extra connectors, advanced ML):

```bash
python3 -m pip install -r requirements.optional.txt
```

3. Run API:

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Run worker and scheduler:

```bash
celery -A src.tasks.worker.celery_app worker --loglevel=info --concurrency=4
celery -A src.tasks.worker.celery_app beat --loglevel=info
```

5. Optional demo data:

```bash
python3 scripts/seed_demo_data.py
```

6. One-shot smoke flow (health + seed + reconcile + reports):

```bash
make smoke
```

## Docker Deployment

```bash
docker compose up --build
```

Docker Compose injects container-safe defaults (`POSTGRES_HOST=postgres`, `REDIS_URL=redis://redis:6379/0`) for API/worker/beat, so `.env` can remain local-first.

For a standalone API container (without Postgres) you can run:

```bash
docker build -t trade-reconciliation-ai:local .
docker run --rm -p 8000:8000 -e DATABASE_URL=sqlite+pysqlite:///./app.db trade-reconciliation-ai:local
```

## API Endpoints (Phase 7)

- `GET /api/v1/health`
- `POST /api/v1/ingestion/run`
- `POST /api/v1/reconciliation/run`
- `POST /api/v1/exceptions/{break_id}/route`
- `POST /api/v1/exceptions/{break_id}/auto-remediate`
- `GET /api/v1/exceptions/overdue`
- `GET /api/v1/breaks/open`
- `GET /api/v1/reports/summary`
- `GET /api/v1/reports/aging`
- `GET /api/v1/reports/runs`
- `GET /api/v1/reports/root-cause`
- `POST /api/v1/prediction/score`

## Celery Scheduling (Phase 8)

Beat schedule configured in `src/tasks/worker.py`:
- `tasks.check_sla_breaches` every 15 minutes

Additional tasks in `src/tasks/jobs.py`:
- `tasks.run_ingestion`
- `tasks.run_reconciliation`
- `tasks.daily_pipeline`

## Deployment and Usage (Phase 9)

1. Configure secrets in `.env` (leave unknown keys blank initially).
2. Deploy API and workers using Docker Compose or your orchestration platform.
3. Set CI pipeline:
   - `python3 -m compileall -q src tests`
   - `pytest`
4. Configure alerting from SLA and escalation endpoints.
5. Add production-grade connectors and model retraining schedule.

## Testing

```bash
pytest -q
python3 -m compileall -q src tests
```

## GitHub CI

GitHub Actions workflow: `.github/workflows/ci-docker.yml`

- Runs unit tests on Python 3.11
- Builds Docker image
- Starts container and verifies `GET /api/v1/health`

## Notes

- Credentials and API keys are intentionally not hard-coded.
- Alternative free OMS option is Kraken public trades (no key required): set `OMS_API_URL=https://api.kraken.com` and optional `KRAKEN_PAIR` (e.g., `XBTUSD`).
- Optional free OMS option is Alpaca paper trading (`OMS_API_URL=https://paper-api.alpaca.markets` plus Alpaca key/secret).
- If `models/<BREAK_PREDICTION_MODEL>` does not exist, prediction endpoint returns 404 with a clear message.
- Default testing path uses SQLite; production should use Postgres.
