#!/usr/bin/env bash
# Start all MTG Deck Manager systems.
#
# Usage:
#   ./start.sh           # start all services in the background
#   ./start.sh --fresh   # same, but clear Next.js cache before starting
#   ./start.sh --stop    # stop all services
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/mtg-app"
DRUPAL_DIR="$SCRIPT_DIR/drupal"

# Load service config from .env — this file is required.
ENV_FILE="$SCRIPT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env not found at $ENV_FILE"
  echo "Create it with GATSBY_PORT, DRUPAL_URL, OLLAMA_PORT, OLLAMA_MODEL, SIDECAR_PORT, MILVUS_PORT, SIM_PORT, CLASSIFIER_HOST, CLASSIFIER_PORT."
  exit 1
fi
# shellcheck source=.env
set -o allexport
source "$ENV_FILE"
set +o allexport

for var in GATSBY_PORT DRUPAL_URL OLLAMA_PORT OLLAMA_MODEL SIDECAR_PORT MILVUS_PORT SIM_PORT CLASSIFIER_HOST CLASSIFIER_PORT; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var is not set in $ENV_FILE"
    exit 1
  fi
done

# Next.js reads mtg-app/.env.local (or .env.development); keep sim port in sync.
frontend_env_file() {
  if [[ -f "$FRONTEND_DIR/.env.local" ]]; then
    echo "$FRONTEND_DIR/.env.local"
  elif [[ -f "$FRONTEND_DIR/.env.development" ]]; then
    echo "$FRONTEND_DIR/.env.development"
  fi
}

# Read KEY=value from a frontend env file without aborting on missing keys.
frontend_env_port() {
  local file="$1"
  local key="$2"
  local value
  value=$(grep -E "^${key}=" "$file" 2>/dev/null | head -n1 | cut -d= -f2- || true)
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  echo "$value" | sed -n 's|.*/:\([0-9]*\).*|\1|p'
}

FRONTEND_ENV="$(frontend_env_file || true)"
if [[ -n "$FRONTEND_ENV" ]]; then
  FRONTEND_SIM_PORT="$(frontend_env_port "$FRONTEND_ENV" 'NEXT_PUBLIC_SIM_URL')"
  if [[ -z "$FRONTEND_SIM_PORT" ]]; then
    FRONTEND_SIM_PORT="$(frontend_env_port "$FRONTEND_ENV" 'GATSBY_SIM_URL')"
    if [[ -n "$FRONTEND_SIM_PORT" ]]; then
      echo "WARNING: $FRONTEND_ENV still uses GATSBY_SIM_URL — rename to NEXT_PUBLIC_SIM_URL."
    fi
  fi
  if [[ -n "$FRONTEND_SIM_PORT" && "$FRONTEND_SIM_PORT" != "$SIM_PORT" ]]; then
    echo "WARNING: frontend sim URL port ($FRONTEND_SIM_PORT) does not match SIM_PORT ($SIM_PORT)."
    echo "         Update $FRONTEND_ENV to use port $SIM_PORT."
  fi
  FRONTEND_CLASSIFIER_PORT="$(frontend_env_port "$FRONTEND_ENV" 'NEXT_PUBLIC_CLASSIFIER_URL')"
  if [[ -z "$FRONTEND_CLASSIFIER_PORT" ]]; then
    FRONTEND_CLASSIFIER_PORT="$(frontend_env_port "$FRONTEND_ENV" 'GATSBY_CLASSIFIER_URL')"
  fi
  if [[ -n "$FRONTEND_CLASSIFIER_PORT" && "$FRONTEND_CLASSIFIER_PORT" != "$CLASSIFIER_PORT" ]]; then
    echo "WARNING: frontend classifier URL port ($FRONTEND_CLASSIFIER_PORT) does not match CLASSIFIER_PORT ($CLASSIFIER_PORT)."
  fi
fi

# Source frontend env and map legacy GATSBY_* names for Next.js.
export_frontend_env() {
  local file
  for file in "$FRONTEND_DIR/.env.development" "$FRONTEND_DIR/.env.local"; do
    if [[ -f "$file" ]]; then
      # shellcheck source=/dev/null
      set -a
      source "$file"
      set +a
    fi
  done
  export NEXT_PUBLIC_DRUPAL_URL="${NEXT_PUBLIC_DRUPAL_URL:-${GATSBY_DRUPAL_URL:-}}"
  export NEXT_PUBLIC_DRUPAL_USER="${NEXT_PUBLIC_DRUPAL_USER:-${GATSBY_DRUPAL_USER:-}}"
  export NEXT_PUBLIC_DRUPAL_PASS="${NEXT_PUBLIC_DRUPAL_PASS:-${GATSBY_DRUPAL_PASS:-}}"
  export NEXT_PUBLIC_SIM_URL="${NEXT_PUBLIC_SIM_URL:-${GATSBY_SIM_URL:-}}"
  export NEXT_PUBLIC_CLASSIFIER_URL="${NEXT_PUBLIC_CLASSIFIER_URL:-${GATSBY_CLASSIFIER_URL:-}}"
  if [[ -z "${NEXT_PUBLIC_CLASSIFIER_URL:-}" && -n "${CLASSIFIER_HOST:-}" && -n "${CLASSIFIER_PORT:-}" ]]; then
    export NEXT_PUBLIC_CLASSIFIER_URL="http://${CLASSIFIER_HOST}:${CLASSIFIER_PORT}"
  fi
}

FRESH_START=false
if [[ "${1:-}" == "--fresh" ]]; then
  FRESH_START=true
fi

# Kill every process listening on a TCP port.
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

wait_for_frontend_ready() {
  local port="$1"
  local attempts="${2:-90}"
  local i code
  for ((i = 1; i <= attempts; i++)); do
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:${port}/" || true)
    if [[ "$code" == "200" ]]; then
      echo "    Next.js ready (HTTP 200) after ${i} attempt(s)."
      return 0
    fi
    sleep 2
  done
  echo "    WARNING: Next.js did not return HTTP 200 within $((attempts * 2))s (last code: ${code:-none})."
  echo "    Check .frontend.log for compile errors."
  return 1
}

# ---------------------------------------------------------------------------
# --stop: shut everything down
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--stop" ]]; then
  echo "==> Stopping Next.js dev server..."
  if lsof -ti :"$GATSBY_PORT" > /dev/null 2>&1; then
    stop_port_listeners "$GATSBY_PORT"
    if wait_for_port_free "$GATSBY_PORT" 10; then
      echo "    Next.js stopped."
    else
      echo "    Next.js may still be running."
    fi
  else
    echo "    Next.js was not running."
  fi

  echo "==> Stopping AI sidecar..."
  OLD_SIDECAR=$(lsof -ti :"$SIDECAR_PORT" 2>/dev/null || true)
  if [[ -n "$OLD_SIDECAR" ]]; then
    kill "$OLD_SIDECAR" 2>/dev/null && echo "    Sidecar stopped."
  else
    echo "    Sidecar was not running."
  fi

  echo "==> Stopping sim service..."
  OLD_SIM=$(lsof -ti :"$SIM_PORT" 2>/dev/null || true)
  if [[ -n "$OLD_SIM" ]]; then
    kill "$OLD_SIM" 2>/dev/null && echo "    Sim service stopped."
  else
    echo "    Sim service was not running."
  fi

  echo "==> Stopping deck deduction classifier..."
  OLD_CLASSIFIER=$(lsof -ti :"$CLASSIFIER_PORT" 2>/dev/null || true)
  if [[ -n "$OLD_CLASSIFIER" ]]; then
    kill "$OLD_CLASSIFIER" 2>/dev/null && echo "    Classifier stopped."
  else
    echo "    Classifier was not running."
  fi

  echo "==> Stopping Ollama..."
  pkill -f "ollama serve" 2>/dev/null && echo "    Ollama stopped." || echo "    Ollama was not running."

  echo "==> Stopping DDEV (includes Milvus)..."
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

DDEV_SITENAME=$(grep -E '^name:' "$DRUPAL_DIR/.ddev/config.yaml" | awk '{print $2}')
MILVUS_CONTAINER="ddev-${DDEV_SITENAME}-milvus"

echo ""
echo "==> Milvus (DDEV)..."
if docker ps --filter "name=^${MILVUS_CONTAINER}$" --filter "status=running" -q | grep -q .; then
  echo "    Milvus running in DDEV ($MILVUS_CONTAINER)."
  echo "    Milvus:  milvus:$MILVUS_PORT inside DDEV — not exposed on host localhost"
else
  echo "    WARNING: DDEV Milvus container not running."
  echo "    Run: cd drupal && ddev restart"
fi

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
# 2b. MTG AI sidecar (host FastAPI, proxies to host Ollama)
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting MTG AI sidecar..."
SIM_DIR="$SCRIPT_DIR/mtg-sim"
if lsof -ti :"$SIDECAR_PORT" > /dev/null 2>&1; then
  echo "    Sidecar already running on port $SIDECAR_PORT."
elif [[ ! -f "$SIM_DIR/.venv/bin/python" ]]; then
  echo "    WARNING: $SIM_DIR/.venv not found — sidecar not started."
else
  cd "$SIM_DIR"
  OLLAMA_URL="http://127.0.0.1:$OLLAMA_PORT" \
  OLLAMA_MODEL="$OLLAMA_MODEL" \
  SIDECAR_HOST="${SIDECAR_HOST:-0.0.0.0}" \
  SIDECAR_PORT="$SIDECAR_PORT" \
  PYTHONPATH="$SIM_DIR" \
  "$SIM_DIR/.venv/bin/python" -m sidecar.main \
    > "$SCRIPT_DIR/.sidecar.log" 2>&1 &
  cd "$SCRIPT_DIR"
  echo "    Sidecar started on port $SIDECAR_PORT (logs: .sidecar.log)."
fi
echo "    Sidecar: http://localhost:$SIDECAR_PORT/health"

# ---------------------------------------------------------------------------
# 3. Python simulation service (mtg-sim/sim, background)
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting Python simulation service..."
if lsof -ti :"$SIM_PORT" > /dev/null 2>&1; then
  echo "    Sim service already running on port $SIM_PORT."
elif [[ ! -f "$SIM_DIR/.venv/bin/python" ]]; then
  echo "    WARNING: $SIM_DIR/.venv not found."
  echo "    Run: cd mtg-sim && python3 -m venv .venv && source .venv/bin/activate && pip install -r sim/requirements.txt"
else
  cd "$SIM_DIR/sim"
  SIDECAR_URL="http://127.0.0.1:$SIDECAR_PORT" \
  OLLAMA_URL="http://127.0.0.1:$OLLAMA_PORT" \
  "$SIM_DIR/.venv/bin/python" main.py \
    > "$SCRIPT_DIR/.sim.log" 2>&1 &
  cd "$SCRIPT_DIR"
  echo "    Sim service started on port $SIM_PORT (logs: .sim.log)."
fi
echo "    Sim API:  http://localhost:$SIM_PORT/health"

# ---------------------------------------------------------------------------
# 3b. Deck deduction classifier (mtg-sim/classifier, background)
# ---------------------------------------------------------------------------
echo ""
echo "==> Starting deck deduction classifier..."
if lsof -ti :"$CLASSIFIER_PORT" > /dev/null 2>&1; then
  echo "    Classifier already running on port $CLASSIFIER_PORT."
elif [[ ! -f "$SIM_DIR/.venv/bin/python" ]]; then
  echo "    WARNING: $SIM_DIR/.venv not found — classifier not started."
else
  cd "$SIM_DIR"
  DRUPAL_URL="$DRUPAL_URL" \
  DRUPAL_USER="$DRUPAL_USER" \
  DRUPAL_PASS="$DRUPAL_PASS" \
  CLASSIFIER_HOST="$CLASSIFIER_HOST" \
  CLASSIFIER_PORT="$CLASSIFIER_PORT" \
  PYTHONPATH="$SIM_DIR" \
  "$SIM_DIR/.venv/bin/python" -m classifier.main \
    > "$SCRIPT_DIR/.classifier.log" 2>&1 &
  cd "$SCRIPT_DIR"
  echo "    Classifier started on port $CLASSIFIER_PORT (logs: .classifier.log)."
fi
echo "    Classifier: http://${CLASSIFIER_HOST}:${CLASSIFIER_PORT}/health"

# ---------------------------------------------------------------------------
# 4. Next.js frontend (dev server in background)
# ---------------------------------------------------------------------------
echo ""
cd "$FRONTEND_DIR"

if [[ ! -f ".env.local" && ! -f ".env.development" ]]; then
  echo "  WARNING: mtg-app/.env.local not found."
  echo "  Copy mtg-app/.env.example to .env.local with NEXT_PUBLIC_DRUPAL_* credentials."
  echo "  Skipping Next.js dev server."
  FRONTEND_STARTED=false
else
  echo "==> Stopping any existing Next.js instance on port $GATSBY_PORT..."
  stop_port_listeners "$GATSBY_PORT"
  wait_for_port_free "$GATSBY_PORT"

  if [[ "$FRESH_START" == true ]]; then
    echo "==> Clearing Next.js cache (--fresh)..."
    rm -rf "$FRONTEND_DIR/.next"
  fi

  echo "==> Starting Next.js dev server (background)..."
  : > "$SCRIPT_DIR/.frontend.log"
  (
    cd "$FRONTEND_DIR"
    export_frontend_env
    export NODE_EXTRA_CA_CERTS="${NODE_EXTRA_CA_CERTS:-$HOME/.local/share/mkcert/rootCA.pem}"
    exec npm run dev -- --port "$GATSBY_PORT" -H localhost
  ) >> "$SCRIPT_DIR/.frontend.log" 2>&1 &
  FRONTEND_PID=$!
  echo "    Next.js PID: $FRONTEND_PID (logs: .frontend.log)"
  echo "    Waiting for first compile..."
  wait_for_frontend_ready "$GATSBY_PORT" || true
  echo "    Frontend:   http://localhost:$GATSBY_PORT"
  FRONTEND_STARTED=true
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "All services started."
echo ""
echo "  Drupal admin:  $DRUPAL_URL/user"
echo "  Frontend:      http://localhost:$GATSBY_PORT"
echo "  Sim API:       http://localhost:$SIM_PORT/health"
echo "  Classifier:    http://${CLASSIFIER_HOST}:${CLASSIFIER_PORT}/health"
echo "  Ollama:        http://localhost:$OLLAMA_PORT"
echo "  AI sidecar:    http://localhost:$SIDECAR_PORT/health"
echo "  Milvus:        milvus:$MILVUS_PORT (DDEV internal — not on host localhost)"
echo ""
echo "Run './start.sh --stop' to shut everything down."
echo "Run './start.sh --fresh' to clear the Next.js cache on the next start."
