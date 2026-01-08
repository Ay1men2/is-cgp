#!/usr/bin/env bash
set -euo pipefail

pip install --no-cache-dir -r requirements.txt
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
