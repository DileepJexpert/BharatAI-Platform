@echo off
REM ============================================
REM BharatAI Platform — Windows Setup Script
REM ============================================

echo.
echo ========================================
echo   BharatAI Platform — Windows Setup
echo ========================================
echo.

REM --- Check Python ---
echo [1/7] Checking Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found.
    echo Install Python 3.11+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
python --version

REM --- Check Docker ---
echo.
echo [2/7] Checking Docker...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Docker not found.
    echo Install Docker Desktop from https://www.docker.com/products/docker-desktop/
    echo PostgreSQL and Redis will not start without Docker.
    echo.
) else (
    docker --version
)

REM --- Check Ollama ---
echo.
echo [3/7] Checking Ollama...
ollama --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Ollama not found.
    echo Install from https://ollama.com/download/windows
    echo LLM inference will not work without Ollama.
    echo.
) else (
    ollama --version
)

REM --- Create virtual environment ---
echo.
echo [4/7] Creating Python virtual environment...
if exist venv (
    echo Virtual environment already exists. Skipping.
) else (
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
)

REM --- Activate venv and install dependencies ---
echo.
echo [5/7] Installing Python dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo Dependencies installed.

REM --- Setup environment file ---
echo.
echo [6/7] Setting up environment file...
if exist .env (
    echo .env already exists. Skipping.
) else (
    copy .env.example .env
    echo .env created from .env.example
    echo Edit .env to customize settings if needed.
)

REM --- Start Docker services ---
echo.
echo [7/7] Starting PostgreSQL and Redis via Docker...
docker --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    docker-compose up -d
    if %ERRORLEVEL% NEQ 0 (
        echo WARNING: Docker services failed to start.
        echo Run manually: docker-compose up -d
    ) else (
        echo PostgreSQL and Redis are running.
    )
) else (
    echo Skipping Docker services (Docker not installed).
)

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Next steps:
echo.
echo   1. Activate the virtual environment:
echo      venv\Scripts\activate
echo.
echo   2. Pull the LLM model (requires Ollama running):
echo      ollama pull llama3.2:3b-instruct-q4_0
echo.
echo   3. Run tests (no GPU/Ollama/Redis needed):
echo      pytest tests/ apps/ -v
echo.
echo   4. Start the server:
echo      uvicorn core.api.gateway:app --reload --port 8000
echo.
echo   5. Test it:
echo      curl http://localhost:8000/health
echo.
echo   If no GPU, set these in .env:
echo      WHISPER_DEVICE=cpu
echo      WHISPER_COMPUTE_TYPE=int8
echo.
pause
