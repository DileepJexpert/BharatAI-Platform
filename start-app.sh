#!/bin/bash
# ============================================
# BharatAI Platform — App Start Script
# Works on Linux, macOS, and Windows (Git Bash)
# ============================================

set -e

echo ""
echo "========================================"
echo "  BharatAI Platform — App Launcher"
echo "========================================"
echo ""

# --- Detect OS ---
OS="unknown"
case "$(uname -s)" in
    Linux*)  OS="linux";;
    Darwin*) OS="mac";;
    MINGW*|MSYS*|CYGWIN*) OS="windows";;
esac
echo "Detected OS: $OS"

# --- Activate virtual environment ---
echo ""
echo "[1/5] Activating virtual environment..."
if [ "$OS" = "windows" ]; then
    if [ -f "venv/Scripts/activate" ]; then
        source venv/Scripts/activate
    else
        echo "ERROR: Virtual environment not found. Run setup-windows.bat first."
        exit 1
    fi
else
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    else
        echo "ERROR: Virtual environment not found. Run setup-mac.sh first."
        exit 1
    fi
fi
echo "Virtual environment activated."

# --- Check .env ---
echo ""
echo "[2/5] Checking environment..."
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi
echo ".env file OK."

# --- Check Docker services ---
echo ""
echo "[3/5] Checking PostgreSQL and Redis..."
DOCKER_OK=true

if command -v docker &> /dev/null; then
    PG_RUNNING=$(docker ps --filter "name=bharatai-postgres" --format "{{.Names}}" 2>/dev/null)
    REDIS_RUNNING=$(docker ps --filter "name=bharatai-redis" --format "{{.Names}}" 2>/dev/null)

    if [ -z "$PG_RUNNING" ] || [ -z "$REDIS_RUNNING" ]; then
        echo "Starting Docker services..."
        docker-compose up -d 2>/dev/null || docker compose up -d 2>/dev/null
        sleep 3
    fi
    echo "PostgreSQL: running"
    echo "Redis: running"
else
    echo "WARNING: Docker not available. DB and session store may not work."
    DOCKER_OK=false
fi

# --- Check Ollama ---
echo ""
echo "[4/5] Checking Ollama..."
OLLAMA_OK=false
if command -v ollama &> /dev/null; then
    # Check if ollama is serving
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama is running."
        OLLAMA_OK=true

        # Check if model is pulled
        MODEL_CHECK=$(curl -s http://localhost:11434/api/tags | python -c "
import sys, json
data = json.load(sys.stdin)
models = [m['name'] for m in data.get('models', [])]
print('found' if any('llama3.2' in m or '3b' in m for m in models) else 'missing')
" 2>/dev/null || echo "error")

        if [ "$MODEL_CHECK" = "found" ]; then
            echo "LLM model: loaded"
        else
            echo "WARNING: LLM model not pulled yet."
            echo "Run: ollama pull llama3.2:3b-instruct-q4_0"
        fi
    else
        echo "WARNING: Ollama installed but not running."
        echo "Start it with: ollama serve"
    fi
else
    echo "WARNING: Ollama not installed. LLM will not work."
    echo "Install from: https://ollama.com"
fi

# --- Start the app ---
echo ""
echo "[5/5] Starting BharatAI Platform..."
echo ""
echo "========================================"
echo "  Server starting on http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo "  Health:   http://localhost:8000/health"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop."
echo ""

uvicorn core.api.gateway:app --reload --host 0.0.0.0 --port 8000
