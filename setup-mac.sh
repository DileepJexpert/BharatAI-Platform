#!/bin/bash
# ============================================
# BharatAI Platform — macOS Setup Script
# ============================================

set -e

echo ""
echo "========================================"
echo "  BharatAI Platform — macOS Setup"
echo "========================================"
echo ""

# --- Check Python ---
echo "[1/7] Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "ERROR: Python not found."
    echo "Install Python 3.11+ via Homebrew:"
    echo "  brew install python@3.11"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)
echo "Found: $PY_VERSION"

# Check version is 3.11+
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    echo "WARNING: Python 3.11+ recommended. You have $PY_VERSION"
    echo "Install via: brew install python@3.11"
fi

# --- Check Docker ---
echo ""
echo "[2/7] Checking Docker..."
if command -v docker &> /dev/null; then
    docker --version
else
    echo "WARNING: Docker not found."
    echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    echo "PostgreSQL and Redis will not start without Docker."
fi

# --- Check Ollama ---
echo ""
echo "[3/7] Checking Ollama..."
if command -v ollama &> /dev/null; then
    ollama --version
else
    echo "WARNING: Ollama not found."
    echo "Install from https://ollama.com/download/mac"
    echo "LLM inference will not work without Ollama."
fi

# --- Create virtual environment ---
echo ""
echo "[4/7] Creating Python virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Skipping."
else
    $PYTHON -m venv venv
    echo "Virtual environment created."
fi

# --- Activate venv and install dependencies ---
echo ""
echo "[5/7] Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo "Dependencies installed."

# --- Setup environment file ---
echo ""
echo "[6/7] Setting up environment file..."
if [ -f ".env" ]; then
    echo ".env already exists. Skipping."
else
    cp .env.example .env
    echo ".env created from .env.example"

    # macOS: default to CPU if no NVIDIA GPU
    if ! command -v nvidia-smi &> /dev/null; then
        echo "No NVIDIA GPU detected. Setting CPU mode..."
        sed -i '' 's/WHISPER_DEVICE=cuda/WHISPER_DEVICE=cpu/' .env
        sed -i '' 's/WHISPER_COMPUTE_TYPE=float16/WHISPER_COMPUTE_TYPE=int8/' .env
        echo "Updated .env: WHISPER_DEVICE=cpu, WHISPER_COMPUTE_TYPE=int8"
    fi
fi

# --- Start Docker services ---
echo ""
echo "[7/7] Starting PostgreSQL and Redis via Docker..."
if command -v docker &> /dev/null; then
    docker-compose up -d 2>/dev/null || docker compose up -d 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "PostgreSQL and Redis are running."
    else
        echo "WARNING: Docker services failed to start."
        echo "Run manually: docker-compose up -d"
    fi
else
    echo "Skipping Docker services (Docker not installed)."
fi

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Pull the LLM model (requires Ollama running):"
echo "     ollama pull llama3.2:3b-instruct-q4_0"
echo ""
echo "  3. Run tests (no GPU/Ollama/Redis needed):"
echo "     pytest tests/ apps/ -v"
echo ""
echo "  4. Start the server:"
echo "     uvicorn core.api.gateway:app --reload --port 8000"
echo ""
echo "  5. Test it:"
echo "     curl http://localhost:8000/health"
echo ""
echo "  Note: macOS has no NVIDIA GPU. STT runs on CPU (slower)."
echo "  LLM via Ollama uses Apple Silicon (Metal) if available."
echo ""
