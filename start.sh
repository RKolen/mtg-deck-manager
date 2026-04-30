#!/usr/bin/env bash
# Start all MTG Deck Manager systems.
#
# Usage:
#   ./start.sh           # start all services in the background
#   ./start.sh --stop    # stop all services
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/mtg-app"
DRUPAL_DIR="$SCRIPT_DIR/drupal"

# Load service config from .env — this file is required.
ENV_FILE="$SCRIPT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env not found at $ENV_FILE"
  echo "Create it with GATSBY_PORT, DRUPAL_URL, OLLAMA_PORT, MILVUS_PORT."
  exit 1
fi
# shellcheck source=.env
set -o allexport
source "$ENV_FILE"
set +o allexport

for var in GATSBY_PORT DRUPAL_URL OLLAMA_PORT MILVUS_PORT; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set in .env"
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# --stop: shut everything down
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--stop" ]]; then
  echo "==> Stopping Gatsby dev server..."
  OLD_GATSBY=$(lsof -ti :"$GATSBY_PORT" 2>/dev/null || true)
  if [[ -n "$OLD_GATSBY" ]]; then
    kill "$OLD_GATSBY" 2>/dev/null && echo "    Gatsby stopped."
  else
    echo "    Gatsby was not running."
  fi

  echo "==> Stopping Ollama..."
  pkill -f "ollama serve" 2>/dev/null && echo "    Ollama stopped." || echo "    Ollama was not running."

  echo "==> Stopping Milvus..."
  docker stop milvus-standalone 2>/dev/null && echo "    Milvus stopped." || echo "    Milvus was not running."

  echo "==> Stopping DDEV..."
  cd "$DRUPAL_DIR" && ddev stop
  echo "    DDEV stopped."
  exit 0
fi

# ---------------------------------------------------------------------------
# 1. Drupal backend via DDEV
# ---------------------------------------------------------------------------
echo "==> Starting Drupal backend (DDEV)..."
cd "$DRUPAL_DIR"
ddev start
echo "    Drupal:  $DRUPAL_URL"

# ---------------------------------------------------------------------------
# 2. Ollama (system service, background)
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting Ollama..."
if curl -s --max-time 2 "http://localhost:$OLLAMA_PORT" > /dev/null 2>&1; then
  echo "    Ollama already running on port $OLLAMA_PORT."
else
  ollama serve > "$SCRIPT_DIR/.ollama.log" 2>&1 &
  echo "    Ollama started (logs: .ollama.log)."
fi
echo "    Ollama:  http://localhost:$OLLAMA_PORT"

# ---------------------------------------------------------------------------
# 3. Milvus vector database (standalone Docker container)
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting Milvus..."
if docker ps --filter "name=milvus-standalone" --filter "status=running" --format '{{.Names}}' | grep -q milvus-standalone; then
  echo "    Milvus already running on port $MILVUS_PORT."
elif docker ps -a --filter "name=milvus-standalone" --format '{{.Names}}' | grep -q milvus-standalone; then
  docker start milvus-standalone > /dev/null
  echo "    Milvus started (existing container)."
else
  echo "    WARNING: no 'milvus-standalone' Docker container found."
  echo "    Create it first — see docs/architecture.md for the docker run command."
fi
echo "    Milvus:  localhost:$MILVUS_PORT"

# ---------------------------------------------------------------------------
# 4. Gatsby frontend (dev server in background)
# ---------------------------------------------------------------------------
echo ""
cd "$FRONTEND_DIR"

if [[ ! -f ".env.development" ]]; then
  echo "  WARNING: mtg-app/.env.development not found."
  echo "  Create it with GATSBY_DRUPAL_URL, GATSBY_DRUPAL_USER, GATSBY_DRUPAL_PASS."
  echo "  Skipping Gatsby dev server."
  GATSBY_STARTED=false
else
  echo "==> Stopping any existing Gatsby instance on port $GATSBY_PORT..."
  OLD_GATSBY=$(lsof -ti :"$GATSBY_PORT" 2>/dev/null || true)
  if [[ -n "$OLD_GATSBY" ]]; then
    kill "$OLD_GATSBY" 2>/dev/null && echo "    Killed existing process(es): $OLD_GATSBY"
  fi

  echo "==> Clearing Gatsby cache..."
  npm run clean > /dev/null 2>&1

  echo "==> Starting Gatsby dev server (background)..."
  npm run develop > "$SCRIPT_DIR/.gatsby.log" 2>&1 &
  GATSBY_PID=$!
  echo "    Gatsby PID: $GATSBY_PID (logs: .gatsby.log)"
  echo "    Frontend:   http://localhost:$GATSBY_PORT"
  GATSBY_STARTED=true
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "All services started."
echo ""
echo "  Drupal admin:  $DRUPAL_URL/user"
echo "  Frontend:      http://localhost:$GATSBY_PORT"
echo "  Ollama:        http://localhost:$OLLAMA_PORT"
echo "  Milvus:        localhost:$MILVUS_PORT"
echo ""
echo "Run './start.sh --stop' to shut everything down."
