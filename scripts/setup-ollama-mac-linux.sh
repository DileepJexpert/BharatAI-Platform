#!/usr/bin/env bash
set -euo pipefail

# ============================================================
#   BharatAI Platform — Ollama Setup (macOS / Linux)
# ============================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo ""
echo -e "${BLUE}${BOLD}============================================================${NC}"
echo -e "${BLUE}${BOLD}  BharatAI Platform — Ollama Setup${NC}"
echo -e "${BLUE}${BOLD}============================================================${NC}"
echo ""

# -----------------------------------------------------------
# 1. Check / Install Ollama
# -----------------------------------------------------------
echo -e "${BOLD}[1/5] Checking if Ollama is installed...${NC}"

if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>/dev/null || echo "unknown")
    echo -e "      ${GREEN}OK${NC} — Ollama found (${OLLAMA_VERSION})"
else
    echo -e "      ${YELLOW}Ollama is not installed.${NC}"
    echo ""

    # Detect OS
    OS="$(uname -s)"
    case "$OS" in
        Linux*)
            echo "  Installing Ollama for Linux..."
            curl -fsSL https://ollama.com/install.sh | sh
            ;;
        Darwin*)
            echo "  On macOS, please install Ollama from:"
            echo "    https://ollama.com/download/mac"
            echo ""
            echo "  Or with Homebrew:"
            echo "    brew install ollama"
            echo ""
            read -p "  Have you installed Ollama? (y/n): " answer
            if [[ "$answer" != "y" && "$answer" != "Y" ]]; then
                echo "  Please install Ollama first, then re-run this script."
                exit 1
            fi
            ;;
        *)
            echo -e "  ${RED}Unsupported OS: $OS${NC}"
            echo "  Please install Ollama manually: https://ollama.com"
            exit 1
            ;;
    esac

    # Verify installation
    if ! command -v ollama &> /dev/null; then
        echo -e "  ${RED}ERROR: Ollama installation failed.${NC}"
        echo "  Install manually from https://ollama.com and re-run this script."
        exit 1
    fi
    echo -e "      ${GREEN}OK${NC} — Ollama installed successfully."
fi
echo ""

# -----------------------------------------------------------
# 2. Check / Start Ollama service
# -----------------------------------------------------------
echo -e "${BOLD}[2/5] Checking if Ollama service is running...${NC}"

if curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo -e "      ${GREEN}OK${NC} — Ollama is running at http://localhost:11434"
else
    echo "      Ollama is not running. Starting it..."
    ollama serve &> /dev/null &
    OLLAMA_PID=$!
    echo "      Waiting for Ollama to start (PID: $OLLAMA_PID)..."
    sleep 3

    # Retry up to 10 seconds
    for i in $(seq 1 7); do
        if curl -s http://localhost:11434/api/tags &> /dev/null; then
            break
        fi
        sleep 1
    done

    if curl -s http://localhost:11434/api/tags &> /dev/null; then
        echo -e "      ${GREEN}OK${NC} — Ollama started successfully."
    else
        echo -e "      ${RED}ERROR: Could not start Ollama.${NC}"
        echo "      Try running 'ollama serve' manually in another terminal."
        exit 1
    fi
fi
echo ""

# -----------------------------------------------------------
# 3. Check GPU availability
# -----------------------------------------------------------
echo -e "${BOLD}[3/5] Checking GPU availability...${NC}"

OS="$(uname -s)"
GPU_FOUND=false

if [[ "$OS" == "Darwin" ]]; then
    # macOS — check for Apple Silicon
    CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
    if [[ "$CHIP" == *"Apple"* ]]; then
        echo -e "      ${GREEN}Apple Silicon detected${NC}: $CHIP"
        echo "      Ollama will use Metal GPU acceleration."
        GPU_FOUND=true
    else
        echo -e "      ${YELLOW}Intel Mac detected${NC} — Ollama will run on CPU."
    fi
elif command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null | head -1)
    echo -e "      ${GREEN}NVIDIA GPU detected${NC}: $GPU_NAME ($GPU_MEM)"
    echo "      Ollama will use CUDA acceleration."
    GPU_FOUND=true
else
    echo -e "      ${YELLOW}No GPU detected${NC} — Ollama will run on CPU."
    echo "      This will be slower but still works for testing."
fi
echo ""

# -----------------------------------------------------------
# 4. Pull required models
# -----------------------------------------------------------
echo -e "${BOLD}[4/5] Pulling required models for BharatAI Platform...${NC}"
echo ""

pull_model() {
    local model="$1"
    local desc="$2"
    local size="$3"

    echo -e "  --- ${BOLD}$model${NC} ($desc ~$size) ---"

    # Check if already downloaded
    if ollama list 2>/dev/null | grep -q "$model"; then
        echo -e "      ${GREEN}Already installed${NC} — skipping download."
    else
        echo "      Downloading... (this may take a few minutes)"
        if ollama pull "$model"; then
            echo -e "      ${GREEN}OK${NC} — $model ready."
        else
            echo -e "      ${RED}WARNING${NC}: Failed to pull $model"
            echo "      You can retry manually: ollama pull $model"
        fi
    fi
    echo ""
}

pull_model "llama3.2:3b-instruct-q4_0" "Primary LLM" "2.4GB"

# -----------------------------------------------------------
# 5. Verify installation
# -----------------------------------------------------------
echo -e "${BOLD}[5/5] Verifying setup...${NC}"
echo ""
echo "  Installed models:"
echo "  -----------------"
ollama list
echo ""

# Quick test
echo "  Running quick test..."
RESPONSE=$(ollama run llama3.2:3b-instruct-q4_0 "Say hello in Hindi in one sentence" 2>/dev/null || echo "FAIL")
if [[ "$RESPONSE" != "FAIL" ]]; then
    echo -e "  ${GREEN}Model response:${NC} $RESPONSE"
    echo ""
    echo -e "      ${GREEN}OK${NC} — Model is working!"
else
    echo -e "      ${YELLOW}WARNING${NC}: Quick test failed. The model may still be loading."
    echo "      Try again: ollama run llama3.2:3b-instruct-q4_0 \"Hello\""
fi

echo ""
echo -e "${BLUE}${BOLD}============================================================${NC}"
echo -e "${BLUE}${BOLD}  Ollama Setup Complete!${NC}"
echo -e "${BLUE}${BOLD}============================================================${NC}"
echo ""
echo "  Models ready:"
echo "    - llama3.2:3b-instruct-q4_0  (Primary LLM)"
echo ""
echo "  Ollama API: http://localhost:11434"
echo ""
echo "  Next steps:"
echo "    1. Start Docker services:  docker-compose up -d"
echo "    2. Start BharatAI server:  python -m uvicorn core.api.gateway:app --reload"
echo "    3. Test health endpoint:   curl http://localhost:8000/health"
echo ""
echo "  Useful Ollama commands:"
echo "    ollama list             — Show installed models"
echo "    ollama ps               — Show running models"
echo "    ollama stop MODEL       — Unload a model from memory"
echo "    ollama rm MODEL         — Remove a model"
echo "    ollama serve            — Start Ollama server (if not running)"
echo ""
