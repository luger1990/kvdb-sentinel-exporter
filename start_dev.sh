#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker-redis-sentinel-compose.yaml"
VENV_DIR="${ROOT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-16379}"
CONFIG_PATH="${CONFIG_PATH:-${ROOT_DIR}/config.dev.yaml}"
DEBUG="${DEBUG:-true}"

log() {
  printf '[start_dev] %s\n' "$*"
}

fail() {
  printf '[start_dev] ERROR: %s\n' "$*" >&2
  exit 1
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

docker_compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif has_command docker-compose; then
    docker-compose "$@"
  else
    fail "Docker Compose is not installed. Install Docker Compose v2 or docker-compose."
  fi
}

check_prerequisites() {
  has_command docker || fail "Docker is not installed or not in PATH."
  docker info >/dev/null 2>&1 || fail "Docker daemon is not running or current user cannot access it."
  has_command "${PYTHON_BIN}" || fail "${PYTHON_BIN} is not installed or not in PATH."
  [[ -f "${COMPOSE_FILE}" ]] || fail "Compose file not found: ${COMPOSE_FILE}"
  [[ -f "${ROOT_DIR}/requirements-dev.txt" ]] || fail "requirements-dev.txt not found."
  [[ -f "${CONFIG_PATH}" ]] || fail "Config file not found: ${CONFIG_PATH}"
}

ensure_venv() {
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    log "Creating virtualenv: ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}" || fail "Failed to create virtualenv. Install python3-venv if needed."
  fi

  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"

  python -m pip --version >/dev/null 2>&1 || fail "pip is not available in ${VENV_DIR}."
}

deps_installed() {
  python - <<'PY'
import importlib.util
import sys

modules = [
    "flask",
    "werkzeug",
    "redis",
    "prometheus_client",
    "yaml",
    "flask_bootstrap",
    "dotenv",
    "gunicorn",
    "flask_debugtoolbar",
]

missing = [module for module in modules if importlib.util.find_spec(module) is None]
if missing:
    print(", ".join(missing))
    sys.exit(1)
PY
}

ensure_dependencies() {
  if deps_installed >/tmp/kvdb-dev-missing-deps.txt 2>/dev/null; then
    log "Python dependencies are already installed."
    return
  fi

  log "Missing Python dependencies: $(cat /tmp/kvdb-dev-missing-deps.txt)"
  log "Installing development dependencies from requirements-dev.txt"
  python -m pip install --upgrade pip
  python -m pip install -r "${ROOT_DIR}/requirements-dev.txt"

  if ! deps_installed >/tmp/kvdb-dev-missing-deps.txt 2>/dev/null; then
    fail "Dependencies are still missing after install: $(cat /tmp/kvdb-dev-missing-deps.txt)"
  fi
}

start_redis_sentinel_cluster() {
  log "Validating Docker Compose file"
  docker_compose -f "${COMPOSE_FILE}" config >/dev/null

  log "Starting Redis Sentinel test cluster"
  docker_compose -f "${COMPOSE_FILE}" up -d
}

print_runtime_info() {
  cat <<EOF
[start_dev] Redis/Sentinel test endpoints:
  Redis master:     127.0.0.1:36379
  Redis replicas:   127.0.0.1:36380, 127.0.0.1:36381
  Redis Sentinel:   127.0.0.1:46379, 127.0.0.1:46380, 127.0.0.1:46381

[start_dev] Exporter endpoints:
  Bind:     ${HOST}:${PORT}
  Home:     http://127.0.0.1:${PORT}/
  UI:       http://127.0.0.1:${PORT}/redis-sentinel-group-2/info
  Metrics:  http://127.0.0.1:${PORT}/redis-sentinel-group-2/metrics

[start_dev] Stop Redis/Sentinel test cluster:
  docker compose -f docker-redis-sentinel-compose.yaml down
EOF
}

start_python_service() {
  export CONFIG_PATH
  export HOST
  export PORT
  export DEBUG
  export SECRET_KEY="${SECRET_KEY:-dev-secret-key-change-me}"

  # Keep local test passwords empty unless the caller explicitly sets them.
  export REDIS_GROUP_1_PASSWORD="${REDIS_GROUP_1_PASSWORD:-}"
  export KVROCKS_GROUP_1_PASSWORD="${KVROCKS_GROUP_1_PASSWORD:-}"

  log "Starting Python service with CONFIG_PATH=${CONFIG_PATH}, HOST=${HOST}, PORT=${PORT}, DEBUG=${DEBUG}"
  exec python "${ROOT_DIR}/run.py"
}

main() {
  cd "${ROOT_DIR}"
  check_prerequisites
  ensure_venv
  ensure_dependencies
  start_redis_sentinel_cluster
  print_runtime_info
  start_python_service
}

main "$@"
