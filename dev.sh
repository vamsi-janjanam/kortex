#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
API="$ROOT/apps/api"
WEB="$ROOT/apps/web"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}! $1${NC}"; }
die()  { echo -e "${RED}✗ $1${NC}"; exit 1; }

# ── .env ──────────────────────────────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
  die ".env not found — create it with your API keys (see Environment Variables in CLAUDE.md)"
fi
export $(grep -v '^#' "$ROOT/.env" | xargs) 2>/dev/null
ok ".env loaded"

# ── Pipenv install ─────────────────────────────────────────────────────────────
if ! command -v pipenv &>/dev/null; then
  warn "pipenv not found — installing..."
  pip3 install pipenv --quiet
fi

cd "$API"
if [ ! -d "$(pipenv --venv 2>/dev/null)" ] 2>/dev/null; then
  echo "Installing Python dependencies..."
  pipenv install --dev --quiet
fi
ok "Python environment ready"

# ── PostgreSQL ─────────────────────────────────────────────────────────────────
if ! pg_isready -q 2>/dev/null; then
  if command -v brew &>/dev/null && brew list postgresql@16 &>/dev/null; then
    brew services start postgresql@16 &>/dev/null
    sleep 2
    ok "PostgreSQL started"
  else
    die "PostgreSQL is not running. Install with: brew install postgresql@16 && brew services start postgresql@16"
  fi
else
  ok "PostgreSQL running"
fi

# Create DB if it doesn't exist
createdb kortex 2>/dev/null && ok "Database 'kortex' created" || ok "Database 'kortex' exists"

# ── Qdrant ─────────────────────────────────────────────────────────────────────
if ! curl -sf http://localhost:6333/healthz &>/dev/null; then
  if command -v qdrant &>/dev/null; then
    warn "Starting Qdrant..."
    nohup qdrant > /tmp/qdrant.log 2>&1 &
    sleep 3
    ok "Qdrant started (logs: /tmp/qdrant.log)"
  else
    warn "Qdrant not running — search endpoints will be unavailable"
    warn "Install with: brew install qdrant"
  fi
else
  ok "Qdrant running"
fi

# ── Migrations ─────────────────────────────────────────────────────────────────
cd "$API"
pipenv run alembic upgrade head --quiet 2>/dev/null && ok "Database migrated" || warn "Migration skipped (check DB connection)"

# ── Start ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Kortex API → http://localhost:8000${NC}"
echo -e "${GREEN}  Swagger UI → http://localhost:8000/docs${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

cd "$API"
PYTHONPATH="$ROOT/pipelines:$ROOT/data" \
  pipenv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
