#!/usr/bin/env bash
set -euo pipefail

STORAGE_HOST="${STORAGE_HOST:-127.0.0.1}"
STORAGE_PORT="${STORAGE_PORT:-8001}"
APP_PORT="${APP_PORT:-8501}"

export STORAGE_BASE_URL="${STORAGE_BASE_URL:-http://$STORAGE_HOST:$STORAGE_PORT}"
export STORAGE_API_TOKEN="${STORAGE_API_TOKEN:-}"

echo "Starting Streamlit app"
echo "Storage URL: $STORAGE_BASE_URL"

exec python -m streamlit run referral.py --server.port "$APP_PORT"
