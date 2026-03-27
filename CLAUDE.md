# BharatAI Platform — Claude Code Instructions

## What This Project Is

A shared Python backend that powers multiple Indian-language AI apps from one codebase. MVP runs on a local NVIDIA RTX 4060 (8GB VRAM). First app: ASHA Health (voice-based health data entry for rural health workers).

## Tech Stack

- **Python 3.11** with **FastAPI** (async)
- **Ollama** for LLM inference (llama3.2:3b-instruct-q4_0)
- **faster-whisper** for STT (IndicWhisper medium model via HuggingFace)
- **gTTS** for TTS (MVP — free, CPU-only, no VRAM)
- **PostgreSQL** for persistent storage (one schema per app)
- **Redis** for session store (30-min TTL)
- **pytest** for testing
- **Alembic** for DB migrations
- **SQLAlchemy 2.0** (async) for ORM

## Project Structure Rules

```
bharatai-platform/
├── core/                  # SHARED — never put app-specific logic here
│   ├── voice/
│   │   ├── stt.py         # faster-whisper wrapper
│   │   ├── tts.py         # gTTS wrapper
│   │   └── pipeline.py    # STT → LLM → TTS chain with error handling
│   ├── llm/
│   │   ├── client.py      # Ollama HTTP client
│   │   ├── prompt_builder.py
│   │   └── model_manager.py  # VRAM budget + sequential loading
│   ├── language/
│   │   ├── detector.py    # Script-based language detection
│   │   └── translator.py  # Stub for MVP, IndicTrans2 later
│   ├── auth/
│   │   ├── middleware.py   # Static API key auth (MVP)
│   │   └── tenancy.py     # app_id isolation
│   ├── db/
│   │   ├── base.py        # SQLAlchemy async engine + session factory
│   │   └── migrations/    # Alembic
│   └── api/
│       ├── gateway.py     # FastAPI app + route registration
│       └── plugin_registry.py  # BasePlugin ABC + loader
├── apps/
│   ├── asha_health/       # First plugin
│   │   ├── plugin.py      # Implements BasePlugin
│   │   ├── prompts.py     # System prompts
│   │   ├── models.py      # SQLAlchemy models (asha_health schema)
│   │   ├── nhm_client.py  # NHM API sync queue
│   │   └── tests/
│   └── lawyer_ai/         # Phase 6 validation
├── tests/
│   ├── core/
│   └── integration/
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
├── .env.example
└── CLAUDE.md              # This file
```

## Architecture Constraints

### VRAM Budget (8GB total, 7GB usable)
- **LLM** (llama3.2:3b): ~2.4GB — kept warm in Ollama
- **STT** (IndicWhisper medium): ~1.5GB — loaded per-request, unloaded after
- **TTS** (gTTS): 0GB — runs on CPU / calls Google API
- **CUDA overhead**: ~800MB–1GB
- **NEVER load STT and LLM simultaneously** — sequential loading only

### Plugin Architecture
- Every app MUST implement `BasePlugin` (see core/api/plugin_registry.py)
- Plugins provide: `app_id`, `system_prompt()`, `parse_response()`, `router()`
- Core auto-provides: voice endpoint, chat endpoint, session management, auth
- Each app gets its own PostgreSQL schema — no cross-app data access

### Voice Pipeline Error Handling (CRITICAL)
The pipeline MUST handle these failure modes:
1. **Low-confidence STT** (< 0.5): Return "please repeat" — do NOT call LLM
2. **Invalid JSON from LLM**: Retry once, then return error gracefully
3. **TTS failure**: Return text-only response (audio=null), never crash

### Session Store
- Redis-backed, JSON serialized
- TTL: 30 minutes from last activity
- Max 5 conversation turns in history (keep LLM context small)
- Schema: session_id, app_id, worker_id, language, conversation_history, app_state

## Coding Standards

- Use `async/await` everywhere — FastAPI + SQLAlchemy async + httpx for Ollama
- Type hints on all function signatures
- Docstrings on all public methods
- No hardcoded languages — always detect or accept as parameter
- All config via environment variables (python-dotenv + .env)
- Use Pydantic models for request/response validation
- Errors return proper HTTP status codes with JSON error bodies
- Never `print()` — use `logging` module with structured output

## Testing Standards

- **Write tests BEFORE implementation** (TDD)
- Use `pytest` + `pytest-asyncio`
- Mock external services: Ollama (httpx mock), Redis (fakeredis), PostgreSQL (test schema)
- Test IDs follow convention: STT-001, LLM-001, LANG-001, VP-001, ASHA-001, AUTH-001
- Every core service needs unit tests
- Voice pipeline needs integration tests

## API Key Auth (MVP)

```python
# .env
ASHA_HEALTH_API_KEY=dev-asha-key-001
LAWYER_AI_API_KEY=dev-lawyer-key-001
```

Middleware reads X-API-Key header, maps to app_id. No JWT for MVP.

## Don't Do These Things

- Don't add app-specific logic to core/
- Don't use synchronous DB calls
- Don't hardcode model names — use config
- Don't skip error handling in the voice pipeline
- Don't load multiple large models simultaneously
- Don't use JWT/OAuth for MVP — static API keys only
- Don't build IndicTrans2 translation for MVP — stub it
- Don't build a frontend — WhatsApp is the interface
