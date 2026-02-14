#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/feifan.wang@flightcentre.com/Personal/EnergyHub"
BE_DIR="$ROOT/backend"
FE_DIR="$ROOT/frontend"
LOG_DIR="/tmp/energyhub"
BE_LOG="$LOG_DIR/backend.log"
FE_LOG="$LOG_DIR/frontend.log"
BE_PID_FILE="$LOG_DIR/backend.pid"
FE_PID_FILE="$LOG_DIR/frontend.pid"

mkdir -p "$LOG_DIR"

kill_existing() {
  pkill -f "uvicorn app.main:app" >/dev/null 2>&1 || true
  if lsof -tiTCP:8000 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    lsof -tiTCP:8000 -sTCP:LISTEN -n -P | xargs kill >/dev/null 2>&1 || true
  fi
  pkill -f "vite --host" >/dev/null 2>&1 || true
  pkill -f "npm run dev -- --host" >/dev/null 2>&1 || true
  if lsof -tiTCP:5174 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    lsof -tiTCP:5174 -sTCP:LISTEN -n -P | xargs kill >/dev/null 2>&1 || true
  fi
}

start_backend() {
  cd "$BE_DIR"
  if [[ ! -x "./.venv/bin/python" ]]; then
    echo "[error] Missing backend venv: $BE_DIR/.venv/bin/python"
    exit 1
  fi
  : "${BACKEND_RELOAD:=0}"
  if [[ "$BACKEND_RELOAD" == "1" ]]; then
    nohup ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload >"$BE_LOG" 2>&1 </dev/null &
  else
    nohup ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >"$BE_LOG" 2>&1 </dev/null &
  fi
  echo $! >"$BE_PID_FILE"
}

start_frontend() {
  cd "$FE_DIR"
  if [[ ! -d "node_modules" ]]; then
    echo "[error] Missing frontend node_modules. Run: cd $FE_DIR && npm install"
    exit 1
  fi
  nohup env NODE_OPTIONS="" npm run dev -- --host 127.0.0.1 --port 5174 --strictPort >"$FE_LOG" 2>&1 </dev/null &
  echo $! >"$FE_PID_FILE"
}

status() {
  echo "Backend:"
  if lsof -iTCP:8000 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    echo "  LISTENING on 127.0.0.1:8000"
    curl -sf http://127.0.0.1:8000/health || true
    echo
  else
    echo "  NOT RUNNING"
  fi

  echo "Frontend:"
  if lsof -iTCP:5174 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
    echo "  LISTENING on 127.0.0.1:5174"
  else
    echo "  NOT RUNNING"
  fi

  echo "Logs:"
  echo "  $BE_LOG"
  echo "  $FE_LOG"
}

logs() {
  echo "== Backend log =="
  tail -n 60 "$BE_LOG" 2>/dev/null || true
  echo
  echo "== Frontend log =="
  tail -n 60 "$FE_LOG" 2>/dev/null || true
}

validate() {
  cd "$ROOT/backend"
  ./.venv/bin/python scripts/validate_pricing_data.py --api-smoke
}

cmd="${1:-}"
case "$cmd" in
  up)
    kill_existing
    start_backend
    start_frontend
    sleep 2
    status
    ;;
  down)
    kill_existing
    echo "Stopped local FE/BE."
    ;;
  restart)
    kill_existing
    start_backend
    start_frontend
    sleep 2
    status
    ;;
  status)
    status
    ;;
  logs)
    logs
    ;;
  validate)
    validate
    ;;
  *)
    echo "Usage: $0 {up|down|restart|status|logs|validate}"
    exit 1
    ;;
esac
