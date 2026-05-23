#!/usr/bin/env bash
# Start all MTG Deck Manager systems.
#
# Usage:
#   ./start.sh           # start all services in the background
#   ./start.sh --fresh   # same, but clear Gatsby cache before starting
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

for var in GATSBY_PORT DRUPAL_URL OLLAMA_PORT MILVUS_PORT SIM_PORT; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set in .env"
    exit 1
  fi
done

FRESH_START=false
if [[ "${1:-}" == "--fresh" ]]; then
  FRESH_START=true
fi

# Kill every process listening on a TCP port (Gatsby spawns child processes).
stop_port_listeners() {
  local port="$1"
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    return 0
  fi
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 1
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
}

wait_for_port_free() {
  local port="$1"
  local attempts="${2:-30}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if ! lsof -ti :"$port" > /dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "ERROR: port $port is still in use after ${attempts}s"
  lsof -i :"$port" 2>/dev/null || true
  return 1
}

wait_for_gatsby_ready() {
  local port="$1"
  local attempts="${2:-90}"
  local i code
  for ((i = 1; i <= attempts; i++)); do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:${port}/" || true)
    if [[ "$code" == "200" ]]; then
      echo "    Gatsby ready (HTTP 200) after ${i} attempt(s)."
      return 0
    fi
    sleep 2
  done
  echo "    WARNING: Gatsby did not return HTTP 200 within $((attempts * 2))s (last code: ${code:-none})."
  echo "    Check .gatsby.log for compile errors."
  return 1
}

# ---------------------------------------------------------------------------
# --stop: shut everything down
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--stop" ]]; then
  echo "==> Stopping Gatsby dev server..."
  if lsof -ti :"$GATSBY_PORT" > /dev/null 2>&1; then
    stop_port_listeners "$GATSBY_PORT"
    if wait_for_port_free "$GATSBY_PORT" 10; then
      echo "    Gatsby stopped."
    else
      echo "    Gatsby may still be running."
    fi
  else
    echo "    Gatsby was not running."
  fi

  echo "==> Stopping sim service..."
  OLD_SIM=$(lsof -ti :"$SIM_PORT" 2>/dev/null || true)
  if [[ -n "$OLD_SIM" ]]; then
    kill "$OLD_SIM" 2>/dev/null && echo "    Sim service stopped."
  else
    echo "    Sim service was not running."
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
# 4. Python simulation service (mtg-sim/sim, background)
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting Python simulation service..."
SIM_DIR="$SCRIPT_DIR/mtg-sim"
if lsof -ti :"$SIM_PORT" > /dev/null 2>&1; then
  echo "    Sim service already running on port $SIM_PORT."
elif [[ ! -f "$SIM_DIR/.venv/bin/python" ]]; then
  echo "    WARNING: $SIM_DIR/.venv not found."
  echo "    Run: cd mtg-sim && python3 -m venv .venv && source .venv/bin/activate && pip install -r sim/requirements.txt"
else
  cd "$SIM_DIR/sim"
  SIM_PORT="$SIM_PORT" "$SIM_DIR/.venv/bin/python" main.py \
    > "$SCRIPT_DIR/.sim.log" 2>&1 &
  cd "$SCRIPT_DIR"
  echo "    Sim service started on port $SIM_PORT (logs: .sim.log)."
fi
echo "    Sim API:  http://localhost:$SIM_PORT"

# ---------------------------------------------------------------------------
# 5. Gatsby frontend (dev server in background)
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
  stop_port_listeners "$GATSBY_PORT"
  wait_for_port_free "$GATSBY_PORT"

  if [[ "$FRESH_START" == true ]]; then
    echo "==> Clearing Gatsby cache (--fresh)..."
    npm run clean > /dev/null 2>&1
  fi

  echo "==> Starting Gatsby dev server (background)..."
  : > "$SCRIPT_DIR/.gatsby.log"
  (
    cd "$FRONTEND_DIR"
    export NODE_EXTRA_CA_CERTS="${NODE_EXTRA_CA_CERTS:-$HOME/.local/share/mkcert/rootCA.pem}"
    exec npx gatsby develop --port "$GATSBY_PORT" -H localhost
  ) >> "$SCRIPT_DIR/.gatsby.log" 2>&1 &
  GATSBY_PID=$!
  echo "    Gatsby PID: $GATSBY_PID (logs: .gatsby.log)"
  echo "    Waiting for first compile..."
  wait_for_gatsby_ready "$GATSBY_PORT" || true
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
echo "  Sim API:       http://localhost:$SIM_PORT"
echo "  Ollama:        http://localhost:$OLLAMA_PORT"
echo "  Milvus:        localhost:$MILVUS_PORT"
echo ""
echo "Run './start.sh --stop' to shut everything down."
echo "Run './start.sh --fresh' to clear the Gatsby cache on the next start."
