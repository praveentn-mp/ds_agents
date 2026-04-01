#!/usr/bin/env bash
# =============================================================================
# Agent Data Fabric — One-command Development Launcher
# =============================================================================
# Usage: ./start.sh
#
# This script:
#   1. Loads .env configuration
#   2. Sets up Python virtual environment
#   3. Installs Python + Node dependencies
#   4. Starts PostgreSQL via Colima Docker
#   5. Initializes the database
#   6. Kills any processes on configured ports
#   7. Starts all services (backend, MCP server, frontend)
#   8. Logs everything to logs/
# =============================================================================

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/startup_${TIMESTAMP}.log"

# Load .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✓ Loaded .env"
else
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ Created .env from .env.example — please review and add your secrets"

        # Auto-generate FERNET_KEY and JWT_SECRET_KEY if empty
        if command -v python3 &>/dev/null; then
            FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")
            if [ -n "$FERNET_KEY" ]; then
                sed -i '' "s|^FERNET_KEY=.*|FERNET_KEY=$FERNET_KEY|" .env 2>/dev/null || true
            fi
        fi
        JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || echo "default_jwt_secret_change_me")
        sed -i '' "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" .env 2>/dev/null || true

        set -a
        source .env
        set +a
    else
        echo "✗ No .env or .env.example found!"
        exit 1
    fi
fi

BACKEND_PORT="${BACKEND_PORT:-7790}"
FRONTEND_PORT="${FRONTEND_PORT:-7791}"
MCP_SERVER_PORT="${MCP_SERVER_PORT:-7792}"
POSTGRES_PORT="${POSTGRES_PORT:-5436}"
POSTGRES_DB="${POSTGRES_DB:-agent_data_fabric}"
POSTGRES_USER="${POSTGRES_USER:-adf_user}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-adf_secret_password_change_me}"

log() {
    local msg="[$(date +'%H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
}

# ─── Helper: Kill process on port ────────────────────────────────────────────

kill_port() {
    local port=$1
    local pid
    pid=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pid" ]; then
        log "⚡ Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# ─── Cleanup on exit ─────────────────────────────────────────────────────────

cleanup() {
    log "🛑 Shutting down services..."
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "${MCP_PID:-}" ] && kill "$MCP_PID" 2>/dev/null
    [ -n "${INSPECTOR_PID:-}" ] && kill "$INSPECTOR_PID" 2>/dev/null
    [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null
    log "✓ All services stopped"
}
trap cleanup EXIT

# ─── 1. Python Virtual Environment ───────────────────────────────────────────

log "═══════════════════════════════════════════════════════════════"
log "  Agent Data Fabric — Starting Up"
log "═══════════════════════════════════════════════════════════════"

if [ ! -d "venv" ]; then
    log "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

log "📦 Activating virtual environment..."
source venv/bin/activate

log "📦 Installing Python dependencies..."
pip install -q --upgrade pip >> "$LOG_FILE" 2>&1
pip install -q -r requirements.txt >> "$LOG_FILE" 2>&1
log "✓ Python dependencies installed"

# ─── 2. PostgreSQL via Docker (Colima) ────────────────────────────────────────

log "🐘 Setting up PostgreSQL on port $POSTGRES_PORT..."

# Check if Docker/Colima is running
if ! docker info &>/dev/null; then
    log "⚠️  Docker is not running. Attempting to start Colima..."
    colima start 2>> "$LOG_FILE" || {
        log "✗ Failed to start Colima. Please start Docker manually."
        exit 1
    }
fi

# Check if container already exists and running
CONTAINER_NAME="adf-postgres-dev"
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log "✓ PostgreSQL container already running"
else
    # Remove stopped container if exists
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    log "🐘 Starting PostgreSQL container..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        -e POSTGRES_DB="$POSTGRES_DB" \
        -e POSTGRES_USER="$POSTGRES_USER" \
        -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
        -p "${POSTGRES_PORT}:5432" \
        pgvector/pgvector:pg16 \
        >> "$LOG_FILE" 2>&1

    log "⏳ Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if docker exec "$CONTAINER_NAME" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" &>/dev/null; then
            break
        fi
        sleep 1
    done
    log "✓ PostgreSQL is ready"
fi

# ─── 3. Database Initialization ───────────────────────────────────────────────

log "🗄️  Initializing database..."
docker exec -i "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < db/init.sql >> "$LOG_FILE" 2>&1 || {
    log "⚠️  DB init had issues (may be OK if tables already exist)"
}
log "✓ Database initialized"

# ─── 4. Generate secrets if needed ────────────────────────────────────────────

if [ -z "${FERNET_KEY:-}" ] || [ "$FERNET_KEY" = "" ]; then
    log "🔑 Generating Fernet key..."
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    export FERNET_KEY
    sed -i '' "s|^FERNET_KEY=.*|FERNET_KEY=$FERNET_KEY|" .env 2>/dev/null || true
fi

if [ -z "${JWT_SECRET_KEY:-}" ] || [ "$JWT_SECRET_KEY" = "" ]; then
    log "🔑 Generating JWT secret..."
    JWT_SECRET_KEY=$(openssl rand -hex 32)
    export JWT_SECRET_KEY
    sed -i '' "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET_KEY|" .env 2>/dev/null || true
fi

# ─── 5. Kill existing processes on our ports ──────────────────────────────────

log "🔌 Freeing ports..."
kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
kill_port "$MCP_SERVER_PORT"
kill_port "$MCP_INSPECTOR_PORT"
kill_port 6277  # MCP Inspector proxy

# ─── 6. Install frontend dependencies ────────────────────────────────────────

log "📦 Installing frontend dependencies..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm install >> "$LOG_FILE" 2>&1
fi
cd ..
log "✓ Frontend dependencies installed"

# ─── 7. Start Backend ────────────────────────────────────────────────────────

# Set SSL cert file for Python 3.14+ on macOS (certifi bundle)
SSL_CA_PATH=$(python -c "import certifi; print(certifi.where())" 2>/dev/null || true)
if [ -n "$SSL_CA_PATH" ] && [ -f "$SSL_CA_PATH" ]; then
    export SSL_CERT_FILE="$SSL_CA_PATH"
    export REQUESTS_CA_BUNDLE="$SSL_CA_PATH"
    log "✓ SSL_CERT_FILE set to $SSL_CA_PATH"
fi

log "🚀 Starting Backend (port $BACKEND_PORT)..."
cd "$SCRIPT_DIR"
python -m uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port "$BACKEND_PORT" \
    --reload \
    >> "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
log "✓ Backend started (PID: $BACKEND_PID)"

# ─── 8. Start MCP Server ─────────────────────────────────────────────────────

log "🚀 Starting MCP Server (port $MCP_SERVER_PORT)..."
python -m mcp_server.server \
    >> "$LOG_DIR/mcp_server.log" 2>&1 &
MCP_PID=$!
log "✓ MCP Server started (PID: $MCP_PID)"

# ─── 8b. Start MCP Inspector ────────────────────────────────────────────────

log "🔍 Starting MCP Inspector (port $MCP_INSPECTOR_PORT)..."
DANGEROUSLY_OMIT_AUTH=true fastmcp dev inspector mcp_server/server.py:mcp \
    --ui-port "$MCP_INSPECTOR_PORT" \
    --server-port 6277 \
    --no-reload \
    >> "$LOG_DIR/mcp_inspector.log" 2>&1 &
INSPECTOR_PID=$!
log "✓ MCP Inspector started (PID: $INSPECTOR_PID)"

# ─── 9. Start Frontend ───────────────────────────────────────────────────────

log "🚀 Starting Frontend (port $FRONTEND_PORT)..."
cd frontend
npm run dev >> "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
cd ..
log "✓ Frontend started (PID: $FRONTEND_PID)"

# ─── 10. Startup Summary ─────────────────────────────────────────────────────

sleep 2

log ""
log "═══════════════════════════════════════════════════════════════"
log "  ✅ Agent Data Fabric is running!"
log "═══════════════════════════════════════════════════════════════"
log ""
log "  🌐 Frontend:     http://localhost:$FRONTEND_PORT"
log "  🔧 Backend API:  http://localhost:$BACKEND_PORT"
log "  📡 MCP Server:   http://localhost:$MCP_SERVER_PORT"
log "  � MCP Inspector: http://localhost:$MCP_INSPECTOR_PORT"
log "  �🐘 PostgreSQL:   localhost:$POSTGRES_PORT"
log "  📝 API Docs:     http://localhost:$BACKEND_PORT/docs"
log ""
log "  📋 Logs:         $LOG_DIR/"
log "  🔑 Login:        admin@adf.local / admin123"
log ""
log "  Press Ctrl+C to stop all services"
log "═══════════════════════════════════════════════════════════════"

# Wait for all background processes
wait
