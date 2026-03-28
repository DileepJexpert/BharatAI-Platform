@echo off
setlocal EnableDelayedExpansion
title BharatAI Platform — Ollama Setup (Windows)
color 0A

echo ============================================================
echo   BharatAI Platform — Ollama Setup for Windows
echo ============================================================
echo.

:: -----------------------------------------------------------
:: 1. Check if Ollama is installed
:: -----------------------------------------------------------
echo [1/5] Checking if Ollama is installed...
where ollama >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo  Ollama is NOT installed.
    echo.
    echo  Please download and install Ollama from:
    echo    https://ollama.com/download/windows
    echo.
    echo  After installing, re-run this script.
    echo.
    pause
    exit /b 1
)
echo       OK — Ollama found.
echo.

:: -----------------------------------------------------------
:: 2. Check if Ollama is running
:: -----------------------------------------------------------
echo [2/5] Checking if Ollama service is running...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo       Ollama is not running. Starting it...
    start "" ollama serve
    echo       Waiting 5 seconds for Ollama to start...
    timeout /t 5 /nobreak >nul
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo.
        echo  ERROR: Could not start Ollama.
        echo  Try running "ollama serve" manually in another terminal.
        echo.
        pause
        exit /b 1
    )
)
echo       OK — Ollama is running at http://localhost:11434
echo.

:: -----------------------------------------------------------
:: 3. Check GPU availability
:: -----------------------------------------------------------
echo [3/5] Checking GPU availability...
nvidia-smi >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo       NVIDIA GPU detected:
    for /f "tokens=*" %%a in ('nvidia-smi --query-gpu=name,memory.total --format=csv,noheader') do (
        echo         %%a
    )
    echo       Ollama will use GPU acceleration.
) else (
    echo       No NVIDIA GPU detected — Ollama will run on CPU.
    echo       This will be slower but still works for testing.
)
echo.

:: -----------------------------------------------------------
:: 4. Pull required models
:: -----------------------------------------------------------
echo [4/5] Pulling required models for BharatAI Platform...
echo.

echo --- Pulling llama3.2:3b-instruct-q4_0 (Primary LLM ~2.4GB) ---
echo     This is the main language model for all BharatAI apps.
echo     Download may take a few minutes on first run...
echo.
ollama pull llama3.2:3b-instruct-q4_0
if %ERRORLEVEL% neq 0 (
    echo.
    echo  WARNING: Failed to pull llama3.2:3b-instruct-q4_0
    echo  You can retry manually: ollama pull llama3.2:3b-instruct-q4_0
    echo.
) else (
    echo       OK — llama3.2:3b-instruct-q4_0 ready.
)
echo.

:: -----------------------------------------------------------
:: 5. Verify installation
:: -----------------------------------------------------------
echo [5/5] Verifying setup...
echo.
echo  Installed models:
echo  -----------------
ollama list
echo.

:: Quick test — run a simple prompt
echo  Running quick test...
ollama run llama3.2:3b-instruct-q4_0 "Say hello in Hindi in one sentence" 2>nul
if %ERRORLEVEL% equ 0 (
    echo.
    echo       OK — Model is working!
) else (
    echo.
    echo  WARNING: Quick test failed. The model may still be loading.
    echo  Try again: ollama run llama3.2:3b-instruct-q4_0 "Hello"
)

echo.
echo ============================================================
echo   Ollama Setup Complete!
echo ============================================================
echo.
echo  Models ready:
echo    - llama3.2:3b-instruct-q4_0  (Primary LLM)
echo.
echo  Ollama API: http://localhost:11434
echo.
echo  Next steps:
echo    1. Start Docker services:  docker-compose up -d
echo    2. Start BharatAI server:  python -m uvicorn core.api.gateway:app --reload
echo    3. Test health endpoint:   curl http://localhost:8000/health
echo.
echo  Useful Ollama commands:
echo    ollama list             — Show installed models
echo    ollama ps               — Show running models
echo    ollama stop MODEL       — Unload a model from memory
echo    ollama rm MODEL         — Remove a model
echo    ollama serve            — Start Ollama server (if not running)
echo.
pause
