# Synthetic Data Studio

Production-style web app for running NVIDIA NeMo Data Designer from a browser.

## Local Stack

```bash
docker compose up --build
```

Services:

- Frontend: http://localhost:3000
- API: http://localhost:8000
- MinIO console: http://localhost:9001
- PostgreSQL: localhost:5432
- Redis: localhost:6379

The default local admin token is `dev-token`. Override it with:

```bash
$env:STUDIO_ADMIN_TOKEN="your-token"
docker compose up --build
```

## Python API Only

```bash
uv sync --all-packages --group studio
$env:STUDIO_ADMIN_TOKEN="dev-token"
$env:STUDIO_RUN_JOBS_INLINE="true"
uv run --group studio uvicorn studio_backend.app:app --reload --host 127.0.0.1 --port 8000
```

Then call protected endpoints with:

```bash
curl http://127.0.0.1:8000/api/state -H "Authorization: Bearer dev-token"
```

## Frontend Only

```bash
cd studio_frontend
npm install
$env:STUDIO_API_BASE="http://localhost:8000"
$env:STUDIO_ADMIN_TOKEN="dev-token"
npm run dev
```

## Worker

For production-like async jobs:

```bash
uv run --group studio celery -A studio_backend.tasks.celery_app worker --loglevel=INFO
```

Set `STUDIO_RUN_JOBS_INLINE=true` only for local smoke tests.

Set `STUDIO_USE_SYNTHETIC_RUNNER=true` only when you want deterministic development records without calling a model endpoint. Leave it `false` for production so failed model/provider configuration is visible in job errors.
