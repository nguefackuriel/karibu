#!/usr/bin/env bash
# Start the hub with the project's own Python.
#
# Running a bare `uvicorn` picks up whatever is first on PATH, which on this
# machine is a system Python 3.10 with no FastAPI in it. This always uses the
# interpreter in .venv, so it cannot pick the wrong one.
#
#     ./scripts/start.sh            # port 8000
#     ./scripts/start.sh 9000       # another port
#     ./scripts/start.sh 8000 fresh # wipe the database and reseed first
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${1:-8000}"
FRESH="${2:-}"
PY=".venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "No virtual environment. Create one with Python 3.12, then:"
  echo "    .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if ! "$PY" -c "import fastapi" 2>/dev/null; then
  echo "The virtual environment is missing its packages. Run:"
  echo "    .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if lsof -ti ":$PORT" >/dev/null 2>&1; then
  echo "Something already holds port $PORT. Stop it with:"
  echo "    lsof -ti :$PORT | xargs kill -9"
  exit 1
fi

if [ "$FRESH" = "fresh" ] || [ ! -f karibu.db ]; then
  rm -f karibu.db
  "$PY" -m hub.seed
fi

if curl -fsS -m 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "model runner: up"
else
  echo "model runner: NOT running. Start it with 'ollama serve' in another window."
  echo "The demo still works: the rules read every message in the script."
fi

echo "visitor page   http://127.0.0.1:$PORT/visitor"
echo "dashboard      http://127.0.0.1:$PORT/"
echo
exec .venv/bin/uvicorn hub.app:app --host 127.0.0.1 --port "$PORT"
